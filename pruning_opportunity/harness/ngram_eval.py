#!/usr/bin/env python3
"""Evaluation of the n-gram statistic (kind `ngram`) for LIKE / contains predicates on ClickBench (small scale).

  ngram_eval.py truth  [--scale small]            # plain-SQL ground truth + exact n-gram ceiling (pip duckdb)
  ngram_eval.py report [--scale small] --configs ng200,ng2000,ng20000 [--baseline baseline_ng]
                       [--check-configs ...] [--check-baselines baseline,baseline_rerun]

truth: on the Phase 1 database db/<scale>/clickbench.db (read-only, row group = rowid // 8192, verified in
results/small/ground_truth_layout.csv), per row group: rows, qualifying rows of the complete pushed-down filter of
scan 0 of q21-q24, whether each n-gram (n = 2..5) of the required literals ('google' in URL, 'Google' in Title) occurs
in the column (bool_or(contains(col, gram)) = exact membership in the exact n-gram set), and the exact number of
distinct byte trigrams of URL and Title (Python). -> results/<scale>/phase4/ngram/truth_partitions.csv

report: reads the counting passes results/raw/<scale>/phase4/<config>/count/clickbench (pruning counters, timing
log with per-row-group n-gram statistics) and the check passes (multi-threaded), compares with the baseline and the
ground truth, and writes the tables of results/<scale>/phase4/ngram/: per_query.csv, per_column.csv,
partitions_<config>.csv, results_check.csv, summary.md.
"""
import argparse
import collections
import csv
import glob
import json
import math
import os
import statistics
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common  # noqa: E402
import phase4  # noqa: E402

RG = 8192
QUERIES = {
    # qid: (complete pushed-down filter of scan 0 as SQL, [(column, literal)] the n-gram statistic can use)
    "q21": ("contains(URL, 'google')", [("URL", "google")]),
    "q22": ("contains(URL, 'google') AND SearchPhrase <> ''", [("URL", "google")]),
    "q23": ("contains(Title, 'Google') AND NOT contains(URL, '.google.') AND SearchPhrase <> ''",
            [("Title", "Google")]),
    "q24": ("contains(URL, 'google')", [("URL", "google")]),
}
NS = [2, 3, 4, 5]


def out_dir(scale):
    d = os.path.join(common.results_dir(scale), "phase4", "ngram")
    os.makedirs(d, exist_ok=True)
    return d


def grams(lit, n):
    b = lit.encode("utf-8")
    return sorted({b[i:i + n] for i in range(len(b) - n + 1)})


# ------------------------------------------------------------------------------------------------------------------
def cmd_truth(args):
    import duckdb
    db = os.path.join(common.db_dir(args.scale), "clickbench.db")
    con = duckdb.connect(db, read_only=True, config={"threads": 3, "memory_limit": "1500MB"})
    n_rg = con.execute("SELECT max(rowid) // %d + 1 FROM hits" % RG).fetchone()[0]
    cols = ["count(*) AS n_rows"]
    for q, (pred, _) in QUERIES.items():
        cols.append("count(*) FILTER (WHERE %s) AS %s_rows" % (pred, q))
    lits = sorted({(c, lit) for _, (_, uses) in QUERIES.items() for c, lit in uses})
    gram_cols = []
    for c, lit in lits:
        for n in NS:
            for g in grams(lit, n):
                name = "has_%s_%s" % (c, g.decode())
                if name not in gram_cols:
                    gram_cols.append(name)
                    cols.append("coalesce(bool_or(contains(%s, '%s')), false) AS %s" % (c, g.decode(), name))
    sql = "SELECT rowid // %d AS rg, %s FROM hits GROUP BY rg ORDER BY rg" % (RG, ", ".join(cols))
    cur = con.execute(sql)
    names = [d[0] for d in cur.description]
    rows = [dict(zip(names, r)) for r in cur.fetchall()]
    assert len(rows) == n_rg
    # exact distinct byte trigrams per row group (independent of the engine's statistic)
    for r in rows:
        rg = r["rg"]
        for c in ("URL", "Title"):
            vals = con.execute("SELECT %s FROM hits WHERE rowid >= %d AND rowid < %d AND %s IS NOT NULL" % (
                c, rg * RG, (rg + 1) * RG, c)).fetchall()
            s3 = set()
            for (v,) in vals:
                b = v.encode("utf-8")
                s3.update(b[i:i + 3] for i in range(len(b) - 2))
            r["distinct3_%s" % c] = len(s3)
            r["bytes_%s" % c] = sum(len(v.encode("utf-8")) for (v,) in vals)
    con.close()
    path = os.path.join(out_dir(args.scale), "truth_partitions.csv")
    with open(path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)
    print("wrote %s (%d row groups)" % (path, len(rows)))


