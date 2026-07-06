"""Ethical URL policy and SSRF guard."""

from __future__ import annotations

import ipaddress
import re
from typing import Any
from urllib.parse import urlparse


class URLPolicy:
    """Decide whether a URL is allowed to be fetched."""

    BLOCKED_SCHEMES = {"file", "ftp", "data", "javascript", "chrome", "about"}
    BLOCKED_HOSTS = {"localhost", "127.0.0.1", "::1", "0.0.0.0"}

    def __init__(self, allow_list: list[str] | None = None) -> None:
        self.allow_list = set(allow_list or [])

    def allow(self, url: str) -> tuple[bool, str]:
        """Return (allowed, reason)."""
        try:
            parsed = urlparse(url)
        except ValueError:
            return False, "unparseable URL"

        if not parsed.scheme or parsed.scheme not in {"http", "https"}:
            return False, f"scheme {parsed.scheme!r} not allowed"

        host = (parsed.hostname or "").lower()
        if not host:
            return False, "missing host"

        if host in self.allow_list:
            return True, "explicit allow-list"

        if host in self.BLOCKED_HOSTS:
            return False, "localhost/loopback blocked"

        try:
            ip = ipaddress.ip_address(host)
            if ip.is_private or ip.is_loopback or ip.is_reserved or ip.is_multicast:
                return False, f"private/reserved IP {host} blocked"
        except ValueError:
            # Not an IP; check for localhost-style hostnames.
            if re.search(r"\blocalhost\b", host) or host.endswith(".local"):
                return False, "local hostname blocked"

        return True, "allowed"

    def rules_summary(self) -> dict[str, Any]:
        return {
            "blocked_schemes": sorted(self.BLOCKED_SCHEMES),
            "blocked_hosts": sorted(self.BLOCKED_HOSTS),
            "allow_list": sorted(self.allow_list),
        }
