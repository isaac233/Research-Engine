"""Improvement proposal pipeline: turn reports into itemized R### deltas."""

from __future__ import annotations

from typing import Any

from research_engine.evaluation.harness import EvaluationReport


class ImprovementProposer:
    """Propose one itemized improvement per report finding. Never auto-applies."""

    def propose(self, report: EvaluationReport) -> list[dict[str, Any]]:
        """Return a list of candidate improvements for frontier/human review."""
        proposals: list[dict[str, Any]] = []
        if report.failed_verification_count > 0:
            proposals.append(
                {
                    "area": "verifier",
                    "kind": "R028-delta-candidate",
                    "issue": f"{report.failed_verification_count} claims failed verification",
                    "suggested_action": "Strengthen evidence extraction or source resolution before delivery.",
                    "auto_apply": False,
                }
            )
        if report.high_severity_count > 0:
            proposals.append(
                {
                    "area": "devil",
                    "kind": "R029-delta-candidate",
                    "issue": f"{report.high_severity_count} high-severity challenges raised",
                    "suggested_action": "Add frontier-model deep audit for high-severity claims.",
                    "auto_apply": False,
                }
            )
        if report.total_claims == 0:
            proposals.append(
                {
                    "area": "extraction",
                    "kind": "R030-delta-candidate",
                    "issue": "No claims were extracted",
                    "suggested_action": "Improve PDF conversion or fallback to abstract extraction.",
                    "auto_apply": False,
                }
            )
        return proposals
