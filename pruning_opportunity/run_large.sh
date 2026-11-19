#!/usr/bin/env bash
# Large-scale pipeline. Expects CSVs in data/large/{micro,tpch,tpcds}/ (micro: <dataset>.csv with header time,data;
# tpch/tpcds: <table>.csv with header) and the full ClickBench hits.csv in the repository root
# (override with CLICKBENCH_CSV=...). Resumable: re-running skips finished databases and queries.
#
#   STEP=db      only build the databases
#   STEP=run     only run the counting pass
#   SETUPS=tpch  restrict the run to setups / benchmarks (comma separated, default all)
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PY="${PY:-$(cd "$HERE/.." && pwd)/.venv/bin/python}"
H="$HERE/harness"
TIMEOUT="${TIMEOUT:-7200}"
SETUPS="${SETUPS:-all}"
STEP="${STEP:-all}"
CB="${CLICKBENCH_CSV:-$HERE/../hits.csv}"

[ -x "$HERE/stock/duckdb/build/release/duckdb" ] || "$HERE/build_stock.sh"
"$PY" "$H/gen_queries.py"
if [ "$STEP" = all ] || [ "$STEP" = db ]; then
    "$PY" "$H/build_db.py" --scale large --clickbench-csv "$CB" ${LOAD_THREADS:+--load-threads "$LOAD_THREADS"}
fi
if [ "$STEP" = all ] || [ "$STEP" = run ]; then
    # counting pass, single thread, results discarded; 1 CLI process per 20 queries
    "$PY" "$H/run.py" --scale large --count --label count --timeout "$TIMEOUT" --batch 20 --setups "$SETUPS" --progress
fi
"$PY" "$H/aggregate.py" --scale large
echo "results in $HERE/results/large/  (optional: $PY $H/ground_truth.py --scale large --micro-sample 50)"
