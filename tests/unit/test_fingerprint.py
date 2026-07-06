"""Unit tests for the fingerprint rotator."""

from __future__ import annotations

from research_engine.browser.fingerprint import FingerprintRotator


def test_headers_contain_user_agent() -> None:
    rotator = FingerprintRotator(seed=42)
    headers = rotator.next_headers()
    assert "User-Agent" in headers
    assert "Chrome" in headers["User-Agent"]


def test_headers_are_deterministic_with_seed() -> None:
    rotator = FingerprintRotator(seed=7)
    first = rotator.next_headers()
    second = rotator.next_headers()
    assert first["User-Agent"] in FingerprintRotator.USER_AGENTS
    assert second["User-Agent"] in FingerprintRotator.USER_AGENTS
    assert first["Viewport-Width"] in {"1920", "1440", "1366"}
    assert second["Viewport-Width"] in {"1920", "1440", "1366"}


def test_headers_are_legitimate() -> None:
    headers = FingerprintRotator().next_headers()
    assert "Accept" in headers
    assert "Accept-Language" in headers
    assert headers.get("DNT") == "1"
    assert headers["Viewport-Width"] in {"1920", "1440", "1366"}
