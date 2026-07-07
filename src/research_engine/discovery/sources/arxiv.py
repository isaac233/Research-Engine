"""arXiv source adapter."""

from __future__ import annotations

from typing import Any

import feedparser
import httpx

from research_engine.discovery.schema import Paper, SearchResult
from research_engine.discovery.sources.base import SourceAdapter
from research_engine.discovery.sources.http import safe_get


class ArxivAdapter(SourceAdapter):
    """Fetch papers from the arXiv OAI/API (Atom feed)."""

    name = "arxiv"
    default_limit = 10
    base_url = "https://export.arxiv.org/api/query"

    def __init__(self, timeout: float = 30.0) -> None:
        self.timeout = timeout

    def search(self, query: str, limit: int | None = None, offset: int = 0) -> SearchResult:
        limit = limit or self.default_limit
        start = offset
        params: dict[str, Any] = {
            "search_query": f"all:{query}",
            "start": start,
            "max_results": limit,
            "sortBy": "relevance",
            "sortOrder": "descending",
        }
        try:
            response = safe_get(
                self.base_url,
                params=params,
                timeout=self.timeout,
            )
            response.raise_for_status()
            feed = feedparser.parse(response.text)
        except httpx.HTTPStatusError as exc:
            return SearchResult(
                source=self.name,
                query=query,
                error=f"HTTP {exc.response.status_code}: {exc.response.text[:200]}",
            )
        except httpx.RequestError as exc:
            return SearchResult(
                source=self.name,
                query=query,
                error=f"Request error: {exc}",
            )
        except Exception as exc:  # noqa: BLE001
            return SearchResult(
                source=self.name,
                query=query,
                error=f"Parse error: {exc}",
            )

        total_raw = feed.feed.get("opensearch_totalresults", len(feed.entries))
        try:
            total = int(total_raw) if isinstance(total_raw, (str, int, float)) else len(feed.entries)
        except ValueError:
            total = len(feed.entries)
        papers = [self._normalize(entry) for entry in feed.entries]
        next_offset = offset + len(papers) if offset + len(papers) < total else None

        return SearchResult(
            source=self.name,
            query=query,
            papers=papers,
            total=total,
            next_offset=next_offset,
            meta={"offset": offset, "limit": limit},
        )

    def fetch_by_id(self, source_id: str) -> Paper | None:
        # source_id may be arxiv:1234.5678 or 1234.5678.
        arxiv_id = source_id.replace("arxiv:", "")
        params: dict[str, Any] = {
            "id_list": arxiv_id,
            "max_results": 1,
        }
        try:
            response = safe_get(
                self.base_url,
                params=params,
                timeout=self.timeout,
            )
            response.raise_for_status()
            feed = feedparser.parse(response.text)
            if feed.entries:
                return self._normalize(feed.entries[0])
            return None
        except Exception:  # noqa: BLE001
            return None

    def _normalize(self, entry: Any) -> Paper:
        authors = [author.name for author in entry.get("authors", []) if hasattr(author, "name")]

        arxiv_id = entry.get("id", "").split("/")[-1].split("v")[0]
        url = entry.get("link") or f"https://arxiv.org/abs/{arxiv_id}"

        year: int | None = None
        if "published_parsed" in entry and entry.published_parsed:
            year = entry.published_parsed.tm_year

        return Paper(
            title=entry.get("title", "").replace("\n", " ").strip(),
            authors=authors,
            year=year,
            doi=entry.get("arxiv_doi"),
            url=url,
            pdf_url=f"https://arxiv.org/pdf/{arxiv_id}.pdf" if arxiv_id else None,
            abstract=entry.get("summary", "").replace("\n", " ").strip(),
            source=self.name,
            source_id=arxiv_id,
            meta={"categories": entry.get("tags", [])},
        )

    def health(self) -> dict[str, Any]:
        return {"ok": True, "source": self.name}
