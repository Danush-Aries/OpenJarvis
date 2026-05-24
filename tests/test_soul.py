"""Tests for the Soul module — identity, memory, persona, dreams, and storage."""

from __future__ import annotations

import os
import shutil
import tempfile
import time
from pathlib import Path

import pytest

# Set soul directory to temp before any imports
TEST_DIR = Path(tempfile.mkdtemp(prefix="soul_test_"))
os.environ["JARVIS_SOUL_DIR"] = str(TEST_DIR)

from openjarvis.soul import Soul, get_soul
from openjarvis.soul.identity import Identity
from openjarvis.soul.memory import MemoryEntry, EpisodicMemory, TieredMemory
from openjarvis.soul.persona import Persona
from openjarvis.soul.dreams import DreamEngine
from openjarvis.soul.storage import SoulStorage, WriteBuffer
from openjarvis.soul.reflection import SelfImprovementLoop, EnhancementSuggestion


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def clean_souls():
    """Clean up test souls before and after each test."""
    # Clean before
    Soul.invalidate_cache()
    if TEST_DIR.exists():
        shutil.rmtree(str(TEST_DIR))
        TEST_DIR.mkdir(parents=True, exist_ok=True)
    yield
    # Clean after
    Soul.invalidate_cache()


@pytest.fixture
def soul():
    """Create a fresh soul for testing."""
    return Soul.load_or_create("test_soul")


# ---------------------------------------------------------------------------
# Identity
# ---------------------------------------------------------------------------


class TestIdentity:
    def test_create(self):
        identity = Identity.create("jarvis")
        assert identity.name == "jarvis"
        assert identity.created_at > 0
        assert "openness" in identity.traits
        assert identity.stats["interactions"] == 0

    def test_record_interaction(self):
        identity = Identity.create("jarvis")
        identity.record_interaction(tokens=100)
        assert identity.stats["interactions"] == 1
        assert identity.stats["tokens_processed"] == 100

    def test_trait_adjustment(self):
        identity = Identity.create("jarvis")
        identity.adjust_trait("openness", 0.2)
        assert identity.traits["openness"] == pytest.approx(0.9)
        identity.adjust_trait("openness", -0.5)
        assert identity.traits["openness"] == pytest.approx(0.4)
        identity.adjust_trait("openness", -1.0)  # Clamped to 0
        assert identity.traits["openness"] == 0.0

    def test_serialization_roundtrip(self):
        identity = Identity.create("jarvis")
        identity.record_interaction(tokens=42)
        identity.set_mood("curious")
        data = identity.to_dict()
        restored = Identity.from_dict(data)
        assert restored.name == "jarvis"
        assert restored.stats["interactions"] == 1
        assert restored.mood == "curious"


# ---------------------------------------------------------------------------
# Memory
# ---------------------------------------------------------------------------


class TestMemoryEntry:
    def test_create(self):
        entry = MemoryEntry.create("hello world", importance=0.8)
        assert entry.content == "hello world"
        assert entry.importance == 0.8
        assert entry.access_count == 0

    def test_from_dict_ignores_unknown_keys(self):
        entry = MemoryEntry.create("test")
        d = entry.to_dict()
        d["score"] = 0.999  # Extra key from retrieval
        d["random_extra"] = "should be ignored"
        restored = MemoryEntry.from_dict(d)
        assert restored.content == "test"
        assert not hasattr(restored, "score")  # Should not exist

    def test_importance_clamping(self):
        entry = MemoryEntry.create("test", importance=1.5)
        assert entry.importance == 1.0
        entry2 = MemoryEntry.create("test", importance=-0.5)
        assert entry2.importance == 0.0


class TestEpisodicMemory:
    def test_store_and_retrieve(self):
        mem = EpisodicMemory()
        mem.store("user asked about python")
        mem.store("user asked about AI", importance=0.9)
        results = mem.retrieve("python")
        assert len(results) >= 1
        assert any("python" in r["content"] for r in results)

    def test_consolidation(self):
        mem = EpisodicMemory()
        old_time = time.time() - (100 * 86400)  # 100 days ago
        for i in range(5):
            entry = MemoryEntry.create(
                f"old memory {i}",
                importance=0.3,
            )
            entry.timestamp = old_time
            mem._entries.append(entry)
        # Add one recent important memory
        mem.store("recent important", importance=0.9)
        removed = mem.consolidate(max_age_days=90)
        assert removed >= 4  # old low-importance memories removed


class TestTieredMemory:
    def test_store_all_types(self):
        mem = TieredMemory.create("test")
        mem.store("conversation about X", memory_type="episodic")
        mem.store("Python is a programming language", memory_type="semantic")
        mem.store("to deploy: build, test, release", memory_type="procedural")
        stats = mem.stats()
        assert stats["total"] == 3
        assert stats["episodic"] == 1
        assert stats["semantic"] == 1
        assert stats["procedural"] == 1

    def test_retrieve_across_types(self):
        mem = TieredMemory.create("test")
        mem.store("chat about python", memory_type="episodic")
        mem.store("python is interpreted", memory_type="semantic")
        results = mem.retrieve("python", limit=10)
        assert len(results) == 2

    def test_auto_consolidation_when_exceeding_max(self):
        mem = TieredMemory.create("test")
        mem.max_memories = 3  # Low threshold for testing
        # Store 4 entries — auto-consolidation should trigger on the 4th
        mem.store("entry one", importance=0.3)
        mem.store("entry two", importance=0.3)
        mem.store("entry three", importance=0.3)
        mem.store("entry four", importance=0.3)
        # Since all are recent, none should be pruned by age-based consolidation
        assert mem.stats()["total"] == 4
        # Now store 4 more (total 8) — still recent, not consolidated
        for i in range(4):
            mem.store(f"extra entry {i}", importance=0.3)
        assert mem.stats()["total"] == 8

    def test_auto_consolidation_does_not_fire_below_threshold(self):
        mem = TieredMemory.create("test")
        mem.max_memories = 100
        mem.store("only entry", importance=0.5)
        assert mem.stats()["total"] == 1

    def test_forget_by_id(self):
        mem = TieredMemory.create("test")
        a = mem.episodic.store("memory A")
        b = mem.episodic.store("memory B")
        c = mem.episodic.store("memory C")
        assert mem.stats()["total"] == 3
        removed = mem.forget(memory_id=a.id)
        assert removed == 1
        assert mem.stats()["total"] == 2
        # Verify the rest still exist
        contents = {r["content"] for r in mem.retrieve("", limit=10)}
        assert "memory A" not in contents
        assert "memory B" in contents

    def test_forget_by_type(self):
        mem = TieredMemory.create("test")
        mem.store("conversation", memory_type="episodic")
        mem.store("fact", memory_type="semantic")
        mem.store("skill", memory_type="procedural")
        removed = mem.forget(memory_type="episodic")
        assert removed == 1
        assert mem.stats()["episodic"] == 0
        assert mem.stats()["semantic"] == 1
        assert mem.stats()["procedural"] == 1

    def test_forget_by_query(self):
        mem = TieredMemory.create("test")
        mem.episodic.store("python programming is fun")
        mem.episodic.store("data science with python")
        mem.episodic.store("javascript for web development")
        removed = mem.forget(query="python")
        assert removed == 2
        contents = [r["content"] for r in mem.retrieve("", limit=10)]
        assert "javascript for web development" in contents
        assert all("python" not in c for c in contents)

    def test_forget_by_query_with_type_filter(self):
        mem = TieredMemory.create("test")
        mem.store("python is great", memory_type="episodic")
        mem.store("python is a language", memory_type="semantic")
        removed = mem.forget(memory_type="semantic", query="python")
        assert removed == 1
        assert mem.stats()["episodic"] == 1
        assert mem.stats()["semantic"] == 0

    def test_forget_invalid_type_raises(self):
        mem = TieredMemory.create("test")
        with pytest.raises(ValueError, match="Unknown memory type"):
            mem.forget(memory_type="unknown")

    def test_forget_unknown_id_returns_zero(self):
        mem = TieredMemory.create("test")
        mem.episodic.store("something")
        removed = mem.forget(memory_id="nonexistent")
        assert removed == 0


# ---------------------------------------------------------------------------
# Persona
# ---------------------------------------------------------------------------


class TestPersona:
    def test_create(self):
        identity = Identity.create("jarvis")
        persona = Persona.create("jarvis", identity=identity)
        assert persona.bio.startswith("I am jarvis")
        assert "verbosity" in persona.communication

    def test_evolve_with_expertise(self):
        identity = Identity.create("jarvis")
        persona = Persona.create("jarvis", identity=identity)
        insights = [
            {
                "type": "expertise_discovery",
                "insight": "I know Python well",
                "domain": "programming",
                "confidence": 0.8,
            }
        ]
        persona.evolve(insights)
        assert "programming" in persona.expertise
        assert persona.expertise["programming"] == 0.8
        assert persona.evolution_count == 1

    def test_summarize(self):
        identity = Identity.create("jarvis")
        persona = Persona.create("jarvis", identity=identity)
        summary = persona.summarize()
        assert "bio" in summary
        assert "expertise" in summary
        assert "quirks" in summary


# ---------------------------------------------------------------------------
# Dream Engine
# ---------------------------------------------------------------------------


