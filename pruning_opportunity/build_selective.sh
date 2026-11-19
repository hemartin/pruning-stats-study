#!/usr/bin/env bash
# Build the repository's duckdb/ tree (DuckDB v1.4.4 + pruning counters + runtime-selectable, per-column
# near-optimal pruning statistics) as ONE release binary that serves as baseline and as the new version.
#
#   pruning_opportunity/build_selective.sh                 # configure (once) + build, ninja, -j3
#   JOBS=6 pruning_opportunity/build_selective.sh          # more parallel jobs
#   BUILD_TPC=1 pruning_opportunity/build_selective.sh     # also build in the tpch + tpcds extensions
#
# Result: duckdb/build/selective/duckdb  (reports v1.4.4)
#   * PRUNING_STATS_COLUMNS unset  -> min/max only (baseline configuration)
#   * PRUNING_STATS_COLUMNS="t.c:occupancy:200,..." -> selective statistics for the listed columns
#   * DUCKDB_PRUNING_STATS=<file>  -> pruning counters (JSON lines), see pruning_opportunity/README.md
#   * PRUNING_STATS_TIMING=<file>  -> ingest/query timings (JSON lines)
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SRC="$(cd "$HERE/../duckdb" && pwd)"
BUILD="$SRC/build/selective"
JOBS="${JOBS:-3}"
EXTS=""
if [ "${BUILD_TPC:-0}" = "1" ]; then
    EXTS="tpch;tpcds"
fi

mkdir -p "$BUILD"
if [ ! -f "$BUILD/build.ninja" ]; then
    cmake -G Ninja -S "$SRC" -B "$BUILD" \
        -DCMAKE_BUILD_TYPE=Release \
        -DOVERRIDE_GIT_DESCRIBE=v1.4.4 \
        -DBUILD_UNITTESTS=FALSE \
        -DBUILD_EXTENSIONS="$EXTS"
fi
cmake --build "$BUILD" --target shell -- -j"$JOBS"

BIN="$BUILD/duckdb"
echo "built $BIN"
"$BIN" -c "SELECT version() AS version;"
