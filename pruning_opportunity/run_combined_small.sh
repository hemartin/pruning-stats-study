#!/usr/bin/env bash
# Combined small-scale ClickBench experiment (1M rows) with the merged selective binary
# (3-gram statistics + predicate cache + row-id range check) and the merge verification.
#   1) merge verification on the persisted db/small/clickbench.db (run.py, 1 thread, counters + hashes):
#      all flags off (vs. the stock binary's rowidexp/stock_count) and PRUNING_ROWID_SKIP=1 (vs. rowidexp/on_count)
#   2) counting passes (phase4.py, 1 thread, one session per config: ingest, q01..q43 cold, q01..q43 warm)
#   3) 8-thread result checks (2 passes): baseline, rowid, all
#   4) timing: 8 threads, --rounds 4 (round 1 cold, rounds 2-4 warm -> median of 3), 1 session per config
#   5) harness/combined_aggregate.py -> results/small/phase4/combined/
# Resumable (finished queries are skipped).
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$HERE"
PY=../.venv/bin/python
SEL=../duckdb/build/selective/duckdb
CLEAN="env -u PRUNING_STATS_COLUMNS -u PRUNING_PREDICATE_CACHE -u PRUNING_ROWID_SKIP -u PRUNING_STATS_BUILD_ON_LOAD -u PRUNING_STATS_TIMING"
NG="--columns hits.URL:ngram:2000,hits.Title:ngram:2000"

# 1) merge verification (persisted DB)
R="harness/run.py --scale small --setups clickbench --memory-limit 3GB --binary $SEL --count --hash --threads 1"
$CLEAN $PY $R --label combined/sel_off_count
$CLEAN PRUNING_ROWID_SKIP=1 $PY $R --label combined/sel_rowid_count

# 2) counting passes
B="harness/phase4.py run --scale small --groups clickbench --memory-limit 1500MB --binary $SEL"
C="$B --mode count --passes 2"
$CLEAN $PY $C --config baseline_cmb
$CLEAN $PY $C --config cmb_ng2000 $NG
$CLEAN $PY $C --config cmb_predcache --predicate-cache 1
$CLEAN $PY $C --config cmb_rowid --rowid-skip
$CLEAN $PY $C --config cmb_ng2000_rowid $NG --rowid-skip
$CLEAN $PY $C --config cmb_all $NG --predicate-cache 1 --rowid-skip

# 3) 8-thread result checks
K="$B --mode check --threads 8 --passes 2"
$CLEAN $PY $K --config baseline_cmb_t8
$CLEAN $PY $K --config cmb_rowid_t8 --rowid-skip
$CLEAN $PY $K --config cmb_all_t8 $NG --predicate-cache 1 --rowid-skip

# 4) timing (noisy: shared machine)
T="$B --mode time --threads 8 --rounds 4 --sessions 1"
$CLEAN $PY $T --config baseline_cmb_time
$CLEAN $PY $T --config cmb_ng2000_time $NG
$CLEAN $PY $T --config cmb_predcache_time --predicate-cache 1
$CLEAN $PY $T --config cmb_rowid_time --rowid-skip
$CLEAN $PY $T --config cmb_ng2000_rowid_time $NG --rowid-skip
$CLEAN $PY $T --config cmb_all_time $NG --predicate-cache 1 --rowid-skip

# 5) tables
$PY harness/combined_aggregate.py
