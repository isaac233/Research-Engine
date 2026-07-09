"""Unit tests for the source-memory database."""

from __future__ import annotations

from pathlib import Path

import pytest

from research_engine.storage.source_memory import SourceMemory


@pytest.fixture
def memory(tmp_path: Path) -> SourceMemory:
    return SourceMemory(tmp_path / "source_memory.db")


def test_remember_and_get(memory: SourceMemory) -> None:
    entry = memory.remember(
        canonical_url="https://arxiv.org/abs/1234.5678",
        source_type="academic_repository",
        information_types=["full_text", "metadata"],
        topic_tags=["machine_learning", "transformers"],
        access_method="public_api",
        requires_auth=False,
        rate_limit_notes="3 requests per second",
        reliability_score=0.9,
        quality_notes="High-quality preprints with metadata.",
        search_hints={"api": "https://export.arxiv.org/api/query", "format": "atom+xml"},
        example_keys=["arxiv:1234.5678"],
        example_urls=["https://arxiv.org/abs/1234.5678"],
        discovery_campaign_id="campaign_1",
        meta={"license": "open_access"},
    )
    assert entry.source_id
    loaded = memory.get(entry.source_id)
    assert loaded is not None
    assert loaded.canonical_url == "https://arxiv.org/abs/1234.5678"
    assert loaded.host == "arxiv.org"
    assert loaded.source_type == "academic_repository"
    assert set(loaded.information_types) == {"full_text", "metadata"}
    assert set(loaded.topic_tags) == {"machine_learning", "transformers"}
    assert loaded.access_method == "public_api"
    assert loaded.requires_auth is False
    assert loaded.reliability_score == 0.9
    assert loaded.search_hints["format"] == "atom+xml"
    assert loaded.meta["license"] == "open_access"


def test_fts_search(memory: SourceMemory) -> None:
    memory.remember(
        canonical_url="https://api.semanticscholar.org/",
        source_type="academic_api",
        information_types=["citations", "abstracts", "metadata"],
        topic_tags=["semantic_search"],
    )
    memory.remember(
        canonical_url="https://www.crossref.org/",
        source_type="academic_api",
        information_types=["metadata", "doi"],
        topic_tags=["bibliographic"],
    )
    results = memory.search("citations")
    assert len(results) == 1
    assert results[0].host == "api.semanticscholar.org"


def test_get_by_tag(memory: SourceMemory) -> None:
    memory.remember(
        canonical_url="https://example.com/foo",
        source_type="dataset",
        topic_tags=["datasets", "nlp"],
        information_types=["download"],
    )
    memory.remember(
        canonical_url="https://example.com/bar",
        source_type="dataset",
        topic_tags=["datasets", "vision"],
        information_types=["download"],
    )
    assert len(memory.get_by_tag("datasets")) == 2
    assert len(memory.get_by_tag("nlp")) == 1
    assert len(memory.get_by_tag("download", tag_kind="information")) == 2


def test_list_tags(memory: SourceMemory) -> None:
    memory.remember(
        canonical_url="https://x.org/1",
        source_type="api",
        topic_tags=["a"],
        information_types=["t1"],
    )
    assert set(memory.list_tags("topic")) == {"a"}
    assert set(memory.list_tags("information")) == {"t1"}


def test_redacts_url_credentials(memory: SourceMemory) -> None:
    entry = memory.remember(
        canonical_url="https://user:pass@api.example.com/papers?api_key=abc123&token=secret&search=ml",
        source_type="api",
        example_urls=["https://x.com?key=secret"],
    )
    assert "user:pass@" not in entry.canonical_url
    assert "api_key=[REDACTED]" in entry.canonical_url
    assert "token=[REDACTED]" in entry.canonical_url
    assert "search=ml" in entry.canonical_url
    assert entry.example_urls[0] == "https://x.com?key=[REDACTED]"


def test_redacts_secrets_in_free_text(memory: SourceMemory) -> None:
    entry = memory.remember(
        canonical_url="https://example.com/api",
        source_type="api",
        rate_limit_notes="Use api_key=abc123456789 and token=SecretValue123",
        quality_notes="Authorization: Bearer abcdef0123456789 works",
        search_hints={"auth": "api_key=abc123456789"},
        meta={"note": "password=SuperSecret123"},
    )
    assert "api_key=[REDACTED]" in entry.rate_limit_notes
    assert "token=[REDACTED]" in entry.rate_limit_notes
    assert "Bearer [REDACTED]" in entry.quality_notes
    # Keys that look like secret holders have their whole value redacted.
    assert entry.search_hints["auth"] == "[REDACTED]"
    assert entry.meta["note"] == "password=[REDACTED]"


def test_remember_clamps_reliability_score(memory: SourceMemory) -> None:
    low = memory.remember(
        canonical_url="https://low.example.com",
        source_type="api",
        reliability_score=-0.5,
    )
    high = memory.remember(
        canonical_url="https://high.example.com",
        source_type="api",
        reliability_score=1.5,
    )
    assert low.reliability_score == 0.0
    assert high.reliability_score == 1.0


def test_update_existing_source(memory: SourceMemory) -> None:
    entry1 = memory.remember(
        canonical_url="https://same.org/page",
        source_type="news",
        reliability_score=0.5,
    )
    entry2 = memory.remember(
        canonical_url="https://same.org/page",
        source_type="news",
        reliability_score=0.8,
        quality_notes="Re-evaluated; now reliable.",
    )
    assert entry1.source_id == entry2.source_id
    loaded = memory.get(entry2.source_id)
    assert loaded.reliability_score == 0.8


def test_remember_does_not_downgrade_learned_score(memory: SourceMemory) -> None:
    """An incidental re-remember without a score must not wipe a learned score."""
    first = memory.remember(
        canonical_url="https://learned.example.com/feed",
        source_type="api",
        reliability_score=0.7,
    )
    # Re-seen during a later campaign with no fresh reliability evidence.
    second = memory.remember(
        canonical_url="https://learned.example.com/feed",
        source_type="api",
    )
    assert first.source_id == second.source_id
    assert second.reliability_score == 0.7
    assert memory.get(second.source_id).reliability_score == 0.7


def test_remember_defaults_new_source_to_neutral_score(memory: SourceMemory) -> None:
    entry = memory.remember(
        canonical_url="https://fresh.example.com/api",
        source_type="api",
    )
    assert entry.reliability_score == 0.5


def test_stats(memory: SourceMemory) -> None:
    memory.remember(
        canonical_url="https://a.b/c",
        source_type="api",
        topic_tags=["x"],
    )
    stats = memory.stats()
    assert stats["total_sources"] == 1
    assert stats["by_type"]["api"] == 1


def test_delete(memory: SourceMemory) -> None:
    entry = memory.remember(
        canonical_url="https://delete.me",
        source_type="api",
    )
    memory.delete(entry.source_id)
    assert memory.get(entry.source_id) is None


def test_clear(memory: SourceMemory) -> None:
    memory.remember(
        canonical_url="https://clear.me",
        source_type="api",
    )
    memory.clear()
    assert memory.search("clear.me") == []
    assert memory.stats()["total_sources"] == 0


def test_rejects_unsupported_url_scheme(memory: SourceMemory) -> None:
    with pytest.raises(ValueError, match="Unsupported URL scheme"):
        memory.remember(
            canonical_url="javascript:alert(1)",
            source_type="api",
        )
