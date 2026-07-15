"""WARP-style deepening: diagnose shallow sections, expand from the bank."""

from __future__ import annotations

import json

from research_engine.memory.evidence_bank import EvidenceBank
from research_engine.synthesis.deepen import deepen_report


def _bank() -> EvidenceBank:
    src = {
        "title": "Aging",
        "paper": {"url": "https://a.org", "title": "Aging"},
        "meta": {
            "page_text": (
                "Japan's elderly population reaches 35 percent by 2040 clearly. "
                "Health spending on seniors rose twelve percent over the decade widely. "
                "Elderly transportation demand shifts toward accessible services strongly."
            )
        },
        "claims": [],
    }
    return EvidenceBank.from_pages([src], lambda _u: "", query="elderly")


class _Provider:
    """Diagnose (contains 'superficial') returns one shallow section; the write call
    echoes its evidence lines."""

    def complete(self, messages, model=None, temperature=0.0, max_tokens=None):  # noqa: ANN001
        body = messages[-1].content
        if "superficial" in body:
            return json.dumps({"expand": [{"section": "Transport", "subquestion": "transportation demand"}]})
        lines = [ln for ln in body.splitlines() if ln.strip().startswith("[e")]
        return " ".join(f"{ln.split('] ', 1)[-1]} [{ln.split(']')[0].strip('[')}]" for ln in lines)


def test_deepen_appends_to_named_section() -> None:
    bank = _bank()  # spans (query 'elderly'): e1 population, e2 transportation
    draft = (
        "# Research Brief: elderly market\n\n"
        "## Population\n\nJapan ages fast [e1].\n\n"
        "## Transport\n\nSeniors travel [e2].\n\n## References\n\n[e1, e2] Aging — https://a.org\n"
    )
    out = deepen_report(draft, bank, "elderly market", _Provider(), None)
    # Deepening content is inserted under Transport, before References; refs intact.
    assert out.index("## Transport") < out.index("## References")
    assert "## References" in out
    assert len(out) > len(draft)  # content was added
    assert "[e2]" in out.split("## Transport")[1].split("## References")[0]


def test_deepen_no_expansion_returns_draft_unchanged() -> None:
    class _Empty:
        def complete(self, *a, **k):  # noqa: ANN002, ANN003
            return '{"expand": []}'

    draft = "# R\n\n## A\n\nx [e1].\n\n## References\n\n[e1] Aging — https://a.org\n"
    assert deepen_report(draft, _bank(), "q", _Empty(), None) == draft
