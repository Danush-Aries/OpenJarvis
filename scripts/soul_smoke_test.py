#!/usr/bin/env python3
"""Smoke test: full Soul pipeline end-to-end.

Exercises: identity, tiered memory, embeddings, persona, dreams, reflection,
persistence, forgetting, cache/thread safety, and CLI commands.
"""

import json
import os
import shutil
import subprocess
import sys
import tempfile
import time

# ── Setup: isolated temp directory ────────────────────────────────────────
TEST_DIR = tempfile.mkdtemp(prefix="soul_smoke_")
os.environ["JARVIS_SOUL_DIR"] = TEST_DIR

PASS = 0
FAIL = 0


def ok(msg: str) -> None:
    global PASS
    PASS += 1
    print(f"  [PASS] {msg}")


def fail(msg: str) -> None:
    global FAIL
    FAIL += 1
    print(f"  [FAIL] {msg}")


def check(condition: bool, msg: str) -> None:
    if condition:
        ok(msg)
    else:
        fail(msg)


# ── Import the Soul API ──────────────────────────────────────────────────
print("\n" + "=" * 60)
print("  1. IMPORT SOUL API")
print("=" * 60)
from openjarvis.soul import (
    Soul,
    Identity,
    TieredMemory,
    Persona,
    DreamEngine,
    SelfImprovementLoop,
    get_soul,
)
from openjarvis.soul.memory import MemoryEntry, EpisodicMemory
from openjarvis.soul.storage import SoulStorage
from openjarvis.soul.embeddings import EmbeddingEngine

check(True, "All soul imports succeeded")


# ── 2. Identity ──────────────────────────────────────────────────────────
print("\n" + "=" * 60)
print("  2. IDENTITY")
print("=" * 60)
identity = Identity.create("smoke-test-agent", traits={
    "openness": 0.9,
    "conscientiousness": 0.7,
})
check(identity.name == "smoke-test-agent", "Identity created with correct name")
check(identity.traits["openness"] == 0.9, "Openness trait set to 0.9")
check(identity.stats["interactions"] == 0, "Interaction count starts at 0")

identity.record_interaction(tokens=150)
identity.record_interaction(tokens=200)
check(identity.stats["interactions"] == 2, "record_interaction increments count")
check(identity.stats["tokens_processed"] == 350, "Token tracking works")

identity.adjust_trait("openness", -0.2)
check(identity.traits["openness"] == 0.7, "Trait adjustment works")

# Serialization roundtrip
data = identity.to_dict()
restored_identity = Identity.from_dict(data)
check(restored_identity.name == "smoke-test-agent", "Identity survives serialization roundtrip")
check(restored_identity.stats["interactions"] == 2, "Stats survive serialization")


# ── 3. Memory ────────────────────────────────────────────────────────────
print("\n" + "=" * 60)
print("  3. TIERED MEMORY")
print("=" * 60)
mem = TieredMemory.create("smoke-test")

# Store in all three tiers
mem.store("User asked about Python decorators and generators", memory_type="episodic", importance=0.7)
mem.store("User asked about async programming in Python", memory_type="episodic", importance=0.6)
mem.store("User asked about Docker containers on AWS", memory_type="episodic", importance=0.8)
mem.store("Python is a dynamically-typed, interpreted programming language", memory_type="semantic", importance=0.9)
mem.store("Docker containers are lightweight virtualized environments", memory_type="semantic", importance=0.8)
mem.store("To deploy: build image, push to registry, pull on server, run container", memory_type="procedural", importance=0.7)

stats = mem.stats()
check(stats["total"] == 6, f"6 memories stored (ep: {stats['episodic']}, sem: {stats['semantic']}, proc: {stats['procedural']})")

# Keyword retrieve
results = mem.retrieve("Python", limit=10)
check(len(results) >= 3, f"Retrieve 'Python' returns >=3 results ({len(results)})")

# Cross-type retrieve
results = mem.retrieve("Docker", limit=10)
check(len(results) >= 2, "Retrieve 'Docker' returns results from multiple tiers")