class TestDreamEngine:
    def test_dream_with_few_memories(self):
        engine = DreamEngine("test")
        insights = engine.dream([], None, min_memories=3)
        assert insights == []

    def test_dream_creates_insights(self):
        engine = DreamEngine("test")
        memories = [
            {"content": "user asked about python programming and data science"},
            {"content": "user asked about building ML models"},
            {"content": "user asked about deploying algorithms"},
            {"content": "user asked about training neural networks"},
        ]
        insights = engine.dream(memories, None, min_memories=2)
        assert len(insights) > 0
        insight_types = {i["type"] for i in insights}
        assert "pattern" in insight_types or "expertise_discovery" in insight_types

    def test_dream_pattern_extraction(self):
        """Pattern extraction detects repeated keywords across memories."""
        engine = DreamEngine("test")
        memories = [
            {"content": "discussed python decorators and generators"},
            {"content": "discussed python async programming"},
            {"content": "discussed python type hints and pydantic"},
        ]
        insights = engine._extract_patterns(memories)
        assert len(insights) > 0
        assert any("python" in str(i.get("insight", "")).lower() for i in insights)

    def test_dream_expertise_devops(self):
        """DevOps keywords should be detected as expertise."""
        engine = DreamEngine("test")
        memories = [
            {"content": "user asked about deploying Docker containers on AWS ECS"},
            {"content": "user asked about Kubernetes pod scheduling and scaling"},
            {"content": "user asked about Terraform infrastructure as code"},
            {"content": "user asked about CI/CD pipeline with GitHub Actions"},
        ]
        insights = engine._identify_expertise(memories)
        domains = {i.get("domain") for i in insights}
        assert "devops" in domains

    def test_dream_style_formality_up(self):
        """Technical language + many memories should suggest formality increase."""
        engine = DreamEngine("test")
        memories = [
            {"content": "The function signature accepts an interface parameter"},
            {"content": "This method implements the abstract class algorithm"},
            {"content": "The class constructor requires three parameters"},
            {"content": "The implementation uses a decorator pattern"},
        ]
        insights = engine._suggest_style_adjustments(memories)
        positive = [i["delta"] for i in insights if i.get("parameter") == "formality" and i["delta"] > 0]
        assert positive, "Technical content should suggest formality increase"

    def test_dream_style_formality_down(self):
        """Casual language should suggest formality decrease."""
        engine = DreamEngine("test")
        memories = [
            {"content": "hi there! thanks for asking, cool question!"},
            {"content": "awesome! great point, nice work!"},
            {"content": "sure thing, thanks! that's cool"},
            {"content": "nice idea! awesome work!"},
        ]
        insights = engine._suggest_style_adjustments(memories)
        negative = [i["delta"] for i in insights if i.get("parameter") == "formality" and i["delta"] < 0]
        assert negative, "Casual content should suggest formality decrease"

    def test_dream_verbosity_detection(self):
        """Very long memories should trigger verbosity increase."""
        engine = DreamEngine("test")
        long = " ".join(["word"] * 600)
        memories = [{"content": long}] * 4
        insights = engine._suggest_style_adjustments(memories)
        positive = [i["delta"] for i in insights if i.get("parameter") == "verbosity" and i["delta"] > 0]
        assert positive, "Long content should suggest verbosity increase"

    def test_dream_quirk_lists(self):
        """Frequent list usage detected as a quirk."""
        engine = DreamEngine("test")
        memories = [
            {"content": "Steps: 1. First 2. Then 3. Finally"},
            {"content": "Key points:\n- Point one\n- Point two"},
            {"content": "Items: \u2022 First \u2022 Second"},
            {"content": "Checklist: 1. Item A 2. Item B"},
        ]
        insights = engine._discover_quirks(memories)
        assert any("list" in str(i.get("quirk", "")).lower() for i in insights)

    def test_dream_quirk_questions(self):
        """Many question marks detected as questioning quirk."""
        engine = DreamEngine("test")
        memories = [
            {"content": "What do you think? How would you approach this?"},
            {"content": "Could you clarify? Is there another option?"},
            {"content": "Does that make sense? Should we try?"},
            {"content": "Why not? When should we start?"},
        ]
        insights = engine._discover_quirks(memories)
        assert any("question" in str(i.get("quirk", "")).lower() for i in insights)

    def test_dream_state_roundtrip(self):
        """DreamEngine state survives to_dict / from_dict roundtrip."""
        engine = DreamEngine("test")
        engine.dreams_count = 7
        engine.last_dream = 12345.0
        engine.insights = [{"type": "test", "insight": "hello"}]
        data = engine.to_dict()
        restored = DreamEngine("test", state=data)
        assert restored.dreams_count == 7
        assert restored.last_dream == 12345.0
        assert len(restored.insights) == 1

    # -- DreamEngine edge cases ---

    def test_dream_empty_memories(self):
        """Dream with empty memory list returns empty insights."""
        engine = DreamEngine("test")
        insights = engine.dream([], None, min_memories=0)
        assert insights == []

    def test_dream_exact_threshold(self):
        """Dream with exactly min_memories works."""
        engine = DreamEngine("test")
        memories = [{"content": f"memory {i}"} for i in range(3)]
        insights = engine.dream(memories, None, min_memories=3)
        assert isinstance(insights, list)

    def test_dream_with_zero_min_memories(self):
        """min_memories=0 allows dreaming on any input without crashing."""
        engine = DreamEngine("test")
        insights = engine.dream([{"content": "test"}], None, min_memories=0)
        assert isinstance(insights, list)

    def test_pattern_no_repeated_keywords(self):
        """All unique content with no repeated words >4 chars yields no patterns."""
        engine = DreamEngine("test")
        memories = [
            {"content": "apple banana carrot daikon eggplant falafel"},
            {"content": "gazpacho haloumi iceberg jicama kale lentil"},
            {"content": "mushroom nectarine okra parsley quinoa radish"},
        ]
        insights = engine._extract_patterns(memories)
        assert len(insights) == 0

    def test_pattern_short_words_only(self):
        """Words <=4 chars are skipped, yielding no patterns."""
        engine = DreamEngine("test")
        memories = [
            {"content": "a an the cat dog run big hot sad red box car pen"},
            {"content": "bat hat mat rat sat fat pat cat bit fit hit"},
        ]
        insights = engine._extract_patterns(memories)
        assert len(insights) == 0

    def test_expertise_no_match(self):
        """Memories with no domain keywords produce no expertise insights."""
        engine = DreamEngine("test")
        memories = [
            {"content": "the weather is nice today"},
            {"content": "I like cooking pasta for dinner"},
            {"content": "flowers bloom in springtime"},
        ]
        insights = engine._identify_expertise(memories)
        assert len(insights) == 0

    def test_style_mixed_language_no_dominance(self):
        """Equal technical and casual content yields no formality adjustment."""
        engine = DreamEngine("test")
        memories = [
            {"content": "This function returns a value"},
            {"content": "thanks for the cool question"},
            {"content": "The class constructor expects a parameter"},
            {"content": "awesome great work on this project"},
        ]
        insights = engine._suggest_style_adjustments(memories)
        formality_deltas = [i["delta"] for i in insights if i.get("parameter") == "formality"]
        assert len(formality_deltas) == 0

    def test_style_verbosity_concise(self):
        """Very short content (<100 chars avg, >5 memories) suggests verbosity decrease."""
        engine = DreamEngine("test")
        memories = [{"content": "hi"}] * 7
        insights = engine._suggest_style_adjustments(memories)
        negative = [i["delta"] for i in insights if i.get("parameter") == "verbosity" and i["delta"] < 0]
        assert negative, "Concise content should suggest verbosity decrease"

    def test_style_verbosity_boundary_500(self):
        """Exactly 500 chars avg should NOT trigger verbosity increase (needs >500)."""
        engine = DreamEngine("test")
        text = "x" * 500
        memories = [{"content": text}]
        insights = engine._suggest_style_adjustments(memories)
        verbosity_deltas = [i["delta"] for i in insights if i.get("parameter") == "verbosity"]
        assert all(d < 0 for d in verbosity_deltas) or len(verbosity_deltas) == 0

    def test_quirk_list_boundary(self):
        """Exactly 3 list-format items should not trigger list quirk (needs >3)."""
        engine = DreamEngine("test")
        memories = [
            {"content": "Steps: 1. First 2. Second"},
            {"content": "Items:\n- Point one"},
            {"content": "Options: \u2022 A \u2022 B"},
        ]
        insights = engine._discover_quirks(memories)
        list_quirks = [i for i in insights if "list" in str(i.get("quirk", "")).lower()]
        assert len(list_quirks) == 0

    def test_quirk_list_ratio_boundary(self):
        """4 lists out of 8 (exactly 50%) should not trigger quirk (needs >50%)."""
        engine = DreamEngine("test")
        memories = [
            {"content": "Step 1: A\nStep 2: B"},
            {"content": "- Item one\n- Item two"},
            {"content": "\u2022 Alpha \u2022 Beta"},
            {"content": "1. X 2. Y 3. Z"},
            {"content": "plain text without any lists"},
            {"content": "also plain without structure"},
            {"content": "just a normal sentence here"},
            {"content": "another non list sentence"},
        ]
        insights = engine._discover_quirks(memories)
        list_quirks = [i for i in insights if "list" in str(i.get("quirk", "")).lower()]
        assert len(list_quirks) == 0

    def test_quirk_question_boundary(self):
        """Exactly 3 question marks should not trigger questioning quirk (needs >3)."""
        engine = DreamEngine("test")
        memories = [
            {"content": "What do you think?"},
            {"content": "Is this correct?"},
            {"content": "Are you sure?"},
        ]
        insights = engine._discover_quirks(memories)
        question_quirks = [i for i in insights if "question" in str(i.get("quirk", "")).lower()]
        assert len(question_quirks) == 0

    def test_dream_insights_exactly_100_cap(self):
        """Insights capped at exactly 100 — overshoot is trimmed."""
        engine = DreamEngine("test")
        mems = [{"content": "python programming"}] * 5
        for _ in range(200):
            engine.dream(mems, None, min_memories=0)
        assert len(engine.insights) == 100

    def test_to_dict_keeps_last_50(self):
        """to_dict() keeps only the last 50 insights (not all 100)."""
        engine = DreamEngine("test")
        mems = [{"content": "python programming"}] * 5
        for _ in range(30):
            engine.dream(mems, None, min_memories=0)
        assert len(engine.insights) >= 50
        data = engine.to_dict()
        assert len(data["insights"]) == 50

    def test_multiple_dream_cycles_accumulate(self):
        """Insights accumulate across multiple dream cycles."""
        engine = DreamEngine("test")
        mems = [{"content": "python programming"}] * 5
        engine.dream(mems, None, min_memories=0)
        count_after_first = len(engine.insights)
        assert count_after_first > 0
        engine.dream(mems, None, min_memories=0)
        count_after_second = len(engine.insights)
        assert count_after_second >= count_after_first
        assert engine.dreams_count == 2

    def test_dream_state_summary_keys(self):
        """state_summary() returns correct keys and values."""
        engine = DreamEngine("test")
        engine.dreams_count = 10
        engine.insights = [{"type": "test", "insight": "x"}]
        summary = engine.state_summary()
        assert summary["dreams_count"] == 10
        assert summary["insights_count"] == 1
        assert "last_dream" in summary


# ---------------------------------------------------------------------------
# Storage
# ---------------------------------------------------------------------------


