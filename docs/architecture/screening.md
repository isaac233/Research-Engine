# Screening

Screening ranks candidate sources against the research plan and decides what
enters the extraction queue.

## Responsibilities

- Parse inclusion/exclusion criteria from the plan.
- Score each candidate on relevance, quality, recency, and accessibility.
- Drop obvious misses before expensive extraction.
- Produce a traceable inclusion record for each kept source.

## Criteria

- `relevance_score` — semantic match to research questions.
- `quality_score` — venue/author/citation signals.
- `recency_score` — publication date relative to the request scope.
- `accessibility_score` — full-text availability and license.

## Flow

```
DiscoveryResult → Screener.score_batch → ScreenedSet → ExtractionQueue
```

The default screener uses deterministic heuristics plus an optional local LLM
call to refine relevance. All scores and decisions are persisted so the result
is auditable.

## Extraction

After screening, the extractor pulls the full text from the browser, converts it
to Markdown, and extracts:

- Title, authors, year, source URL, DOI
- Abstract/summary
- Numbered claims with inline source markers
- Confidence labels (`HIGH`, `MEDIUM`, `LOW`)

Extracted content is stored as `ExtractedSource` objects and passed to the
adversarial stage.
