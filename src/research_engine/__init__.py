"""Research Engine — model-agnostic locally-driven research apparatus."""

__version__ = "0.1.0"


def _use_os_trust_store() -> None:
    """Trust the OS certificate store for all TLS.

    Corporate TLS-inspection proxies inject a root CA present in the OS store
    but not in certifi, which otherwise breaks every HTTPS discovery source with
    CERTIFICATE_VERIFY_FAILED. truststore routes verification through the OS
    store so discovery/resolution actually work. Best-effort: absent truststore
    or on failure, fall back to the default (certifi) behavior.
    """
    try:
        import truststore

        truststore.inject_into_ssl()
    except Exception:  # noqa: BLE001 - never block import on trust-store setup
        pass


_use_os_trust_store()
