#!/usr/bin/env python3
"""Generate TPC-H CSVs (header, ',' delimiter) with DuckDB's tpch extension, out of core.

The big tables are generated with dbgen(sf, children=C, step=i); each step is written to a part file
(no header) and the parts are concatenated in step order, which keeps dbgen's natural row order
(lineitem/orders ascending by orderkey). nation and region do not depend on the scale factor and are
taken from dbgen(sf=0.01).

Resumable: finished part files and finished final CSVs are skipped; everything is written to *.tmp
and renamed when complete.

Usage: gen_tpch.py --sf 100 --children 500 --workers 2 --out-dir DIR --tmp-dir DIR
"""
import argparse
import multiprocessing as mp
import os
import shutil
import sys
import time

import duckdb

BIG = ["lineitem", "orders", "customer", "part", "partsupp", "supplier"]
SMALL = ["nation", "region"]


def connect(tmp_dir, mem):
    con = duckdb.connect()
    con.execute("LOAD tpch")
    con.execute("SET threads=1")
    con.execute("SET enable_progress_bar=false")
    con.execute(f"SET memory_limit='{mem}'")
    con.execute("SET preserve_insertion_order=true")
    con.execute(f"SET temp_directory='{tmp_dir}'")
    return con


def part_path(parts_dir, table, step):
    return os.path.join(parts_dir, f"{table}.{step:05d}.csv")


def gen_step(args):
    sf, children, step, parts_dir, tmp_dir, mem, tables = args
    if all(os.path.exists(part_path(parts_dir, t, step)) for t in tables):
        return step, 0.0
    t0 = time.time()
    con = connect(tmp_dir, mem)
    con.execute(f"CALL dbgen(sf={sf}, children={children}, step={step})")
    for t in tables:
        final = part_path(parts_dir, t, step)
        if os.path.exists(final):
            continue
        tmp = final + ".tmp"
        con.execute(f"COPY {t} TO '{tmp}' (FORMAT csv, HEADER false, DELIMITER ',')")
        os.rename(tmp, final)
    con.close()
    return step, time.time() - t0


def header(con, table):
    cols = [r[0] for r in con.execute(f"DESCRIBE {table}").fetchall()]
    return ",".join(cols) + "\n"


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--sf", type=float, default=100)
    p.add_argument("--children", type=int, default=500)
    p.add_argument("--workers", type=int, default=2)
    p.add_argument("--mem", default="1500MB", help="memory_limit per worker")
    p.add_argument("--out-dir", required=True)
    p.add_argument("--tmp-dir", required=True)
    a = p.parse_args()
    out = os.path.abspath(a.out_dir)
    parts = os.path.join(os.path.abspath(a.tmp_dir), "tpch_parts")
    spill = os.path.join(os.path.abspath(a.tmp_dir), "tpch_spill")
    os.makedirs(out, exist_ok=True)
    os.makedirs(parts, exist_ok=True)
    os.makedirs(spill, exist_ok=True)
    sfs = int(a.sf) if a.sf == int(a.sf) else a.sf

    # nation / region (scale-factor independent)
    con = duckdb.connect()
    con.execute("LOAD tpch")
    con.execute("CALL dbgen(sf=0.01)")
    for t in SMALL:
        final = os.path.join(out, f"{t}.csv")
        if not os.path.exists(final):
            con.execute(f"COPY {t} TO '{final}.tmp' (FORMAT csv, HEADER true, DELIMITER ',')")
            os.rename(final + ".tmp", final)
    headers = {t: header(con, t) for t in BIG}
    con.close()

    todo_tables = [t for t in BIG if not os.path.exists(os.path.join(out, f"{t}.csv"))]
    if todo_tables:
        t0 = time.time()
        jobs = [(sfs, a.children, s, parts, spill, a.mem, todo_tables) for s in range(a.children)]
        done = 0
        with mp.get_context("spawn").Pool(a.workers, maxtasksperchild=20) as pool:
            for step, dt in pool.imap_unordered(gen_step, jobs):
                done += 1
                if done % 10 == 0 or done == a.children:
                    print(f"[{time.time() - t0:8.0f}s] steps done {done}/{a.children} (last step {step}: {dt:.1f}s)",
                          flush=True)
        print(f"generation finished in {time.time() - t0:.0f}s", flush=True)

        for t in todo_tables:
            final = os.path.join(out, f"{t}.csv")
            tmp = final + ".tmp"
            t1 = time.time()
            with open(tmp, "wb") as f:
                f.write(headers[t].encode())
                for s in range(a.children):
                    with open(part_path(parts, t, s), "rb") as pf:
                        shutil.copyfileobj(pf, f, 64 << 20)
            os.rename(tmp, final)
            for s in range(a.children):
                os.remove(part_path(parts, t, s))
            print(f"{t}.csv concatenated in {time.time() - t1:.0f}s ({os.path.getsize(final) / 1e9:.1f} GB)",
                  flush=True)
    shutil.rmtree(parts, ignore_errors=True)
    shutil.rmtree(spill, ignore_errors=True)
    print("TPC-H done", flush=True)


if __name__ == "__main__":
    sys.exit(main())
