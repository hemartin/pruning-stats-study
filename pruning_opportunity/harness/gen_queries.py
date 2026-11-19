#!/usr/bin/env python3
"""Generate corrected cardinality query files (queries/sql_queries_cardinality_<N>.sql).

The original experiments/sql/cardinality/*.sql query user_id values of about 1e19, which never occur in the data
(the generator draws ids from [0, N)). The paper states that the searched values are always present, so these files
draw 1,000 ids uniformly from [0, N) with a fixed seed. The setup statements (SET/ATTACH/USE/CREATE/COPY) are copied
unchanged from the original file so that the files keep the same structure.
"""
import argparse
import os
import random
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import CARDINALITIES, QUERY_DIR, SQL_DIR, split_sql  # noqa: E402


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--n", type=int, default=1000)
    ap.add_argument("--seed", type=int, default=20260101)
    args = ap.parse_args()
    os.makedirs(QUERY_DIR, exist_ok=True)
    for card in CARDINALITIES:
        src = os.path.join(SQL_DIR, "cardinality", "sql_queries_cardinality_%d.sql" % card)
        with open(src) as f:
            stmts = split_sql(f.read())
        header = [s for s in stmts if s.split(None, 1)[0].upper() in ("SET", "ATTACH", "USE", "CREATE", "COPY")]
        rng = random.Random(args.seed + card)
        out = os.path.join(QUERY_DIR, "sql_queries_cardinality_%d.sql" % card)
        with open(out, "w") as f:
            for s in header:
                f.write(s + ";\n")
            for _ in range(args.n):
                f.write("SELECT * FROM sensor_records WHERE user_id = %d;\n" % rng.randrange(card))
        print("wrote", out)


if __name__ == "__main__":
    main()
