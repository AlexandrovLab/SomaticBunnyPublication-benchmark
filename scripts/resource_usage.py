#!/usr/bin/env python3
"""Per-process resource usage from Nextflow run records, to right-size resource requests.

usage: resource_usage.py RUN [RUN ...]      (a records directory, trace file or HTML report each)

For every process (all runs pooled) prints the number of completed tasks, the CPUs requested
(when recorded), the mean and maximum %cpu, the maximum and 95th percentile of peak RSS, the
maximum realtime, and a suggested memory request: max peak RSS x 1.5, rounded up to 2 GB (the
retry doubles it), minimum 2 GB. Use it on the HTML reports or traces of complete runs.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from benchmark_metrics import MEM, duration_s, find_records, mem_b, pct, short_name  # noqa: E402


def main():
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    per = {}
    for run in sys.argv[1:]:
        rows, src, _ = find_records(run)
        print(f"# {len(rows)} records from {src}", file=sys.stderr)
        for r in rows:
            if r.get("status") != "COMPLETED":
                continue
            p = per.setdefault(short_name(r.get("name") or r.get("process") or ""), dict(n=0, cpus=set(), pcpu=[], rss=[], rt=[]))
            p["n"] += 1
            if r.get("cpus") not in (None, "", "-"):
                p["cpus"].add(str(r["cpus"]))
            p["pcpu"].append(pct(r.get("%cpu", "-")))
            p["rss"].append(mem_b(r.get("peak_rss", "-")) / MEM["GB"])
            p["rt"].append(duration_s(r.get("realtime", "-")) / 3600.0)
    print("process\tn\tcpus_req\tmean_pct_cpu\tmax_pct_cpu\tmax_peak_rss_gb\tp95_peak_rss_gb\tmax_realtime_h\tsuggested_mem_gb")
    for name, p in sorted(per.items(), key=lambda kv: -max(kv[1]["rss"])):
        rss = sorted(p["rss"])
        p95 = rss[min(len(rss) - 1, int(round(0.95 * (len(rss) - 1))))]
        sugg = max(2, int(-(-(rss[-1] * 1.5) // 2) * 2))
        print(f"{name}\t{p['n']}\t{'/'.join(sorted(p['cpus'])) or 'NA'}\t{sum(p['pcpu'])/len(p['pcpu']):.0f}\t{max(p['pcpu']):.0f}"
              f"\t{rss[-1]:.1f}\t{p95:.1f}\t{max(p['rt']):.2f}\t{sugg}")


if __name__ == "__main__":
    main()
