#!/usr/bin/env bash
# ClickBench Q19 (0-based; harness id q20, UserID = c): nullspace@200 and occupancy@200 on hits.UserID, 1 thread, counts.
cd "$(dirname "${BASH_SOURCE[0]}")"
L=results/raw/large
P="../.venv/bin/python harness/phase4.py run --scale large --attach-existing --memory-limit 4GB --binary ../duckdb/build/selective/duckdb --timeout 7200 --ingest-timeout 28800 --max-restarts 2 --groups clickbench --qids q20 --mode count --threads 1 --build-on-load 6"
rc=0
$P --config finalcb_q19_nsuid200 --columns hits.UserID:nullspace:200 >> $L/run_final_q19.log 2>&1 || rc=1
$P --config finalcb_q19_occuid200 --columns hits.UserID:occupancy:200 >> $L/run_final_q19.log 2>&1 || rc=1
echo "rc=$rc $(date)" > $L/DONE_final_q19
