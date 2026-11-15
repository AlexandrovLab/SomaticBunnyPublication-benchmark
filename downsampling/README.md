# Benchmark downsampling

This directory contains the procedure used to create the downsampled tumor/normal WGS FASTQs for the SomaticBunny vs. Sarek benchmark.

## Summary

| | Input coverage | Target coverage | Fraction kept |
|---|---|---|---|
| Tumor | 90x | 60x | 0.6666 |
| Normal | 40x | 30x | 0.7500 |

Read pairs were randomly subsampled with [`seqtk sample`](https://github.com/lh3/seqtk) in fraction mode, using seed `1234` for both R1 and R2 so mates stay paired. Fractions are computed as `target / current` with `bc` at `scale=4`, which truncates rather than rounds (60/90 → 0.6666).

## Input

Paired-end tumor/normal WGS FASTQs, one set per sample, named:

```
{sample}_tumor_1.fastq.gz   {sample}_tumor_2.fastq.gz
{sample}_normal_1.fastq.gz  {sample}_normal_2.fastq.gz
```

The samples used in the benchmark are listed in [`samples.txt`](samples.txt).

## Running

Requirements: `seqtk` (benchmark run used version 1.5-r133), `gzip`, `bc`, `bash` ≥ 4.

```bash
./downsample.sh \
    -s samples.txt \
    -i /path/to/original_fastq \
    -o /path/to/fastq_downsampled_60x_or_30x \
    --jobs 4
```

## Outputs

| File | Contents |
|---|---|
| `{sample}_{tumor,normal}_{1,2}.fastq.gz` | Downsampled FASTQs |
| `run_info.txt` | Date, host, command, seqtk/gzip versions, seed, fractions |
| `manifest.tsv` | Per sample/status: fraction, seed, and R1/R2 read counts |
| `logs/{sample}.log` | Per-sample log |

## Datasets of the benchmark

| Dataset | Tumor / normal coverage | How it was produced | Records |
|---|---|---|---|
| `wgs_90x` | 90x / 40x | the original TCGA FASTQs, no downsampling | `records/wgs_90x/fastq_list.txt` |
| `wgs_60x` | 60x / 30x | `downsample.sh` on the originals, fractions 0.6666 (tumor) and 0.7500 (normal), seed 1234 | `records/wgs_60x/run_info.txt`, `manifest.tsv` |
| `wgs_30x` | 30x / 30x | FILL IN: the `downsample.sh` call (target coverage or fraction) that produced the 30x tumors | `records/wgs_30x/run_info.txt`, `manifest.tsv` |
| `wes` | as sequenced | the TCGA WES FASTQs of `samples_wes.txt`, no downsampling | `records/wes/fastq_list.txt` |

Exact commands, as run (TSCC paths):

```bash
# wgs_60x: 60x tumor / 30x normal
./downsample.sh -s samples.txt -i <original FASTQ directory> -o <60x output directory> --jobs 4
# wgs_30x: FILL IN the command used, or paste the command line from that run's run_info.txt
```

`run_info.txt` (date, host, command, seqtk and gzip versions, seed, fractions) and `manifest.tsv`
(per sample and status: fraction, seed, R1/R2 read counts) are written by `downsample.sh` into its
output directory; copy them into `records/<dataset>/` and commit them. For the two undownsampled
datasets, `records/<dataset>/fastq_list.txt` lists the FASTQ files with their sizes and read counts
(`ls -l` and `zcat f | awk 'END{print NR/4}'`).