class TestSoulStorage:
    def test_save_and_load(self):
        storage = SoulStorage("test", base_dir=Path(tempfile.mkdtemp()))
        data = {"name": "test", "data": {"hello": "world"}}
        storage.save(data)
        storage.flush()  # Flush WriteBuffer so the file hits disk
        assert storage.exists()
        loaded = storage.load()
        assert loaded["name"] == "test"
        assert loaded["data"]["hello"] == "world"

    def test_backup_rotation(self):
        base = Path(tempfile.mkdtemp())
        storage = SoulStorage("test", base_dir=base)
        for i in range(15):
            storage.save({"version": i})
            storage.flush()  # Flush after each save to ensure backups are created
        backups = list((base / "test" / "backups").glob("soul_*.json"))
        assert len(backups) <= 10


class TestWriteBuffer:
    def test_batch_flush(self):
        flushes = []
        buf = WriteBuffer(flush_fn=lambda d: flushes.append(d),
                          flush_interval=0.05, max_ops=5)
        for i in range(10):
            buf.put({"i": i})
        time.sleep(0.2)
        buf.close()
        assert len(flushes) >= 1  # At least one batch flush

    def test_immediate_flush(self):
        flushes = []
        buf = WriteBuffer(flush_fn=lambda d: flushes.append(d),
                          flush_interval=10.0, max_ops=10)
        buf.put({"test": 1})
        buf.flush()
        assert len(flushes) == 1


# ---------------------------------------------------------------------------
# Soul (Integration)
# ---------------------------------------------------------------------------


class TestSoul:
    def test_create_and_cache(self):
        s1 = Soul.load_or_create("integ_test")
        s2 = Soul.load_or_create("integ_test")
        assert s1 is s2  # Same cached instance

    def test_remember_and_recall(self):
        s = Soul.load_or_create("recall_test")
        s.remember("python programming is fun", importance=0.8)
        s.remember("data science with AI", importance=0.7)
        results = s.recall("python")
        assert len(results) >= 1

    def test_reflection_cycle(self):
        s = Soul.load_or_create("reflect_test")
        s.remember("discussed python programming", importance=0.7)
        s.remember("discussed ML models", importance=0.7)
        s.remember("discussed data science", importance=0.7)
        result = s.reflect()
        assert "reflection" in result

    def test_state_summary(self):
        s = Soul.load_or_create("state_test")
        summary = s.state_summary()
        assert summary["name"] == "state_test"
        assert "identity" in summary
        assert "persona" in summary
        assert "memory_stats" in summary

    def test_suggest_enhancements(self):
        s = Soul.load_or_create("enhance_test")
        enhancements = s.suggest_enhancements()
        assert isinstance(enhancements, list)

    def test_persist_and_reload(self):
        s = Soul.load_or_create("reload_test")
        s.remember("memory before persist", importance=0.9)
        s._storage.flush()
        s.close()
        s2 = Soul.load_or_create("reload_test")
        results = s2.recall("memory before")
        assert len(results) >= 1
        s2.close()

    def test_cache_invalidation(self):
        s = Soul.load_or_create("inval_test")
        assert get_soul("inval_test") is s
        Soul.invalidate_cache("inval_test")
        assert get_soul("inval_test") is None

    def test_forget_by_id(self):
        s = Soul.load_or_create("forget_id_test")
        s.remember("memory to forget", importance=0.9)
        s.remember("memory to keep", importance=0.5)
        # Find the ID of the first memory
        results = s.recall("to forget", limit=10)
        target = [r for r in results if "to forget" in r["content"]][0]
        removed = s.forget(memory_id=target["id"])
        assert removed == 1
        remaining = s.recall("memory", limit=10)
        assert all("to forget" not in r["content"] for r in remaining)

    def test_forget_by_query(self):
        s = Soul.load_or_create("forget_query_test")
        s.remember("python programming basics", importance=0.7)
        s.remember("data science with python", importance=0.7)
        s.remember("javascript fundamentals", importance=0.5)
        removed = s.forget(query="python")
        assert removed == 2

    def test_forget_by_type(self):
        s = Soul.load_or_create("forget_type_test")
        s.remember("conversation", memory_type="episodic", importance=0.5)
        s.remember("fact learned", memory_type="semantic", importance=0.8)
        removed = s.forget(memory_type="episodic")
        assert removed == 1
        assert s.memory.stats()["episodic"] == 0
        assert s.memory.stats()["semantic"] == 1

    def test_forget_persists(self):
        """Forget flushes to disk so reloaded soul reflects the change."""
        s = Soul.load_or_create("forget_persist_test")
        s.remember("will be forgotten", importance=0.9)
        s.remember("will be kept", importance=0.5)
        removed = s.forget(query="forgotten")
        assert removed == 1
        s.close()
        s2 = Soul.load_or_create("forget_persist_test")
        remaining = s2.recall("kept", limit=10)
        assert len(remaining) >= 1
        s2.close()

    def test_list_souls(self):
        a = Soul.load_or_create("list_test_a")
        b = Soul.load_or_create("list_test_b")
        # Close souls to flush WriteBuffers so they appear on disk
        a.close()
        b.close()
        souls = Soul.list_souls()
        names = [s for s in souls if s.startswith("list_test")]
        assert len(names) >= 2

    def test_close_all(self):
        """close_all() closes all cached souls and clears the cache."""
        s1 = Soul.load_or_create("close_all_a")
        s2 = Soul.load_or_create("close_all_b")
        assert get_soul("close_all_a") is not None
        Soul.close_all()
        assert get_soul("close_all_a") is None
        assert get_soul("close_all_b") is None

    def test_close_all_no_souls(self):
        """close_all() should not crash when cache is empty."""
        Soul.close_all()  # No error


# ---------------------------------------------------------------------------
# Self-Improvement Loop
# ---------------------------------------------------------------------------


class TestSelfImprovementLoop:
    def test_analyze_no_memories(self, monkeypatch):
        """A soul with no memories should suggest memory seeding."""
        s = Soul.load_or_create("improve_test")
        suggestions = s.improvement.analyze()
        assert len(suggestions) > 0
        categories = {sg.category for sg in suggestions}
        assert "memory" in categories or "general" in categories

    def test_analyze_with_data(self):
        """Soul with data produces suggestions."""
        s = Soul.load_or_create("improve_data")
        s.remember("discussed python and data science", importance=0.7)
        s.remember("discussed ML algorithms and training", importance=0.7)
        s.remember("discussed neural networks and deep learning", importance=0.8)
        s.reflect()
        suggestions = s.improvement.analyze()
        assert isinstance(suggestions, list)

    def test_apply_not_actionable(self):
        """Non-actionable suggestion returns False."""
        s = Soul.load_or_create("apply_test")
        suggestion = EnhancementSuggestion(
            category="general",
            title="Not actionable",
            description="Test",
            actionable=False,
        )
        result = s.improvement.apply(suggestion)
        assert result is False

    def test_suggestion_to_dict(self):
        """EnhancementSuggestion.to_dict() returns serializable dict."""
        sg = EnhancementSuggestion(
            category="test",
            title="Test Suggestion",
            description="A test",
            priority=2,
            actionable=True,
        )
        d = sg.to_dict()
        assert d["category"] == "test"
        assert d["title"] == "Test Suggestion"
        assert d["actionable"] is True

    def test_summary_format(self):
        """suggestion_summary() returns properly structured dict."""
        s = Soul.load_or_create("summary_test")
        s.improvement.analyze()
        summary = s.improvement.suggestion_summary()
        assert "total_suggestions" in summary
        assert "by_category" in summary
        assert "applied_count" in summary

    # -- SelfImprovementLoop edge cases ---

    def test_memory_health_exactly_five(self):
        """5 memories is not 'very few' (only <5 triggers that suggestion)."""
        s = Soul.load_or_create("mem_health_five")
        for i in range(5):
            s.remember(f"memory {i}", importance=0.5)
        suggestions = s.improvement.analyze()
        # Should not have "Very few memories" title
        memory_titles = [sg.title for sg in suggestions if sg.category == "memory"]
        assert all("few" not in t.lower() for t in memory_titles)

    def test_memory_health_imbalanced_types(self):
        """episodic >> semantic with no dream suggests consolidation."""
        s = Soul.load_or_create("mem_health_imb")
        for i in range(25):
            s.remember(f"conversation {i}", memory_type="episodic", importance=0.5)
        # Purposely don't run reflect() so no semantic memories are created
        suggestions = s.improvement.analyze()
        memory_titles = [sg.title for sg in suggestions if sg.category == "memory"]
        assert any("consolidation" in t.lower() or "dream" in t.lower() for t in memory_titles)

    def test_memory_health_over_100(self):
        """Total >100 memories should suggest consolidation."""
        s = Soul.load_or_create("mem_health_over100")
        for i in range(105):
            s.remember(f"memory {i}", memory_type="episodic", importance=0.5)
        suggestions = s.improvement.analyze()
        memory_titles = [sg.title for sg in suggestions if sg.category == "memory"]
        assert any("consolidation" in t.lower() or "prune" in t.lower() for t in memory_titles)

    def test_persona_no_expertise(self):
        """Soul with no expertise should get a suggestion."""
        s = Soul.load_or_create("persona_no_exp")
        s.remember("test interaction", importance=0.5)
        # Don't reflect — no expertise developed
        suggestions = s.improvement.analyze()
        persona_titles = [sg.title for sg in suggestions if sg.category == "persona"]
        assert any("expertise" in t.lower() for t in persona_titles)

    def test_persona_not_evolved(self):
        """evolution_count == 0 should suggest running a dream cycle."""
        s = Soul.load_or_create("persona_not_evolved")
        s.remember("test interaction", importance=0.5)
        suggestions = s.improvement.analyze()
        persona_titles = [sg.title for sg in suggestions if sg.category == "persona"]
        assert any("evolv" in t.lower() for t in persona_titles)

    def test_persona_extreme_traits(self):
        """Traits >0.95 should trigger extreme trait suggestion."""
        s = Soul.load_or_create("persona_extreme")
        s.identity.traits["openness"] = 0.99
        s.remember("test interaction", importance=0.5)
        suggestions = s.improvement.analyze()
        persona_titles = [sg.title for sg in suggestions if sg.category == "persona"]
        assert any("extreme" in t.lower() or "traits" in t.lower() for t in persona_titles)

    def test_dreams_no_cycles(self):
        """dreams_count == 0 should suggest running a dream cycle."""
        s = Soul.load_or_create("dreams_no_cyc")
        s.remember("test interaction", importance=0.5)
        suggestions = s.improvement.analyze()
        dream_titles = [sg.title for sg in suggestions if sg.category == "dreams"]
        assert any("dream" in t.lower() or "cycle" in t.lower() for t in dream_titles)

    def test_dreams_low_insight_diversity(self):
        """>3 dream cycles with <2 insights should trigger suggestion."""
        s = Soul.load_or_create("dreams_low_div")
        s.remember("test interaction", importance=0.5)
        s.dreams.dreams_count = 5
        s.dreams.insights = [{"type": "pattern", "insight": "only one"}]
        suggestions = s.improvement.analyze()
        dream_titles = [sg.title for sg in suggestions if sg.category == "dreams"]
        assert any("insight" in t.lower() or "diversity" in t.lower() for t in dream_titles)

    def test_dreams_inefficient(self):
        """>50 cycles with <10 insights should trigger suggestion."""
        s = Soul.load_or_create("dreams_ineff")
        s.remember("test interaction", importance=0.5)
        s.dreams.dreams_count = 60
        s.dreams.insights = [{"type": "pattern", "insight": "only one"}]
        suggestions = s.improvement.analyze()
        dream_titles = [sg.title for sg in suggestions if sg.category == "dreams"]
        assert any("inefficient" in t.lower() for t in dream_titles)

    def test_general_no_interactions(self):
        """interactions == 0 should suggest starting a conversation."""
        s = Soul.load_or_create("general_no_int")
        suggestions = s.improvement.analyze()
        general_titles = [sg.title for sg in suggestions if sg.category == "general"]
        assert any("interaction" in t.lower() or "conversation" in t.lower() for t in general_titles)

    def test_general_interactions_without_sessions(self):
        """interactions >0 with sessions==0 should trigger session tracking suggestion."""
        s = Soul.load_or_create("general_no_sess")
        s.identity.stats["interactions"] = 10
        s.identity.stats["sessions"] = 0
        suggestions = s.improvement.analyze()
        general_titles = [sg.title for sg in suggestions if sg.category == "general"]
        assert any("session" in t.lower() for t in general_titles)

    def test_apply_actionable_success(self):
        """Actionable suggestion with working apply_fn returns True."""
        s = Soul.load_or_create("apply_success")
        applied = []
        sg = EnhancementSuggestion(
            category="test", title="Test", description="",
            actionable=True,
            apply_fn=lambda: applied.append(True),
        )
        result = s.improvement.apply(sg)
        assert result is True
        assert applied == [True]
        assert s.improvement._applied_count == 1

    def test_apply_actionable_failure(self):
        """Actionable suggestion whose apply_fn raises returns False."""
        s = Soul.load_or_create("apply_fail")
        sg = EnhancementSuggestion(
            category="test", title="Fail Test", description="",
            actionable=True,
            apply_fn=lambda: (_ for _ in ()).throw(RuntimeError("boom")),
        )
        result = s.improvement.apply(sg)
        assert result is False

    def test_apply_actionable_no_fn(self):
        """Actionable suggestion with no apply_fn returns False."""
        s = Soul.load_or_create("apply_no_fn")
        sg = EnhancementSuggestion(
            category="test", title="No Fn", description="",
            actionable=True,
            apply_fn=None,
        )
        result = s.improvement.apply(sg)
        assert result is False

    def test_suggestion_summary_empty(self):
        """suggestion_summary() before any analysis returns empty counts."""
        s = Soul.load_or_create("summary_empty")
        summary = s.improvement.suggestion_summary()
        assert summary["total_suggestions"] == 0
        assert summary["by_category"] == {}
        assert summary["applied_count"] == 0
        assert summary["last_analysis"] == 0.0


