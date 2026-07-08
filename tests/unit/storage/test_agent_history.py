"""Unit tests for the agent-history audit database."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from research_engine.storage.agent_history import (
    AgentActionOutcome,
    AgentHistory,
    AgentHistoryRecord,
)


@pytest.fixture
def history(tmp_path: Path) -> AgentHistory:
    return AgentHistory(tmp_path / "agent_history.db")


def test_record_and_get(history: AgentHistory) -> None:
    record = history.record(
        AgentHistoryRecord(
            campaign_id="c1",
            agent_name="discovery",
            action_type="api_call",
            target_url="https://api.example.com/papers",
            api_endpoint="/papers",
            http_method="GET",
            request_headers={"Accept": "application/json"},
            request_summary="Search for transformer papers",
            response_status=200,
            response_size_bytes=1234,
            response_summary="12 papers returned",
            data_gathered_summary="titles and abstracts",
            outcome=AgentActionOutcome.SUCCESS,
            reason="OK",
            evidence_links=["https://api.example.com/papers/1"],
            related_paper_keys=["p1"],
            audit_level="normal",
            session_id="session_1",
            trace_id="trace_1",
            meta={"source": "example"},
        )
    )
    assert record.history_id is not None
    loaded = history.get(record.history_id)
    assert loaded is not None
    assert loaded.agent_name == "discovery"
    assert loaded.action_type == "api_call"
    assert loaded.target_url == "https://api.example.com/papers"
    assert loaded.response_status == 200
    assert loaded.outcome == AgentActionOutcome.SUCCESS
    assert loaded.evidence_links == ["https://api.example.com/papers/1"]
    assert loaded.session_id == "session_1"
    assert loaded.meta["source"] == "example"


def test_redacts_sensitive_headers(history: AgentHistory) -> None:
    record = history.record(
        AgentHistoryRecord(
            agent_name="discovery",
            action_type="api_call",
            request_headers={
                "Authorization": "Bearer secret-token",
                "X-Api-Key": "super-secret",
                "Accept": "application/json",
            },
            outcome=AgentActionOutcome.SUCCESS,
        )
    )
    loaded = history.get(record.history_id)
    assert loaded.request_headers["Authorization"] == "[REDACTED]"
    assert loaded.request_headers["X-Api-Key"] == "[REDACTED]"
    assert loaded.request_headers["Accept"] == "application/json"


def test_redacts_url_credentials_and_secrets_in_text(history: AgentHistory) -> None:
    record = history.record(
        AgentHistoryRecord(
            agent_name="browser",
            action_type="fetch",
            target_url="https://user:pass@api.example.com/papers?api_key=abc123456789&token=secret",
            request_summary="Fetched with api_key=abc123456789 and Bearer xyz-token-secret",
            response_summary="Got token=super-secret-value",
            reason="Authorization: Bearer abcdef0123456789 failed",
            evidence_links=["https://x.com?key=secret"],
            meta={"note": "password=SuperSecret123"},
            outcome=AgentActionOutcome.FAILURE,
        )
    )
    loaded = history.get(record.history_id)
    assert loaded is not None
    assert "user:pass@" not in loaded.target_url
    assert "api_key=[REDACTED]" in loaded.target_url
    assert "token=[REDACTED]" in loaded.target_url
    assert "api_key=[REDACTED]" in loaded.request_summary
    assert "Bearer [REDACTED]" in loaded.request_summary
    assert "token=[REDACTED]" in loaded.response_summary
    assert "Authorization: Bearer [REDACTED]" in loaded.reason
    assert loaded.evidence_links[0] == "https://x.com?key=[REDACTED]"
    assert loaded.meta["note"] == "password=[REDACTED]"


def test_fts_search(history: AgentHistory) -> None:
    history.record(
        AgentHistoryRecord(
            agent_name="browser",
            action_type="fetch",
            target_url="https://arxiv.org/abs/1234",
            request_summary="Fetch arxiv abstract",
            outcome=AgentActionOutcome.SUCCESS,
        )
    )
    history.record(
        AgentHistoryRecord(
            agent_name="discovery",
            action_type="api_call",
            api_endpoint="/search",
            request_summary="Query semantic scholar",
            outcome=AgentActionOutcome.SUCCESS,
        )
    )
    results = history.search("arxiv")
    assert len(results) == 1
    assert results[0].agent_name == "browser"


def test_structured_filters(history: AgentHistory) -> None:
    history.record(
        AgentHistoryRecord(
            campaign_id="c1",
            agent_name="a1",
            action_type="fetch",
            outcome=AgentActionOutcome.SUCCESS,
        )
    )
    history.record(
        AgentHistoryRecord(
            campaign_id="c1",
            agent_name="a1",
            action_type="api_call",
            outcome=AgentActionOutcome.FAILURE,
        )
    )
    history.record(
        AgentHistoryRecord(
            campaign_id="c2",
            agent_name="a2",
            action_type="fetch",
            outcome=AgentActionOutcome.SUCCESS,
        )
    )
    assert len(history.search(campaign_id="c1")) == 2
    assert len(history.search(campaign_id="c1", action_type="fetch")) == 1
    assert len(history.search(outcome=AgentActionOutcome.FAILURE)) == 1
    assert len(history.search(agent_name="a2")) == 1


def test_date_range_filters(history: AgentHistory) -> None:
    base = datetime(2026, 1, 1, 12, 0, 0, tzinfo=UTC)
    history.record(
        AgentHistoryRecord(
            timestamp=base - timedelta(days=2),
            agent_name="a1",
            action_type="fetch",
            outcome=AgentActionOutcome.SUCCESS,
        )
    )
    history.record(
        AgentHistoryRecord(
            timestamp=base,
            agent_name="a1",
            action_type="fetch",
            outcome=AgentActionOutcome.SUCCESS,
        )
    )
    history.record(
        AgentHistoryRecord(
            timestamp=base + timedelta(days=2),
            agent_name="a1",
            action_type="fetch",
            outcome=AgentActionOutcome.SUCCESS,
        )
    )

    assert len(history.search(start=base - timedelta(days=1), end=base + timedelta(days=1))) == 1
    assert len(history.search(end=base)) == 2
    assert len(history.search(start=base)) == 2


def test_recent(history: AgentHistory) -> None:
    history.record(
        AgentHistoryRecord(
            agent_name="a1",
            action_type="fetch",
            outcome=AgentActionOutcome.SUCCESS,
        )
    )
    history.record(
        AgentHistoryRecord(
            agent_name="a2",
            action_type="fetch",
            outcome=AgentActionOutcome.SUCCESS,
        )
    )
    recent = history.recent(limit=1)
    assert len(recent) == 1
    assert recent[0].agent_name == "a2"


def test_summarize_campaign(history: AgentHistory) -> None:
    history.record(
        AgentHistoryRecord(
            campaign_id="c1",
            agent_name="discovery",
            action_type="api_call",
            source_name="s1",
            outcome=AgentActionOutcome.SUCCESS,
        )
    )
    history.record(
        AgentHistoryRecord(
            campaign_id="c1",
            agent_name="browser",
            action_type="fetch",
            source_name="s2",
            outcome=AgentActionOutcome.FAILURE,
        )
    )
    summary = history.summarize_campaign("c1")
    assert summary["total_actions"] == 2
    assert summary["outcomes"][AgentActionOutcome.SUCCESS] == 1
    assert summary["outcomes"][AgentActionOutcome.FAILURE] == 1
    assert summary["action_types"]["api_call"] == 1
    assert summary["sources_touched"] == ["s1", "s2"]


def test_export_range(history: AgentHistory) -> None:
    history.record(
        AgentHistoryRecord(
            campaign_id="c1",
            agent_name="a1",
            action_type="fetch",
            outcome=AgentActionOutcome.SUCCESS,
        )
    )
    exported = history.export_range(campaign_id="c1")
    assert len(exported) == 1
    assert exported[0]["campaign_id"] == "c1"


def test_redacts_nested_meta_values(history: AgentHistory) -> None:
    record = history.record(
        AgentHistoryRecord(
            agent_name="a1",
            action_type="api_call",
            outcome=AgentActionOutcome.SUCCESS,
            meta={
                "plain": "ok",
                "nested": {"password": "password=MySuperSecret123"},
                "list_of_dicts": [{"api_key": "api_key=abc123456789"}, {"safe": "value"}],
                "mixed_list": ["token=SecretValue9", {"secret": "secret=Hidden1234"}],
            },
        )
    )
    loaded = history.get(record.history_id)
    assert loaded.meta["plain"] == "ok"
    # Non-sensitive outer keys preserve structure; sensitive inner keys are redacted.
    assert loaded.meta["nested"]["password"] == "[REDACTED]"
    assert loaded.meta["list_of_dicts"][0]["api_key"] == "[REDACTED]"
    assert loaded.meta["list_of_dicts"][1]["safe"] == "value"
    assert loaded.meta["mixed_list"][0] == "token=[REDACTED]"
    assert loaded.meta["mixed_list"][1]["secret"] == "[REDACTED]"


def test_empty_or_special_fts_query_returns_all(history: AgentHistory) -> None:
    history.record(
        AgentHistoryRecord(
            agent_name="a1",
            action_type="fetch",
            request_summary="arxiv preprint",
            outcome=AgentActionOutcome.SUCCESS,
        )
    )
    assert len(history.search("...")) == 1
    assert len(history.search("")) == 1
    assert len(history.search("!!!")) == 1


def test_stats(history: AgentHistory) -> None:
    history.record(
        AgentHistoryRecord(
            agent_name="a1",
            action_type="fetch",
            outcome=AgentActionOutcome.SUCCESS,
        )
    )
    history.record(
        AgentHistoryRecord(
            agent_name="a2",
            action_type="api_call",
            outcome=AgentActionOutcome.ERROR,
            audit_level="sensitive",
        )
    )
    stats = history.stats()
    assert stats["total_actions"] == 2
    assert stats["by_agent"]["a1"] == 1
    assert stats["by_outcome"][AgentActionOutcome.ERROR] == 1
    assert stats["sensitive_actions"] == 1
