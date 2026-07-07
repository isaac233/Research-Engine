"""Unit tests for the pdf_to_md micro tool."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from micro_tools.pdf_to_md.__main__ import main  # noqa: TID252


def test_missing_pdf_returns_error(capsys: Any) -> None:
    code = main(["/nonexistent/missing.pdf"])
    assert code == 1
    captured = capsys.readouterr()
    assert "failed" in captured.err.lower() or "not found" in captured.err.lower()


def test_corrupt_pdf_returns_error(tmp_path: Path, capsys: Any) -> None:
    pdf_path = tmp_path / "corrupt.pdf"
    pdf_path.write_bytes(b"not a pdf")
    code = main([str(pdf_path)])
    assert code == 1
