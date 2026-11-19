#!/usr/bin/env python3
"""Checks that every timing configuration returns the same query results as stock DuckDB.

  ec2_check_results.py --db-dir pruning_opportunity/db/small --stock-binary ... --timing-binary ... [--sample 10]

For every session of ec2_timing.py's matrix, all its queries are run as
  SELECT count(*), bit_xor(hash(t)) FROM (<query>) t
(row count plus an order-independent hash of all rows) in one shell session with the session's environment, and
compared with the stock binary's answers. ClickBench sessions run their queries twice (the second pass is the
predicate cache's repeat run). Exit code 1 on any mismatch.
"""
import argparse
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import ec2_timing as t  # noqa: E402


def answers(binary, env_extra, db_file, queries, passes, build_threads):
    env = {k: v for k, v in os.environ.items() if not k.startswith("PRUNING_") and k != "DUCKDB_PRUNING_STATS"}
    env.update(env_extra)
    if env_extra.get("PRUNING_STATS_COLUMNS"):
        env["PRUNING_STATS_BUILD_ON_LOAD"] = str(build_threads)
    script = ["ATTACH '%s' AS db (READ_ONLY);" % db_file.replace("'", "''"), "USE db;", ".mode csv",
              ".headers off"]
    keys = []
    for p in range(passes):
        for key, sql in queries:
            keys.append((p, key))
            script.append(".print __Q__")
            script.append("SELECT count(*), bit_xor(hash(t)) FROM (%s) t;" % sql.strip().rstrip(";"))
    r = subprocess.run([binary], input="\n".join(script) + "\n", capture_output=True, text=True, env=env)
    if r.returncode != 0 or "Error" in r.stderr:
        raise SystemExit("%s failed: %s" % (binary, r.stderr[:500]))
    blocks = r.stdout.split("__Q__\n")[1:]
    if len(blocks) != len(keys):
        raise SystemExit("expected %d answers, got %d" % (len(keys), len(blocks)))
    return {k: b.strip() for k, b in zip(keys, blocks)}


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--db-dir", required=True)
    ap.add_argument("--micro-db", default="micro_unsorted.db")
    ap.add_argument("--cb-db", default="clickbench.db")
    ap.add_argument("--stock-binary", required=True)
    ap.add_argument("--timing-binary", required=True)
    ap.add_argument("--sample", type=int, default=10)
    ap.add_argument("--build-threads", type=int, default=4)
    args = ap.parse_args()

    expected = {}
    mismatches = 0
    for dataset, binary_key, config, env, items in t.sessions():
        db_file = os.path.join(args.db_dir, args.micro_db if dataset == "micro" else args.cb_db)
        if dataset == "micro":
            queries = [("%s/%s" % (setup, qid), sql) for setup in items for qid, sql in t.micro_queries(setup, args.sample)]
            passes = 1
        else:
            queries = [(t.CB_NAMES[qid], sql) for qid, sql in t.clickbench_queries()]
            passes = 2
        binary = args.stock_binary if binary_key == "stock" else args.timing_binary
        got = answers(binary, env, db_file, queries, passes, args.build_threads)
        if binary_key == "stock":
            for (p, key), value in got.items():
                expected[(dataset, key)] = value
            print("%-38s %4d answers (reference)" % (t.session_name(dataset, binary_key, config), len(got)))
            continue
        bad = [(p, key, value, expected.get((dataset, key))) for (p, key), value in got.items()
               if value != expected.get((dataset, key))]
        mismatches += len(bad)
        print("%-38s %4d answers, %d mismatch(es)" % (t.session_name(dataset, binary_key, config), len(got), len(bad)))
        for p, key, value, exp in bad[:10]:
            print("    pass %d %s: got %s, stock %s" % (p, key, value, exp))
    print("total mismatches: %d" % mismatches)
    return 1 if mismatches else 0


if __name__ == "__main__":
    sys.exit(main())
