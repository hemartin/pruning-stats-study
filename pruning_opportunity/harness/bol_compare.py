#!/usr/bin/env python3
"""Build-on-load validation: statistics built while ATTACH loads a persistent database
(PRUNING_STATS_BUILD_ON_LOAD, phase4.py --attach-existing --build-on-load N) vs. statistics built at in-session
ingest (the normal phase4.py runs), both counting passes (1 thread).

  bol_compare.py --scale small --group clickbench --load-config bol_ng2000 --ingest-config cmb_ng2000 \
                 --base-config bol_baseline [--out results/small/phase4/build_on_load/clickbench.md]

Per query (tags present in both runs): result identical (vs. the ingest run and vs. the attach baseline), pruned
row groups by min/max equal, pruned_additional (load) vs. (ingest). The persisted database and the in-session
database hold the same rows in the same row groups when both were loaded single-threaded; build-on-load also
builds a statistic for the last, partial row group (ingest does not), so pruned_additional(load) >=
pruned_additional(ingest) with at most one extra row group per scan.
"""
import argparse
import collections
import glob
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common  # noqa: E402
import phase4  # noqa: E402


def load(scale, config, group):
    d = os.path.join(common.raw_dir(scale, "phase4"), config, "count", group)
    scans, status, timing = collections.defaultdict(list), {}, []
    for a in sorted(glob.glob(os.path.join(d, "session_*", "attempt_*"))):
        cur = {}
        for r in phase4.load_jsonl(os.path.join(a, "pruning.jsonl")):
            tag = r.get("tag", "")
            if "/ingest/" in tag or not tag:
                continue
            if r["type"] == "query" and not r["sql"].startswith("SET"):
                cur[tag] = r["seq"]
                scans[tag] = []
            elif r["type"] == "scan" and cur.get(tag) == r["seq"]:
                scans[tag].append(r)
        for r in phase4.load_jsonl(os.path.join(a, "status.jsonl")):
            if r.get("kind") == "query":
                status[r["tag"]] = r
        timing += [r for r in phase4.load_jsonl(os.path.join(a, "timing.jsonl"))
                   if r.get("type") in ("load_build", "ingest")]
    return scans, status, timing


def h(r):
    return (r.get("status"), r.get("rows"), r.get("hash_sorted") or r.get("hash_multiset") or r.get("hash"))


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--scale", default="small")
    ap.add_argument("--group", required=True)
    ap.add_argument("--load-config", required=True)
    ap.add_argument("--ingest-config", required=True)
    ap.add_argument("--base-config", default="")
    ap.add_argument("--out", default="")
    args = ap.parse_args()
    ls, lst, ltim = load(args.scale, args.load_config, args.group)
    is_, ist, itim = load(args.scale, args.ingest_config, args.group)
    bst = load(args.scale, args.base_config, args.group)[1] if args.base_config else {}
    tags = [t for t in lst if t in ist]
    c = collections.Counter()
    notes = []
    for t in tags:
        c["queries"] += 1
        if h(lst[t]) == h(ist[t]):
            c["result_eq_ingest"] += 1
        else:
            notes.append("%s: result differs from ingest run" % t)
        if t in bst:
            c["with_base"] += 1
            if h(lst[t]) == h(bst[t]):
                c["result_eq_base"] += 1
            else:
                notes.append("%s: result differs from attach baseline" % t)
        a, b = ls.get(t, []), is_.get(t, [])
        pa = sum(s["pruned_additional"] for s in a)
        pb = sum(s["pruned_additional"] for s in b)
        ma = sum(s["pruned_minmax"] for s in a)
        mb = sum(s["pruned_minmax"] for s in b)
        c["pruned_additional_load"] += pa
        c["pruned_additional_ingest"] += pb
        c["wasted_load"] += sum(s["scanned_no_rows"] for s in a)
        c["wasted_ingest"] += sum(s["scanned_no_rows"] for s in b)
        if ma != mb:
            c["minmax_differs"] += 1
            notes.append("%s: min/max pruned %d (load) vs %d (ingest)" % (t, ma, mb))
        if pa == pb:
            c["additional_equal"] += 1
        elif pb < pa <= pb + len(a):
            c["additional_plus_last_rg"] += 1
        else:
            notes.append("%s: pruned_additional %d (load) vs %d (ingest)" % (t, pa, pb))
    lb = [r for r in ltim if r["type"] == "load_build"]
    li = [r for r in ltim if r["type"] == "ingest"]
    ii = [r for r in itim if r["type"] == "ingest"]
    md = ["# Build-on-load vs. ingest-time statistics: %s (%s)" % (args.group, args.scale), "",
          "load = `%s` (persistent DB attached read-only, statistics built by ATTACH), ingest = `%s` (in-session "
          "COPY), base = `%s` (attach, no statistics)." % (args.load_config, args.ingest_config, args.base_config), "",
          "* queries compared: %d; results identical load vs. ingest %d, load vs. base %d/%d" % (
              c["queries"], c["result_eq_ingest"], c["result_eq_base"], c["with_base"]),
          "* min/max pruning differs in %d queries" % c["minmax_differs"],
          "* pruned by the statistic: load %d, ingest %d; per query equal %d, load = ingest + last partial row "
          "group(s) %d, other %d" % (c["pruned_additional_load"], c["pruned_additional_ingest"],
                                     c["additional_equal"], c["additional_plus_last_rg"],
                                     c["queries"] - c["additional_equal"] - c["additional_plus_last_rg"]),
          "* wasted reads (scanned_no_rows): load %d, ingest %d" % (c["wasted_load"], c["wasted_ingest"])]
    for r in lb:
        md.append("* load_build: table %s, %d row groups, %d thread(s), wall %.0f ms, data read %.0f ms; %s" % (
            r["table"], r["row_groups"], r["threads"], r["wall_ms"], r["read_ms"], "; ".join(
                "%s %s@%d: %d stats, %d bytes, build %.0f ms, key extraction %.0f ms" % (
                    x["column"], x["kind"], x["words"], x["row_groups_built_total"], x["bytes_total"],
                    x["build_ns_total"] / 1e6, x["buffer_ns_total"] / 1e6) for x in r["columns"])))
    for name, recs in (("load (ATTACH statement)", li), ("ingest (COPY)", ii)):
        per = collections.defaultdict(lambda: collections.Counter())
        for r in recs:
            per[(r["column"], r["kind"])].update({"rg": r["row_groups_built"], "build_ns": r["build_ns"],
                                                  "buffer_ns": r["buffer_ns"], "bytes": r["bytes"]})
        for (col, kind), v in per.items():
            md.append("* %s: %s %s: %d statistics, build %.0f ms (%.1f ms per row group), key extraction %.0f ms, "
                      "%d bytes" % (name, col, kind, v["rg"], v["build_ns"] / 1e6,
                                    v["build_ns"] / 1e6 / max(v["rg"], 1), v["buffer_ns"] / 1e6, v["bytes"]))
    if notes:
        md += ["", "Notes:", ""] + ["* " + n for n in notes[:40]]
    text = "\n".join(md) + "\n"
    print(text)
    if args.out:
        os.makedirs(os.path.dirname(args.out), exist_ok=True)
        with open(args.out, "w") as f:
            f.write(text)


if __name__ == "__main__":
    main()
