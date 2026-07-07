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
from research_engine.browser.ssrf_guard import safe_redirect_url, safe_request


class RawHTTPBrowser(AIBrowser):
    """HTTP-only browser: fast, lightweight, and policy-guarded."""

    name = "raw_http"

    SAFE_METHODS = {"GET", "HEAD", "OPTIONS"}
    MAX_BODY_SIZE = 50 * 1024 * 1024
    MAX_REDIRECTS = 5

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
                follow_redirects=False,
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

    def fetch_bytes(self, url: str, headers: dict[str, str] | None = None) -> bytes:
        """Fetch raw response bytes, pinned to a pre-validated public IP."""
        return self._request_bytes_with_redirects(
            method="GET",
            url=url,
            headers=dict(headers or {}),
        )

    def _fetch(self, action: BrowserAction) -> BrowserResult:
        url = action.url
        if not url:
            return BrowserResult(
                ok=False,
                action=action.action,
                url=None,
                status=None,
                content="",
                error="fetch requires url",
            )

        # API actions preserve their method; FETCH actions are restricted to safe methods.
        if action.action == BrowserActionType.API:
            method = action.method.upper() if action.method else "GET"
        else:
            method = action.method.upper() if action.method.upper() in self.SAFE_METHODS else "GET"
        headers = self.fingerprints.next_headers()
        headers.update(action.headers)

        return self._request_with_retry(
            action=action.action,
            method=method,
            url=url,
            headers=headers,
            content=action.body,
        )

    def _request_with_retry(
        self,
        action: BrowserActionType,
        method: str,
        url: str,
        headers: dict[str, str] | None = None,
        content: bytes | str | None = None,
    ) -> BrowserResult:
        """Issue a request with retries/backoff on transient failures."""
        last_error = ""
        for attempt in range(self.max_retries + 1):
            try:
                response = self._request_with_redirects(
                    method=method,
                    url=url,
                    headers=headers,
                    content=content,
                )
                return BrowserResult(
                    ok=True,
                    action=action,
                    url=url,
                    status=response.status_code,
                    content=response.text,
                    headers=dict(response.headers),
                )
            except (httpx.HTTPError, OSError) as exc:
                last_error = f"HTTP error: {exc}"
                if attempt < self.max_retries:
                    self._backoff(attempt)
                    continue
                return BrowserResult(
                    ok=False,
                    action=action,
                    url=url,
                    status=None,
                    content="",
                    error=last_error,
                )
            except RuntimeError as exc:
                last_error = str(exc)
                # Retry transient server errors and rate-limit responses.
                transient = (
                    "server error" in last_error.lower()
                    or "429" in last_error
                    or "too many requests" in last_error.lower()
                )
                if transient and attempt < self.max_retries:
                    self._backoff(attempt)
                    continue
                return BrowserResult(
                    ok=False,
                    action=action,
                    url=url,
                    status=None,
                    content="",
                    error=last_error,
                )

        # Safety net for type checkers; all loop paths above return.
        return BrowserResult(
            ok=False,
            action=action,
            url=url,
            status=None,
            content="",
            error=last_error or "fetch failed after retries",
        )

    def _request_with_redirects(
        self,
        method: str,
        url: str,
        headers: dict[str, str] | None = None,
        content: bytes | str | None = None,
        max_redirects: int | None = None,
    ) -> httpx.Response:
        """Issue a request and follow redirects while re-checking policy.

        All requests are pinned to pre-validated public IPs to close DNS-rebinding.
        """
        allowed, reason = self.policy.allow(url)
        if not allowed:
            raise RuntimeError(f"URL blocked by policy: {reason}")

        max_redirects = max_redirects if max_redirects is not None else self.MAX_REDIRECTS
        client = self._get_client()
        current_url = url
        for _ in range(max_redirects + 1):
            response = safe_request(
                client,
                method=method,
                url=current_url,
                headers=headers,
                content=content,
                resolve_hosts=True,
                max_body_size=self.MAX_BODY_SIZE,
            )
            if 500 <= response.status_code < 600:
                raise RuntimeError(f"Server error {response.status_code}")
            redirect_url = safe_redirect_url(response, current_url)
            if redirect_url is not None:
                current_url = redirect_url
                allowed, reason = self.policy.allow(current_url)
                if not allowed:
                    raise RuntimeError(f"Redirect blocked by policy: {reason}")
                continue
            if response.status_code >= 400:
                raise RuntimeError(f"HTTP error {response.status_code}")
            return response
        raise RuntimeError("Too many redirects")

    def _request_bytes_with_redirects(
        self,
        method: str,
        url: str,
        headers: dict[str, str] | None = None,
        content: bytes | str | None = None,
        max_redirects: int | None = None,
    ) -> bytes:
        """Issue a request and return raw response bytes, following redirects."""
        response = self._request_with_redirects(
            method=method,
            url=url,
            headers=headers,
            content=content,
            max_redirects=max_redirects,
        )
        return response.content

    def _api(self, action: BrowserAction) -> BrowserResult:
        return self._fetch(action)

    def _backoff(self, attempt: int) -> None:
        sleep = self.base_backoff * (2 ** attempt) + random.uniform(0, 1)
        time.sleep(sleep)

    def close(self) -> None:
        if self._client is not None and not self._client.is_closed:
            self._client.close()
