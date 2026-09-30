# nfl-data

Builds NFL **compiled play-by-play datasets** and trains **EP / WP / CP models** from the raw NFL
game JSON committed in [`sportsdataverse/nfl-raw`](https://github.com/sportsdataverse/nfl-raw),
then publishes datasets + model artifacts to GitHub Releases on
[`sportsdataverse/sportsdataverse-data`](https://github.com/sportsdataverse/sportsdataverse-data).

Sibling of `nfl-raw` in the SportsDataverse `-raw` → `-data` split: `nfl-raw` scrapes and commits
raw JSON; `nfl-data` is the consumer that reshapes (with nflfastR parity), models, reports, and
publishes. See `docs/raw-to-data-migration-playbook.md` and
`docs/superpowers/specs/2026-06-17-nfl-raw-to-data-migration-design.md`.

## NFL workflow diagram

```mermaid
  graph LR;
    S[api.nfl.com Shield API]-->A[nfl-raw];
    A[nfl-raw]-->B[nfl-data];
    B[nfl-data]-->C1[nfl_model_pbp];
    B[nfl-data]-->C2[nfl_model_artifacts];
    B[nfl-data]-->C3[nfl_4th_down_models];
    B[nfl-data]-->C4[nfl_espn_qbr];
    B[nfl-data]-->C5[nfl_ratings_weekly];
    B[nfl-data]-->C6[nfl_rosters];
    B[nfl-data]-->C7[nfl_players];
    B[nfl-data]-->C8[nfl_player_stats];
    B[nfl-data]-->C9[nfl_team_stats];
```

```mermaid
flowchart TB;
    subgraph A[nfl-raw];
        direction TB;
        A0[python/nfl_raw_01_scrape.py]-->A1[python/nfl_raw_02_extract.py];
    end;

    subgraph B[nfl-data];
        direction TB;
        B0[python -m native_pbp build]-->B1[nfl_model_01_ep ... 05_xyac - scripts/nfl_models.sh];
        B1[nfl_model_01_ep ... 05_xyac - scripts/nfl_models.sh]-->B2[nfl_model_06_xpass ... 11_punt];
        B2[nfl_model_06_xpass ... 11_punt]-->B3[python -m nfl_model_publish pbp / artifacts];
        B3[python -m nfl_model_publish pbp / artifacts]-->B4[python -m nfl_ratings_weekly];
    end;

    subgraph C[sportsdataverse-data Releases];
        direction TB;
        C1[nfl_model_pbp];
        C2[nfl_model_artifacts];
        C3[nfl_4th_down_models];
        C4[nfl_espn_qbr];
        C5[nfl_ratings_weekly];
        C6[nfl_rosters];
        C7[nfl_players];
        C8[nfl_player_stats];
        C9[nfl_team_stats];
    end;

    A-->B;
    B-->C;
```

Drivers are the four cron workflows (`nfl_pbp_cron.yml`, `nfl_model_pipeline.yml`,
`nfl_ratings_weekly.yml`, `nfl_rosters_players_cron.yml`); each invokes the numbered
stages above (run subsets locally via `scripts/nfl_data.sh` / `scripts/nfl_models.sh`
by number or name). Raw per-game JSON is fetched from
[`nfl-raw`](https://github.com/sportsdataverse/nfl-raw) over HTTP — never a clone.

[nfl-raw repository (source: api.nfl.com Shield API)](https://github.com/sportsdataverse/nfl-raw)

[sportsdataverse-py (Shield wrappers, `.nfl` submodule)](https://github.com/sportsdataverse/sportsdataverse-py)

## Repository layout

<!-- BEGIN GENERATED: layout -->

```
nfl-data/
├── R/   # R pipeline stages and publish toolchain
│   ├── _data_utils.R
│   └── nfl_publish_model_pbp.R
├── dev/   # working notes, not part of the pipeline
├── docs/   # explainers, model reports and dataset docs
│   ├── models/
│   └── superpowers/
├── features/   # feature-set definitions
├── models/   # model artifacts, cards and the registry
├── models_fullhist/
├── out/
│   ├── nfl_ratings_weekly/
│   └── nfl_ratings_weekly_early/
├── python/   # Python pipeline stages, numbered in build order
│   ├── data/
│   ├── model_training/
│   ├── models/
│   ├── native_pbp/
│   ├── nfl_data_ingest/
│   ├── nfl_model_publish/
│   ├── nfl_ratings_weekly/
│   ├── nfl_team_summaries/
│   ├── out/
│   ├── conftest.py
│   ├── nfl_data_01_ingest.py
│   ├── nfl_data_02_model_pbp.py
│   ├── nfl_data_03_pbp_publish.py
│   ├── nfl_data_04_rosters_players.py
│   ├── nfl_data_05_ratings_weekly.py
│   ├── nfl_data_06_team_summaries.py
│   ├── nfl_model_01_ep.py
│   ├── nfl_model_02_wp_spread.py
│   └── … 9 more
├── scripts/   # bash drivers (the daily/weekly entry points)
│   ├── nfl_data.sh
│   └── nfl_models.sh
├── tests/   # test suite
│   ├── native_pbp/
│   ├── nfl_data_ingest/
│   ├── nfl_model_publish/
│   ├── __init__.py
│   ├── test_constants.py
│   ├── test_decision_models_parity.py
│   ├── test_decision_models_trainer_smoke.py
│   ├── test_feature_sets.py
│   ├── test_features.py
│   ├── test_fetcher.py
│   ├── test_figures_report.py
│   ├── test_fingerprint.py
│   ├── test_id_conventions.py
│   ├── test_ingest.py
│   ├── test_labels.py
│   ├── test_metrics.py
│   └── … 7 more
└── tools/   # repo-local helper scripts
    ├── hooks/
    └── nfl4th_models/
```

<!-- END GENERATED: layout -->

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

## Reports & explainers

<!-- BEGIN GENERATED: reports -->

| Report | What it is | Last updated |
|---|---|---|
| [Model registry](models/REGISTRY.md) | model | artifact | gates | retrain, one row per published model | 2026-09-01 |
| [Model reports & cards](docs/models/) | 14 files, one per item | 2026-09-01 |
| [`-raw` → `-data` Migration Playbook (CFB reference → NFL target)](docs/raw-to-data-migration-playbook.md) | explainer | 2026-06-24 |

<!-- END GENERATED: reports -->

## Automation & status

<!-- BEGIN GENERATED: status -->

| workflow | schedule | last run |
|---|---|---|
| [![nfl_model_pipeline.yml](https://github.com/sportsdataverse/nfl-data/actions/workflows/nfl_model_pipeline.yml/badge.svg)](https://github.com/sportsdataverse/nfl-data/actions/workflows/nfl_model_pipeline.yml) | day 1 06:00 UTC in Mar | never run |
| [![nfl_pbp_cron.yml](https://github.com/sportsdataverse/nfl-data/actions/workflows/nfl_pbp_cron.yml/badge.svg)](https://github.com/sportsdataverse/nfl-data/actions/workflows/nfl_pbp_cron.yml) | Mondays 09:00 UTC in Jan, Feb, Sep, Oct, Nov, Dec | 2026-06-30 |
| [![nfl_ratings_weekly.yml](https://github.com/sportsdataverse/nfl-data/actions/workflows/nfl_ratings_weekly.yml/badge.svg)](https://github.com/sportsdataverse/nfl-data/actions/workflows/nfl_ratings_weekly.yml) | Tuesdays 14:00 UTC in Jan, Feb, Sep, Oct, Nov, Dec | never run |
| [![nfl_rosters_players_cron.yml](https://github.com/sportsdataverse/nfl-data/actions/workflows/nfl_rosters_players_cron.yml/badge.svg)](https://github.com/sportsdataverse/nfl-data/actions/workflows/nfl_rosters_players_cron.yml) | Mondays 09:00 UTC in Jan, Feb, Sep, Oct, Nov, Dec | never run |
| [![orphan_scripts.yml](https://github.com/sportsdataverse/nfl-data/actions/workflows/orphan_scripts.yml/badge.svg)](https://github.com/sportsdataverse/nfl-data/actions/workflows/orphan_scripts.yml) | on push / PR / dispatch | 2026-08-28 |
| [![tests.yml](https://github.com/sportsdataverse/nfl-data/actions/workflows/tests.yml/badge.svg)](https://github.com/sportsdataverse/nfl-data/actions/workflows/tests.yml) | on push / PR / dispatch | 2026-08-28 |

| release tag | assets | size | last publish |
|---|---:|---:|---|
| [`nfl_4th_down_models`](https://github.com/sportsdataverse/sportsdataverse-data/releases/tag/nfl_4th_down_models) | 2 | 66.9 MB | 2026-06-24 |
| [`nfl_espn_qbr`](https://github.com/sportsdataverse/sportsdataverse-data/releases/tag/nfl_espn_qbr) | 2 | 0.4 MB | 2026-06-23 |
| [`nfl_model_artifacts`](https://github.com/sportsdataverse/sportsdataverse-data/releases/tag/nfl_model_artifacts) | 11 | 50.8 MB | 2026-06-24 |
| [`nfl_model_pbp`](https://github.com/sportsdataverse/sportsdataverse-data/releases/tag/nfl_model_pbp) | 27 | 168.7 MB | 2026-06-30 |
| [`nfl_player_stats`](https://github.com/sportsdataverse/sportsdataverse-data/releases/tag/nfl_player_stats) | 1 | 4.2 MB | 2026-06-23 |
| [`nfl_players`](https://github.com/sportsdataverse/sportsdataverse-data/releases/tag/nfl_players) | 1 | 0.4 MB | 2026-06-18 |
| [`nfl_ratings_weekly`](https://github.com/sportsdataverse/sportsdataverse-data/releases/tag/nfl_ratings_weekly) | 27 | 0.8 MB | 2026-08-07 |
| [`nfl_rosters`](https://github.com/sportsdataverse/sportsdataverse-data/releases/tag/nfl_rosters) | 24 | 5.1 MB | 2026-07-12 |
| [`nfl_team_stats`](https://github.com/sportsdataverse/sportsdataverse-data/releases/tag/nfl_team_stats) | 1 | 0.9 MB | 2026-06-23 |

<!-- END GENERATED: status -->

## Player percentiles

Every ranked metric on `nfl_passing` / `nfl_rushing` / `nfl_receiving` ships a
`{metric}_pct` column next to its `{metric}_rank`, and `nfl_player_percentiles`
carries the thresholds behind them. Five things a reader will otherwise get wrong:

1. **Percentile is among QUALIFIERS, not among all players.** The gate is
   Pro-Football-Reference's per-category minimum — **14 dropbacks**, **6.25
   carries** or **1.875 targets per team-game** — the same one gameonpaper.com's
   leaderboards advertise and the same one `_rank` uses. A receiver at the 50th
   percentile sits well above the median receiver; a UI that calls it "median"
   is lying.
2. **The position group is the table.** Percentiles are computed within
   (season, table), so a QB is placed against QBs.
3. **Weibull position `100 · (n + 1 − rank) / (n + 1)`** — nobody is pinned to
   exactly 0 or 100, which leaves room at both ends.
4. **A null metric yields a null percentile**, and null rows leave the
   denominator, so "unknown" never renders as "worst" or depresses everyone
   else's placing. (`_rank` still hands it a trailing rank — that is R's
   `na.last = TRUE`, kept for the leaderboard.)
5. **In-season percentiles move weekly** as the qualifier population grows.
   Expected, not a bug.

`nfl_player_percentiles` (release tag of the same name, one file per season) is
the player twin of `nfl_percentiles`: 297 rows × 27 columns — `position_group`
(`passing` / `rushing` / `receiving`) × `pctile` (0.01 … 0.99), one Float64
column per ranked metric (the union of the three tables' metrics; a metric a
group does not rank is null there), plus `season`. Direction is handled in the
table: for a **low-is-good** metric (`pass_int`, `sacked`, `fumbles`) the row at
`pctile = 0.90` holds the value a player with `{metric}_pct = 90` actually has —
a LOW count — so a bar drawn from these thresholds agrees with the player's own
`_pct` instead of contradicting it.

## Team opponent splits

`nfl_team_opponent_splits` is one row per team per regular-season game, so every
game has two rows. It feeds the vs-opponent bars on team-season pages, and its
columns match the college twin's `cfb_team_opponent_splits`. `epa_per_play`,
`success_rate` and `plays` come from the same scrimmage frame as
`team_summaries.EPAplay_off`: weight a team's rows by `plays` and you get its
season `EPAplay_off` back. The points are the game's final score.

| col_name | col_type | col_description |
| --- | --- | --- |
| season | Int64 | Season year (e.g. 2025). |
| team_id | Int64 | ESPN team id (vendored crosswalk). |
| opponent_id | Int64 | ESPN team id of the opponent. |
| game_id | Int64 | ESPN event id, from nfl-raw's `crosswalk/games.json`. Null before 2002, where ESPN has no library. |
| epa_per_play | Float64 | Mean EPA over the team's scrimmage plays in the game. |
| success_rate | Float64 | Share of those plays with EPA > 0. |
| points_for | Int64 | Team's final score. |
| points_against | Int64 | Opponent's final score. |
| plays | Int64 | Scrimmage plays behind `epa_per_play`. |
| is_home | Boolean | Team is the designated home team (true at a neutral site too). |
| week | Int64 | Week of the season. |
| season_type | Int64 | ESPN season-type code (2 = regular season). |
| nflverse_game_id | Utf8 | nflverse game id (e.g. `2025_01_KC_LAC`). |

## League averages

`nfl_league_averages` is the mean / median / sd / n baseline behind every
`_rank` / `_pct` column and the `percentiles` ladder — the college twin's
`cfb_league_averages`, ported straight over (`python/nfl_team_summaries/league_averages.py`
mirrors `cfbfastR-cfb-data`'s module of the same name; only the levels differ, since this
league has one tier where the college grid splits fbs/p4/g5). The grain is one row per
`(season, level, entity, category, metric)`, with `level` always `nfl` (no p4/g5-style
split in a single-tier league):

| col_name | col_type | col_description |
| --- | --- | --- |
| season | Int64 | Season year (e.g. 2025). |
| level | Utf8 | Always `nfl` in this league. |
| entity | Utf8 | Population the row is drawn from: `team` (`team_summaries`, `team_game`) or `player` (`passing`, `rushing`, `receiving`). |
| category | Utf8 | Source table the metric comes from: `team_summaries`, `passing`, `rushing`, `receiving`, or `team_game` (the per-game frame behind `percentiles`). |
| metric | Utf8 | Name of the summarized column (e.g. `EPAplay`, `TEPA`). Ids, ranks, percentiles and sample-size (`_n`) columns are never metrics. |
| mean | Float64 | **Unweighted mean of `metric` across qualifying, finite entity rows — not a pooled per-play rate.** Averaging 32 teams' EPA/play is not the same number as EPA/play over every play league-wide, and this column is always the former. |
| median | Float64 | Median of `metric` across the same rows. |
| sd | Float64 | Sample standard deviation (`ddof=1`); null when `n == 1` (no spread from a single value). |
| n | Int64 | Count of finite, qualifying rows the statistics are computed over — **the same denominator as the matching `{metric}_pct` column**, since a baseline is never taken over a different population than the percentile beside it. A null or non-finite metric value is skipped and does not count toward `n`. |
| qualifier_min | Float64 | The per-team-game leaderboard gate applied before summarizing a player category (14.0 dropbacks for `passing`, 6.25 carries for `rushing`, 1.875 targets for `receiving`); **null on the team categories** (`team_summaries`, `team_game`), which have no qualifier. |

## Consumers

The packages that read what this repo produces:

- **Python:** [`sportsdataverse.nfl (load_nfl_*)`](https://github.com/sportsdataverse/sportsdataverse-py) — docs at <https://py.sportsdataverse.org>
- nflreadpy-parity surface; see also the [nflverse](https://nflverse.nflverse.com) ecosystem

## Stage inventory

Every numbered pipeline stage in `python/` (auto-listed; run subsets with the `scripts/*.sh` drivers by number or name):

- `python/nfl_data_01_ingest.py`
- `python/nfl_data_02_model_pbp.py`
- `python/nfl_data_03_pbp_publish.py`
- `python/nfl_data_04_rosters_players.py`
- `python/nfl_data_05_ratings_weekly.py`
- `python/nfl_data_06_team_summaries.py` — season team grid + passing/rushing/receiving leaderboards + percentiles + league baselines (`nfl_team_summaries`, `nfl_passing`, `nfl_rushing`, `nfl_receiving`, `nfl_percentiles`, `nfl_player_percentiles`, `nfl_league_averages`, `nfl_team_opponent_splits`); the NFL twin of the college `team_summaries` family that gameonpaper.com's NFL pages read
- `python/nfl_model_01_ep.py`
- `python/nfl_model_02_wp_spread.py`
- `python/nfl_model_03_wp_naive.py`
- `python/nfl_model_04_cp.py`
- `python/nfl_model_05_xyac.py`
- `python/nfl_model_06_xpass.py`
- `python/nfl_model_07_fd.py`
- `python/nfl_model_08_two_pt.py`
- `python/nfl_model_09_fg.py`
- `python/nfl_model_10_wp.py`
- `python/nfl_model_11_punt.py`

Model release tags published from here: `nfl_4th_down_models`, `nfl_model_artifacts`, `nfl_model_pbp`
