#!/usr/bin/env bash
#######################################################################
# SomaticBunny benchmark: SomaticBunny on WGS (30x, 60x, 90x)
#######################################################################

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BENCH_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"          # this repository
CLUSTER_CONFIG="${BENCH_DIR}/config/cluster.config"      # scheduler settings, identical for both pipelines
TRACE_CONFIG="${BENCH_DIR}/config/trace.config"           # trace/report/timeline, same for both pipelines
SOMATICBUNNY_DIR="${SOMATICBUNNY_DIR:?set SOMATICBUNNY_DIR to the SomaticBunny checkout (directory containing main.nf)}"
PATHS_ENV="${PATHS_ENV:-${SCRIPT_DIR}/paths.env}"

# ---- Nextflow environment (benchmark: conda env "env_nf") ----
if [[ -z "${CONDA_SH:-}" ]]; then
    CONDA_SH="$(conda info --base 2>/dev/null)/etc/profile.d/conda.sh"
fi
# shellcheck disable=SC1090
source "$CONDA_SH" || { echo "ERROR: cannot source conda: $CONDA_SH (set CONDA_SH=...)" >&2; exit 1; }
conda activate "${NF_CONDA_ENV:-env_nf}" || { echo "ERROR: cannot activate conda env ${NF_CONDA_ENV:-env_nf}" >&2; exit 1; }

set -euo pipefail

export NXF_OPTS='-Xms1g -Xmx4g'

# ---- reference paths (exports TMPDIR, as in the original session) ----
[[ -f "$PATHS_ENV" ]] || { echo "ERROR: paths file not found: $PATHS_ENV" >&2; exit 1; }
set -a
# shellcheck disable=SC1090
source "$PATHS_ENV"
set +a
# Every variable the run needs must come from the paths file. A PATHS_ENV left over from another
# pipeline's run, or a truncated file, is reported by name rather than as "unbound variable".
for v in DATABASE_PATH TMPDIR REF REF_FAI REF_DICT BED BED_TBI; do
    [[ -n "${!v:-}" ]] || { echo "ERROR: $v is not set by $PATHS_ENV (PATHS_ENV must point at this pipeline's paths.env; unset it to use the default)" >&2; exit 1; }
done
mkdir -p "$TMPDIR" 2>/dev/null || { echo "ERROR: cannot create TMPDIR=${TMPDIR} (edit paths.env)" >&2; exit 1; }

missing=0
for f in "${SOMATICBUNNY_DIR}/main.nf" "$CLUSTER_CONFIG" "$TRACE_CONFIG" \
         "$REF" "$REF_FAI" "$REF_DICT" \
         "$BED" "$BED_TBI"; do
    [[ -f "$f" ]] || { echo "ERROR: file not found: $f" >&2; missing=1; }
done
[[ -d "$DATABASE_PATH" ]] || { echo "ERROR: database path not found: $DATABASE_PATH" >&2; missing=1; }
(( missing == 0 )) || exit 1

command -v nextflow >/dev/null 2>&1 || { echo "ERROR: nextflow not on PATH" >&2; exit 1; }
nextflow -version 2>&1 | grep -i "version" | head -n1 > nextflow_version.txt || true

# Benchmark runs are made once, from scratch: no -resume, and a launch directory that has not run before.
for a in "$@"; do
    [[ "$a" == -resume* ]] && { echo "ERROR: -resume is not allowed for a benchmark run: restart the dataset from scratch in a fresh launch directory" >&2; exit 1; }
done
[[ -e .nextflow/history ]] && { echo "ERROR: $(pwd) already holds a Nextflow run; use a fresh launch directory" >&2; exit 1; }

nextflow run "${SOMATICBUNNY_DIR}/main.nf" -profile conda \
    -c "$CLUSTER_CONFIG" --max_cpus 64 --max_memory 900.GB --max_time 240.h \
    --type genome --first_step mapping --genome GRCh38 \
    --publish recal_bam \
    --database_path "$DATABASE_PATH" \
    --ref "$REF" \
    --ref_fai "$REF_FAI" \
    --ref_dict "$REF_DICT" \
    --bed "$BED" \
    --bed_tbi "$BED_TBI" \
    --tool ascat,manta,delly,cnvkit \
    -c "$TRACE_CONFIG" \
    "$@"
