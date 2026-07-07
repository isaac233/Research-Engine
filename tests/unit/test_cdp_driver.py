"""Unit tests for the CDP/Playwright driver."""

from __future__ import annotations

import pytest

pytest.importorskip("playwright")

from research_engine.browser.ai_browser import BrowserAction, BrowserActionType
from research_engine.browser.cdp_driver import CDPDriver


def test_health_returns_status() -> None:
    driver = CDPDriver(headless=True)
    health = driver.health()
    assert health["ok"] is True
    assert health["client"] == "playwright"
    assert health["headless"] is True


def test_unsupported_action_returns_error() -> None:
    driver = CDPDriver()
    result = driver.act(BrowserAction(action=BrowserActionType.UNBLOCK))
    assert result.ok is False
    assert "not supported" in (result.error or "").lower()


def test_fetch_requires_url() -> None:
    driver = CDPDriver()
    result = driver.act(BrowserAction(action=BrowserActionType.FETCH))
    assert result.ok is False
    assert "url" in (result.error or "").lower()


def test_fetch_blocks_policy_violation() -> None:
    driver = CDPDriver()
    result = driver.act(BrowserAction(action=BrowserActionType.FETCH, url="file:///etc/passwd"))
    assert result.ok is False
    assert "policy" in (result.error or "").lower()
