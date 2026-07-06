"""CDP/Playwright driver for AI perception."""

from __future__ import annotations

from typing import Any

from playwright.sync_api import Browser, Page, Playwright, sync_playwright

from research_engine.browser.ai_browser import (
    AIBrowser,
    BrowserAction,
    BrowserActionType,
    BrowserResult,
)
from research_engine.browser.fingerprint import FingerprintRotator
from research_engine.browser.policy import URLPolicy
from research_engine.browser.robots import RobotsChecker


class CDPDriver(AIBrowser):
    """Playwright-based headless browser with accessibility-DOM-first perception."""

    name = "cdp"

    def __init__(
        self,
        policy: URLPolicy | None = None,
        robots: RobotsChecker | None = None,
        fingerprints: FingerprintRotator | None = None,
        headless: bool = True,
        timeout: float = 30.0,
    ) -> None:
        self.policy = policy or URLPolicy()
        self.robots = robots or RobotsChecker()
        self.fingerprints = fingerprints or FingerprintRotator()
        self.headless = headless
        self.timeout = timeout
        self._playwright: Playwright | None = None
        self._browser: Browser | None = None

    def act(self, action: BrowserAction) -> BrowserResult:
        if action.action == BrowserActionType.FETCH:
            return self._fetch(action)
        if action.action == BrowserActionType.SNAPSHOT:
            return self._snapshot(action)
        if action.action == BrowserActionType.CLICK:
            return self._click(action)
        if action.action == BrowserActionType.FILL:
            return self._fill(action)
        if action.action == BrowserActionType.EVALUATE:
            return self._evaluate(action)
        return BrowserResult(
            ok=False,
            action=action.action,
            url=action.url,
            status=None,
            content="",
            error=f"Action {action.action.value} not supported by CDPDriver",
        )

    def health(self) -> dict[str, Any]:
        return {"ok": True, "client": "playwright", "headless": self.headless}

    def _fetch(self, action: BrowserAction) -> BrowserResult:
        url = action.url
        if not url:
            return BrowserResult(
                ok=False,
                action=BrowserActionType.FETCH,
                url=None,
                status=None,
                content="",
                error="fetch requires url",
            )
        allowed, reason = self.policy.allow(url)
        if not allowed:
            return BrowserResult(
                ok=False,
                action=BrowserActionType.FETCH,
                url=url,
                status=None,
                content="",
                error=f"URL blocked by policy: {reason}",
            )
        robots_ok, robots_reason = self.robots.can_fetch(url)
        if not robots_ok:
            return BrowserResult(
                ok=False,
                action=BrowserActionType.FETCH,
                url=url,
                status=None,
                content="",
                error=f"robots.txt: {robots_reason}",
            )

        page = self._page()
        try:
            response = page.goto(url, timeout=self.timeout * 1000, wait_until="domcontentloaded")
            status = response.status if response else None
            return BrowserResult(
                ok=status is not None and status < 400,
                action=BrowserActionType.FETCH,
                url=page.url,
                status=status,
                content=page.content(),
                meta={"robots": robots_reason},
            )
        except Exception as exc:  # noqa: BLE001
            return BrowserResult(
                ok=False,
                action=BrowserActionType.FETCH,
                url=url,
                status=None,
                content="",
                error=f"Playwright error: {exc}",
            )

    def _snapshot(self, action: BrowserAction) -> BrowserResult:
        page = self._page()
        try:
            title = page.title()
            text = page.inner_text("body")
            return BrowserResult(
                ok=True,
                action=BrowserActionType.SNAPSHOT,
                url=page.url,
                status=None,
                content=text,
                meta={"title": title},
            )
        except Exception as exc:  # noqa: BLE001
            return BrowserResult(
                ok=False,
                action=BrowserActionType.SNAPSHOT,
                url=page.url,
                status=None,
                content="",
                error=f"Snapshot error: {exc}",
            )

    def _click(self, action: BrowserAction) -> BrowserResult:
        page = self._page()
        selector = action.selector or ""
        try:
            page.click(selector)
            return BrowserResult(
                ok=True,
                action=BrowserActionType.CLICK,
                url=page.url,
                status=None,
                content="",
            )
        except Exception as exc:  # noqa: BLE001
            return BrowserResult(
                ok=False,
                action=BrowserActionType.CLICK,
                url=page.url,
                status=None,
                content="",
                error=f"Click error: {exc}",
            )

    def _fill(self, action: BrowserAction) -> BrowserResult:
        page = self._page()
        selector = action.selector or ""
        value = action.value or ""
        try:
            page.fill(selector, value)
            return BrowserResult(
                ok=True,
                action=BrowserActionType.FILL,
                url=page.url,
                status=None,
                content="",
            )
        except Exception as exc:  # noqa: BLE001
            return BrowserResult(
                ok=False,
                action=BrowserActionType.FILL,
                url=page.url,
                status=None,
                content="",
                error=f"Fill error: {exc}",
            )

    def _evaluate(self, action: BrowserAction) -> BrowserResult:
        page = self._page()
        script = action.script or ""
        try:
            result = page.evaluate(script)
            return BrowserResult(
                ok=True,
                action=BrowserActionType.EVALUATE,
                url=page.url,
                status=None,
                content=str(result),
            )
        except Exception as exc:  # noqa: BLE001
            return BrowserResult(
                ok=False,
                action=BrowserActionType.EVALUATE,
                url=page.url,
                status=None,
                content="",
                error=f"Evaluate error: {exc}",
            )

    def _page(self) -> Page:
        if self._playwright is None:
            self._playwright = sync_playwright().start()
        if self._browser is None:
            self._browser = self._playwright.chromium.launch(headless=self.headless)
        context = self._browser.new_context(
            user_agent=self.fingerprints.next_headers()["User-Agent"],
            viewport={"width": 1920, "height": 1080},
        )
        return context.new_page()

    def close(self) -> None:
        if self._browser:
            self._browser.close()
            self._browser = None
        if self._playwright:
            self._playwright.stop()
            self._playwright = None
