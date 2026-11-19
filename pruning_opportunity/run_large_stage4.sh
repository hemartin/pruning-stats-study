#!/usr/bin/env bash
# Rebuild the cardinality databases single-threaded (parallel loading misaligned the 8,192-row partitions with the
# generator's per-partition id subsets) and redo their counting pass. Old DBs/results are kept as *_misaligned.
cd "$(dirname "${BASH_SOURCE[0]}")"
L=results/raw/large
while [ ! -f $L/DONE3 ]; do sleep 60; done
mkdir -p db/large/misaligned $L/count_misaligned
for n in 100 1000 10000 100000; do
  mv db/large/micro_cardinality_$n.db* db/large/misaligned/ 2>/dev/null
  mv $L/count/cardinality_$n $L/count_misaligned/ 2>/dev/null
done
../.venv/bin/python harness/build_db.py --scale large --dbs micro_cardinality_100,micro_cardinality_1000,micro_cardinality_10000,micro_cardinality_100000 --load-threads 1 --memory-limit 6GB > $L/db_cardinality_st.log 2>&1
../.venv/bin/python harness/run.py --scale large --count --label count --timeout 7200 --batch 20 --progress --threads 8 --memory-limit 6GB --sample 5 --setups cardinality_100,cardinality_1000,cardinality_10000,cardinality_100000 > $L/run_cardinality_st.log 2>&1
../.venv/bin/python harness/aggregate.py --scale large > $L/aggregate.log 2>&1
echo "ALL DONE $(date)" > $L/DONE4
