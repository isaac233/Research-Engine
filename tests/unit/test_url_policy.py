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


def test_allow_list_overrides_public_host(policy: URLPolicy) -> None:
    policy = URLPolicy(allow_list=["example.com"])
    allowed, reason = policy.allow("https://example.com/")
    assert allowed is True
    assert reason == "explicit allow-list"


def test_allow_list_cannot_override_localhost(policy: URLPolicy) -> None:
    policy = URLPolicy(allow_list=["localhost"])
    allowed, reason = policy.allow("https://localhost/")
    assert allowed is False
    assert "blocked" in reason


def test_rules_summary(policy: URLPolicy) -> None:
    summary = policy.rules_summary()
    assert "blocked_schemes" in summary
    assert "file" in summary["blocked_schemes"]
    assert "allow_list" in summary


@pytest.mark.parametrize(
    "url",
    [
        "https://[::1]/admin",
        "https://[::ffff:127.0.0.1]/",
        "https://127.000.000.001/",
    ],
)
def test_blocks_ipv6_and_obfuscated_loopback(policy: URLPolicy, url: str) -> None:
    allowed, reason = policy.allow(url)
    assert allowed is False, f"{url} should be blocked, got: {reason}"


def test_blocks_nonstandard_web_ports(policy: URLPolicy) -> None:
    for url in ("https://example.com:8080/", "https://example.com:22/"):
        allowed, reason = policy.allow(url)
        assert allowed is False, reason


def test_allows_standard_ports(policy: URLPolicy) -> None:
    for url in ("https://example.com/", "http://example.com:80/"):
        allowed, _ = policy.allow(url)
        assert allowed is True


def test_blocks_url_with_credentials(policy: URLPolicy) -> None:
    allowed, _ = policy.allow("https://user:pass@example.com/")
    assert allowed is False


def test_blocks_reserved_and_multicast_ips(policy: URLPolicy) -> None:
    for host in ("240.0.0.1", "224.0.0.1", "169.254.1.1"):
        allowed, reason = policy.allow(f"https://{host}/")
        assert allowed is False, reason


def test_blocks_missing_host(policy: URLPolicy) -> None:
    allowed, reason = policy.allow("https:///path")
    assert allowed is False
    assert "missing host" in reason


@pytest.mark.parametrize(
    "url",
    [
        "https://%6c%6f%63%61%6c%68%6f%73%74/",  # percent-encoded localhost
        "https://127.0.0.%31/",  # percent-encoded 127.0.0.1
    ],
)
def test_blocks_url_encoded_local_hosts(policy: URLPolicy, url: str) -> None:
    allowed, reason = policy.allow(url)
    assert allowed is False, f"{url} should be blocked, got: {reason}"


def test_idna_homoglyph_does_not_match_allow_list(policy: URLPolicy) -> None:
    # Cyrillic 'е' (U+0435) instead of Latin 'e' in "example.com".
    homoglyph = "https://еxample.com/"
    policy = URLPolicy(allow_list=["example.com"])
    allowed, reason = policy.allow(homoglyph)
    assert allowed is False, f"homoglyph should not match allow-list, got: {reason}"
