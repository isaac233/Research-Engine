"""PDF to Markdown conversion with corruption detection and fallback."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass(frozen=True, slots=True)
class PDFConversionResult:
    """Outcome of converting a PDF to Markdown."""

    markdown: str
    ok: bool
    tool: str
    error: str | None = None
    original_path: str | None = None
    fallback_path: str | None = None
    meta: dict[str, Any] = field(default_factory=dict)


class PDFConverter:
    """Convert PDF files to Markdown, keeping originals on failure."""

    def __init__(self, dpi: int = 200) -> None:
        self.dpi = dpi

    def convert(self, pdf_path: Path | str, output_dir: Path | str | None = None) -> PDFConversionResult:
        """Convert a PDF to Markdown.

        Tries pdfplumber first, then pypdf. If both fail, returns an empty result
        marked as failed but preserves the original path so callers can keep it.
        """
        pdf_path = Path(pdf_path)
        if not pdf_path.exists():
            return PDFConversionResult(
                markdown="",
                ok=False,
                tool="none",
                error=f"PDF not found: {pdf_path}",
                original_path=str(pdf_path),
            )

        output_dir = Path(output_dir) if output_dir else pdf_path.parent
        output_dir.mkdir(parents=True, exist_ok=True)

        result = self._try_pdfplumber(pdf_path)
        if result.ok:
            return result

        result = self._try_pypdf(pdf_path)
        if result.ok:
            return result

        return PDFConversionResult(
            markdown="",
            ok=False,
            tool="none",
            error=result.error,
            original_path=str(pdf_path),
            fallback_path=str(pdf_path),
            meta={"tried": ["pdfplumber", "pypdf"]},
        )

    def _try_pdfplumber(self, pdf_path: Path) -> PDFConversionResult:
        try:
            import pdfplumber
        except ImportError:
            return PDFConversionResult(
                markdown="",
                ok=False,
                tool="pdfplumber",
                error="pdfplumber not installed",
            )

        try:
            with pdfplumber.open(pdf_path) as pdf:
                pages: list[str] = []
                for i, page in enumerate(pdf.pages):
                    text = page.extract_text()
                    if text:
                        pages.append(f"## Page {i + 1}\n\n{text.strip()}")
                markdown = "\n\n".join(pages)
                return PDFConversionResult(
                    markdown=markdown,
                    ok=bool(markdown.strip()),
                    tool="pdfplumber",
                    original_path=str(pdf_path),
                    meta={"pages": len(pages)},
                )
        except Exception as exc:  # noqa: BLE001
            return PDFConversionResult(
                markdown="",
                ok=False,
                tool="pdfplumber",
                error=f"pdfplumber failed: {exc}",
                original_path=str(pdf_path),
            )

    def _try_pypdf(self, pdf_path: Path) -> PDFConversionResult:
        try:
            from pypdf import PdfReader
        except ImportError:
            return PDFConversionResult(
                markdown="",
                ok=False,
                tool="pypdf",
                error="pypdf not installed",
            )

        try:
            reader = PdfReader(str(pdf_path))
            pages: list[str] = []
            for i, page in enumerate(reader.pages):
                text = page.extract_text()
                if text:
                    pages.append(f"## Page {i + 1}\n\n{text.strip()}")
            markdown = "\n\n".join(pages)
            return PDFConversionResult(
                markdown=markdown,
                ok=bool(markdown.strip()),
                tool="pypdf",
                original_path=str(pdf_path),
                meta={"pages": len(pages)},
            )
        except Exception as exc:  # noqa: BLE001
            return PDFConversionResult(
                markdown="",
                ok=False,
                tool="pypdf",
                error=f"pypdf failed: {exc}",
                original_path=str(pdf_path),
            )
