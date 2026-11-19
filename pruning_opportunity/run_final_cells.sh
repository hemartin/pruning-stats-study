#!/usr/bin/env bash
# Measure the two derived cells of the Step 4 ClickBench table (1 thread, counts):
#  Q23 (harness q24): trigram@2000 on URL+Title + row-id check, no predicate cache
#  Q19 (harness q20): nullspace@200 on UserID + predicate cache, 2 passes (no earlier query shares its filter)
cd "$(dirname "${BASH_SOURCE[0]}")"
L=results/raw/large
P="../.venv/bin/python harness/phase4.py run --scale large --attach-existing --memory-limit 4GB --binary ../duckdb/build/selective/duckdb --timeout 7200 --ingest-timeout 28800 --max-restarts 2 --groups clickbench --mode count --threads 1 --build-on-load 6"
rc=0
$P --qids q20 --config finalcb_q19_ns_cache --columns hits.UserID:nullspace:200 --predicate-cache 1 --passes 2 >> $L/run_final_cells.log 2>&1 || rc=1
$P --qids q24 --config finalcb_q23_tg_rowid --columns "hits.URL:ngram:2000,hits.Title:ngram:2000" --rowid-skip >> $L/run_final_cells.log 2>&1 || rc=1
echo "rc=$rc $(date)" > $L/DONE_final_cells
