#!/usr/bin/env python3
"""Compute the benchmark metrics of one or more Nextflow runs, overall and per stage.

usage:
  benchmark_metrics.py --run SomaticBunny_WES=runs/somaticbunny/wes --run Sarek_WES=runs/sarek/wes \
                       [--out tables/metrics.tsv]

A run is a directory holding the run's records (an execution trace `trace*.txt` or
`execution_trace*.txt`, optionally the HTML report `report*.html` / `execution_report*.html` and
`command.txt`, the run's `.nextflow/history` line), or a single trace / report file.

Metrics (see METRICS.md; every one is computed the same way for every pipeline):

  wall_clock_h        the run's duration from its .nextflow/history line (command.txt): everything
                      from `nextflow run` to completion, including scheduler queueing and
                      environment creation. Overall only. "NA" without command.txt.
  task_realtime_h     sum of task realtime (the task's own execution time, no queue wait) over
                      completed tasks.
  used_cpu_h          sum over completed tasks of realtime x %cpu / 100: CPU time actually consumed,
                      as Nextflow measured it (Linux cgroup accounting of the task's processes).
  reserved_core_h     sum over all task attempts of cpus x realtime: core-hours the scheduler
                      reserved while tasks ran (what a cluster charges). Needs the `cpus` field,
                      present in a trace produced with the benchmark `trace.config` or in the
                      HTML report; "NA" otherwise.
  peak_rss_gb         the largest peak resident set size of any single task.
  tasks / failed      completed tasks, and attempts that failed (retried or fatal).

Stages: each process is assigned to exactly one stage by name (STAGES below). An unknown process
name stops the script, so no task is silently left out or misassigned.
"""
import argparse
import csv
import glob
import json
import os
import re
import sys
from collections import defaultdict

STAGES = [
    ("alignment/preprocessing", re.compile(r"""^(
        FASTQC|FASTP|BWA_MEM|BWAMEM1_MEM|BWAMEM2_MEM|
        MKDUP|GATK4_MARKDUPLICATES|GATK4SPARK_MARKDUPLICATES|
        CHECK_BAM_.*|COMBINE_REPORTS_.*|CLEANUP_.*|RENAME_BAM_HEADER|
        RECALIBRATE_.*|GATK4_BASERECALIBRATOR|GATK4SPARK_BASERECALIBRATOR|GATK4_APPLYBQSR|GATK4SPARK_APPLYBQSR|GATK4_GATHERBQSRREPORTS|
        MERGE_CRAM|INDEX_CRAM|CRAM_TO_BAM|SAMTOOLS_CONVERT|SAMTOOLS_INDEX|SAMTOOLS_STATS|
        MOSDEPTH|CONPAIR|
        SAVE_CSV_FASTQC|SAVE_CSV_BWA_MEM|SAVE_CSV_MKDUP|SAVE_CSV_RECAL|SAVE_CSV_MOSDEPTH|SAVE_CSV_CONPAIR
        )$""", re.X)),
    ("SNV/indel calling", re.compile(r"""^(
        MUTECT2_CALLING|MUTECT2_PAIRED|GETpileUP|GETpileUP_Merge|GETPILEUPSUMMARIES_.*|GATHERPILEUPSUMMARIES_.*|
        LearnReadOrientationModel|LEARNREADORIENTATIONMODEL|MergeMutectStats|MERGEMUTECTSTATS|MergeVcfs|MERGE_MUTECT2|
        CalculateContamination|CALCULATECONTAMINATION|FilterMutectCalls|FILTERMUTECTCALLS|
        STRELKA|STRELKA_SOMATIC|MERGE_STRELKA_.*|MuSE|MUSE_CALL|MUSE_SUMP|TABIX_MUSE|SAGE|
        FREEBAYES|MERGE_FREEBAYES|BCFTOOLS_SORT|VCFLIB_VCFFILTER|TABIX_VC_FREEBAYES_FILT|
        POST_SCENARIOS|POST_SCENARIOS_NONHUMAN|POST_scenario\d|ALLELECOUNTER|
        BCFTOOLS_CONCAT|BCFTOOLS_ISEC|CONSENSUS_FROM_SITES|ADD_INFO_TO_VCF|TABIX_EXT_VCF|VCFS_NORM|VCFS_NORM_SORT|
        BCFTOOLS_STATS|VCFTOOLS_.*|
        SAVE_CSV_SAGE|SAVE_CSV_STRELKA|SAVE_CSV_MuSE|SAVE_CSV_Mutect2
        )$""", re.X)),
    ("SV/CNV analysis", re.compile(r"""^(
        MANTA|Delly_.*|Create_sample_tsv|CNVkit|CNVkit_buildcnn|CNVKIT_.*|ASCAT|ASCAT_.*
        )$""", re.X)),
    ("setup/reporting", re.compile(r"""^(
        BQSR_INTERVALS|GENERATE_INTERVALS|CREATE_INTERVALS_BED|BUILD_INTERVALS|TABIX_BGZIPTABIX_INTERVAL_.*|
        PREPARE_.*|UNZIP.*|UNTAR.*|MULTIQC|CUSTOM_DUMPSOFTWAREVERSIONS|SAMPLESHEET_.*
        )$""", re.X)),
]
STAGE_ORDER = [name for name, _ in STAGES] + ["overall pipeline"]

