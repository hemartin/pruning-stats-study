#!/usr/bin/env bash
# Final step 1: single-threaded reload of micro_unsorted (exact 8,192-row partitions); old DB kept as misaligned.
cd "$(dirname "${BASH_SOURCE[0]}")"
L=results/raw/large
mkdir -p db/large/misaligned
[ -f db/large/misaligned/micro_unsorted.db ] || mv db/large/micro_unsorted.db db/large/micro_unsorted.db.json db/large/micro_unsorted.build.log db/large/misaligned/ 2>/dev/null
../.venv/bin/python harness/build_db.py --scale large --dbs micro_unsorted --load-threads 1 --memory-limit 4GB > $L/db_unsorted_st.log 2>&1
rc=$?
echo "rc=$rc $(date)" > $L/DONE_final_s1
