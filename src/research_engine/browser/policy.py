"""Ethical URL policy and SSRF guard."""

from __future__ import annotations

import ipaddress
import re
import socket
from typing import Any
from urllib.parse import unquote, urlparse


def _is_public_ip(ip: ipaddress.IPv4Address | ipaddress.IPv6Address) -> bool:
    """Return True only for globally routable, non-special-use addresses."""
    if not ip.is_global:
        return False
    if ip.is_multicast or ip.is_reserved or ip.is_private or ip.is_loopback:
        return False
    if isinstance(ip, ipaddress.IPv6Address):
        # site-local is deprecated but still returned by some libraries
        if getattr(ip, "is_site_local", False):
            return False
    return True


class URLPolicy:
    """Decide whether a URL is allowed to be fetched."""

    BLOCKED_SCHEMES = {"file", "ftp", "data", "javascript", "chrome", "about"}
    BLOCKED_HOSTS = {"localhost", "127.0.0.1", "::1", "0.0.0.0"}

    def __init__(
        self,
        allow_list: list[str] | None = None,
        trusted_origins: list[str] | None = None,
    ) -> None:
        self.allow_list = {h.lower() for h in (allow_list or [])}
        # Operator-configured endpoints (e.g. a local SearXNG instance) that
        # bypass the localhost/port SSRF checks. Matched on exact
        # (scheme, host, port) — never derived from untrusted content.
        self._trusted_origins: set[tuple[str, str, int | None]] = set()
        for origin in trusted_origins or []:
            parsed = urlparse(origin)
            if parsed.scheme in {"http", "https"} and parsed.hostname:
                self._trusted_origins.add(
                    (parsed.scheme, parsed.hostname.lower(), parsed.port)
                )

    @staticmethod
    def _decode_host(host: str) -> str:
        """Percent-decode a hostname until stable to catch encoded local names."""
        for _ in range(3):
            decoded = unquote(host)
            if decoded == host:
                return decoded
            host = decoded
        return host

    @staticmethod
    def _canonicalize_numeric_host(
        host: str, port: int | None
    ) -> ipaddress.IPv4Address | ipaddress.IPv6Address | None:
        """Return a canonical IP address if ``host`` is a numeric IP literal.

        Uses ``AI_NUMERICHOST`` first so platform-specific shorthand such as
        octal, hex, or integer-encoded IPv4 is normalized before we classify
        it. Falls back to manual parsing for forms the platform does not
        canonicalize.
        """
        try:
            infos = socket.getaddrinfo(host, port or 0, flags=socket.AI_NUMERICHOST)
            for _family, _type, _proto, _canon, sockaddr in infos:
                try:
                    return ipaddress.ip_address(sockaddr[0])
                except ValueError:
                    continue
        except socket.gaierror:
            pass

        # Fallbacks for hex / integer / dotted-shorthand encodings.
        try:
            if host.startswith("0x"):
                return ipaddress.IPv4Address(int(host, 16))
            if re.fullmatch(r"\d+", host):
                return ipaddress.IPv4Address(int(host))
            raw = socket.inet_aton(host)
            return ipaddress.IPv4Address(int.from_bytes(raw, "big"))
        except Exception:
            pass

        if ":" in host:
            try:
                return ipaddress.IPv6Address(host)
            except ValueError:
                pass

        return None

    @staticmethod
    def _host_resolves_to_public_ip(host: str, port: int | None) -> tuple[bool, str]:
        """Return (ok, reason) after resolving the host and requiring *all*
        returned addresses to be public.
        """
        # Numeric literals should already have been canonicalized by ``allow``,
        # but defense-in-depth: treat them as already resolved.
        canonical = URLPolicy._canonicalize_numeric_host(host, port)
        if canonical is not None:
            if _is_public_ip(canonical):
                return True, ""
            return False, f"numeric host {host!r} resolves to a non-public IP"

        try:
            infos = socket.getaddrinfo(host, port or 0)
        except socket.gaierror as exc:
            return False, f"could not resolve host {host!r}: {exc}"

        public_count = 0
        for _family, _type, _proto, _canon, sockaddr in infos:
            addr = sockaddr[0]
            try:
                ip = ipaddress.ip_address(addr)
            except ValueError:
                continue
            if not _is_public_ip(ip):
                return False, f"host {host!r} resolves to a non-public address"
            public_count += 1

        if public_count == 0:
            return False, f"host {host!r} does not resolve to any public IP"
        return True, ""

    def is_trusted_origin(self, url: str) -> bool:
        """True if the URL's (scheme, host, port) matches a trusted origin."""
        try:
            parsed = urlparse(url)
        except ValueError:
            return False
        host = (parsed.hostname or "").lower()
        return (parsed.scheme, host, parsed.port) in self._trusted_origins

    def allow(self, url: str, *, resolve_hosts: bool = False) -> tuple[bool, str]:
        """Return (allowed, reason)."""
        try:
            parsed = urlparse(url)
        except ValueError:
            return False, "unparseable URL"

        if not parsed.scheme or parsed.scheme not in {"http", "https"}:
            return False, f"scheme {parsed.scheme!r} not allowed"

        netloc = parsed.netloc or ""
        if "@" in netloc:
            return False, "URLs with credentials are not allowed"

        host = self._decode_host((parsed.hostname or "").lower())
        if not host:
            return False, "missing host"

        # Trusted origins (operator config, e.g. local SearXNG) bypass the
        # localhost/port checks below — but never the scheme/credential checks.
        if (parsed.scheme, host, parsed.port) in self._trusted_origins:
            return True, "trusted origin"

        # Block non-ASCII / IDNA hostnames unless explicitly allow-listed.
        # This prevents homoglyph attacks (e.g., Cyrillic е vs Latin e).
        if not host.isascii() and host not in self.allow_list:
            return False, "non-ASCII hostname blocked"

        # Restrict to standard web ports before any allow-list short-circuit.
        port = parsed.port
        if port is not None and port not in {80, 443}:
            return False, f"port {port} not allowed"

        # Canonicalize numeric IP literals (hex, octal, integer, dotted) and
        # reject any loopback/private/reserved/link-local/multicast form.
        canonical_ip = self._canonicalize_numeric_host(host, port)
        if canonical_ip is not None:
            if not _is_public_ip(canonical_ip):
                return False, f"non-public numeric host {host} blocked"

        # Not a numeric IP: still block well-known local names.
        if host in self.BLOCKED_HOSTS:
            return False, "localhost/loopback blocked"
        if re.search(r"\blocalhost\b", host) or host.endswith(".local"):
            return False, "local hostname blocked"

        # Allow-list only applies after scheme, port, and host safety checks.
        if host in self.allow_list:
            return True, "explicit allow-list"

        if resolve_hosts:
            ok, reason = self._host_resolves_to_public_ip(host, port)
            if not ok:
                return False, reason

        return True, "allowed"

    def rules_summary(self) -> dict[str, Any]:
        return {
            "blocked_schemes": sorted(self.BLOCKED_SCHEMES),
            "blocked_hosts": sorted(self.BLOCKED_HOSTS),
            "allow_list": sorted(self.allow_list),
            "trusted_origins": sorted(
                f"{scheme}://{host}" + (f":{port}" if port is not None else "")
                for scheme, host, port in self._trusted_origins
            ),
        }
