"""Raw HTTP client with retries, backoff, jitter, and header rotation."""

from __future__ import annotations

import random
import time
from typing import Any

import httpx

from research_engine.browser.ai_browser import (
    AIBrowser,
    BrowserAction,
    BrowserActionType,
    BrowserResult,
)
from research_engine.browser.fingerprint import FingerprintRotator
from research_engine.browser.policy import URLPolicy


class RawHTTPBrowser(AIBrowser):
    """HTTP-only browser: fast, lightweight, and policy-guarded."""

    name = "raw_http"

    SAFE_METHODS = {"GET", "HEAD", "OPTIONS"}

    def __init__(
        self,
        policy: URLPolicy | None = None,
        fingerprints: FingerprintRotator | None = None,
        timeout: float = 30.0,
        max_retries: int = 3,
        base_backoff: float = 1.0,
    ) -> None:
        self.policy = policy or URLPolicy()
        self.fingerprints = fingerprints or FingerprintRotator()
        self.timeout = timeout
        self.max_retries = max_retries
        self.base_backoff = base_backoff
        self._client: httpx.Client | None = None

    def _get_client(self) -> httpx.Client:
        if self._client is None or self._client.is_closed:
            self._client = httpx.Client(
                timeout=self.timeout,
                follow_redirects=True,
                headers=self.fingerprints.next_headers(),
            )
        return self._client

    def act(self, action: BrowserAction) -> BrowserResult:
        if action.action == BrowserActionType.FETCH:
            return self._fetch(action)
        if action.action == BrowserActionType.API:
            return self._api(action)
        return BrowserResult(
            ok=False,
            action=action.action,
            url=action.url,
            status=None,
            content="",
            error=f"Action {action.action.value} not supported by RawHTTPBrowser",
        )

    def health(self) -> dict[str, Any]:
        return {"ok": True, "client": "httpx", "policy": self.policy.rules_summary()}

    def _fetch(self, action: BrowserAction) -> BrowserResult:
        url = action.url
        if not url:
            return BrowserResult(
                ok=False,
                action=BrowserActionType.FETCH,
                url=None,
                status=None,
                content="",
                error="fetch requires url",
            )
        allowed, reason = self.policy.allow(url)
        if not allowed:
            return BrowserResult(
                ok=False,
                action=BrowserActionType.FETCH,
                url=url,
                status=None,
                content="",
                error=f"URL blocked by policy: {reason}",
            )

        method = action.method.upper() if action.method.upper() in self.SAFE_METHODS else "GET"
        headers = self.fingerprints.next_headers()
        headers.update(action.headers)

        for attempt in range(self.max_retries + 1):
            try:
                client = self._get_client()
                response = client.request(
                    method=method,
                    url=url,
                    headers=headers,
                    content=action.body,
                )
                if response.status_code < 500 or response.status_code == 404:
                    return BrowserResult(
                        ok=response.status_code < 400,
                        action=BrowserActionType.FETCH,
                        url=str(response.url),
                        status=response.status_code,
                        content=response.text,
                        headers=dict(response.headers),
                    )
                # 5xx triggers retry.
                if attempt < self.max_retries:
                    self._backoff(attempt)
            except httpx.RequestError as exc:
                if attempt < self.max_retries:
                    self._backoff(attempt)
                    continue
                return BrowserResult(
                    ok=False,
                    action=BrowserActionType.FETCH,
                    url=url,
                    status=None,
                    content="",
                    error=f"Request error: {exc}",
                )

        # Should not reach here, but guard anyway.
        return BrowserResult(
            ok=False,
            action=BrowserActionType.FETCH,
            url=url,
            status=None,
            content="",
            error="Max retries exceeded",
        )

    def _api(self, action: BrowserAction) -> BrowserResult:
        result = self._fetch(action)
        if not result.ok:
            return result
        return BrowserResult(
            ok=result.ok,
            action=BrowserActionType.API,
            url=result.url,
            status=result.status,
            content=result.content,
            headers=result.headers,
        )

    def _backoff(self, attempt: int) -> None:
        sleep = self.base_backoff * (2 ** attempt) + random.uniform(0, 1)
        time.sleep(sleep)

    def close(self) -> None:
        if self._client is not None and not self._client.is_closed:
            self._client.close()
