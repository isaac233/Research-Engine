"""Tests for the challenge dispatcher."""

from __future__ import annotations

from research_engine.adversarial.challenge import Challenge, ChallengeDispatcher


def _challenge(severity: str, kind: str = "test") -> Challenge:
    return Challenge(
        claim_index=0,
        source_id="s1",
        severity=severity,
        kind=kind,
        reason="reason",
    )


def test_dispatch_partitions_by_severity() -> None:
    challenges = [
        _challenge("high"),
        _challenge("medium"),
        _challenge("low"),
        _challenge("high"),
    ]
    dispatcher = ChallengeDispatcher()
    triage = dispatcher.dispatch(challenges)

    assert len(triage["high"]) == 2
    assert len(triage["medium"]) == 1
    assert len(triage["low"]) == 1


def test_dispatch_returns_empty_buckets_for_no_challenges() -> None:
    dispatcher = ChallengeDispatcher()
    triage = dispatcher.dispatch([])

    assert triage == {"high": [], "medium": [], "low": []}
