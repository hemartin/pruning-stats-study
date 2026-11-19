#!/usr/bin/env bash
# Resume after the WSL restart (13:33, Nov 17): ClickBench first (focus), then cardinality.
# 1) ClickBench single-threaded reload (exact 8,192-row partitions) + recount; old DB/results kept as misaligned.
# 2) Rebuild micro_cardinality_100000 single-threaded (partial .building files removed), recount all 4 cardinality
#    setups (run.py resumes finished queries).
cd "$(dirname "${BASH_SOURCE[0]}")"
L=results/raw/large
mkdir -p db/large/misaligned $L/count_misaligned
if [ ! -f $L/DONE6_clickbench ]; then
  mv db/large/clickbench.db db/large/clickbench.db.json db/large/clickbench.build.log db/large/misaligned/ 2>/dev/null
  mv $L/count/clickbench $L/count_misaligned/ 2>/dev/null
  ../.venv/bin/python harness/build_db.py --scale large --dbs clickbench --load-threads 1 --memory-limit 4GB --clickbench-csv "$(pwd)/../hits.csv" > $L/db_clickbench_st.log 2>&1 || exit 1
  ../.venv/bin/python harness/run.py --scale large --count --label count --timeout 7200 --batch 5 --progress --threads 8 --memory-limit 4GB --setups clickbench > $L/run_clickbench_st.log 2>&1
  echo "done $(date)" > $L/DONE6_clickbench
fi
rm -f db/large/micro_cardinality_100000.db.building db/large/micro_cardinality_100000.db.building.wal
../.venv/bin/python harness/build_db.py --scale large --dbs micro_cardinality_100000 --load-threads 1 --memory-limit 4GB > $L/db_cardinality100000_st.log 2>&1 || exit 1
../.venv/bin/python harness/run.py --scale large --count --label count --timeout 7200 --batch 20 --progress --threads 8 --memory-limit 4GB --sample 5 --setups cardinality_100,cardinality_1000,cardinality_10000,cardinality_100000 > $L/run_cardinality_st.log 2>&1
../.venv/bin/python harness/aggregate.py --scale large > $L/aggregate.log 2>&1
echo "ALL DONE $(date)" > $L/DONE6