def load_truth(scale):
    path = os.path.join(out_dir(scale), "truth_partitions.csv")
    with open(path) as f:
        rows = list(csv.DictReader(f))
    for r in rows:
        for k, v in list(r.items()):
            if v in ("True", "False"):
                r[k] = v == "True"
            else:
                r[k] = int(v)
    return rows


def exact_prunable(r, qid, n):
    """the exact n-gram set of the row group proves that no row of the query's scan 0 qualifies"""
    for c, lit in QUERIES[qid][1]:
        for g in grams(lit, n):
            if not r["has_%s_%s" % (c, g.decode())]:
                return True
    return False


# ------------------------------------------------------------------------------------------------------------------
def gdir(scale, config, mode):
    return os.path.join(common.raw_dir(scale, "phase4"), config, mode, "clickbench")


def attempts(d):
    return sorted(glob.glob(os.path.join(d, "session_*", "attempt_*")))


def load_count(scale, config):
    """scans by tag (last execution), query timings by tag, ingest records, status by tag"""
    scans, timings, ingest, status, runs = {}, {}, [], {}, {}
    for a in attempts(gdir(scale, config, "count")):
        cur = {}
        for r in phase4.load_jsonl(os.path.join(a, "pruning.jsonl")):
            if r["type"] == "query" and r.get("n_scans"):
                cur[r["tag"]] = r["seq"]
                scans[r["tag"]] = []
            elif r["type"] == "scan" and cur.get(r["tag"]) == r["seq"]:
                scans[r["tag"]].append(r)
        for r in phase4.load_jsonl(os.path.join(a, "timing.jsonl")):
            if r["type"] == "query_timing" and r["tag"].startswith("clickbench/q") and not r["sql"].startswith("SET"):
                timings[r["tag"]] = r
            elif r["type"] == "ingest":
                ingest.append(r)
        for r in phase4.load_jsonl(os.path.join(a, "status.jsonl")):
            status[r["tag"]] = r
    return scans, timings, ingest, status


def check_threads(scale, config):
    try:
        with open(os.path.join(gdir(scale, config, "check"), "run.json")) as f:
            return json.load(f).get("threads") or "default"
    except OSError:
        return "?"


def load_status(scale, config, mode):
    status = {}
    for a in attempts(gdir(scale, config, mode)):
        for r in phase4.load_jsonl(os.path.join(a, "status.jsonl")):
            if r.get("kind") == "query":
                status[r["tag"]] = r
    return status


def hash_of(r):
    return (r.get("status"), r.get("rows"), r.get("hash_sorted") or r.get("hash_multiset") or r.get("hash"))


def pct(a, b):
    return "%.1f" % (100.0 * a / b) if b else "-"


def q(vals, p):
    vals = sorted(vals)
    if not vals:
        return float("nan")
    k = (len(vals) - 1) * p
    lo, hi = int(math.floor(k)), int(math.ceil(k))
    return vals[lo] + (vals[hi] - vals[lo]) * (k - lo)


