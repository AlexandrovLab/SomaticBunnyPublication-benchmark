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
| SomaticBunny | tag `v1.0.1` | from a checkout of the tag, its `conda` profile, scheduler settings from `config/cluster.config` |
| nf-core/sarek | release `3.8.1` (`-r 3.8.1`) | directly from nf-core, scheduler settings from `config/cluster.config` and the four justified memory overrides of `config/sarek_resources.config`; nothing of Sarek's configuration tree is copied. 3.8.1 contains the SNV-consensus fix ([nf-core/sarek#2128](https://github.com/nf-core/sarek/pull/2128)) that earlier lab runs patched into 3.8.0 |
| Nextflow | 25.10.2 (`env/env_nf.yml`) | the same environment for both pipelines |

Both pipelines run with `config/trace.config`, which writes the trace with the `cpus` and `memory`
fields, the report and the timeline in the same way.

## Layout

```
config/        cluster.config (scheduler settings, both pipelines); trace.config (run records, both pipelines); sarek_resources.config (Sarek memory overrides)
somaticbunny/  run_somaticbunny_wgs.sh, run_somaticbunny_wes.sh, paths.env, samplesheets/
sarek/         run_sarek_wgs.sh, run_sarek_wes.sh, paths.env, samplesheets/, intervals/ (WGS intervals)
downsampling/  the WGS and WES sample IDs, how each dataset was produced, the records of each downsampling
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
2. **Scheduler settings, identical for both pipelines** (`config/cluster.config`, passed to both):
   SLURM, partition `platinum`, QoS `hcp-ddp302`, account `ddp302`, 100 jobs in the queue at once,
   one submission every 10 s, and a ceiling of 64 CPUs, 900 GB and 240 h for any single job
   (SomaticBunny also receives the ceiling through `--max_cpus/--max_memory/--max_time`).
3. **Resource requests.** Each pipeline uses its own defaults (SomaticBunny `conf/base.config`;
   Sarek `conf/base.config` of release 3.8.1). For Sarek, `config/sarek_resources.config` raises
   four memory requests and the retry count, each justified by the earlier traces (see the file).
   Tasks run on node-local scratch where the pipeline asks for it.
4. **Environments.** Conda, created on first use in each run's launch directory for both pipelines
   (that time is in wall-clock, not in task time).
5. **One launch directory per run**, holding the sample sheet (`sample.csv` for SomaticBunny, any
   name for Sarek) and nothing else before the run. A run is made exactly once, from scratch:
   `-resume` is refused by the run scripts, a directory that already holds a run is refused, and
   the metric script rejects traces with cached tasks. If a run fails, delete its launch directory
   and restart the dataset in a fresh one; note the restart in the commit message of its records.
6. **Launch** from that directory:

   ```bash
   # SomaticBunny (edit somaticbunny/paths.env or point PATHS_ENV at a filled-in copy)
   SOMATICBUNNY_DIR=/path/to/SomaticBunny-v1.0.0 bash /path/to/this/repo/somaticbunny/run_somaticbunny_wgs.sh   # or _wes.sh
   # Sarek (edit sarek/paths.env)
   bash /path/to/this/repo/sarek/run_sarek_wgs.sh /path/to/samplesheet.csv                                        # or _wes.sh
   ```

   Extra arguments are passed to `nextflow run` (`-resume` is refused).
7. **Records.** When the run has finished, from the same launch directory:

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

## Datasets and sample sheets

`downsampling/samples.txt` and `downsampling/samples_wes.txt` list the WGS and WES patients;
`downsampling/README.md` states how each WGS dataset was produced with the exact commands and keeps
the `run_info.txt` and `manifest.tsv` of every downsampling under `downsampling/records/`. The sample
sheets used for the runs are committed under `somaticbunny/samplesheets/` and `sarek/samplesheets/`.

## Text for the Methods

SomaticBunny v1.0.1 and nf-core/sarek 3.8.1 were run on the UCSD TSCC cluster (SLURM, platinum
partition) on the same five tumor/normal WGS pairs at 30x, 60x and 90x and on five WES pairs, with
the same Nextflow version (25.10.2), identical scheduler settings (100 queued jobs, one submission
per 10 s, a per-job ceiling of 64 CPUs, 900 GB and 240 h) and conda environments built on first
use. Each pipeline used its own published per-process resource requests. For Sarek, four memory
requests were raised (FreeBayes 24 GB, bwa-mem2 64 GB, BaseRecalibrator 8 GB, CalculateContamination
24 GB, each scaled by the attempt number) and the retry limit was set to 3, because earlier runs
showed the released values insufficient for these data (peak RSS 15, 43, 7.4 and 18 GB). Every run
was executed once from an empty directory, without resumption. CPU time used was computed as the sum
over completed tasks of task runtime x measured CPU utilisation; reserved core-hours as the sum over
all attempts, failed ones included, of allocated CPUs x runtime; wall-clock time as the duration of
the Nextflow run. Failed-attempt counts are reported with both. Processes were assigned to stages
(alignment/preprocessing, SNV/indel calling, SV/CNV analysis, setup) by name.

## Earlier runs

`runs/archive/sarek-3.8.0-lab-config/` holds the records of the Sarek runs made in August 2026 with
a copied and modified Sarek configuration; they are superseded by the runs made with this protocol
and kept only for the record.

## License

Scripts in this repository are released under the BSD 2-Clause License, copyright The Regents of
the University of California. `downsampling/` and the run scripts were moved here from the
SomaticBunny repository. The archived `base.config` is modified from nf-core/sarek (MIT License).
