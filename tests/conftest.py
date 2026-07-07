"""Shared pytest fixtures."""

from __future__ import annotations

from typing import Any
from urllib.parse import urlparse

import pytest

from research_engine.browser.policy import URLPolicy


def _host(url: str | Any) -> str:
    return urlparse(str(url)).hostname or str(url)


@pytest.fixture
def stub_public_dns(monkeypatch: pytest.MonkeyPatch) -> None:
    """Make DNS resolution return the original host as a "public" IP in tests.

    The source-adapter and resolver tests monkey-patch ``httpx.Client.request``
    and do not perform real network I/O. DNS resolution of API hostnames would
    otherwise fail or timeout, so we return the original host unchanged.
    This keeps the pinned URL identical to the original URL that tests register
    responses against, while still exercising the pinning/policy validation
    paths.

    This fixture is **not** autouse so that real SSRF tests can exercise
    ``resolve_hosts=True`` without a global stub.
    """
    monkeypatch.setattr(
        URLPolicy,
        "_host_resolves_to_public_ip",
        lambda _self, _host, _port: (True, ""),
    )
    monkeypatch.setattr(
        "research_engine.browser.ssrf_guard.resolve_public_ip",
        lambda _url, resolve_hosts=True, **_kwargs: (_host(_url), _host(_url)),
    )
