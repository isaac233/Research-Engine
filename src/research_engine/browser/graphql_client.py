"""GraphQL and JSON API client helpers."""

from __future__ import annotations

import json
from typing import Any

from research_engine.browser.ai_browser import (
    AIBrowser,
    BrowserAction,
    BrowserActionType,
    BrowserResult,
)
from research_engine.browser.raw_http import RawHTTPBrowser


class GraphQLClient(AIBrowser):
    """GraphQL-aware browser helper."""

    name = "graphql"

    def __init__(
        self,
        http_browser: RawHTTPBrowser | None = None,
    ) -> None:
        self.http = http_browser or RawHTTPBrowser()

    def act(self, action: BrowserAction) -> BrowserResult:
        if action.action != BrowserActionType.GRAPHQL:
            return BrowserResult(
                ok=False,
                action=action.action,
                url=action.url,
                status=None,
                content="",
                error="GraphQLClient only supports graphql actions",
            )
        url = action.url
        if not url:
            return BrowserResult(
                ok=False,
                action=BrowserActionType.GRAPHQL,
                url=None,
                status=None,
                content="",
                error="graphql requires url",
            )
        query = action.body or action.query or ""
        headers = {"Content-Type": "application/json"}
        headers.update(action.headers)
        fetch_action = BrowserAction(
            action=BrowserActionType.API,
            url=url,
            method="POST",
            body=json.dumps({"query": query}),
            headers=headers,
        )
        result = self.http.act(fetch_action)
        if not result.ok:
            return result
        try:
            data = json.loads(result.content)
            return BrowserResult(
                ok="errors" not in data,
                action=BrowserActionType.GRAPHQL,
                url=result.url,
                status=result.status,
                content=result.content,
                headers=result.headers,
                meta={"parsed": data},
                error=("GraphQL errors: " + json.dumps(data.get("errors"))) if "errors" in data else None,
            )
        except json.JSONDecodeError as exc:
            return BrowserResult(
                ok=False,
                action=BrowserActionType.GRAPHQL,
                url=result.url,
                status=result.status,
                content=result.content,
                headers=result.headers,
                error=f"Invalid JSON response: {exc}",
            )

    def health(self) -> dict[str, Any]:
        return {"ok": True, "client": "graphql", "http": self.http.health()}
