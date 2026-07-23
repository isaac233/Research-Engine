#!/usr/bin/env bash
# Helper to run one task-53 A/B config and log to a unique file.
# Usage from repo root: source scripts/run_task53_ab.sh config_name
set -euo pipefail
CONFIG_NAME="${1:-baseline}"
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

# Purge retrieval replay cache for clean independent recording per config.
# KEEP_CACHE=1 replays the previously-recorded pages instead (frozen-retrieval
# isolation: baseline and a +lever cell then see IDENTICAL pages, so the lever is
# the only variable — collapses the ~±11 N=1 retrieval-noise band to judge noise).
if [ -z "${KEEP_CACHE:-}" ]; then
  python -c "import sqlite3; c=sqlite3.connect('data/cache.db'); c.execute('DELETE FROM serp_replay_cache'); c.execute('DELETE FROM page_replay_cache'); c.commit(); print('purged replay cache')"
else
  python -c "import sqlite3; c=sqlite3.connect('data/cache.db'); print('KEEP_CACHE=1 — replaying frozen cache: serp=%d page=%d' % (c.execute('SELECT COUNT(*) FROM serp_replay_cache').fetchone()[0], c.execute('SELECT COUNT(*) FROM page_replay_cache').fetchone()[0]))"
fi

LOG_FILE="$REPO_ROOT/task53_ab_${CONFIG_NAME}.log"
export OLLAMA_HOST=http://localhost:11444
export RESEARCH_ENGINE_SERP_ENDPOINT='http://localhost:8080/search?q={query}&format=json'
export RESEARCH_ENGINE_PLANNER=react
export RESEARCH_ENGINE_REACT_MAX_PAGES=48
export RESEARCH_ENGINE_REACT_SEEDED_OUTLINE=1
export RESEARCH_ENGINE_REACT_PER_OBJECTIVE_SEARCHES=3
export RESEARCH_ENGINE_REACT_REASONING_TIMEOUT=90
export RESEARCH_ENGINE_WRITER_MAX_SENTENCES=16
export RESEARCH_ENGINE_WRITER_MAX_TOKENS=2400
export RESEARCH_ENGINE_REACT_SKIP_COLLECT=1
export RESEARCH_ENGINE_MAX_WORKERS=1
export RESEARCH_ENGINE_PROGRESS=1
export RESEARCH_ENGINE_REACT_DEBUG=1
export RESEARCH_ENGINE_ITEM_TIMEOUT=120
export RESEARCH_ENGINE_CDP_FALLBACK=1
export RESEARCH_ENGINE_RETRIEVAL_CACHE=1
export RESEARCH_ENGINE_PDF_INGEST=1
export RESEARCH_ENGINE_WAYBACK_FALLBACK=1

# v9 levers toggled per config
case "$CONFIG_NAME" in
  baseline)
    : # no v9 levers
    ;;
  scope)
    export RESEARCH_ENGINE_RUBRIC_SCAFFOLD=1
    export RESEARCH_ENGINE_SCOPING_PASS=1
    export RESEARCH_ENGINE_RUBRIC_CRITIC=1
    ;;
  warp)
    export RESEARCH_ENGINE_RUBRIC_SCAFFOLD=1
    export RESEARCH_ENGINE_SCOPING_PASS=1
    export RESEARCH_ENGINE_RUBRIC_CRITIC=1
    export RESEARCH_ENGINE_WARP_WRITER=1
    export RESEARCH_ENGINE_WARP_ROUNDS=3
    ;;
  ranker)
    export RESEARCH_ENGINE_RUBRIC_SCAFFOLD=1
    export RESEARCH_ENGINE_SCOPING_PASS=1
    export RESEARCH_ENGINE_RUBRIC_CRITIC=1
    export RESEARCH_ENGINE_EVIDENCE_RANKER=1
    ;;
  gap)
    export RESEARCH_ENGINE_RUBRIC_SCAFFOLD=1
    export RESEARCH_ENGINE_SCOPING_PASS=1
    export RESEARCH_ENGINE_RUBRIC_CRITIC=1
    export RESEARCH_ENGINE_EPHEMERAL_GAP=1
    ;;
  tongyi)
    export RESEARCH_ENGINE_RUBRIC_SCAFFOLD=1
    export RESEARCH_ENGINE_SCOPING_PASS=1
    export RESEARCH_ENGINE_RUBRIC_CRITIC=1
    export RESEARCH_ENGINE_REACT_REASONING_LANE=tongyi_dr
    ;;
  stacked)
    export RESEARCH_ENGINE_RUBRIC_SCAFFOLD=1
    export RESEARCH_ENGINE_SCOPING_PASS=1
    export RESEARCH_ENGINE_RUBRIC_CRITIC=1
    export RESEARCH_ENGINE_WARP_WRITER=1
    export RESEARCH_ENGINE_WARP_ROUNDS=3
    export RESEARCH_ENGINE_EPHEMERAL_GAP=1
    export RESEARCH_ENGINE_REACT_REASONING_LANE=tongyi_dr
    export RESEARCH_ENGINE_EVIDENCE_RANKER=1
    ;;
  vague)
    # One switch = the winning `warp` cell (scope R1/R2 + WARP R4). The profile's
    # react/fetchability flags are already set as base env above (setdefault no-op);
    # it newly fills the 5 v9 quality flags. Should reproduce `warp` (RACE ~34).
    export RESEARCH_ENGINE_PROFILE=vague
    ;;
  v1_spanwin)
    # V10 lever V1: sentence-window spans (exposure lever). vague + windowed banking.
    # Run with KEEP_CACHE=1 so it replays the vague B0 pages → pure exposure delta.
    export RESEARCH_ENGINE_PROFILE=vague
    export RESEARCH_ENGINE_SPAN_WINDOW_SENTENCES=2
    export RESEARCH_ENGINE_SPAN_WINDOW_CHARS=1024
    ;;
  v3b_tables)
    # V10 lever V3b: span-cited comparison tables (insight/read). Layered on V1 (the
    # validated winner) so the baseline for this cell is v1_spanwin, not B0.
    export RESEARCH_ENGINE_PROFILE=vague
    export RESEARCH_ENGINE_SPAN_WINDOW_SENTENCES=2
    export RESEARCH_ENGINE_SPAN_WINDOW_CHARS=1024
    export RESEARCH_ENGINE_COMPARISON_TABLES=1
    ;;
  *)
    echo "Unknown config: $CONFIG_NAME" >&2
    exit 1
    ;;
esac

# Archive any stale task53_full outputs so the script runs fresh
mv -f bench/out/engine_task53_full.jsonl "bench/out/engine_task53_full_${CONFIG_NAME}_$(date +%Y%m%d_%H%M%S).jsonl.bak" 2>/dev/null || true
mv -f bench/out/scores_task53_full.jsonl "bench/out/scores_task53_full_${CONFIG_NAME}_$(date +%Y%m%d_%H%M%S).jsonl.bak" 2>/dev/null || true

echo "=== CONFIG: $CONFIG_NAME ===" | tee "$LOG_FILE"
python scripts/run_task53_full.py --judge ollama --judge-model kimi-k2.7-code:cloud --output bench/out 2>&1 | tee -a "$LOG_FILE"

# Copy result files to config-named artifacts
cp bench/out/engine_task53_full.jsonl "bench/out/engine_task53_${CONFIG_NAME}.jsonl"
cp bench/out/scores_task53_full.jsonl "bench/out/scores_task53_${CONFIG_NAME}.jsonl"
echo "=== DONE $CONFIG_NAME ===" | tee -a "$LOG_FILE"
