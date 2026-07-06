"""Legitimate fingerprint rotation for polite requests."""

from __future__ import annotations

import random


class FingerprintRotator:
    """Rotate legitimate browser headers and viewports."""

    USER_AGENTS = [
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
    ]

    VIEWPORTS = [
        "1920x1080",
        "1440x900",
        "1366x768",
    ]

    def __init__(self, seed: int | None = None) -> None:
        self.rng = random.Random(seed)

    def next_headers(self) -> dict[str, str]:
        """Return a fresh set of legitimate headers."""
        ua = self.rng.choice(self.USER_AGENTS)
        viewport = self.rng.choice(self.VIEWPORTS)
        return {
            "User-Agent": ua,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.5",
            "Accept-Encoding": "gzip, deflate, br",
            "DNT": "1",
            "Viewport-Width": viewport.split("x")[0],
        }
