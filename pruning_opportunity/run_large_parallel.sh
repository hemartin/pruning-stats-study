#!/usr/bin/env bash
# Large-scale counting pass with micro setups split over two streams that run while the TPC/ClickBench
# databases are built. Resumable (build_db.py and run.py skip finished work). Logs: results/raw/large/*.log
set -uo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"; cd "$HERE"
PY="$HERE/../.venv/bin/python"; H="$HERE/harness"; L="$HERE/results/raw/large"; mkdir -p "$L"
TIMEOUT="${TIMEOUT:-7200}"
run() { "$PY" "$H/run.py" --scale large --count --label count --timeout "$TIMEOUT" --batch 20 --progress "$@"; }
"$PY" "$H/gen_queries.py"
"$PY" "$H/build_db.py" --scale large --dbs micro --load-threads 6 > "$L/db_micro.log" 2>&1
run --memory-limit 1500MB --setups point_unsorted,range_seconds_unsorted,cardinality_100,cardinality_10000,point_outliers,range_seconds_outliers,range_minutes_outliers,range_hours_outliers > "$L/run_microA.log" 2>&1 &
run --memory-limit 1500MB --setups range_minutes_unsorted,range_hours_unsorted,cardinality_1000,cardinality_100000,point_sorted,range_seconds_sorted,range_minutes_sorted,range_hours_sorted > "$L/run_microB.log" 2>&1 &
"$PY" "$H/build_db.py" --scale large --dbs tpch,tpcds,clickbench --load-threads 6 --memory-limit 5GB --clickbench-csv "$HERE/../hits.csv" > "$L/db_established.log" 2>&1
run --memory-limit 5GB --setups tpch,tpcds,clickbench > "$L/run_established.log" 2>&1
wait
"$PY" "$H/aggregate.py" --scale large > "$L/aggregate.log" 2>&1
echo "ALL DONE $(date)" > "$L/DONE"
