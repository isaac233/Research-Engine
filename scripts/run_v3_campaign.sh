#!/usr/bin/env bash
# V3 measurement campaign (frozen-cache, single-variable) — runs unattended.
#
# Prereq: task-57 baseline already recorded its retrieval cache (record run), and
# the frozen task-53 B0 pages are present in data/cache.db. This script NEVER purges
# the replay cache (RETRIEVAL_CACHE=1 only records-on-miss / replays-on-hit), so the
# frozen pages survive.
#
# Runs (each writes engine_task{ID}_full.jsonl, copied to a labeled artifact):
#   1. t57_v1        — task 57, V1 span window ON  (class-proof of V1 vs the running baseline_57)
#   2-4. t53_v1_r1..3   — task 53, V1 only         (V3 baseline, N=3 for writer noise)
#   5-7. t53_v1v3_r1..3 — task 53, V1 + V3 notes   (V3 treatment, N=3)
set -uo pipefail
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"
OUT="bench/out/campaign"
mkdir -p "$OUT"

export OLLAMA_HOST=http://localhost:11444
export JUDGE_KIND=ollama JUDGE_MODEL=kimi-k2.7-code:cloud QUALITY=0.3
export RESEARCH_ENGINE_SERP_ENDPOINT='http://localhost:8080/search?q={query}&format=json'
export RESEARCH_ENGINE_RETRIEVAL_CACHE=1
export RESEARCH_ENGINE_PROFILE=vague
export RESEARCH_ENGINE_REACT_REASONING_TIMEOUT=90
export RESEARCH_ENGINE_MAX_WORKERS=1
export RESEARCH_ENGINE_PROGRESS=1
export RESEARCH_ENGINE_ITEM_TIMEOUT=120
# V1 (validated exposure lever) ON for every cell — it is the banked baseline now.
export RESEARCH_ENGINE_SPAN_WINDOW_SENTENCES=2
export RESEARCH_ENGINE_SPAN_WINDOW_CHARS=1024

run_cell() {
  local label="$1" task="$2" notes="$3"
  echo "=== CELL $label (task $task notes=$notes) $(date +%H:%M:%S) ==="
  if [ "$notes" = "1" ]; then export RESEARCH_ENGINE_SYNTHESIS_NOTES=1; else unset RESEARCH_ENGINE_SYNTHESIS_NOTES; fi
  TASK_ID="$task" python scripts/run_task53_full.py > "$OUT/log_${label}.txt" 2>&1
  cp -f "bench/out/engine_task${task}_full.jsonl" "$OUT/engine_${label}.jsonl" 2>/dev/null || true
  cp -f "bench/out/scores_task${task}_full.jsonl" "$OUT/scores_${label}.jsonl" 2>/dev/null || true
  echo "=== DONE $label $(date +%H:%M:%S) ==="
}

run_cell t57_v1      57 0
run_cell t53_v1_r1   53 0
run_cell t53_v1_r2   53 0
run_cell t53_v1_r3   53 0
run_cell t53_v1v3_r1 53 1
run_cell t53_v1v3_r2 53 1
run_cell t53_v1v3_r3 53 1
echo "=== CAMPAIGN COMPLETE $(date +%H:%M:%S) ==="
