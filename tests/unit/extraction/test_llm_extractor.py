"""Unit tests for the LLM full-text section extractor."""

from __future__ import annotations

from typing import Any

from research_engine.extraction.llm_extractor import LLMSectionExtractor
from research_engine.llm.provider import LLMProvider, Message

FULL_TEXT = (
    "Methods. We trained a ResNet-50 on ImageNet for 90 epochs with SGD.\n\n"
    "Data. We used the ImageNet-1k dataset of 1.28 million images.\n\n"
    "Results. Top-1 accuracy improved from 76.1% to 78.4% with our augmentation."
)


class FakeProvider(LLMProvider):
    name = "fake"

    def __init__(self, response: str) -> None:
        self._response = response
        self.calls = 0

    def complete(
        self, messages: list[Message], model: str | None = None,
        temperature: float = 0.7, max_tokens: int | None = None,
    ) -> str:
        self.calls += 1
        return self._response

    def ping(self) -> dict[str, Any]:
        return {"ok": True}

    @property
    def default_model(self) -> str:
        return "fake-model"


_GOOD_JSON = """{
  "methodology": "Trained a ResNet-50 on ImageNet for 90 epochs with SGD.",
  "data_summary": "ImageNet-1k dataset of 1.28 million images.",
  "results_summary": "Top-1 accuracy improved from 76.1% to 78.4%.",
  "conclusions": "The augmentation helps.",
  "replication_notes": "Need the augmentation hyperparameters.",
  "claims": [
    {"claim": "Accuracy improved", "evidence": "Top-1 accuracy improved from 76.1% to 78.4% with our augmentation", "section": "results", "confidence": "high"}
  ]
}"""


def test_parses_sections_and_claims() -> None:
    ext = LLMSectionExtractor(FakeProvider(_GOOD_JSON), model="m")
    out = ext.extract_sections("Title", "abstract", FULL_TEXT)
    assert "ResNet-50" in out.methodology
    assert "ImageNet-1k" in out.data_summary
    assert "78.4%" in out.results_summary
    assert out.conclusions and out.replication_notes
    assert len(out.claims) == 1
    assert out.claims[0].confidence == "high"


def test_absent_sections_become_empty() -> None:
    resp = '{"methodology": "ABSENT", "data_summary": "ABSENT", "results_summary": "ABSENT", "conclusions": "ABSENT", "replication_notes": "none", "claims": []}'
    out = LLMSectionExtractor(FakeProvider(resp)).extract_sections("t", "a", FULL_TEXT)
    assert out.methodology == ""
    assert out.data_summary == ""


def test_malformed_json_degrades_gracefully() -> None:
    out = LLMSectionExtractor(FakeProvider("sorry, I cannot comply")).extract_sections(
        "t", "a", FULL_TEXT
    )
    assert out.methodology == ""
    assert out.claims == []
    assert "error" in out.meta


def test_hallucinated_evidence_is_dropped() -> None:
    resp = """{
      "methodology": "m", "data_summary": "d", "results_summary": "r",
      "conclusions": "c", "replication_notes": "n",
      "claims": [
        {"claim": "real", "evidence": "Top-1 accuracy improved from 76.1% to 78.4%", "section": "results", "confidence": "high"},
        {"claim": "fabricated", "evidence": "accuracy reached 99.9% on a secret dataset", "section": "results", "confidence": "high"}
      ]
    }"""
    out = LLMSectionExtractor(FakeProvider(resp)).extract_sections("t", "a", FULL_TEXT)
    claims = [c.claim for c in out.claims]
    assert "real" in claims
    assert "fabricated" not in claims
    assert out.meta["unverified_dropped"] == 1


def test_json_inside_code_fence_and_prose() -> None:
    resp = "Here is the result:\n```json\n" + _GOOD_JSON + "\n```\nDone."
    out = LLMSectionExtractor(FakeProvider(resp)).extract_sections("t", "a", FULL_TEXT)
    assert "ResNet-50" in out.methodology


def test_empty_full_text_returns_empty() -> None:
    out = LLMSectionExtractor(FakeProvider(_GOOD_JSON)).extract_sections("t", "a", "")
    assert out.methodology == ""
    assert "error" in out.meta


def test_structured_extractor_uses_llm_path_on_full_text() -> None:
    from research_engine.discovery.schema import Paper
    from research_engine.extraction.structured import StructuredExtractor

    ext = LLMSectionExtractor(FakeProvider(_GOOD_JSON), model="m")
    se = StructuredExtractor(llm_extractor=ext)
    paper = Paper(title="T", source="s", source_id="1", doi="10.1/1", abstract="abs")
    src = se.extract(paper, content=FULL_TEXT)
    assert src.extraction_tool == "llm:m"
    assert "ResNet-50" in src.methodology
    assert src.conclusions != ""


def test_structured_extractor_skips_llm_when_abstract_only() -> None:
    from research_engine.discovery.schema import Paper
    from research_engine.extraction.structured import StructuredExtractor

    provider = FakeProvider(_GOOD_JSON)
    se = StructuredExtractor(llm_extractor=LLMSectionExtractor(provider, model="m"))
    paper = Paper(title="T", source="s", source_id="1", doi="10.1/1", abstract="Only an abstract.")
    src = se.extract(paper)  # no content, no url, not OA -> abstract fallback
    assert src.meta.get("degraded") == "abstract_only"
    assert provider.calls == 0  # LLM never invoked on abstract-only
