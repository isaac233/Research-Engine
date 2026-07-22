#!/usr/bin/env bash
# V7 entity-wise probe on task 57 (clear entity set: Big Four + Accenture/MBB/IBM/Capgemini).
# Compares to the thematic baselines: baseline_57 (35.20, no window) and t57_v1 (37.82, +V1).
# V7 changes rubric->objectives->searches, so retrieval is LIVE (not frozen); run N>=2.
# Usage: bash scripts/run_v7_probe.sh <label> <entity:0|1>
set -uo pipefail
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"; cd "$REPO_ROOT"
LABEL="${1:-t57_v7_r1}"; ENTITY="${2:-1}"
OUT="bench/out/campaign"; mkdir -p "$OUT"

export OLLAMA_HOST=http://localhost:11444
export JUDGE_KIND=ollama JUDGE_MODEL=kimi-k2.7-code:cloud TASK_ID=57 QUALITY=0.3
export RESEARCH_ENGINE_SERP_ENDPOINT='http://localhost:8080/search?q={query}&format=json'
export RESEARCH_ENGINE_RETRIEVAL_CACHE=1
export RESEARCH_ENGINE_PROFILE=vague
export RESEARCH_ENGINE_REACT_REASONING_TIMEOUT=90
export RESEARCH_ENGINE_MAX_WORKERS=1 RESEARCH_ENGINE_PROGRESS=1 RESEARCH_ENGINE_ITEM_TIMEOUT=120
export RESEARCH_ENGINE_SPAN_WINDOW_SENTENCES=2 RESEARCH_ENGINE_SPAN_WINDOW_CHARS=1024
if [ "$ENTITY" = "1" ]; then
  export RESEARCH_ENGINE_ENTITY_SECTIONS=1
  export RESEARCH_ENGINE_REACT_MAX_ITERS=14   # cover ~9-13 entity objectives
  export RESEARCH_ENGINE_REACT_MAX_PAGES=64   # more pages spread across more objectives
else
  unset RESEARCH_ENGINE_ENTITY_SECTIONS
fi

echo "=== V7 PROBE $LABEL entity=$ENTITY $(date +%H:%M:%S) ==="
python scripts/run_task53_full.py > "$OUT/log_${LABEL}.txt" 2>&1
cp -f bench/out/engine_task57_full.jsonl "$OUT/engine_${LABEL}.jsonl" 2>/dev/null || true
cp -f bench/out/scores_task57_full.jsonl "$OUT/scores_${LABEL}.jsonl" 2>/dev/null || true
python - "$OUT/engine_${LABEL}.jsonl" <<'PY'
import json,re,sys
a=json.loads(open(sys.argv[1],encoding='utf-8').readline()).get('article','')
heads=re.findall(r'^#{1,3} .+',a,re.M)
print("chars=%d sections=%d" % (len(a),len(heads)))
for h in heads: print("  ",h[:70])
PY
echo "=== DONE $LABEL $(date +%H:%M:%S) ==="
