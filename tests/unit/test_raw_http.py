"""Unit tests for the raw HTTP browser."""

from __future__ import annotations

import socket

import httpx
import pytest

from research_engine.browser.ai_browser import BrowserAction, BrowserActionType
from research_engine.browser.raw_http import RawHTTPBrowser


class FakeResponse:
    def __init__(
        self,
        status_code: int,
        text: str = "",
        headers: dict[str, str] | None = None,
        url: str = "https://example.com",
        is_redirect: bool = False,
    ) -> None:
        self.status_code = status_code
        self.text = text
        self.headers = httpx.Headers(headers or {})
        self.url = httpx.URL(url)
        self.is_redirect = is_redirect

    @property
    def content(self) -> bytes:
        return self.text.encode("utf-8")


class FakeHTTPClient:
    def __init__(self, responses: list[FakeResponse], **kwargs: object) -> None:
        self.responses = responses
        self.requests: list[dict[str, object]] = []
        self._closed = False

    def request(self, **kwargs: object) -> FakeResponse:
        self.requests.append(kwargs)
        return self.responses.pop(0)

    @property
    def is_closed(self) -> bool:
        return self._closed

    def close(self) -> None:
        self._closed = True

    def __enter__(self) -> FakeHTTPClient:
        return self

    def __exit__(self, *args: object) -> None:
        pass


@pytest.fixture
def browser(monkeypatch: pytest.MonkeyPatch) -> RawHTTPBrowser:
    monkeypatch.setattr("time.sleep", lambda _s: None)
    monkeypatch.setattr(
        "socket.getaddrinfo",
        lambda host, port, *args, **kwargs: [
            (socket.AF_INET, socket.SOCK_STREAM, 0, "", ("93.184.216.34", port or 80))
        ],
    )
    return RawHTTPBrowser()


def make_client(responses: list[FakeResponse]) -> FakeHTTPClient:
    return FakeHTTPClient(responses)


def test_fetch_blocks_policy_violation(browser: RawHTTPBrowser) -> None:
    action = BrowserAction(action=BrowserActionType.FETCH, url="file:///etc/passwd")
    result = browser.act(action)
    assert result.ok is False
    assert "policy" in (result.error or "").lower()


def test_fetch_requires_url(browser: RawHTTPBrowser) -> None:
    action = BrowserAction(action=BrowserActionType.FETCH)
    result = browser.act(action)
    assert result.ok is False
    assert "url" in (result.error or "").lower()


def test_fetch_success(browser: RawHTTPBrowser, monkeypatch: pytest.MonkeyPatch) -> None:
    fake = make_client([FakeResponse(200, "hello", {"Content-Type": "text/html"})])
    monkeypatch.setattr("httpx.Client", lambda **kwargs: fake)

    action = BrowserAction(action=BrowserActionType.FETCH, url="https://example.com")
    result = browser.act(action)
    assert result.ok is True
    assert result.status == 200
    assert result.content == "hello"
    assert result.headers.get("content-type") == "text/html"


def test_fetch_retries_on_500_then_succeeds(browser: RawHTTPBrowser, monkeypatch: pytest.MonkeyPatch) -> None:
    fake = make_client([FakeResponse(500), FakeResponse(200, "ok")])
    monkeypatch.setattr("httpx.Client", lambda **kwargs: fake)

    action = BrowserAction(action=BrowserActionType.FETCH, url="https://example.com")
    result = browser.act(action)
    assert result.ok is True
    assert result.status == 200
    assert len(fake.requests) == 2


def test_fetch_max_retries_exceeded(browser: RawHTTPBrowser, monkeypatch: pytest.MonkeyPatch) -> None:
    fake = make_client([FakeResponse(500), FakeResponse(500), FakeResponse(500), FakeResponse(500)])
    monkeypatch.setattr("httpx.Client", lambda **kwargs: fake)

    action = BrowserAction(action=BrowserActionType.FETCH, url="https://example.com")
    result = browser.act(action)
    assert result.ok is False
    assert "server error" in (result.error or "").lower()


def test_api_action_returns_parsed_result(browser: RawHTTPBrowser, monkeypatch: pytest.MonkeyPatch) -> None:
    fake = make_client([FakeResponse(200, '{"x":1}', {"Content-Type": "application/json"})])
    monkeypatch.setattr("httpx.Client", lambda **kwargs: fake)

    action = BrowserAction(action=BrowserActionType.API, url="https://api.example.com")
    result = browser.act(action)
    assert result.ok is True
    assert result.action == BrowserActionType.API
    assert result.content == '{"x":1}'


def test_unsupported_action_returns_error(browser: RawHTTPBrowser) -> None:
    action = BrowserAction(action=BrowserActionType.CLICK, url="https://example.com")
    result = browser.act(action)
    assert result.ok is False
    assert "not supported" in (result.error or "").lower()


def test_close_shuts_client(browser: RawHTTPBrowser, monkeypatch: pytest.MonkeyPatch) -> None:
    fake = make_client([FakeResponse(200)])
    monkeypatch.setattr("httpx.Client", lambda **kwargs: fake)
    browser._get_client()
    browser.close()
    assert fake.is_closed


def test_httpx_can_decode_advertised_encodings() -> None:
    """Fingerprint headers advertise Accept-Encoding "br"; without the brotli
    decoder installed, httpx silently returns raw compressed bytes."""
    import httpx._decoders as decoders

    assert "br" in decoders.SUPPORTED_DECODERS