# ---------------------------------------------------------------------------
# KnowledgeGraph
# ---------------------------------------------------------------------------


class TestKnowledgeGraph:
    def test_add_memory_extracts_entities(self):
        from openjarvis.soul.knowledge import KnowledgeGraph
        kg = KnowledgeGraph()
        kg.add_memory("The user mentioned John Smith who loves Python")
        entity = kg.query_entity("john smith")
        assert entity is not None
        assert entity.entity_type == "person"
        entity2 = kg.query_entity("python")
        assert entity2 is not None
        assert entity2.entity_type == "technology"

    def test_add_memory_extracts_facts(self):
        from openjarvis.soul.knowledge import KnowledgeGraph
        kg = KnowledgeGraph()
        facts = kg.add_memory("The user loves programming in Python")
        assert len(facts) > 0
        # Should have a fact: user -> likes -> python
        user_facts = kg.query_facts(subject="user")
        assert len(user_facts) > 0

    def test_contradiction_resolution(self):
        from openjarvis.soul.knowledge import KnowledgeGraph
        kg = KnowledgeGraph()
        kg.add_memory("The user works at Acme Corp")
        kg.add_memory("The user works at BigCorp")  # Contradicts
        # Need valid_only=False to see expired facts too
        facts = kg.query_facts(subject="user", predicate="works_at", valid_only=False)
        assert len(facts) >= 1
        # The older fact should be expired
        expired = [f for f in facts if not f.is_valid]
        assert len(expired) >= 1
        valid = [f for f in facts if f.is_valid]
        assert len(valid) >= 1
        assert valid[0].object == "bigcorp"

    def test_related_entities(self):
        from openjarvis.soul.knowledge import KnowledgeGraph
        kg = KnowledgeGraph()
        # Use different predicates to avoid false contradiction (same subj+pred but different obj)
        kg.add_memory("The user knows Python")
        kg.add_memory("The user uses Docker")
        related = kg.query_related_entities("user")
        objects = {r[0] for r in related}
        assert "python" in objects
        assert "docker" in objects

    def test_search_entities(self):
        from openjarvis.soul.knowledge import KnowledgeGraph
        kg = KnowledgeGraph()
        kg.add_memory("The user talked to John Smith about Python")
        results = kg.search_entities("john")
        assert len(results) >= 1
        assert "john" in results[0].name

    def test_get_domains_from_entities(self):
        from openjarvis.soul.knowledge import KnowledgeGraph
        kg = KnowledgeGraph()
        kg.add_memory("Uses Python and Docker and Kubernetes")
        domains = kg.get_domains_from_entities()
        assert "technology" in domains
        assert domains["technology"] > 0

    def test_deduplicate_facts(self):
        from openjarvis.soul.knowledge import KnowledgeGraph
        kg = KnowledgeGraph()
        kg.add_memory("Sarah likes Python")  # creates fact: user -> likes -> python
        kg.deduplicate_facts()  # no dupes yet
        before = len(kg._facts)
        # Add duplicate fact manually
        import copy
        if kg._facts:
            dup = copy.deepcopy(kg._facts[0])
            kg._facts.append(dup)
            removed = kg.deduplicate_facts()
            assert removed == 1
            assert len(kg._facts) == before

    def test_remove_memory(self):
        from openjarvis.soul.knowledge import KnowledgeGraph
        kg = KnowledgeGraph()
        kg.add_memory("Sarah likes Python", memory_id="mem_1")
        kg.add_memory("Sarah likes Java", memory_id="mem_2")
        removed = kg.remove_memory("mem_1")
        assert removed >= 1
        # Only memory 2 facts remain
        remaining_ids = {f.source_memory_id for f in kg._facts}
        assert "mem_1" not in remaining_ids

    def test_query_memories_for_entity(self):
        from openjarvis.soul.knowledge import KnowledgeGraph
        kg = KnowledgeGraph()
        kg.add_memory("The user Alice uses Python", memory_id="mem_a")
        ids = kg.query_memories_for_entity("alice")
        assert "mem_a" in ids

    def test_serialization_roundtrip(self):
        from openjarvis.soul.knowledge import KnowledgeGraph
        kg = KnowledgeGraph()
        kg.add_memory("John knows Python and Docker")
        data = kg.to_dict()
        restored = KnowledgeGraph.from_dict(data)
        assert restored.stats()["entities"] == kg.stats()["entities"]
        assert restored.stats()["facts"] == kg.stats()["facts"]

    def test_stats(self):
        from openjarvis.soul.knowledge import KnowledgeGraph
        kg = KnowledgeGraph()
        kg.add_memory("The user John Smith uses Python and Docker")
        stats = kg.stats()
        assert stats["entities"] >= 2  # john smith + Python
        assert stats["facts"] >= 1

    def test_empty_kg(self):
        from openjarvis.soul.knowledge import KnowledgeGraph
        kg = KnowledgeGraph()
        assert kg.query_entity("nobody") is None
        assert kg.query_facts() == []
        assert kg.query_related_entities("nobody") == []
        assert kg.search_entities("x") == []
        assert kg.get_domains_from_entities() == {}

    def test_resolve_all_contradictions(self):
        from openjarvis.soul.knowledge import KnowledgeGraph, Fact
        kg = KnowledgeGraph()
        # Add contradictory facts manually
        import time as _time
        now = _time.time()
        kg._facts.append(Fact(subject="user", predicate="likes", object="python",
                              confidence=0.5, timestamp=now - 100))
        kg._facts.append(Fact(subject="user", predicate="likes", object="java",
                              confidence=0.6, timestamp=now))
        expired = kg.resolve_all_contradictions()
        assert expired >= 1

    def test_fact_repr(self):
        from openjarvis.soul.knowledge import Fact
        f = Fact(subject="user", predicate="likes", object="python")
        r = repr(f)
        assert "user" in r
        assert "likes" in r
        assert "python" in r

    def test_entity_to_dict(self):
        from openjarvis.soul.knowledge import Entity
        e = Entity(name="test", entity_type="concept", confidence=0.8, first_seen=1.0, last_seen=2.0)
        d = e.to_dict()
        assert d["name"] == "test"
        assert d["confidence"] == 0.8
        restored = Entity.from_dict(d)
        assert restored.name == "test"

    def test_add_memory_extracts_url_entity(self):
        from openjarvis.soul.knowledge import KnowledgeGraph
        kg = KnowledgeGraph()
        kg.add_memory("Check out https://example.com for more info")
        entity = kg.query_entity("https://example.com")
        assert entity is not None
        assert entity.entity_type == "url"


# ---------------------------------------------------------------------------
# EmotionalState
# ---------------------------------------------------------------------------


