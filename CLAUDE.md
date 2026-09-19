# CLAUDE.md — nfl-data

NFL **data/publish** sibling of `sportsdataverse/nfl-raw` (the scraper). Consumes raw Shield JSON
committed in `nfl-raw`, reshapes it to nflfastR parity, trains EP/WP/CP/decision_models models, and publishes
datasets + model artifacts to GitHub Releases on `sportsdataverse/sportsdataverse-data`. Mirrors the
`cfbfastR-cfb-data` role for NFL. The uv project lives at the repo root (`pyproject.toml` + `uv.lock`);
the build code lives under `python/`.

## Commands

All commands run from the repo root (that is where `pyproject.toml` + `uv.lock` live); scripts are under `python/`.

```sh
cd python
uv sync --frozen                      # install from lockfile (CI uses --frozen)
uv run pytest                         # tests; integration marker is deselected by default
uv run pytest -m integration          # whole-corpus / network tests (need fetched JSON)

# 1. ingest raw JSON from nfl-raw into a local cache
uv run python -m nfl_data_ingest --seasons 2020:2024 --cache-dir .cache/nfl_raw

# 2. build the canonical model_pbp dataset (--enrich = EP/WP/CP/xYAC via sdv-py)
uv run python -m native_pbp build --enrich --seasons 2024 \
    --raw-dir .cache/nfl_raw --out out/model_pbp

# 3. publish (each subcommand builds + uploads; --dry-run plans without uploading)
uv run python -m nfl_model_publish pbp          --parquet-dir out/model_pbp --tag nfl_model_pbp
uv run python -m nfl_model_publish rosters      --seasons 2024      --out out/rosters
uv run python -m nfl_model_publish players      --out out/players
uv run python -m nfl_model_publish player-stats --seasons 1999:2024 --out out/player_stats
uv run python -m nfl_model_publish team-stats   --seasons 1999:2024 --out out/team_stats
uv run python -m nfl_model_publish qbr          --seasons 2006:2024 --out out/qbr
uv run python -m nfl_model_publish artifacts    --models models/ --tag nfl_model_artifacts

# 4. espn_nfl_* processed-game family (ESPN library in nfl-raw -> NFLPlayProcess -> 15 datasets)
uv run python -m nfl_espn_build --dataset all -s 2025 --workers 2            # cache finals + cut every dataset
uv run python python/espn_nfl_01_pbp_creation.py -s 2025 --publish           # one dataset, upload to its tag
bash scripts/espn_nfl_data.sh -s 2002 -e 2026                                # backfill; tail -f logs/espn_nfl_data_*.log
```

`--repo` defaults to `sportsdataverse/sportsdataverse-data` on every publish subcommand. The
`native_pbp` builder reads files at `{raw_dir}/{season}/*.json`.

## Conventions

- **Python `>=3.11`**, uv-packaged (PEP 621 `[project]` + PEP 735 `[dependency-groups]`); CI runs
  Python 3.12. polars `>=1.0,<2.0`, xgboost `>=2.0`. No `setup.py`.
- **sdv-py pin:** `sportsdataverse>=0.0.65` in `pyproject.toml`, BUT both cron workflows then
  `uv pip install "sportsdataverse @ git+...sportsdataverse-py.git@main"` because the producer
  surface (`calculate_xyac`, `build_nfl_rosters`, `build_nfl_players`, etc.) landed on sdv-py `main`
  after the pinned release. Re-pin to a PyPI release once it ships those (TODOs in the workflows).
- Commits: Conventional Commits. **Never add AI co-author trailers to commits or PRs.**

## Inputs / Outputs

Input: per-game Shield JSON from `sportsdataverse/nfl-raw` (`nfl/raw/{season}/{game_id}.json`).
Output: parquet uploaded to releases on `sportsdataverse/sportsdataverse-data` (one tag per dataset):