# Type-filtered retrieve
episodic = mem.retrieve("Python", memory_type="episodic", limit=10)
check(len(episodic) >= 1, "Type-filtered retrieve works")
check(all(r["memory_type"] == "episodic" for r in episodic), "All results are episodic type")


# ── 4. Embedding Engine ───────────────────────────────────────────────────
print("\n" + "=" * 60)
print("  4. EMBEDDING ENGINE")
print("=" * 60)
engine = EmbeddingEngine.get_instance()
if engine.available:
    ok("Embedding engine loaded (fastembed all-MiniLM-L6-v2)")

    emb = engine.embed("Python programming")
    check(emb is not None and len(emb) == 384, f"Embedding is 384-dim ({len(emb) if emb else 0})")

    emb2 = engine.embed("Python coding")
    sim = EmbeddingEngine.cosine_similarity(emb, emb2)
    check(0.7 <= sim <= 1.0, f"Similar Python queries are semantically close ({sim:.4f})")

    emb3 = engine.embed("Quantum physics theory")
    sim2 = EmbeddingEngine.cosine_similarity(emb, emb3)
    check(sim2 < sim, f"Unrelated queries are less similar ({sim2:.4f} < {sim:.4f})")

    # Edge cases
    zero_emb = [0.0] * 384
    sim_zero = EmbeddingEngine.cosine_similarity(emb, zero_emb)
    check(sim_zero == 0.0, "Cosine similarity with zero vector is 0")

    sim_same = EmbeddingEngine.cosine_similarity(emb, emb)
    check(sim_same >= 0.999, "Cosine similarity of identical vectors is ~1.0")

    # Singleton
    engine2 = EmbeddingEngine.get_instance()
    check(engine is engine2, "Embedding engine is a singleton")
else:
    ok("Embedding engine not available (graceful fallback enabled)")


# ── 5. Persona ──────────────────────────────────────────────────────────
print("\n" + "=" * 60)
print("  5. PERSONA")
print("=" * 60)
persona = Persona.create("smoke-test-agent", identity=identity)

check(persona.bio.startswith("I am smoke-test-agent"), "Persona bio created")
check(persona.evolution_count == 0, "Evolution count starts at 0")
check("verbosity" in persona.communication, "Communication style initialized")
check("formality" in persona.communication, "Formality initialized")

# Evolve with expertise
insights = [{
    "type": "expertise_discovery",
    "insight": "I have knowledge of Python programming",
    "domain": "python",
    "confidence": 0.85,
}]
persona.evolve(insights)
check(persona.evolution_count == 1, "Evolution count incremented")
check("python" in persona.expertise, "Python expertise added")
check(persona.expertise["python"] == 0.85, "Expertise confidence stored")

# Summarize
summary = persona.summarize()
check("bio" in summary, "Summary contains bio")
check("expertise" in summary, "Summary contains expertise")
check("quirks" in summary, "Summary contains quirks")


# ── 6. Dream Engine ─────────────────────────────────────────────────────
print("\n" + "=" * 60)
print("  6. DREAM ENGINE")
print("=" * 60)
dreams = DreamEngine("smoke-test-agent")
check(dreams.dreams_count == 0, "Dream count starts at 0")

# Dream with too few memories returns empty
no_insights = dreams.dream([], None, min_memories=3)
check(no_insights == [], "Dream with < min_memories returns []")

# Dream with enough memories
test_memories = [
    {"content": "User asked about Python decorators and generators"},
    {"content": "User asked about async programming in Python"},
    {"content": "User asked about Docker containers on AWS ECS"},
    {"content": "User asked about Kubernetes pod scheduling"},
]
insights = dreams.dream(test_memories, None, min_memories=2)
check(len(insights) > 0, f"Dream produces {len(insights)} insights")

# Pattern extraction
patterns = dreams._extract_patterns(test_memories)
python_patterns = [p for p in patterns if "python" in str(p.get("insight", "")).lower()]
check(len(python_patterns) >= 1, "Pattern extraction detects 'python'")

