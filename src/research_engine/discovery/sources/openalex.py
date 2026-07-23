"""OpenAlex source adapter."""

from __future__ import annotations

from typing import Any
from urllib.parse import urlparse

import httpx

from research_engine.discovery.schema import Paper, SearchResult
from research_engine.discovery.sources.base import SourceAdapter
from research_engine.discovery.sources.http import safe_get


class OpenAlexAdapter(SourceAdapter):
    """Fetch works from OpenAlex with polite mailto."""

    name = "openalex"
    default_limit = 10
    base_url = "https://api.openalex.org/works"

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
            "search": query,
            "per-page": limit,
            "page": 1 + offset // limit if limit else 1,
        }
        if self.mailto:
            params["mailto"] = self.mailto

        headers = {
            "User-Agent": "mailto:research@example.com",
            "Accept": "application/json",
        }

        try:
            response = safe_get(
                self.base_url,
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

        results = data.get("results", [])
        total = data.get("meta", {}).get("count", len(results))
        papers = [self._normalize(work) for work in results]
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
        """Fetch a single OpenAlex work by URL or work ID.

        Accepts:
        - an OpenAlex URL: ``https://openalex.org/W<...>``
        - an OpenAlex work ID: ``W<...>``

        Arbitrary URLs are rejected to prevent metadata-driven SSRF.
        """
        if source_id.startswith("https://"):
            parsed = urlparse(source_id)
            if parsed.scheme != "https" or parsed.netloc != "openalex.org":
                return None
            work_id = source_id
        elif source_id.startswith("W") and source_id[1:].isalnum():
            work_id = f"https://openalex.org/{source_id}"
        else:
            return None

        params: dict[str, Any] = {}
        if self.mailto:
            params["mailto"] = self.mailto
        headers = {"User-Agent": "mailto:research@example.com"}
        try:
            response = safe_get(
                work_id,
                params=params,
                headers=headers,
                timeout=self.timeout,
            )
            response.raise_for_status()
            return self._normalize(response.json())
        except Exception:  # noqa: BLE001
            return None

    def _normalize(self, raw: dict[str, Any]) -> Paper:
        authors = []
        for authorship in raw.get("authorships", []):
            author = authorship.get("author", {})
            name = author.get("display_name")
            if name:
                authors.append(name)

        title = raw.get("display_name", "")
        doi = raw.get("doi")
        if doi:
            doi = doi.replace("https://doi.org/", "")

        year: int | None = None
        pub_date = raw.get("publication_date")
        if pub_date and len(pub_date) >= 4:
            try:
                year = int(pub_date[:4])
            except ValueError:
                year = None

        open_access = raw.get("open_access") or {}
        pdf_url = open_access.get("oa_url") if isinstance(open_access, dict) else None

        return Paper(
            title=title,
            authors=authors,
            year=year,
            doi=doi,
            url=raw.get("id"),
            pdf_url=pdf_url,
            abstract=raw.get("abstract", "") or _rebuild_abstract(raw.get("abstract_inverted_index")),
            source=self.name,
            source_id=raw.get("id"),
            meta={
                "cited_by_count": raw.get("cited_by_count"),
                "concepts": [c.get("display_name") for c in raw.get("concepts", [])],
            },
        )

    def health(self) -> dict[str, Any]:
        return {"ok": True, "source": self.name, "mailto": bool(self.mailto)}


def _rebuild_abstract(inverted_index: Any) -> str:
    """OpenAlex ships abstracts as {word: [positions]}; rebuild the plain text."""
    if not isinstance(inverted_index, dict):
        return ""
    positions: list[tuple[int, str]] = []
    for word, indexes in inverted_index.items():
        if not isinstance(indexes, list):
            continue
        positions.extend((i, str(word)) for i in indexes if isinstance(i, int))
    return " ".join(word for _, word in sorted(positions))
