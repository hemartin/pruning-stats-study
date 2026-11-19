#!/usr/bin/env bash
# Step 4 at full scale (PREPARED, NOT YET RUN): baseline (min/max only) vs. the new version on the persistent
# Phase 1 databases -- observed pruning, statistic build cost, lookup cost on top of min/max, end-to-end time
# (median of 3 runs).
#
#   micro (1B rows, 122,723 row groups; db/large/micro_{unsorted,outliers,sorted}.db):
#       baseline_step4  vs. occts200_step4 (sensor_records.timestamp_ms occupancy@200)
#                       vs. nsts200_step4  (sensor_records.timestamp_ms nullspace@200)
#   ClickBench (100M rows, db/large/clickbench.db = the single-threaded reload of run_large_stage6.sh):
#       baseline_step4cb vs. cbnew_step4 (3-gram ng2000 on hits.URL + hits.Title, predicate cache, row-id range check)
#
# The selective statistics are not persisted in the .db file. Every DuckDB process attaches the database read-only
# (phase4.py --attach-existing) and, for the new version, rebuilds them while ATTACH loads the table
# (PRUNING_STATS_BUILD_ON_LOAD=<threads>: streams the row groups of the selected columns, one row group at a time;
# memory = the statistics + one row group's key buffer per thread). That ATTACH is the "ingest" item of the run:
# ATTACH wall time (new - baseline) = build cost; build CPU / key extraction / data read are in timing.jsonl.
#
# Modes per group and config (one process each, resumable: re-run the script, finished queries are skipped):
#   count  counters (DUCKDB_PRUNING_STATS), COUNT_THREADS threads (default 8 = the Phase 1 large count run),
#          ClickBench with 2 passes (cold + warm predicate cache)
#   time   QUERY_THREADS threads, .mode trash; micro --rounds 3, ClickBench --rounds 4 (round 1 = cold predicate
#          cache, rounds 2-4 = warm: median of 3); one session (= one statistic build) per config
#
# Waits for results/raw/large/DONE6 (run_large_stage6.sh) before starting. Do not run anything else meanwhile.
#
#   nohup pruning_opportunity/run_large_step4.sh > pruning_opportunity/results/raw/large/step4.log 2>&1 &
#   STEPS=clickbench ./run_large_step4.sh          # only ClickBench (STEPS=micro: only micro)
#   SCALE=small SKIP_WAIT=1 MICRO_SAMPLE=100 SORTED_SAMPLE=100 ./run_large_step4.sh   # dry run at small scale
#
# Knobs: MEM (memory_limit, default 5GB), BUILD_THREADS (default 6), COUNT_THREADS (8), QUERY_THREADS (8),
# MICRO_SAMPLE (every k-th query of the unsorted/outliers setups, default 50 = 20 per setup),
# SORTED_SAMPLE (every k-th query of the sorted setups, default 10 = 100 per setup), MICRO_GROUPS,
# MICRO_KINDS (default "occupancy nullspace"), MICRO_LOAD_THREADS (e.g. 1: skip micro DBs not loaded with that many
# threads; NOTE: db/large/micro_{unsorted,outliers,sorted}.db were loaded with 6 threads = 122,723 row groups incl.
# 653 partial ones; the statistics are built for every row group, partial ones included).
#
# Run ClickBench first, without waiting for stage 6:  SKIP_WAIT=1 STEPS=clickbench ./run_large_step4.sh
set -uo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$HERE"
PY=../.venv/bin/python
SCALE="${SCALE:-large}"
MEM="${MEM:-5GB}"
BT="${BUILD_THREADS:-6}"
CT="${COUNT_THREADS:-8}"
QT="${QUERY_THREADS:-8}"
MS="${MICRO_SAMPLE:-50}"
SS="${SORTED_SAMPLE:-10}"
STEPS="${STEPS:-micro clickbench}"
MICRO_GROUPS="${MICRO_GROUPS:-micro_unsorted micro_outliers micro_sorted}"
MICRO_KINDS="${MICRO_KINDS:-occupancy nullspace}"
SEL=../duckdb/build/selective/duckdb
LOG=results/raw/$SCALE/step4
mkdir -p "$LOG"

