"""Tests for the discovery source cache."""

from __future__ import annotations

from pathlib import Path

import pytest

from research_engine.discovery.schema import Paper
from research_engine.storage.cache import SourceCache


@pytest.fixture
def cache(tmp_path: Path) -> SourceCache:
    return SourceCache(tmp_path / "cache.db")


def test_empty_cache(cache: SourceCache) -> None:
    assert cache.get("machine learning") == []
    assert cache.get_papers("machine learning") == []
    assert not cache.has("machine learning")


def test_put_and_get_round_trip(cache: SourceCache) -> None:
    paper = Paper(
        title="Deep Learning",
        authors=["A", "B"],
        year=2024,
        doi="10.1000/dl",
        url="https://example.com/dl",
        source="arxiv",
    )
    inserted = cache.put("machine learning", "arxiv", [paper])
    assert inserted == 1

    assert cache.has("machine learning", "arxiv")
    assert cache.has("machine learning")
    results = cache.get("machine learning", "arxiv")
    assert len(results) == 1
    assert results[0].paper.title == "Deep Learning"
    assert results[0].paper.doi == "10.1000/dl"
    assert results[0].source == "arxiv"


def test_get_papers_filtered_by_source(cache: SourceCache) -> None:
    arxiv = Paper(title="Arxiv Paper", source="arxiv")
    crossref = Paper(title="Crossref Paper", source="crossref")
    cache.put("q", "arxiv", [arxiv])
    cache.put("q", "crossref", [crossref])

    assert len(cache.get_papers("q")) == 2
    assert len(cache.get_papers("q", "arxiv")) == 1
    assert cache.get_papers("q", "arxiv")[0].source == "arxiv"
    assert cache.get_papers("q", "missing") == []


def test_clear(cache: SourceCache) -> None:
    cache.put("q", "arxiv", [Paper(title="P", source="arxiv")])
    assert cache.has("q")
    deleted = cache.clear()
    assert deleted == 1
    assert not cache.has("q")


def test_put_replaces_duplicate_keys(cache: SourceCache) -> None:
    paper = Paper(title="First", source="arxiv", doi="10.1000/x")
    cache.put("q", "arxiv", [paper])
    updated = Paper(title="Updated", source="arxiv", doi="10.1000/x")
    cache.put("q", "arxiv", [updated])
    results = cache.get_papers("q", "arxiv")
    assert len(results) == 1
    assert results[0].title == "Updated"


def test_corrupted_json_ignored(cache: SourceCache, tmp_path: Path) -> None:
    db_path = tmp_path / "cache.db"
    cache = SourceCache(db_path)
    cache.put("q", "arxiv", [Paper(title="P", source="arxiv")])

    conn = __import__("sqlite3").connect(db_path)
    try:
        conn.execute("UPDATE source_cache SET paper_json = 'not-json'")
        conn.commit()
    finally:
        conn.close()

    assert cache.get("q", "arxiv") == []
