"""SSRF protection helpers: DNS pinning and IP validation."""

from __future__ import annotations

import ipaddress
import socket
from typing import Any
from urllib.parse import urljoin

import httpx


def is_public_ip(ip: ipaddress.IPv4Address | ipaddress.IPv6Address) -> bool:
    """Return True only for globally routable, non-special-use addresses."""
    if not ip.is_global:
        return False
    if isinstance(ip, ipaddress.IPv6Address):
        # site-local is deprecated but still returned by some libraries
        if getattr(ip, "is_site_local", False):
            return False
    return True


def resolve_public_ip(url: str, resolve_hosts: bool = True) -> tuple[str, str]:
    """Resolve a URL host to a public IP and return (ip_str, original_host).

    Raises RuntimeError if the host cannot be resolved or resolves only to
    non-public addresses.
    """
    parsed = httpx.URL(url)
    host = parsed.host
    if not host:
        raise RuntimeError("URL has no host")
    if not resolve_hosts:
        return (host, host)

    try:
        infos = socket.getaddrinfo(host, parsed.port or 0)
    except socket.gaierror as exc:
        raise RuntimeError(f"Could not resolve host {host!r}: {exc}") from exc

    for _family, _type, _proto, _canon, sockaddr in infos:
        addr = sockaddr[0]
        try:
            ip = ipaddress.ip_address(addr)
        except ValueError:
            continue
        if is_public_ip(ip):
            ip_str = f"[{addr}]" if isinstance(ip, ipaddress.IPv6Address) else str(addr)
            return (ip_str, host)

    raise RuntimeError(f"Host {host!r} does not resolve to a public IP")


def _build_pinned_url(original: httpx.URL, ip_str: str, port: int | None) -> httpx.URL:
    """Construct a URL targeting the resolved IP while preserving path/query."""
    scheme = original.scheme
    default_port = 443 if scheme == "https" else 80
    effective_port = port or default_port
    netloc = f"{ip_str}:{effective_port}"
    return httpx.URL(
        url=f"{scheme}://{netloc}{original.path}",
        query=original.query,
    )


def safe_request(
    client: httpx.Client,
    method: str,
    url: str,
    *,
    headers: dict[str, str] | None = None,
    content: bytes | str | None = None,
    resolve_hosts: bool = True,
    max_body_size: int = 50 * 1024 * 1024,
) -> httpx.Response:
    """Issue a request pinned to a pre-validated public IP.

    Sets the Host header and SNI hostname to the original host so TLS
    certificate validation continues to work for HTTPS URLs.
    """
    ip_str, original_host = resolve_public_ip(url, resolve_hosts=resolve_hosts)
    original_url = httpx.URL(url)
    pinned_url = _build_pinned_url(original_url, ip_str, original_url.port)

    # Normalize incoming headers to lowercase, drop any user-supplied Host, and
    # force the correct Host (with non-default port) for virtual-host routing.
    request_headers = {k.lower(): v for k, v in (headers or {}).items()}
    request_headers.pop("host", None)
    host_header = original_host
    default_port = 443 if original_url.scheme == "https" else 80
    if original_url.port and original_url.port != default_port:
        host_header = f"{original_host}:{original_url.port}"
    request_headers["host"] = host_header
    extensions: dict[str, Any] = {"sni_hostname": original_host}

    response = client.request(
        method=method,
        url=pinned_url,
        headers=request_headers,
        content=content,
        extensions=extensions,
        follow_redirects=False,
    )
    content_length = response.headers.get("content-length")
    if content_length is not None and int(content_length) > max_body_size:
        raise RuntimeError("Response exceeds maximum allowed size")
    body = response.content
    if len(body) > max_body_size:
        raise RuntimeError("Response exceeds maximum allowed size")
    return response


def safe_redirect_url(response: httpx.Response, base_url: str) -> str | None:
    """Return the absolute redirect target, if any."""
    if response.is_redirect and "location" in response.headers:
        return urljoin(base_url, response.headers["location"])
    return None
