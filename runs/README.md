# Run records

One directory per completed benchmark run, `runs/<pipeline>/<dataset>/`, written by
`scripts/collect_provenance.sh` from the launch directory of the run:

| Pipeline | Datasets |
|---|---|
| `somaticbunny/` | `wgs_30x`, `wgs_60x`, `wgs_90x`, `wes` |
| `sarek/` | `wgs_30x`, `wgs_60x`, `wgs_90x`, `wes` |

Each holds `command.txt` (the `.nextflow/history` line: exact command, duration, run name), the
trace, report and timeline produced with `config/trace.config`, the resolved parameters, the
Nextflow version, the tool versions of every conda environment, the disk measurement and, for
SomaticBunny, the database hash check. A run that has not been performed has no directory.

Every run is made once, from scratch. A run that failed is restarted in a fresh launch directory;
its records are not kept, and the restart is noted in the commit message of the final records.

`archive/sarek-3.8.0-lab-config/` keeps the traces, parameters and versions of the earlier Sarek
runs (August 2026) together with the copied Sarek configuration they used (`nextflow.config`,
`base.config` with raised resource requests). They are superseded by the `sarek/` runs made with
the pinned release and `config/sarek_tscc.config`, and are kept for the record only.
