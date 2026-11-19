#!/usr/bin/env python3
"""Combined small-scale ClickBench experiment (3-gram statistics + predicate cache + row-id range check) and the
merge verification of the row-id range check into the selective tree.

Runs (run_combined_small.sh):
  count (phase4.py, threads 1, counters, ONE session per config: ingest, q01..q43 = cold pass, q01..q43 = warm pass)
        configs baseline_cmb, cmb_ng2000, cmb_predcache, cmb_rowid, cmb_ng2000_rowid, cmb_all
  check (phase4.py, threads 8, 2 passes): baseline_cmb_t8, cmb_all_t8 (+ earlier baseline 8-thread samples)
  time  (phase4.py, threads 8, --rounds 4, 1 session: round 1 = cold, rounds 2-4 = warm): cmb_<config>_time
  merge verification on the persisted db/small/clickbench.db (run.py, threads 1, counters + hashes):
        combined/sel_off_count (all flags off) vs rowidexp/stock_count (stock binary),
        combined/sel_rowid_count (PRUNING_ROWID_SKIP=1) vs rowidexp/on_count (the separate rowid binary)

-> results/small/phase4/combined/{per_query.csv,per_config.csv,timing.csv,checks.csv,summary.md}
"""
import collections
import csv
import json
import os
import statistics
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common  # noqa: E402
import predcache_aggregate as pa  # noqa: E402

SCALE = "small"
CONFIGS = ["baseline_cmb", "cmb_ng2000", "cmb_predcache", "cmb_rowid", "cmb_ng2000_rowid", "cmb_all"]
LABELS = {"baseline_cmb": "baseline", "cmb_ng2000": "ng2000", "cmb_predcache": "predcache", "cmb_rowid": "rowid",
          "cmb_ng2000_rowid": "ng2000+rowid", "cmb_all": "all"}
QIDS = pa.QIDS
NONDET_8T = {"q12", "q18", "q19", "q23", "q25", "q31", "q32", "q33", "q39", "q40", "q41"}
OUT = os.path.join(common.results_dir(SCALE), "phase4", "combined")


def per_query(scans):
    d = collections.Counter()
    for s in scans:
        for k in ("total_row_groups", "pruned", "pruned_minmax", "pruned_additional", "pruned_predicate_cache",
                  "pruned_rowid_range", "pruned_rowid_only", "scanned_no_rows", "scanned_with_rows",
                  "partial_no_rows", "not_reached", "rows_passed"):
            d[k] += s.get(k, 0)
    d["scans"] = len(scans)
    # causes: min/max zonemaps (incl. nothing else), n-gram statistic, predicate cache, row-id range check (row
    # groups that only a rowid leaf can prune; pruned_minmax counts them, since the check is done in the zonemap
    # loop)
    d["by_minmax"] = d["pruned_minmax"] - d["pruned_rowid_only"]
    d["by_ngram"] = d["pruned_additional"]
    d["by_predcache"] = d["pruned_predicate_cache"]
    d["by_rowid"] = d["pruned_rowid_only"]
    return d


def invariants(c, tag, scans, problems):
    for s in scans:
        tot = s["pruned"] + s["scanned_no_rows"] + s["scanned_with_rows"] + s["partial_no_rows"] + s["not_reached"]
        if tot != s["total_row_groups"]:
            problems.append("%s %s scan %s: total" % (c, tag, s["scan_id"]))
        if s["pruned"] != s["pruned_minmax"] + s["pruned_additional"] + s.get("pruned_predicate_cache", 0):
            problems.append("%s %s scan %s: pruned split" % (c, tag, s["scan_id"]))
        if s.get("pruned_unattributed", 0):
            problems.append("%s %s scan %s: pruned_unattributed %d" % (c, tag, s["scan_id"],
                                                                      s["pruned_unattributed"]))
        if s.get("pruned_rowid_only", 0) > s.get("pruned_rowid_range", 0):
            problems.append("%s %s scan %s: rowid_only > rowid_range" % (c, tag, s["scan_id"]))


