"""Tests for the deep auditor."""

from __future__ import annotations

from typing import Any

from research_engine.evaluation.deep_audit import DeepAuditor
from research_engine.llm.provider import LLMProvider, Message


class FakeProvider(LLMProvider):
    name = "fake"

    def __init__(self, response: str) -> None:
        self.response = response

    def complete(
        self,
        messages: list[Message],
        model: str | None = None,
        temperature: float = 0.7,
        max_tokens: int | None = None,
    ) -> str:
        return self.response

    def ping(self) -> dict[str, Any]:
        return {"ok": True}

    @property
    def default_model(self) -> str:
        return "fake-model"


def test_deep_audit_skips_without_provider() -> None:
    auditor = DeepAuditor()
    result = auditor.audit({"key": "value"})

    assert result.anomalies == []
    assert any("skipped" in r.lower() for r in result.recommendations)


def test_deep_audit_parses_response() -> None:
    response = """ANOMALIES:
- no verifiable source
RECOMMENDATIONS:
- re-run extraction with PDF fetcher"""
    auditor = DeepAuditor(FakeProvider(response))
    result = auditor.audit({"campaign_id": "c1"})

    assert result.anomalies == ["no verifiable source"]
    assert result.recommendations == ["re-run extraction with PDF fetcher"]
    assert result.raw_response == response


def test_deep_audit_captures_provider_failure() -> None:
    class FailingProvider(FakeProvider):
        def complete(
            self,
            messages: list[Message],
            model: str | None = None,
            temperature: float = 0.7,
            max_tokens: int | None = None,
        ) -> str:
            raise RuntimeError("model down")

    auditor = DeepAuditor(FailingProvider(""))
    result = auditor.audit({"campaign_id": "c1"})

    assert result.anomalies == []
    assert any("failed" in r.lower() for r in result.recommendations)
