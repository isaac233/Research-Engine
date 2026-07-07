# Monitoring

Monitoring gives users and the main AI continuous visibility into a running
campaign.

## What is reported

- `progress_pct` — 0–100, mapped to campaign state.
- `eta_seconds` — estimated time remaining based on moving-average step cost.
- `current_stage` — one of the lifecycle states.
- `remaining_steps` — count and names of states yet to run.
- `sources_found`, `sources_kept`, `claims_verified` — live counters.

## Components

- `CampaignMonitor` — attached to the orchestrator, records stage timestamps
  and step durations.
- `ProgressReporter` — renders `CampaignStatus` as JSON or Markdown.
- `AnomalyDetector` — flags unexpectedly long stages or repeated failures so
  the user can intervene.

## Calibration

ETA calibration uses an exponential moving average of prior stage durations,
with a safety margin. Early campaigns are intentionally conservative; as the
state DB accumulates history, estimates tighten.

## Status query

Both the CLI and the MCP adapter expose `status(campaign_id)`, which returns a
JSON blob suitable for the main AI to read directly.
