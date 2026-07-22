#!/usr/bin/env bash
# V8 evidence-depth A/B: V1 + MAX_PAGE_SPANS=32 on the FROZEN task-53 B0 cache, N=3.
# Baseline = V1 (20 spans) already measured this session (mean 34.65).
# Never purges the replay cache (RETRIEVAL_CACHE=1 replays frozen B0 pages).
set -uo pipefail
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"; cd "$REPO_ROOT"
OUT="bench/out/campaign"; mkdir -p "$OUT"

export OLLAMA_HOST=http://localhost:11444
export JUDGE_KIND=ollama JUDGE_MODEL=kimi-k2.7-code:cloud TASK_ID=53 QUALITY=0.3
export RESEARCH_ENGINE_SERP_ENDPOINT='http://localhost:8080/search?q={query}&format=json'
export RESEARCH_ENGINE_RETRIEVAL_CACHE=1
export RESEARCH_ENGINE_PROFILE=vague
export RESEARCH_ENGINE_REACT_REASONING_TIMEOUT=90
export RESEARCH_ENGINE_MAX_WORKERS=1 RESEARCH_ENGINE_PROGRESS=1 RESEARCH_ENGINE_ITEM_TIMEOUT=120
export RESEARCH_ENGINE_SPAN_WINDOW_SENTENCES=2 RESEARCH_ENGINE_SPAN_WINDOW_CHARS=1024
export RESEARCH_ENGINE_MAX_PAGE_SPANS=32   # V8 depth: 20 -> 32

for r in r1 r2 r3; do
  label="t53_v8_${r}"
  echo "=== CELL $label $(date +%H:%M:%S) ==="
  python scripts/run_task53_full.py > "$OUT/log_${label}.txt" 2>&1
  cp -f bench/out/engine_task53_full.jsonl "$OUT/engine_${label}.jsonl" 2>/dev/null || true
  cp -f bench/out/scores_task53_full.jsonl "$OUT/scores_${label}.jsonl" 2>/dev/null || true
  echo "=== DONE $label $(date +%H:%M:%S) ==="
done
echo "=== V8 CAMPAIGN COMPLETE $(date +%H:%M:%S) ==="
