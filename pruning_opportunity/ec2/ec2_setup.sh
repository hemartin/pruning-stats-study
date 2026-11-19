#!/usr/bin/env bash
# One-time setup of the EC2 timing machine (Ubuntu 24.04, x86_64), run from a checkout of branch ec2-timing:
#
#   git clone -b ec2-timing https://github.com/hemartin/pruning-stats-study.git ~/repo
#   ~/repo/pruning_opportunity/ec2/ec2_setup.sh
#
# Needs AWS credentials that can read the data bucket (instance role, or `aws configure`).
# Steps (each skipped if already done): packages, AWS CLI, databases from S3, stock DuckDB v1.4.4 build (no patch),
# timing build (this checkout's duckdb/ tree), sanity checks. Writes $DATA/setup.log.
#
#   DATA=~/data BUCKET=s3://... JOBS=16 ec2_setup.sh
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO="$(cd "$HERE/../.." && pwd)"
DATA="${DATA:-$HOME/data}"
BUCKET="${BUCKET:-s3://pruning-opportunity-919341187522-eu-central-1-an}"
JOBS="${JOBS:-$(nproc)}"
STOCK="${STOCK:-$HOME/duckdb-stock}"
DBS=(micro_unsorted clickbench)

mkdir -p "$DATA/db/large"
exec > >(tee -a "$DATA/setup.log") 2>&1
echo "=== setup $(date -Is) repo=$REPO data=$DATA jobs=$JOBS"

# 1. packages
if ! command -v ninja >/dev/null || ! command -v cmake >/dev/null || ! command -v g++ >/dev/null; then
    sudo apt-get update -q
    sudo DEBIAN_FRONTEND=noninteractive apt-get install -y -q build-essential cmake ninja-build git python3 \
        unzip curl util-linux
fi

# 2. AWS CLI v2
if ! command -v aws >/dev/null; then
    tmp="$(mktemp -d)"
    curl -sSfL "https://awscli.amazonaws.com/awscli-exe-linux-x86_64.zip" -o "$tmp/awscliv2.zip"
    (cd "$tmp" && unzip -q awscliv2.zip && sudo ./aws/install)
    rm -rf "$tmp"
fi
aws sts get-caller-identity --query Arn --output text

# 3. databases from S3 (size-checked, so an interrupted copy is repeated)
for db in "${DBS[@]}"; do
    for f in "$db.db" "$db.db.json"; do
        src="$BUCKET/pruning_opportunity/db/large/$f"
        remote=$(aws s3 ls "$src" | awk '{print $3}')
        local_size=$(stat -c %s "$DATA/db/large/$f" 2>/dev/null || echo -1)
        if [ "$remote" != "$local_size" ]; then
            echo "copying $src"
            aws s3 cp --only-show-errors "$src" "$DATA/db/large/$f"
        fi
    done
done
ls -la "$DATA/db/large"

# 4. stock DuckDB v1.4.4, unmodified, same build flags as the timing binary
if [ ! -x "$STOCK/build/release/duckdb" ]; then
    [ -d "$STOCK/.git" ] || git clone --depth 1 --branch v1.4.4 https://github.com/duckdb/duckdb "$STOCK"
    (cd "$STOCK" && test -z "$(git status --porcelain)")
    cmake -G Ninja -S "$STOCK" -B "$STOCK/build/release" -DCMAKE_BUILD_TYPE=Release \
        -DOVERRIDE_GIT_DESCRIBE=v1.4.4 -DBUILD_UNITTESTS=FALSE -DBUILD_EXTENSIONS=""
    cmake --build "$STOCK/build/release" --target shell -- -j"$JOBS"
fi

# 5. timing binary from this checkout
if [ ! -x "$REPO/duckdb/build/timing/duckdb" ]; then
    BUILD_NAME=timing JOBS="$JOBS" "$REPO/pruning_opportunity/build_selective.sh"
fi

# 6. sanity checks
for b in "$STOCK/build/release/duckdb" "$REPO/duckdb/build/timing/duckdb"; do
    echo "$b: $("$b" -noheader -list -c "SELECT library_version || ' ' || source_id FROM pragma_version();")"
done
B="$REPO/duckdb/build/timing/duckdb"
"$B" -noheader -list -c "ATTACH '$DATA/db/large/micro_unsorted.db' AS m (READ_ONLY); SELECT 'micro rows', count(*) FROM m.sensor_records;"
"$B" -noheader -list -c "ATTACH '$DATA/db/large/clickbench.db' AS c (READ_ONLY); SELECT 'clickbench rows', count(*) FROM c.hits;"
sudo -n true && echo "passwordless sudo: ok (needed to drop the page cache and for the M2 cgroup)"
echo "=== setup done $(date -Is)"
