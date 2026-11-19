#!/usr/bin/env bash
# Build stock DuckDB v1.4.4 with the pruning-counter patch.
#
#   pruning_opportunity/build_stock.sh            # clone (if needed), apply patch (if needed), build
#   JOBS=4 pruning_opportunity/build_stock.sh     # fewer parallel jobs (default 6)
#
# Result: pruning_opportunity/stock/duckdb/build/release/duckdb   (tpch + tpcds extensions built in)
# The binary behaves exactly like stock v1.4.4 unless DUCKDB_PRUNING_STATS=<file> is set.
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SRC="$HERE/stock/duckdb"
PATCH="$HERE/patches/duckdb-v1.4.4-pruning-counters.patch"
JOBS="${JOBS:-6}"

if [ ! -d "$SRC/.git" ]; then
    mkdir -p "$HERE/stock"
    git clone --depth 1 --branch v1.4.4 https://github.com/duckdb/duckdb "$SRC"
fi

cd "$SRC"
if git apply --check "$PATCH" 2>/dev/null; then
    echo "applying $PATCH"
    git apply "$PATCH"
elif git apply --reverse --check "$PATCH" 2>/dev/null; then
    echo "patch already applied"
else
    echo "ERROR: patch neither applies nor is already applied (local modifications?)" >&2
    exit 1
fi

# version string: a shallow clone of the tag yields 'v1.4.4'; enforce it anyway
GEN=ninja BUILD_TPCH=1 BUILD_TPCDS=1 OVERRIDE_GIT_DESCRIBE=v1.4.4 \
    CMAKE_BUILD_PARALLEL_LEVEL="$JOBS" EXTRA_CMAKE_VARIABLES="-DBUILD_UNITTESTS=FALSE" \
    make release

BIN="$SRC/build/release/duckdb"
echo "built $BIN"
"$BIN" -c "SELECT version() AS version, (SELECT count(*) FROM duckdb_extensions() WHERE loaded AND extension_name IN ('tpch','tpcds')) AS tpc_extensions_loaded;"