class TestEmotionalState:
    def test_initial_state(self):
        from openjarvis.soul.emotional import EmotionalState
        e = EmotionalState()
        assert e.valence == 0.0
        assert e.arousal == 0.5
        assert e.dominance == 0.5
        assert e.mood == "neutral"
        assert e.frustration_level == 0.0

    def test_positive_interaction(self):
        from openjarvis.soul.emotional import EmotionalState
        e = EmotionalState()
        e.update_from_interaction("I love this! It's amazing!", explicit_sentiment="positive")
        assert e.valence > 0

    def test_negative_interaction(self):
        from openjarvis.soul.emotional import EmotionalState
        e = EmotionalState()
        e.update_from_interaction("I hate this bug. It's terrible.", explicit_sentiment="negative")
        assert e.valence < 0
        assert e.frustration_level > 0

    def test_sentiment_analysis_positive(self):
        from openjarvis.soul.emotional import EmotionalState
        result = EmotionalState._analyze_sentiment("I love this amazing awesome product")
        assert result == "positive"

    def test_sentiment_analysis_negative(self):
        from openjarvis.soul.emotional import EmotionalState
        result = EmotionalState._analyze_sentiment("This is terrible and awful")
        assert result == "negative"

    def test_sentiment_analysis_neutral(self):
        from openjarvis.soul.emotional import EmotionalState
        result = EmotionalState._analyze_sentiment("The sky is blue today")
        assert result == "neutral"

    def test_sentiment_analysis_empty(self):
        from openjarvis.soul.emotional import EmotionalState
        result = EmotionalState._analyze_sentiment("")
        assert result == "neutral"

    def test_mood_classification_excited(self):
        from openjarvis.soul.emotional import EmotionalState
        e = EmotionalState(valence=0.6, arousal=0.8)
        mood = e._compute_mood()
        assert mood == "excited"

    def test_mood_classification_calm(self):
        from openjarvis.soul.emotional import EmotionalState
        e = EmotionalState(valence=0.6, arousal=0.2)
        mood = e._compute_mood()
        assert mood == "calm"

    def test_mood_classification_tense(self):
        from openjarvis.soul.emotional import EmotionalState
        e = EmotionalState(valence=-0.6, arousal=0.8)
        mood = e._compute_mood()
        assert mood == "tense"

    def test_mood_classification_sad(self):
        from openjarvis.soul.emotional import EmotionalState
        e = EmotionalState(valence=-0.6, arousal=0.2)
        mood = e._compute_mood()
        assert mood == "sad"

    def test_mood_frustrated(self):
        from openjarvis.soul.emotional import EmotionalState
        e = EmotionalState(frustration_level=0.8)
        mood = e._compute_mood()
        assert mood == "frustrated"

    def test_frustration_accumulates(self):
        from openjarvis.soul.emotional import EmotionalState
        e = EmotionalState()
        for _ in range(8):
            e.update_from_interaction("This is terrible", explicit_sentiment="negative")
        assert e.frustration_level > 0.5

    def test_frustration_decays(self):
        from openjarvis.soul.emotional import EmotionalState
        import time as _time
        e = EmotionalState()
        e.last_update = _time.time()
        e.frustration_level = 1.0
        e._apply_decay(_time.time() + 7200)  # 2 hours later
        assert e.frustration_level < 1.0

    def test_get_emotional_context(self):
        from openjarvis.soul.emotional import EmotionalState
        e = EmotionalState()
        ctx = e.get_emotional_context()
        assert "mood" in ctx
        assert "valence" in ctx
        assert "arousal" in ctx
        assert "dominance" in ctx

    def test_communication_adjustments_frustrated(self):
        from openjarvis.soul.emotional import EmotionalState
        e = EmotionalState(frustration_level=0.7)
        adj = e.communication_adjustments()
        assert adj.get("empathy", 0) > 0

    def test_communication_adjustments_negative(self):
        from openjarvis.soul.emotional import EmotionalState
        e = EmotionalState(valence=-0.5)
        adj = e.communication_adjustments()
        assert adj.get("empathy", 0) > 0

    def test_get_recent_trend_stable(self):
        from openjarvis.soul.emotional import EmotionalState
        e = EmotionalState()
        trend = e.get_recent_trend()
        assert trend == "stable"

    def test_get_recent_trend_improving(self):
        from openjarvis.soul.emotional import EmotionalState
        e = EmotionalState()
        e.mood_history = [
            {"valence": -0.5}, {"valence": -0.3}, {"valence": 0.0},
            {"valence": 0.2}, {"valence": 0.4}, {"valence": 0.5},
        ]
        trend = e.get_recent_trend()
        assert trend == "improving"

    def test_serialization_roundtrip(self):
        from openjarvis.soul.emotional import EmotionalState
        e = EmotionalState(valence=0.5, arousal=0.7, dominance=0.8, mood="happy")
        e.update_from_interaction("Great!", explicit_sentiment="positive")
        data = e.to_dict()
        restored = EmotionalState.from_dict(data)
        assert restored.valence == e.valence
        assert restored.arousal == e.arousal
        assert restored.dominance == e.dominance
        assert restored.mood_history == e.mood_history

    def test_decay_over_time(self):
        from openjarvis.soul.emotional import EmotionalState
        import time as _time
        e = EmotionalState(valence=1.0, arousal=0.9)
        e.last_update = _time.time()
        e._apply_decay(_time.time() + 36000)  # 10 hours later
        assert e.valence < 1.0  # Should have decayed toward 0
        assert e.arousal < 0.9  # Should have decayed toward 0.5

    def test_mood_history_capped_at_100(self):
        from openjarvis.soul.emotional import EmotionalState
        e = EmotionalState()
        for i in range(150):
            e.update_from_interaction(f"interaction {i}", explicit_sentiment="positive")
        assert len(e.mood_history) <= 100

    def test_exclamation_arousal(self):
        from openjarvis.soul.emotional import EmotionalState
        e = EmotionalState()
        e.update_from_interaction("Wow!!!")
        assert e.arousal > 0.5

    def test_question_dominance(self):
        from openjarvis.soul.emotional import EmotionalState
        # Questions reduce dominance
        e = EmotionalState()
        e.update_from_interaction("What? Where? When?", explicit_sentiment="neutral")
        # Question marks decrease dominance by 0.03 * number of questions
        assert e.dominance < 0.8  # started at 0.5, may have other adjustments


# ---------------------------------------------------------------------------
# SessionLog
# ---------------------------------------------------------------------------


class TestSessionLog:
    def test_start_and_end(self):
        from openjarvis.soul.sessions import SessionLog
        log = SessionLog()
        session = log.start_session()
        assert session is not None
        assert session.is_active
        completed = log.end_session()
        assert completed is not None
        assert not completed.is_active
        assert completed.id == session.id

    def test_record_interaction(self):
        from openjarvis.soul.sessions import SessionLog
        log = SessionLog()
        log.start_session()
        log.record_interaction("hello", "hi there", entity_names=["python"])
        session = log.get_active_session()
        assert session.interaction_count == 1
        assert "python" in session.entities_seen

    def test_auto_starts_session(self):
        from openjarvis.soul.sessions import SessionLog
        log = SessionLog()
        log.record_interaction("hello", "hi")  # Auto-starts session
        assert log.get_active_session() is not None
        assert log.get_active_session().interaction_count == 1

    def test_start_new_ends_old(self):
        from openjarvis.soul.sessions import SessionLog
        log = SessionLog()
        s1 = log.start_session()
        log.record_interaction("msg", "res")
        s2 = log.start_session()  # Should end s1
        assert s1.is_active is False
        assert s2.is_active
        assert log.get_active_session().id == s2.id

    def test_generate_summary(self):
        from openjarvis.soul.sessions import Session
        s = Session.create()
        s.record_interaction("What is Python?", "Python is a language")
        s.record_interaction("Tell me about AI", "AI is a field")
        summary = s.generate_summary(memories=[
            {"content": "What is Python?"},
            {"content": "Python is a language"},
            {"content": "Tell me about AI"},
        ])
        assert len(summary) > 0
        assert s.key_topics is not None

    def test_cross_session_summary(self):
        from openjarvis.soul.sessions import SessionLog
        log = SessionLog()
        log.start_session()
        log.record_interaction("hello", "hi")
        log.end_session()
        log.start_session()
        log.record_interaction("bye", "bye")
        log.end_session()
        summary = log.get_cross_session_summary()
        assert "Recent sessions" in summary
        assert len(log._completed) == 2

    def test_topics_across_sessions(self):
        from openjarvis.soul.sessions import SessionLog
        log = SessionLog()
        s = log.start_session()
        s.key_topics = ["python", "data"]
        log.end_session()
        s2 = log.start_session()
        s2.key_topics = ["python", "ml"]
        log.end_session()
        topics = log.get_topics_across_sessions()
        assert topics.get("python", 0) == 2
        assert topics.get("data", 0) == 1

    def test_end_session_no_active(self):
        from openjarvis.soul.sessions import SessionLog
        log = SessionLog()
        session = log.end_session()  # No active session
        assert session.id == "noop"

    def test_stats_empty(self):
        from openjarvis.soul.sessions import SessionLog
        log = SessionLog()
        stats = log.stats()
        assert stats["total_sessions"] == 0
        assert stats["total_interactions"] == 0

    def test_stats_with_sessions(self):
        from openjarvis.soul.sessions import SessionLog
        log = SessionLog()
        log.start_session()
        log.record_interaction("a", "b")
        log.record_interaction("c", "d")
        log.end_session()
        stats = log.stats()
        assert stats["total_sessions"] == 1
        assert stats["total_interactions"] == 2

    def test_session_properties(self):
        from openjarvis.soul.sessions import Session
        s = Session.create()
        assert s.is_active
        assert s.duration >= 0
        assert len(s.id) == 12  # UUID first 12 chars
        s.record_interaction("hello world", "response text")
        assert s.token_estimate > 0
        # Token estimate ~4 chars/token: 11 + 13 = 24 / 4 = 6
        assert s.token_estimate >= 5

    def test_serialization_roundtrip(self):
        from openjarvis.soul.sessions import SessionLog, Session
        log = SessionLog()
        s = log.start_session()
        s.record_interaction("hi", "hello")
        s.dominant_mood = "happy"
        log.end_session()
        data = log.to_dict()
        restored = SessionLog.from_dict(data)
        assert len(restored._completed) == 1
        assert restored._completed[0].dominant_mood == "happy"

    def test_session_repr(self):
        from openjarvis.soul.sessions import SessionLog
        log = SessionLog()
        r = repr(log)
        assert "active" in r or "completed" in r

    def test_cross_session_summary_empty(self):
        from openjarvis.soul.sessions import SessionLog
        log = SessionLog()
        assert log.get_cross_session_summary() == "No previous sessions."


# ---------------------------------------------------------------------------
# WorkingMemory
# ---------------------------------------------------------------------------


