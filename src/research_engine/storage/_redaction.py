"""Shared redaction and sanitization helpers for storage modules.

Centralizes URL credential stripping, secret redaction in free text, recursive
metadata cleaning, and FTS5 query escaping. Keeping the logic in one place
avoids subtle differences between source memory and agent history.
"""

from __future__ import annotations

import re
import urllib.parse
from typing import Any, overload

# Common URL query parameter names that may carry credentials or session data.
SENSITIVE_URL_PARAMS: set[str] = {
    "api_key",
    "apikey",
    "key",
    "token",
    "secret",
    "password",
    "auth",
    "access_token",
    "refresh_token",
    "id_token",
    "oauth_token",
    "oauth_verifier",
    "client_id",
    "client_secret",
    "code",
    "nonce",
    "session",
    "request_token",
}

# Header names that commonly contain secrets or session identifiers.
SENSITIVE_HEADER_RE: re.Pattern[str] = re.compile(
    r"("
    r"auth(orization)?|cookie|x-api-key|api-key|apikey|x-apikey|x-api-token"
    r"|token|secret|session|set-cookie|proxy-authorization|x-auth-token"
    r"|signature|x-amz-signature|x-amz-security-token|x-requested-token"
    r"|access-token|refresh-token|client-id|client-secret|id-token"
    r"|authorization-code"
    r")",
    re.IGNORECASE,
)

# Keywords that commonly precede a secret value in free text.
_SECRET_KEYWORDS: tuple[str, ...] = (
    "api[_-]?key",
    "apikey",
    "access[_-]?token",
    "refresh[_-]?token",
    "id[_-]?token",
    "oauth[_-]?token",
    "oauth[_-]?verifier",
    "client[_-]?secret",
    "client[_-]?id",
    "token",
    "secret",
    "password",
    "bearer",
    "basic",
    "private[_-]?key",
    "signature",
    "nonce",
    "credential",
    "pwd",
    "passwd",
)

_KEY_VALUE_SECRET_RE: re.Pattern[str] = re.compile(
    rf"(?i)({'|'.join(_SECRET_KEYWORDS)})(\s*[:=]\s*)['\"]?[\w\-/+=.]{{8,}}['\"]?",
)

_BEARER_TOKEN_RE: re.Pattern[str] = re.compile(
    r"(?i)(Bearer\s+)['\"]?[\w\-/+=.]{8,}['\"]?",
)

_BASIC_AUTH_RE: re.Pattern[str] = re.compile(
    r"(?i)(Basic\s+)['\"]?[A-Za-z0-9+/=]{8,}['\"]?",
)


def redact_secrets(text: str) -> str:
    """Remove common secret and credential patterns from free-text fields."""
    if not text:
        return text
    redacted = _KEY_VALUE_SECRET_RE.sub(r"\1\2[REDACTED]", text)
    redacted = _BEARER_TOKEN_RE.sub(r"\1[REDACTED]", redacted)
    redacted = _BASIC_AUTH_RE.sub(r"\1[REDACTED]", redacted)
    return redacted


@overload
def redact_url(url: str) -> str: ...


@overload
def redact_url(url: None) -> None: ...


def redact_url(url: str | None) -> str | None:
    """Strip embedded credentials and sensitive query parameters from a URL."""
    if not url:
        return url
    try:
        parsed = urllib.parse.urlparse(url)
    except ValueError:
        return redact_secrets(url)
    netloc = parsed.hostname or parsed.netloc
    if parsed.port:
        netloc = f"{netloc}:{parsed.port}"
    if parsed.query:
        query_pairs = urllib.parse.parse_qsl(parsed.query, keep_blank_values=True)
        safe_pairs = [
            (k, "[REDACTED]") if k.lower() in SENSITIVE_URL_PARAMS else (k, v)
            for k, v in query_pairs
        ]
        query = urllib.parse.urlencode(safe_pairs, safe="[]")
    else:
        query = ""
    return urllib.parse.urlunparse(
        (parsed.scheme, netloc, parsed.path, parsed.params, query, parsed.fragment)
    )


_SENSITIVE_KEY_RE: re.Pattern[str] = re.compile(
    rf"^({'|'.join(_SECRET_KEYWORDS)})$",
    re.IGNORECASE,
)


def _is_sensitive_key(key: str) -> bool:
    """Return True when a dict key looks like it holds a secret or credential."""
    return bool(_SENSITIVE_KEY_RE.match(key) or SENSITIVE_HEADER_RE.search(key))


def redact_meta(meta: dict[str, Any] | None) -> dict[str, Any]:
    """Recursively redact secrets from string values in a metadata dict.

    Dict keys that look like secret holders have their values replaced with
    ``[REDACTED]`` regardless of the value's content.
    """
    if not isinstance(meta, dict):
        return meta or {}
    redacted: dict[str, Any] = {}
    for key, value in meta.items():
        if _is_sensitive_key(key):
            redacted[key] = "[REDACTED]"
        elif isinstance(value, str):
            redacted[key] = redact_secrets(value)
        elif isinstance(value, list):
            redacted[key] = redact_list(value)
        elif isinstance(value, dict):
            redacted[key] = redact_meta(value)
        else:
            redacted[key] = value
    return redacted


def redact_list(items: list[Any]) -> list[Any]:
    """Redact secrets in strings and recurse into nested containers."""
    result: list[Any] = []
    for item in items:
        if isinstance(item, str):
            result.append(redact_secrets(item))
        elif isinstance(item, list):
            result.append(redact_list(item))
        elif isinstance(item, dict):
            result.append(redact_meta(item))
        else:
            result.append(item)
    return result


def redact_headers(headers: dict[str, str] | None) -> dict[str, str]:
    """Sanitize request headers before storage to avoid leaking secrets."""
    if not headers:
        return {}
    safe: dict[str, str] = {}
    for key, value in headers.items():
        safe[key] = "[REDACTED]" if SENSITIVE_HEADER_RE.search(key) else value
    return safe


def sanitize_fts_query(query: str) -> str | None:
    """Escape an arbitrary user query for safe FTS5 matching.

    Punctuation such as ``.`` or ``-`` is interpreted as FTS5 syntax, so we
    tokenize on alphanumeric characters and OR the tokens together. Returns
    ``None`` when no usable tokens remain.
    """
    tokens = re.findall(r"[a-zA-Z0-9]+", query)
    if not tokens:
        return None
    return " OR ".join(f'"{token}"' for token in tokens)


def redact_payload(value: Any) -> Any:
    """Recursively redact secrets from a JSON-serializable value.

    Useful for sanitizing event-bus payloads and stage results before they are
    persisted. Dict keys that look like secret holders have their values
    redacted regardless of content.
    """
    if isinstance(value, str):
        return redact_secrets(value)
    if isinstance(value, dict):
        return redact_meta(value)
    if isinstance(value, list):
        return redact_list(value)
    return value
