#!/usr/bin/env bash
# Upload the experiment databases (and the small-scale data) to S3, retrying until a sync pass succeeds.
# aws s3 sync only transfers missing/changed files, so re-running resumes an interrupted upload.
#
#   pruning_opportunity/s3_upload_db.sh                       # uses AWS profile "pruning"
#   S3_PROFILE=other BUCKET=s3://... pruning_opportunity/s3_upload_db.sh
#
# Writes a log to $LOG and, on success, the marker file $LOG.DONE.
set -uo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
AWS="${AWS:-$(command -v aws || echo "$HOME/.local/bin/aws")}"
# own variable: AWS_PROFILE is often already set in the shell (e.g. to an SSO profile)
S3_PROFILE="${S3_PROFILE:-pruning}"
BUCKET="${BUCKET:-s3://pruning-opportunity-919341187522-eu-central-1-an}"
PREFIX="${PREFIX:-pruning_opportunity}"
LOG="${LOG:-$HERE/results/raw/s3_upload_db.log}"
MAX_ATTEMPTS="${MAX_ATTEMPTS:-20}"
DIRS=(db/large db/small data/small)
# not needed for the microbenchmark + ClickBench runs: TPC-H/TPC-DS and the superseded multi-threaded loads
EXCLUDES=(--exclude '*.wal' --exclude 'tmp/*' --exclude 'tpch*' --exclude 'tpcds*' --exclude 'misaligned/*')

mkdir -p "$(dirname "$LOG")"
rm -f "$LOG.DONE"
for attempt in $(seq 1 "$MAX_ATTEMPTS"); do
    echo "=== attempt $attempt $(date -Is)" >> "$LOG"
    ok=1
    for d in "${DIRS[@]}"; do
        "$AWS" --profile "$S3_PROFILE" s3 sync "$HERE/$d" "$BUCKET/$PREFIX/$d" "${EXCLUDES[@]}" \
            --no-progress >> "$LOG" 2>&1 || ok=0
    done
    if [ "$ok" = 1 ]; then
        echo "=== done $(date -Is)" >> "$LOG"
        date -Is > "$LOG.DONE"
        exit 0
    fi
    sleep 60
done
echo "=== giving up after $MAX_ATTEMPTS attempts $(date -Is)" >> "$LOG"
exit 1
