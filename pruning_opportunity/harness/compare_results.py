#!/usr/bin/env python3
"""Check that counting does not change query results.

1. Instrumented binary with counting ON vs OFF (both run with --hash): per query the hash of the CSV output
   lines (in output order) must be identical, as must the status (ok/error).
2. Instrumented binary vs pip `duckdb` (independent build, different version): row counts for every query;
   for the microbenchmarks additionally the order-independent hash of all rows (rendered as CSV lines).

Writes results/<scale>/result_check.{csv,md}.
"""
import argparse
import collections
import csv
import hashlib
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common  # noqa: E402
from aggregate import load_status  # noqa: E402


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--scale", required=True)
    ap.add_argument("--on", default="count", help="label of the counting-on run (must use --hash)")
    ap.add_argument("--off", default="nocount", help="label of the counting-off run (must use --hash)")
    ap.add_argument("--setups", default="all")
    ap.add_argument("--pip", action="store_true", help="also compare against the pip duckdb package")
    args = ap.parse_args()
    rows = []
    summ = collections.OrderedDict()
    for setup in common.select_setups(args.setups):
        on = load_status(os.path.join(common.raw_dir(args.scale, args.on), setup.name))
        off = load_status(os.path.join(common.raw_dir(args.scale, args.off), setup.name))
        if not on and not off:
            continue
        s = summ.setdefault(setup.name, collections.Counter())
        con = None
        queries = setup.queries()
        qids = setup.qids(len(queries))
        if args.pip:
            import duckdb
            con = duckdb.connect(os.path.join(common.db_dir(args.scale), setup.db_name + ".db"), read_only=True)
            con.execute("SET threads TO 1")
            con.execute("SET memory_limit = '6GB'")
        t0 = time.time()
        for qid, sql in zip(qids, queries):
            tag = "%s/%s" % (setup.name, qid)
            a, b = on.get(tag), off.get(tag)
            if a is None and b is None:
                continue
            r = {"setup": setup.name, "qid": qid, "status_on": a and a["status"], "status_off": b and b["status"],
                 "rows_on": a and a["rows"], "rows_off": b and b["rows"]}
            s["queries"] += 1
            if a and b:
                r["on_off_equal"] = (a["status"] == b["status"] and a.get("hash") == b.get("hash")
                                     and a["rows"] == b["rows"])
                s["on_off_compared"] += 1
                s["on_off_mismatch"] += 0 if r["on_off_equal"] else 1
            if con is not None and a and a["status"] == "ok":
                try:
                    res = con.execute(sql).fetchall()
                    r["rows_pip"] = len(res)
                    r["pip_rowcount_equal"] = len(res) == a["rows"]
                    s["pip_compared"] += 1
                    s["pip_rowcount_mismatch"] += 0 if r["pip_rowcount_equal"] else 1
                    if setup.benchmark == "micro":
                        lines = sorted((",".join(str(v) for v in row) + "\r\n").encode() for row in res)  # CLI csv mode: CRLF
                        r["pip_hash_equal"] = hashlib.sha1(b"".join(lines)).hexdigest() == a.get("hash_sorted")
                        s["pip_hash_compared"] += 1
                        s["pip_hash_mismatch"] += 0 if r["pip_hash_equal"] else 1
                except Exception as e:  # noqa: BLE001
                    r["pip_error"] = str(e)[:300]
                    s["pip_error"] += 1
            rows.append(r)
        if con is not None:
            con.close()
        print("%s: %s (%.1f s)" % (setup.name, dict(s), time.time() - t0), flush=True)
    out = common.results_dir(args.scale)
    os.makedirs(out, exist_ok=True)
    cols = ["setup", "qid", "status_on", "status_off", "rows_on", "rows_off", "on_off_equal", "rows_pip",
            "pip_rowcount_equal", "pip_hash_equal", "pip_error"]
    with open(os.path.join(out, "result_check.csv"), "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols, extrasaction="ignore")
        w.writeheader()
        for r in rows:
            w.writerow(r)
    keys = ["queries", "on_off_compared", "on_off_mismatch", "pip_compared", "pip_rowcount_mismatch",
            "pip_hash_compared", "pip_hash_mismatch", "pip_error"]
    lines = ["# Result check (scale %s): counting on vs off, and vs pip duckdb\n" % args.scale,
             "| setup | " + " | ".join(keys) + " |", "|---|" + "|".join("---" for _ in keys) + "|"]
    for name, s in summ.items():
        lines.append("| %s | %s |" % (name, " | ".join(str(s.get(k, 0)) for k in keys)))
    bad = [r for r in rows if r.get("on_off_equal") is False or r.get("pip_rowcount_equal") is False or
           r.get("pip_hash_equal") is False or r.get("pip_error")]
    lines.append("\nMismatching queries: %d\n" % len(bad))
    for r in bad[:100]:
        lines.append("- " + json.dumps(r))
    with open(os.path.join(out, "result_check.md"), "w") as f:
        f.write("\n".join(lines) + "\n")
    print("\n".join(lines[:len(summ) + 4]))


if __name__ == "__main__":
    main()
