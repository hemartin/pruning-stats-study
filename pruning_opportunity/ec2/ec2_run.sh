#!/usr/bin/env bash
# All timing sessions on the EC2 machine (after ec2_setup.sh), meant to run inside tmux:
#
#   tmux new -s timing '~/repo/pruning_opportunity/ec2/ec2_run.sh'
#
# Runs M1 (all memory), then M2 (2 GB DuckDB / 6 GB cgroup, page cache dropped per session), aggregates, copies the
# results to S3 after every session and at the end, and shuts the instance down (SHUTDOWN=0 to keep it running).
# Resumable: finished sessions are skipped when the script is started again.
#
#   MODES="M1" ONLY=micro SHUTDOWN=0 ec2_run.sh      # a subset
set -uo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO="$(cd "$HERE/../.." && pwd)"
DATA="${DATA:-$HOME/data}"
STOCK="${STOCK:-$HOME/duckdb-stock}"
OUT="${OUT:-$REPO/pruning_opportunity/results/ec2}"
BUCKET="${BUCKET:-s3://pruning-opportunity-919341187522-eu-central-1-an}"
S3_OUT="${S3_OUT:-$BUCKET/pruning_opportunity/results/ec2}"
MODES="${MODES:-M1 M2}"
ONLY="${ONLY:-}"
SHUTDOWN="${SHUTDOWN:-1}"
THREADS="${THREADS:-16}"

mkdir -p "$OUT"
exec > >(tee -a "$OUT/run.log") 2>&1
echo "=== ec2_run $(date -Is) modes=$MODES only=${ONLY:-all} commit=$(git -C "$REPO" rev-parse --short HEAD)"

rc=0
for mode in $MODES; do
    extra=()
    if [ "$mode" = "M2" ]; then
        extra=(--cgroup-runner sudo --require-drop-caches)
    fi
    python3 "$HERE/ec2_timing.py" --mode "$mode" --db-dir "$DATA/db/large" --out "$OUT" \
        --stock-binary "$STOCK/build/release/duckdb" --timing-binary "$REPO/duckdb/build/timing/duckdb" \
        --tmp-dir "$DATA/tmp" --threads "$THREADS" --build-threads "$THREADS" --only "$ONLY" --s3 "$S3_OUT" \
        "${extra[@]}" || rc=1
done
python3 "$HERE/ec2_aggregate.py" "$OUT" || rc=1
aws s3 sync --only-show-errors "$OUT" "$S3_OUT" || rc=1
echo "=== ec2_run done rc=$rc $(date -Is)"
aws s3 cp --only-show-errors "$OUT/run.log" "$S3_OUT/run.log" || true
if [ "$SHUTDOWN" = "1" ]; then
    echo "shutting down in 2 minutes (cancel with: sudo shutdown -c)"
    sudo shutdown -h +2
fi
exit $rc
