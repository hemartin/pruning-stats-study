#!/usr/bin/env bash
# Reload ClickBench single-threaded (the 6-thread load produced 17,556 partitions instead of ~12,207 full
# 8,192-row ones) and redo its counting pass. The old DB and results are kept as *_misaligned.
cd "$(dirname "${BASH_SOURCE[0]}")"
L=results/raw/large
while [ ! -f $L/DONE4 ]; do sleep 60; done
mkdir -p db/large/misaligned $L/count_misaligned
mv db/large/clickbench.db* db/large/misaligned/ 2>/dev/null
mv $L/count/clickbench $L/count_misaligned/ 2>/dev/null
../.venv/bin/python harness/build_db.py --scale large --dbs clickbench --load-threads 1 --memory-limit 6GB --clickbench-csv "$(pwd)/../hits.csv" > $L/db_clickbench_st.log 2>&1
../.venv/bin/python harness/run.py --scale large --count --label count --timeout 7200 --batch 5 --progress --threads 8 --memory-limit 6GB --setups clickbench > $L/run_clickbench_st.log 2>&1
../.venv/bin/python harness/aggregate.py --scale large > $L/aggregate.log 2>&1
echo "ALL DONE $(date)" > $L/DONE5