UNIT = {"ms": 0.001, "s": 1, "m": 60, "h": 3600, "d": 86400}
MEM = {"B": 1, "KB": 1024, "MB": 1024 ** 2, "GB": 1024 ** 3, "TB": 1024 ** 4}


def duration_s(v):
    """Trace duration string ('1h 2m 3.5s', '125ms', '-') or report milliseconds -> seconds."""
    v = str(v).strip()
    if v in ("-", "", "null"):
        return 0.0
    if re.fullmatch(r"\d+", v):
        return int(v) / 1000.0
    return sum(float(n) * UNIT[u] for n, u in re.findall(r"([\d.]+)\s*(ms|[smhd])", v))


def mem_b(v):
    """Trace memory string ('1.3 GB', '-') or report bytes -> bytes."""
    v = str(v).strip()
    if v in ("-", "", "null"):
        return 0.0
    if re.fullmatch(r"\d+", v):
        return float(v)
    m = re.match(r"([\d.]+)\s*([KMGT]?B)", v)
    return float(m.group(1)) * MEM[m.group(2)] if m else 0.0


def pct(v):
    v = str(v).strip().rstrip("%")
    return float(v) if v not in ("-", "", "null") else 0.0


def short_name(name):
    name = name.split(" (")[0]
    return name.split(":")[-1]


def stage_of(process):
    for stage, rx in STAGES:
        if rx.match(process):
            return stage
    return None


def load_trace(path):
    with open(path) as fh:
        rows = list(csv.DictReader(fh, delimiter="\t"))
    return rows


def load_report(path):
    """Task records embedded in the HTML report (`window.data = {trace: [...]}`).

    The embedded JSON is not parsed as a whole: Nextflow does not escape the quotes and backslashes
    of the free-text fields (script, env, workdir) correctly, so json.loads fails on real reports.
    Each record is read from its `{"task_id":` up to its first free-text field; every field before
    that point (process, name, status, exit, cpus, memory, realtime, %cpu, peak_rss, ...) is a plain
    `"key":"value"` pair."""
    html = open(path, encoding="utf-8", errors="replace").read()
    i = html.find("window.data")
    if i < 0:
        sys.exit(f"{path}: no embedded trace found (window.data)")
    text = html[i:]
    rows = []
    for m in re.finditer(r'\{"task_id":"', text):
        start = m.start()
        window = text[start:start + 20000]
        cut = min([k for k in (window.find(',"env":'), window.find(',"workdir":'), window.find(',"script":'), window.find('}')) if k != -1] or [len(window)])
        rec = dict(re.findall(r'"([^"]+)":"([^"]*)"', window[:cut]))
        # cpus, memory, time and queue are written after the free-text fields; take the last match
        # of each exact pair inside this record
        nxt = text.find('{"task_id":"', m.end())
        record = text[start:nxt if nxt != -1 else start + 200000]
        for key in ("cpus", "memory", "time", "queue", "attempt", "hostname"):
            found = re.findall(r',"%s":"([^"]*)"' % key, record)
            if found and key not in rec:
                rec[key] = found[-1]
        if "name" in rec and "status" in rec:
            rows.append(rec)
    if not rows:
        sys.exit(f"{path}: no task records found in the report")
    return rows


