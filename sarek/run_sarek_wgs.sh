#!/usr/bin/env bash
#######################################################################
# SomaticBunny benchmark: nf-core/sarek 3.8.1 on WGS (30x, 60x, 90x)
#
# The pinned release is run directly from nf-core; the only configuration added is the cluster overlay
# (config/sarek_tscc.config) and the run-record settings shared with SomaticBunny (config/trace.config).
# Run records go to runs/sarek/<dataset>/ afterwards (scripts/collect_provenance.sh).
#######################################################################

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BENCH_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"          # this repository
SAMPLESHEET="${1:-./samplesheet.csv}"
shift || true
CLUSTER_CONFIG="${BENCH_DIR}/config/sarek_tscc.config"   # executor, queue, node limits only
TRACE_CONFIG="${BENCH_DIR}/config/trace.config"           # trace/report/timeline, same for both pipelines
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

source "$PATHS_ENV"
set +a
# Every variable the run needs must come from the paths file. A PATHS_ENV left over from another
# pipeline's run, or a truncated file, is reported by name rather than as "unbound variable".
for v in DATABASE_PATH TMPDIR DBSNP_VCF DBSNP_TBI KNOWN_INDELS KNOWN_INDELS_TBI PON_VCF PON_TBI GERMLINE_RESOURCE INTERVALS; do
    [[ -n "${!v:-}" ]] || { echo "ERROR: $v is not set by $PATHS_ENV (PATHS_ENV must point at this pipeline's paths.env; unset it to use the default)" >&2; exit 1; }
done
mkdir -p "$TMPDIR" 2>/dev/null || { echo "ERROR: cannot create TMPDIR=${TMPDIR} (edit paths.env)" >&2; exit 1; }

missing=0
for f in "$SAMPLESHEET" "$CLUSTER_CONFIG" "$TRACE_CONFIG" \
         "$DBSNP_VCF" "$DBSNP_TBI" "$KNOWN_INDELS" "$KNOWN_INDELS_TBI" \
         "$PON_VCF" "$PON_TBI" "$GERMLINE_RESOURCE" "$INTERVALS"; do
    [[ -f "$f" ]] || { echo "ERROR: file not found: $f" >&2; missing=1; }
done
(( missing == 0 )) || exit 1

command -v nextflow >/dev/null 2>&1 || { echo "ERROR: nextflow not on PATH" >&2; exit 1; }
nextflow -version 2>&1 | grep -i "version" | head -n1 > nextflow_version.txt || true

nextflow run nf-core/sarek -r 3.8.1 -profile conda \
    --input "$SAMPLESHEET" --step mapping --outdir ./results \
    --aligner bwa-mem2 --genome GATK.GRCh38 \
    --tools mutect2,strelka,freebayes,muse \
    -c "$CLUSTER_CONFIG" -c "$TRACE_CONFIG" \
    --dbsnp "$DBSNP_VCF" \
    --dbsnp_tbi "$DBSNP_TBI" \
    --known_indels "$KNOWN_INDELS" \
    --known_indels_tbi "$KNOWN_INDELS_TBI" \
    --pon "$PON_VCF" \
    --pon_tbi "$PON_TBI" \
    --germline_resource "$GERMLINE_RESOURCE" \
    --only_paired_variant_calling \
    --snv_consensus_calling \
    --consensus_min_count 2 \
    --intervals "$INTERVALS" \
    --normalize_vcfs \
    "$@"
