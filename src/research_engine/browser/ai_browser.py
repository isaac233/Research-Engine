"""AIBrowser abstraction for AI-only browser automation."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any


class BrowserActionType(StrEnum):
    """Supported browser actions."""

    FETCH = "fetch"
    CLICK = "click"
    FILL = "fill"
    EVALUATE = "evaluate"
    SNAPSHOT = "snapshot"
    GRAPHQL = "graphql"
    API = "api"
    UNBLOCK = "unblock"


@dataclass(frozen=True, slots=True)
class BrowserAction:
    """A single browser action request."""

    action: BrowserActionType
    url: str | None = None
    selector: str | None = None
    value: str | None = None
    script: str | None = None
    query: str | None = None
    headers: dict[str, str] = field(default_factory=dict)
    method: str = "GET"
    body: str | None = None
    meta: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class BrowserResult:
    """Result of a browser action."""

    ok: bool
    action: BrowserActionType
    url: str | None
    status: int | None
    content: str
    headers: dict[str, str] = field(default_factory=dict)
    meta: dict[str, Any] = field(default_factory=dict)
    error: str | None = None


class AIBrowser(ABC):
    """Model-agnostic browser interface for fetch, DOM, HTTP, GraphQL, and unblocking."""

    name: str

    @abstractmethod
    def act(self, action: BrowserAction) -> BrowserResult:
        """Execute one browser action and return a structured result."""

    @abstractmethod
    def health(self) -> dict[str, Any]:
        """Return lightweight health/status information."""

    def fetch(self, url: str, headers: dict[str, str] | None = None) -> BrowserResult:
        """Convenience fetch helper."""
        return self.act(BrowserAction(action=BrowserActionType.FETCH, url=url, headers=headers or {}))

    def fetch_bytes(self, url: str, headers: dict[str, str] | None = None) -> bytes:
        """Fetch a URL and return raw response bytes.

        Default implementation delegates to :meth:`fetch`. Subclasses that
        support binary content should override to avoid text decoding.
        """
        result = self.fetch(url, headers)
        if not result.ok:
            raise RuntimeError(result.error or f"fetch failed for {url}")
        content = result.content
        if isinstance(content, str):
            return content.encode("utf-8")
        return content

    def unblock(self, query: str) -> BrowserResult:
        """Convenience unblocking helper."""
        return self.act(BrowserAction(action=BrowserActionType.UNBLOCK, query=query))