def fmt(d):
    causes = []
    for k, short in (("by_minmax", "mm"), ("by_ngram", "ng"), ("by_predcache", "pc"), ("by_rowid", "rid")):
        if d[k]:
            causes.append("%s %d" % (short, d[k]))
    extra = ""
    if d["partial_no_rows"] or d["not_reached"]:
        extra = " (+%d partial, %d not reached)" % (d["partial_no_rows"], d["not_reached"])
    return "%d [%s] / **%d** / %d%s" % (d["pruned"], ", ".join(causes) or "-", d["scanned_no_rows"],
                                      d["scanned_with_rows"], extra)


# ------------------------------------------------------------------ run.py (persisted DB) comparisons
def runpy_load(label):
    base = os.path.join(common.PO_DIR, "results", "raw", SCALE, label, "clickbench")
    status = {}
    p = os.path.join(base, "status.jsonl")
    if not os.path.exists(p):
        return None, None
    for line in open(p):
        r = json.loads(line)
        status[r["qid"]] = r
    res, cur = {}, None
    for line in open(os.path.join(base, "pruning.jsonl")):
        d = json.loads(line)
        tag = d.get("tag") or ""
        if not tag.startswith("clickbench/"):
            continue
        qid = tag.split("/", 1)[1]
        if d["type"] == "query":
            if d.get("sql", "").strip().upper().startswith("SET VARIABLE"):
                continue
            res[qid] = []
        elif d["type"] == "scan" and qid in res:
            res[qid].append(d)
    return status, res


SKIP = {"session", "seq", "elapsed_ms"}


def subset_equal(ref, other):
    """every key of the reference record (except timing/session) has the same value in the other record
    (filters compared leaf by leaf on the reference's keys)"""
    for k, v in ref.items():
        if k in SKIP:
            continue
        if k == "filters":
            o = other.get("filters", [])
            if len(o) != len(v):
                return False, "filters length"
            for a, b in zip(v, o):
                for kk, vv in a.items():
                    if b.get(kk) != vv:
                        return False, "filter %s.%s %r vs %r" % (a.get("column"), kk, vv, b.get(kk))
            continue
        if other.get(k) != v:
            return False, "%s %r vs %r" % (k, v, other.get(k))
    return True, ""


def compare_runpy(ref_label, label):
    rs, rp = runpy_load(ref_label)
    s, p = runpy_load(label)
    if s is None or rs is None:
        return None
    out = {"queries": 0, "results_equal": 0, "counters_equal": 0, "diffs": []}
    for q in QIDS:
        if q not in rs or q not in s:
            continue
        out["queries"] += 1
        a, b = rs[q], s[q]
        if (a.get("rows"), a.get("hash")) == (b.get("rows"), b.get("hash")) and a.get("status") == b.get("status"):
            out["results_equal"] += 1
        else:
            out["diffs"].append("%s result" % q)
        ra, rb = rp.get(q, []), p.get(q, [])
        ok = len(ra) == len(rb)
        why = "scan count %d vs %d" % (len(ra), len(rb))
        if ok:
            for x, y in zip(ra, rb):
                ok, why = subset_equal(x, y)
                if not ok:
                    break
        if ok:
            out["counters_equal"] += 1
        else:
            out["diffs"].append("%s counters: %s" % (q, why))
    return out


def runpy_wasted(label):
    _, p = runpy_load(label)
    if p is None:
        return None
    return sum(s["scanned_no_rows"] for q in p for s in p[q])


