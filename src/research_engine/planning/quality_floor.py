"""Minimum-quality floor for speed mode.

Even the fastest single-model run must clear a floor: the goal is addressed,
no key information is omitted (every included source yields >=1 insight), and
nothing is fabricated (every claim carries evidence). Speed mode uses this to
decide when a step must escalate one lane up.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True, slots=True)
class FloorResult:
    passed: bool
    reasons: list[str] = field(default_factory=list)

    @property
    def fabrication(self) -> list[str]:
        return [r for r in self.reasons if r.startswith("fabrication:")]

    @property
    def omission(self) -> list[str]:
        return [r for r in self.reasons if r.startswith("omission:")]


class QualityFloor:
    """Check a delivered brief + its sources against the minimum bar."""

    def check(self, brief: str, sources: list[dict[str, Any]]) -> FloorResult:
        reasons: list[str] = []

        if not brief.strip():
            reasons.append("goal: brief is empty")

        for source in sources:
            title = str(source.get("title") or source.get("paper", {}).get("title") or "?")
            claims = source.get("claims", []) or []
            if not claims:
                reasons.append(f"omission: source '{title[:60]}' contributes no insight")
                continue
            for claim in claims:
                if not str(claim.get("evidence", "")).strip():
                    text = str(claim.get("claim", ""))[:60]
                    reasons.append(f"fabrication: claim without evidence in '{title[:40]}': {text}")

        return FloorResult(passed=not reasons, reasons=reasons)


def _demo() -> None:
    qf = QualityFloor()
    good = [{"title": "A", "claims": [{"claim": "x improves y", "evidence": "we found x improves y"}]}]
    assert qf.check("Insight brief.", good).passed

    empty_brief = qf.check("", good)
    assert not empty_brief.passed

    no_claims = qf.check("brief", [{"title": "B", "claims": []}])
    assert not no_claims.passed and no_claims.omission

    fabricated = qf.check("brief", [{"title": "C", "claims": [{"claim": "z", "evidence": ""}]}])
    assert not fabricated.passed and fabricated.fabrication
    print("quality_floor demo ok")


if __name__ == "__main__":
    _demo()
