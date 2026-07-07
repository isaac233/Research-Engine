"""CLI entry point: convert a PDF to Markdown and write to stdout or file."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from research_engine.extraction.pdf_converter import PDFConverter  # noqa: TID252


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Convert a PDF to Markdown.")
    parser.add_argument("pdf", help="Path to the PDF file")
    parser.add_argument("-o", "--output", help="Output markdown file (default: stdout)")
    args = parser.parse_args(argv)

    converter = PDFConverter()
    result = converter.convert(args.pdf)

    if not result.ok:
        print(f"Conversion failed: {result.error}", file=sys.stderr)
        return 1

    if args.output:
        try:
            output_path = _safe_output_path(args.output)
        except ValueError as exc:
            print(f"Invalid output path: {exc}", file=sys.stderr)
            return 1
        output_path.write_text(result.markdown, encoding="utf-8")
    else:
        print(result.markdown)

    return 0


def _safe_output_path(output: str) -> Path:
    """Resolve ``output`` relative to cwd and reject directory escapes."""
    cwd = Path.cwd().resolve()
    candidate = (cwd / Path(output)).resolve()
    if not candidate.is_relative_to(cwd):
        raise ValueError(f"output path must be inside {cwd}")
    return candidate


if __name__ == "__main__":
    raise SystemExit(main())