# ------------------------------------------------------------------ main
def main():
    os.makedirs(OUT, exist_ok=True)
    problems = []
    data = {c: pa.load(SCALE, c, "count") for c in CONFIGS}
    base_status = data["baseline_cmb"][2]
    agg = {}
    rows = []
    checks = []
    for c in CONFIGS:
        scans, timings, status, natt = data[c]
        if natt != 1:
            problems.append("%s: %d attempts (session restarted)" % (c, natt))
        for p in (1, 2):
            for q in QIDS:
                tag = "clickbench/%s%s" % (q, "" if p == 1 else "#p2")
                ss = scans.get(tag, [])
                invariants(c, tag, ss, problems)
                d = per_query(ss)
                st = status.get(tag, {})
                bs = base_status.get("clickbench/" + q, {})
                same = pa.hash_of(st) == pa.hash_of(bs) if st else None
                d["result_identical"] = same
                agg[(c, p, q)] = d
                rows.append({"config": LABELS[c], "pass": "cold" if p == 1 else "warm", "qid": q,
                             **{k: d[k] for k in ("scans", "total_row_groups", "pruned", "by_minmax", "by_ngram",
                                                  "by_predcache", "by_rowid", "pruned_rowid_range",
                                                  "scanned_no_rows", "scanned_with_rows", "partial_no_rows",
                                                  "not_reached", "rows_passed")},
                             "result_identical": same})
                if same is False:
                    problems.append("%s %s: result differs from baseline cold" % (c, tag))
                # scanned_with_rows / rows_passed must equal the baseline (pruning never removes qualifying rows)
                b = agg.get(("baseline_cmb", 1, q))
                if b and (d["scanned_with_rows"] != b["scanned_with_rows"] or d["rows_passed"] != b["rows_passed"]
                          or d["total_row_groups"] != b["total_row_groups"]):
                    problems.append("%s %s: with_rows/rows_passed/total differ from baseline" % (c, tag))
    with open(os.path.join(OUT, "per_query.csv"), "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)
    # totals
    tot_rows = []
    for c in CONFIGS:
        for p in (1, 2):
            t = collections.Counter()
            for q in QIDS:
                t.update(agg[(c, p, q)])
            n_ident = sum(1 for q in QIDS if agg[(c, p, q)]["result_identical"])
            tot_rows.append({"config": LABELS[c], "pass": "cold" if p == 1 else "warm",
                             **{k: t[k] for k in ("total_row_groups", "pruned", "by_minmax", "by_ngram",
                                                  "by_predcache", "by_rowid", "scanned_no_rows",
                                                  "scanned_with_rows", "partial_no_rows", "not_reached")},
                             "results_identical": "%d/43" % n_ident})
    with open(os.path.join(OUT, "per_config.csv"), "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(tot_rows[0].keys()))
        w.writeheader()
        w.writerows(tot_rows)

    # ---- 8-thread check passes vs. baseline samples
    t8 = []
    base_samples = []
    for b in ["baseline_cmb_t8", "baseline_pc_t8", "baseline_pc_t8b", "baseline_t8", "baseline_t8b"]:
        if os.path.isdir(pa.gdir(SCALE, b, "check")):
            st = pa.load(SCALE, b, "check")[2]
            for p in (1, 2):
                smp = {q: pa.hash_of(st.get("clickbench/%s%s" % (q, "" if p == 1 else "#p2"), {})) for q in QIDS}
                if any(v[0] for v in smp.values()):
                    base_samples.append(smp)
    for c in ["cmb_all_t8", "cmb_rowid_t8"]:
        if not os.path.isdir(pa.gdir(SCALE, c, "check")):
            continue
        st = pa.load(SCALE, c, "check")[2]
        for p in (1, 2):
            diff_det, diff_nondet, rows_diff = [], [], []
            for q in QIDS:
                h = pa.hash_of(st.get("clickbench/%s%s" % (q, "" if p == 1 else "#p2"), {}))
                if not any(h == smp[q] for smp in base_samples):
                    (diff_nondet if q in NONDET_8T else diff_det).append(q)
                if base_samples and h[1] != base_samples[0][q][1]:
                    rows_diff.append(q)
            t8.append((c, "cold" if p == 1 else "warm", diff_det, diff_nondet, rows_diff))
            if diff_det:
                problems.append("%s pass %d: deterministic queries differ at 8 threads: %s" % (c, p, diff_det))

    # ---- timing (8 threads): round 1 = cold, median of rounds 2-4 = warm
    timing_rows = []
    tdata = {}
    reps_used = 0
    for c in CONFIGS:
        tc0 = "baseline_cmb_time" if c == "baseline_cmb" else c + "_time"
        # repetitions: <config>_time, <config>_time_b, _c, ... (each its own session, run interleaved by config)
        reps = [tc0 + sfx for sfx in ("", "_b", "_c", "_d", "_e") if os.path.isdir(pa.gdir(SCALE, tc0 + sfx, "time"))]
        if not reps:
            continue
        reps_used = max(reps_used, len(reps))
        loaded = [pa.load(SCALE, tc, "time")[1] for tc in reps]
        for q in QIDS:
            colds, warms = [], []
            for timings in loaded:
                for k in (1, 2, 3, 4):
                    tag = "clickbench/%s#r%d" % (q, k)
                    if tag in timings:
                        (colds if k == 1 else warms).append(timings[tag]["elapsed_ms"])
            tdata[(c, q)] = (statistics.median(colds) if colds else None, statistics.median(warms) if warms else None)
    if tdata:
        for q in QIDS:
            row = {"qid": q}
            for c in CONFIGS:
                cold, warm = tdata.get((c, q), (None, None))
                row[LABELS[c] + "_cold_ms"] = round(cold, 2) if cold is not None else ""
                row[LABELS[c] + "_warm_median_ms"] = round(warm, 2) if warm is not None else ""
            timing_rows.append(row)
        with open(os.path.join(OUT, "timing.csv"), "w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=list(timing_rows[0].keys()))
            w.writeheader()
            w.writerows(timing_rows)

    # ---- merge verification (persisted DB, run.py)
    merge = []
    off = compare_runpy("rowidexp/stock_count", "combined/sel_off_count")
    if off:
        merge.append(("selective binary, all flags off vs. stock binary (counters on the stock binary's fields)", off))
    on = compare_runpy("rowidexp/on_count", "combined/sel_rowid_count")
    if on:
        merge.append(("selective binary, PRUNING_ROWID_SKIP=1 vs. the separate rowid binary with the flag on", on))
    w_off, w_on = runpy_wasted("combined/sel_off_count"), runpy_wasted("combined/sel_rowid_count")
    for title, r in merge:
        checks.append({"check": title, "queries": r["queries"], "results_equal": r["results_equal"],
                       "counters_equal": r["counters_equal"], "diffs": "; ".join(r["diffs"])})
    with open(os.path.join(OUT, "checks.csv"), "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["check", "queries", "results_equal", "counters_equal", "diffs"])
        w.writeheader()
        w.writerows(checks)

    # ---------------------------------------------------------------- summary.md
    md = ["# Combined pruning: 3-gram statistics + predicate cache + row-id range check (ClickBench 1M, small)", "",
          "Generated by `harness/combined_aggregate.py` from `run_combined_small.sh`. One DuckDB session per config: "
          "in-session ingest (1M rows, 123 row groups of 8,192 rows) + CHECKPOINT, predicate cache empty, pass 1 = "
          "q01..q43 (cold), pass 2 = q01..q43 again (warm); counting passes with 1 thread. Binary: "
          "`duckdb/build/selective/duckdb` (v1.4.4 + counters + selective statistics + predicate cache + row-id range "
          "check).", "",
          "Configs: **baseline** (min/max only), **ng2000** (`hits.URL:ngram:2000,hits.Title:ngram:2000`, 3-grams), "
          "**predcache** (`PRUNING_PREDICATE_CACHE=1`), **rowid** (`PRUNING_ROWID_SKIP=1`), **ng2000+rowid**, "
          "**all** (ng2000 + predcache + rowid).", "",
          "Cell format: `pruned [by cause] / **wasted** / with rows`; wasted = `scanned_no_rows` (row group read, no "
          "row passes the filters applied to rows). Causes: mm = min/max zonemap, ng = 3-gram statistic, pc = "
          "predicate cache, rid = row-id range check (row groups that only a rowid filter can prune).", ""]
    md += ["## Checks", ""]
    for title, r in merge:
        md.append("* %s: results %d/%d identical, counters %d/%d identical%s" % (
            title, r["results_equal"], r["queries"], r["counters_equal"], r["queries"],
            ("; differences: " + "; ".join(r["diffs"][:10])) if r["diffs"] else ""))
    if w_off is not None and w_on is not None:
        md.append("* persisted DB, wasted reads over 43 queries: flags off %d, rowid on %d (earlier rowid binary: "
                  "627 -> 394)" % (w_off, w_on))
    for c in CONFIGS:
        ok1 = sum(1 for q in QIDS if agg[(c, 1, q)]["result_identical"])
        ok2 = sum(1 for q in QIDS if agg[(c, 2, q)]["result_identical"])
        md.append("* %s, 1 thread: results identical to the baseline cold pass: cold %d/43, warm %d/43" % (
            LABELS[c], ok1, ok2))
    for c, pas, det, nondet, rows_diff in t8:
        md.append("* %s (8 threads) %s pass vs. %d baseline 8-thread samples: deterministic queries differing: %s; "
                  "nondeterministic queries (ties under ORDER BY ... LIMIT / LIMIT without ORDER BY) not matching "
                  "any sample: %s; row counts differing from the first sample: %s" % (
                      c, pas, len(base_samples), ", ".join(det) or "none", ", ".join(nondet) or "none",
                      ", ".join(rows_diff) or "none"))
    md.append("* invariants (`total = pruned + no_rows + with_rows + partial + not_reached`, `pruned = minmax + "
              "additional + predicate_cache`, no unattributed pruning), `scanned_with_rows` / `rows_passed` / total "
              "equal to the baseline for every query and pass: %s" % (
                  "0 violations" if not problems else "%d problems: %s" % (len(problems), "; ".join(problems[:20]))))
    md += ["", "## Totals over the 43 queries (1 thread)", "",
           "| config | pass | row groups | pruned | min/max | 3-gram | pred. cache | rowid | **wasted** | with rows |",
           "|---|---|---|---|---|---|---|---|---|---|"]
    for r in tot_rows:
        md.append("| %s | %s | %d | %d | %d | %d | %d | %d | **%d** | %d |" % (
            r["config"], r["pass"], r["total_row_groups"], r["pruned"], r["by_minmax"], r["by_ngram"],
            r["by_predcache"], r["by_rowid"], r["scanned_no_rows"], r["scanned_with_rows"]))
    for p, name in ((1, "Cold pass"), (2, "Warm pass")):
        md += ["", "## %s, per query (q01..q43 in execution order)" % name, "",
               "| query | total | " + " | ".join(LABELS[c] for c in CONFIGS) + " |",
               "|---|---|" + "---|" * len(CONFIGS)]
        for q in QIDS:
            md.append("| %s | %d | %s |" % (q, agg[("baseline_cmb", p, q)]["total_row_groups"],
                                           " | ".join(fmt(agg[(c, p, q)]) for c in CONFIGS)))
        tline = []
        for c in CONFIGS:
            t = collections.Counter()
            for q in QIDS:
                t.update(agg[(c, p, q)])
            tline.append(fmt(t))
        md.append("| **sum** | %d | %s |" % (sum(agg[("baseline_cmb", p, q)]["total_row_groups"] for q in QIDS),
                                             " | ".join(tline)))
    if timing_rows:
        md += ["", "## Timing (8 threads; machine otherwise idle, still +-10-30 % noise at this scale; the first, loaded-machine sessions are kept as `loaded_*` raw dirs and not used)",
               "", "Engine-side elapsed ms per query; %d session(s) per config, run interleaved (config order "
               "repeated); cold = median of round 1 of each session (empty predicate cache), warm = median of rounds "
               "2-4 of all sessions. Only" % reps_used + " queries where any config differs from the baseline by more than 20 % "
               "and 1 ms are listed; full table in `timing.csv`.", "",
               "| query | " + " | ".join("%s cold / warm" % LABELS[c] for c in CONFIGS) + " |",
               "|---|" + "---|" * len(CONFIGS)]
        sums = {c: [0.0, 0.0] for c in CONFIGS}
        for q in QIDS:
            vals = {c: tdata.get((c, q), (None, None)) for c in CONFIGS}
            for c in CONFIGS:
                if vals[c][0] is not None:
                    sums[c][0] += vals[c][0]
                if vals[c][1] is not None:
                    sums[c][1] += vals[c][1]
            bw = vals["baseline_cmb"][1]
            interesting = bw is not None and any(
                v[1] is not None and abs(v[1] - bw) > max(1.0, 0.2 * bw) for v in vals.values())
            if interesting:
                md.append("| %s | %s |" % (q, " | ".join(
                    "%.1f / %.1f" % v if v[0] is not None and v[1] is not None else "-" for v in vals.values())))
        md.append("| **sum (43 q.)** | %s |" % " | ".join("%.0f / %.0f" % tuple(sums[c]) for c in CONFIGS))
    with open(os.path.join(OUT, "summary.md"), "w") as f:
        f.write("\n".join(md) + "\n")
    print("\n".join(md[:60]))
    if problems:
        print("PROBLEMS:", *problems[:30], sep="\n  ")


if __name__ == "__main__":
    main()
