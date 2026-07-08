# Storage

Storage keeps durable state, caches, and artifacts organized and clean.

## Layout

All data lives under the host project's `data/` directory by default:

```
data/
├── state.db          # campaigns, stages, progress, status history
├── cache.db          # source cache, robots.txt, adapter responses
├── source_memory.db  # catalog of known-good sources and what they provide
├── agent_history.db  # append-only audit log of agent actions
└── cache_files/      # raw downloaded PDFs and HTML
```

Campaign artifacts live under `Research/<campaign-slug>/`.

## Components

- `EngineConfig` — resolves project root, DB paths, and Research/ layout.
- `StateStore` (`CampaignStore`) — SQLite-backed campaign and stage persistence.
- `SourceCache` — upstream call deduplication and TTL eviction.
- `SourceMemory` — searchable catalog of sources discovered by agents. Records
  what information each source provides, how to access it, reliability, topic
  tags, and search hints. Uses SQLite + FTS5 so agents can query prior
  discoveries with natural-language or structured filters.
- `AgentHistory` — append-only audit log of every significant agent action. Each
  record captures who acted, what they did, the target URL/API, request/response
  summary, outcome, reason, evidence links, and related paper keys. Designed for
  accountability and replay.
- `ArtifactManager` — writes, reads, and hashes deliverable files.
- `CleanupJanitor` — end-of-session cleanup: vacuum DBs, remove duplicate
  files by SHA-256, delete expired cache entries.

## Source memory

`SourceMemory.remember(...)` upserts a source using a canonical URL-derived id.
Tags are split into `topic` and `information` kinds for precise filtering, and a
contentless FTS5 index makes URLs, notes, hints, source types, information
types, and topic tags searchable. Reliability scores (0–1) help rank results.

## Agent history

`AgentHistory.record(...)` stores an immutable `AgentHistoryRecord`. Request
headers are automatically redacted before persistence so credentials do not leak
into the audit log. Records support full-text search over action fields and
structured filters (campaign, agent, action type, outcome, source, time range,
etc.). Campaign summaries and exports provide audit-ready views.

## Resilience

- State DB writes happen inside transactions, one per stage transition.
- Cache entries have a TTL and are lazily expired on read.
- The janitor refuses to delete files outside the configured project root.
- If the state DB is locked, operations retry with exponential backoff.
