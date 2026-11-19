#!/usr/bin/env python3
"""Predicate-cache experiment on ClickBench (small scale): tables from the phase4.py runs.

Runs (all ONE session per config: ingest, then q01..q43 (cold pass), then q01..q43 again (warm pass, tags #p2)):
  count  (threads 1, counters):  --configs  e.g. baseline_pc,ng2000_pc,predcache,predcache_ng2000[,predcache_sub,...]
  check  (threads 8, no counters): <config>_t8 for every config, + baseline check repetitions (--check-baselines)
  time   (threads 8, .mode trash, --rounds 4: round 1 = cold, rounds 2-4 = warm): --time-configs

  predcache_aggregate.py --scale small --configs ... --base baseline_pc [--check-baselines b1,b2,...]
                         [--time-configs baseline_pct,predcache_t,predcache_ng2000_t]
-> results/<scale>/phase4/predcache/{per_query.csv,per_config.csv,results_check.csv,timing.csv,cache_size.csv,
   summary.md}
"""
import argparse
import collections
import csv
import glob
import json
import os
import statistics
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common  # noqa: E402
import phase4  # noqa: E402

FIELDS = ["total_row_groups", "pruned", "pruned_minmax", "pruned_additional", "pruned_predicate_cache",
          "scanned_no_rows", "scanned_with_rows", "partial_no_rows", "not_reached", "rows_passed"]
QIDS = ["q%02d" % i for i in range(1, 44)]


def gdir(scale, config, mode):
    return os.path.join(common.raw_dir(scale, "phase4"), config, mode, "clickbench")


def attempts(d):
    return sorted(glob.glob(os.path.join(d, "session_*", "attempt_*")))


def split_tag(tag):
    """'clickbench/q05#p2' -> ('q05', 2)"""
    t = tag.split("/", 1)[1]
    if "#p" in t:
        q, p = t.split("#p")
        return q, int(p)
    if "#r" in t:
        q, r = t.split("#r")
        return q, int(r)
    return t, 1


def load(scale, config, mode):
    scans, timings, status, att = collections.defaultdict(list), {}, {}, attempts(gdir(scale, config, mode))
    for a in att:
        cur = {}
        for r in phase4.load_jsonl(os.path.join(a, "pruning.jsonl")):
            if not r.get("tag", "").startswith("clickbench/q"):
                continue
            if r["type"] == "query" and not r["sql"].startswith("SET"):
                cur[r["tag"]] = r["seq"]
                scans[r["tag"]] = []
            elif r["type"] == "scan" and cur.get(r["tag"]) == r["seq"]:
                scans[r["tag"]].append(r)
        for r in phase4.load_jsonl(os.path.join(a, "timing.jsonl")):
            if r["type"] == "query_timing" and r["tag"].startswith("clickbench/q") and not r["sql"].startswith("SET"):
                timings[r["tag"]] = r
        for r in phase4.load_jsonl(os.path.join(a, "status.jsonl")):
            if r.get("kind") == "query":
                status[r["tag"]] = r
    return scans, timings, status, len(att)


def hash_of(r):
    return (r.get("status"), r.get("rows"), r.get("hash_sorted") or r.get("hash_multiset") or r.get("hash"))


