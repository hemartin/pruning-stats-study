#!/usr/bin/env python3
"""Final step 6: exact pruning ceilings for the LIKE queries q21-q24 on ClickBench 100M (db/large/clickbench.db).

One plain-SQL scan (stock CLI, read-only) computes per partition (rowid // 8192): rows, qualifying rows of the complete
pushed-down filter of scan 0 of each query, and whether each n-gram (n = 3, 4, 5) of the required literal occurs in the
column (bool_or(contains(col, gram)) = exact membership in the exact n-gram set of the partition).
Per query:
  no_match      partitions without a qualifying row = the most any exact statistic or the predicate cache can prune
  exact_<n>gram partitions an exact n-gram set would prune (some n-gram of the literal is absent)
-> results/large/final/ceilings_partitions.csv, ceilings.csv, ceilings.md
"""
import argparse, csv, os, subprocess, sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "harness"))
from ngram_eval import QUERIES, grams  # noqa: E402

ap = argparse.ArgumentParser()
ap.add_argument("--binary", default="stock/duckdb/build/release/duckdb")
ap.add_argument("--db", default="db/large/clickbench.db")
ap.add_argument("--threads", type=int, default=4)
ap.add_argument("--memory-limit", default="3GB")
ap.add_argument("--out", default="results/large/final")
args = ap.parse_args()
os.makedirs(args.out, exist_ok=True)
RG, NS = 8192, [3, 4, 5]

cols, gram_cols = ["count(*) AS n_rows"], []
for q, (pred, _) in QUERIES.items():
    cols.append("count(*) FILTER (WHERE %s) AS %s_rows" % (pred, q))
for c, lit in sorted({u for _, (_, uses) in QUERIES.items() for u in uses}):
    for n in NS:
        for g in grams(lit, n):
            name = "has_%s_%s" % (c, g.decode())
            if name not in gram_cols:
                gram_cols.append(name)
                cols.append("coalesce(bool_or(contains(%s, '%s')), false) AS %s" % (c, g.decode(), name))
sql = ("SET threads TO %d; SET memory_limit='%s';\n.mode csv\n"
       "SELECT rowid // %d AS rg, %s FROM hits GROUP BY rg ORDER BY rg;\n"
       % (args.threads, args.memory_limit, RG, ", ".join(cols)))
part_path = os.path.join(args.out, "ceilings_partitions.csv")
with open(part_path, "w") as f:
    subprocess.run([args.binary, "-readonly", args.db], input=sql.encode(), stdout=f, check=True)
rows = list(csv.DictReader(open(part_path)))
for r in rows:
    for k, v in r.items():
        r[k] = (v == "true") if v in ("true", "false") else int(v)
print("partitions:", len(rows), "short:", sum(r["n_rows"] != RG for r in rows))

out = []
for q, (pred, uses) in QUERIES.items():
    rec = dict(query=q, filter=pred, partitions=len(rows),
               with_match=sum(r["%s_rows" % q] > 0 for r in rows),
               no_match=sum(r["%s_rows" % q] == 0 for r in rows))
    for n in NS:
        rec["exact_%dgram" % n] = sum(any(not r["has_%s_%s" % (c, g.decode())] for c, lit in uses for g in grams(lit, n))
                                      for r in rows)
        # soundness: an absent n-gram implies no match
        assert all(r["%s_rows" % q] == 0 for r in rows
                   if any(not r["has_%s_%s" % (c, g.decode())] for c, lit in uses for g in grams(lit, n)))
    out.append(rec)
with open(os.path.join(args.out, "ceilings.csv"), "w", newline="") as f:
    w = csv.DictWriter(f, fieldnames=list(out[0]))
    w.writeheader()
    w.writerows(out)
with open(os.path.join(args.out, "ceilings.md"), "w") as f:
    f.write("| query | filter (scan 0) | partitions | with match | no match (= ceiling) | exact 3-gram | exact 4-gram | exact 5-gram |\n")
    f.write("|---|---|---|---|---|---|---|---|\n")
    for r in out:
        f.write("| %s | `%s` | %d | %d | %d | %d | %d | %d |\n" % (r["query"], r["filter"], r["partitions"], r["with_match"],
                r["no_match"], r["exact_3gram"], r["exact_4gram"], r["exact_5gram"]))
print(open(os.path.join(args.out, "ceilings.md")).read())
