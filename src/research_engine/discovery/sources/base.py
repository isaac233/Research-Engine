"""Base class for discovery source adapters."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from research_engine.discovery.schema import Paper, SearchResult


class SourceAdapter(ABC):
    """Every discovery source implements this interface."""

    name: str
    default_limit: int = 10

    @abstractmethod
    def search(self, query: str, limit: int | None = None, offset: int = 0) -> SearchResult:
        """Run a search query and return normalized results."""

    @abstractmethod
    def fetch_by_id(self, source_id: str) -> Paper | None:
        """Fetch a single paper by its source-specific identifier."""

    def health(self) -> dict[str, Any]:
        """Return lightweight health/status information."""
        return {"ok": True, "source": self.name}
