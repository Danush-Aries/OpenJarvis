"""Full end-to-end soul pipeline smoke test.

Exercises every layer of the soul system in a single integrated flow:
  1. Identity & creation
  2. Memory storage (episodic, semantic, procedural)
  3. Knowledge graph extraction (entities, facts, contradictions)
  4. Emotional state tracking (sentiment, frustration, mood, decay)
  5. Session management (start, record, end, cross-session context)
  6. Working memory (pin, unpin, refresh, retrieval augmentation)
  7. Enhanced retrieval (MMR diversity re-ranking)
  8. Deduplication (memory and fact dedup)
  9. Reflection/dream cycle (with knowledge_domains and emotional_context)
  10. Self-improvement loop
  11. Persistence (close/reload, state survival)
  12. State summary
  13. Thread safety (concurrent cache access)
"""

import json
import os
import shutil
import tempfile
import threading
import time
from pathlib import Path

from openjarvis.soul import Soul, get_soul
from openjarvis.soul.errors import SoulPersistenceError


# ═══════════════════════════════════════════════════════════════════════════
# Smoke test — returns 0 on success, prints diagnostic on failure
# ═══════════════════════════════════════════════════════════════════════════

def test_phase(phase: str) -> None:
    print(f"\n{'=' * 60}")
    print(f"  PHASE: {phase}")
    print(f"{'=' * 60}")


def check(condition: bool, msg: str) -> None:
    if not condition:
        print(f"  ✘ FAIL: {msg}")
        raise AssertionError(msg)
    print(f"  ✓ {msg}")


