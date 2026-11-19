#!/usr/bin/env python3
"""Prepare the small-scale input data under data/small/:

  micro/<dataset>.csv     symlinks to the 10M-row CSVs of the pruning-log worktree (header time,data)
  tpch/<table>.csv        TPC-H SF1   (dbgen of the tpch extension, exported with header)
  tpcds/<table>.csv       TPC-DS SF1  (dsdgen of the tpcds extension, exported with header)
  clickbench/hits.csv     first 1,000,000 lines of the repo-root hits.csv

The column order of the generated tables is checked against the DDL of the experiment SQL files (COPY maps CSV
columns by position).
"""
import argparse
import os
import re
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common  # noqa: E402

MICRO_SRC = os.path.join(os.path.dirname(common.REPO_DIR), "pruning-stats-study-pruning-log", "pruning_analysis",
                         "data")


def ddl_columns(create):
    m = re.match(r"\s*CREATE\s+TABLE\s+(\w+)\s*\((.*)\)\s*;?\s*$", create, flags=re.S | re.I)
    body = m.group(2)
    cols, depth, cur = [], 0, ""
    for ch in body:
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
        if ch == "," and depth == 0:
            cols.append(cur.strip())
            cur = ""
        else:
            cur += ch
    if cur.strip():
        cols.append(cur.strip())
    return m.group(1), [c.split()[0] for c in cols]


def gen_tpc(binary, bench, sf, out_dir):
    creates, _, _ = common.parse_experiment_file(
        os.path.join(common.SQL_DIR, "established", "sql_queries_%s.sql" % bench))
    tables = [ddl_columns(c) for c in creates]
    os.makedirs(out_dir, exist_ok=True)
    if all(os.path.exists(os.path.join(out_dir, t + ".csv")) for t, _ in tables):
        print("%s: CSVs exist" % bench)
        return
    gen = "CALL dbgen(sf=%s);" % sf if bench == "tpch" else "CALL dsdgen(sf=%s);" % sf
    sql = ["SET memory_limit='6GB';", gen, ".mode csv"]
    for t, cols in tables:
        sql.append("SELECT '%s', string_agg(column_name, '|' ORDER BY column_index) FROM duckdb_columns() "
                   "WHERE table_name = '%s';" % (t, t))
    for t, cols in tables:
        sql.append("COPY %s TO %s (FORMAT csv, HEADER, DELIMITER ',');" % (t, common.sql_str(
            os.path.join(out_dir, t + ".csv"))))
    p = subprocess.run([binary, "-bail", ":memory:"], input="\n".join(sql).encode(), stdout=subprocess.PIPE,
                       stderr=subprocess.STDOUT)
    out = p.stdout.decode()
    if p.returncode != 0:
        raise SystemExit(out)
    gen_cols = {}
    for line in out.splitlines():
        parts = line.split(",", 1)
        if len(parts) == 2:
            gen_cols[parts[0]] = parts[1].strip('"').split("|")
    for t, cols in tables:
        if gen_cols.get(t) != cols:
            print("WARNING %s.%s: generated columns %s differ from DDL %s" % (bench, t, gen_cols.get(t), cols))
    print("%s: generated SF%s into %s" % (bench, sf, out_dir))


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--binary", default=common.DEFAULT_BINARY)
    ap.add_argument("--sf", default="1")
    ap.add_argument("--clickbench-lines", type=int, default=1000000)
    args = ap.parse_args()
    ddir = common.data_dir("small")
    micro = os.path.join(ddir, "micro")
    os.makedirs(micro, exist_ok=True)
    for d in common.MICRO_DATASETS:
        dst = os.path.join(micro, d + ".csv")
        if not os.path.exists(dst):
            os.symlink(os.path.join(MICRO_SRC, d + ".csv"), dst)
    gen_tpc(args.binary, "tpch", args.sf, os.path.join(ddir, "tpch"))
    gen_tpc(args.binary, "tpcds", args.sf, os.path.join(ddir, "tpcds"))
    cb = os.path.join(ddir, "clickbench")
    os.makedirs(cb, exist_ok=True)
    dst = os.path.join(cb, "hits.csv")
    if not os.path.exists(dst):
        with open(os.path.join(common.REPO_DIR, "hits.csv"), "rb") as src, open(dst, "wb") as out:
            for i, line in enumerate(src):
                if i >= args.clickbench_lines:
                    break
                out.write(line)
    print("data/small ready")


if __name__ == "__main__":
    main()