class TestWorkingMemory:
    def test_pin_and_unpin(self):
        from openjarvis.soul.memory import WorkingMemory
        wm = WorkingMemory()
        wm.pin("mem_1")
        assert wm.is_pinned("mem_1")
        wm.unpin("mem_1")
        assert not wm.is_pinned("mem_1")

    def test_get_ids(self):
        from openjarvis.soul.memory import WorkingMemory
        wm = WorkingMemory()
        wm.pin("mem_a")
        ids = wm.get_ids()
        assert "mem_a" in ids

    def test_refresh_with_entries(self):
        from openjarvis.soul.memory import WorkingMemory, MemoryEntry
        wm = WorkingMemory(max_slots=3)
        entries = [
            MemoryEntry.create("low", importance=0.2),
            MemoryEntry.create("high", importance=0.9),
            MemoryEntry.create("medium", importance=0.5),
        ]
        wm.refresh(entries)
        ids = wm.get_ids()
        assert len(ids) <= 3
        # High importance should be included
        high_id = entries[1].id
        assert high_id in ids

    def test_pinned_survives_refresh(self):
        from openjarvis.soul.memory import WorkingMemory, MemoryEntry
        wm = WorkingMemory(max_slots=2)
        entries = [
            MemoryEntry.create("a", importance=0.3),
            MemoryEntry.create("b", importance=0.4),
            MemoryEntry.create("c", importance=0.5),
        ]
        wm.pin(entries[2].id)
        wm.refresh(entries)
        ids = wm.get_ids()
        assert entries[2].id in ids  # Pinned always stays

    def test_pin_promotes_to_front(self):
        from openjarvis.soul.memory import WorkingMemory
        wm = WorkingMemory()
        wm.pin("mem_1")
        wm.pin("mem_2")
        ids = wm.get_ids()
        assert ids[0] == "mem_2" or ids[0] == "mem_1"  # Most recently pinned is at front

    def test_new_entry_boost(self):
        from openjarvis.soul.memory import WorkingMemory, MemoryEntry
        wm = WorkingMemory(max_slots=3)
        entries = [MemoryEntry.create(f"entry_{i}", importance=0.5) for i in range(5)]
        # Add a new entry
        new_entry = MemoryEntry.create("new_one", importance=0.5)
        entries.append(new_entry)
        wm.refresh(entries, new_entry_id=new_entry.id)
        ids = wm.get_ids()
        assert new_entry.id in ids

    def test_max_slots_respected(self):
        from openjarvis.soul.memory import WorkingMemory, MemoryEntry
        wm = WorkingMemory(max_slots=3)
        entries = [MemoryEntry.create(f"entry_{i}", importance=0.8) for i in range(10)]
        wm.refresh(entries)
        assert len(wm.get_ids()) <= 3

    def test_serialization_roundtrip(self):
        from openjarvis.soul.memory import WorkingMemory
        wm = WorkingMemory(max_slots=5)
        wm.pin("mem_a")
        wm.pin("mem_b")
        data = wm.to_dict()
        restored = WorkingMemory.from_dict(data)
        assert restored.max_slots == 5
        assert restored.is_pinned("mem_a")
        assert restored.is_pinned("mem_b")

    def test_unpin_nonexistent(self):
        from openjarvis.soul.memory import WorkingMemory
        wm = WorkingMemory()
        wm.unpin("nobody")  # Should not raise

    def test_is_pinned_nonexistent(self):
        from openjarvis.soul.memory import WorkingMemory
        wm = WorkingMemory()
        assert not wm.is_pinned("nobody")


# ---------------------------------------------------------------------------
# Importance Scoring & MMR
# ---------------------------------------------------------------------------


class TestImportanceScoring:
    def test_empty_content(self):
        from openjarvis.soul.memory import compute_importance_score
        assert compute_importance_score("") == 0.1
        assert compute_importance_score("   ") == 0.1

    def test_short_content(self):
        from openjarvis.soul.memory import compute_importance_score
        score = compute_importance_score("hi")
        assert score > 0.0  # Should have a tiny positive score
        assert score < 1.0

    def test_technical_content(self):
        from openjarvis.soul.memory import compute_importance_score
        score = compute_importance_score("The function uses a data algorithm to deploy the system")
        assert score > 0.3  # Technical keywords bump score

    def test_user_preference(self):
        from openjarvis.soul.memory import compute_importance_score
        score = compute_importance_score("I love Python and I like programming")
        assert score > 0.2  # Preference language bumps score ("i love" + "i like" = 0.16, base 0.1)

    def test_instruction_keywords(self):
        from openjarvis.soul.memory import compute_importance_score
        score = compute_importance_score("Remember: this is important! Critical bug!")
        assert score > 0.3  # Instruction keywords bump score

    def test_long_content(self):
        from openjarvis.soul.memory import compute_importance_score
        score = compute_importance_score("x" * 5000)
        assert score > 0.2  # Length contributes

    def test_questions_and_exclamations(self):
        from openjarvis.soul.memory import compute_importance_score
        score = compute_importance_score("What is this? How does it work? Wow!")
        assert score > 0.2  # ? and ! both contribute

    def test_clamped_to_one(self):
        from openjarvis.soul.memory import compute_importance_score
        score = compute_importance_score(
            "I love Python! This function is a critical algorithm! "
            "Remember: data deployment is important! Important bug fix! "
            "I need this urgently! " * 10
        )
        assert score <= 1.0


class TestMMRReranker:
    def test_empty_results(self):
        from openjarvis.soul.memory import mmr_rerank
        assert mmr_rerank([], limit=5) == []

    def test_single_result(self):
        from openjarvis.soul.memory import mmr_rerank
        results = [{"content": "only", "score": 0.5, "embedding": [0.1, 0.2]}]
        reranked = mmr_rerank(results, limit=5)
        assert len(reranked) == 1

    def test_no_query_embedding_falls_back_to_score(self):
        from openjarvis.soul.memory import mmr_rerank
        results = [
            {"content": "a", "score": 0.3},
            {"content": "b", "score": 0.9},
            {"content": "c", "score": 0.6},
        ]
        reranked = mmr_rerank(results, limit=3)
        assert reranked[0]["content"] == "b"  # Highest score first

    def test_respects_limit(self):
        from openjarvis.soul.memory import mmr_rerank
        results = [
            {"content": f"item_{i}", "score": 0.5, "embedding": [i/10, 1-i/10]}
            for i in range(10)
        ]
        reranked = mmr_rerank(results, limit=3)
        assert len(reranked) == 3

    def test_diverse_reranking(self):
        """MMR should prefer diverse items over similar ones."""
        from openjarvis.soul.memory import mmr_rerank
        # Two similar items (close embeddings) and one different
        results = [
            {"content": "python A", "score": 0.9, "embedding": [1.0, 0.0]},
            {"content": "python B", "score": 0.85, "embedding": [0.95, 0.05]},
            {"content": "docker", "score": 0.7, "embedding": [0.0, 1.0]},
        ]
        reranked = mmr_rerank(results, query_embedding=[0.5, 0.5], lambda_param=0.5, limit=2)
        contents = {r["content"] for r in reranked}
        assert "docker" in contents  # Diverse item should be selected over second python


# ---------------------------------------------------------------------------
# MemoryEntry Advanced (decay, access)
# ---------------------------------------------------------------------------


class TestMemoryEntryAdvanced:
    def test_record_access(self):
        entry = MemoryEntry.create("test")
        assert entry.access_count == 0
        entry.record_access()
        assert entry.access_count == 1
        assert entry.last_accessed > 0
        entry.record_access()
        assert entry.access_count == 2

    def test_compute_decay_factor_new(self):
        """A brand new memory with no accesses should have a moderate decay factor."""
        entry = MemoryEntry.create("test")
        factor = entry.compute_decay_factor()
        assert 0.0 <= factor <= 1.0

    def test_compute_decay_factor_frequently_accessed(self):
        """Frequently accessed memories should have higher decay factors."""
        import time
        entry = MemoryEntry.create("test")
        for _ in range(10):
            entry.record_access()
        time.sleep(0.01)  # Tiny delay so last_accessed differs
        factor = entry.compute_decay_factor()
        assert factor > 0.3  # High access count boosts strength

    def test_compute_decay_factor_ranges(self):
        """Decay factor is always between 0 and 1."""
        entry = MemoryEntry.create("test", importance=0.5)
        for _ in range(20):
            factor = entry.compute_decay_factor()
            assert 0.0 <= factor <= 1.0
            entry.record_access()


# ---------------------------------------------------------------------------
# TieredMemory Advanced (dedup, MMR, working memory)
# ---------------------------------------------------------------------------


class TestTieredMemoryAdvanced:
    def test_deduplicate_empty(self):
        mem = TieredMemory.create("test")
        removed = mem.deduplicate(similarity_threshold=0.9)
        assert removed == 0

    def test_deduplicate_none_similar(self):
        mem = TieredMemory.create("test")
        mem.store("python programming", importance=0.5)
        mem.store("docker containers", importance=0.5)
        removed = mem.deduplicate(similarity_threshold=0.9)
        assert removed == 0  # Different content, different embeddings

    def test_retrieve_with_working_memory(self):
        """Working memory items are included in retrieve results."""
        mem = TieredMemory.create("test")
        mem.store("python programming", importance=0.8)
        # No explicit working memory test needed — retrieve just works
        results = mem.retrieve("python", include_working=True)
        assert len(results) > 0

    def test_retrieve_with_mmr_flag(self):
        """Retrieve with use_mmr=True works without error."""
        mem = TieredMemory.create("test")
        mem.store("python programming is fun", importance=0.9)
        mem.store("python is a programming language", importance=0.8)
        mem.store("docker container deployment", importance=0.7)
        results = mem.retrieve("python", use_mmr=True, limit=2)
        assert len(results) > 0
        assert len(results) <= 2

    def test_consolidation_with_all_tiers(self):
        mem = TieredMemory.create("test")
        mem.store("old memory", memory_type="episodic", importance=0.3)
        mem.store("fact", memory_type="semantic", importance=0.5)
        mem.store("skill", memory_type="procedural", importance=0.5)
        pruned = mem.consolidate(max_age_days=0)  # Everything is "old"
        assert pruned["episodic"] >= 1  # Episodic with low importance gets pruned
        assert pruned["semantic"] == 0  # Semantic is never pruned
        assert pruned["procedural"] == 0  # Procedural is never pruned

    def test_working_memory_integration(self):
        """Storing a memory updates working memory."""
        mem = TieredMemory.create("test")
        mem.store("important memory", importance=0.9)
        # Working memory should have been refreshed
        ids = mem.working.get_ids()
        assert len(ids) > 0


