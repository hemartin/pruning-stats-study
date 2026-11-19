#!/usr/bin/env bash
# Small-scale pipeline: 10M-row microbenchmarks, TPC-H SF1, TPC-DS SF1, ClickBench (first 1M rows of hits.csv).
# Every step is resumable: finished databases / queries are skipped when the script is re-run.
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PY="${PY:-$(cd "$HERE/.." && pwd)/.venv/bin/python}"
H="$HERE/harness"
TIMEOUT="${TIMEOUT:-600}"

[ -x "$HERE/stock/duckdb/build/release/duckdb" ] || "$HERE/build_stock.sh"
"$PY" "$H/gen_queries.py"
"$PY" "$H/prepare_small.py"
"$PY" "$H/build_db.py" --scale small
# 1) counting run (results hashed so they can be compared with the run without counting)
"$PY" "$H/run.py" --scale small --count --hash --label count --timeout "$TIMEOUT"
# 2) same binary, counting off, results hashed
"$PY" "$H/run.py" --scale small --hash --label nocount --timeout "$TIMEOUT"
# 3) timing run: counting off, results discarded (.mode trash)
"$PY" "$H/run.py" --scale small --label time --timeout "$TIMEOUT"
# checks and tables
"$PY" "$H/compare_results.py" --scale small --pip
"$PY" "$H/ground_truth.py" --scale small --micro-sample 100
"$PY" "$H/aggregate.py" --scale small
echo "results in $HERE/results/small/"
