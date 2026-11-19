#!/usr/bin/env python3
"""Verify the TPC-H / TPC-DS CSVs by loading them with exactly the DDL and COPY statements of the repo's
experiment SQL file (run from --data-root so that the relative 'tpch/<t>.csv' / 'tpcds/<t>.csv' paths resolve).

Checks per table:
  - CSV header == DDL column names (same order)
  - COPY statement succeeds; row count (TPC-H: against the official SF100 counts)
  - TPC-H lineitem/orders: orderkey non-decreasing in file order (streamed)
  - TPC-DS (--ref-db = the dsdgen database): row count, per-column NULL count and per-column
    bit_xor(hash(value::VARCHAR)) equal to the reference table, and the first --order-rows rows are identical
    and in the same order as in the reference table (natural order preserved)
Writes one JSON line per table to --report. The verification database is deleted afterwards.
"""
import argparse
import json
import os
import re
import sys
import time

import duckdb
import numpy as np

TPCH_SF100 = {"lineitem": 600037902, "orders": 150000000, "customer": 15000000, "part": 20000000,
              "partsupp": 80000000, "supplier": 1000000, "nation": 25, "region": 5}


def parse_sql(path):
    ddl, copy = {}, {}
    for line in open(path):
        line = line.strip()
        m = re.match(r"CREATE TABLE (\w+)\((.*)\);+$", line)
        if m:
            ddl[m.group(1)] = line.rstrip(";") + ";"
        m = re.match(r"COPY (\w+) FROM", line)
        if m:
            copy[m.group(1)] = line
    return ddl, copy


def ddl_columns(con, t):
    return [r[0] for r in con.execute(f"DESCRIBE {t}").fetchall()]


def col_summary(con, rel, cols):
    exprs = []
    for c in cols:
        exprs.append(f'count(*) - count("{c}")')
        exprs.append(f'bit_xor(hash("{c}"::VARCHAR))')
    return list(con.execute(f"SELECT count(*), {', '.join(exprs)} FROM {rel}").fetchone())


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--bench", choices=["tpch", "tpcds"], required=True)
    p.add_argument("--sql", required=True)
    p.add_argument("--data-root", required=True)
    p.add_argument("--tmp-dir", required=True)
    p.add_argument("--ref-db")
    p.add_argument("--tables", help="comma-separated subset")
    p.add_argument("--order-rows", type=int, default=200000)
    p.add_argument("--report", required=True)
    p.add_argument("--mem", default="3GB")
    p.add_argument("--threads", type=int, default=4)
    a = p.parse_args()
    a.report = os.path.abspath(a.report)
    ddl, copy = parse_sql(os.path.abspath(a.sql))
    tables = a.tables.split(",") if a.tables else sorted(copy)
    os.makedirs(a.tmp_dir, exist_ok=True)
    vdb = os.path.join(os.path.abspath(a.tmp_dir), f"verify_{a.bench}.duckdb")
    spill = os.path.join(os.path.abspath(a.tmp_dir), f"verify_{a.bench}_spill")
    os.makedirs(spill, exist_ok=True)
    if os.path.exists(vdb):
        os.remove(vdb)
    os.chdir(a.data_root)
    con = duckdb.connect(vdb)
    con.execute(f"SET memory_limit='{a.mem}'")
    con.execute(f"SET threads={a.threads}")
    con.execute(f"SET temp_directory='{spill}'")
    con.execute("SET preserve_insertion_order=true")
    con.execute("SET enable_progress_bar=false")
    if a.ref_db:
        con.execute(f"ATTACH '{os.path.abspath(a.ref_db)}' AS ref (READ_ONLY)")
    allok = True
    for t in tables:
        t0 = time.time()
        r = {"bench": a.bench, "table": t, "errors": []}
        try:
            csv = os.path.join(a.bench, f"{t}.csv")
            r["bytes"] = os.path.getsize(csv)
            con.execute(f"DROP TABLE IF EXISTS {t}")
            con.execute(ddl[t])
            cols = ddl_columns(con, t)
            with open(csv) as f:
                head = f.readline().rstrip("\n").split(",")
            if head != cols:
                r["errors"].append(f"header {head} != DDL columns {cols}")
            con.execute(copy[t])
            n = con.execute(f"SELECT count(*) FROM {t}").fetchone()[0]
            r["rows"] = n
            r["load_seconds"] = round(time.time() - t0)
            if a.bench == "tpch":
                if n != TPCH_SF100.get(t):
                    r["errors"].append(f"row count {n} != SF100 {TPCH_SF100.get(t)}")
                if t in ("lineitem", "orders"):
                    key = "l_orderkey" if t == "lineitem" else "o_orderkey"
                    con.execute("SET threads=1")
                    prev, bad, mn, mx = None, 0, None, None
                    for b in con.sql(f"SELECT {key} FROM {t}").to_arrow_reader(1 << 23):
                        k = b.column(0).to_numpy()
                        bad += int(np.count_nonzero(k[1:] < k[:-1]))
                        if prev is not None and k[0] < prev:
                            bad += 1
                        prev = k[-1]
                        mn = int(k.min()) if mn is None else min(mn, int(k.min()))
                        mx = int(k.max()) if mx is None else max(mx, int(k.max()))
                    con.execute(f"SET threads={a.threads}")
                    r["orderkey_decreases"] = bad
                    r["orderkey_range"] = [mn, mx]
                    if bad:
                        r["errors"].append(f"{key} decreases {bad} times in file order")
            else:
                rcols = [c[0] for c in con.execute(f"DESCRIBE ref.{t}").fetchall()]
                if rcols != cols:
                    r["errors"].append(f"reference columns {rcols} != DDL columns {cols}")
                s_csv = col_summary(con, t, cols)
                s_ref = col_summary(con, f"ref.{t}", rcols)
                r["null_cells"] = int(sum(s_csv[1::2]))
                if s_csv != s_ref:
                    diff = [cols[i // 2] for i in range(len(cols) * 2) if s_csv[1 + i] != s_ref[1 + i]]
                    r["errors"].append(f"content differs from reference (rows {s_csv[0]} vs {s_ref[0]}; "
                                       f"columns {sorted(set(diff))})")
                con.execute("SET threads=1")
                q = ", ".join(f'"{c}"::VARCHAR' for c in cols)
                h1 = con.execute(f"SELECT hash({q}) FROM (SELECT * FROM {t} LIMIT {a.order_rows})").fetchall()
                h2 = con.execute(f"SELECT hash({q}) FROM (SELECT * FROM ref.{t} LIMIT {a.order_rows})").fetchall()
                con.execute(f"SET threads={a.threads}")
                r["order_prefix_rows_checked"] = len(h1)
                if h1 != h2:
                    r["errors"].append("row order of the first rows differs from the reference")
            con.execute(f"DROP TABLE {t}")
            con.execute("CHECKPOINT")
        except Exception as e:  # noqa: BLE001
            r["errors"].append(f"{type(e).__name__}: {e}"[:2000])
        r["ok"] = not r["errors"]
        r["seconds"] = round(time.time() - t0)
        allok &= r["ok"]
        print(json.dumps(r), flush=True)
        with open(a.report, "a") as f:
            f.write(json.dumps(r) + "\n")
    con.close()
    os.remove(vdb)
    if os.path.exists(vdb + ".wal"):
        os.remove(vdb + ".wal")
    print("ALL OK" if allok else "FAILURES", flush=True)
    return 0 if allok else 1


if __name__ == "__main__":
    sys.exit(main())
