"""Challenge dataclass and dispatcher for adversarial review."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class Challenge:
    """A single challenge raised against a claim or source."""

    claim_index: int | None = None
    source_id: str | None = None
    claim_text: str = ""
    severity: str = "low"  # low | medium | high
    kind: str = ""
    reason: str = ""
    requested_evidence: str = ""
    resolved: bool = False


@dataclass(frozen=True, slots=True)
class VerificationResult:
    """Outcome of verifying a claim against its source."""

    claim_index: int | None = None
    source_id: str | None = None
    claim_text: str = ""
    ok: bool = False
    reason: str = ""


def challenge_to_dict(challenge: Challenge) -> dict[str, Any]:
    return {
        "claim_index": challenge.claim_index,
        "source_id": challenge.source_id,
        "claim_text": challenge.claim_text,
        "severity": challenge.severity,
        "kind": challenge.kind,
        "reason": challenge.reason,
        "requested_evidence": challenge.requested_evidence,
        "resolved": challenge.resolved,
    }


def verification_to_dict(result: VerificationResult) -> dict[str, Any]:
    return {
        "claim_index": result.claim_index,
        "source_id": result.source_id,
        "claim_text": result.claim_text,
        "ok": result.ok,
        "reason": result.reason,
    }


class ChallengeDispatcher:
    """Group challenges and route them for response or escalation."""

    def __init__(self, frontier_model: Any | None = None) -> None:
        self.frontier_model = frontier_model

    def dispatch(self, challenges: list[Challenge]) -> dict[str, list[Challenge]]:
        """Partition challenges by severity for triage."""
        return {
            "high": [c for c in challenges if c.severity == "high"],
            "medium": [c for c in challenges if c.severity == "medium"],
            "low": [c for c in challenges if c.severity == "low"],
        }
