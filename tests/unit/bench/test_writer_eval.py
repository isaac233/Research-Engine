"""The writer-eval harness must rebuild the bank deterministically from cached
sources (no re-fetch) and dispatch each writer variant."""

from __future__ import annotations

from bench.writer_eval import WRITERS
from research_engine.memory.evidence_bank import EvidenceBank


class _Echo:
    def complete(self, messages, model=None, temperature=0.0, max_tokens=None):  # noqa: ANN001
        body = messages[-1].content
        lines = [ln for ln in body.splitlines() if ln.strip().startswith("[e")]
        return " ".join(f"{ln.split('] ', 1)[-1]} [{ln.split(']')[0].strip('[')}]" for ln in lines)


def _cached_source() -> dict:
    return {
        "title": "Aging",
        "paper": {"url": "https://a.org", "title": "Aging"},
        "meta": {
            "page_text": (
                "Japan's elderly population reaches 35 percent by 2040 clearly. "
                "Senior consumer spending on housing rises sharply each year."
            )
        },
        "claims": [],
    }


def test_bank_rebuilds_from_cache_without_fetching() -> None:
    def boom(url: str) -> str:
        raise AssertionError("cached page_text must be reused, not fetched")

    bank = EvidenceBank.from_pages([_cached_source()], boom, "elderly spending")
    assert bank.spans()
    assert all(s.url == "https://a.org" for s in bank.spans())


def test_variants_dispatch_and_produce_articles() -> None:
    bank = EvidenceBank.from_pages([_cached_source()], lambda _u: "", "elderly spending")
    for name, fn in WRITERS.items():
        article = fn(bank, "elderly spending", _Echo(), None)
        assert article.strip(), f"variant {name} produced empty"
        assert "## References" in article
