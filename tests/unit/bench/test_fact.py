"""FactScorer with a scripted judge + fake fetcher (official-parity semantics)."""

from __future__ import annotations

import json

from bench.fact import FactScorer
from research_engine.llm.provider import Message

_TRIPLETS = """[
  {"fact": "Claim A", "ref_idx": "1", "url": "http://a.example"},
  {"fact": "Claim B", "ref_idx": "2", "url": "http://b.example"},
  {"fact": "Claim A", "ref_idx": "1", "url": "http://a.example"}
]"""


class _Judge:
    """Returns triplets for extraction; batched per-URL verdicts for validation.

    Validation protocol mirrors the official bench: one call per URL with all its
    numbered statements; response = JSON list of {"idx": 1-based, "result": ...}.
    """

    default_model = "fake"

    def __init__(self, verdicts: dict[str, str] | None = None) -> None:
        # claim text -> supported|unsupported|unknown
        self.verdicts = verdicts or {"Claim A": "supported", "Claim B": "unsupported"}
        self.validate_calls: list[str] = []

    def complete(self, messages: list[Message], model: str | None = None,
                 temperature: float = 0.7, max_tokens: int | None = None,
                 format: dict | None = None) -> str:  # noqa: A002
        content = messages[0].content
        if "<statements>" in content:
            self.validate_calls.append(content)
            block = content.split("<statements>")[1].split("</statements>")[0]
            out = []
            for line in block.strip().splitlines():
                idx, _, claim = line.partition(". ")
                out.append({"idx": int(idx), "result": self.verdicts.get(claim.strip(), "unknown")})
            return json.dumps(out)
        return _TRIPLETS


def _fetch(url: str) -> str:
    return f"content of {url}"


def test_fact_dedupes_and_scores() -> None:
    res = FactScorer(_Judge(), fetch_url=_fetch).score(1, "article body")
    assert res["num_pairs"] == 2  # dedup removes the repeat (Claim A, a.example)
    assert res["num_supported"] == 1
    assert res["num_unsupported"] == 1
    assert res["num_unknown"] == 0
    assert abs(res["citation_accuracy"] - 0.5) < 1e-9
    assert res["effective_citations"] == 1


def test_fact_no_citations() -> None:
    class _Empty(_Judge):
        def complete(self, messages: list[Message], model: str | None = None,
                     temperature: float = 0.7, max_tokens: int | None = None,
                     format: dict | None = None) -> str:  # noqa: A002
            return "[]"

    res = FactScorer(_Empty(), fetch_url=_fetch).score(1, "no citations here")
    assert res["num_pairs"] == 0
    assert res["citation_accuracy"] == 0.0


def test_fact_unknown_excluded_from_denominator() -> None:
    """Official stat.py parity: 'unknown' pairs drop out of the accuracy denominator."""
    judge = _Judge({"Claim A": "supported", "Claim B": "unknown"})
    res = FactScorer(judge, fetch_url=_fetch).score(1, "x")
    assert res["num_supported"] == 1
    assert res["num_unknown"] == 1
    assert res["num_unsupported"] == 0
    assert res["citation_accuracy"] == 1.0  # 1 / (1 supported + 0 unsupported)
    assert abs(res["citation_accuracy_all"] - 0.5) < 1e-9  # legacy all-pairs view


def test_fact_failed_fetch_counts_unknown_not_unsupported() -> None:
    """Official parity: an unfetchable page is 'unknown' (excluded), not a miss."""
    scorer = FactScorer(_Judge(), fetch_url=lambda u: "scrape failed: boom", retry_sleep=0.0)
    res = scorer.score(1, "x")
    assert res["num_supported"] == 0
    assert res["num_unknown"] == 2
    assert res["citation_accuracy"] == 0.0  # empty official denominator
    assert res["citation_accuracy_all"] == 0.0


def test_fact_fetch_retries_then_succeeds() -> None:
    """Official scrape.py parity: up to 3 fetch attempts per URL."""
    attempts: dict[str, int] = {}

    def flaky(url: str) -> str:
        attempts[url] = attempts.get(url, 0) + 1
        if attempts[url] < 3:
            return "scrape failed: transient"
        return f"content of {url}"

    res = FactScorer(_Judge(), fetch_url=flaky, retry_sleep=0.0).score(1, "x")
    assert all(n == 3 for n in attempts.values())
    assert res["num_supported"] == 1
    assert res["num_unknown"] == 0


