#!/usr/bin/env bash
# Depth-stack A/B: V1 + more spans (MAX_PAGE_SPANS=32) + higher writer cap
# (WRITER_MAX_SENTENCES=28 / TOKENS=3600) on the FROZEN task-53 cache, N=2.
# Tests whether adding LENGTH (the biggest measured gap: 21k vs 83k reference)
# lifts RACE, now that the writer output cap is raised so extra spans get written.
# Baseline = V1 (20 spans / 16 sent) mean 34.65 this session. Never purges cache.
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
export RESEARCH_ENGINE_MAX_PAGE_SPANS=32          # V8 depth
export RESEARCH_ENGINE_WRITER_MAX_SENTENCES=28    # raise writer output cap (was 16)
export RESEARCH_ENGINE_WRITER_MAX_TOKENS=3600     # was 2400

for r in r1 r2; do
  label="t53_depthstack_${r}"
  echo "=== CELL $label $(date +%H:%M:%S) ==="
  python scripts/run_task53_full.py > "$OUT/log_${label}.txt" 2>&1
  cp -f bench/out/engine_task53_full.jsonl "$OUT/engine_${label}.jsonl" 2>/dev/null || true
  cp -f bench/out/scores_task53_full.jsonl "$OUT/scores_${label}.jsonl" 2>/dev/null || true
  python -c "import json;print('chars=%d' % len(json.loads(open('$OUT/engine_${label}.jsonl',encoding='utf-8').readline()).get('article','')))" 2>/dev/null || true
  echo "=== DONE $label $(date +%H:%M:%S) ==="
done
echo "=== DEPTHSTACK COMPLETE $(date +%H:%M:%S) ==="
