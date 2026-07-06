# ADR-001 — Language and Storage

## Decision
- Primary implementation language: **Python 3.12+**.
- Campaign state and metadata: **SQLite**.
- Large corpora / embeddings-ready storage: **DuckDB**.
- Source documents: **Markdown first**; raw PDFs kept only when conversion would corrupt.

## Alternatives considered
- TypeScript/Node for the browser layer: rejected because Python has richer scientific/document tooling (pypdf, pdfplumber, DuckDB) and Ollama integration is simpler via HTTP.
- PostgreSQL for state: rejected because SQLite is zero-config and sufficient for a local-first desktop tool.
- Plain JSON files for sources: rejected because DBs compress better and support FTS5/search.

## Load-bearing assumption
Users can install Python 3.12+ and run Ollama locally. If the user base shifts to non-technical end users, a packaged binary or Docker wrapper may be needed.
