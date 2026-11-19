#!/usr/bin/env python3
"""Aggregate Phase 4 runs (phase4.py) into tables: baseline vs. selective configurations side by side.

Input : results/raw/<scale>/phase4/<config>/<mode>/<group>/session_<k>/attempt_<a>/{status,timing,pruning}.jsonl
Output: results/<scale>/phase4/
  counts_per_query.csv    count mode: per config and query, summed over the query's table scans: row groups total,
                          pruned by min/max, pruned by additional statistics, scanned without / with qualifying rows,
                          partial / not reached, incl.-optional no-rows, rows passed; invariant check
  counts_per_setup.csv    the same summed per setup, configs side by side with the baseline; share of the baseline's
                          "scanned without rows" row groups that each config prunes with additional statistics
  results_check.csv       per config / mode / query: result hash equal to the baseline (count: 1 thread, check:
                          default threads), and equal with-rows counters
  runtimes_per_query.csv  time mode: per config and query: median / min engine-side elapsed ms over all rounds and
                          sessions, median stat-consultation time and count, row groups pruned by additional stats
  runtimes_per_setup.csv  per setup: sum of the per-query medians per config and speedup vs. baseline
  ingest.csv              per config / group / table: COPY time (median over sessions), per selected column: time to
                          buffer values and build statistics (median over sessions), bytes and row groups built
  summary.md              Markdown version of the setup-level tables
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

COUNTERS = ["total_row_groups", "pruned", "pruned_minmax", "pruned_additional", "scanned", "scanned_no_rows",
            "scanned_with_rows", "partial_no_rows", "not_reached", "incl_optional_no_rows",
            "incl_optional_with_rows", "rows_passed", "rows_passed_incl_optional", "pruned_unattributed"]


def attempts(gdir):
    return sorted(glob.glob(os.path.join(gdir, "session_*", "attempt_*")))


def session_of(adir):
    return os.path.basename(os.path.dirname(adir))


def load_counts(gdir):
    """tag -> summed counters (last execution of every tag wins), plus invariant violations"""
    by_tag = {}
    violations = []
    for adir in attempts(gdir):
        queries, scans = {}, collections.defaultdict(list)
        for r in phase4.load_jsonl(os.path.join(adir, "pruning.jsonl")):
            key = (r.get("session"), r.get("seq"))
            if r["type"] == "query":
                queries[key] = r
            elif r["type"] == "scan":
                scans[key].append(r)
        for key, q in queries.items():
            tag = q.get("tag") or ""
            if not tag or "/ingest/" in tag or q.get("sql", "").lstrip().upper().startswith(("SET ", "RESET ")):
                continue
            sums = collections.Counter()
            sums["scans"] = len(scans.get(key, []))
            for s in scans.get(key, []):
                for c in COUNTERS:
                    sums[c] += s.get(c, 0)
                total = s["total_row_groups"]
                parts = s["pruned"] + s["scanned_no_rows"] + s["scanned_with_rows"] + s["partial_no_rows"] + \
                    s["not_reached"]
                if total != parts or s["pruned"] != s.get("pruned_minmax", s["pruned"]) + s.get(
                        "pruned_additional", 0):
                    violations.append((tag, s["scan_id"]))
            sums["error"] = 1 if q.get("error") else 0
            by_tag[tag] = sums
    return by_tag, violations


def load_status(gdir, kind="query"):
    """item -> status record (last attempt wins)"""
    res = {}
    for adir in attempts(gdir):
        for r in phase4.load_jsonl(os.path.join(adir, "status.jsonl")):
            if r.get("kind") == kind:
                res[r["item"]] = r
    return res


def load_walls(gdir):
    """harness-side wall times (also available for binaries without the timing log, e.g. stock):
    (query key -> [ms], ingest table -> [ms, one per session])"""
    q = collections.defaultdict(list)
    ingest = collections.defaultdict(dict)
    for adir in attempts(gdir):
        sess = session_of(adir)
        for r in phase4.load_jsonl(os.path.join(adir, "status.jsonl")):
            if r["status"] != "ok":
                continue
            if r.get("kind") == "query":
                q[r["item"].split("#")[0]].append(1000.0 * r["wall_s"])
            elif r.get("kind") == "ingest":
                ingest[r["item"].split(":", 1)[1]].setdefault(sess, 1000.0 * r["wall_s"])
    return q, {t: list(v.values()) for t, v in ingest.items()}


def load_timing(gdir):
    """returns (query samples: key -> list of dicts, ingest: session -> {table: elapsed_ms},
    columns: session -> {(table, column): dict})"""
    samples = collections.defaultdict(list)
    ingest = collections.defaultdict(dict)
    columns = collections.defaultdict(dict)
    for adir in attempts(gdir):
        sess = session_of(adir)
        for r in phase4.load_jsonl(os.path.join(adir, "timing.jsonl")):
            tag = r.get("tag") or ""
            if r["type"] == "query_timing":
                if "/ingest/" in tag:
                    table = tag.split("/ingest/")[1]
                    if table not in ("done",) and r.get("sql", "").lstrip().upper().startswith(("COPY", "CHECKPOINT")):
                        ingest[sess].setdefault(table, r["elapsed_ms"])  # first complete attempt of the session
                    continue
                if not tag or r.get("sql", "").lstrip().upper().startswith(("SET ", "RESET ")):
                    continue
                samples[tag.split("#")[0]].append(r)
            elif r["type"] == "ingest":
                key = (r["table"], r["column"])
                if key in columns[sess]:
                    continue
                columns[sess][key] = r
    return samples, ingest, columns


def med(values):
    return statistics.median(values) if values else None


def fmt(v, digits=2):
    if v is None:
        return ""
    if isinstance(v, float):
        return ("%." + str(digits) + "f") % v
    return str(v)


def write_csv(path, header, rows):
    with open(path, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(header)
        for r in rows:
            w.writerow([fmt(x, 4) if isinstance(x, float) else ("" if x is None else x) for x in r])


def md_table(header, rows):
    out = ["| " + " | ".join(header) + " |", "|" + "---|" * len(header)]
    for r in rows:
        out.append("| " + " | ".join(fmt(x) if isinstance(x, float) else ("" if x is None else str(x))
                                     for x in r) + " |")
    return "\n".join(out)


def setup_of(tag):
    return tag.split("/")[0]


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--scale", required=True)
    ap.add_argument("--configs", default=None, help="comma-separated configs (default: all found; baseline first)")
    ap.add_argument("--baseline", default="baseline")
    args = ap.parse_args()

    root = os.path.join(common.raw_dir(args.scale, "phase4"))
    found = sorted(d for d in os.listdir(root) if os.path.isdir(os.path.join(root, d))) if os.path.isdir(root) else []
    configs = args.configs.split(",") if args.configs else found
    if args.baseline in configs:
        configs = [args.baseline] + [c for c in configs if c != args.baseline]
    out_dir = os.path.join(common.results_dir(args.scale), "phase4")
    os.makedirs(out_dir, exist_ok=True)
    group_names = list(phase4.groups())
    setup_order = [s.name for g in phase4.groups().values() for s in g]
    md = ["# Phase 4: selective pruning statistics (%s scale)" % args.scale, ""]
    runs = {}
    for cfg in configs:
        for mode in ("count", "check", "time"):
            for g in group_names:
                gdir = os.path.join(root, cfg, mode, g)
                if os.path.isdir(gdir):
                    runs[(cfg, mode, g)] = gdir
    for (cfg, mode, g), gdir in sorted(runs.items()):
        rj = os.path.join(gdir, "run.json")
        if os.path.exists(rj) and mode == "count":
            md.append("* `%s`: %s" % (cfg, (json.load(open(rj)).get("columns") or "(no selective statistics)")[:300]))
    md = list(collections.OrderedDict.fromkeys(md))
    md.append("")

    # ---------------------------------------------------------------- counts
    counts = {}       # cfg -> tag -> counters
    violations = {}
    for (cfg, mode, g), gdir in runs.items():
        if mode != "count":
            continue
        c, v = load_counts(gdir)
        counts.setdefault(cfg, {}).update(c)
        violations.setdefault(cfg, []).extend(v)
    rows = []
    for cfg in configs:
        for tag in sorted(counts.get(cfg, {}), key=lambda t: (setup_order.index(setup_of(t))
                                                              if setup_of(t) in setup_order else 999, t)):
            c = counts[cfg][tag]
            rows.append([cfg, setup_of(tag), tag.split("/", 1)[1], c["scans"]] + [c[k] for k in COUNTERS] +
                        [c["error"]])
    write_csv(os.path.join(out_dir, "counts_per_query.csv"),
              ["config", "setup", "qid", "scans"] + COUNTERS + ["error"], rows)

    base = counts.get(args.baseline, {})
    setup_rows, md_rows = [], []
    per_setup = {}
    for cfg in configs:
        agg = collections.defaultdict(collections.Counter)
        nq = collections.Counter()
        for tag, c in counts.get(cfg, {}).items():
            agg[setup_of(tag)].update(c)
            nq[setup_of(tag)] += 1
        per_setup[cfg] = (agg, nq)
    base_agg = per_setup.get(args.baseline, ({}, {}))[0]
    for setup in setup_order:
        for cfg in configs:
            agg, nq = per_setup[cfg]
            if setup not in agg:
                continue
            c = agg[setup]
            b = base_agg.get(setup)
            share = share_io = None
            with_rows_equal = None
            if b is not None:
                # only over the queries present in both passes (a config may have run a subset)
                common_tags = [t for t, x in counts[cfg].items() if setup_of(t) == setup and t in base]
                b_no_rows = sum(base[t]["scanned_no_rows"] for t in common_tags)
                c_no_rows = sum(counts[cfg][t]["scanned_no_rows"] for t in common_tags)
                b_io = sum(base[t]["incl_optional_no_rows"] for t in common_tags)
                c_pruned = sum(counts[cfg][t]["pruned_additional"] for t in common_tags)
                # share of the baseline's "scanned, no rows" row groups that are no longer scanned (pruned by the
                # statistics; min/max pruning is identical), and of the baseline's "incl. optional filters, no
                # rows" row groups (pruning via optional join filters can also remove row groups whose rows pass
                # the non-optional filters only)
                if b_no_rows:
                    share = 100.0 * (b_no_rows - c_no_rows) / b_no_rows
                if b_io:
                    share_io = 100.0 * c_pruned / b_io
                with_rows_equal = all(counts[cfg][t]["scanned_with_rows"] == base[t]["scanned_with_rows"]
                                      for t in common_tags)
            setup_rows.append([setup, cfg, nq[setup], c["total_row_groups"], c["pruned_minmax"], c["pruned_additional"],
                               c["scanned_no_rows"], c["scanned_with_rows"], c["partial_no_rows"], c["not_reached"],
                               c["incl_optional_no_rows"], share, share_io, with_rows_equal])
            md_rows.append([setup, cfg, nq[setup], c["total_row_groups"], c["pruned_minmax"], c["pruned_additional"],
                            c["scanned_no_rows"], c["scanned_with_rows"], c["incl_optional_no_rows"], share,
                            share_io])
    write_csv(os.path.join(out_dir, "counts_per_setup.csv"),
              ["setup", "config", "queries", "total_row_groups", "pruned_minmax", "pruned_additional",
               "scanned_no_rows", "scanned_with_rows", "partial_no_rows", "not_reached", "incl_optional_no_rows",
               "pct_of_baseline_no_rows_pruned_by_additional", "pct_of_baseline_incl_optional_no_rows_pruned",
               "with_rows_equal_baseline"], setup_rows)
    md += ["## Row groups (counting pass, threads=1, sums over all queries and scans)", "",
           md_table(["setup", "config", "queries", "total", "pruned min/max", "pruned additional",
                     "scanned, no rows", "scanned, with rows", "incl. optional, no rows",
                     "% of baseline no-rows pruned (common queries)", "% of baseline incl.-optional no-rows pruned"],
                    md_rows), ""]
    viol_lines = ["%s: %d invariant violations %s" % (cfg, len(v), v[:5]) for cfg, v in violations.items()]
    md += ["Invariant `total = pruned + no_rows + with_rows + partial + not_reached`, "
           "`pruned = pruned_minmax + pruned_additional`: " + ("; ".join(viol_lines) or "no counting runs"), ""]

    # ---------------------------------------------------------------- result check
    status = {}
    for (cfg, mode, g), gdir in runs.items():
        if mode in ("count", "check"):
            status.setdefault((cfg, mode), {}).update(load_status(gdir))
    ref = status.get((args.baseline, "count"), {})
    check_rows = []
    summary = collections.OrderedDict()
    for (cfg, mode), st in sorted(status.items()):
        n = same = diff = missing = failed = 0
        same_mode_ref = status.get((args.baseline, mode), {})
        sm_same = sm_diff = 0
        for item, r in st.items():
            bm = same_mode_ref.get(item)
            eq_mode = None
            if bm is not None:
                eq_mode = bool(phase4.results_equal(r, bm))
                sm_same += 1 if eq_mode else 0
                sm_diff += 0 if eq_mode else 1
            n += 1
            if r["status"] != "ok":
                failed += 1
            b = ref.get(item)
            if b is None:
                missing += 1
                eq = None
            else:
                eq = bool(phase4.results_equal(r, b))
                same += 1 if eq else 0
                diff += 0 if eq else 1
            wr = None
            if mode == "count" and cfg in counts and item in counts[cfg] and item in base:
                wr = counts[cfg][item]["scanned_with_rows"] == base[item]["scanned_with_rows"]
            check_rows.append([cfg, mode, setup_of(item), item.split("/", 1)[1], r["status"], r.get("rows"),
                               r.get("hash_sorted"), eq, eq_mode, wr])
        summary[(cfg, mode)] = (n, same, diff, missing, failed, sm_same, sm_diff)
    write_csv(os.path.join(out_dir, "results_check.csv"),
              ["config", "mode", "setup", "qid", "status", "rows", "hash_sorted", "equal_to_baseline_count",
               "equal_to_baseline_same_mode", "with_rows_equal_baseline"], check_rows)
    md += ["## Result check (order-independent result hash vs. baseline counting pass)", "",
           md_table(["config", "mode", "queries", "equal (vs. baseline count)", "different", "no reference", "not ok",
                     "equal (vs. baseline, same mode)", "different (same mode)"],
                    [[c, m] + list(v) for (c, m), v in summary.items()]), ""]

    # ---------------------------------------------------------------- runtimes
    timing = {}
    walls = {}
    ingest_rows = []
    for (cfg, mode, g), gdir in sorted(runs.items()):
        samples, ingest, columns = load_timing(gdir)
        qwall, iwall = load_walls(gdir)
        if mode == "time":
            timing.setdefault(cfg, {}).update(samples)
            walls.setdefault(cfg, {}).update(qwall)
        tables = sorted({t for s in ingest.values() for t in s} | set(iwall))
        for t in tables:
            vals = [s[t] for s in ingest.values() if t in s]
            wv = iwall.get(t, [])
            ingest_rows.append([cfg, mode, g, t, "", "", max(len(vals), len(wv)), med(vals),
                                min(vals) if vals else None, med(wv), "", "", "", ""])
        keys = sorted({k for s in columns.values() for k in s})
        for k in keys:
            recs = [s[k] for s in columns.values() if k in s]
            ingest_rows.append([cfg, mode, g, k[0], k[1], recs[0]["kind"] + ":" + str(recs[0]["words"]), len(recs),
                                "", "", "", med([r["buffer_ns"] / 1e6 for r in recs]),
                                med([r["build_ns"] / 1e6 for r in recs]), recs[0]["bytes"],
                                recs[0]["row_groups_built"]])
    write_csv(os.path.join(out_dir, "ingest.csv"),
              ["config", "mode", "group", "table", "column", "statistic", "sessions", "copy_ms_median",
               "copy_ms_min", "copy_wall_ms_median", "buffer_ms_median", "build_ms_median", "stat_bytes", "row_groups_built"], ingest_rows)

    q_rows = []
    med_by = {}
    wall_by = {}
    for cfg in configs:
        keys = set(timing.get(cfg, {})) | set(walls.get(cfg, {}))
        for key in keys:
            recs = timing.get(cfg, {}).get(key, [])
            vals = [r["elapsed_ms"] for r in recs if not r.get("error")]
            m = med(vals)
            w = med(walls.get(cfg, {}).get(key, []))
            # engine-side elapsed time where available (selective binary), else the harness wall time (stock)
            med_by[(cfg, key)] = m if m is not None else w
            wall_by[(cfg, key)] = w
            q_rows.append([cfg, setup_of(key), key.split("/", 1)[1], len(vals), m, min(vals) if vals else None, w,
                           med([r["consult_ns"] / 1e6 for r in recs]), med([r["consultations"] for r in recs]),
                           med([r["pruned_additional"] for r in recs])])
    q_rows.sort(key=lambda r: (configs.index(r[0]), setup_order.index(r[1]) if r[1] in setup_order else 999, r[2]))
    write_csv(os.path.join(out_dir, "runtimes_per_query.csv"),
              ["config", "setup", "qid", "samples", "elapsed_ms_median", "elapsed_ms_min", "wall_ms_median",
               "consult_ms_median",
               "consultations_median", "pruned_additional_median"], q_rows)
    s_rows = []
    for setup in setup_order:
        for cfg in configs:
            keys = [k for (c, k) in med_by if c == cfg and setup_of(k) == setup and med_by[(c, k)] is not None]
            if not keys:
                continue
            total = sum(med_by[(cfg, k)] for k in keys)
            consult = sum(r[7] or 0 for r in q_rows if r[0] == cfg and r[1] == setup)
            wall_total = sum(wall_by.get((cfg, k)) or 0 for k in keys)
            bkeys = [k for k in keys if med_by.get((args.baseline, k)) is not None]
            btotal = sum(med_by[(args.baseline, k)] for k in bkeys)
            ctotal = sum(med_by[(cfg, k)] for k in bkeys)
            speedup = btotal / ctotal if ctotal else None
            s_rows.append([setup, cfg, len(keys), total, total / len(keys), wall_total, consult, speedup])
    write_csv(os.path.join(out_dir, "runtimes_per_setup.csv"),
              ["setup", "config", "queries", "sum_of_median_ms", "mean_of_median_ms", "sum_of_median_wall_ms",
               "sum_consult_ms",
               "speedup_vs_baseline"], s_rows)
    md += ["## Query runtimes (time mode: median per query over rounds x sessions, engine-side elapsed)", "",
           md_table(["setup", "config", "queries", "sum of medians (ms)", "mean (ms)", "harness wall (ms)",
                     "stat consultation (ms)",
                     "speedup vs. baseline"], s_rows), ""]
    md += ["## Ingest (COPY elapsed: median over sessions; statistics: buffering + building, per column)", "",
           md_table(["config", "mode", "group", "table", "column", "statistic", "sessions", "COPY ms (median)",
                     "COPY ms (min)", "COPY wall ms", "buffer ms", "build ms", "bytes", "row groups"], ingest_rows), ""]
    with open(os.path.join(out_dir, "summary.md"), "w") as f:
        f.write("\n".join(md) + "\n")
    print("wrote %s" % out_dir)


if __name__ == "__main__":
    main()