| Producer (`python -m ...`) | Release tag | Range | Source |
|---|---|---|---|
| `native_pbp build --enrich` → `nfl_model_publish pbp` | `nfl_model_pbp` | 1999– | nfl-raw JSON + sdv-py `enrich_nfl_pbp(method="lead_diff")` |
| `nfl_model_publish rosters` | `nfl_rosters` | per-season | NFL Shield rosters API |
| `nfl_model_publish players` | `nfl_players` | season-less | ESPN core-v2 athletes (~7,500 `$ref`s, dedup on espn_id; runs several minutes) |
| `nfl_model_publish player-stats` | `nfl_player_stats` | 1999– | aggregates SDV-native PBP release (week-level, REG+POST, offense) |
| `nfl_model_publish team-stats` | `nfl_team_stats` | 1999– | aggregates SDV-native PBP (offense+defense+kicking+returns) |
| `nfl_model_publish qbr` | `nfl_espn_qbr` | 2006– | ESPN `fitt/v3` QBR endpoint, nflverse-shape |
| `nfl_ratings_weekly` | `nfl_ratings_weekly` | 1999– | sdv-py `nfl_ratings(as_of_date=)` per week; `as_of_week` is STRICTLY EXCLUSIVE (fit on games before week W's first kickoff). Weekly in-season cron + dispatch (`nfl_ratings_weekly.yml`) |
| `nfl_team_summaries` (stage 06) | `nfl_team_summaries`, `nfl_passing`, `nfl_rushing`, `nfl_receiving`, `nfl_percentiles`, `nfl_player_percentiles` | 1999– | season grid off `nfl_model_pbp` (REG only): the college `team_summaries` column contract (`{metric}_{off\|def\|margin}[_pass\|_rush][_rank]`, drive efficiency, opponent-adjusted EPA via sdv-py `cfb_adjusted_epa`) + rbsdm.com extras (pass rate over expected, neutral pass rate, fourth-down decisions vs the model, luck) + QB CPOE/composite. Each ranked player metric also carries a `{metric}_pct` (Weibull percentile among the PFR-minimum qualifiers — 14 dropbacks / 6.25 carries / 1.875 targets per team-game — within (season, table); null metric -> null percentile), and `nfl_player_percentiles` publishes the matching thresholds (`position_group` x `pctile` x metric, low-is-good metrics read from the opposite tail). See README "Player percentiles". `team_id` is the **ESPN** id (vendored crosswalk `nfl_team_summaries/data/espn_team_ids.csv`); `pos_team` the nflverse abbr. Runs after stage 03 in `nfl_pbp_cron.yml`. |
| `nfl_espn_build` (`espn_nfl_01..63_*_creation.py`) | `espn_nfl_pbp`, `espn_nfl_team_box`, `espn_nfl_player_box`, `espn_nfl_drives`, `espn_nfl_play_participants`, `espn_nfl_adv_{team,passing,rushing,receiving,defensive,turnover,drives,situational,defensive_players,specialists}`, the usage box per game `espn_nfl_adv_{player_usage,position_group_usage,tackles,position_group_tackles,team_usage,drive_scripting}` and special teams `espn_nfl_adv_st_{kickers,punters,returners,blocks,team}` (shims 30-40; computed at BUILD time from each final's plays + participants by `sportsdataverse.football.usage_box`, so the installed sdv-py defines them) and their season leaderboards `espn_nfl_usage_{players,position_groups,tackles,position_group_tackles,teams,drive_scripting,st_kickers,st_punters,st_returners,st_blocks,st_team}` (shims 50-60; `aggregate_usage_box`, rates recomputed from summed counts), and the tendencies family `espn_nfl_team_tendencies` (season x team), `espn_nfl_coach_tendencies` (season x team x head coach; the coach of each game from the nflverse schedule's `home_coach`/`away_coach`, regular + postseason only) and `espn_nfl_coach_careers` (one season-less file summing every written coach season, rates recomputed) -- shims 61-63, `sportsdataverse.football.tendencies` over the season's plays at build time | 2002– | nfl-raw's **ESPN** library (`nfl/espn/raw\|plays`, read locally or over raw.githubusercontent.com) processed here with sdv-py `NFLPlayProcess` (offline: `espn_nfl_pbp(summary=)` + `play_participants_from_items`), one cached final per game (`.cache/nfl_espn_final`, stamped `processing_version` = `<sdv-py version>+[<sdv-py git sha>.]<SCHEMA_REV>`; a stale stamp is reprocessed and never enters a cut), then the same flatten/reshape rules as `cfbfastR-cfb-data`'s `espn_cfb_*`. The same stamp rides in each written parquet's file-level metadata and in each dataset's manifest `espn_nfl_{dataset}_in_data_repo.csv` (one row per season: `row_count`, `processing_version`, `generated_at_utc`), published to the tag next to the season parquet, so a tag always says which library state cut each season. **Bump `SCHEMA_REV` (`nfl_espn_build/config.py`) whenever a sdv-py change moves processed output**, then rerun the seasons -- the stamp check reprocesses them. `game_id` is the ESPN event id; `nflverse_game_id` / `season_type` ride along from the crosswalk. Tuesdays in season (`espn_nfl_cron.yml`). |
| `nfl_espn_build qa` (`espn_nfl_99_qa_creation.py`) | `espn_nfl_qa` | 2002– | **Report-only data-integrity gate.** One row per game from sdv-py's `sportsdataverse.validation.validate_game` (invariant rule table, era/league/source scoped): `ok`, `n_errors`, `n_warnings`, comma-joined `failed_rule_ids` / `warned_rule_ids`, `n_rows`, `processing_version`, `built_at`. The row is computed at PROCESS time and cached in the final (`SCHEMA_REV` 5), so a `--no-process` rebuild costs nothing. Each season also ships an `espn_nfl_qa_{season}_summary.json` sidecar: the season aggregate (`error_free_share`, `max_error_share`, `threshold_exceeded`, `blocking`, `counts_by_rule`) plus the pre-publish **drift** findings (`schema_contract` / `null_rate` / `constant_column` / `rate_anomaly` vs the previously published `espn_nfl_pbp` season asset). **Nothing fails the build on QA** — `nfl_espn_build.qa.BLOCKING` is `False`; `MAX_ERROR_SHARE` (0.30, re-seeded from the full 2026 season: 47/66 games error-free, `error_share` 0.2879) is a ratchet target lowered only with a ledger entry. |
| `nfl_model_publish artifacts` / `decision_models-artifacts` | `nfl_model_artifacts` | n/a | `.ubj` models + cards from `models/` (play_level/decision_models trainers) |

Consumed downstream by sdv-py `load_nfl_pbp(source="sdv")`, `load_nfl_espn_qbr(source="sdv")`, etc.

## Model registry

A row here is mandatory for every new published model/artifact family; "frozen" is a valid
cadence but must be stated explicitly. Trained artifacts publish via
`nfl_model_publish artifacts` (play_level → `nfl_model_artifacts`) and
`nfl_model_publish decision_models-artifacts` (xpass → `nfl_model_artifacts`; fd/wp →
`nfl_4th_down_models`; two_pt/fg/punt_data copied into the sdv-py bundle
`sportsdataverse/nfl/models/`, no release tag). Methodology cards: `docs/models/`; parity
framework: `docs/models/parity.md`. Retrains run from `.github/workflows/nfl_model_pipeline.yml` (annual 1 March cron + dispatch; publishing is an explicit opt-in input, off by default). "#14" = the era-aware 1999–2025 retrain
(`721fa97`, merged 2026-06-24).

| model | artifact(s) | release tag | training data (seasons/source) | fitting script | gates at publish | last retrain | cadence |
|---|---|---|---|---|---|---|---|
| EP (18-feat, 7-class softprob) | `ep_model.ubj` + card `.json` | `nfl_model_artifacts` (also bundled in sdv-py) | 1999–2025 nflfastR-parity PBP, 1,195,636 plays, era0..4 one-hot | `python/model_training/play_level/` | parity r≥0.98 vs nflfastR `ep` (r 0.996) + LOSO calibration | 2026-06-24 (#14) | annual (Mar 1 cron) + dispatch — `nfl_model_pipeline.yml` |
| WP spread (12-feat) | `wp_spread.ubj` + card | `nfl_model_artifacts` (also bundled) | 1999–2025, 1,268,220 plays | play_level | Brier ≤0.20; `vegas_wp` r 0.998 | 2026-06-24 (#14) | annual (Mar 1 cron) + dispatch — `nfl_model_pipeline.yml` |
| WP naive (11-feat) | `wp_naive.ubj` + card | `nfl_model_artifacts` (also bundled) | 1999–2025 (spread set minus spread) | play_level | Brier ≤0.20; `wp` r 0.997 | 2026-06-24 (#14) | annual (Mar 1 cron) + dispatch — `nfl_model_pipeline.yml` |
| CP (18-feat) | `cp_model.ubj` + card | `nfl_model_artifacts` (also bundled) | 339,706 charted passes, air-yards era 2006+ | play_level | `cpoe` scale-correct (percentage points) | 2026-06-24 (#14) | annual (Mar 1 cron) + dispatch — `nfl_model_pipeline.yml` |
| xYAC (76-class) | `xyac_model.ubj` + card | `nfl_model_artifacts` (download-on-demand, not bundled) | 222,020 completions 2006–2025 | play_level | faithful `add_xyac` port (sdv-py parity) | 2026-06-24 (#14) | annual (Mar 1 cron) + dispatch — `nfl_model_pipeline.yml` |
| xpass (19-feat) | `xpass_model.ubj` | `nfl_model_artifacts` (also bundled) | 1999–2025, 892,122 scrimmage plays | `python/model_training/decision_models/` | oracle corr 0.9895 (informational since era retrain) | 2026-06-24 (#14) | annual (Mar 1 cron) + dispatch — `nfl_model_pipeline.yml` |
| fd 4th-down gain (14-feat, 76-class) | `fd_model.ubj` | `nfl_4th_down_models` | 1999–2025, 182,138 3rd/4th-down plays | decision_models | mean-gain corr 0.9856 (informational) | 2026-06-24 (#14) | annual (Mar 1 cron) + dispatch — `nfl_model_pipeline.yml` |
| nfl4th decision WP (11-feat, home-persp.) | `wp_model.ubj` | `nfl_4th_down_models` | nfl4th `cal_data` calibration frame | decision_models (`train_wp`) | reproduction corr ≥0.99 (0.9947) | 2026-06-23 (#12; unchanged by #14) | frozen (cal_data-bound) |
| FG (7-feat XGBoost, was GAM) | `fg_model.ubj` | — (sdv-py bundle) | 1999–2025, 23,919 FG attempts | decision_models | attempted-cells corr 0.971 vs GAM grid (informational) | 2026-06-24 (#14) | annual (Mar 1 cron) + dispatch — `nfl_model_pipeline.yml` |
| two-point (9-feat) | `two_pt_model.ubj` | — (sdv-py bundle) | 2010–2025, 1,363 attempts | decision_models | corr 0.806 (vintage-drift ceiling, informational) | 2026-06-24 (#14) | annual (Mar 1 cron) + dispatch — `nfl_model_pipeline.yml` |
| punt distribution (empirical, not a model) | `punt_data.parquet` | — (sdv-py bundle) | full-history punts, 2-D KDE landing distribution | decision_models | freq-weighted TV ≤0.10 vs converted nfl4th dist | 2026-06-24 (#14) | annual (Mar 1 cron) + dispatch — `nfl_model_pipeline.yml` |
| QBR reconstruction (6-feat regression) | `qbr_model.ubj` | — (sdv-py bundle) | ESPN published raw Total QBR per QB-game; EPA components from the EP model | TODO — trainer not in this repo (card only: `docs/models/qbr.md`) | TODO | TODO | TODO |

## Gotchas

- **ESPN stub plays (2005, the 2004 Pro Bowl, the 2008 AFC Championship).** Those games' plays
  carry no `text`, in the summary and in the core items alike, so `NFLPlayProcess` cannot parse
  them and never will. `process_season` tallies them as `stub` (a warning) rather than `failed`,
  so the season's other games still build and publish; the stub games simply have no final.
- **No NGS scraper here.** NextGen Stats lives in sdv-py (`load_nfl_nextgen_stats`); references to
  "ngs" in this repo are PBP feature columns, not a producer.
- **Public-tier endpoints only.** Auth-walled Shield endpoints are excluded; rosters/players use the
  public rosters API + ESPN athletes.
- **QBR publishes only the *qualified* leaderboard** (`isqualified=true`) — byte-matches nflverse's
  qualified rows; nflverse's capture-time unqualified tail is intentionally not reproduced (no stable
  rule). `rank` is recomputed as R-style average-tie `rank(desc(qbr_total))`, not ESPN's integer rank.
- **`--clobber`/idempotent uploads:** republishing the same bytes is safe. Off-season cron runs
  (Mar–Aug) are effectively no-ops for `model_pbp` when nfl-raw is unchanged.
- **`SDV_GH_TOKEN` is required** for cross-repo publish (a PAT with `Contents: write` on
  sportsdataverse-data); `GITHUB_TOKEN` cannot do a cross-repo upload at all — it answers
  `403 Resource not accessible by integration`. This file used to name the secret
  `SDV_DATA_TOKEN`, which is provisioned nowhere in the org, and the rosters cron was written
  from that line: its first-ever run (2026-09-07) fell through a `|| secrets.GITHUB_TOKEN`
  fallback and 403'd after the whole build, while the pbp cron published fine the same morning
  on the standard name. Neither workflow carries a fallback now — an absent secret must fail
  as an absent secret, before the build rather than after it.
- **`--enrich` downloads ~34 MB of model artifacts** on first use (cached under
  `~/.cache/sportsdataverse`); the cron caches that path.
- `R/` is a small dataset-parity publish toolchain (`write_dataset`/`publish_dataset` via piggyback);
  the Python path is the primary pipeline.

## Reference

- `espn_nfl_*` family: `python/nfl_espn_build/` (`config.REGISTRY` is the dataset list; `process`
  runs the processor + cache, `build` cuts datasets, `publish` uploads per file). The numbered
  `python/espn_nfl_NN_*_creation.py` shims mirror `cfbfastR-cfb-data` (01 pbp, 02 team_box,
  03 player_box, 04 = all ten adv_* (20-29), 05 play_participants, 06 drives, 99 qa). Driver
  `scripts/espn_nfl_data.sh` (env: `NFL_RAW_DIR`, `ESPN_NFL_WORKERS`, `PUBLISH=1`); workflow
  `espn_nfl_cron.yml`. Processing is ~8 s a game: only a completed game (`state == "post"`) is
  cached, and a cached final is rebuilt when its stamp differs from the installed sdv-py.
  Fixture: `tests/fixtures/espn_nfl` (one real game, laid out like the raw library).
- Workflows: `.github/workflows/nfl_pbp_cron.yml` (model_pbp), `nfl_rosters_players_cron.yml`
  (rosters/players/player-stats/team-stats/qbr). Both: `workflow_dispatch` + cron
  `0 9 * 9-12,1,2 1` (Mondays 09:00 UTC, Sep–Feb); checkout nfl-data + nfl-raw, install uv,
  install sdv-py from git@main, publish with `SDV_GH_TOKEN`.
- `python/native_pbp/__init__.py` documents the build-module order (stat_ids → parse → players →
  description → features → labels → parity).
- `model_training/play_level/` (EP/WP/CP) + `decision_models/` (xpass + nfl4th 4th-down)
  are the model trainers; each track validates against the converted R artifact (parity oracle).
- `README.md`, `docs/raw-to-data-migration-playbook.md`, and the design spec under
  `docs/superpowers/specs/` cover the raw→data migration.
