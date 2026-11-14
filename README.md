# SomaticBunny publication benchmark

Everything needed to reproduce the comparison of [SomaticBunny](https://github.com/AlexandrovLab/SomaticBunny)
with [nf-core/sarek](https://nf-co.re/sarek) reported in the SomaticBunny manuscript: the protocol
of both pipelines, the exact release versions, the cluster overlay configurations, the sample
sheets, the downsampling procedure, every run's records (trace, report, timeline, parameters, tool
versions, disk, database hashes), the metric definitions and the code that computes the tables and
figures. The SomaticBunny repository itself holds only the pipeline.

## Versions

| Pipeline | Version | How it is run |
|---|---|---|
| SomaticBunny | tag `v1.0.0` | from a checkout of the tag, with its own `nextflow.config` (`-profile tscc_slurm,conda`) |
| nf-core/sarek | release `3.8.1` (`-r 3.8.1`) | directly from nf-core, with `config/sarek_tscc.config` as the only cluster configuration; nothing of Sarek's configuration tree is copied. 3.8.1 contains the SNV-consensus fix ([nf-core/sarek#2128](https://github.com/nf-core/sarek/pull/2128)) that earlier lab runs patched into 3.8.0 |
| Nextflow | 25.10.2 (`env/env_nf.yml`) | the same environment for both pipelines |

Both pipelines run with `config/trace.config`, which writes the trace with the `cpus` and `memory`
fields, the report and the timeline in the same way.

## Layout

```
config/        trace.config (run records, both pipelines); sarek_tscc.config (Sarek cluster overlay)
somaticbunny/  run_somaticbunny_wgs.sh, run_somaticbunny_wes.sh, paths.env, samplesheets/
sarek/         run_sarek_wgs.sh, run_sarek_wes.sh, paths.env, samplesheets/, intervals/ (WGS intervals)
downsampling/  how the WGS FASTQs were downsampled (seqtk), sample list
env/           env_nf.yml
runs/          one directory of records per completed run, runs/<pipeline>/<dataset>/ (runs/README.md)
scripts/       collect_provenance.sh, benchmark_metrics.py, plot_metrics.py, resource_usage.py, pon_flag_counts.py
tables/        metrics.tsv, pon_flag_counts.tsv (generated)
figures/       one PNG per metric (generated)
METRICS.md     metric and stage definitions
```

## Datasets

Five TCGA tumor/normal WGS pairs (`downsampling/samples.txt`) at three tumor coverages (30x, 60x,
90x; see `downsampling/README.md` for how they were produced) and five TCGA tumor/normal WES
pairs. Each pipeline is run once per dataset, so eight runs in all: `wgs_30x`, `wgs_60x`,
`wgs_90x`, `wes` for each pipeline. FASTQ paths are not part of this repository; the sample sheets
under `*/samplesheets/` are templates.

## Protocol

Both pipelines, every dataset, the same way:

1. **Cluster.** UCSD TSCC, `platinum` partition, SLURM executor. The head job is an interactive
   session, `srun -N 1 -n 1 -c 64 --mem 900G -t 100:00:00 -p platinum -q hcp-ddp302 -A ddp302 --pty bash`,
   with `NXF_OPTS='-Xms1g -Xmx4g'` (set by the run scripts).
2. **Resource requests.** Each pipeline uses its own defaults (SomaticBunny `conf/base.config`;
   Sarek `conf/base.config` of release 3.8.1), capped at 64 CPUs, 900 GB and 240 h for both
   (SomaticBunny `max_*` parameters; `resourceLimits` in `config/sarek_tscc.config`). Tasks run on
   node-local scratch where the pipeline asks for it.
3. **Environments.** Conda, created on first use in each run's launch directory for both pipelines
   (that time is in wall-clock, not in task time).
4. **One launch directory per run**, holding the sample sheet (`sample.csv` for SomaticBunny, any
   name for Sarek) and nothing else before the run.
5. **Launch** from that directory:

   ```bash
   # SomaticBunny (edit somaticbunny/paths.env or point PATHS_ENV at a filled-in copy)
   SOMATICBUNNY_DIR=/path/to/SomaticBunny-v1.0.0 bash /path/to/this/repo/somaticbunny/run_somaticbunny_wgs.sh   # or _wes.sh
   # Sarek (edit sarek/paths.env)
   bash /path/to/this/repo/sarek/run_sarek_wgs.sh /path/to/samplesheet.csv                                        # or _wes.sh
   ```

   Extra arguments are passed to `nextflow run` (`-resume` after an infrastructure failure).
6. **Records.** When the run has finished, from the same launch directory:

   ```bash
   bash /path/to/this/repo/scripts/collect_provenance.sh somaticbunny wgs_30x --db /path/to/SomaticBunny_database
   bash /path/to/this/repo/scripts/collect_provenance.sh sarek wgs_30x
   ```

   writes `runs/<pipeline>/<dataset>/` (command line and duration, trace, report, timeline,
   parameters, Nextflow and tool versions, disk usage, database hash check), to be committed.
   `work/` is deleted only after the disk measurement.

The SomaticBunny runs use `--publish recal_bam` and all optional tools (`--tool ascat,manta,delly,cnvkit`
for WGS; `ascat,manta,cnvkit` for WES, with the capture targets as `--callable_bed`). The Sarek runs
use `--tools mutect2,strelka,freebayes,muse --only_paired_variant_calling --snv_consensus_calling
--consensus_min_count 2 --normalize_vcfs` with `--wes` and the exome BED as `--intervals` for WES,
and the 20 WGS intervals of `sarek/intervals/` for WGS. See the run scripts for every option.

## Metrics and tables

Definitions are in [`METRICS.md`](METRICS.md). "CPU-hours" means CPU time actually used
(`realtime × %cpu`); reserved core-hours (`cpus × realtime`) are reported next to it; both are
computed identically for the two pipelines, overall and per stage (alignment/preprocessing,
SNV/indel calling, SV/CNV analysis, setup), because the workflows are not identical (FreeBayes vs
SAGE, SV/CNV tools only in SomaticBunny, different GRCh38 resource bundles).

```bash
python3 scripts/benchmark_metrics.py \
    --run SomaticBunny_WGS30x=runs/somaticbunny/wgs_30x --run Sarek_WGS30x=runs/sarek/wgs_30x \
    --run SomaticBunny_WES=runs/somaticbunny/wes       --run Sarek_WES=runs/sarek/wes \
    --out tables/metrics.tsv
python3 scripts/plot_metrics.py tables/metrics.tsv figures/
```

`scripts/resource_usage.py runs/somaticbunny/*` lists per-process peak memory, CPU use and
realtime from the run records (used to size SomaticBunny's resource requests).

## Panel-of-normals flag in the SomaticBunny consensus

SomaticBunny's scenario 6 keeps a variant that Mutect2 flagged `panel_of_normals` when two other
callers pass it (the veto, `--pon_veto true`, is off by default). The number of such variants in
each benchmark run, per sample and variant type, is reported with

```bash
python3 scripts/pon_flag_counts.py /path/to/launch_dir/RESULTS/POST --out tables/pon_flag_counts_<dataset>.tsv
```

## Earlier runs

`runs/archive/sarek-3.8.0-lab-config/` holds the records of the Sarek runs made in August 2026 with
a copied and modified Sarek configuration; they are superseded by the runs made with this protocol
and kept only for the record.

## License

Scripts in this repository are released under the BSD 2-Clause License, copyright The Regents of
the University of California. `downsampling/` and the run scripts were moved here from the
SomaticBunny repository. The archived `base.config` is modified from nf-core/sarek (MIT License).
