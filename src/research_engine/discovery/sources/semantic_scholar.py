"""Semantic Scholar source adapter."""

from __future__ import annotations

from typing import Any

import httpx

from research_engine.discovery.schema import Paper, SearchResult
from research_engine.discovery.sources.base import SourceAdapter


class SemanticScholarAdapter(SourceAdapter):
    """Fetch papers from the Semantic Scholar public API."""

    name = "semantic_scholar"
    default_limit = 10
    base_url = "https://api.semanticscholar.org/graph/v1"

    def __init__(self, timeout: float = 30.0, api_key: str | None = None) -> None:
        self.timeout = timeout
        self.api_key = api_key

    def search(self, query: str, limit: int | None = None, offset: int = 0) -> SearchResult:
        limit = limit or self.default_limit
        fields = "title,authors,year,abstract,externalIds,openAccessPdf,citationCount"
        params: dict[str, Any] = {
            "query": query,
            "limit": limit,
            "offset": offset,
            "fields": fields,
        }
        headers: dict[str, str] = {}
        if self.api_key:
            headers["x-api-key"] = self.api_key

        try:
            response = httpx.get(
                f"{self.base_url}/paper/search",
                params=params,
                headers=headers,
                timeout=self.timeout,
                follow_redirects=True,
            )
            response.raise_for_status()
            data = response.json()
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

        raw_papers = data.get("data", [])
        total = data.get("total", len(raw_papers))
        papers = [self._normalize(paper) for paper in raw_papers]
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
        # source_id may be a Semantic Scholar paper ID or DOI.
        paper_id = source_id.replace("doi:", "")
        url = f"{self.base_url}/paper/{paper_id}"
        params = {"fields": "title,authors,year,abstract,externalIds,openAccessPdf,citationCount"}
        headers: dict[str, str] = {}
        if self.api_key:
            headers["x-api-key"] = self.api_key
        try:
            response = httpx.get(
                url,
                params=params,
                headers=headers,
                timeout=self.timeout,
                follow_redirects=True,
            )
            response.raise_for_status()
            return self._normalize(response.json())
        except Exception:  # noqa: BLE001
            return None

    def _normalize(self, raw: dict[str, Any]) -> Paper:
        authors = []
        for author in raw.get("authors", []):
            name = author.get("name") or " ".join(
                filter(None, [author.get("firstName"), author.get("lastName")])
            )
            if name:
                authors.append(name)

        external_ids = raw.get("externalIds") or {}
        doi = external_ids.get("DOI")
        paper_id = raw.get("paperId")
        pdf_info = raw.get("openAccessPdf") or {}
        pdf_url = pdf_info.get("url") if isinstance(pdf_info, dict) else None

        return Paper(
            title=raw.get("title", ""),
            authors=authors,
            year=raw.get("year"),
            doi=doi,
            url=f"https://www.semanticscholar.org/paper/{paper_id}" if paper_id else None,
            pdf_url=pdf_url,
            abstract=raw.get("abstract", ""),
            source=self.name,
            source_id=paper_id,
            meta={
                "citation_count": raw.get("citationCount"),
                "external_ids": external_ids,
            },
        )

    def health(self) -> dict[str, Any]:
        return {"ok": True, "source": self.name, "has_api_key": bool(self.api_key)}
