"""Safe HTTP helpers for source adapters.

Adapters talk to fixed, trusted API endpoints. The risk we guard against is
an upstream redirect or a caller-supplied identifier being turned into a
request to an internal/private URL.
"""

from __future__ import annotations

from typing import Any

import httpx

from research_engine.browser import ssrf_guard
from research_engine.browser.policy import URLPolicy

DEFAULT_MAX_REDIRECTS = 5
DEFAULT_MAX_BODY_SIZE = 50 * 1024 * 1024  # 50 MiB


def safe_get(
    url: str,
    *,
    params: dict[str, Any] | None = None,
    headers: dict[str, str] | None = None,
    timeout: float = 30.0,
    policy: URLPolicy | None = None,
    max_redirects: int = DEFAULT_MAX_REDIRECTS,
    max_body_size: int = DEFAULT_MAX_BODY_SIZE,
) -> httpx.Response:
    """Issue a GET request with DNS pinning and policy-checked redirects.

    ``httpx`` is told not to follow redirects automatically. Each request
    target is validated with ``URLPolicy`` (including DNS resolution) and
    then pinned to the resolved public IP with the original ``Host`` header
    and SNI hostname. This delegates the actual request handling to
    ``ssrf_guard.safe_request`` so body-size limits and DNS pinning are
    implemented in one place.
    """
    policy = policy or URLPolicy()
    current_url = str(httpx.URL(url, params=params)) if params else url
    with httpx.Client(timeout=timeout) as client:
        for _redirect in range(max_redirects + 1):
            allowed, reason = policy.allow(current_url, resolve_hosts=False)
            if not allowed:
                raise RuntimeError(f"URL blocked by policy: {reason}")

            response = ssrf_guard.safe_request(
                client,
                "GET",
                current_url,
                headers=headers,
                resolve_hosts=True,
                max_body_size=max_body_size,
            )

            redirect_target = ssrf_guard.safe_redirect_url(response, current_url)
            if redirect_target is not None:
                current_url = redirect_target
                continue

            return response

    raise RuntimeError("Too many redirects")
