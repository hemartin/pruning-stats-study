#!/usr/bin/env python3
"""Final step 7: aggregate the full-scale pruning counts (no timing).

micro (results/raw/large/count_final = stock Step 1; phase4 final_occts200 / final_nsts200 = Step 4):
  per setup: queries, partitions, pruned, wasted (scanned, 0 qualifying rows), with rows, % of min/max wasted pruned
ClickBench (phase4 baseline_finalcb, finalcb_{trigram,predcache,rowid,all}; 1 thread; passes p1 / p2):
  per query and config: pruned split into min/max, trigram (pruned_additional), predicate cache, row-id
  (pruned_rowid_range; the selective binary also counts them in pruned_minmax -> subtracted), wasted, with rows
-> results/large/final/{micro_per_setup.csv, clickbench_per_query.csv, summary.md}
"""
import collections, csv, glob, json, os

RAW = "results/raw/large"
OUT = "results/large/final"
os.makedirs(OUT, exist_ok=True)
SETUPS = ["point_unsorted", "range_seconds_unsorted", "range_minutes_unsorted", "range_hours_unsorted"]


def scans_of(files):
    """tag -> list of scan records of the last execution of that tag"""
    res, cur = {}, {}
    for f in files:
        for line in open(f):
            r = json.loads(line)
            if r["type"] == "query" and r.get("n_scans") and r["tag"]:
                cur[r["tag"]] = r["seq"]
                res[r["tag"]] = []
            elif r["type"] == "scan" and r["tag"] and cur.get(r["tag"]) == r["seq"]:
                res[r["tag"]].append(r)
    return res


def phase4_files(config, group):
    return sorted(glob.glob("%s/phase4/%s/count/%s/session_*/attempt_*/pruning.jsonl" % (RAW, config, group)))


def ingest(config, group):
    for f in glob.glob("%s/phase4/%s/count/%s/session_*/attempt_*/timing.jsonl" % (RAW, config, group)):
        for line in open(f):
            r = json.loads(line)
            if r["type"] == "ingest":
                yield r


def tot(scans):
    t = collections.Counter()
    for s in scans:
        t["total"] += s["total_row_groups"]
        t["pruned"] += s["pruned"]
        t["wasted"] += s["scanned_no_rows"] + s["partial_no_rows"]
        t["with_rows"] += s["scanned_with_rows"]
        t["not_reached"] += s["not_reached"]
        rid = s.get("pruned_rowid_range", 0)
        t["rowid"] += rid
        t["minmax"] += s.get("pruned_minmax", s["pruned"]) - rid
        t["stat"] += s.get("pruned_additional", 0)
        t["cache"] += s.get("pruned_predicate_cache", 0)
    return t


md = ["# Final full-scale pruning counts", "",
      "All databases loaded single-threaded (exact 8,192-row partitions): micro_unsorted 1,000,000,000 rows = 122,071 "
      "partitions, ClickBench 99,997,497 rows = 12,207 partitions. Counts only, no timing.", ""]

# ---------------- micro ----------------
base = {}
for s in SETUPS:
    base.update(scans_of(["%s/count_final/%s/pruning.jsonl" % (RAW, s)]))
cfgs = [("minmax (stock)", None), ("occupancy@200", "final_occts200"), ("nullspace@200", "final_nsts200")]
data = {c: (base if cfg is None else scans_of(phase4_files(cfg, "micro_unsorted"))) for c, cfg in cfgs}
rows = []
for s in SETUPS:
    btags = sorted(t for t in base if t.startswith(s + "/"))
    bt = tot(sc for t in btags for sc in base[t])
    for c, cfg in cfgs:
        tags = [t for t in btags if t in data[c]]
        t = tot(sc for tg in tags for sc in data[c][tg])
        bsub = tot(sc for tg in tags for sc in base[tg])
        rows.append(dict(setup=s, config=c, queries=len(tags), partitions=t["total"], pruned=t["pruned"],
                         pruned_by_statistic=t["stat"], wasted=t["wasted"], with_rows=t["with_rows"],
                         minmax_wasted=bsub["wasted"],
                         pct_wasted_pruned=round(100.0 * (bsub["wasted"] - t["wasted"]) / bsub["wasted"], 1) if bsub["wasted"] else None,
                         with_rows_equal_minmax=t["with_rows"] == bsub["with_rows"]))
