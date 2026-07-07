# Orchestrator

The orchestrator owns the lifecycle of a single research campaign. It is the
only component that changes campaign state.

## Lifecycle states

```
INIT → PLAN → DISCOVER → SCREEN → EXTRACT → ADVERSARIAL → EVALUATE → DELIVER → FINALIZE
```

Each state transition is logged to the state database and emitted as a progress
update. State transitions are one-way; a retrying campaign restarts from the
earliest failed state rather than mutating history.

## Responsibilities

- Accept a `ResearchRequest` (query + optional scope hints).
- Generate a `ResearchPlan` with ranked questions, source queries, and a
  staged schedule.
- Dispatch discovery, screening, extraction, adversarial, and evaluation in
  sequence.
- Persist intermediate results after every step so crashes can resume.
- Deliver a `CampaignResult` with status, `ResearchBrief`, and artifact paths.
- Surface progress, ETA, and remaining steps on demand.

## Key types

- `Orchestrator` — public API: `start_campaign(request)`, `run_campaign(id)`,
  `status(id)`, `resume_campaign(id)`.
- `Campaign` — immutable state snapshot, identified by UUID.
- `CampaignResult` — final status plus the list of `ResearchBrief` objects.

## Error handling

- Transient failures are retried with exponential backoff using the local
  provider.
- Permanent failures set the campaign state to `FAILED` and record the reason.
- The MCP adapter maps failures to structured JSON with a `recommendation`
  field.
