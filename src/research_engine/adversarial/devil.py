"""Devil adversarial agent: challenges claims for evidence, soundness, and coverage."""

from __future__ import annotations

from research_engine.adversarial.challenge import Challenge
from research_engine.extraction.structured import ExtractedSource
from research_engine.llm.provider import LLMProvider, Message


class DevilAgent:
    """Rule-based adversarial challenger with optional frontier-model deep audit."""

    def __init__(self, provider: LLMProvider | None = None, model: str | None = None) -> None:
        self.provider = provider
        self.model = model

    def challenge(
        self,
        sources: list[ExtractedSource],
        query: str = "",
    ) -> list[Challenge]:
        """Return challenges for weak, unsupported, or thin claims."""
        challenges: list[Challenge] = []
        for source in sources:
            for index, claim in enumerate(source.claims):
                source_id = source.paper.source_id or source.paper.doi
                claim_text = claim.claim

                if not claim.evidence or len(claim.evidence.strip()) < 20:
                    challenges.append(
                        Challenge(
                            claim_index=index,
                            source_id=source_id,
                            claim_text=claim_text,
                            severity="high",
                            kind="missing_evidence",
                            reason="Claim lacks supporting evidence or evidence is too short.",
                            requested_evidence="Provide the sentence or table from the source that supports this claim.",
                        )
                    )

                if claim.confidence == "low":
                    challenges.append(
                        Challenge(
                            claim_index=index,
                            source_id=source_id,
                            claim_text=claim_text,
                            severity="medium",
                            kind="low_confidence",
                            reason="Extractor assigned low confidence to this claim.",
                            requested_evidence="Re-run extraction with more context or flag for manual review.",
                        )
                    )

                if not (source.paper.doi or source.paper.pdf_url or source.paper.url):
                    challenges.append(
                        Challenge(
                            claim_index=index,
                            source_id=source_id,
                            claim_text=claim_text,
                            severity="high",
                            kind="missing_source",
                            reason="No DOI, PDF URL, or landing page available for the source.",
                            requested_evidence="Resolve a stable URL or DOI for the source.",
                        )
                    )

                if len(claim.claim.split()) < 6:
                    challenges.append(
                        Challenge(
                            claim_index=index,
                            source_id=source_id,
                            claim_text=claim_text,
                            severity="low",
                            kind="coverage",
                            reason="Claim is very short; may omit nuance or caveats.",
                            requested_evidence="Restate the claim with full context and any stated limitations.",
                        )
                    )

        if self.provider is not None:
            challenges.extend(self._llm_challenges(sources, query))

        return challenges

    def _llm_challenges(self, sources: list[ExtractedSource], query: str) -> list[Challenge]:
        """Optional frontier-model audit. Returns no challenges on failure to avoid false positives."""
        assert self.provider is not None
        if not sources or not any(s.claims for s in sources):
            return []
        claims_text = "\n".join(
            f"[{i}] {claim.claim}"
            for i, source in enumerate(sources)
            for claim in source.claims
        )
        messages = [
            Message(
                role="system",
                content="You are a skeptical reviewer. Identify the weakest claims in the list below. Reply with one line per issue: severity|claim_index|reason|requested_evidence. Use only high/medium/low for severity.",
            ),
            Message(
                role="user",
                content=f"Research query: {query}\n\nClaims:\n{claims_text}",
            ),
        ]
        try:
            response = self.provider.complete(messages, model=self.model, temperature=0.0, max_tokens=512)
        except Exception:  # noqa: BLE001
            return []
        return self._parse_llm_response(response, sources)

    def _parse_llm_response(self, response: str, sources: list[ExtractedSource]) -> list[Challenge]:
        challenges: list[Challenge] = []
        for line in response.strip().splitlines():
            parts = [p.strip() for p in line.split("|")]
            if len(parts) != 4:
                continue
            severity, raw_index, reason, requested = parts
            if severity not in {"high", "medium", "low"}:
                continue
            try:
                index = int(raw_index)
            except ValueError:
                continue
            flat_claims = [(source, claim) for source in sources for claim in source.claims]
            if not (0 <= index < len(flat_claims)):
                continue
            source, claim = flat_claims[index]
            challenges.append(
                Challenge(
                    claim_index=index,
                    source_id=source.paper.source_id or source.paper.doi,
                    claim_text=claim.claim,
                    severity=severity,
                    kind="llm_audit",
                    reason=reason,
                    requested_evidence=requested,
                )
            )
        return challenges
