"""Unit tests for PDF conversion."""

from __future__ import annotations

from pathlib import Path

from research_engine.extraction.pdf_converter import PDFConverter


def test_missing_pdf_returns_error(tmp_path: Path) -> None:
    converter = PDFConverter()
    result = converter.convert(tmp_path / "missing.pdf")
    assert result.ok is False
    assert "not found" in (result.error or "").lower()


def test_corrupt_pdf_keeps_original(tmp_path: Path) -> None:
    pdf_path = tmp_path / "corrupt.pdf"
    pdf_path.write_bytes(b"not a pdf")
    converter = PDFConverter()
    result = converter.convert(pdf_path)
    assert result.ok is False
    assert result.original_path == str(pdf_path)


def test_convert_bytes_preserves_original(tmp_path: Path) -> None:
    converter = PDFConverter()
    result = converter.convert_bytes(b"not a pdf", output_dir=tmp_path)
    assert result.meta.get("original_bytes_size") == 9
    assert result.meta.get("original_bytes_preserved") is True
