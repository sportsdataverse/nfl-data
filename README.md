# nfl-data

Builds NFL **compiled play-by-play datasets** and trains **EP / WP / CP models** from the raw NFL
game JSON committed in [`sportsdataverse/nfl-raw`](https://github.com/sportsdataverse/nfl-raw),
then publishes datasets + model artifacts to GitHub Releases on
[`sportsdataverse/sportsdataverse-data`](https://github.com/sportsdataverse/sportsdataverse-data).

Sibling of `nfl-raw` in the SportsDataverse `-raw` → `-data` split: `nfl-raw` scrapes and commits
raw JSON; `nfl-data` is the consumer that reshapes (with nflfastR parity), models, reports, and
publishes. See `docs/raw-to-data-migration-playbook.md` and
`docs/superpowers/specs/2026-06-17-nfl-raw-to-data-migration-design.md`.

## Layout

- `python/` — uv project. `native_pbp/` (compiled-PBP builder, nflfastR parity), `nfl_data_ingest/`
  (URL-ingest of nfl-raw JSON), `model_training/play_level/` (EP/WP/CP trainer + reports),
  `nfl_model_publish/` (artifact uploader). *(Populated across SP1–SP2.)*
- `R/` — dataset-parity publish toolchain (`write_dataset`/`publish_dataset` → parquet/rds/csv.gz via
  piggyback). *(Added in SP2.)*
- `docs/` — migration playbook, design spec, implementation plans, generated model reports.

## Develop

```sh
cd python
uv sync
uv run pytest          # hermetic suite (integration tests deselected by default)
```

## Automation & status

<!-- BEGIN GENERATED: status -->

| workflow | schedule | last run |
|---|---|---|
| [![nfl_model_pipeline.yml](https://github.com/sportsdataverse/nfl-data/actions/workflows/nfl_model_pipeline.yml/badge.svg)](https://github.com/sportsdataverse/nfl-data/actions/workflows/nfl_model_pipeline.yml) | day 1 06:00 UTC in Mar | never run |
| [![nfl_pbp_cron.yml](https://github.com/sportsdataverse/nfl-data/actions/workflows/nfl_pbp_cron.yml/badge.svg)](https://github.com/sportsdataverse/nfl-data/actions/workflows/nfl_pbp_cron.yml) | daily 09:00 UTC in Jan, Feb, Sep, Oct, Nov, Dec, dow 1 | 2026-06-30 |
| [![nfl_ratings_weekly.yml](https://github.com/sportsdataverse/nfl-data/actions/workflows/nfl_ratings_weekly.yml/badge.svg)](https://github.com/sportsdataverse/nfl-data/actions/workflows/nfl_ratings_weekly.yml) | daily 10:00 UTC in Jan, Feb, Sep, Oct, Nov, Dec, dow 2 | never run |
| [![nfl_rosters_players_cron.yml](https://github.com/sportsdataverse/nfl-data/actions/workflows/nfl_rosters_players_cron.yml/badge.svg)](https://github.com/sportsdataverse/nfl-data/actions/workflows/nfl_rosters_players_cron.yml) | daily 09:00 UTC in Jan, Feb, Sep, Oct, Nov, Dec, dow 1 | never run |
| [![orphan_scripts.yml](https://github.com/sportsdataverse/nfl-data/actions/workflows/orphan_scripts.yml/badge.svg)](https://github.com/sportsdataverse/nfl-data/actions/workflows/orphan_scripts.yml) | on push / PR / dispatch | 2026-08-19 |
| [![tests.yml](https://github.com/sportsdataverse/nfl-data/actions/workflows/tests.yml/badge.svg)](https://github.com/sportsdataverse/nfl-data/actions/workflows/tests.yml) | on push / PR / dispatch | 2026-08-19 |

<!-- END GENERATED: status -->