def run_info(scale, config, mode):
    try:
        with open(os.path.join(gdir(scale, config, mode), "run.json")) as f:
            return json.load(f)
    except OSError:
        return {}


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--scale", default="small")
    ap.add_argument("--configs", required=True)
    ap.add_argument("--base", default="baseline_pc")
    ap.add_argument("--labels", default="", help="config=label,... for the tables")
    ap.add_argument("--check-baselines", default="")
    ap.add_argument("--time-configs", default="")
    ap.add_argument("--time-reps", default="", help="suffixes of repeated timing sessions, e.g. _b,_c: each "
                                                    "time config is <config><suffix>; warm executions are pooled")
    args = ap.parse_args()
    od = os.path.join(common.results_dir(args.scale), "phase4", "predcache")
    os.makedirs(od, exist_ok=True)
    configs = args.configs.split(",")
    labels = dict(x.split("=") for x in args.labels.split(",") if x)
    lab = lambda c: labels.get(c, c)  # noqa: E731
    data = {c: load(args.scale, c, "count") for c in configs}
    base_status = data[args.base][2]
    md = ["# Predicate cache: ClickBench 1M (small scale)", ""]

    # ---------------- per query ----------------
    rows, inv = [], []
    agg = {}  # (config, pass, qid) -> dict
    for c in configs:
        scans, timings, status, natt = data[c]
        if natt != 1:
            inv.append("%s: %d attempts (session restarted: cache not continuous)" % (c, natt))
        for p in (1, 2):
            for q in QIDS:
                tag = "clickbench/%s%s" % (q, "" if p == 1 else "#p2")
                d = {k: 0 for k in FIELDS}
                ss = scans.get(tag, [])
                for s in ss:
                    for k in FIELDS:
                        d[k] += s.get(k, 0)
                    tot = s["pruned"] + s["scanned_no_rows"] + s["scanned_with_rows"] + s["partial_no_rows"] + \
                        s["not_reached"]
                    if tot != s["total_row_groups"]:
                        inv.append("%s %s scan %s: total" % (c, tag, s["scan_id"]))
                    if s["pruned"] != s["pruned_minmax"] + s["pruned_additional"] + s.get("pruned_predicate_cache", 0):
                        inv.append("%s %s scan %s: pruned split" % (c, tag, s["scan_id"]))
                st = status.get(tag, {})
                bs = base_status.get("clickbench/" + q, {})
                tm = timings.get(tag, {})
                d.update({"config": c, "pass": "cold" if p == 1 else "warm", "qid": q, "scans": len(ss),
                          "cacheable_scans": sum(1 for s in ss if (s.get("predicate_cache") or {}).get("cacheable")),
                          "result_identical": hash_of(st) == hash_of(bs) if st else None,
                          "elapsed_ms": round(tm.get("elapsed_ms", 0.0), 3),
                          "pc_entries": tm.get("pc_entries", ""), "pc_bytes": tm.get("pc_bytes", ""),
                          "pc_recorded_empty": tm.get("pc_recorded_empty", ""),
                          "pc_recorded_rows": tm.get("pc_recorded_rows", ""),
                          "pc_conflicts": tm.get("pc_conflicts", ""),
                          "pc_lookup_ns": tm.get("pc_lookup_ns", ""), "pc_record_ns": tm.get("pc_record_ns", ""),
                          "pc_recheck_ns": tm.get("pc_recheck_ns", ""),
                          "keys": " | ".join(sorted({(s.get("predicate_cache") or {}).get("key", "") for s in ss
                                                     if (s.get("predicate_cache") or {}).get("cacheable")}))})
                agg[(c, p, q)] = d
                rows.append(d)
    cols = ["config", "pass", "qid", "scans", "cacheable_scans"] + FIELDS + [
        "result_identical", "elapsed_ms", "pc_entries", "pc_bytes", "pc_recorded_empty", "pc_recorded_rows",
        "pc_conflicts", "pc_lookup_ns", "pc_record_ns", "pc_recheck_ns", "keys"]
    with open(os.path.join(od, "per_query.csv"), "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        w.writerows(rows)

    # ---------------- per config totals ----------------
    tot_rows = []
    for c in configs:
        for p in (1, 2):
            t = {k: sum(agg[(c, p, q)][k] for q in QIDS) for k in FIELDS}
            t.update({"config": c, "pass": "cold" if p == 1 else "warm",
                      "identical": sum(1 for q in QIDS if agg[(c, p, q)]["result_identical"]),
                      "queries": len(QIDS)})
            last = agg[(c, p, "q43")]
            t["pc_entries_end"] = last["pc_entries"]
            t["pc_bytes_end"] = last["pc_bytes"]
            t["pc_conflicts"] = sum(int(agg[(c, p, q)]["pc_conflicts"] or 0) for q in QIDS)
            t["pc_lookup_ms"] = round(sum(int(agg[(c, p, q)]["pc_lookup_ns"] or 0) for q in QIDS) / 1e6, 3)
            t["pc_record_ms"] = round(sum(int(agg[(c, p, q)]["pc_record_ns"] or 0) for q in QIDS) / 1e6, 3)
            t["pc_recheck_ms"] = round(sum(int(agg[(c, p, q)]["pc_recheck_ns"] or 0) for q in QIDS) / 1e6, 3)
            tot_rows.append(t)
    with open(os.path.join(od, "per_config.csv"), "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["config", "pass", "queries", "identical"] + FIELDS + [
            "pc_entries_end", "pc_bytes_end", "pc_conflicts", "pc_lookup_ms", "pc_record_ms", "pc_recheck_ms"])
        w.writeheader()
        w.writerows(tot_rows)

    # ---------------- correctness ----------------
    md += ["## Correctness", ""]
    check_rows = []
    for t in tot_rows:
        check_rows.append({"config": t["config"], "mode": "count, threads 1, %s pass" % t["pass"],
                           "identical": t["identical"], "queries": t["queries"], "details": ""})
    md.append("* Counting passes (1 thread), result (row count + order-independent hash) vs. `%s` cold pass: %s." % (
        args.base, "; ".join("`%s` %s %d/%d" % (t["config"], t["pass"], t["identical"], t["queries"])
                             for t in tot_rows)))
    md.append("* Counter invariants (`total = pruned + scanned_no_rows + scanned_with_rows + partial_no_rows + "
              "not_reached`, `pruned = pruned_minmax + pruned_additional + pruned_predicate_cache`) per scan: %s." % (
                  "0 violations" if not inv else "%d problems: %s" % (len(inv), "; ".join(inv[:10]))))
    confl = sum(t["pc_conflicts"] for t in tot_rows)
    md.append("* Cache merge conflicts (a row group recorded once as \"no rows\" and once as \"has rows\" for the "
              "same key): %d." % confl)
    for c in configs:
        if c == args.base:
            continue
        diffs = []
        for p in (1, 2):
            for q in QIDS:
                a, b = agg[(args.base, 1, q)], agg[(c, p, q)]
                if a["scanned_with_rows"] != b["scanned_with_rows"] or a["rows_passed"] != b["rows_passed"] or \
                        a["total_row_groups"] != b["total_row_groups"]:
                    diffs.append("%s/%s" % (q, "cold" if p == 1 else "warm"))
        md.append("* `%s`: `scanned_with_rows`, `rows_passed`, `total_row_groups` per query equal to the baseline "
                  "cold pass: %s" % (c, "all 86 query executions" if not diffs else "differences in " +
                                     ", ".join(diffs)))
    if args.check_baselines:
        # every pass of every baseline check run is one sample of the (possibly nondeterministic) baseline result
        bases = []
        for b in args.check_baselines.split(","):
            st = load(args.scale, b, "check")[2]
            for suffix in ("", "#p2"):
                if any(t.endswith(suffix) for t in st if suffix) or not suffix:
                    sample = {q: st.get("clickbench/" + q + suffix) for q in QIDS}
                    if any(v is not None for v in sample.values()):
                        bases.append(sample)
        nondet = {q for q in QIDS if len({hash_of(b.get(q) or {}) for b in bases}) > 1}
        allowed = {q: {hash_of(b.get(q) or {}) for b in bases} for q in QIDS}
        md.append("* Multi-threaded check passes (%s threads, cold + warm pass in one session) vs. %d baseline samples "
                  "(every pass of the baseline check runs `%s`); the baseline samples disagree among themselves on "
                  "%s (nondeterministic with threads > 1: ties in `ORDER BY ... LIMIT`, `LIMIT` without `ORDER BY`):" % (
                      run_info(args.scale, args.check_baselines.split(",")[0], "check").get("threads"),
                      len(bases), args.check_baselines, ", ".join(sorted(nondet)) or "none"))
        for c in configs:
            cc = c + "_t8"
            if not os.path.isdir(gdir(args.scale, cc, "check")):
                continue
            st = load(args.scale, cc, "check")[2]
            for p in (1, 2):
                suffix = "" if p == 1 else "#p2"
                same = [q for q in QIDS if hash_of(st.get("clickbench/" + q + suffix, {})) ==
                        hash_of(bases[0].get(q) or {})]
                seen = [q for q in QIDS if hash_of(st.get("clickbench/" + q + suffix, {})) in allowed[q]]
                bad = [q for q in QIDS if q not in seen]
                bad_det = [q for q in bad if q not in nondet]
                check_rows.append({"config": cc, "mode": "check, threads 8, %s pass" % ("cold" if p == 1 else "warm"),
                                   "identical": len(same), "queries": len(QIDS),
                                   "details": "equal to one of the baseline runs: %d; not equal to any: %s; of these "
                                              "deterministic: %s" % (len(seen), ",".join(bad) or "none",
                                                                     ",".join(bad_det) or "none")})
                md.append("  * `%s` %s pass: identical to the first baseline run %d/43, to one of the baseline runs "
                          "%d/43; equal to none: %s%s" % (
                              cc, "cold" if p == 1 else "warm", len(same), len(seen), ", ".join(bad) or "none",
                              "" if not bad else " (deterministic among them: %s)" % (", ".join(bad_det) or "none")))
    with open(os.path.join(od, "results_check.csv"), "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["config", "mode", "queries", "identical", "details"])
        w.writeheader()
        w.writerows(check_rows)

    # ---------------- totals ----------------
    md += ["", "## Totals over the 43 queries (counting pass, 1 thread)", "",
           "| config | pass | row groups | pruned | of which min/max | of which n-gram stat | of which predicate "
           "cache | scanned, no rows (wasted) | scanned with rows | cache entries / bytes at end of pass |",
           "|---|---|---|---|---|---|---|---|---|---|"]
    for t in tot_rows:
        md.append("| %s | %s | %d | %d | %d | %d | %d | %d | %d | %s / %s |" % (
            lab(t["config"]), t["pass"], t["total_row_groups"], t["pruned"], t["pruned_minmax"],
            t["pruned_additional"], t["pruned_predicate_cache"], t["scanned_no_rows"], t["scanned_with_rows"],
            t["pc_entries_end"], t["pc_bytes_end"]))

    # ---------------- per query tables ----------------
    for p in (1, 2):
        md += ["", "## %s pass, per query (q01..q43 in execution order)" % ("Cold" if p == 1 else "Warm"), "",
               "Per configuration: pruned (of which by the predicate cache) / scanned, no rows (wasted) / scanned with "
               "rows. `total` = row groups scanned or pruned (sum over the query's table scans; equal in all "
               "configurations).", ""]
        hdr = "| query | total | " + " | ".join(lab(c) for c in configs) + " |"
        md += [hdr, "|---|---|" + "---|" * len(configs)]
        for q in QIDS:
            cells = []
            for c in configs:
                d = agg[(c, p, q)]
                cells.append("%d (%d) / %d / %d" % (d["pruned"], d["pruned_predicate_cache"], d["scanned_no_rows"],
                                                    d["scanned_with_rows"]))
            totals = {agg[(c, p, q)]["total_row_groups"] for c in configs}
            md.append("| %s | %s | %s |" % (q, "/".join(str(x) for x in sorted(totals)), " | ".join(cells)))
        t = [x for x in tot_rows if x["pass"] == ("cold" if p == 1 else "warm")]
        md.append("| **sum** | %d | %s |" % (t[0]["total_row_groups"], " | ".join(
            "%d (%d) / %d / %d" % (x["pruned"], x["pruned_predicate_cache"], x["scanned_no_rows"],
                                   x["scanned_with_rows"]) for x in t)))

    # ---------------- cache size ----------------
    md += ["", "## Cache size and cost (counting pass, 1 thread)", "",
           "| config | entries after cold / warm pass | bytes after cold / warm pass | lookup ms (cold / warm, all "
           "queries) | record ms | static re-check ms |", "|---|---|---|---|---|---|"]
    size_rows = []
    for c in configs:
        a = [t for t in tot_rows if t["config"] == c]
        if a[0]["pc_entries_end"] == "":
            continue
        md.append("| %s | %s / %s | %s / %s | %s / %s | %s / %s | %s / %s |" % (
            lab(c), a[0]["pc_entries_end"], a[1]["pc_entries_end"], a[0]["pc_bytes_end"], a[1]["pc_bytes_end"],
            a[0]["pc_lookup_ms"], a[1]["pc_lookup_ms"], a[0]["pc_record_ms"], a[1]["pc_record_ms"],
            a[0]["pc_recheck_ms"], a[1]["pc_recheck_ms"]))
        for x in a:
            size_rows.append({"config": c, "pass": x["pass"], "entries": x["pc_entries_end"],
                              "bytes": x["pc_bytes_end"], "lookup_ms": x["pc_lookup_ms"],
                              "record_ms": x["pc_record_ms"], "recheck_ms": x["pc_recheck_ms"]})
    with open(os.path.join(od, "cache_size.csv"), "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["config", "pass", "entries", "bytes", "lookup_ms", "record_ms",
                                          "recheck_ms"])
        w.writeheader()
        w.writerows(size_rows)
    # keys
    keys = collections.OrderedDict()
    for c in configs:
        for q in QIDS:
            for k in agg[(c, 1, q)]["keys"].split(" | "):
                if k:
                    keys.setdefault(k, []).append(q)
    md += ["", "Cache keys (static non-optional pushed-down conjunctions of cacheable scans; `#<n>` = storage column "
               "index of `hits`) and the queries using them:", ""]
    for k, qs in keys.items():
        md.append("* `%s`: %s" % (k, ", ".join(sorted(set(qs)))))

    # ---------------- timing ----------------
    if args.time_configs:
        tcs = args.time_configs.split(",")
        trows = []
        med = {}
        reps = args.time_reps.split(",") if args.time_reps else [""]
        for c in tcs:
            loaded = [(rep, load(args.scale, c + rep, "time")[1]) for rep in reps]
            info = run_info(args.scale, c + reps[0], "time")
            for q in QIDS:
                warm_all = []
                for rep, timings in loaded:
                    warm = [timings[t]["elapsed_ms"] for t in ("clickbench/%s#r%d" % (q, r) for r in (2, 3, 4))
                            if t in timings]
                    warm_all += warm
                    cold = timings.get("clickbench/%s#r1" % q, {}).get("elapsed_ms")
                    trows.append({"config": c + rep, "qid": q, "threads": info.get("threads"), "cold_ms": cold,
                                  "warm_ms_r2": warm[0] if len(warm) > 0 else None,
                                  "warm_ms_r3": warm[1] if len(warm) > 1 else None,
                                  "warm_ms_r4": warm[2] if len(warm) > 2 else None,
                                  "warm_median_ms": statistics.median(warm) if warm else None})
                med[(c, q)] = statistics.median(warm_all) if warm_all else None
        with open(os.path.join(od, "timing.csv"), "w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=list(trows[0].keys()))
            w.writeheader()
            w.writerows(trows)
        info = run_info(args.scale, tcs[0] + reps[0], "time")
        md += ["", "## Query time (engine-side elapsed ms; %s threads; %d session(s) per config (%s), each: ingest, "
                   "then the 43 queries 4 times round-robin; round 1 = cold cache, rounds 2-4 = warm; value = median "
                   "of the %d warm executions)" % (info.get("threads"), len(reps), ", ".join(c + r for c in tcs[:1]
                                                                                           for r in reps),
                                                   3 * len(reps)), "",
               "| query | " + " | ".join(lab(c) for c in tcs) + " | " + " | ".join(
                   "speedup %s" % lab(c) for c in tcs[1:]) + " |",
               "|---|" + "---|" * (2 * len(tcs) - 1)]
        for q in QIDS:
            b = med[(tcs[0], q)]
            md.append("| %s | %s | %s |" % (q, " | ".join("%.2f" % med[(c, q)] if med[(c, q)] is not None else "-"
                                                         for c in tcs),
                                          " | ".join("%.2f" % (b / med[(c, q)]) if b and med[(c, q)] else "-"
                                                     for c in tcs[1:])))
        sums = {c: sum(med[(c, q)] or 0 for q in QIDS) for c in tcs}
        md.append("| **sum** | %s | %s |" % (" | ".join("%.1f" % sums[c] for c in tcs),
                                             " | ".join("%.2f" % (sums[tcs[0]] / sums[c]) for c in tcs[1:])))
    with open(os.path.join(od, "summary.md"), "w") as f:
        f.write("\n".join(md) + "\n")
    print("wrote %s" % od)


if __name__ == "__main__":
    main()
