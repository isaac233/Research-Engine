"""Verifier: re-runs claimed source lookups and checks for hallucinated citations."""

from __future__ import annotations

import re
from typing import Any, Protocol

from research_engine.adversarial.challenge import VerificationResult
from research_engine.extraction.citation import normalize_doi
from research_engine.extraction.structured import ExtractedSource


class HTTPClient(Protocol):
    """Minimal HTTP client protocol for reachability checks."""

    def head(self, url: str) -> Any:
        ...


class Verifier:
    """Verify claims against their extracted source text and locators."""

    def __init__(self, http_client: HTTPClient | None = None) -> None:
        self.http_client = http_client

    def verify(self, sources: list[ExtractedSource]) -> list[VerificationResult]:
        """Return a verification result for every claim."""
        results: list[VerificationResult] = []
        for source in sources:
            source_text = " ".join(
                [
                    source.summary,
                    source.methodology,
                    source.data_summary,
                    source.results_summary,
                ]
            )
            for index, claim in enumerate(source.claims):
                source_id = source.paper.source_id or source.paper.doi
                claim_text = claim.claim
                ok = True
                reasons: list[str] = []

                if not claim.evidence:
                    ok = False
                    reasons.append("claim has no quoted evidence")
                elif _normalize(claim.evidence) not in _normalize(source_text):
                    ok = False
                    reasons.append("quoted evidence not found in extracted source text")

                if not (source.paper.doi or source.paper.pdf_url or source.paper.url):
                    ok = False
                    reasons.append("source has no DOI, PDF URL, or landing page")
                elif source.paper.doi and not _valid_doi(source.paper.doi):
                    ok = False
                    reasons.append("DOI does not match expected shape")

                if self.http_client is not None:
                    url: str | None = source.full_text_url or source.paper.pdf_url or source.paper.url
                    if url is not None and not _url_reachable(self.http_client, url):
                        ok = False
                        reasons.append("source URL is not reachable")

                results.append(
                    VerificationResult(
                        claim_index=index,
                        source_id=source_id,
                        claim_text=claim_text,
                        ok=ok,
                        reason="; ".join(reasons) if reasons else "claim checks passed",
                    )
                )
        return results


def _normalize(text: str) -> str:
    """Collapse whitespace for fuzzy substring matching."""
    return re.sub(r"\s+", " ", text.lower()).strip()


def _valid_doi(doi: str) -> bool:
    r"""DOI prefix must be `10.\d+/...`."""
    cleaned = normalize_doi(doi)
    return bool(re.match(r"10\.\d+/[-._;()/:\wA-Za-z0-9]+", cleaned))


def _url_reachable(client: HTTPClient, url: str) -> bool:
    try:
        response = client.head(url)
        return getattr(response, "status_code", 0) < 400
    except Exception:  # noqa: BLE001
        return False
