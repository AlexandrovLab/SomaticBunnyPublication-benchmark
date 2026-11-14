# Benchmark metrics

Every metric below is computed by `scripts/benchmark_metrics.py` from the Nextflow run records,
with the same code for SomaticBunny and Sarek. Both pipelines are run with `config/trace.config`,
so their traces carry the same fields.

## Definitions

| Metric | Definition | Source |
|---|---|---|
| Wall-clock time | Duration of the `nextflow run` invocation, from launch to completion: task execution, scheduler queueing, conda environment creation and the head job's own work. Reported for the overall pipeline only. | `.nextflow/history` line of the run (`command.txt`) |
| Task realtime | Sum over completed tasks of the task's execution time (`realtime`): no queue wait. | trace |
| **CPU time used** (CPU-hours) | Sum over completed tasks of `realtime × %cpu / 100`. `%cpu` is Nextflow's measurement of the CPU the task's processes consumed (cgroup accounting), so this is CPU actually used, whatever was reserved. | trace |
| **Reserved core-hours** | Sum over every task attempt, failed and retried attempts included, of `cpus × realtime`, the CPUs the scheduler held for the task while it ran. This is what a cluster charges, and is sensitive to how a pipeline sizes its requests. | trace (`cpus` field) |
| Peak memory | Largest peak resident set size (`peak_rss`) of any single task. | trace |
| Disk | `du -sh` of the work directory and the results directory at the end of the run, before any cleanup. | `disk_usage.txt` |

"CPU-hours" in the manuscript means **CPU time used** unless stated otherwise; reserved core-hours
are reported next to it. Neither includes the head job.

## Stages

Each process is assigned to exactly one stage by name (`STAGES` in `scripts/benchmark_metrics.py`;
an unknown process name stops the script, so nothing is dropped silently).

| Stage | SomaticBunny | Sarek |
|---|---|---|
| Alignment/preprocessing | FastQC, bwa-mem2 + sort, quickchecks, MarkDuplicates, BaseRecalibrator / ApplyBQSR / gather / merge, mosdepth, Conpair | FastQC, fastp, bwa-mem2, MarkDuplicates, BaseRecalibrator / ApplyBQSR / gather, CRAM merge, index and conversion, samtools stats, mosdepth |
| SNV/indel calling | Mutect2 chain, Strelka2, MuSE, SAGE, consensus (`consensus_scenarios.sh`), VAF annotation | Mutect2 chain, Strelka2, MuSE, FreeBayes, VCF normalisation, consensus, VCF QC (bcftools/vcftools stats) |
| SV/CNV analysis | Manta, Delly, CNVkit, ASCAT | none in the benchmark configuration |
| Setup/reporting | interval lists | interval preparation, MultiQC, version dump |
| Overall pipeline | all of the above | all of the above |

## Known differences between the pipelines, stated rather than hidden

- Caller sets differ: Sarek runs FreeBayes where SomaticBunny runs SAGE.
- SomaticBunny runs SV/CNV tools (Manta, Delly, CNVkit, ASCAT) that the Sarek configuration does
  not; that stage has no Sarek counterpart.
- The GRCh38 reference and resource bundles differ (SomaticBunny: GRCh38.d1.vd1 and its database;
  Sarek: `GATK.GRCh38` from iGenomes with the dbSNP, known-indel, PON and gnomAD files listed in
  `sarek/paths.env`).
- Sarek splits each FASTQ into 50 M-read shards for alignment; SomaticBunny aligns each FASTQ pair
  in one task.
- Conda environments are created on first use in each launch directory for both pipelines; that
  time is in wall-clock, not in task realtime.
- Reserved core-hours depend on each pipeline's own resource requests (SomaticBunny
  `conf/base.config`; Sarek `conf/base.config` of release 3.8.1), with the cluster limits of
  `config/sarek_tscc.config` and SomaticBunny's `max_*` parameters applied identically.
