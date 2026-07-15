"""Convert HTML to readable Markdown."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

# Cap HTML fed to the regex passes. A multi-MB page ran the DOTALL passes into
# catastrophic backtracking (pure-CPU, no fetch/Ollama timeout fires) and froze a
# whole collect batch. Truncating bounds the work — real content lives near the
# top, so a 2 MB slice keeps the readable body.
# ponytail: size cap, not a backtracking fix. Adversarial unclosed-tag input can
# still be O(n²) within the cap; upgrade path is a per-item wall-clock timeout in
# util/parallel.py if a pathological page slips through.
_MAX_HTML_CHARS = 2_000_000


@dataclass(frozen=True, slots=True)
class MarkdownifyResult:
    """Result of converting HTML to Markdown."""

    markdown: str
    title: str | None
    links: list[tuple[str, str | None]]
    headings: list[tuple[int, str]]
    meta: dict[str, Any]


def _strip_inline_styles(html: str) -> str:
    """Drop style attributes and tags that complicate text extraction."""
    html = re.sub(r"\s+style=\"[^\"]*\"", "", html, flags=re.IGNORECASE)
    html = re.sub(r"\s+style='[^']*'", "", html, flags=re.IGNORECASE)
    return html


def _extract_title(html: str) -> str | None:
    match = re.search(r"<title>([^<]+)</title>", html, re.IGNORECASE)
    if match:
        return match.group(1).strip()
    match = re.search(r"<h1[^>]*>([^<]+)</h1>", html, re.IGNORECASE)
    if match:
        return match.group(1).strip()
    return None


def _convert_headings(html: str) -> tuple[str, list[tuple[int, str]]]:
    headings: list[tuple[int, str]] = []

    def repl(match: re.Match[str]) -> str:
        level = int(match.group(1))
        text = _clean_text(match.group(2))
        headings.append((level, text))
        return f"{'#' * level} {text}\n\n"

    html = re.sub(r"<h([1-6])[^>]*>(.*?)</h\1>", repl, html, flags=re.IGNORECASE | re.DOTALL)
    return html, headings


def _convert_bold_italic(html: str) -> str:
    html = re.sub(r"<strong\b[^>]*>(.*?)</strong>", r"**\1**", html, flags=re.IGNORECASE | re.DOTALL)
    html = re.sub(r"<b\b[^>]*>(.*?)</b>", r"**\1**", html, flags=re.IGNORECASE | re.DOTALL)
    html = re.sub(r"<em\b[^>]*>(.*?)</em>", r"*\1*", html, flags=re.IGNORECASE | re.DOTALL)
    html = re.sub(r"<i\b[^>]*>(.*?)</i>", r"*\1*", html, flags=re.IGNORECASE | re.DOTALL)
    return html


def _convert_links(html: str) -> tuple[str, list[tuple[str, str | None]]]:
    links: list[tuple[str, str | None]] = []

    def repl(match: re.Match[str]) -> str:
        href = match.group(1)
        text = _clean_text(match.group(2)) if match.group(2) else href
        links.append((href, text or None))
        return f"[{text}]({href})"

    html = re.sub(r"<a\b[^>]*href=\"([^\"]+)\"[^>]*>(.*?)</a>", repl, html, flags=re.IGNORECASE | re.DOTALL)
    html = re.sub(r"<a\b[^>]*href='([^']+)'[^>]*>(.*?)</a>", repl, html, flags=re.IGNORECASE | re.DOTALL)
    return html, links


def _convert_lists(html: str) -> str:
    def process_list(match: re.Match[str]) -> str:
        tag = match.group(1).lower()
        content = match.group(2)
        items = re.findall(r"<li\b[^>]*>(.*?)</li>", content, flags=re.IGNORECASE | re.DOTALL)
        lines: list[str] = []
        for item in items:
            cleaned = _clean_text(item)
            if tag == "ol":
                lines.append(f"1. {cleaned}")
            else:
                lines.append(f"- {cleaned}")
        return "\n".join(lines) + "\n\n"

    html = re.sub(r"<(ol|ul)\b[^>]*>(.*?)</\1>", process_list, html, flags=re.IGNORECASE | re.DOTALL)
    return html


def _convert_tables(html: str) -> str:
    def process_table(match: re.Match[str]) -> str:
        content = match.group(1)
        rows: list[list[str]] = []
        for row_match in re.finditer(r"<tr\b[^>]*>(.*?)</tr>", content, flags=re.IGNORECASE | re.DOTALL):
            cells = re.findall(r"<(?:td|th)\b[^>]*>(.*?)</(?:td|th)>", row_match.group(1), flags=re.IGNORECASE | re.DOTALL)
            rows.append([_clean_text(cell) for cell in cells])
        if not rows:
            return ""
        lines: list[str] = []
        for i, row in enumerate(rows):
            lines.append("| " + " | ".join(row) + " |")
            if i == 0:
                lines.append("| " + " | ".join("---" for _ in row) + " |")
        return "\n".join(lines) + "\n\n"

    html = re.sub(r"<table\b[^>]*>(.*?)</table>", process_table, html, flags=re.IGNORECASE | re.DOTALL)
    return html


def _drop_noisy_tags(html: str) -> str:
    """Remove scripts, styles, nav, header, footer, aside, and SVG content."""
    for tag in ["script", "style", "nav", "header", "footer", "aside", "svg", "noscript"]:
        html = re.sub(rf"<{tag}\b[^>]*>.*?</{tag}>", "", html, flags=re.IGNORECASE | re.DOTALL)
    return html


def _clean_text(text: str) -> str:
    text = re.sub(r"<[^>]+>", "", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def _paragraphs(html: str) -> str:
    """Convert remaining block tags into paragraph breaks and collapse."""
    html = re.sub(r"</?(?:div|section|article|main|body)[^>]*>", "\n\n", html, flags=re.IGNORECASE)
    html = re.sub(r"<br\s*/?>", "\n", html, flags=re.IGNORECASE)
    html = re.sub(r"</p\b[^>]*>", "\n\n", html, flags=re.IGNORECASE)
    html = re.sub(r"</p>", "\n\n", html, flags=re.IGNORECASE)
    html = re.sub(r"<[^>]+>", "", html)
    return html


def _collapse(markdown: str) -> str:
    lines = markdown.splitlines()
    cleaned: list[str] = []
    prev_blank = False
    for line in lines:
        stripped = line.strip()
        if stripped == "":
            if not prev_blank:
                cleaned.append("")
            prev_blank = True
            continue
        cleaned.append(line.rstrip())
        prev_blank = False
    return "\n".join(cleaned).strip()


def markdownify(html: str) -> MarkdownifyResult:
    """Convert raw HTML into Markdown and metadata."""
    if len(html) > _MAX_HTML_CHARS:
        html = html[:_MAX_HTML_CHARS]
    title = _extract_title(html)
    html = _strip_inline_styles(html)
    html = _drop_noisy_tags(html)
    html, headings = _convert_headings(html)
    html = _convert_bold_italic(html)
    html, links = _convert_links(html)
    html = _convert_lists(html)
    html = _convert_tables(html)
    html = _paragraphs(html)
    markdown = _collapse(html)

    return MarkdownifyResult(
        markdown=markdown,
        title=title,
        links=links,
        headings=headings,
        meta={
            "link_count": len(links),
            "heading_count": len(headings),
            "char_count": len(markdown),
        },
    )