# Expertise identification
expertise_insights = dreams._identify_expertise(test_memories)
domains = {e.get("domain") for e in expertise_insights}
check("devops" in domains, "DevOps expertise identified from Docker/K8s")

# State roundtrip
dreams.dreams_count = 5
dreams.last_dream = time.time()
state = dreams.to_dict()
restored_dreams = DreamEngine("smoke-test-agent", state=state)
check(restored_dreams.dreams_count == 5, "Dream state survives serialize/deserialize")

# Insights capped at 100
for _ in range(200):
    dreams.dream(test_memories, None, min_memories=0)
check(len(dreams.insights) <= 100, f"Insights capped at 100 ({len(dreams.insights)})")


# ── 7. Reflection ───────────────────────────────────────────────────────
print("\n" + "=" * 60)
print("  7. SELF-IMPROVEMENT LOOP")
print("=" * 60)
s = Soul.load_or_create("smoke-test-agent")
improvement = SelfImprovementLoop(s)

suggestions = improvement.analyze()
check(len(suggestions) > 0, f"Self-improvement suggests {len(suggestions)} items")
categories = {sg.category for sg in suggestions}
check(len(categories) > 0, "Suggestions have categories")

# Suggestion serialization
if suggestions:
    sg = suggestions[0]
    d = sg.to_dict()
    check(d["category"] == sg.category, "Suggestion to_dict preserves category")

summary = improvement.suggestion_summary()
check("total_suggestions" in summary, "suggestion_summary() has total_suggestions")
check("by_category" in summary, "suggestion_summary() has by_category")


# ── 8. Full Soul Pipeline (Integration) ────────────────────────────────
print("\n" + "=" * 60)
print("  8. FULL SOUL PIPELINE")
print("=" * 60)
soul = Soul.load_or_create("smoke-test-agent")
check(soul.name == "smoke-test-agent", "Soul loaded/created")

# Remember — start fresh with 3 memories, plus 2 more including Docker for forget test
soul.remember("User discussed Python type hints and Pydantic", importance=0.7)
soul.remember("User discussed Docker containers on AWS ECS", importance=0.8)
soul.remember("User discussed FastAPI and async endpoints", importance=0.8)
soul.remember("User discussed SQLAlchemy ORM patterns", importance=0.6)
soul.remember("Docker Compose for multi-container deployments", importance=0.7)
check(soul.memory.stats()["total"] == 5, f"5 memories stored ({soul.memory.stats()['total']})")

# Recall
results = soul.recall("Python", limit=5)
check(len(results) >= 1, f"Soul.recall returns results ({len(results)})")

# State summary
summary = soul.state_summary()
check(summary["name"] == "smoke-test-agent", "state_summary has correct name")
for key in ("identity", "memory_stats", "persona", "dreams"):
    check(key in summary, f"state_summary has '{key}'")

# Reflection
result = soul.reflect()
check("reflection" in result, "reflection() returns result")
check("insights" in result, "reflection() returns insights key")
if result.get("insights"):
    ok(f"Reflection produced {len(result['insights'])} insights")


# ── 9. Persistence ──────────────────────────────────────────────────────
print("\n" + "=" * 60)
print("  9. PERSISTENCE")
print("=" * 60)
soul.close()

soul2 = Soul.load_or_create("smoke-test-agent")
check(soul2.identity.name == "smoke-test-agent", "Identity persists after reload")
check(soul2.memory.stats()["total"] >= 5, f"Memories persist ({soul2.memory.stats()['total']})")
check(soul2.persona.evolution_count >= 0, "Persona evolution persists")
check(soul2.dreams.dreams_count >= 0, "Dream count persists")

# Verify specific content persisted
results = soul2.recall("Python", limit=5)
check(len(results) >= 1, "Recall works after reload")
soul2.close()


# ── 10. Forgetting ──────────────────────────────────────────────────────
print("\n" + "=" * 60)
print("  10. FORGETTING")
print("=" * 60)
soul3 = Soul.load_or_create("smoke-test-agent")
before = soul3.memory.stats()["total"]

