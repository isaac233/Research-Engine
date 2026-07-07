"""Reporter: turn an EvaluationReport into a Markdown brief for the main AI."""

from __future__ import annotations

from research_engine.adversarial.challenge import Challenge, VerificationResult
from research_engine.evaluation.harness import EvaluationReport
from research_engine.extraction.structured import ExtractedSource


class Reporter:
    """Generate a human-readable insight brief with evidence and caveats."""

    def to_markdown(
        self,
        report: EvaluationReport,
        sources: list[ExtractedSource] | None = None,
        challenges: list[Challenge] | None = None,
        verifications: list[VerificationResult] | None = None,
        query: str = "",
    ) -> str:
        """Return a Markdown brief suitable for return to the main AI."""
        sources = sources or []
        challenges = challenges or []
        verifications = verifications or []

        lines: list[str] = [
            f"# Research Brief: {query or 'Campaign'}",
            "",
            "## Summary",
            "",
            f"- Sources reviewed: **{report.total_sources}**",
            f"- Claims extracted: **{report.total_claims}**",
            f"- Citations found: **{report.citation_count}**",
            f"- Claims challenged: **{report.challenged_count}** ({report.high_severity_count} high severity)",
            f"- Verifications passed: **{report.verified_count}/{len(verifications)}**",
            f"- Coverage score: **{report.coverage_score:.2f}**",
            f"- Quality score: **{report.quality_score:.2f}**",
            "",
            "## Claims",
            "",
        ]

        claim_number = 1
        for source in sources:
            for claim in source.claims:
                lines.append(f"{claim_number}. **{claim.claim}**")
                lines.append(f"   - Evidence: {claim.evidence or 'none'}")
                lines.append(f"   - Confidence: {claim.confidence}")
                lines.append(f"   - Source: {source.title} ({source.full_text_url or 'no URL'})")
                lines.append("")
                claim_number += 1

        if challenges:
            lines.extend(["## Challenges", ""])
            for challenge in challenges:
                lines.append(
                    f"- **[{challenge.severity.upper()}]** {challenge.kind}: {challenge.reason}"
                )
                lines.append(f"  - Claim: {challenge.claim_text}")
                lines.append(f"  - Requested evidence: {challenge.requested_evidence}")
                lines.append("")

        if verifications:
            failed = [v for v in verifications if not v.ok]
            if failed:
                lines.extend(["## Failed Verifications", ""])
                for v in failed:
                    lines.append(f"- {v.claim_text}")
                    lines.append(f"  - Reason: {v.reason}")
                    lines.append("")

        lines.extend(
            [
                "## Caveats",
                "",
                "All scores are heuristic and provisional. High-severity challenges and failed verifications must be resolved before downstream use.",
                "",
            ]
        )

        return "\n".join(lines).strip()
