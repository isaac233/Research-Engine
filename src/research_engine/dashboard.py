"""Campaign analytics dashboard and report generation."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from research_engine.state import CampaignStatus, CampaignStore


@dataclass(frozen=True)
class CampaignSummary:
    """Analytics summary for a single campaign."""

    campaign_id: str
    slug: str
    query: str
    status: str
    current_stage: str
    created_at: str
    updated_at: str
    duration_seconds: float | None = None
    stage_durations: dict[str, float] = field(default_factory=dict)


@dataclass(frozen=True)
class DashboardMetrics:
    """Aggregated analytics across all campaigns."""

    total: int = 0
    completed: int = 0
    failed: int = 0
    killed: int = 0
    running: int = 0
    paused: int = 0
    average_duration_seconds: float | None = None
    median_duration_seconds: float | None = None
    stage_counts: dict[str, int] = field(default_factory=dict)
    status_counts: dict[str, int] = field(default_factory=dict)
    top_queries: list[str] = field(default_factory=list)


class CampaignDashboard:
    """Produce analytics reports from a CampaignStore."""

    def __init__(self, store: CampaignStore) -> None:
        self.store = store

    def metrics(self) -> DashboardMetrics:
        """Return aggregated metrics across all stored campaigns."""
        campaigns = self.store.list_campaigns()
        total = len(campaigns)
        if total == 0:
            return DashboardMetrics()

        status_counts: dict[str, int] = {}
        stage_counts: dict[str, int] = {}
        durations: list[float] = []
        top_queries: list[str] = []
        completed = 0
        failed = 0
        killed = 0
        running = 0
        paused = 0

        for campaign in campaigns:
            status_counts[campaign.status.value] = status_counts.get(campaign.status.value, 0) + 1
            stage_counts[campaign.stage.value] = stage_counts.get(campaign.stage.value, 0) + 1
            if campaign.status == CampaignStatus.COMPLETED:
                completed += 1
            elif campaign.status == CampaignStatus.FAILED:
                failed += 1
            elif campaign.status == CampaignStatus.KILLED:
                killed += 1
            elif campaign.status == CampaignStatus.RUNNING:
                running += 1
            elif campaign.status == CampaignStatus.PAUSED:
                paused += 1

            duration = self._duration_seconds(campaign.id)
            if duration is not None:
                durations.append(duration)
            top_queries.append(campaign.request.query)

        average = sum(durations) / len(durations) if durations else None
        median = self._median(durations) if durations else None

        return DashboardMetrics(
            total=total,
            completed=completed,
            failed=failed,
            killed=killed,
            running=running,
            paused=paused,
            average_duration_seconds=average,
            median_duration_seconds=median,
            stage_counts=stage_counts,
            status_counts=status_counts,
            top_queries=top_queries[:5],
        )

    def campaign_summary(self, campaign_id: str) -> CampaignSummary | None:
        """Return a detailed analytics summary for a single campaign."""
        campaign = self.store.get_campaign(campaign_id)
        if campaign is None:
            return None

        events = self.store.get_events(campaign_id)
        stage_durations = self._stage_durations(events)
        duration = self._duration_seconds(campaign_id)

        return CampaignSummary(
            campaign_id=campaign.id,
            slug=campaign.slug,
            query=campaign.request.query,
            status=campaign.status.value,
            current_stage=campaign.stage.value,
            created_at=campaign.created_at.isoformat(),
            updated_at=campaign.updated_at.isoformat(),
            duration_seconds=duration,
            stage_durations=stage_durations,
        )

    def list_summaries(self) -> list[CampaignSummary]:
        """Return summaries for every campaign in the store."""
        campaigns = self.store.list_campaigns()
        summaries: list[CampaignSummary] = []
        for campaign in campaigns:
            summary = self.campaign_summary(campaign.id)
            if summary is not None:
                summaries.append(summary)
        return summaries

    def generate_report(
        self,
        output_path: Path | str | None = None,
        *,
        project_root: Path | str | None = None,
    ) -> str:
        """Generate a markdown analytics report and optionally write it to disk.

        If ``project_root`` is supplied, ``output_path`` must resolve inside it
        to prevent path-traversal writes.
        """
        out: Path | None = None
        if output_path is not None:
            out = Path(output_path).resolve()
            if project_root is None:
                raise ValueError("project_root is required when writing a report to disk")
            root = Path(project_root).resolve()
            if not out.is_relative_to(root):
                raise ValueError(f"report output must be inside project root {root}")
        metrics = self.metrics()
        summaries = self.list_summaries()

        lines: list[str] = [
            "# Research Engine Campaign Report",
            "",
            f"_Generated at {datetime.now(UTC).isoformat()}_",
            "",
            "## Aggregate Metrics",
            "",
            f"- **Total campaigns**: {metrics.total}",
            f"- **Completed**: {metrics.completed}",
            f"- **Failed**: {metrics.failed}",
            f"- **Killed**: {metrics.killed}",
            f"- **Running**: {metrics.running}",
            f"- **Paused**: {metrics.paused}",
        ]
        if metrics.average_duration_seconds is not None:
            lines.append(f"- **Average duration**: {metrics.average_duration_seconds:.1f}s")
        if metrics.median_duration_seconds is not None:
            lines.append(f"- **Median duration**: {metrics.median_duration_seconds:.1f}s")

        if metrics.status_counts:
            lines.extend(["", "### Status Breakdown", ""])
            for status, count in sorted(metrics.status_counts.items()):
                lines.append(f"- {status}: {count}")

        if metrics.stage_counts:
            lines.extend(["", "### Current Stage Breakdown", ""])
            for stage, count in sorted(metrics.stage_counts.items()):
                lines.append(f"- {stage}: {count}")

        if metrics.top_queries:
            lines.extend(["", "### Recent Queries", ""])
            for query in metrics.top_queries:
                lines.append(f"- {query}")

        if summaries:
            lines.extend(["", "## Per-Campaign Details", ""])
            for summary in summaries:
                lines.extend(self._render_summary(summary))

        report = "\n".join(lines)
        if out is not None:
            out.write_text(report, encoding="utf-8")
        return report

    def _render_summary(self, summary: CampaignSummary) -> list[str]:
        lines = [
            f"### {summary.slug} ({summary.campaign_id})",
            "",
            f"- **Query**: {summary.query}",
            f"- **Status**: {summary.status}",
            f"- **Stage**: {summary.current_stage}",
            f"- **Created**: {summary.created_at}",
            f"- **Updated**: {summary.updated_at}",
        ]
        if summary.duration_seconds is not None:
            lines.append(f"- **Duration**: {summary.duration_seconds:.1f}s")
        if summary.stage_durations:
            lines.append("- **Stage durations**:")
            for stage, seconds in sorted(summary.stage_durations.items()):
                lines.append(f"  - {stage}: {seconds:.1f}s")
        lines.append("")
        return lines

    def _duration_seconds(self, campaign_id: str) -> float | None:
        campaign = self.store.get_campaign(campaign_id)
        if campaign is None:
            return None
        try:
            created = campaign.created_at
            updated = campaign.updated_at
            return max(0.0, (updated - created).total_seconds())
        except (TypeError, AttributeError):
            return None

    def _stage_durations(self, events: list[dict[str, Any]]) -> dict[str, float]:
        """Compute cumulative seconds spent in each stage from enter/exit events."""
        durations: dict[str, float] = {}
        active: dict[str, datetime] = {}
        for event in events:
            payload = event.get("payload", {})
            stage = payload.get("stage")
            if not stage:
                continue
            ts_str = event.get("timestamp")
            if not ts_str:
                continue
            try:
                ts = datetime.fromisoformat(ts_str)
            except ValueError:
                continue
            if event.get("type") == "stage_enter":
                if stage in active:
                    elapsed = (ts - active[stage]).total_seconds()
                    durations[stage] = durations.get(stage, 0.0) + max(0.0, elapsed)
                active[stage] = ts
            elif event.get("type") == "stage_exit" and stage in active:
                elapsed = (ts - active[stage]).total_seconds()
                durations[stage] = durations.get(stage, 0.0) + max(0.0, elapsed)
                del active[stage]
        return durations

    @staticmethod
    def _median(values: list[float]) -> float:
        sorted_values = sorted(values)
        n = len(sorted_values)
        mid = n // 2
        if n % 2 == 1:
            return sorted_values[mid]
        return (sorted_values[mid - 1] + sorted_values[mid]) / 2