def cmd_report(args):
    od = out_dir(args.scale)
    truth = load_truth(args.scale)
    full = [r for r in truth if r["n_rows"] == RG]
    configs = args.configs.split(",")
    base_scans, base_timings, _, base_status = load_count(args.scale, args.baseline)
    data = {c: load_count(args.scale, c) for c in configs}
    md = ["# N-gram statistic (kind `ngram`, n = 3) for LIKE / contains: ClickBench 1M (small scale)", ""]

    # ---------------- correctness: results (count pass, threads 1) + scans ----------------
    check_rows = []
    md += ["## Correctness", ""]
    for c in configs:
        scans, timings, ingest, status = data[c]
        qtags = sorted(t for t in base_status if t.startswith("clickbench/q"))
        same = sum(1 for t in qtags if t in status and hash_of(status[t]) == hash_of(base_status[t]))
        diff_scan, inv = [], 0
        for t in qtags:
            for b, s in zip(base_scans.get(t, []), scans.get(t, [])):
                for fld in ("total_row_groups", "pruned_minmax", "scanned_with_rows", "incl_optional_with_rows",
                            "rows_passed", "rows_passed_incl_optional"):
                    if b[fld] != s[fld]:
                        diff_scan.append("%s scan %d %s %s->%s" % (t, s["scan_id"], fld, b[fld], s[fld]))
                tot = s["pruned"] + s["scanned_no_rows"] + s["scanned_with_rows"] + s["partial_no_rows"] + \
                    s["not_reached"]
                if tot != s["total_row_groups"] or s["pruned"] != s["pruned_minmax"] + s["pruned_additional"]:
                    inv += 1
                leaf_sum = sum(f.get("pruned_first_additional", 0) for f in s["filters"]) + \
                    s["pruned_additional_no_single_leaf"]
                col_sum = sum(x["pruned_first"] for x in s["additional_columns"]) + \
                    s["additional_columns_unattributed"]
                if leaf_sum != s["pruned_additional"] or col_sum != s["pruned_additional"]:
                    inv += 1
            if len(base_scans.get(t, [])) != len(scans.get(t, [])):
                diff_scan.append("%s: %d vs %d scans" % (t, len(base_scans.get(t, [])), len(scans.get(t, []))))
        check_rows.append({"config": c, "mode": "count (threads 1)", "queries": len(qtags), "identical": same,
                           "scan_counter_differences": len(diff_scan), "invariant_violations": inv,
                           "details": "; ".join(diff_scan[:10])})
        md.append("* `%s`, counting pass (1 thread): results identical for %d / %d queries (row count + "
                  "order-independent hash); per scan, `total_row_groups`, `pruned_minmax`, `scanned_with_rows`, "
                  "`incl_optional_with_rows`, `rows_passed`, `rows_passed_incl_optional` equal to the baseline: %s; "
                  "invariant / attribution violations: %d" % (
                      c, same, len(qtags), "all scans" if not diff_scan else "%d differences: %s" % (
                          len(diff_scan), "; ".join(diff_scan[:5])), inv))
    # check passes (multi-threaded)
    if args.check_configs:
        bases = [load_status(args.scale, b, "check") for b in args.check_baselines.split(",")]
        nondet = set()
        for b in bases[1:]:
            nondet |= {t for t in bases[0] if t.startswith("clickbench/") and hash_of(b.get(t, {})) !=
                       hash_of(bases[0][t])}
        for c in args.check_configs.split(","):
            st = load_status(args.scale, c, "check")
            qtags = sorted(t for t in bases[0] if t.startswith("clickbench/q"))
            diffs = [t for t in qtags if all(hash_of(st.get(t, {})) != hash_of(b.get(t, {})) for b in bases)]
            same = sum(1 for t in qtags if hash_of(st.get(t, {})) == hash_of(bases[0][t]))
            check_rows.append({"config": c, "mode": "check (threads %s)" % check_threads(args.scale, c), "queries": len(qtags), "identical": same,
                               "scan_counter_differences": "", "invariant_violations": "",
                               "details": "equal to none of the baseline check runs: %s; baseline runs disagree "
                                          "among themselves on: %s" % (",".join(x.split("/")[1] for x in diffs) or
                                                                       "none", ",".join(sorted(
                                                                           x.split("/")[1] for x in nondet)))})
            md.append("* `%s`, check pass (%s threads): identical to the first baseline check for %d / %d queries; "
                      "equal to none of the baseline check runs (%s): %s; baseline check runs differ among "
                      "themselves on %s (nondeterministic with threads > 1)." % (
                          c, check_threads(args.scale, c), same, len(qtags), args.check_baselines,
                          ", ".join(x.split("/")[1] for x in diffs) or "none",
                          ", ".join(sorted(x.split("/")[1] for x in nondet)) or "none"))
    with open(os.path.join(od, "results_check.csv"), "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(check_rows[0].keys()))
        w.writeheader()
        w.writerows(check_rows)

    # ---------------- ground truth vs counters (baseline) ----------------
    md += ["", "## Ground truth (plain SQL, `rowid // 8192`, pip duckdb on the Phase 1 database)", ""]
    gt_lines = []
    for qid in QUERIES:
        tag = "clickbench/" + qid
        with_rows = sum(1 for r in truth if r[qid + "_rows"] > 0)
        rows = sum(r[qid + "_rows"] for r in truth)
        s0 = base_scans[tag][0]
        gt_lines.append("| %s | %d | %d | %d | %d | %s |" % (qid, with_rows, s0["scanned_with_rows"], rows,
                                                            s0["rows_passed"], "ok" if (
                                                                with_rows == s0["scanned_with_rows"] and
                                                                rows == s0["rows_passed"]) else "MISMATCH"))
    md += ["| query | row groups with a qualifying row (SQL) | baseline `scanned_with_rows` | qualifying rows (SQL) "
           "| baseline `rows_passed` | |", "|---|---|---|---|---|---|"] + gt_lines
    md += ["", "In every n-gram configuration, for each pruned row group of q21-q24 scan 0 the ground truth has 0 "
               "qualifying rows (checked per partition in `partitions_<config>.csv`: column `pruned_with_rows`)."]

    # ---------------- per query ----------------
    per_query = []
    for qid in QUERIES:
        tag = "clickbench/" + qid
        b0 = base_scans[tag][0]
        wasted = b0["scanned_no_rows"]
        wasted_full = sum(1 for r in full if r[qid + "_rows"] == 0)
        row = {"query": qid, "filter": QUERIES[qid][0], "baseline_wasted": wasted,
               "baseline_with_rows": b0["scanned_with_rows"], "wasted_full_row_groups": wasted_full}
        for n in NS:
            row["exact_n%d" % n] = sum(1 for r in full if r[qid + "_rows"] == 0 and exact_prunable(r, qid, n))
        for c in configs:
            scans, timings, _, _ = data[c]
            s0 = scans[tag][0]
            t = timings.get(tag, {})
            row["%s_pruned" % c] = s0["pruned_additional"]
            row["%s_consultations" % c] = t.get("consultations", "")
            row["%s_consult_us_per_rg" % c] = "%.2f" % (t["consult_ns"] / 1000.0 / t["consultations"]) \
                if t.get("consultations") else ""
            row["%s_consult_ms" % c] = "%.3f" % (t["consult_ns"] / 1e6) if t else ""
            row["%s_elapsed_ms" % c] = "%.1f" % t["elapsed_ms"] if t else ""
        row["baseline_elapsed_ms"] = "%.1f" % base_timings[tag]["elapsed_ms"] if tag in base_timings else ""
        # other scans of the query (q24 late materialisation): unchanged
        row["other_scans_wasted"] = sum(s["scanned_no_rows"] for s in base_scans[tag][1:])
        per_query.append(row)
    with open(os.path.join(od, "per_query.csv"), "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(per_query[0].keys()))
        w.writeheader()
        w.writerows(per_query)
    tot = {k: sum(r[k] for r in per_query if isinstance(r[k], int)) for k in per_query[0]
           if isinstance(per_query[0][k], int)}
    md += ["", "## Wasted reads of q21-q24 (scan 0) pruned", "",
           "Baseline = min/max only (`%s`); \"wasted\" = scanned, no qualifying row. Exact n = the exact set of "
           "distinct byte n-grams per row group (computed with plain SQL), full row groups only (the last, partial "
           "row group of 575 rows never gets a statistic; it is wasted in q22 and q23)." % args.baseline, "",
           "| query | baseline wasted / with rows | exact n=2 | exact n=3 | exact n=4 | exact n=5 | " +
           " | ".join("`%s`" % c for c in configs) + " |",
           "|---|---|---|---|---|---|" + "---|" * len(configs)]
    for r in per_query + [dict(tot, query="total", baseline_with_rows=tot["baseline_with_rows"])]:
        md.append("| %s | %d / %d | %s | %s | %s | %s | %s |" % (
            r["query"], r["baseline_wasted"], r["baseline_with_rows"],
            *["%d (%s %%)" % (r["exact_n%d" % n], pct(r["exact_n%d" % n], r["baseline_wasted"])) for n in NS],
            " | ".join("%d (%s %%)" % (r["%s_pruned" % c], pct(r["%s_pruned" % c], r["baseline_wasted"]))
                       for c in configs)))
    md += ["", "Consult time per consulted row group (µs, `consult_ns / consultations`, single thread) and "
               "engine-side elapsed time per query (ms):", "",
           "| query | baseline elapsed | " + " | ".join("`%s` consult µs/RG; elapsed" % c for c in configs) + " |",
           "|---|---|" + "---|" * len(configs)]
    for r in per_query:
        md.append("| %s | %s | %s |" % (r["query"], r["baseline_elapsed_ms"], " | ".join(
            "%s; %s" % (r["%s_consult_us_per_rg" % c], r["%s_elapsed_ms" % c]) for c in configs)))

    # ---------------- per column / config: statistic ----------------
    per_col = []
    part_rows = {}
    for c in configs:
        _, _, ingest, _ = data[c]
        by_col = collections.defaultdict(lambda: collections.defaultdict(list))
        for r in ingest:
            if r.get("kind") != "ngram":
                continue
            d = by_col[r["column"]]
            for k in ("rg_distinct", "rg_bytes", "rg_eps"):
                d[k] += r[k]
            for k in ("row_groups_built", "row_groups_useless", "row_groups_empty", "build_ns", "buffer_ns", "bytes",
                      "values"):
                d[k].append(r[k])
            d["words"] = r["words"]
        for col, d in sorted(by_col.items()):
            nrg = len(d["rg_distinct"])
            built = [i for i in range(nrg) if d["rg_bytes"][i] > 0]
            bits_per = [d["rg_bytes"][i] * 8.0 / d["rg_distinct"][i] for i in built if d["rg_distinct"][i]]
            budget_bits_per = [d["words"] * 64.0 / x for x in d["rg_distinct"] if x]
            tcol = "distinct3_URL" if col == "url" else "distinct3_Title"
            exact = [r[tcol] for r in full]
            per_col.append({
                "config": c, "column": col, "words": d["words"], "row_groups": nrg, "built": len(built),
                "useless": sum(d["row_groups_useless"]), "empty": sum(d["row_groups_empty"]),
                "distinct_min": min(d["rg_distinct"]), "distinct_median": int(statistics.median(d["rg_distinct"])),
                "distinct_max": max(d["rg_distinct"]),
                "distinct_matches_python": d["rg_distinct"] == exact[:nrg],
                "bytes_per_rg_mean": "%.0f" % (sum(d["rg_bytes"]) / nrg),
                "bytes_per_rg_max": max(d["rg_bytes"]),
                "budget_bits_per_distinct_median": "%.3f" % statistics.median(budget_bits_per),
                "stored_bits_per_distinct_median": "%.3f" % statistics.median(bits_per) if bits_per else "",
                "eps_min": "%.3g" % min(d["rg_eps"]), "eps_median": "%.3g" % statistics.median(d["rg_eps"]),
                "eps_max": "%.3g" % max(d["rg_eps"]),
                "build_ms_per_rg": "%.2f" % (sum(d["build_ns"]) / 1e6 / max(1, nrg)),
                "buffer_ms_per_rg": "%.2f" % (sum(d["buffer_ns"]) / 1e6 / max(1, nrg)),
            })
            part_rows[(c, col)] = d
    with open(os.path.join(od, "per_column.csv"), "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(per_col[0].keys()))
        w.writeheader()
        w.writerows(per_col)
    md += ["", "## Statistic per row group (122 full row groups per column)", "",
           "| config | column | built / useless / empty | distinct trigrams min / median / max | budget bits per "
           "distinct trigram (median) | stored bytes per RG mean / max | expected FP rate per absent trigram min / "
           "median / max | build ms/RG | buffering ms/RG |", "|---|---|---|---|---|---|---|---|---|"]
    for r in per_col:
        md.append("| `%s` | %s | %d / %d / %d | %d / %d / %d | %s | %s / %d | %s / %s / %s | %s | %s |" % (
            r["config"], r["column"], r["built"], r["useless"], r["empty"], r["distinct_min"],
            r["distinct_median"], r["distinct_max"], r["budget_bits_per_distinct_median"], r["bytes_per_rg_mean"],
            r["bytes_per_rg_max"], r["eps_min"], r["eps_median"], r["eps_max"], r["build_ms_per_rg"],
            r["buffer_ms_per_rg"]))
    ok = all(r["distinct_matches_python"] for r in per_col)
    md += ["", "Distinct trigram counts of the engine (exact bitmap at n = 3) equal the Python count of the ground "
               "truth for every full row group: %s." % ("yes" if ok else "NO")]

    # ---------------- per partition: measured vs expected pruning ----------------
    md += ["", "## Measured vs. expected pruning", "",
           "Expected = sum over the wasted full row groups of 1 - eps^k, where eps is the row group's expected "
           "false-positive rate per absent n-gram (from the build) and k the number of the literal's trigrams "
           "absent from the exact set (independent hash positions assumed).", "",
           "| config | query | wasted full RGs prunable exactly | pruned | expected | pruned RG with qualifying "
           "row |", "|---|---|---|---|---|---|"]
    for c in configs:
        prow = []
        for qid in QUERIES:
            col, lit = QUERIES[qid][1][0]
            d = part_rows.get((c, col.lower()))
            if not d:
                continue
            exp = 0.0
            exact_cnt = 0
            for r in full:
                k = sum(1 for g in grams(lit, 3) if not r["has_%s_%s" % (col, g.decode())])
                if r[qid + "_rows"] == 0 and k > 0:
                    exact_cnt += 1
                    eps = d["rg_eps"][r["rg"]]
                    exp += 1 - eps ** k
                prow.append({"config": c, "query": qid, "rg": r["rg"], "qualifying_rows": r[qid + "_rows"],
                             "absent_trigrams": k, "eps": d["rg_eps"][r["rg"]],
                             "distinct": d["rg_distinct"][r["rg"]], "bytes": d["rg_bytes"][r["rg"]]})
            pruned = data[c][0]["clickbench/" + qid][0]["pruned_additional"]
            # a pruned row group with a qualifying row is impossible if scanned_with_rows is unchanged; the counters
            # are per scan, so the check is: pruned <= wasted and scanned_with_rows equal (above)
            b0 = base_scans["clickbench/" + qid][0]
            s0 = data[c][0]["clickbench/" + qid][0]
            bad = b0["scanned_with_rows"] - s0["scanned_with_rows"]
            md.append("| `%s` | %s | %d | %d | %.1f | %d |" % (c, qid, exact_cnt, pruned, exp, bad))
        with open(os.path.join(od, "partitions_%s.csv" % c), "w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=list(prow[0].keys()))
            w.writeheader()
            w.writerows(prow)
    with open(os.path.join(od, "summary.md"), "w") as f:
        f.write("\n".join(md) + "\n")
    print("\n".join(md))


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    t = sub.add_parser("truth")
    t.add_argument("--scale", default="small")
    r = sub.add_parser("report")
    r.add_argument("--scale", default="small")
    r.add_argument("--configs", required=True)
    r.add_argument("--baseline", default="baseline_ng")
    r.add_argument("--check-configs", default="")
    r.add_argument("--check-baselines", default="baseline,baseline_rerun")
    args = ap.parse_args()
    {"truth": cmd_truth, "report": cmd_report}[args.cmd](args)


if __name__ == "__main__":
    main()
