"""The orchestrator's page-bytes fetcher must resolve to a client that actually
fetches — the default browser is an UnblockProbe that only does unblock actions
but wraps a working RawHTTPBrowser at ``.http``.
"""

from __future__ import annotations

from research_engine.browser.unblock_probe import UnblockProbe
from research_engine.orchestrator import _resolve_byte_fetcher


def test_unblockprobe_resolves_to_inner_http() -> None:
    class FakeRaw:
        def fetch_bytes(self, url: str, headers: dict[str, str] | None = None) -> bytes:
            return b"REAL:" + url.encode()

    probe = UnblockProbe(FakeRaw())  # type: ignore[arg-type]
    fetch = _resolve_byte_fetcher(probe)
    assert fetch("http://x") == b"REAL:http://x"


def test_direct_browser_used_as_is() -> None:
    class DirectBrowser:
        def fetch_bytes(self, url: str, headers: dict[str, str] | None = None) -> bytes:
            return b"DIRECT"

    fetch = _resolve_byte_fetcher(DirectBrowser())
    assert fetch("http://y") == b"DIRECT"