if [ "$SCALE" = "large" ] && [ -z "${SKIP_WAIT:-}" ]; then
  echo "[$(date +%T)] waiting for results/raw/large/DONE6 ..."
  until [ -f results/raw/large/DONE6 ]; do sleep 300; done
  # the stage-6 job must really be gone (aggregate.py is its last step)
  while pgrep -f run_large_stage6.sh > /dev/null; do sleep 60; done
fi
[ -x "$SEL" ] || { echo "binary $SEL missing (build_selective.sh)"; exit 1; }
"$SEL" -c "SELECT 1" > /dev/null || exit 1

# databases: must exist; ClickBench must be the single-threaded load (exact 8,192-row partitions)
check_db() {  # db expected_load_threads(or '')
  local j="db/$SCALE/$1.db.json"
  [ -f "db/$SCALE/$1.db" ] || { echo "missing db/$SCALE/$1.db"; return 1; }
  local lt
  lt=$($PY -c "import json;print(json.load(open('$j')).get('load_threads'))" 2>/dev/null)
  echo "[$(date +%T)] $1: load_threads=$lt"
  if [ -n "$2" ] && [ "$lt" != "$2" ]; then echo "  $1 was not loaded with $2 thread(s)"; return 1; fi
}

P="$PY harness/phase4.py run --scale $SCALE --attach-existing --memory-limit $MEM --binary $SEL --timeout 7200 --ingest-timeout 28800 --max-restarts 2"
OCC="sensor_records.timestamp_ms:occupancy:200"
NUL="sensor_records.timestamp_ms:nullspace:200"
NG="hits.URL:ngram:2000,hits.Title:ngram:2000"

run() {  # description, command...
  echo "[$(date +%T)] $1"
  shift
  "$@" || echo "[$(date +%T)]   FAILED (exit $?): $*"
}

if [[ " $STEPS " == *" micro "* ]]; then
  for g in $MICRO_GROUPS; do
    check_db "$g" "${MICRO_LOAD_THREADS:-}" || continue
    case "$g" in
      micro_sorted) S="--sample $SS --sample-setups sorted" ;;
      *) S="--sample $MS --sample-setups unsorted,outliers,cardinality" ;;
    esac
    for mode in count time; do
      if [ "$mode" = count ]; then M="--mode count --threads $CT"; else M="--mode time --threads $QT --rounds 3 --sessions 1"; fi
      run "$g $mode baseline" $P --groups "$g" $S $M --config baseline_step4
      for k in $MICRO_KINDS; do
        case "$k" in
          occupancy) run "$g $mode occupancy@200" $P --groups "$g" $S $M --config occts200_step4 --columns "$OCC" --build-on-load "$BT" ;;
          nullspace) run "$g $mode nullspace@200" $P --groups "$g" $S $M --config nsts200_step4 --columns "$NUL" --build-on-load "$BT" ;;
        esac
      done
    done
  done
fi

if [[ " $STEPS " == *" clickbench "* ]]; then
  if check_db clickbench 1; then
    for mode in count time; do
      if [ "$mode" = count ]; then M="--mode count --threads $CT --passes 2"; else M="--mode time --threads $QT --rounds 4 --sessions 1"; fi
      run "clickbench $mode baseline" $P --groups clickbench $M --config baseline_step4cb
      run "clickbench $mode ng2000+predcache+rowid" $P --groups clickbench $M --config cbnew_step4 \
          --columns "$NG" --build-on-load "$BT" --predicate-cache 1 --rowid-skip
    done
  fi
fi

$PY harness/step4_aggregate.py --scale "$SCALE" > "$LOG/aggregate.log" 2>&1 && echo "[$(date +%T)] summary: results/$SCALE/phase4/step4/summary.md"
echo "done $(date)" > "$LOG/DONE"