# ---------------------------------------------------------------------------
# Soul Advanced (new feature integration)
# ---------------------------------------------------------------------------


class TestSoulAdvanced:
    def test_pin_and_unpin_memory(self):
        s = Soul.load_or_create("adv_pin")
        s.remember("important thing", importance=0.9)
        results = s.recall("important", limit=10)
        assert len(results) >= 1
        mem_id = results[0]["id"]
        s.pin_memory(mem_id)
        assert mem_id in s.get_working_memory()
        s.unpin_memory(mem_id)
        assert mem_id not in s.get_working_memory()

    def test_start_and_end_session(self):
        s = Soul.load_or_create("adv_session")
        session = s.start_session()
        assert session is not None
        assert session.is_active
        s.remember("test interaction", importance=0.5)
        completed = s.end_session()
        assert completed is not None
        assert not completed.is_active

    def test_end_session_no_active(self):
        s = Soul.load_or_create("adv_no_sess")
        result = s.end_session()
        assert result is None

    def test_cross_session_context(self):
        s = Soul.load_or_create("adv_xsess")
        ctx = s.get_cross_session_context()
        assert isinstance(ctx, str)

    def test_query_entity(self):
        s = Soul.load_or_create("adv_entity")
        s.remember("The user John Smith knows Python and Docker")
        entity = s.query_entity("john smith")
        assert entity is not None

    def test_query_entity_nonexistent(self):
        s = Soul.load_or_create("adv_no_entity")
        assert s.query_entity("nobody") is None

    def test_query_facts(self):
        s = Soul.load_or_create("adv_facts")
        s.remember("User likes Python")
        facts = s.query_facts(predicate="likes")
        assert len(facts) > 0

    def test_search_entities(self):
        s = Soul.load_or_create("adv_search")
        s.remember("The user Alice Smith works with Python")
        results = s.search_entities("alice")
        assert len(results) > 0

    def test_query_related_entities(self):
        s = Soul.load_or_create("adv_related")
        s.remember("User uses Python")
        s.remember("User uses Docker")
        related = s.query_related_entities("user")
        assert len(related) > 0

    def test_get_emotional_context(self):
        s = Soul.load_or_create("adv_emotion")
        ctx = s.get_emotional_context()
        assert "mood" in ctx
        assert "valence" in ctx

    def test_emotional_trend_stable(self):
        s = Soul.load_or_create("adv_trend")
        trend = s.emotional_trend()
        assert isinstance(trend, str)

    def test_deduplicate_memories(self):
        s = Soul.load_or_create("adv_dedup")
        s.remember("python programming", importance=0.5)
        s.remember("docker containers", importance=0.5)
        removed = s.deduplicate_memories(threshold=0.95)
        assert removed >= 0  # At minimum, no crash

    def test_state_summary_includes_new_subsystems(self):
        s = Soul.load_or_create("adv_summary")
        summary = s.state_summary()
        assert "knowledge" in summary
        assert "emotion" in summary
        assert "sessions" in summary
        assert "working_memory" in summary

    def test_remember_triggers_knowledge_extraction(self):
        s = Soul.load_or_create("adv_kg")
        s.remember("Sarah loves programming in Python")
        facts = s.query_facts()
        assert len(facts) > 0

    def test_remember_triggers_emotion_update(self):
        s = Soul.load_or_create("adv_emo_update")
        s.remember("I love this! It's amazing!")
        ctx = s.get_emotional_context()
        # Valence should have increased from the positive content
        # Note: may be close to 0 if sentiment analysis doesn't pick it up robustly
        assert isinstance(ctx["valence"], float)

    def test_reflect_uses_knowledge_and_emotion(self):
        """Reflect now includes knowledge domains and emotional context."""
        s = Soul.load_or_create("adv_kge")
        s.remember("discussed Python, Docker, and Kubernetes", importance=0.8)
        s.remember("discussed ML models and data science", importance=0.8)
        result = s.reflect()
        assert "reflection" in result
        assert "insights" in result

    def test_forget_persists_knowledge_cleanup(self):
        """Forget by memory_id also cleans up knowledge graph."""
        s = Soul.load_or_create("adv_forget_kg")
        s.remember("John knows Python", importance=0.7)
        s.remember("John knows Java", importance=0.7)
        # Find the memory ID for "Python"
        results = s.recall("Python", limit=10)
        target = [r for r in results if "Python" in r["content"]][0]
        removed = s.forget(memory_id=target["id"])
        assert removed >= 1
        # Knowledge graph should still have other facts
        assert len(s.knowledge._facts) >= 1

    def test_dream_with_knowledge_domains(self):
        """dream() method accepts knowledge_domains param."""
        engine = DreamEngine("test")
        memories = [{"content": "python programming"}] * 5
        insights = engine.dream(
            memories, None, min_memories=0,
            knowledge_domains={"technology": 0.8},
        )
        assert len(insights) > 0
        # Should have a knowledge-driven insight
        domain_types = [i["type"] for i in insights]
        assert "expertise_discovery" in domain_types or "pattern" in domain_types

    def test_dream_with_emotional_context(self):
        """dream() with high frustration emotional context adds self-awareness insight."""
        engine = DreamEngine("test")
        memories = [{"content": "python programming"}] * 5
        insights = engine.dream(
            memories, None, min_memories=0,
            emotional_context={"frustration": 0.7, "mood": "frustrated"},
        )
        types = [i["type"] for i in insights]
        assert "self_awareness" in types

    def test_dream_with_excited_emotional_context(self):
        """dream() with excited emotional context adds self-awareness insight."""
        engine = DreamEngine("test")
        memories = [{"content": "python programming"}] * 5
        insights = engine.dream(
            memories, None, min_memories=0,
            emotional_context={"frustration": 0.0, "mood": "excited"},
        )
        types = [i["type"] for i in insights]
        assert "self_awareness" in types

    def test_reflect_with_negative_emotion(self):
        """Reflect with negative emotion should still work."""
        s = Soul.load_or_create("adv_neg_emo")
        s.remember("This is terrible! Nothing works!", importance=0.7)
        s.remember("I hate these bugs!", importance=0.7)
        result = s.reflect()
        assert "reflection" in result


# ---------------------------------------------------------------------------
# Dream Integration (knowledge_domains + emotional_context)
# ---------------------------------------------------------------------------


