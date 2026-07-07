"""Full-text resolver: map discovered papers to downloadable open-access URLs."""

from __future__ import annotations

import re
from typing import Any

import httpx

from research_engine.browser.policy import URLPolicy
from research_engine.discovery.schema import Paper, ResolveResult


class FullTextResolver:
    """Resolve papers to open-access PDF/HTML URLs without paywall scraping."""

    def __init__(
        self,
        email: str = "research@example.com",
        timeout: float = 20.0,
        policy: URLPolicy | None = None,
    ) -> None:
        self.email = email
        self.timeout = timeout
        self.policy = policy or URLPolicy()

    def resolve(self, paper: Paper) -> ResolveResult:
        """Find an authorized open-access full-text URL for a paper."""
        # 1. Already known PDF URL.
        if paper.pdf_url:
            allowed, reason = self.policy.allow(paper.pdf_url)
            if allowed:
                return ResolveResult(
                    paper_key=paper.key,
                    url=paper.pdf_url,
                    is_oa=True,
                    source="adapter_pdf_url",
                    reason="PDF URL provided by source adapter",
                )

        # 2. arXiv ID.
        arxiv_id = self._extract_arxiv_id(paper)
        if arxiv_id:
            pdf_url = f"https://arxiv.org/pdf/{arxiv_id}.pdf"
            allowed, _ = self.policy.allow(pdf_url)
            if allowed:
                return ResolveResult(
                    paper_key=paper.key,
                    url=pdf_url,
                    is_oa=True,
                    source="arxiv",
                    reason=f"arXiv ID {arxiv_id}",
                )

        # 3. Unpaywall by DOI.
        if paper.doi:
            up_result = self._unpaywall(paper.doi)
            if up_result.url:
                return up_result

        # 4. DOI landing page (not guaranteed OA, but authorized).
        if paper.doi:
            doi_url = f"https://doi.org/{paper.doi}"
            allowed, _ = self.policy.allow(doi_url)
            if allowed:
                return ResolveResult(
                    paper_key=paper.key,
                    url=doi_url,
                    is_oa=False,
                    source="doi_landing",
                    reason="DOI landing page; verify access before use",
                    evidence={"doi": paper.doi},
                )

        return ResolveResult(
            paper_key=paper.key,
            url=None,
            is_oa=False,
            source="none",
            reason="No open-access URL, arXiv ID, or DOI found",
            evidence={"doi": paper.doi, "source_id": paper.source_id},
        )

    def _extract_arxiv_id(self, paper: Paper) -> str | None:
        if paper.source == "arxiv" and paper.source_id:
            return paper.source_id.split("v")[0]
        if paper.url:
            match = re.search(r"arxiv\.org/abs/(\d+\.\d+)", paper.url)
            if match:
                return match.group(1)
        if paper.doi and paper.doi.startswith("10.48550/arXiv."):
            return paper.doi.replace("10.48550/arXiv.", "")
        return None

    def _unpaywall(self, doi: str) -> ResolveResult:
        url = f"https://api.unpaywall.org/v2/{doi}"
        params = {"email": self.email}
        try:
            response = httpx.get(
                url,
                params=params,
                timeout=self.timeout,
                follow_redirects=True,
            )
            response.raise_for_status()
            data = response.json()
        except httpx.HTTPStatusError as exc:
            return ResolveResult(
                paper_key=doi,
                url=None,
                is_oa=False,
                source="unpaywall",
                reason=f"HTTP {exc.response.status_code}",
                evidence={"doi": doi},
            )
        except httpx.RequestError as exc:
            return ResolveResult(
                paper_key=doi,
                url=None,
                is_oa=False,
                source="unpaywall",
                reason=f"Request error: {exc}",
                evidence={"doi": doi},
            )

        is_oa = bool(data.get("is_oa"))
        best_oa = data.get("best_oa_location") or {}
        oa_url = best_oa.get("url") if isinstance(best_oa, dict) else None
        oa_url_pdf = best_oa.get("url_for_pdf") if isinstance(best_oa, dict) else None
        resolved = oa_url_pdf or oa_url

        if resolved:
            allowed, _ = self.policy.allow(resolved)
            if allowed:
                return ResolveResult(
                    paper_key=doi,
                    url=resolved,
                    is_oa=is_oa,
                    source="unpaywall",
                    reason="Open-access location from Unpaywall",
                    evidence={
                        "doi": doi,
                        "license": best_oa.get("license"),
                        "version": best_oa.get("version"),
                    },
                )

        return ResolveResult(
            paper_key=doi,
            url=None,
            is_oa=is_oa,
            source="unpaywall",
            reason="No open-access URL in Unpaywall response",
            evidence={"doi": doi, "is_oa": is_oa},
        )

    def health(self) -> dict[str, Any]:
        return {"ok": True, "source": "full_text_resolver", "email": bool(self.email)}
