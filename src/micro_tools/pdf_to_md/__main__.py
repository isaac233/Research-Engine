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
        Path(args.output).write_text(result.markdown, encoding="utf-8")
    else:
        print(result.markdown)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
