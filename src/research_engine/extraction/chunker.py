"""Split long full text into overlapping chunks for map-reduce extraction."""

from __future__ import annotations


class Chunker:
    """Character-based splitter with overlap, preferring paragraph boundaries."""

    def __init__(self, max_chars: int = 24000, overlap: int = 1000) -> None:
        if max_chars <= 0:
            raise ValueError("max_chars must be positive")
        if not 0 <= overlap < max_chars:
            raise ValueError("overlap must be >= 0 and < max_chars")
        self.max_chars = max_chars
        self.overlap = overlap

    def split(self, text: str) -> list[str]:
        """Return chunks; a short text is returned as a single chunk."""
        if len(text) <= self.max_chars:
            return [text] if text else []

        chunks: list[str] = []
        start = 0
        n = len(text)
        while start < n:
            end = min(start + self.max_chars, n)
            # Prefer to break at a paragraph boundary within the last 20%.
            if end < n:
                window = text.rfind("\n\n", start + int(self.max_chars * 0.8), end)
                if window != -1:
                    end = window
            chunks.append(text[start:end])
            if end >= n:
                break
            start = max(end - self.overlap, start + 1)
        return chunks


def _demo() -> None:
    c = Chunker(max_chars=100, overlap=20)
    text = "para one.\n\n" + ("x" * 250)
    parts = c.split(text)
    assert len(parts) > 1, "long text should split"
    assert all(len(p) <= 100 for p in parts), "chunks respect max_chars"
    assert c.split("short") == ["short"], "short text is one chunk"
    assert c.split("") == [], "empty text yields no chunks"
    print("chunker demo ok:", [len(p) for p in parts])


if __name__ == "__main__":
    _demo()
