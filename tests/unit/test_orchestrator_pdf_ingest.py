"""W5: PDF ingestion in the react read path — env gating + bytes→text conversion.

The closures (_fetchable_ref / read_fn) live inside _react_plan; the non-trivial logic
(env gate, size cap, convert-or-drop) is extracted to module-level pure helpers tested
here. The flag-off path keeping .pdf dropped is covered by the existing react tests,
which never set the env.
"""

from __future__ import annotations

import research_engine.orchestrator as orch
from research_engine.extraction.pdf_converter import PDFConversionResult


def test_pdf_ingest_disabled_by_default(monkeypatch) -> None:
    monkeypatch.delenv("RESEARCH_ENGINE_PDF_INGEST", raising=False)
    assert orch._pdf_ingest_enabled() is False


def test_pdf_ingest_enabled_via_env(monkeypatch) -> None:
    monkeypatch.setenv("RESEARCH_ENGINE_PDF_INGEST", "1")
    assert orch._pdf_ingest_enabled() is True


def test_pdf_max_bytes_default(monkeypatch) -> None:
    monkeypatch.delenv("RESEARCH_ENGINE_PDF_MAX_BYTES", raising=False)
    assert orch._pdf_max_bytes() == 10_000_000


def test_pdf_max_bytes_from_env(monkeypatch) -> None:
    monkeypatch.setenv("RESEARCH_ENGINE_PDF_MAX_BYTES", "500")
    assert orch._pdf_max_bytes() == 500


def test_pdf_bytes_empty_returns_empty() -> None:
    assert orch._pdf_bytes_to_text(b"", 1000) == ""


def test_pdf_bytes_over_cap_returns_empty() -> None:
    assert orch._pdf_bytes_to_text(b"x" * 100, 10) == ""


def test_pdf_bytes_unparseable_returns_empty() -> None:
    # not a real PDF → pdfplumber+pypdf both fail → convert ok=False → ""
    assert orch._pdf_bytes_to_text(b"definitely not a pdf", 10_000) == ""


def test_pdf_bytes_converted_when_ok(monkeypatch) -> None:
    class FakeConverter:
        def convert_bytes(self, raw: bytes, output_dir=None) -> PDFConversionResult:
            return PDFConversionResult(markdown="# Report\n\nsome text", ok=True, tool="fake")

    monkeypatch.setattr(orch, "PDFConverter", FakeConverter)
    out = orch._pdf_bytes_to_text(b"%PDF-1.4 fake", 10_000)
    assert "some text" in out


def test_pdf_bytes_convert_failure_non_fatal(monkeypatch) -> None:
    class FailingConverter:
        def convert_bytes(self, raw: bytes, output_dir=None) -> PDFConversionResult:
            return PDFConversionResult(markdown="", ok=False, tool="none", error="boom")

    monkeypatch.setattr(orch, "PDFConverter", FailingConverter)
    assert orch._pdf_bytes_to_text(b"%PDF-1.4", 10_000) == ""
