"""Instrumentation helpers for the campaign orchestrator.

Keeps the orchestrator itself focused on stage dispatch while isolating
audit-history, source-memory, input-validation, and keyword-tagging helpers.
"""

from __future__ import annotations

from typing import Any

from research_engine.browser.policy import URLPolicy
from research_engine.events import EventBus
from research_engine.state import Campaign
from research_engine.storage._redaction import redact_secrets, redact_url
from research_engine.storage.agent_history import AgentHistory, AgentHistoryRecord
from research_engine.storage.source_memory import SourceMemory


class OrchestratorInstrumentation:
    """Best-effort instrumentation mix-in for :class:`Orchestrator`."""

    # Canonical URLs for known discovery sources used by source memory.
    SOURCE_CANONICAL_URLS: dict[str, str] = {
        "arxiv": "https://arxiv.org",
        "semantic_scholar": "https://api.semanticscholar.org",
        "crossref": "https://api.crossref.org",
        "openalex": "https://api.openalex.org",
        "serp": "https://serpapi.com",
    }

    event_bus: EventBus
    agent_history: AgentHistory | None
    source_memory: SourceMemory | None

    def record_agent_action(self, record: AgentHistoryRecord) -> AgentHistoryRecord:
        """Persist an agent action to the audit history when configured.

        Instrumentation is best-effort: storage failures are captured by the
        event bus but must not crash a campaign.
        """
        if self.agent_history is None:
            return record
        try:
            return self.agent_history.record(record)
        except Exception as exc:  # noqa: BLE001 - instrumentation must not break campaign logic
            self.event_bus.emit(
                record.campaign_id or "unknown",
                "agent_history_failed",
                {"error": redact_secrets(str(exc)), "action_type": record.action_type},
            )
            return record

    def remember_source(
        self,
        canonical_url: str,
        source_type: str,
        information_types: list[str] | None = None,
        topic_tags: list[str] | None = None,
        access_method: str = "",
        requires_auth: bool = False,
        rate_limit_notes: str = "",
        reliability_score: float | None = None,
        quality_notes: str = "",
        search_hints: dict[str, Any] | None = None,
        example_keys: list[str] | None = None,
        example_urls: list[str] | None = None,
        campaign_id: str | None = None,
        meta: dict[str, Any] | None = None,
    ) -> None:
        """Persist a source observation to source memory when configured.

        Best-effort: storage failures are captured by the event bus but must not
        crash a campaign.
        """
        if self.source_memory is None:
            return
        try:
            self.source_memory.remember(
                canonical_url=canonical_url,
                source_type=source_type,
                information_types=information_types or [],
                topic_tags=topic_tags or [],
                access_method=access_method,
                requires_auth=requires_auth,
                rate_limit_notes=rate_limit_notes,
                reliability_score=reliability_score,
                quality_notes=quality_notes,
                search_hints=search_hints or {},
                example_keys=example_keys or [],
                example_urls=example_urls or [],
                discovery_campaign_id=campaign_id,
                meta=meta or {},
            )
        except Exception as exc:  # noqa: BLE001 - instrumentation must not break campaign logic
            self.event_bus.emit(
                campaign_id or "unknown",
                "source_memory_failed",
                {"error": redact_secrets(str(exc)), "canonical_url": redact_url(canonical_url)},
            )

    def _plan_keywords(self, campaign: Campaign) -> list[str]:
        """Return clean keyword tags from the research plan if available."""
        plan = campaign.meta.get("plan", {})
        keywords = plan.get("keywords", [])
        if keywords:
            return [str(k).lower().strip() for k in keywords if k]
        # Fallback to a normalized tokenization of the query.
        return [
            token
            for token in campaign.request.query.lower().split()
            if len(token) > 2 and token.isalpha()
        ]

    def _validate_request_input(self, campaign: Campaign) -> None:
        """Enforce sane length/content limits on untrusted research queries."""
        query = campaign.request.query
        if not isinstance(query, str) or len(query) > 1000:
            raise ValueError("campaign query must be a string of at most 1000 characters")
        context = campaign.request.context
        if not isinstance(context, str) or len(context) > 5000:
            raise ValueError("campaign context must be a string of at most 5000 characters")

    def _validate_url(self, url: str) -> None:
        """Reject URLs that are not safe to fetch before passing them downstream."""
        if not url:
            return
        allowed, reason = URLPolicy().allow(url)
        if not allowed:
            raise ValueError(reason)
