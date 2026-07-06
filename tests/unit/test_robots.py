"""Unit tests for robots.txt enforcement."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from research_engine.browser.robots import RobotsChecker


class FakeResponse:
    def __init__(self, status_code: int, text: str = "") -> None:
        self.status_code = status_code
        self.text = text

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise RuntimeError("HTTP error")


class FakeClient:
    def __init__(self, responses: list[FakeResponse]) -> None:
        self.responses = responses
        self.calls: list[str] = []

    def get(self, url: str) -> FakeResponse:
        self.calls.append(url)
        return self.responses.pop(0)

    def __enter__(self) -> FakeClient:
        return self

    def __exit__(self, *args: object) -> None:
        pass


@pytest.fixture
def checker() -> RobotsChecker:
    return RobotsChecker()


def test_invalid_url_returns_false(checker: RobotsChecker, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("httpx.Client", lambda **kwargs: MagicMock())
    allowed, reason = checker.can_fetch("not-a-url")
    assert allowed is False


def test_missing_robots_txt_allows_all(checker: RobotsChecker, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "httpx.Client",
        lambda **kwargs: FakeClient([FakeResponse(404, "")]),
    )
    allowed, reason = checker.can_fetch("https://example.com/page")
    assert allowed is True
    assert "no robots.txt" in reason


def test_disallowed_path_blocks(checker: RobotsChecker, monkeypatch: pytest.MonkeyPatch) -> None:
    robot_text = "User-agent: *\nDisallow: /private/"
    monkeypatch.setattr(
        "httpx.Client",
        lambda **kwargs: FakeClient([FakeResponse(200, robot_text)]),
    )
    allowed, reason = checker.can_fetch("https://example.com/private/x")
    assert allowed is False
    assert "disallows" in reason


def test_allowed_path_passes(checker: RobotsChecker, monkeypatch: pytest.MonkeyPatch) -> None:
    robot_text = "User-agent: *\nDisallow: /private/\nAllow: /public/"
    monkeypatch.setattr(
        "httpx.Client",
        lambda **kwargs: FakeClient([FakeResponse(200, robot_text)]),
    )
    allowed, reason = checker.can_fetch("https://example.com/public/x")
    assert allowed is True
    assert "allows" in reason


def test_cache_reuses_fetched_robots(checker: RobotsChecker, monkeypatch: pytest.MonkeyPatch) -> None:
    robot_text = "User-agent: *\nDisallow: /private/"
    fake = FakeClient([FakeResponse(200, robot_text)])
    monkeypatch.setattr("httpx.Client", lambda **kwargs: fake)

    checker.can_fetch("https://example.com/private/1")
    checker.can_fetch("https://example.com/private/2")
    assert len(fake.calls) == 1
