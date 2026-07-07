"""Unit tests for robots.txt enforcement."""

from __future__ import annotations

import pytest

from research_engine.browser.ai_browser import BrowserActionType, BrowserResult
from research_engine.browser.robots import RobotsChecker


class FakeBrowser:
    def __init__(self, responses: list[BrowserResult]) -> None:
        self.responses = responses
        self.calls: list[str] = []

    def fetch(self, url: str) -> BrowserResult:
        self.calls.append(url)
        return self.responses.pop(0)


def _result(status: int, content: str) -> BrowserResult:
    return BrowserResult(
        ok=status < 400,
        action=BrowserActionType.FETCH,
        url=None,
        status=status,
        content=content,
    )


@pytest.fixture
def checker() -> RobotsChecker:
    return RobotsChecker()


def test_invalid_url_returns_false(checker: RobotsChecker) -> None:
    allowed, reason = checker.can_fetch("not-a-url")
    assert allowed is False


def test_missing_robots_txt_allows_all(checker: RobotsChecker) -> None:
    browser = FakeBrowser([_result(404, "")])
    checker = RobotsChecker(browser=browser)
    allowed, reason = checker.can_fetch("https://example.com/page")
    assert allowed is True
    assert "no robots.txt" in reason


def test_disallowed_path_blocks(checker: RobotsChecker) -> None:
    robot_text = "User-agent: *\nDisallow: /private/"
    browser = FakeBrowser([_result(200, robot_text)])
    checker = RobotsChecker(browser=browser)
    allowed, reason = checker.can_fetch("https://example.com/private/x")
    assert allowed is False
    assert "disallows" in reason


def test_allowed_path_passes(checker: RobotsChecker) -> None:
    robot_text = "User-agent: *\nDisallow: /private/\nAllow: /public/"
    browser = FakeBrowser([_result(200, robot_text)])
    checker = RobotsChecker(browser=browser)
    allowed, reason = checker.can_fetch("https://example.com/public/x")
    assert allowed is True
    assert "allows" in reason


def test_cache_reuses_fetched_robots(checker: RobotsChecker) -> None:
    robot_text = "User-agent: *\nDisallow: /private/"
    browser = FakeBrowser([_result(200, robot_text)])
    checker = RobotsChecker(browser=browser)

    checker.can_fetch("https://example.com/private/1")
    checker.can_fetch("https://example.com/private/2")
    assert len(browser.calls) == 1
