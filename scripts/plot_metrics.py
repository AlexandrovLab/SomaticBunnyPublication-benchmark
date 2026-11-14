#!/usr/bin/env python3
"""Bar charts of the benchmark metrics table written by benchmark_metrics.py.

usage: plot_metrics.py tables/metrics.tsv figures/

One PNG per metric (used_cpu_h, reserved_core_h, task_realtime_h, peak_rss_gb): stages on the x
axis, one bar per run. "NA" values are left out. Requires matplotlib.
"""
import csv
import os
import sys
from collections import defaultdict

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

METRICS = [("used_cpu_h", "CPU time used (CPU-hours)"), ("reserved_core_h", "Reserved core-hours"),
           ("task_realtime_h", "Task realtime (hours)"), ("peak_rss_gb", "Peak memory of a single task (GB)")]
STAGES = ["alignment/preprocessing", "SNV/indel calling", "SV/CNV analysis", "setup/reporting", "overall pipeline"]


def main():
    if len(sys.argv) != 3:
        sys.exit(__doc__)
    table, outdir = sys.argv[1], sys.argv[2]
    os.makedirs(outdir, exist_ok=True)
    rows = list(csv.DictReader(open(table), delimiter="\t"))
    runs = []
    for r in rows:
        if r["run"] not in runs:
            runs.append(r["run"])
    for key, title in METRICS:
        vals = defaultdict(dict)
        for r in rows:
            if r[key] != "NA":
                vals[r["stage"]][r["run"]] = float(r[key])
        stages = [s for s in STAGES if s in vals]
        if not stages:
            continue
        fig, ax = plt.subplots(figsize=(1.6 * len(stages) + 3, 4.5))
        width = 0.8 / max(1, len(runs))
        for i, run in enumerate(runs):
            xs = [j + (i - (len(runs) - 1) / 2) * width for j in range(len(stages))]
            ys = [vals[s].get(run, 0.0) for s in stages]
            bars = ax.bar(xs, ys, width, label=run)
            for b, y in zip(bars, ys):
                if y:
                    ax.annotate(f"{y:.3g}", (b.get_x() + b.get_width() / 2, y), ha="center", va="bottom", fontsize=7)
        ax.set_xticks(range(len(stages)))
        ax.set_xticklabels(stages, rotation=20, ha="right")
        ax.set_ylabel(title)
        ax.legend(frameon=False)
        ax.spines[["top", "right"]].set_visible(False)
        fig.tight_layout()
        out = os.path.join(outdir, f"{key}.png")
        fig.savefig(out, dpi=150)
        plt.close(fig)
        print(out)


if __name__ == "__main__":
    main()
