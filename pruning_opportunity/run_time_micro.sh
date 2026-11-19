#!/usr/bin/env bash
# Timing, microbenchmark unsorted (1B rows): 20 queries per setup (every 50th of 1,000; a subset of the 100 counted).
# 8 threads, counters off, results discarded, 1 round, 1 session per config. One untimed warm-up query per config
# (point query on a value outside the data, run via --setting before the timed queries). Configs one at a time.
cd "$(dirname "${BASH_SOURCE[0]}")"
L=results/raw/large
W="SELECT count(*) FROM sensor_records WHERE timestamp_ms = 1;"
P="../.venv/bin/python harness/phase4.py run --scale large --attach-existing --memory-limit 5GB --binary ../duckdb/build/selective/duckdb --timeout 7200 --ingest-timeout 28800 --max-restarts 2 --groups micro_unsorted --sample 50 --mode time --threads 8 --rounds 1 --sessions 1"
ALL=point_unsorted,range_seconds_unsorted,range_minutes_unsorted,range_hours_unsorted
rc=0
$P --setups $ALL --setting "$W" --config baseline_time_micro >> $L/run_time_micro.log 2>&1 || rc=1
$P --setups $ALL --setting "$W" --config time_micro_occ200 --columns sensor_records.timestamp_ms:occupancy:200 --build-on-load 6 >> $L/run_time_micro.log 2>&1 || rc=1
$P --setups point_unsorted --setting "$W" --config time_micro_ns200 --columns sensor_records.timestamp_ms:nullspace:200 --build-on-load 6 >> $L/run_time_micro.log 2>&1 || rc=1
echo "rc=$rc $(date)" > $L/DONE_time_micro