def find_records(run):
    """Return (rows, source_file, history_line_or_None)."""
    if os.path.isfile(run):
        files = [run]
        d = os.path.dirname(run) or "."
    else:
        d = run
        files = sorted(glob.glob(os.path.join(d, "*report*.html"))) + \
                sorted(glob.glob(os.path.join(d, "*trace*.txt")))
    if not files:
        sys.exit(f"{run}: no trace or report found")
    reports = [f for f in files if f.endswith(".html")]
    traces = [f for f in files if f.endswith(".txt")]
    # the HTML report carries every field (cpus included); a default trace lacks cpus
    src = reports[0] if reports else traces[0]
    rows = load_report(src) if src.endswith(".html") else load_trace(src)
    if "cpus" not in rows[0] and reports:
        rows = load_report(reports[0]); src = reports[0]
    hist = None
    cmd = os.path.join(d, "command.txt")
    if os.path.isfile(cmd):
        line = [l for l in open(cmd).read().splitlines() if l.strip()]
        if line:
            hist = line[-1]
    return rows, src, hist


def wall_clock_h(history_line):
    """Second tab-separated field of a .nextflow/history line is the duration."""
    parts = history_line.split("\t")
    if len(parts) < 2:
        return None
    return duration_s(parts[1]) / 3600.0


def summarise(label, run):
    rows, src, hist = find_records(run)
    has_cpus = "cpus" in rows[0]
    acc = defaultdict(lambda: dict(tasks=0, failed=0, realtime_h=0.0, used_cpu_h=0.0,
                                   reserved_core_h=0.0, peak_rss_gb=0.0))
    unknown = set()
    for r in rows:
        proc = short_name(r.get("name") or r.get("process") or "")
        stage = stage_of(proc)
        if stage is None:
            unknown.add(proc)
            continue
        rt_h = duration_s(r.get("realtime", "-")) / 3600.0
        for key in (stage, "overall pipeline"):
            a = acc[key]
            if r.get("status") == "COMPLETED":
                a["tasks"] += 1
                a["realtime_h"] += rt_h
                a["used_cpu_h"] += rt_h * pct(r.get("%cpu", "-")) / 100.0
            else:
                a["failed"] += 1
            if has_cpus:
                a["reserved_core_h"] += rt_h * float(r.get("cpus") or 0)   # every attempt reserved its cores
            a["peak_rss_gb"] = max(a["peak_rss_gb"], mem_b(r.get("peak_rss", "-")) / MEM["GB"])
    if unknown:
        sys.exit(f"{label}: {len(unknown)} process name(s) not assigned to a stage, add them to STAGES: {sorted(unknown)}")
    wall = wall_clock_h(hist) if hist else None
    out = []
    for stage in STAGE_ORDER:
        a = acc.get(stage)
        if not a:
            continue
        out.append(dict(run=label, stage=stage, tasks=a["tasks"], failed_attempts=a["failed"],
                        wall_clock_h=f"{wall:.2f}" if (wall is not None and stage == "overall pipeline") else "NA",
                        task_realtime_h=f"{a['realtime_h']:.2f}",
                        used_cpu_h=f"{a['used_cpu_h']:.2f}",
                        reserved_core_h=f"{a['reserved_core_h']:.2f}" if has_cpus else "NA",
                        peak_rss_gb=f"{a['peak_rss_gb']:.1f}"))
    note = "" if has_cpus else " (no cpus field: reserved_core_h unavailable; rerun with trace.config or supply the HTML report)"
    print(f"# {label}: {len(rows)} task records from {src}{note}", file=sys.stderr)
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--run", action="append", required=True, metavar="LABEL=PATH",
                    help="run label and its records directory (or trace/report file); repeatable")
    ap.add_argument("--out", help="write the table as TSV here (default: stdout only)")
    args = ap.parse_args()
    table = []
    for spec in args.run:
        label, _, path = spec.partition("=")
        if not path:
            sys.exit(f"--run needs LABEL=PATH, got {spec}")
        table += summarise(label, path)
    cols = ["run", "stage", "tasks", "failed_attempts", "wall_clock_h", "task_realtime_h", "used_cpu_h", "reserved_core_h", "peak_rss_gb"]
    lines = ["\t".join(cols)] + ["\t".join(str(r[c]) for c in cols) for r in table]
    print("\n".join(lines))
    if args.out:
        os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
        with open(args.out, "w") as fh:
            fh.write("\n".join(lines) + "\n")
        print(f"# written {args.out}", file=sys.stderr)


if __name__ == "__main__":
    main()
