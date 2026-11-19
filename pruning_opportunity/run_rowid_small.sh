#!/usr/bin/env bash
# Row-id range check experiment on small ClickBench (1M rows, 123 row groups).
# Binaries: stock (counter patch only) and rowid (counter patch + rowid-range patch, flag PRUNING_ROWID_SKIP).
# Raw output: results/raw/small/rowidexp/<label>/clickbench/{status,pruning}.jsonl  (resumable)
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$HERE"
PY=../.venv/bin/python
STOCK=stock/duckdb/build/release/duckdb
ROWID=rowid/duckdb/build/release/duckdb
TIME_THREADS="${TIME_THREADS:-12}"
R="harness/run.py --scale small --setups clickbench --memory-limit 3GB"

# counting, 1 thread (deterministic counters), with full-result hashes
$PY $R --binary $STOCK --count --hash --threads 1 --label rowidexp/stock_count
env -u PRUNING_ROWID_SKIP $PY $R --binary $ROWID --count --hash --threads 1 --label rowidexp/off_count
PRUNING_ROWID_SKIP=1 $PY $R --binary $ROWID --count --hash --threads 1 --label rowidexp/on_count
# result hashes at 8 threads, no counting, 3 runs each (ties in ORDER BY ... LIMIT are thread-nondeterministic)
for s in "" _b _c; do
  env -u PRUNING_ROWID_SKIP $PY $R --binary $ROWID --hash --threads 8 --label rowidexp/off_hash8$s
  PRUNING_ROWID_SKIP=1 $PY $R --binary $ROWID --hash --threads 8 --label rowidexp/on_hash8$s
done
# timing: no counting, .mode trash, 3 rounds interleaved
for r in 1 2 3; do
  env -u PRUNING_ROWID_SKIP $PY $R --binary $ROWID --threads "$TIME_THREADS" --label rowidexp/time_off_r$r
  PRUNING_ROWID_SKIP=1 $PY $R --binary $ROWID --threads "$TIME_THREADS" --label rowidexp/time_on_r$r
done
$PY harness/rowid_selftest.py --out results/small/phase4/rowid/selftest.json
$PY harness/rowid_aggregate.py