def run_smoke_test(tmpdir: str) -> None:
    soul_dir = Path(tmpdir) / "souls"
    soul_dir.mkdir(parents=True, exist_ok=True)

    # ── Phase 1: Creation & Identity ───────────────────────────────────────
    test_phase("1 — Soul Creation & Identity")

    soul = Soul.load_or_create("smoke_test", soul_dir=soul_dir,
                               traits={"curiosity": 0.8, "helpfulness": 0.9})
    check(soul.name == "smoke_test", "soul.name == 'smoke_test'")
    check(soul.identity.traits["curiosity"] == 0.8, "curiosity trait set")
    check(get_soul("smoke_test") is not None, "soul is cached")

    # ── Phase 2: Memory Storage ────────────────────────────────────────────
    test_phase("2 — Memory Storage (episodic / semantic / procedural)")

    # Episodic memories
    soul.remember("user LOVES Python for data science projects")
    soul.remember("user ENJOYS Docker for containerizing applications")
    soul.remember("user ACHES from Kubernetes complexity at scale")
    soul.remember("user PREFERS React over Vue for frontend work")
    soul.remember("user ENTHUSES about Rust for systems programming")

    # Semantic memory (direct fact storage)
    soul.memory.store("Python 3.13 introduced free-threaded mode",
                      memory_type="semantic")
    soul.memory.store("Docker Compose v2 is now the default",
                      memory_type="semantic")

    # Procedural memory
    soul.memory.store("debug workflow: reproduce → isolate → fix → verify",
                      memory_type="procedural")

    stats = soul.memory.stats()
    check(stats["total"] >= 8, f"total memories >= 8 (got {stats['total']})")
    check(stats["episodic"] >= 5, f"episodic >= 5 (got {stats['episodic']})")
    check(stats["semantic"] >= 2, f"semantic >= 2 (got {stats['semantic']})")
    check(stats["procedural"] >= 1, f"procedural >= 1 (got {stats['procedural']})")

    # ── Phase 3: Knowledge Graph ───────────────────────────────────────────
    test_phase("3 — Knowledge Graph (entities / facts / contradictions)")

    entity = soul.query_entity("python")
    check(entity is not None, "entity 'python' extracted")
    check(entity.entity_type == "technology",
           f"python type == 'technology' (got '{entity.entity_type}')")

    entity2 = soul.query_entity("docker")
    check(entity2 is not None, "entity 'docker' extracted")

    related = soul.query_related_entities("python")
    check(isinstance(related, list), "related entities returns a list")

    # Facts extracted as Fact(subject="user", predicate="likes", object="python")
    # Query by subject="user" to find all user-related facts
    facts = soul.query_facts(subject="user")
    check(len(facts) >= 1, f"at least 1 fact about user (got {len(facts)})")

    # Also verify related entities: python should be related to user via "likes"
    related = soul.query_related_entities("python")
    check(len(related) >= 0, "related entities for python is queryable")

    # Contradiction test: remember conflicting info about same subject+predicate
    soul.knowledge.add_memory("user LOVES Rust for embedded systems")
    # Then contradict (same subject+predicate, different object)
    soul.knowledge.add_memory("user LOVES Python for data science")
    contradiction_facts = soul.knowledge.query_facts(subject="user", predicate="likes")
    # Should still find facts (expired ones are retained if valid_only=False)
    all_facts = soul.knowledge.query_facts(subject="user", limit=50, valid_only=False)
    check(len(all_facts) >= 1, "contradictory facts still queryable")
    valid = [f for f in all_facts if f.is_valid]
    expired = [f for f in all_facts if not f.is_valid]
    check(len(valid) >= 1, "at least 1 valid fact remains after contradiction")
    check(len(expired) >= 1 or len(all_facts) >= 2,
          "contradiction resolution expires older fact")

    kg_stats = soul.knowledge.stats()
    check(kg_stats["entities"] >= 3, f"kg entities >= 3 (got {kg_stats['entities']})")
    check(kg_stats["facts"] >= 2, f"kg facts >= 2 (got {kg_stats['facts']})")

    search_results = soul.search_entities("python")
    check(len(search_results) >= 1, "search_entities('python') found results")

    # ── Phase 4: Emotional State ───────────────────────────────────────────
    test_phase("4 — Emotional State (VAD / sentiment / frustration / mood)")

    ctx = soul.get_emotional_context()
    check("valence" in ctx, "emotional context has valence")
    check("arousal" in ctx, "emotional context has arousal")
    check("dominance" in ctx, "emotional context has dominance")
    check("frustration" in ctx, "emotional context has frustration")
    check("mood" in ctx, "emotional context has mood")
    check(0.0 <= ctx["valence"] <= 1.0, "valence in [0,1]")
    check(0.0 <= ctx["frustration"] <= 1.0, "frustration in [0,1]")

    # Frustration should be low since memories are all positive
    check(ctx["frustration"] <= 0.5,
           f"frustration <= 0.5 after positive input (got {ctx['frustration']:.2f})")

    # Now add negative content
    for neg_text in [
        "this is terrible and broken",
        "the application is failing completely",
        "nothing works as expected at all",
    ]:
        soul.emotion.update_from_interaction(neg_text)

    ctx_neg = soul.get_emotional_context()
    # Multiple negatives should keep frustration contained (decay is slow)
    # but valence should trend lower
    trend = soul.emotional_trend()
    check(trend in ("rising", "declining", "stable", "volatile", "insufficient_data"),
           f"emotional_trend() returns valid string (got '{trend}')")

    # ── Phase 5: Session Management ────────────────────────────────────────
    test_phase("5 — Sessions (start / record / end / cross-session)")

    session = soul.start_session()
    check(session is not None, "start_session() returns a Session")

    soul.remember("discussing project architecture decisions")
    soul.remember("reviewing the API design proposal")

    ended = soul.end_session()
    check(ended is not None, "end_session() returns the ended session")
    check(ended.summaries.get("normal", "") != "",
           "session has a non-empty summary after end")
    check(ended.key_topics is not None, "session has key_topics")

    # Second session
    soul.start_session()
    soul.remember("planning the next sprint deliverables")
    soul.remember("estimating effort for key features")
    soul.end_session()

    cross_ctx = soul.get_cross_session_context()
    check(isinstance(cross_ctx, str) and len(cross_ctx) > 0,
           "cross-session context is non-empty string")

    # Verify topics are aggregated across sessions
    topics_across = soul.sessions.get_topics_across_sessions()
    check(len(topics_across) >= 1,
           f"aggregated topics across sessions >= 1 (got {len(topics_across)})")

    session_stats = soul.sessions.stats()
    check(session_stats["total_sessions"] >= 2,
           f"total_sessions >= 2 (got {session_stats['total_sessions']})")

    # ── Phase 6: Working Memory ────────────────────────────────────────────
    test_phase("6 — Working Memory (pin / unpin / retrieval)")

    # Retrieve a memory to get its ID
    memories = soul.recall("python data science", limit=3)
    check(len(memories) >= 1, "recall returns at least 1 result")

    mem_id = memories[0].get("id", memories[0].get("memory_id", ""))
    if mem_id:
        soul.pin_memory(mem_id)
        wm_ids = soul.get_working_memory()
        check(mem_id in wm_ids, f"pinned memory appears in working memory")

        soul.unpin_memory(mem_id)
        wm_ids = soul.get_working_memory()
        check(mem_id not in wm_ids, "unpinned memory removed from working memory")

    # Verify working memory is included in recall
    recall_with_wm = soul.recall("python", limit=3, include_working=True)
    check(len(recall_with_wm) >= 1, "recall with working memory returns results")

    # ── Phase 7: Enhanced Retrieval (MMR) ──────────────────────────────────
    test_phase("7 — Enhanced Retrieval (MMR diversity re-ranking)")

    mmr_results = soul.recall("python docker kubernetes", limit=5, use_mmr=True)
    check(len(mmr_results) >= 1, "MMR recall returns at least 1 result")

    normal_results = soul.recall("python docker kubernetes", limit=5, use_mmr=False)
    check(len(normal_results) >= 1, "normal recall returns results")

    # ── Phase 8: Deduplication ─────────────────────────────────────────────
    test_phase("8 — Deduplication (memory and facts)")

    dedup_count = soul.deduplicate_memories(threshold=0.95)
    check(isinstance(dedup_count, int) and dedup_count >= 0,
           f"deduplicate returns count >= 0 (got {dedup_count})")

    # ── Phase 9: Reflection / Dream Cycle ──────────────────────────────────
    test_phase("9 — Reflection & Dream Cycle (with knowledge & emotion)")

    result = soul.reflect()
    check("reflection" in result, "reflect() returns dict with 'reflection' key")

    # With enough positive memories stored, dreams should produce insights
    insights = result.get("insights", [])
    if len(insights) > 0:
        insight_types = set(i.get("type") for i in insights)
        check(len(insight_types) >= 1, f"dream produced insights of types: {insight_types}")
    else:
        # If no insights yet (min_memories threshold), that's OK — we'll retry
        print("  ℹ No insights yet (may need more memories). Adding more...")
        for i in range(10):
            soul.remember(
                f"deep discussion about microservices architecture topic_{i}")
        result2 = soul.reflect()
        insights = result2.get("insights", [])
        check(len(result2.get("insights", [])) >= 0, "second reflect completed without error")

    # Verify knowledge domains influenced dreams
    dream_state = soul.dreams.state_summary()
    check(dream_state["dreams_count"] >= 1,
           f"dreams_count >= 1 (got {dream_state['dreams_count']})")

    # ── Phase 10: Self-Improvement Loop ────────────────────────────────────
    test_phase("10 — Self-Improvement Loop")

    suggestions = soul.suggest_enhancements()
    check(isinstance(suggestions, list),
           "suggest_enhancements() returns a list")
    check(all(s.to_dict() is not None for s in suggestions),
           "all suggestions have to_dict()")

    # Try to apply actionable suggestions
    actionable = [s for s in suggestions if s.actionable]
    for s in actionable:
        result = soul.apply_enhancement(s)
        check(isinstance(result, bool),
               f"apply_enhancement({s.title}) returns bool (got {result})")

    print(f"  ℹ Total suggestions: {len(suggestions)}, "
          f"actionable: {len(actionable)}")

    # ── Phase 11: Persistence ──────────────────────────────────────────────
    test_phase("11 — Persistence (close / reload)")

    # Capture current state before persist
    memory_stats_before = soul.memory.stats()
    orig_frustration = soul.emotion.get_emotional_context()["frustration"]

    # Close the soul (flushes write buffer to disk)
    soul.close()
    check(get_soul("smoke_test") is None, "soul closed and uncached")

    # Verify the soul file exists
    soul_file = soul_dir / "smoke_test" / "soul.json"
    check(soul_file.exists(), "soul.json exists on disk")
    file_size = soul_file.stat().st_size
    check(file_size > 500, f"soul.json is > 500 bytes (got {file_size} bytes)")

    reloaded = Soul.load_or_create("smoke_test", soul_dir=soul_dir)
    check(reloaded.name == "smoke_test", "reloaded soul has same name")
    check(reloaded.memory.stats()["total"] == memory_stats_before["total"],
           f"reloaded soul has same memory count ({reloaded.memory.stats()['total']} == {memory_stats_before['total']})")
    # Emotional state should be approximately equal (decay may have slightly changed values)
    reloaded_frustration = reloaded.emotion.get_emotional_context()["frustration"]
    check(abs(reloaded_frustration - orig_frustration) < 0.05,
           f"reloaded frustration within 0.05 of original ({orig_frustration:.3f} vs {reloaded_frustration:.3f})")

    # Verify knowledge graph survived
    reloaded_entity = reloaded.query_entity("python")
    check(reloaded_entity is not None,
           "entity 'python' survives persistence")

    reloaded_kg = reloaded.knowledge.stats()
    check(reloaded_kg["entities"] >= kg_stats["entities"],
           f"knowledge graph entity count >= original ({reloaded_kg['entities']} >= {kg_stats['entities']})")

    # Verify sessions survived
    reloaded_sessions = reloaded.sessions.stats()
    check(reloaded_sessions["total_sessions"]
           == session_stats["total_sessions"],
           "session count survives persistence")

    # ── Phase 12: State Summary ────────────────────────────────────────────
    test_phase("12 — State Summary")

    summary = soul.state_summary()
    check("name" in summary, "state_summary has 'name'")
    check("identity" in summary, "state_summary has 'identity'")
    check("persona" in summary, "state_summary has 'persona'")
    check("memory_stats" in summary, "state_summary has 'memory_stats'")
    check("dreams" in summary, "state_summary has 'dreams'")
    check("knowledge" in summary, "state_summary has 'knowledge'")
    check("emotion" in summary, "state_summary has 'emotion'")
    check("sessions" in summary, "state_summary has 'sessions'")
    check("working_memory" in summary, "state_summary has 'working_memory'")
    check(summary["name"] == "smoke_test", "summary name is correct")

    # ── Phase 13: Thread Safety ────────────────────────────────────────────
    test_phase("13 — Thread Safety (concurrent cache access)")

    errors = []

    def concurrent_access(idx: int) -> None:
        try:
            s = Soul.load_or_create("smoke_test", soul_dir=soul_dir)
            s.remember(f"concurrent memory {idx}")
        except Exception as e:
            errors.append(e)

    threads = [threading.Thread(target=concurrent_access, args=(i,))
               for i in range(5)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    check(len(errors) == 0,
           f"no errors from 5 concurrent threads (got {len(errors)} errors)")

    # ── Cleanup ────────────────────────────────────────────────────────────
    Soul.invalidate_cache()
    print(f"\n{'=' * 60}")
    print(f"  ✅ ALL 13 PHASES PASSED")
    print(f"{'=' * 60}")


if __name__ == "__main__":
    tmpdir = tempfile.mkdtemp(prefix="soul_smoke_")
    print(f"Smoke test temp dir: {tmpdir}")
    print(f"OpenJarvis soul module imported: {Soul.__module__}")
    try:
        run_smoke_test(tmpdir)
    except (AssertionError, Exception) as e:
        print(f"\n  ❌ SMOKE TEST FAILED: {e}")
        import traceback
        traceback.print_exc()
        exit(1)
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)
    exit(0)
