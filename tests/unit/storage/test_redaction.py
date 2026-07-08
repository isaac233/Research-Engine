"""Unit tests for shared redaction helpers."""

from __future__ import annotations

from research_engine.storage._redaction import (
    redact_meta,
    redact_payload,
    redact_secrets,
    redact_url,
)


def test_redact_payload_redacts_dict_values_with_sensitive_keys() -> None:
    payload = {
        "api_key": "abcdef0123456789",
        "Authorization": "Bearer secret-token-value",
        "token": "super-secret",
        "safe": "visible",
        "nested": {"password": "MySuperSecret123"},
    }
    redacted = redact_payload(payload)
    assert redacted["api_key"] == "[REDACTED]"
    assert redacted["Authorization"] == "[REDACTED]"
    assert redacted["token"] == "[REDACTED]"
    assert redacted["safe"] == "visible"
    # Non-sensitive outer keys keep their structure; sensitive inner keys are redacted.
    assert redacted["nested"]["password"] == "[REDACTED]"


def test_redact_meta_redacts_sensitive_json_keys() -> None:
    meta = {
        "client_id": "public-id",
        "client_secret": "should-be-hidden",
        "plain": "ok",
    }
    redacted = redact_meta(meta)
    assert redacted["client_id"] == "[REDACTED]"
    assert redacted["client_secret"] == "[REDACTED]"
    assert redacted["plain"] == "ok"


def test_redact_meta_redacts_non_string_sensitive_values() -> None:
    meta = {
        "api_key": 12345678,
        "token": ["abcdef0123456789"],
        "secret": {"nested": "value"},
        "plain": True,
    }
    redacted = redact_meta(meta)
    assert redacted["api_key"] == "[REDACTED]"
    assert redacted["token"] == "[REDACTED]"
    assert redacted["secret"] == "[REDACTED]"
    assert redacted["plain"] is True


def test_redact_secrets_keeps_short_and_safe_strings() -> None:
    assert redact_secrets("hello world") == "hello world"
    assert "[REDACTED]" in redact_secrets("api_key=abcdef0123456789")


def test_redact_url_strips_credentials_and_sensitive_params() -> None:
    url = "https://user:pass@api.example.com/papers?api_key=secret&token=xyz&safe=visible"
    redacted = redact_url(url)
    assert "user:pass@" not in redacted
    assert "api_key=[REDACTED]" in redacted
    assert "token=[REDACTED]" in redacted
    assert "safe=visible" in redacted
