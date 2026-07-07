# Discovery

Discovery turns a research plan into a ranked set of candidate sources. It is
responsible for breadth, deduplication, and traceability.

## Pipeline

```
Plan → Queries → Source adapters → Raw results → Deduplication → Snowballing → Ranked candidates
```

The `DiscoveryPipeline` is the main entry point. It runs source adapters in
parallel, deduplicates by normalized DOI/arXiv ID/URL, then performs citation
snowballing and full-text resolution.

## Source adapters

| Adapter | Sources | Key capability |
|---|---|---|
| `SemanticScholarAdapter` | papers, citations | citation graph, PDF links |
| `CrossrefAdapter` | DOI metadata | publisher, license, reference lists |
| `OpenAlexAdapter` | open scholarly graph | institutions, concepts |
| `ArxivAdapter` | arXiv preprints | category, abstract, PDF |
| `SerpAdapter` | general web search | query routing, snippet extraction |
| `WebCrawlAdapter` | URL discovery | sitemap/map + targeted scrape |

Each adapter returns a `DiscoveryResult` with `Paper` or `WebPage` objects and
source-specific metadata. Adapters never call the network directly; they use the
`AIBrowser`.

## Deduplication

- Normalized DOI, arXiv ID, and URL host+path are canonical identifiers.
- `CleanupJanitor` removes duplicate artifact files by SHA-256.
- `SourceCache` deduplicates upstream API calls.

## Snowballing

- Forward snowball: collect papers that cite a seed hit.
- Backward snowball: collect references from a seed hit's bibliography.
- Iteration stops when the candidate pool stabilizes or the configured budget
  is exhausted.

## Full-text resolution

The `DiscoveryPipeline` resolves full-text URLs through Unpaywall, arXiv PDF,
OpenAlex OA locations, and publisher HTML. Resolution results are cached and
adversarially checked before extraction.
