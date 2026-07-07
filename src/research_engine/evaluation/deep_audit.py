"""Deep audit trigger and frontier-model audit runner."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from research_engine.llm.provider import LLMProvider, Message


@dataclass(frozen=True, slots=True)
class DeepAuditResult:
    """Outcome of a frontier-model audit of the eval/adversarial chain."""

    anomalies: list[str]
    recommendations: list[str]
    raw_response: str = ""


class DeepAuditor:
    """Run periodic frontier-model audits of logs and the adversarial chain."""

    def __init__(self, provider: LLMProvider | None = None, model: str | None = None) -> None:
        self.provider = provider
        self.model = model

    def audit(
        self,
        campaign_meta: dict[str, Any],
        trigger: str = "periodic",
    ) -> DeepAuditResult:
        """Return audit findings; if no provider is available, return empty findings."""
        if self.provider is None:
            return DeepAuditResult(
                anomalies=[],
                recommendations=["No frontier provider configured; deep audit skipped."],
                raw_response="",
            )

        prompt = f"""Review the campaign metadata below and identify any anomalies or weaknesses in the adversarial/evaluation chain.

Trigger: {trigger}

Metadata keys: {list(campaign_meta.keys())}

Reply with:
ANOMALIES:
- one per line
RECOMMENDATIONS:
- one per line"""
        messages = [
            Message(role="system", content="You are a meticulous audit reviewer."),
            Message(role="user", content=prompt),
        ]
        try:
            response = self.provider.complete(messages, model=self.model, temperature=0.0, max_tokens=512)
        except Exception as exc:  # noqa: BLE001
            return DeepAuditResult(
                anomalies=[],
                recommendations=[f"Deep audit failed: {exc}"],
                raw_response="",
            )
        return self._parse(response)

    def _parse(self, response: str) -> DeepAuditResult:
        anomalies: list[str] = []
        recommendations: list[str] = []
        target = anomalies
        for line in response.splitlines():
            stripped = line.strip()
            if not stripped:
                continue
            if stripped.upper().startswith("ANOMALIES"):
                target = anomalies
                continue
            if stripped.upper().startswith("RECOMMENDATIONS"):
                target = recommendations
                continue
            if stripped.startswith("-"):
                target.append(stripped.lstrip("-").strip())
        return DeepAuditResult(anomalies=anomalies, recommendations=recommendations, raw_response=response)
