#!/usr/bin/env bash
# Stage 2 of the large-scale counting pass (replaces the query part of run_large_parallel.sh).
# Full-scan-heavy micro setups (unsorted, outliers, cardinality) take 30-90 s per query single-threaded at
# 1B rows, so they run every 5th query (200 of 1,000) with 8 threads; sorted setups run all 1,000 queries.
set -uo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"; cd "$HERE"
PY="$HERE/../.venv/bin/python"; H="$HERE/harness"; L="$HERE/results/raw/large"
run() { "$PY" "$H/run.py" --scale large --count --label count --timeout 7200 --batch 20 --progress "$@"; }
(
run --memory-limit 2GB --threads 8 --sample 5 --setups point_unsorted,point_outliers,range_seconds_unsorted,range_minutes_unsorted,range_hours_unsorted,range_seconds_outliers,range_minutes_outliers,range_hours_outliers,cardinality_100,cardinality_1000,cardinality_10000,cardinality_100000
run --memory-limit 2GB --setups point_sorted,range_seconds_sorted,range_minutes_sorted,range_hours_sorted
) > "$L/run_micro2.log" 2>&1 &
while pgrep -f "build_db.py --scale large" >/dev/null; do sleep 30; done
"$PY" "$H/build_db.py" --scale large --dbs tpch,tpcds,clickbench --load-threads 6 --memory-limit 5GB --clickbench-csv "$HERE/../hits.csv" >> "$L/db_established.log" 2>&1
run --memory-limit 5GB --setups tpch,tpcds,clickbench > "$L/run_established.log" 2>&1
wait
"$PY" "$H/aggregate.py" --scale large > "$L/aggregate.log" 2>&1
echo "ALL DONE $(date)" > "$L/DONE"
