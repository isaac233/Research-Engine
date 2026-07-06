"""Unit tests for the ethical URL policy."""

from __future__ import annotations

import pytest

from research_engine.browser.policy import URLPolicy


@pytest.fixture
def policy() -> URLPolicy:
    return URLPolicy()


def test_allows_https_public_url(policy: URLPolicy) -> None:
    allowed, reason = policy.allow("https://example.com/path?q=1")
    assert allowed is True
    assert reason == "allowed"


def test_allows_http_scheme(policy: URLPolicy) -> None:
    allowed, reason = policy.allow("http://example.com")
    assert allowed is True
    assert reason == "allowed"


def test_blocks_file_scheme(policy: URLPolicy) -> None:
    allowed, reason = policy.allow("file:///etc/passwd")
    assert allowed is False
    assert "file" in reason


def test_blocks_localhost(policy: URLPolicy) -> None:
    for host in ("localhost", "127.0.0.1", "::1", "0.0.0.0"):
        allowed, _ = policy.allow(f"https://{host}/")
        assert allowed is False


def test_blocks_private_ip(policy: URLPolicy) -> None:
    for host in ("10.0.0.1", "192.168.1.1", "172.16.0.1", "169.254.1.1"):
        allowed, reason = policy.allow(f"https://{host}/")
        assert allowed is False, reason


def test_blocks_local_hostname(policy: URLPolicy) -> None:
    allowed, _ = policy.allow("https://mybox.local/")
    assert allowed is False


def test_allow_list_overrides(policy: URLPolicy) -> None:
    policy = URLPolicy(allow_list=["localhost"])
    allowed, reason = policy.allow("https://localhost/")
    assert allowed is True
    assert reason == "explicit allow-list"


def test_rules_summary(policy: URLPolicy) -> None:
    summary = policy.rules_summary()
    assert "blocked_schemes" in summary
    assert "file" in summary["blocked_schemes"]
    assert "allow_list" in summary
