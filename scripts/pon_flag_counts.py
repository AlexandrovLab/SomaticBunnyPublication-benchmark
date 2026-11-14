#!/usr/bin/env python3
"""Count the consensus variants that Mutect2 flagged panel_of_normals.

usage: pon_flag_counts.py RESULTS/POST [--scenario 6] [--out table.tsv]

Reads every <patient_sample>/scenario_<N>/snvs/*_snv_annotated.tsv.gz and
indels/*_indel_annotated.tsv.gz that SomaticBunny publishes (consensus_scenarios.sh annotated
tables: one row per variant seen by any caller, with the scenario decision and each caller's
FILTER). For each sample and variant type it reports

  consensus      rows whose SCENARIO<N>_DECISION is PASS (the variants kept by the scenario)
  consensus_pon  of those, rows whose MUTECT2_FILTER contains panel_of_normals: variants kept
                 although Mutect2 flagged them as present in its panel of normals (the PON veto,
                 --pon_veto, is off by default; with it on this count is 0 by construction)
  any_pon        rows with the flag at any decision, for scale

A consensus variant can carry the flag because the scenario needs two PASS callers and Mutect2
need not be one of them.
"""
import argparse
import glob
import gzip
import os
import re
import sys


def count_file(path, scenario):
    opener = gzip.open if path.endswith(".gz") else open
    with opener(path, "rt") as fh:
        header = fh.readline().lstrip("#").rstrip("\n").split("\t")
        want_dec = f"SCENARIO{scenario}_DECISION"
        if want_dec not in header or "MUTECT2_FILTER" not in header:
            sys.exit(f"{path}: expected columns {want_dec} and MUTECT2_FILTER, found {header}")
        i_dec, i_mt = header.index(want_dec), header.index("MUTECT2_FILTER")
        pon = re.compile(r"(^|;)panel_of_normals(;|$)")
        consensus = consensus_pon = any_pon = 0
        for line in fh:
            if not line.strip():
                continue
            f = line.rstrip("\n").split("\t")
            flagged = bool(pon.search(f[i_mt]))
            any_pon += flagged
            if f[i_dec] == "PASS":
                consensus += 1
                consensus_pon += flagged
    return consensus, consensus_pon, any_pon


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("post_dir", help="SomaticBunny RESULTS/POST directory")
    ap.add_argument("--scenario", type=int, default=6)
    ap.add_argument("--out", help="write the table as TSV here")
    a = ap.parse_args()
    rows = []
    for kind, sub in (("snv", "snvs"), ("indel", "indels")):
        pattern = os.path.join(a.post_dir, "*", f"scenario_{a.scenario}", sub, f"*_{kind}_annotated.tsv*")
        for path in sorted(glob.glob(pattern)):
            sample = os.path.basename(os.path.dirname(os.path.dirname(os.path.dirname(path))))
            c, cp, ap_ = count_file(path, a.scenario)
            rows.append((sample, kind, c, cp, ap_))
    if not rows:
        sys.exit(f"no scenario_{a.scenario} annotated tables under {a.post_dir}")
    tot = {}
    for s, k, c, cp, ap_ in rows:
        t = tot.setdefault(k, [0, 0, 0]); t[0] += c; t[1] += cp; t[2] += ap_
    lines = ["sample\ttype\tconsensus\tconsensus_pon\tany_pon"]
    lines += [f"{s}\t{k}\t{c}\t{cp}\t{ap_}" for s, k, c, cp, ap_ in rows]
    lines += [f"ALL\t{k}\t{t[0]}\t{t[1]}\t{t[2]}" for k, t in tot.items()]
    print("\n".join(lines))
    if a.out:
        with open(a.out, "w") as fh:
            fh.write("\n".join(lines) + "\n")


if __name__ == "__main__":
    main()
