"""Crossref source adapter."""

from __future__ import annotations

import re
from typing import Any
from urllib.parse import quote

import httpx

from research_engine.discovery.schema import Paper, SearchResult
from research_engine.discovery.sources.base import SourceAdapter
from research_engine.discovery.sources.http import safe_get

_DOI_RE = re.compile(r"^10\.\d{4,}\/.+$", re.IGNORECASE)


class CrossrefAdapter(SourceAdapter):
    """Fetch works from Crossref with polite email and rate-limit handling."""

    name = "crossref"
    default_limit = 10
    base_url = "https://api.crossref.org"

    def __init__(
        self,
        timeout: float = 30.0,
        mailto: str | None = None,
    ) -> None:
        self.timeout = timeout
        self.mailto = mailto

    def search(self, query: str, limit: int | None = None, offset: int = 0) -> SearchResult:
        limit = limit or self.default_limit
        params: dict[str, Any] = {
            "query": query,
            "rows": limit,
            "offset": offset,
            "select": "DOI,title,author,abstract,created,published-print,published-online,link",
        }
        if self.mailto:
            params["mailto"] = self.mailto

        headers = {
            "User-Agent": "ResearchEngine/0.1 (mailto:research@example.com)",
        }

        try:
            response = safe_get(
                f"{self.base_url}/works",
                params=params,
                headers=headers,
                timeout=self.timeout,
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

        items = data.get("message", {}).get("items", [])
        total = data.get("message", {}).get("total-results", len(items))
        papers = [self._normalize(item) for item in items]
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
        doi = source_id.replace("doi:", "")
        if not _DOI_RE.match(doi):
            return None
        encoded = quote(doi, safe="/")
        url = f"{self.base_url}/works/{encoded}"
        headers = {"User-Agent": "ResearchEngine/0.1"}
        try:
            response = safe_get(
                url,
                headers=headers,
                timeout=self.timeout,
            )
            response.raise_for_status()
            return self._normalize(response.json().get("message", {}))
        except Exception:  # noqa: BLE001
            return None

    def _normalize(self, raw: dict[str, Any]) -> Paper:
        authors = []
        for author in raw.get("author", []):
            name = " ".join(
                filter(None, [author.get("given"), author.get("family")])
            )
            if name:
                authors.append(name)

        title_list = raw.get("title", [])
        title = title_list[0] if title_list else ""

        doi = raw.get("DOI")
        year = self._extract_year(raw)

        links = raw.get("link", [])
        url = links[0].get("URL") if links else None
        if not url and doi:
            url = f"https://doi.org/{doi}"

        return Paper(
            title=title,
            authors=authors,
            year=year,
            doi=doi,
            url=url,
            abstract=raw.get("abstract", ""),
            source=self.name,
            source_id=doi,
            meta={"created": raw.get("created")},
        )

    def _extract_year(self, raw: dict[str, Any]) -> int | None:
        for key in ("published-print", "published-online", "created"):
            part = raw.get(key, {}).get("date-parts", [[]])
            if part and part[0]:
                return int(part[0][0])
        return None

    def health(self) -> dict[str, Any]:
        return {"ok": True, "source": self.name, "mailto": bool(self.mailto)}