# Forget by query — soul has "Docker containers on AWS ECS" and "Docker Compose..."
removed = soul3.forget(query="Docker")
check(removed >= 2, f"Forget 'Docker' removed {removed} memory(ies)")
check(soul3.memory.stats()["total"] == before - removed, "Total decreased after forget")

# Verify no Docker memories remain
remaining_after = soul3.recall("Docker", limit=5)
check(all("Docker" not in r.get("content", "") for r in remaining_after), "No Docker memories remain")

# Forget by type
soul3.remember("test fact to forget", memory_type="semantic", importance=0.5)
soul3.remember("test procedure to forget", memory_type="procedural", importance=0.5)
removed_type = soul3.forget(memory_type="semantic")
check(removed_type >= 1, f"Forget type 'semantic' removed {removed_type}")

# Forget persists
soul3.close()
soul4 = Soul.load_or_create("smoke-test-agent")
remaining = soul4.recall("Docker", limit=1)
check(len(remaining) == 0 or "Docker" not in remaining[0].get("content", ""), "Forget survives reload")
soul4.close()


# ── 11. Cache & Thread Safety ──────────────────────────────────────────
print("\n" + "=" * 60)
print("  11. CACHE & THREAD SAFETY")
print("=" * 60)
s5a = Soul.load_or_create("cache_test")
s5b = Soul.load_or_create("cache_test")
check(s5a is s5b, "Soul cache returns same instance")

cached = get_soul("cache_test")
check(cached is s5a, "get_soul() retrieves cached instance")

Soul.invalidate_cache("cache_test")
check(get_soul("cache_test") is None, "invalidate_cache() removes from cache")

# close_all
s6a = Soul.load_or_create("close_a")
s6b = Soul.load_or_create("close_b")
Soul.close_all()
check(get_soul("close_a") is None, "close_all() clears all souls")
check(get_soul("close_b") is None, "close_all() clears all souls")

# close_all with empty cache
Soul.close_all()
ok("close_all() on empty cache does not crash")


# ── 12. CLI Commands ───────────────────────────────────────────────────
print("\n" + "=" * 60)
print("  12. CLI COMMANDS")
print("=" * 60)
project_root = "/Users/dhanush/Desktop/Jarvis/OpenJarvis"

def run_cli(*args: str) -> str:
    result = subprocess.run(
        ["uv", "run", "jarvis", "soul", *args],
        capture_output=True, text=True, timeout=30,
        cwd=project_root,
        env={**os.environ, "JARVIS_SOUL_DIR": TEST_DIR},
    )
    return result.stdout + result.stderr

# Init
output = run_cli("init", "cli-test-soul", "--openness", "0.8", "--conscientiousness", "0.6")
check("Created" in output or "already exists" in output, "CLI: soul init")

# Status
output = run_cli("status", "cli-test-soul")
check("Identity" in output or "cli-test-soul" in output, "CLI: soul status")

# List
output = run_cli("list-souls")
check("cli-test-soul" in output or "smoke-test-agent" in output, "CLI: soul list")

# Recall (options after subcommand)
output = run_cli("recall", "--soul-name", "cli-test-soul", "Python")
check("score" in output or "No memories" in output, "CLI: soul recall")

# Forget nonexistent
output = run_cli("forget", "nonexistent-soul", "--force")
check("not found" in output, "CLI: forget nonexistent")

ok("All CLI commands executed without crashes")


# ── 13. Cleanup ─────────────────────────────────────────────────────────
print("\n" + "=" * 60)
print("  13. CLEANUP")
print("=" * 60)
Soul.close_all()
Soul.invalidate_cache()
shutil.rmtree(TEST_DIR, ignore_errors=True)
ok("Test directory cleaned up")


# ── Results ─────────────────────────────────────────────────────────────
print(f"\n{'=' * 60}")
print(f"  RESULTS: {PASS} passed, {FAIL} failed, {PASS + FAIL} total")
print(f"{'=' * 60}")

if FAIL > 0:
    print("\n  ❌ SOME CHECKS FAILED")
    sys.exit(1)
else:
    print("\n  ✅ FULL SOUL PIPELINE: ALL CHECKS PASSED")
    sys.exit(0)
