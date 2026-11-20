#!/usr/bin/env python3
"""Summarises the timing runs of ec2_timing.py.

  ec2_aggregate.py <out>          # e.g. pruning_opportunity/results/ec2

Writes <out>/summary.csv and <out>/summary.md: per memory mode, dataset, binary, configuration and setup/query the
number of timed runs and min / median / avg / max of the shell's real time (ms), the same for the wall-clock time
measured around each statement, the mean bytes read from storage per run, errors, and the ATTACH time (incl. the
statistics build). Warm-up runs are left out.
"""
import csv
import glob
import json
import os
import statistics
import sys

MICRO_ORDER = ["point_unsorted", "range_seconds_unsorted", "range_minutes_unsorted", "range_hours_unsorted"]
MICRO_LABEL = {"point_unsorted": "point", "range_seconds_unsorted": "1 s", "range_minutes_unsorted": "1 min",
               "range_hours_unsorted": "1 h"}
CB_ORDER = ["Q19", "Q21", "Q23"]
CONFIG_ORDER = ["stock_baseline", "timing_baseline", "timing_bloom200", "timing_occupancy200", "timing_nullspace200",
                "stock_C1_baseline", "timing_C1_baseline", "timing_C2_statistic", "timing_C2_bloom200", "timing_C3_all_repeat"]


def stats(values):
    values = [v for v in values if v is not None]
    if not values:
        return {"n": 0, "min": None, "median": None, "avg": None, "max": None}
    return {"n": len(values), "min": min(values), "median": statistics.median(values),
            "avg": statistics.fmean(values), "max": max(values)}


def fmt(v, digits=1):
    if v is None:
        return "–"
    return "{:,.{d}f}".format(v, d=digits)


def main():
    if len(sys.argv) != 2:
        raise SystemExit(__doc__)
    out = sys.argv[1]
    rows = []
    for runs_path in sorted(glob.glob(os.path.join(out, "M*", "*", "*", "runs.csv"))):
        sdir = os.path.dirname(runs_path)
        mode = os.path.basename(os.path.dirname(os.path.dirname(sdir)))
        dataset = os.path.basename(os.path.dirname(sdir))
        session = os.path.basename(sdir)
        with open(os.path.join(sdir, "session.json")) as f:
            info = json.load(f)
        with open(runs_path, newline="") as f:
            runs = [r for r in csv.DictReader(f) if r["warmup"] == "0"]
        order = MICRO_ORDER if dataset == "micro" else CB_ORDER
        for setup in [s for s in order if any(r["setup"] == s for r in runs)]:
            all_runs = [r for r in runs if r["setup"] == setup]
            sel = [r for r in all_runs if r["error"] == "0"]  # failed runs are counted, not timed
            real = stats([float(r["real_ms"]) if r["real_ms"] else None for r in sel])
            wall = stats([float(r["wall_ms"]) for r in sel])
            reads = [int(r["read_bytes"]) for r in sel if r["read_bytes"] not in ("", None)]
            rows.append({
                "mode": mode, "dataset": dataset, "session": session, "binary": info["binary"],
                "config": info["config"], "setup": setup, "runs": real["n"],
                "real_min_ms": real["min"], "real_median_ms": real["median"], "real_avg_ms": real["avg"],
                "real_max_ms": real["max"],
                "wall_min_ms": wall["min"], "wall_median_ms": wall["median"], "wall_avg_ms": wall["avg"],
                "wall_max_ms": wall["max"],
                "read_mb_avg": statistics.fmean(reads) / 1e6 if reads else None,
                "errors": sum(int(r["error"]) for r in all_runs),
                "attach_s": (info.get("attach") or {}).get("wall_s"),
                "session_done": info.get("done"),
                "drop_caches_ok": (info.get("drop_caches") or {}).get("ok"),
                "cgroup_memory_max": (info.get("cgroup") or {}).get("memory.max"),
                "cgroup_anon_mb_after_attach": ((info.get("cgroup_memory") or {}).get("after_attach") or {}).get("anon",
                                                                                                         0) / 1e6
                if info.get("cgroup_memory") else None,
                "cgroup_peak_mb": ((info.get("cgroup_memory") or {}).get("end") or {}).get("peak", 0) / 1e6
                if info.get("cgroup_memory") and ((info["cgroup_memory"].get("end") or {}).get("peak")) else None,
            })

    def key(r):
        return (r["mode"], r["dataset"] != "micro",
                CONFIG_ORDER.index(r["session"]) if r["session"] in CONFIG_ORDER else 99,
                (MICRO_ORDER + CB_ORDER).index(r["setup"]))
    rows.sort(key=key)

    with open(os.path.join(out, "summary.csv"), "w", newline="") as f:
        if rows:
            w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
            w.writeheader()
            w.writerows(rows)

    md = ["# EC2 timing runs: summary", "",
          "Times in ms over the timed runs (warm-up runs excluded), from the DuckDB shell's timer (`.timer on`, real "
          "time, 1 ms resolution). Wall median = wall clock around each statement in the driver (µs resolution, "
          "includes the pipe round trip). Read MB = mean bytes the DuckDB process read from storage per run (`/proc/<pid>/io`). "
          "Attach s = ATTACH incl. building the statistics, not part of the query times. Failed runs are counted "
          "under Errors and left out of the times.", ""]
    for mode in sorted({r["mode"] for r in rows}):
        for dataset in ["micro", "clickbench"]:
            sel = [r for r in rows if r["mode"] == mode and r["dataset"] == dataset]
            if not sel:
                continue
            title = {"micro": "Microbenchmark, unsorted, 1B rows", "clickbench": "ClickBench Q19, Q21, Q23"}[dataset]
            md += ["## %s · %s" % (mode, title), "",
                   "| Binary | Configuration | Query | Runs | Min | Median | Avg | Max | Wall median | Read MB | Errors | Attach s |",
                   "|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|"]
            for r in sel:
                label = MICRO_LABEL.get(r["setup"], r["setup"])
                md.append("| %s | %s | %s | %d | %s | %s | %s | %s | %s | %s | %d | %s |" % (
                    r["binary"], r["config"], label, r["runs"], fmt(r["real_min_ms"]), fmt(r["real_median_ms"]),
                    fmt(r["real_avg_ms"]), fmt(r["real_max_ms"]), fmt(r["wall_median_ms"], 2), fmt(r["read_mb_avg"]),
                    r["errors"], fmt(r["attach_s"])))
            md.append("")
    with open(os.path.join(out, "summary.md"), "w") as f:
        f.write("\n".join(md) + "\n")
    print("wrote %s and %s (%d rows)" % (os.path.join(out, "summary.csv"), os.path.join(out, "summary.md"), len(rows)))


if __name__ == "__main__":
    main()
