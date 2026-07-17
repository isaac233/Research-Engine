"""Retrieval determinism cache — record-then-replay of serp results + page text."""

from __future__ import annotations

from pathlib import Path

from research_engine.discovery.retrieval_cache import RetrievalCache
from research_engine.discovery.schema import Paper


def _cache(tmp_path: Path) -> RetrievalCache:
    return RetrievalCache(tmp_path / "cache.db")


def test_serp_miss_returns_none(tmp_path: Path) -> None:
    assert _cache(tmp_path).get_serp("norway swf") is None


def test_serp_roundtrip_preserves_order(tmp_path: Path) -> None:
    c = _cache(tmp_path)
    papers = [
        Paper(title="A", url="http://a", source="serp"),
        Paper(title="B", url="http://b", source="serp"),
        Paper(title="C", url="http://c", source="serp"),
    ]
    c.put_serp("q", papers)
    got = c.get_serp("q")
    assert got is not None
    assert [p.url for p in got] == ["http://a", "http://b", "http://c"]  # order preserved
    assert [p.title for p in got] == ["A", "B", "C"]


def test_serp_empty_is_cached_not_a_miss(tmp_path: Path) -> None:
    c = _cache(tmp_path)
    c.put_serp("dry", [])
    assert c.get_serp("dry") == []  # cached empty, distinct from None (miss)


def test_serp_replace_updates(tmp_path: Path) -> None:
    c = _cache(tmp_path)
    c.put_serp("q", [Paper(title="old", url="http://old", source="serp")])
    c.put_serp("q", [Paper(title="new", url="http://new", source="serp")])
    got = c.get_serp("q")
    assert got is not None and [p.url for p in got] == ["http://new"]


def test_page_miss_returns_none(tmp_path: Path) -> None:
    assert _cache(tmp_path).get_page("http://x") is None


def test_page_roundtrip(tmp_path: Path) -> None:
    c = _cache(tmp_path)
    c.put_page("http://x", "some page text")
    assert c.get_page("http://x") == "some page text"


def test_page_empty_is_cached_not_a_miss(tmp_path: Path) -> None:
    # A dry/blocked read is recorded as "" so it isn't re-attempted live each run.
    c = _cache(tmp_path)
    c.put_page("http://blocked", "")
    assert c.get_page("http://blocked") == ""


def test_persists_across_instances(tmp_path: Path) -> None:
    db = tmp_path / "cache.db"
    RetrievalCache(db).put_page("http://x", "persisted")
    assert RetrievalCache(db).get_page("http://x") == "persisted"  # new process, same file


def test_db_error_degrades_to_miss_never_crashes(tmp_path: Path, monkeypatch) -> None:
    # A lock/IO hiccup (plausible on the OneDrive-synced repo path / concurrent runs) must
    # degrade to a miss (→ live fetch), never propagate and abort the whole task.
    import research_engine.discovery.retrieval_cache as rc

    c = rc.RetrievalCache(tmp_path / "cache.db")
    c.put_page("http://x", "text")  # populate before breaking the DB

    def boom(*_a: object, **_k: object) -> object:
        raise rc.sqlite3.OperationalError("database is locked")

    monkeypatch.setattr(rc.sqlite3, "connect", boom)
    assert c.get_page("http://x") is None  # error → miss, not an exception
    assert c.get_serp("q") is None
    c.put_page("http://y", "z")  # no raise
    c.put_serp("q", [])  # no raise


def test_env_flag_default_off(monkeypatch) -> None:
    import research_engine.orchestrator as orch

    monkeypatch.delenv("RESEARCH_ENGINE_RETRIEVAL_CACHE", raising=False)
    assert orch._retrieval_cache_enabled() is False
    monkeypatch.setenv("RESEARCH_ENGINE_RETRIEVAL_CACHE", "1")
    assert orch._retrieval_cache_enabled() is True
