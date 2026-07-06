"""Unit tests for the GraphQL browser helper."""

from __future__ import annotations

from research_engine.browser.ai_browser import BrowserAction, BrowserActionType, BrowserResult
from research_engine.browser.graphql_client import GraphQLClient
from research_engine.browser.raw_http import RawHTTPBrowser


class FakeHTTPBrowser(RawHTTPBrowser):
    def __init__(self, results: list[BrowserResult]) -> None:
        self.results = results

    def act(self, action: BrowserAction) -> BrowserResult:
        return self.results.pop(0)


def test_unsupported_action_returns_error() -> None:
    client = GraphQLClient()
    result = client.act(BrowserAction(action=BrowserActionType.FETCH))
    assert result.ok is False
    assert "only supports graphql" in (result.error or "").lower()


def test_missing_url_returns_error() -> None:
    client = GraphQLClient()
    result = client.act(BrowserAction(action=BrowserActionType.GRAPHQL))
    assert result.ok is False
    assert "url" in (result.error or "").lower()


def test_successful_graphql_parsing() -> None:
    http = FakeHTTPBrowser([
        BrowserResult(
            ok=True,
            action=BrowserActionType.API,
            url="https://api.example.com/graphql",
            status=200,
            content='{"data": {"items": [1, 2]}}',
        ),
    ])
    client = GraphQLClient(http)
    result = client.act(
        BrowserAction(
            action=BrowserActionType.GRAPHQL,
            url="https://api.example.com/graphql",
            query="{ items }",
        )
    )
    assert result.ok is True
    assert result.status == 200
    assert result.meta.get("parsed") == {"data": {"items": [1, 2]}}


def test_graphql_errors_returned() -> None:
    http = FakeHTTPBrowser([
        BrowserResult(
            ok=True,
            action=BrowserActionType.API,
            url="https://api.example.com/graphql",
            status=200,
            content='{"errors": [{"message": "boom"}]}',
        ),
    ])
    client = GraphQLClient(http)
    result = client.act(
        BrowserAction(
            action=BrowserActionType.GRAPHQL,
            url="https://api.example.com/graphql",
            query="{ bad }",
        )
    )
    assert result.ok is False
    assert "GraphQL errors" in (result.error or "")


def test_invalid_json_returns_error() -> None:
    http = FakeHTTPBrowser([
        BrowserResult(
            ok=True,
            action=BrowserActionType.API,
            url="https://api.example.com/graphql",
            status=200,
            content="not-json",
        ),
    ])
    client = GraphQLClient(http)
    result = client.act(
        BrowserAction(
            action=BrowserActionType.GRAPHQL,
            url="https://api.example.com/graphql",
        )
    )
    assert result.ok is False
    assert "Invalid JSON" in (result.error or "")
