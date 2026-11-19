#!/usr/bin/env bash
# Final step 4: selective binary, statistics built at ATTACH (not persisted), counts only, the same 4x100 unsorted queries
# as step 2 (every 10th). Configs: min/max baseline (selective binary, flags off), occupancy@200, nullspace@200 on timestamp_ms.
cd "$(dirname "${BASH_SOURCE[0]}")"
L=results/raw/large
P="../.venv/bin/python harness/phase4.py run --scale large --attach-existing --memory-limit 4GB --binary ../duckdb/build/selective/duckdb --timeout 7200 --ingest-timeout 28800 --max-restarts 2 --groups micro_unsorted --setups point_unsorted,range_seconds_unsorted,range_minutes_unsorted,range_hours_unsorted --sample 10 --mode count --threads 8"
rc=0
$P --config final_baseline >> $L/run_final_s4.log 2>&1 || rc=1
$P --config final_occts200 --columns sensor_records.timestamp_ms:occupancy:200 --build-on-load 6 >> $L/run_final_s4.log 2>&1 || rc=1
$P --config final_nsts200 --columns sensor_records.timestamp_ms:nullspace:200 --build-on-load 6 >> $L/run_final_s4.log 2>&1 || rc=1
echo "rc=$rc $(date)" > $L/DONE_final_s4
