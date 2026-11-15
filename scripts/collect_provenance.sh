#!/usr/bin/env bash
# Collect the records of one benchmark run into runs/<pipeline>/<dataset>/ of this repository.
#
#   bash scripts/collect_provenance.sh somaticbunny wes      --db /path/to/SomaticBunny_database
#   bash scripts/collect_provenance.sh sarek        wgs_30x
#
# Run it FROM THE LAUNCH DIRECTORY of the finished run (the one holding .nextflow/, work/ and the
# results). It copies, as listed in README.md "Run records":
#   command.txt            the run's .nextflow/history line (exact command line, duration, run name)
#   report/trace/timeline  trace-*.txt, report-*.html, timeline-*.html (config/trace.config)
#   params_*.json          the resolved parameters (SomaticBunny: RESULTS/pipeline_info; Sarek: results/pipeline_info)
#   pipeline.log           SomaticBunny's own run log
#   nextflow_version.txt   written by the run scripts
#   tool_versions.txt      conda list --explicit of every environment under work/conda/
#                          (Sarek: also results/pipeline_info/nf_core_sarek_software_mqc_versions.yml)
#   database_check.txt     SomaticBunny: bin/verify_database.sh --hash of the database (needs SOMATICBUNNY_DIR)
#   disk_usage.txt         du -sh of work/ and the results directory, before any cleanup
set -euo pipefail

PIPELINE="${1:?usage: collect_provenance.sh somaticbunny|sarek <dataset> [--db <database_path>]}"
DATASET="${2:?usage: collect_provenance.sh somaticbunny|sarek <dataset> [--db <database_path>]}"
DB=""
[[ "${3:-}" == "--db" ]] && DB="${4:?--db needs the database path}"
[[ "$PIPELINE" == somaticbunny || "$PIPELINE" == sarek ]] || { echo "ERROR: pipeline must be somaticbunny or sarek" >&2; exit 1; }

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
OUT="$(cd "${SCRIPT_DIR}/.." && pwd)/runs/${PIPELINE}/${DATASET}"
mkdir -p "$OUT"
[[ -f .nextflow/history ]] || { echo "ERROR: no .nextflow/history here: run this from the launch directory" >&2; exit 1; }
n_runs=$(grep -c . .nextflow/history)
[[ "$n_runs" -eq 1 ]] || { echo "ERROR: .nextflow/history lists $n_runs runs; a benchmark launch directory holds exactly one run made from scratch (no -resume, no relaunch)" >&2; exit 1; }
grep -q -- '-resume' .nextflow/history && { echo "ERROR: the run used -resume; benchmark runs are made from scratch" >&2; exit 1; }

tail -n 1 .nextflow/history > "$OUT/command.txt"

shopt -s nullglob
for f in report-*.html trace-*.txt timeline-*.html; do cp -p "$f" "$OUT/"; done
[[ -n "$(ls "$OUT"/trace-*.txt 2>/dev/null)" ]] || echo "WARNING: no trace-*.txt in $(pwd): was config/trace.config passed with -c?" >&2

if [[ "$PIPELINE" == somaticbunny ]]; then
    RESULTS=RESULTS
    cp -p RESULTS/pipeline_info/params_*.json "$OUT/" 2>/dev/null || echo "WARNING: no RESULTS/pipeline_info/params_*.json" >&2
    cp -p pipeline.log "$OUT/pipeline.log" 2>/dev/null || true
else
    RESULTS=results
    cp -p results/pipeline_info/params_*.json "$OUT/" 2>/dev/null || echo "WARNING: no results/pipeline_info/params_*.json" >&2
    cp -p results/pipeline_info/nf_core_sarek_software_mqc_versions.yml "$OUT/" 2>/dev/null || echo "WARNING: no software versions file" >&2
fi

cp -p nextflow_version.txt "$OUT/" 2>/dev/null || nextflow -version 2>&1 | grep -i version | head -n1 > "$OUT/nextflow_version.txt"

: > "$OUT/tool_versions.txt"
for env in work/conda/*/; do
    env="${env%/}"
    echo "### $(basename "$env")" >> "$OUT/tool_versions.txt"
    conda list --explicit -p "$env" >> "$OUT/tool_versions.txt" 2>&1 || echo "(conda list failed)" >> "$OUT/tool_versions.txt"
    echo >> "$OUT/tool_versions.txt"
done
[[ -s "$OUT/tool_versions.txt" ]] || echo "WARNING: no environments under work/conda/" >&2

if [[ "$PIPELINE" == somaticbunny ]]; then
    if [[ -n "$DB" && -n "${SOMATICBUNNY_DIR:-}" ]]; then
        bash "$SOMATICBUNNY_DIR/bin/verify_database.sh" "$DB" --hash > "$OUT/database_check.txt" 2>&1 \
            || echo "WARNING: verify_database.sh reported a problem, see $OUT/database_check.txt" >&2
    else
        echo "NOTE: database hash check skipped (needs --db <path> and SOMATICBUNNY_DIR)" >&2
    fi
fi

{
    echo "measured $(date -u +%Y-%m-%dT%H:%M:%SZ), before any cleanup (work/ kept until this measurement)"
    du -sh work "$RESULTS" 2>/dev/null
} > "$OUT/disk_usage.txt"

echo "written to $OUT:"
ls -l "$OUT"
