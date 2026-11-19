#!/usr/bin/env python3
"""Compare a Phase 4 counting pass (default: config 'baseline') with the stock instrumented binary's counting run
(results/raw/<scale>/count/<setup>/, Phase 1): per query identical result (row count + order-independent hash) and
per table scan identical counters (pruned, scanned without / with rows, partial, not reached, incl.-optional
counters, rows passed) and identical per-filter attribution (pruned_first, prunable_alone).

  phase4_compare_stock.py --scale small [--config baseline] [--stock-label count]
Writes results/<scale>/phase4/compare_stock_<config>.{csv,md}.
"""
import argparse
import collections
import csv
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import aggregate  # noqa: E402
import common  # noqa: E402
import phase4  # noqa: E402
import phase4_aggregate  # noqa: E402
import phase4_validate  # noqa: E402

FIELDS = ["total_row_groups", "pruned", "scanned_no_rows", "scanned_with_rows", "partial_no_rows", "not_reached",
          "incl_optional_with_rows", "incl_optional_no_rows", "incl_optional_partial_no_rows", "rows_passed",
          "rows_passed_incl_optional", "pruned_unattributed"]


def load_phase4_scans(gdir):
    by_tag = {}
    for adir in phase4_aggregate.attempts(gdir):
        by_tag.update(aggregate.load_run(adir))
    return by_tag


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--scale", required=True)
    ap.add_argument("--config", default="baseline")
    ap.add_argument("--stock-label", default="count")
    ap.add_argument("--fields", default=None, help="comma-separated counter fields to compare (default: all)")
    args = ap.parse_args()
    fields = args.fields.split(",") if args.fields else FIELDS
    rows = []
    totals = collections.OrderedDict()
    for group, setups in phase4.groups().items():
        gdir = os.path.join(common.raw_dir(args.scale, "phase4"), args.config, "count", group)
        if not os.path.isdir(gdir):
            continue
        new_scans = load_phase4_scans(gdir)
        new_status = phase4_aggregate.load_status(gdir)
        for setup in setups:
            sdir = os.path.join(common.raw_dir(args.scale, args.stock_label), setup.name)
            if not os.path.isdir(sdir):
                continue
            old_scans = aggregate.load_run(sdir)
            old_status = aggregate.load_status(sdir)
            t = totals.setdefault(setup.name, collections.Counter())
            for tag, (q_old, scans_old) in old_scans.items():
                if tag not in new_scans:
                    continue
                t["queries"] += 1
                q_new, scans_new = new_scans[tag]
                so, sn = old_status.get(tag), new_status.get(tag)
                result_eq = bool(phase4.results_equal(so, sn))
                t["result_equal"] += 1 if result_eq else 0
                diffs = []
                if len(scans_old) != len(scans_new):
                    diffs.append("n_scans %d vs %d" % (len(scans_old), len(scans_new)))
                pairs, realigned = phase4_validate.align(scans_old, scans_new)
                t["realigned"] += realigned
                for a, b in pairs:
                    for f in fields:
                        if a.get(f) != b.get(f):
                            diffs.append("scan%d.%s %s vs %s" % (a["scan_id"], f, a.get(f), b.get(f)))
                    fa = [(x["col"], x["kind"], x["pruned_first"], x["prunable_alone"]) for x in a["filters"]]
                    fb = [(x["col"], x["kind"], x["pruned_first"], x["prunable_alone"]) for x in b["filters"]]
                    if fa != fb:
                        diffs.append("scan%d.filters" % a["scan_id"])
                    # origin labels: the selective binary labels leaves of scans without plan-time filters 'join'
                    # (fixed 2026-11-17); the Phase 1 stock binary labelled them 'static'
                    if [x["origin"] for x in a["filters"]] != [x["origin"] for x in b["filters"]]:
                        relabelled = all(x["origin"] == y["origin"] or (x["origin"] == "static" and
                                                                          y["origin"] == "join")
                                         for x, y in zip(a["filters"], b["filters"]))
                        if relabelled:
                            t["origin_relabelled_scans"] += 1
                        else:
                            diffs.append("scan%d.origin" % a["scan_id"])
                    if b.get("pruned_additional", 0):
                        diffs.append("scan%d.pruned_additional=%d" % (a["scan_id"], b["pruned_additional"]))
                t["counters_equal"] += 0 if diffs else 1
                if diffs or not result_eq:
                    rows.append([setup.name, tag.split("/", 1)[1], result_eq, "; ".join(diffs)[:1000]])
    out_dir = os.path.join(common.results_dir(args.scale), "phase4")
    os.makedirs(out_dir, exist_ok=True)
    with open(os.path.join(out_dir, "compare_stock_%s.csv" % args.config), "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["setup", "qid", "result_equal", "counter_differences"])
        w.writerows(rows)
    md = ["# Phase 4 `%s` counting pass vs. stock instrumented v1.4.4 (Phase 1 `%s` run)" % (args.config,
                                                                                             args.stock_label), "",
          "| setup | queries | identical result | identical counters (all scans, all filters) | scans matched by identity "
          "(scan ids permuted) | scans with leaves relabelled static -> join |", "|---|---|---|---|---|---|"]
    for s, t in totals.items():
        md.append("| %s | %d | %d | %d | %d | %d |" % (s, t["queries"], t["result_equal"], t["counters_equal"],
                                                       t["realigned"], t["origin_relabelled_scans"]))
    md.append("")
    if rows:
        md.append("Differences (first 40, full list in compare_stock_%s.csv):" % args.config)
        md.append("")
        for r in rows[:40]:
            md.append("* %s/%s: result_equal=%s %s" % tuple(r))
    with open(os.path.join(out_dir, "compare_stock_%s.md" % args.config), "w") as f:
        f.write("\n".join(md) + "\n")
    print("\n".join(md[:len(totals) + 4]))
    print("%d queries with differences" % len(rows))


if __name__ == "__main__":
    main()
