"""Unit tests for HTML-to-Markdown conversion."""

from __future__ import annotations

from research_engine.extraction.markdownify import markdownify


def test_extracts_title_and_headings() -> None:
    html = """
    <html><head><title>Page Title</title></head>
    <body>
      <h1>Main Heading</h1>
      <p>First paragraph.</p>
      <h2>Sub Heading</h2>
      <p>Second paragraph.</p>
    </body></html>
    """
    result = markdownify(html)
    assert result.title == "Page Title"
    assert "# Main Heading" in result.markdown
    assert "## Sub Heading" in result.markdown
    assert "First paragraph." in result.markdown
    assert len(result.headings) == 2


def test_converts_links() -> None:
    html = '<p>See <a href="https://example.com">this link</a>.</p>'
    result = markdownify(html)
    assert "[this link](https://example.com)" in result.markdown
    assert ("https://example.com", "this link") in result.links


def test_converts_lists() -> None:
    html = "<ul><li>One</li><li>Two</li></ul>"
    result = markdownify(html)
    assert "- One" in result.markdown
    assert "- Two" in result.markdown


def test_converts_tables() -> None:
    html = "<table><tr><th>A</th><th>B</th></tr><tr><td>1</td><td>2</td></tr></table>"
    result = markdownify(html)
    assert "| A | B |" in result.markdown
    assert "| 1 | 2 |" in result.markdown


def test_drops_noisy_tags() -> None:
    html = "<p>Visible</p><script>alert('hidden');</script><style>.hidden{color:red}</style>"
    result = markdownify(html)
    assert "Visible" in result.markdown
    assert "hidden" not in result.markdown
    assert "color:red" not in result.markdown


def test_caps_oversized_html_input() -> None:
    """A huge page must not freeze the run: input is capped before the regex passes.

    Regression for the collect stall where one multi-MB page hung the DOTALL
    regex passes (pure-CPU, no fetch/Ollama timeout fires). The size cap bounds
    the work so it completes and truncates rather than hanging the batch.
    """
    lead = "<html><body><h1>Big</h1>"
    body = "<p>lorem ipsum dolor sit amet consectetur. </p>" * 200_000  # ~9 MB
    result = markdownify(lead + body + "</body></html>")
    # Completed (didn't hang) and the output reflects capped, not full, input.
    assert result.title == "Big"
    assert result.meta["char_count"] < 3_000_000
