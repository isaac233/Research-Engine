# Storage

Storage keeps durable state, caches, and artifacts organized and clean.

## Layout

All data lives under the host project's `Research/` directory by default:

```
Research/
├── .state.sqlite          # campaigns, stages, progress, status history
├── .cache.sqlite          # source cache, robots.txt, adapter responses
├── .cache_files/          # raw downloaded PDFs and HTML
└── <campaign-slug>/
    ├── <campaign-slug>_Insights.MD
    ├── evidence_map.json
    └── artifacts/         # extracted text, fetched files
```

## Components

- `EngineConfig` — resolves project root, DB paths, and Research/ layout.
- `StateStore` — SQLite-backed campaign and stage persistence.
- `SourceCache` — upstream call deduplication and TTL eviction.
- `ArtifactManager` — writes, reads, and hashes deliverable files.
- `CleanupJanitor` — end-of-session cleanup: vacuum DBs, remove duplicate
  files by SHA-256, delete expired cache entries.

## Resilience

- State DB writes happen inside transactions, one per stage transition.
- Cache entries have a TTL and are lazily expired on read.
- The janitor refuses to delete files outside the configured project root.
- If the state DB is locked, operations retry with exponential backoff.
