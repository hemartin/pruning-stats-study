#!/usr/bin/env python3
"""Generate TPC-DS CSVs (header, ',' delimiter, NULL = empty unquoted field) with DuckDB's tpcds extension.

dsdgen(sf) runs once into an on-disk database (memory_limit / temp_directory bound the footprint); every
table is then exported with COPY ... TO csv with threads=1 and preserve_insertion_order=true, i.e. in
dsdgen's natural row order. Resumable: the database is kept until all CSVs exist (a marker table records
that dsdgen finished), finished CSVs are skipped, outputs go to *.tmp and are renamed.

Usage: gen_tpcds.py --sf 100 --out-dir DIR --tmp-dir DIR [--mem 3GB --threads 4] [--cleanup]
"""
import argparse
import os
import sys
import time

import duckdb


def log(msg):
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--sf", type=float, default=100)
    p.add_argument("--mem", default="3GB")
    p.add_argument("--threads", type=int, default=4)
    p.add_argument("--out-dir", required=True)
    p.add_argument("--tmp-dir", required=True)
    p.add_argument("--cleanup", action="store_true", help="delete the intermediate database at the end")
    a = p.parse_args()
    out = os.path.abspath(a.out_dir)
    tmp = os.path.abspath(a.tmp_dir)
    os.makedirs(out, exist_ok=True)
    spill = os.path.join(tmp, "tpcds_spill")
    os.makedirs(spill, exist_ok=True)
    sf = int(a.sf) if a.sf == int(a.sf) else a.sf
    db = os.path.join(tmp, f"tpcds_sf{sf}.duckdb")

    con = duckdb.connect(db)
    con.execute("INSTALL tpcds; LOAD tpcds")
    con.execute(f"SET memory_limit='{a.mem}'")
    con.execute(f"SET threads={a.threads}")
    con.execute(f"SET temp_directory='{spill}'")
    con.execute("SET preserve_insertion_order=true")
    con.execute("SET enable_progress_bar=false")
    done = con.execute("SELECT count(*) FROM duckdb_tables() WHERE table_name='_dsdgen_done'").fetchone()[0]
    if not done:
        t0 = time.time()
        log(f"dsdgen(sf={sf}) into {db}")
        con.execute(f"CALL dsdgen(sf={sf}, overwrite=true)")
        con.execute("CHECKPOINT")
        con.execute(f"CREATE TABLE _dsdgen_done AS SELECT {time.time() - t0} AS seconds")
        con.execute("CHECKPOINT")
        log(f"dsdgen finished in {time.time() - t0:.0f}s")
    tables = [r[0] for r in con.execute(
        "SELECT table_name FROM duckdb_tables() WHERE table_name <> '_dsdgen_done' ORDER BY table_name").fetchall()]
    log(f"{len(tables)} tables")
    con.execute("SET threads=1")  # single-threaded export: rows written exactly in storage (insertion) order
    for t in tables:
        final = os.path.join(out, f"{t}.csv")
        if os.path.exists(final):
            continue
        t1 = time.time()
        con.execute(f"COPY {t} TO '{final}.tmp' (FORMAT csv, HEADER true, DELIMITER ',')")
        os.rename(final + ".tmp", final)
        log(f"{t}.csv exported in {time.time() - t1:.0f}s ({os.path.getsize(final) / 1e9:.2f} GB)")
    con.close()
    if a.cleanup:
        os.remove(db)
        if os.path.exists(db + ".wal"):
            os.remove(db + ".wal")
        log("database removed")
    log("TPC-DS done")


if __name__ == "__main__":
    sys.exit(main())