def test_fact_batches_statements_per_url() -> None:
    """All statements citing one URL are validated in a single judge call."""

    class _SameUrl(_Judge):
        def complete(self, messages: list[Message], model: str | None = None,
                     temperature: float = 0.7, max_tokens: int | None = None,
                     format: dict | None = None) -> str:  # noqa: A002
            content = messages[0].content
            if "<statements>" in content:
                return super().complete(messages, model, temperature, max_tokens)
            return json.dumps(
                [
                    {"fact": "Claim A", "ref_idx": "1", "url": "http://a.example"},
                    {"fact": "Claim B", "ref_idx": "1", "url": "http://a.example"},
                ]
            )

    judge = _SameUrl()
    res = FactScorer(judge, fetch_url=_fetch).score(1, "x")
    assert len(judge.validate_calls) == 1  # one batched call for both statements
    assert res["num_pairs"] == 2
    assert res["num_supported"] == 1
    assert res["num_unsupported"] == 1


def test_fact_validate_parse_failure_counts_unknown() -> None:
    """Official validate.py parity: a citation whose judge call keeps failing is
    excluded from the denominator (we report its statements as unknown)."""

    class _Broken(_Judge):
        def complete(self, messages: list[Message], model: str | None = None,
                     temperature: float = 0.7, max_tokens: int | None = None,
                     format: dict | None = None) -> str:  # noqa: A002
            content = messages[0].content
            if "<statements>" in content:
                return "not json at all"
            return _TRIPLETS

    res = FactScorer(_Broken(), fetch_url=_fetch, retry_sleep=0.0).score(1, "x")
    assert res["num_unknown"] == 2
    assert res["num_supported"] == 0
    assert res["citation_accuracy"] == 0.0


def test_default_fetcher_html_path_and_close(monkeypatch) -> None:
    """default_fetcher: html fetch + markdownify + close() releases the browser."""
    import bench.fact as fact_mod
    from research_engine.browser.ai_browser import BrowserResult

    monkeypatch.setenv("RESEARCH_ENGINE_BENCH_FACT_CDP", "0")  # no Chromium in unit tests

    class _B:
        policy = None
        closed = False

        def act(self, action):  # noqa: ANN001
            return BrowserResult(
                ok=True, action=action.action, url=action.url, status=200,
                content="<html><body><p>Sovereign funds hold equities.</p></body></html>",
            )

        def close(self):
            self.closed = True

    b = _B()
    fetch = fact_mod.default_fetcher(b)  # type: ignore[arg-type]
    out = fetch("https://x.example/page")
    assert "Sovereign funds hold equities" in out
    fetch.close()  # type: ignore[attr-defined]
    assert b.closed is True


def test_default_fetcher_failure_reports_scrape_failed(monkeypatch) -> None:
    import bench.fact as fact_mod
    from research_engine.browser.ai_browser import BrowserResult

    monkeypatch.setenv("RESEARCH_ENGINE_BENCH_FACT_CDP", "0")

    class _B:
        policy = None

        def act(self, action):  # noqa: ANN001
            return BrowserResult(
                ok=False, action=action.action, url=action.url, status=403,
                content="", error="HTTP error 403",
            )

        def close(self):
            pass

    fetch = fact_mod.default_fetcher(_B())  # type: ignore[arg-type]
    assert fetch("https://blocked.example/x").startswith("scrape failed: HTTP error 403")


def test_validate_normalizes_zero_based_idx_and_loose_verdicts() -> None:
    """Local judges emit 0-based idx and yes/true/neutral verdicts; both normalize."""

    class _Loose(_Judge):
        def complete(self, messages: list[Message], model: str | None = None,
                     temperature: float = 0.7, max_tokens: int | None = None,
                     format: dict | None = None) -> str:  # noqa: A002
            content = messages[0].content
            if "<statements>" in content:
                return json.dumps(
                    [
                        {"idx": 0, "result": "Yes"},
                        {"idx": 1, "result": "neutral"},
                    ]
                )
            return json.dumps(
                [
                    {"fact": "Claim A", "ref_idx": "1", "url": "http://a.example"},
                    {"fact": "Claim B", "ref_idx": "1", "url": "http://a.example"},
                ]
            )

    res = FactScorer(_Loose(), fetch_url=_fetch, retry_sleep=0.0).score(1, "x")
    assert res["num_supported"] == 1  # Yes -> supported (0-based idx detected)
    assert res["num_unknown"] == 1  # neutral -> unknown
    assert res["citation_accuracy"] == 1.0
