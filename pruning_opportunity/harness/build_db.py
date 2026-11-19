#!/usr/bin/env python3
"""Build the persistent DuckDB files db/<scale>/<name>.db from the CSV files in data/<scale>/.

Tables and COPY statements are taken verbatim from the experiment SQL files (experiments/sql/...), only the CSV
path is replaced. As in those files the database is attached with ROW_GROUP_SIZE 8192 and loaded with
SET threads TO 1 by default (keeps row groups aligned to the file order: row group k = rows k*8192 ...);
preserve_insertion_order stays true, memory_limit and temp_directory are set so that large loads spill to
db/tmp instead of running out of memory.

A database is built into <name>.db.building and renamed when complete, so an interrupted build is redone
and a finished one is skipped (use --force to rebuild).
"""
import argparse
import json
import os
import subprocess
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common  # noqa: E402

ALL_DBS = ["micro_" + d for d in common.MICRO_DATASETS] + ["tpch", "tpcds", "clickbench"]


def run_cli(binary, sql, log_path):
    env = dict(os.environ)
    env.pop("DUCKDB_PRUNING_STATS", None)
    with open(log_path, "a") as log:
        log.write("\n==== %s\n%s\n" % (time.strftime("%Y-%m-%d %H:%M:%S"), sql))
        log.flush()
        p = subprocess.run([binary, "-bail", ":memory:"], input=sql.encode(), stdout=subprocess.PIPE,
                           stderr=subprocess.STDOUT, env=env)
        out = p.stdout.decode("utf-8", "replace")
        log.write(out)
    return p.returncode, out


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--scale", required=True)
    ap.add_argument("--dbs", default="all", help="comma-separated: micro, tpch, tpcds, clickbench or db names")
    ap.add_argument("--binary", default=common.DEFAULT_BINARY)
    ap.add_argument("--load-threads", type=int, default=1)
    ap.add_argument("--memory-limit", default="6GB")
    ap.add_argument("--clickbench-csv", default=None, help="override path of hits.csv")
    ap.add_argument("--force", action="store_true")
    args = ap.parse_args()

    wanted = []
    for w in (ALL_DBS if args.dbs == "all" else args.dbs.split(",")):
        w = w.strip()
        if w == "micro":
            wanted += ["micro_" + d for d in common.MICRO_DATASETS]
        elif w in ALL_DBS:
            wanted.append(w)
        else:
            raise SystemExit("unknown db %s" % w)
    defs = common.db_definitions(args.scale, args.clickbench_csv)
    ddir = common.db_dir(args.scale)
    tmp = os.path.join(common.PO_DIR, "db", "tmp")
    os.makedirs(ddir, exist_ok=True)
    os.makedirs(tmp, exist_ok=True)
    for name in wanted:
        creates, loads = defs[name]
        final = os.path.join(ddir, name + ".db")
        if os.path.exists(final) and not args.force:
            print("%s: exists, skipping" % final)
            continue
        missing = [csv for _, csv, _ in loads if not os.path.exists(csv)]
        if missing:
            print("%s: missing CSV files %s, skipping" % (name, missing[:3]))
            continue
        building = final + ".building"
        for f in (building, building + ".wal", final, final + ".wal"):
            if os.path.exists(f):
                os.remove(f)
        sql = ["SET threads TO %d;" % args.load_threads,
               "SET memory_limit = '%s';" % args.memory_limit,
               "SET temp_directory = %s;" % common.sql_str(tmp),
               "SET preserve_insertion_order = true;",
               "ATTACH %s AS db (ROW_GROUP_SIZE 8192);" % common.sql_str(building),
               "USE db;"]
        sql += [c.rstrip(";") + ";" for c in creates]
        sql += [c.rstrip(";") + ";" for _, _, c in loads]
        sql.append("CHECKPOINT;")
        counts = " UNION ALL ".join("SELECT '%s' AS t, count(*) AS n FROM %s" % (t, t) for t, _, _ in loads)
        sql.append(".mode csv")
        sql.append(counts + ";")
        t0 = time.time()
        print("%s: loading %d table(s) ..." % (name, len(loads)), flush=True)
        rc, out = run_cli(args.binary, "\n".join(sql) + "\n", os.path.join(ddir, name + ".build.log"))
        if rc != 0 or "Error" in out:
            print("%s: FAILED (rc=%d), see %s.build.log\n%s" % (name, rc, os.path.join(ddir, name), out[-2000:]))
            continue
        rows = {}
        for line in out.splitlines():
            parts = line.split(",")
            if len(parts) == 2 and parts[1].isdigit():
                rows[parts[0]] = int(parts[1])
        os.rename(building, final)
        if os.path.exists(building + ".wal"):
            os.rename(building + ".wal", final + ".wal")
        manifest = {"db": name, "scale": args.scale, "load_threads": args.load_threads, "rows": rows,
                    "csv": {t: csv for t, csv, _ in loads}, "load_seconds": round(time.time() - t0, 1),
                    "binary": args.binary}
        with open(final + ".json", "w") as f:
            json.dump(manifest, f, indent=1)
        print("%s: done in %.1f s, rows %s" % (name, time.time() - t0, rows), flush=True)


if __name__ == "__main__":
    main()
