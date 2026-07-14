"""Unit tests for the attribute-first writer (Phase 1.0 spike)."""

from __future__ import annotations

from research_engine.memory.evidence_bank import EvidenceBank
from research_engine.synthesis.attribute_writer import AttributeFirstWriter


class _FakeProvider:
    def __init__(self, reply: str) -> None:
        self.reply = reply
        self.calls = 0

    def complete(self, messages, model=None, temperature=0.0, max_tokens=None):  # noqa: ANN001
        self.calls += 1
        return self.reply


def _bank(*claims_per_source):
    sources = []
    for i, claims in enumerate(claims_per_source):
        sources.append(
            {
                "title": f"S{i}",
                "paper": {"url": f"https://s{i}.org", "title": f"S{i}"},
                "claims": claims,
            }
        )
    return EvidenceBank.from_sources(sources)


def test_writes_body_with_citations_and_references() -> None:
    bank = _bank([{"claim": "c", "evidence": "Aging reaches 35% by 2040."}])
    writer = AttributeFirstWriter(_FakeProvider("Aging reaches 35% by 2040 [e1]."))
    out = writer.write(bank, "japan aging")
    assert "[e1]" in out
    assert "## References" in out
    assert "https://s0.org" in out


def test_foreign_citation_ids_stripped() -> None:
    # Model cites an id not in this source's cluster -> removed (no cross-source mis-cite).
    bank = _bank([{"claim": "c", "evidence": "Fact one."}])
    writer = AttributeFirstWriter(_FakeProvider("Fact one [e1]. Fabricated [e99]."))
    out = writer.write(bank, "q")
    assert "[e1]" in out
    assert "[e99]" not in out


def test_empty_bank_returns_empty() -> None:
    writer = AttributeFirstWriter(_FakeProvider("nothing"))
    assert writer.write(EvidenceBank.from_sources([]), "q") == ""


def test_one_call_per_source() -> None:
    bank = _bank(
        [{"claim": "a", "evidence": "First span."}],
        [{"claim": "b", "evidence": "Second span."}],
    )
    provider = _FakeProvider("Text [e1].")
    AttributeFirstWriter(provider).write(bank, "q")
    assert provider.calls == 2  # grouped by source URL


def test_provider_failure_is_nonfatal() -> None:
    class _Boom:
        def complete(self, *a, **k):  # noqa: ANN002, ANN003
            raise RuntimeError("model down")

    bank = _bank([{"claim": "c", "evidence": "span"}])
    # A failed source is skipped, not crashed; empty overall -> "".
    assert AttributeFirstWriter(_Boom()).write(bank, "q") == ""