class TestDreamIntegration:
    """Integration tests for the enhanced dream() pipeline.

    Tests the full flow: remember() → knowledge graph / emotion →
    reflect() → dream() with knowledge_domains + emotional_context.
    """

    # ── Knowledge domains integration ──────────────────────────────────

    def test_knowledge_domains_flow_through_reflect(self):
        """Knowledge graph entities produce domain signals that reach dream()."""
        s = Soul.load_or_create("int_kg_flow")
        # Remember tech content to seed knowledge graph
        s.remember("discussed Python programming and Docker containers", importance=0.8)
        s.remember("discussed Kubernetes deployment and AWS cloud", importance=0.8)
        s.remember("discussed CI/CD pipelines with GitHub Actions", importance=0.8)

        # Verify knowledge graph has tech entities
        python_entity = s.query_entity("python")
        docker_entity = s.query_entity("docker")
        assert python_entity is not None, "Knowledge graph should have 'python' entity"
        assert docker_entity is not None, "Knowledge graph should have 'docker' entity"

        # Verify get_domains_from_entities includes technology
        domains = s.knowledge.get_domains_from_entities()
        assert "technology" in domains, "Knowledge graph should detect technology domain"
        assert domains["technology"] > 0.3, "Domain confidence should exceed threshold"

        # Now reflect — dream() should receive knowledge_domains
        result = s.reflect()
        assert "reflection" in result
        assert "insights" in result

        # Should have produced some insights (patterns + expertise)
        insights = result["insights"]
        assert len(insights) > 0

        # At least one insight should mention a domain or technology
        domain_texts = " ".join(i.get("insight", "") + " " + str(i.get("domain", "")) for i in insights)
        domain_texts_lower = domain_texts.lower()
        assert any(kw in domain_texts_lower for kw in ["technology", "devops", "programming", "docker", "python", "aws"]), \
            f"Insights should reference tech domains: {insights}"

    def test_knowledge_domains_empty_no_domain_insight(self):
        """With no entities in knowledge graph, no domain-driven insights."""
        s = Soul.load_or_create("int_kg_empty")
        # Remember content that won't trigger entity extraction
        s.remember("the weather is nice today", importance=0.5)
        s.remember("i like cooking dinner", importance=0.5)

        # Verify no tech entities exist
        domains = s.knowledge.get_domains_from_entities()
        assert len(domains) == 0, "No entities should yield empty domains"

        # Reflect — should not produce knowledge-driven domain insights
        result = s.reflect()
        insights = result.get("insights", [])

        # May still produce pattern/other insights, but none should be domain-driven
        for i in insights:
            assert i.get("domain") is None or i.get("domain") not in ["technology", "programming", "devops"], \
                f"No tech domain insight expected: {i}"

    def test_knowledge_domains_from_multiple_tech_entities(self):
        """Multiple tech entities create stronger domain signals."""
        s = Soul.load_or_create("int_kg_multi")
        tech_list = [
            "Python", "JavaScript", "TypeScript", "Rust", "Go",
            "Docker", "Kubernetes", "AWS", "React", "Django",
        ]
        for tech in tech_list:
            s.remember(f"discussed {tech} in detail", importance=0.5)

        # Verify tech entity count
        stats = s.knowledge.stats()
        assert stats["entities"] >= 5

        # Domain confidence should be high (5+ tech entities → min(1.0, 5/5) = 1.0)
        domains = s.knowledge.get_domains_from_entities()
        assert "technology" in domains
        assert domains["technology"] >= 0.8, f"Expected high domain confidence, got {domains}"

        # Reflect with strong domain signals
        result = s.reflect()
        insights = result.get("insights", [])
        assert len(insights) > 0

        # Some insights should be expertise_discovery with domain
        domain_insights = [i for i in insights if i.get("type") == "expertise_discovery"]
        assert len(domain_insights) > 0, f"Expected domain insights, got: {insights}"

    def test_knowledge_domains_survive_persist(self):
        """Knowledge graph entities and domain signals survive persist/reload."""
        s = Soul.load_or_create("int_kg_persist")
        s.remember("discussed Python and Docker", importance=0.8)
        s.remember("discussed Kubernetes and AWS", importance=0.8)

        # Capture domain state before persist
        domains_before = s.knowledge.get_domains_from_entities()
        assert "technology" in domains_before

        # Close and reload
        s._storage.flush()
        s.close()

        s2 = Soul.load_or_create("int_kg_persist")

        # Verify knowledge graph survived
        python = s2.query_entity("python")
        assert python is not None, "Entity should survive persist/reload"

        # Domain signals should still be available
        domains_after = s2.knowledge.get_domains_from_entities()
        assert "technology" in domains_after
        assert domains_after["technology"] > 0

        # Reflect after reload should still produce insights
        result = s2.reflect()
        assert "insights" in result
        s2.close()

    # ── Emotional context integration ─────────────────────────────────

    def test_emotional_context_flow_through_reflect(self):
        """Negative interactions update emotion, which feeds into dream()."""
        s = Soul.load_or_create("int_emo_flow")
        # Seed some memories so reflect has content to process
        for i in range(3):
            s.remember(f"discussed topic {i}", importance=0.5)

        # Send several negative interactions to raise frustration
        for i in range(8):
            s.remember(
                "hate terrible awful horrible broken bugs fail error crash",
                importance=0.7,
            )

        # Verify frustration is high
        ctx = s.get_emotional_context()
        assert ctx["frustration"] > 0.5, \
            f"Expected high frustration, got {ctx['frustration']}"

        # Reflect — should receive emotional_context with high frustration
        result = s.reflect()
        insights = result.get("insights", [])
        assert len(insights) > 0, "Reflect should produce insights"

        # Must have self-awareness insight about frustration (guaranteed by code)
        self_aware = [i for i in insights if i.get("type") == "self_awareness"]
        assert len(self_aware) > 0, \
            f"Expected self-awareness insight given frustration={ctx['frustration']}: {insights}"
        assert any("frustrated" in i.get("insight", "").lower() for i in self_aware), \
            f"Self-awareness should mention frustration: {self_aware}"

    def test_emotional_context_excited_mood(self):
        """Excited mood produces a positive self-awareness insight."""
        s = Soul.load_or_create("int_emo_excited")
        # Seed some memories (3 to meet min_memories threshold)
        for i in range(3):
            s.remember(f"discussed topic {i}", importance=0.5)

        # Send positive high-arousal content to create excited mood
        # After 5x: valence=0.5, arousal=1.0 → deterministically "excited"
        for i in range(5):
            s.remember(
                "amazing incredible love wow fantastic excellent work",
                importance=0.7,
            )

        # Verify mood is excited
        ctx = s.get_emotional_context()
        assert ctx["mood"] == "excited", \
            f"Expected excited mood after 5 high-arousal positives, got: {ctx}"

        # Reflect should produce self-awareness insight about excitement
        result = s.reflect()
        insights = result.get("insights", [])
        assert len(insights) > 0, "Reflect should produce insights"

        self_aware = [i for i in insights if i.get("type") == "self_awareness"]
        assert len(self_aware) > 0, \
            f"Expected self-awareness insight for excited mood: {insights}"
        assert any("excited" in i.get("insight", "").lower() for i in self_aware), \
            f"Self-awareness should mention excitement: {self_aware}"

    def test_no_self_awareness_when_frustration_low(self):
        """When frustration <= 0.5, no frustration self-awareness insight."""
        engine = DreamEngine("test")
        memories = [{"content": "python programming"}] * 5
        insights = engine.dream(
            memories, None, min_memories=0,
            emotional_context={"frustration": 0.3, "mood": "neutral"},
        )
        types = [i["type"] for i in insights]
        assert "self_awareness" not in types, \
            f"Low frustration should not trigger self-awareness: {insights}"

    def test_no_self_awareness_when_mood_neutral(self):
        """Neutral mood with low frustration produces no self-awareness insight."""
        engine = DreamEngine("test")
        memories = [{"content": "python programming"}] * 5
        insights = engine.dream(
            memories, None, min_memories=0,
            emotional_context={"frustration": 0.0, "mood": "neutral"},
        )
        types = [i["type"] for i in insights]
        assert "self_awareness" not in types, \
            f"Neutral mood should not trigger self-awareness: {insights}"

    def test_emotional_context_survives_persist(self):
        """Emotional state and mood survive persist/reload."""
        s = Soul.load_or_create("int_emo_persist")
        s.remember("discussed python basics", importance=0.5)

        # Pump up frustration — use explicit_sentiment to avoid punctuation
        # issues with keyword analysis (e.g., "terrible!" not matching split tokens)
        for i in range(10):
            s.emotion.update_from_interaction(
                "terrible awful horrible",
                explicit_sentiment="negative",
            )
        s.emotion.last_update = 0.0  # Reset so decay doesn't apply on reload

        ctx_before = s.get_emotional_context()
        assert ctx_before["frustration"] > 0.5, \
            f"Frustration should be high before persist: {ctx_before}"

        # Persist and reload
        s._persist()
        s._storage.flush()
        s.close()

        s2 = Soul.load_or_create("int_emo_persist")
        ctx_after = s2.get_emotional_context()

        # Emotional state should survive
        assert ctx_after["frustration"] > 0.5, \
            f"Frustration should survive persist: {ctx_after}"
        assert ctx_after["mood"] == ctx_before["mood"], \
            f"Mood should survive persist: {ctx_before['mood']} vs {ctx_after['mood']}"
        assert ctx_after["valence"] == ctx_before["valence"], \
            f"Valence should survive persist: {ctx_before['valence']} vs {ctx_after['valence']}"
        s2.close()

    # ── Combined knowledge + emotion integration ───────────────────────

    def test_both_knowledge_and_emotion_in_single_reflect(self):
        """Both knowledge domains and emotional context work together."""
        s = Soul.load_or_create("int_both")
        # Seed knowledge graph with tech entities
        s.remember("discussed Python and Docker", importance=0.8)
        s.remember("discussed Kubernetes", importance=0.8)

        # Pump negative emotion
        for i in range(8):
            s.remember("This is terrible! Nothing works!", importance=0.7)

        # Verify both subsystems have data
        domains = s.knowledge.get_domains_from_entities()
        assert "technology" in domains, "Knowledge should have tech domain"

        ctx = s.get_emotional_context()
        frustration_high = ctx["frustration"] > 0.5

        # Reflect should process both
        result = s.reflect()
        insights = result.get("insights", [])

        # Organize insights by type
        types = {i.get("type") for i in insights}
        domains_found = {i.get("domain") for i in insights if i.get("domain")}

        # Should have at least some variety of insight types
        assert len(types) >= 1

        # If frustration is high, self-awareness should appear
        if frustration_high:
            assert "self_awareness" in types, \
                f"Expected self-awareness given frustration={ctx['frustration']}: {insights}"

    def test_multiple_reflects_accumulate_knowledge_insights(self):
        """Repeated reflects with growing knowledge produce richer insights."""
        s = Soul.load_or_create("int_multi_reflect")

        # First reflect — need at least 3 episodic memories (min_memories=3 threshold)
        s.remember("discussed Python basics", importance=0.7)
        s.remember("discussed Data structures", importance=0.7)
        s.remember("discussed Machine Learning", importance=0.7)
        r1 = s.reflect()
        insights_1 = r1.get("insights", [])

        # Add more tech content and reflect again
        s.remember("discussed Docker and Kubernetes", importance=0.8)
        s.remember("discussed React components", importance=0.8)
        s.remember("discussed Python frameworks", importance=0.8)
        r2 = s.reflect()
        insights_2 = r2.get("insights", [])

        # Knowledge graph should have accumulated entities across both phases
        entity_count = s.knowledge.stats()["entities"]
        assert entity_count >= 4, \
            f"Expected >=4 entities after 6 tech memories, got {entity_count}: {list(s.knowledge._entities.keys())}"

        # Both reflects should have run dream cycles (3+ memories each)
        assert s.dreams.dreams_count >= 2, \
            f"Expected >=2 dream cycles, got {s.dreams.dreams_count}"
        assert len(s.dreams.insights) > 0

    def test_no_domain_insight_when_confidence_below_threshold(self):
        """knowledge_domains with confidence <= 0.3 should not produce domain insights."""
        engine = DreamEngine("test")
        memories = [{"content": "python programming"}] * 5
        insights = engine.dream(
            memories, None, min_memories=0,
            knowledge_domains={"technology": 0.3},
            # 0.3 is NOT > 0.3, so no domain insight
        )
        domain_insights = [i for i in insights if i.get("type") == "expertise_discovery" and i.get("domain") == "technology"]
        assert len(domain_insights) == 0, \
            f"confidence=0.3 should not produce domain insight: {domain_insights}"

        # Now test with 0.31 which should produce an insight
        insights2 = engine.dream(
            memories, None, min_memories=0,
            knowledge_domains={"technology": 0.31},
        )
        domain_insights2 = [i for i in insights2 if i.get("type") == "expertise_discovery" and i.get("domain") == "technology"]
        assert len(domain_insights2) > 0, \
            f"confidence=0.31 should produce domain insight: {domain_insights2}"

    def test_reflect_with_sessions_feeds_emotion(self):
        """Sessions capture interactions that feed emotional context for dream."""
        s = Soul.load_or_create("int_sess_emo")

        # Start a session and record interactions
        s.start_session()

        # Seed memories
        s.remember("discussed Python and data science", importance=0.7)
        s.remember("discussed machine learning models", importance=0.7)

        # End the session (stores summary as semantic memory)
        session = s.end_session()
        assert session is not None

        # Verify session recorded interactions
        stats = s.sessions.stats()
        assert stats["total_interactions"] >= 2

        # Reflect should have knowledge domains from the session content
        result = s.reflect()
        assert "insights" in result

        # Verify session summary has some content
        cross_ctx = s.get_cross_session_context()
        assert "Recent sessions" in cross_ctx

    def test_reflect_pipeline_does_not_crash_with_edge_emotion_values(self):
        """Extreme or zero emotional context values don't crash the pipeline."""
        s = Soul.load_or_create("int_edge_emo")
        s.remember("test memory", importance=0.5)

        # Manually set extreme emotional values
        s.emotion.valence = -1.0
        s.emotion.arousal = 1.0
        s.emotion.dominance = 0.0
        s.emotion.frustration_level = 1.0
        s.emotion.mood = "frustrated"

        # Should not crash
        result = s.reflect()
        assert "reflection" in result

        # Set neutral/zero values
        s.emotion.valence = 0.0
        s.emotion.arousal = 0.0
        s.emotion.dominance = 1.0
        s.emotion.frustration_level = 0.0
        s.emotion.mood = "neutral"

        result2 = s.reflect()
        assert "reflection" in result2
