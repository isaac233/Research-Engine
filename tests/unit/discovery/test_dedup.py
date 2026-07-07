"""Unit tests for the deduplication engine."""

from __future__ import annotations

from research_engine.discovery.dedup import DedupEngine
from research_engine.discovery.schema import Paper


def paper(
    title: str,
    doi: str | None = None,
    url: str | None = None,
    year: int | None = None,
    source: str = "test",
) -> Paper:
    return Paper(
        title=title,
        doi=doi,
        url=url,
        year=year,
        source=source,
        source_id="id",
    )


def test_doi_exact_match() -> None:
    engine = DedupEngine()
    papers = [
        paper("Large Language Models", doi="10.1234/llm", year=2023),
        paper("LLMs: A Survey", doi="10.1234/llm", year=2023),
    ]
    groups = engine.deduplicate(papers)
    assert len(groups) == 1
    assert len(groups[0].duplicates) == 1
    assert groups[0].match_reason == "doi_exact"


def test_url_exact_match() -> None:
    engine = DedupEngine()
    papers = [
        paper("Paper A", url="https://example.com/paper-a", year=2022),
        paper("Paper A", url="http://www.example.com/paper-a/", year=2022),
    ]
    groups = engine.deduplicate(papers)
    assert len(groups) == 1
    assert groups[0].match_reason == "url_exact"


def test_title_similarity_groups() -> None:
    engine = DedupEngine()
    papers = [
        paper("Attention is All You Need", year=2017),
        paper("Attention Is All You Need: A Survey", year=2017),
        paper("Completely different topic", year=2020),
    ]
    groups = engine.deduplicate(papers)
    assert len(groups) == 2


def test_different_year_same_title_not_duplicate() -> None:
    engine = DedupEngine()
    papers = [
        paper("Annual Report", year=2022),
        paper("Annual Report", year=2023),
    ]
    groups = engine.deduplicate(papers)
    assert len(groups) == 2


def test_empty_list() -> None:
    engine = DedupEngine()
    assert engine.deduplicate([]) == []


def test_stats_counts() -> None:
    engine = DedupEngine()
    papers = [
        paper("One", doi="10.1/one"),
        paper("One again", doi="10.1/one"),
        paper("Two", doi="10.1/two"),
    ]
    groups = engine.deduplicate(papers)
    stats = engine.stats(groups)
    assert stats["input_count"] == 3
    assert stats["canonical_count"] == 2
    assert stats["duplicate_count"] == 1


def test_f1_on_synthetic_pairs() -> None:
    """Hand-labeled synthetic sample: 25 duplicate pairs + 25 non-duplicate pairs."""
    engine = DedupEngine()

    duplicates: list[tuple[Paper, Paper, bool]] = []
    for i in range(25):
        duplicates.append(
            (
                paper(f"Shared Title {i}", doi=f"10.dup/{i}", year=2024),
                paper(f"Shared Title {i}: Extended", doi=f"10.dup/{i}", year=2024),
                True,
            )
        )
    for i in range(25):
        duplicates.append(
            (
                paper(f"Unique Title {i}", doi=f"10.uniq/{i}", year=2024),
                paper(f"Other Unique {i + 100}", doi=f"10.other/{i}", year=2024),
                False,
            )
        )

    tp = fp = tn = fn = 0
    for a, b, is_dup in duplicates:
        predicted = bool(engine.is_duplicate(a, b))
        if predicted and is_dup:
            tp += 1
        elif predicted and not is_dup:
            fp += 1
        elif not predicted and not is_dup:
            tn += 1
        else:
            fn += 1

    precision = tp / (tp + fp) if (tp + fp) else 0.0
    recall = tp / (tp + fn) if (tp + fn) else 0.0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) else 0.0
    assert f1 >= 0.90, f"F1 {f1} below 0.90"
