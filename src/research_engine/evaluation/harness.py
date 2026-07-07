"""Evaluation harness: score a campaign's extracted and challenged output."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from research_engine.adversarial.challenge import Challenge, VerificationResult
from research_engine.extraction.structured import ExtractedSource


@dataclass(frozen=True, slots=True)
class EvaluationReport:
    """Metrics and narrative summary of a campaign's output quality."""

    total_claims: int = 0
    total_sources: int = 0
    challenged_count: int = 0
    high_severity_count: int = 0
    verified_count: int = 0
    failed_verification_count: int = 0
    citation_count: int = 0
    coverage_score: float = 0.0
    quality_score: float = 0.0
    markdown: str = ""
    meta: dict[str, Any] = field(default_factory=dict)


class EvaluationHarness:
    """Compute verifiable quality metrics from extraction + adversarial outputs."""

    def evaluate(
        self,
        sources: list[ExtractedSource],
        challenges: list[Challenge],
        verifications: list[VerificationResult],
        query: str = "",
    ) -> EvaluationReport:
        total_claims = sum(len(s.claims) for s in sources)
        total_sources = len(sources)
        citation_count = sum(len(s.citations) for s in sources)

        challenge_set = {self._challenge_key(c) for c in challenges}
        challenged_count = len(challenge_set)
        high_severity_count = sum(1 for c in challenges if c.severity == "high")

        verified_count = sum(1 for v in verifications if v.ok)
        failed_verification_count = len(verifications) - verified_count

        coverage_score = self._coverage_score(total_sources, total_claims, citation_count)
        quality_score = self._quality_score(
            total_claims,
            challenged_count,
            high_severity_count,
            failed_verification_count,
        )

        report = EvaluationReport(
            total_claims=total_claims,
            total_sources=total_sources,
            challenged_count=challenged_count,
            high_severity_count=high_severity_count,
            verified_count=verified_count,
            failed_verification_count=failed_verification_count,
            citation_count=citation_count,
            coverage_score=round(coverage_score, 4),
            quality_score=round(quality_score, 4),
            meta={"query": query, "conflict_count": sum(len(s.conflicts) for s in sources)},
        )
        return report

    def _challenge_key(self, challenge: Challenge) -> tuple[str | None, int | None, str]:
        return (challenge.source_id, challenge.claim_index, challenge.kind)

    def _coverage_score(self, sources: int, claims: int, citations: int) -> float:
        """Simple coverage heuristic: at least one source + claims + citations."""
        if sources == 0:
            return 0.0
        score = 0.5
        if claims > 0:
            score += 0.25
        if citations > 0:
            score += 0.25
        return min(1.0, score)

    def _quality_score(
        self,
        claims: int,
        challenged: int,
        high_severity: int,
        failed_verification: int,
    ) -> float:
        if claims == 0:
            return 0.0
        base = 1.0
        base -= 0.2 * min(challenged / max(claims, 1), 1.0)
        base -= 0.4 * min(high_severity / max(claims, 1), 1.0)
        base -= 0.4 * min(failed_verification / max(claims, 1), 1.0)
        return max(0.0, base)
