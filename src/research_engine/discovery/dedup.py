"""Deduplication engine for discovered papers."""

from __future__ import annotations

import re
from difflib import SequenceMatcher
from typing import Any

from research_engine.discovery.schema import DuplicateGroup, Paper


class DedupEngine:
    """Fuzzy deduplication of papers by DOI, URL, and normalized title."""

    TITLE_SIMILARITY_THRESHOLD = 0.85

    def __init__(self, title_threshold: float = TITLE_SIMILARITY_THRESHOLD) -> None:
        self.title_threshold = title_threshold

    def deduplicate(self, papers: list[Paper]) -> list[DuplicateGroup]:
        """Return groups of duplicate papers; first item in each group is canonical."""
        groups: list[DuplicateGroup] = []
        for paper in papers:
            match_index: int | None = None
            match_reason = ""
            for idx, group in enumerate(groups):
                reason = self._is_duplicate(paper, group.canonical)
                if reason:
                    match_index = idx
                    match_reason = reason
                    break
            if match_index is not None:
                group = groups[match_index]
                groups[match_index] = DuplicateGroup(
                    canonical=group.canonical,
                    duplicates=[*group.duplicates, paper],
                    match_reason=match_reason,
                )
            else:
                groups.append(DuplicateGroup(canonical=paper, match_reason="canonical"))
        return groups

    def is_duplicate(self, a: Paper, b: Paper) -> str:
        """Public check: return reason string if a and b are duplicates, else empty."""
        return self._is_duplicate(a, b)

    def _is_duplicate(self, a: Paper, b: Paper) -> str:
        # DOI exact match is strongest signal.
        if a.doi and b.doi:
            if a.doi.lower().strip() == b.doi.lower().strip():
                return "doi_exact"
            # Different DOIs mean different works; do not fuzzy-match over them.
            return ""

        # URL exact match (after normalization).
        a_url = self._normalize_url(a.url)
        b_url = self._normalize_url(b.url)
        if a_url and b_url and a_url == b_url:
            return "url_exact"

        # Title fuzzy match with same year (if both have year).
        a_title = self._normalize_title(a.title)
        b_title = self._normalize_title(b.title)
        if a_title and b_title:
            similarity = SequenceMatcher(None, a_title, b_title).ratio()
            if similarity >= self.title_threshold:
                if a.year and b.year and a.year != b.year:
                    # Same title but different year: not a duplicate.
                    return ""
                return f"title_similarity:{similarity:.2f}"

        return ""

    def _normalize_title(self, title: str) -> str:
        cleaned = title.lower()
        # Remove common subtitle splitters before stripping punctuation.
        cleaned = re.sub(r"\s*[:;—–-]\s*.*$", "", cleaned)
        cleaned = re.sub(r"[^\w\s]", "", cleaned)
        cleaned = re.sub(r"\s+", " ", cleaned).strip()
        return cleaned

    def _normalize_url(self, url: str | None) -> str:
        if not url:
            return ""
        url = url.lower().strip()
        url = re.sub(r"^https?://", "", url)
        url = re.sub(r"www\.", "", url)
        url = url.rstrip("/")
        return url

    def stats(self, groups: list[DuplicateGroup]) -> dict[str, Any]:
        total = sum(1 + len(g.duplicates) for g in groups)
        return {
            "input_count": total,
            "canonical_count": len(groups),
            "duplicate_count": total - len(groups),
            "groups": [
                {
                    "canonical": g.canonical.key,
                    "duplicates": [d.key for d in g.duplicates],
                    "reason": g.match_reason,
                }
                for g in groups
            ],
        }