with open(os.path.join(OUT, "micro_per_setup.csv"), "w", newline="") as f:
    w = csv.DictWriter(f, fieldnames=list(rows[0]))
    w.writeheader()
    w.writerows(rows)
md += ["## Microbenchmark, unsorted, 1B rows (100 queries per setup, every 10th)", "",
       "| setup | config | queries | partitions | pruned | wasted | with rows | % of min/max wasted pruned | with rows unchanged |",
       "|---|---|---|---|---|---|---|---|---|"]
for r in rows:
    md.append("| %s | %s | %d | %d | %d | %d | %d | %s | %s |" % (r["setup"], r["config"], r["queries"], r["partitions"], r["pruned"],
              r["wasted"], r["with_rows"], "-" if r["pct_wasted_pruned"] is None else r["pct_wasted_pruned"], r["with_rows_equal_minmax"]))
for c, cfg in cfgs[1:]:
    for r in ingest(cfg, "micro_unsorted"):
        md.append("")
        md.append("%s build at ATTACH: %d row groups, %.1f MB, %.0f s CPU" % (c, r["row_groups_built"], r["bytes"] / 1e6, r["build_ns"] / 1e9))
md.append("")

# ---------------- ClickBench ----------------
CB = [("min/max", "baseline_finalcb"), ("trigram@2000", "finalcb_trigram"), ("pred. cache", "finalcb_predcache"),
      ("row-id", "finalcb_rowid"), ("all three", "finalcb_all")]
cbd = {c: scans_of(phase4_files(cfg, "clickbench")) for c, cfg in CB}
qids = sorted({t.split("/")[1].split("#")[0] for t in cbd["min/max"]})
cbrows = []
for q in qids:
    for c, _ in CB:
        for p in ("p1", "p2"):
            tag = "clickbench/%s" % q + ("" if p == "p1" else "#p2")
            if tag not in cbd[c]:
                continue
            t = tot(cbd[c][tag])
            cbrows.append(dict(query=q, config=c, run="first" if p == "p1" else "repeat", partitions=t["total"],
                               pruned=t["pruned"], minmax=t["minmax"], trigram=t["stat"], cache=t["cache"], rowid=t["rowid"],
                               wasted=t["wasted"], with_rows=t["with_rows"], not_reached=t["not_reached"], scans=len(cbd[c][tag])))
with open(os.path.join(OUT, "clickbench_per_query.csv"), "w", newline="") as f:
    w = csv.DictWriter(f, fieldnames=list(cbrows[0]))
    w.writeheader()
    w.writerows(cbrows)
md += ["## ClickBench 100M (1 thread, the queries with wasted reads under min/max)", "",
       "| query | config | run | partitions | pruned | min/max | trigram | cache | row-id | wasted | with rows | not reached |",
       "|---|---|---|---|---|---|---|---|---|---|---|---|"]
for r in cbrows:
    md.append("| %(query)s | %(config)s | %(run)s | %(partitions)d | %(pruned)d | %(minmax)d | %(trigram)d | %(cache)d | %(rowid)d | %(wasted)d | %(with_rows)d | %(not_reached)d |" % r)
md.append("")
for c, cfg in CB:
    for r in ingest(cfg, "clickbench"):
        md.append("%s build at ATTACH: %s.%s %d row groups, %.1f MB, %.0f s CPU  " % (c, r["table"], r["column"], r["row_groups_built"], r["bytes"] / 1e6, r["build_ns"] / 1e9))
md.append("")
for name in ("validation_micro.md", "ceilings.md"):
    p = os.path.join(OUT, name)
    if os.path.exists(p):
        md += ["## " + name, "", open(p).read(), ""]
open(os.path.join(OUT, "summary.md"), "w").write("\n".join(md))
print("\n".join(md))
