# CLAUDE.md — nfl-data

NFL **data/publish** sibling of `sportsdataverse/nfl-raw` (the scraper). Consumes raw Shield JSON
committed in `nfl-raw`, reshapes it to nflfastR parity, trains EP/WP/CP/decision_models models, and publishes
datasets + model artifacts to GitHub Releases on `sportsdataverse/sportsdataverse-data`. Mirrors the
`cfbfastR-cfb-data` role for NFL. The uv project lives under `python/` (not the repo root).

## Commands

All commands run from `python/` (that is where `pyproject.toml` + `uv.lock` live).

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
| `nfl_model_publish artifacts` / `decision_models-artifacts` | `nfl_model_artifacts` | n/a | `.ubj` models + cards from `models/` (play_level/decision_models trainers) |

Consumed downstream by sdv-py `load_nfl_pbp(source="sdv")`, `load_nfl_espn_qbr(source="sdv")`, etc.

## Gotchas

- **No NGS scraper here.** NextGen Stats lives in sdv-py (`load_nfl_nextgen_stats`); references to
  "ngs" in this repo are PBP feature columns, not a producer.
- **Public-tier endpoints only.** Auth-walled Shield endpoints are excluded; rosters/players use the
  public rosters API + ESPN athletes.
- **QBR publishes only the *qualified* leaderboard** (`isqualified=true`) — byte-matches nflverse's
  qualified rows; nflverse's capture-time unqualified tail is intentionally not reproduced (no stable
  rule). `rank` is recomputed as R-style average-tie `rank(desc(qbr_total))`, not ESPN's integer rank.
- **`--clobber`/idempotent uploads:** republishing the same bytes is safe. Off-season cron runs
  (Mar–Aug) are effectively no-ops for `model_pbp` when nfl-raw is unchanged.
- **`SDV_DATA_TOKEN` is required** for cross-repo publish (a PAT with `Contents: write` on
  sportsdataverse-data); the `GITHUB_TOKEN` fallback fails for cross-repo uploads.
- **`--enrich` downloads ~34 MB of model artifacts** on first use (cached under
  `~/.cache/sportsdataverse`); the cron caches that path.
- `R/` is a small dataset-parity publish toolchain (`write_dataset`/`publish_dataset` via piggyback);
  the Python path is the primary pipeline.

## Reference

- Workflows: `.github/workflows/nfl_pbp_cron.yml` (model_pbp), `nfl_rosters_players_cron.yml`
  (rosters/players/player-stats/team-stats/qbr). Both: `workflow_dispatch` + cron
  `0 9 * 9-12,1,2 1` (Mondays 09:00 UTC, Sep–Feb); checkout nfl-data + nfl-raw, install uv,
  install sdv-py from git@main, publish with `SDV_DATA_TOKEN`.
- `python/native_pbp/__init__.py` documents the build-module order (stat_ids → parse → players →
  description → features → labels → parity).
- `model_training/play_level/` (EP/WP/CP) + `decision_models/` (xpass + nfl4th 4th-down)
  are the model trainers; each track validates against the converted R artifact (parity oracle).
- `README.md`, `docs/raw-to-data-migration-playbook.md`, and the design spec under
  `docs/superpowers/specs/` cover the raw→data migration.
