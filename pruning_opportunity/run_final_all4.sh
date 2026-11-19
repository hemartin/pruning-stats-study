#!/usr/bin/env bash
# ClickBench, the 15 queries with wasted reads (0-based Q10-Q14, Q19-Q24, Q26, Q28, Q30, Q31 = harness ids below),
# all Step 2 strategies combined: trigram@2000 on URL+Title, nullspace@200 on UserID, predicate cache, row-id check.
# 1 thread, 2 passes (cold cache, then repeat).
cd "$(dirname "${BASH_SOURCE[0]}")"
L=results/raw/large
Q=q11,q12,q13,q14,q15,q20,q21,q22,q23,q24,q25,q27,q29,q31,q32
../.venv/bin/python harness/phase4.py run --scale large --attach-existing --memory-limit 4GB --binary ../duckdb/build/selective/duckdb \
  --timeout 7200 --ingest-timeout 28800 --max-restarts 2 --groups clickbench --qids $Q --mode count --threads 1 \
  --config finalcb_all4 --columns "hits.URL:ngram:2000,hits.Title:ngram:2000,hits.UserID:nullspace:200" --build-on-load 6 \
  --predicate-cache 1 --rowid-skip --passes 2 >> $L/run_final_all4.log 2>&1
echo "rc=$? $(date)" > $L/DONE_final_all4
