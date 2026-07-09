"""FactScorer with a scripted judge + fake fetcher."""

from __future__ import annotations

from bench.fact import FactScorer
from research_engine.llm.provider import Message

_TRIPLETS = """[
  {"fact": "Claim A", "ref_idx": "1", "url": "http://a.example"},
  {"fact": "Claim B", "ref_idx": "2", "url": "http://b.example"},
  {"fact": "Claim A", "ref_idx": "1", "url": "http://a.example"}
]"""


class _Judge:
    """Returns triplets for extraction, and support verdicts keyed by claim text."""

    default_model = "fake"

    def complete(self, messages: list[Message], model: str | None = None,
                 temperature: float = 0.7, max_tokens: int | None = None) -> str:
        content = messages[0].content
        if "fact-checking judge" in content:
            # Claim A supported, Claim B not.
            return '{"supported": true}' if "Claim A" in content else '{"supported": false}'
        return _TRIPLETS


def _fetch(url: str) -> str:
    return f"content of {url}"


def test_fact_dedupes_and_scores() -> None:
    res = FactScorer(_Judge(), fetch_url=_fetch).score(1, "article body")
    assert res["num_pairs"] == 2  # dedup removes the repeat (Claim A, a.example)
    assert res["num_supported"] == 1  # only Claim A supported
    assert abs(res["citation_accuracy"] - 0.5) < 1e-9
    assert res["effective_citations"] == 1


def test_fact_no_citations() -> None:
    class _Empty(_Judge):
        def complete(self, messages: list[Message], model: str | None = None,
                     temperature: float = 0.7, max_tokens: int | None = None) -> str:
            return "[]"

    res = FactScorer(_Empty(), fetch_url=_fetch).score(1, "no citations here")
    assert res["num_pairs"] == 0
    assert res["citation_accuracy"] == 0.0


def test_fact_skips_failed_fetch() -> None:
    res = FactScorer(_Judge(), fetch_url=lambda u: "scrape failed: boom").score(1, "x")
    assert res["num_supported"] == 0
