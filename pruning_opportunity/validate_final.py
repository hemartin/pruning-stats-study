#!/usr/bin/env python3
"""Final step 3: ground-truth check of the pruning counters at full scale.

For a sample of queries per setup, counts the partitions (rowid // 8192) that contain at least one qualifying row with
plain SQL (one scan per setup, all sampled predicates evaluated in the same scan) and compares with the counters:
  * counter scanned_with_rows must equal the true number of partitions with matches
    (a match inside a pruned partition would show up as a mismatch, so this also checks pruning soundness)
  * total_row_groups == pruned + scanned + not_reached, scanned == scanned_no_rows + scanned_with_rows + partial_no_rows
Usage: validate_final.py --label count_final --setups a,b --per-setup 20 --binary B --db DB --out results/large/final
"""
import argparse, csv, json, os, re, subprocess

ap = argparse.ArgumentParser()
ap.add_argument("--label", default="count_final")
ap.add_argument("--scale", default="large")
ap.add_argument("--setups", default="point_unsorted,range_seconds_unsorted,range_minutes_unsorted,range_hours_unsorted")
ap.add_argument("--per-setup", type=int, default=20)
ap.add_argument("--binary", default="stock/duckdb/build/release/duckdb")
ap.add_argument("--db", default="db/large/micro_unsorted.db")
ap.add_argument("--table", default="sensor_records")
ap.add_argument("--threads", type=int, default=8)
ap.add_argument("--out", default="results/large/final")
args = ap.parse_args()
os.makedirs(args.out, exist_ok=True)


def load_scans(setup):
    path = "results/raw/%s/%s/%s/pruning.jsonl" % (args.scale, args.label, setup)
    qsql, scans = {}, {}
    for line in open(path):
        r = json.loads(line)
        if r["type"] == "query" and r.get("n_scans", 0) > 0 and r["tag"]:
            qsql[r["tag"]] = r["sql"]
        elif r["type"] == "scan" and r["tag"]:
            scans.setdefault(r["tag"], []).append(r)
    return qsql, scans


rows_out = []
for setup in args.setups.split(","):
    qsql, scans = load_scans(setup)
    tags = sorted(qsql)
    step = max(1, len(tags) // args.per_setup)
    sample = tags[::step][:args.per_setup]
    preds = []
    for t in sample:
        m = re.search(r"\bWHERE\b(.*?);?\s*$", qsql[t], re.S | re.I)
        preds.append(m.group(1).strip().rstrip(";"))
    cols = ", ".join("bool_or(%s) AS q%d" % (p, i) for i, p in enumerate(preds))
    sums = ", ".join("count(*) FILTER (WHERE q%d) AS q%d" % (i, i) for i in range(len(preds)))
    sql = ("SET threads TO %d; SET memory_limit='4GB';\n.mode csv\n"
           "SELECT count(*) AS n_part, %s FROM (SELECT rowid // 8192 AS p, %s FROM %s GROUP BY p);\n"
           % (args.threads, sums, cols, args.table))
    out = subprocess.run([args.binary, "-readonly", args.db], input=sql.encode(), stdout=subprocess.PIPE,
                         stderr=subprocess.STDOUT, check=True).stdout.decode().strip().splitlines()
    vals = [int(x) for x in out[-1].split(",")]
    n_part, truth = vals[0], vals[1:]
    for t, p, tr in zip(sample, preds, truth):
        s = scans[t][0]
        inv1 = s["total_row_groups"] == s["pruned"] + s["scanned"] + s["not_reached"]
        inv2 = s["scanned"] == s["scanned_no_rows"] + s["scanned_with_rows"] + s["partial_no_rows"]
        ok = (s["scanned_with_rows"] == tr) and inv1 and inv2 and s["total_row_groups"] == n_part and len(scans[t]) == 1
        rows_out.append(dict(setup=setup, tag=t, predicate=p, true_partitions_with_rows=tr,
                             counter_with_rows=s["scanned_with_rows"], pruned=s["pruned"],
                             wasted=s["scanned_no_rows"] + s["partial_no_rows"], total=s["total_row_groups"],
                             sql_partitions=n_part, invariants=inv1 and inv2, ok=ok))
    print(setup, "checked", len(sample), "ok", sum(r["ok"] for r in rows_out if r["setup"] == setup), flush=True)

with open(os.path.join(args.out, "validation_micro.csv"), "w", newline="") as f:
    w = csv.DictWriter(f, fieldnames=list(rows_out[0]))
    w.writeheader()
    w.writerows(rows_out)
with open(os.path.join(args.out, "validation_micro.md"), "w") as f:
    f.write("| setup | queries checked | counter = ground truth | invariants hold | partitions (SQL) |\n|---|---|---|---|---|\n")
    for setup in args.setups.split(","):
        rs = [r for r in rows_out if r["setup"] == setup]
        f.write("| %s | %d | %d | %d | %d |\n" % (setup, len(rs), sum(r["counter_with_rows"] == r["true_partitions_with_rows"] for r in rs),
                                                sum(r["invariants"] for r in rs), rs[0]["sql_partitions"]))
print("all ok" if all(r["ok"] for r in rows_out) else "MISMATCHES: %d" % sum(not r["ok"] for r in rows_out))
