# NFL `nfl-raw` → `nfl-data` Migration — Design Spec

- **Date:** 2026-06-17
- **Author:** Saiem Gilani
- **Status:** Draft (pending review)
- **Template:** the cfbfastR-cfb-raw → cfbfastR-cfb-data migration (June 2026); see
  `nfl-raw/docs/raw-to-data-migration-playbook.md`.

## 1. Goal

Split `nfl-raw` along the SportsDataverse `-raw` / `-data` boundary so that **`nfl-raw` is
scraping-only** (fetch NFL Shield-API JSON → commit raw per-game files to git) and a new
**`nfl-data`** repo owns everything downstream: reading the raw JSON by URL, building the compiled
play-by-play dataset (with nflfastR parity), training the EP/WP/CP models (Track 6), rendering model
reports, and publishing datasets + artifacts to GitHub Releases. The trained NFL models then replace
sdv-py's placeholder CFB-shape `nfl/models/*.ubj`.

## 2. Background — current state

`nfl-raw` today mixes all three responsibilities in one repo (the pre-migration state cfb-raw was in):

| Path | Role | Disposition |
|---|---|---|
| `python/scrape_nfl_json.py`, `python/extract_nfl_games.py` | scrape Shield API → per-game JSON | **stays in nfl-raw** |
| `nfl/raw/{season}/{game_id}.json` (3.1 GB) | committed raw JSON | **stays in nfl-raw** |
| `python/native_pbp/` (`build/features/labels/parity/parse/description/stat_ids`) | compiled-PBP builder w/ nflfastR parity | **moves → nfl-data** |
| `python/model_training/track6_nfl_ep_wp/` | EP/WP/CP trainer + reporting suite + model cards + validate/CLI | **moves → nfl-data** |
| `models/*.ubj` | trained models | **published from nfl-data** |
| `pyproject.toml` deps `xgboost`, `numpy`, `figures` group (`plotnine`, `scikit-misc`) | modeling deps | **dropped from nfl-raw in SP3** |

Facts established:
- **`nfl-data` does not exist as a git repo** (empty local dir; no GitHub repo in either org). It must
  be stood up — unlike CFB, where the data repo pre-existed.
- **`nfl-raw` has no git remote** — it is local-only. The producer==consumer URL-ingest seam requires
  nfl-raw to be pushed to GitHub first.
- **Org decision (locked):** all three repos live under **`sportsdataverse`**; datasets/artifacts
  publish to **`sportsdataverse/sportsdataverse-data`**.
- **Track 6 modeling is real and substantially built** (recent commits: native-source training +
  a model-reporting suite with calibration figures, LOSO, cards, report CLI) — SP1 is a genuine move
  of working code, and SP2 reporting largely exists already.
- **sdv-py NFL models are placeholders:** `sportsdataverse/nfl/models/*.ubj` are 8/13-feat CFB-shape
  copies; the real NFL contract is **18 EP / 12 WP-spread / 11 WP-naive** (see `nfl-raw/HANDOFF.md`).

## 3. Architecture (producer == consumer)

```
nfl-raw  (sportsdataverse/nfl-raw)                 nfl-data (sportsdataverse/nfl-data)
  scrape_nfl_json.py → nfl/raw/{season}/{gid}.json
        │ committed to git, pushed to GitHub
        ▼ read by raw.githubusercontent URL (RAW_BASE)
                                       nfl_data_ingest/  → cached raw JSON
                                       native_pbp/       → compiled PBP parquet (nflfastR parity)
                                       track6_nfl_ep_wp/ → EP/WP/CP .ubj + cards + reports
                                                │
                            ┌───────────────────┴───────────────────┐
                Python publisher (gh)                   R publisher (piggyback)
                nfl_model_artifacts  (.ubj + cards)      nfl_model_pbp (parquet/rds/csv.gz)
                            └──────────── sportsdataverse/sportsdataverse-data ────────────┘
```

The compiled PBP is the same code that feeds training, so producer and consumer share one code path
(parity by construction). nflfastR parity (`native_pbp/parity.py`) is the dataset's correctness gate.

## 4. Division of labor (locked)

- **Python** owns: ingest, compiled-PBP build, model training, reports, and **artifact** publishing
  (`.ubj`/`.pkl` + cards via `gh release`).
- **R** owns: **dataset-parity publishing** — `write_dataset` (parquet + rds + gzipped-csv) →
  `publish_dataset` → piggyback to `sportsdataverse-data`. Ported from cfb-data in its **hardened**
  form (see §7).

## 5. Sub-projects

Each sub-project is its own plan + subagent-driven execution with review gates, in order.

### SP0 — stand up the repos
- Push existing local `nfl-raw` to **`sportsdataverse/nfl-raw`** (`gh repo create` + initial push).
  ⚠️ ~3.1 GB first push (commit-to-repo pattern, as cfb-raw); slow but viable.
- Create **`sportsdataverse/nfl-data`**: `gh repo create`, `git init`, uv scaffold (`python/`
  project, `pyproject.toml`, `[dependency-groups]`), hermetic `integration` pytest marker
  (`addopts='-m "not integration"'`), `R/` directory, `docs/` (this spec + playbook), `.gitignore`
  (exclude `nfl/`, `.cache/`, build artifacts).
- **Deliverable:** both repos exist on GitHub; nfl-data has a green empty-skeleton test run.

### SP1 — lift-and-shift + ingest seam
- `git mv` `native_pbp/` and `model_training/track6_nfl_ep_wp/` (+ their tests/fixtures) from nfl-raw
  into nfl-data `python/`.
- New `nfl_data_ingest/` — reads `nfl-raw/nfl/raw/{season}/{game_id}.json` by `RAW_BASE` URL (keyed
  off the schedule master), with a local cache (mirror `cfb_data_ingest`).
- Wire `native_pbp` build to consume the ingest (it already supports `source="native"`); produce the
  compiled PBP parquet per season.
- Carry over the `figures`/training dep groups to nfl-data's `pyproject.toml`.
- **Deliverable:** `python -m native_pbp build` and the track-6 trainer run end-to-end in nfl-data off
  URL-ingested raw; hermetic tests green; nflfastR parity check passes on a sample.

### SP2 — reports + publish
- Wire the existing track-6 **report suite** (calibration figures, LOSO, cards, report CLI) to write
  committed Markdown under `nfl-data/docs/models/`.
- **Python artifact publisher** (`nfl_model_publish`, mirror `cfb_model_publish`): `gh release` upload
  of `.ubj` + cards to tag **`nfl_model_artifacts`**, with create-release-if-missing.
- **R dataset publisher** (§7): `R/nfl_publish_model_pbp.R` reads the compiled-PBP parquet →
  `write_dataset` → `publish_dataset` to tag **`nfl_model_pbp`** (parquet/rds/csv.gz), gated by an
  env flag (`NFL_PUBLISH=1`).
- **Deliverable:** both tags exist on `sportsdataverse-data` with the expected assets; reports
  committed.

### SP3 — decommission modeling from nfl-raw
- `git rm` `native_pbp/` + `track6_nfl_ep_wp/` (+ tests/fixtures) from nfl-raw.
- Drop modeling-only deps from nfl-raw `pyproject.toml`: `xgboost`, `numpy` (if only modeling used it —
  verify), the `figures` group. Keep `sportsdataverse`, `polars`. Re-lock.
- Boundary gate: `git grep` proves no surviving scraper/test imports a removed package; the scraping
  suite stays green; scraper modules import clean.
- **Deliverable:** nfl-raw is scraping-only; squash-merge PR.

### SP4 — sdv-py handoff (gated)
- Replace sdv-py `sportsdataverse/nfl/models/{ep_model,wp_spread}.ubj` with the trained NFL models and
  add `wp_naive.ubj` (new). Update `nfl/model_vars.py` to the NFL feature contract (18 EP / 12
  WP-spread / 11 WP-naive) + the start/end/touchback column selectors; wire `wp_naive` into
  `nfl_pbp.py`.
- **Gated** by `HANDOFF.md`: EP corr ≥ 0.98 vs nflfastR on sample games; WP Brier ≤ 0.20 on held-out
  2023; saved-model feature names match the loader contract.
- Own reviewed sdv-py PR; never auto-overwrite. Fixes the placeholder-models CI-red issue.
- **Deliverable:** sdv-py NFL EPA/WPA computed from real NFL models, parity-gated.

## 6. Release tags

On `sportsdataverse/sportsdataverse-data` (registered idempotently in `nfl-data/R/releases_init.R`):

- **`nfl_model_pbp`** — compiled NFL play-by-play dataset (parquet/rds/csv.gz, per season). R-published.
- **`nfl_model_artifacts`** — trained `.ubj` (EP/WP-spread/WP-naive/CP) + model cards. Python-published.

(No `espn_` prefix — NFL source is the Shield API/nflverse, not ESPN.)

## 7. R toolchain (ported hardened from cfb-data)

`nfl-data/R/` mirrors cfb-data's R side, **including the fixes landed during the CFB publish work** so
NFL avoids re-hitting them:

- **`_data_utils.R`** — `write_dataset(df, dataset, season, stem)` (parquet/rds/csv.gz +
  `stringify_list_cols`); `publish_dataset(dataset, season, stem, tag)`; `pb_upload_both(file, tag)`.
  Constant: `PUBLISH_REPOS = c("sportsdataverse/sportsdataverse-data")`. Unlike cfb-data, the NFL R
  side is **publish-only** — reshaping/compiled-PBP is Python (`native_pbp`), so there is no R-side
  raw reading and **no `RAW_BASE`** is needed (the R script reads the Python-built parquet from disk).
  - **Source-guard** any script's `source("R/_data_utils.R")` on **`publish_dataset`** (a name unique
    to the file), NEVER `write_dataset` — `library(arrow)` exports its own `write_dataset()`, which
    would make an `exists("write_dataset")` guard skip the source and shadow the custom writer.
  - **`pb_upload_both` is self-sufficient:** create the release if missing, busting **both** the
    `pb_releases` and `pb_info` memoise caches and **polling until the tag is visible** before
    `pb_upload` (GitHub's list-releases endpoint lags create by up to ~70s; pay the wait once on the
    first asset). `pb_release_create` warns (HTTP 422) when present → suppressed.
- **`releases_init.R`** — idempotent `pb_release_create` for `nfl_model_pbp` + `nfl_model_artifacts`.
- **`nfl_publish_model_pbp.R`** — reads the Python-built compiled-PBP parquet → `write_dataset` →
  (if `NFL_PUBLISH=1`) `publish_dataset(...,"nfl_model_pbp")`.

**New dependency:** nfl-data gains an R toolchain (R + `arrow`, `piggyback`, `cli`, `optparse`,
`readr`, `dplyr`) for CI + local. nfl-raw remains Python-only.

## 8. Decisions (locked)

| # | Decision | Choice |
|---|---|---|
| 1 | Org / homes | `sportsdataverse/nfl-raw` + `sportsdataverse/nfl-data`; publish to `sportsdataverse/sportsdataverse-data`. |
| 2 | nfl-raw push | Push the 3.1 GB committed-JSON repo to GitHub (commit-to-repo pattern; prerequisite for URL-ingest). |
| 3 | Dataset publish | **R toolchain** — parquet + **rds** + csv.gz via `write_dataset`/`publish_dataset` (ported hardened from cfb-data). |
| 4 | Artifact publish | Python `gh release` (`.ubj` + cards). |
| 5 | Tags | `nfl_model_pbp` (dataset), `nfl_model_artifacts` (models). |
| 6 | sdv-py handoff | In scope as SP4, **parity-gated**, own reviewed PR, no auto-overwrite. |
| 7 | Scope this pass | Full: spec + plan, then execute SP0→SP4 via subagent-driven dev with review gates. |

## 9. Risks

- **3.1 GB initial push** to a fresh repo — slow; may need chunked pushing or a one-time large push.
  No git-lfs (the pattern commits JSON directly).
- **SP4 is a breaking sdv-py change** (model shapes 8/13 → 18/12/11) — must pass the nflfastR parity
  gate before merge; staged behind its own PR.
- **R toolchain in CI** — nfl-data CI must provision R + arrow/piggyback (heavier than a Python-only
  repo). Mitigate by gating R publish behind `NFL_PUBLISH=1` (R not needed for the default test run).
- **nflfastR parity drift** — `native_pbp/parity.py` is the gate; a parser change that breaks parity
  must fail CI before it can corrupt a release.

## 10. Verification

- **SP0:** both repos on GitHub; `gh repo view` succeeds; nfl-data empty-skeleton `uv run pytest`
  green.
- **SP1:** `native_pbp build` + track-6 trainer run off URL-ingest; parity check passes on a sample
  season; hermetic suite green.
- **SP2:** `nfl_model_pbp` + `nfl_model_artifacts` releases carry expected assets; reports committed;
  R publisher dry-run lists the 3 formats.
- **SP3:** `git grep` boundary gate empty; scraping suite green; scrapers import clean; modeling deps
  gone from nfl-raw pyproject.
- **SP4:** parity gate (EP corr ≥ 0.98, WP Brier ≤ 0.20) passes; sdv-py NFL EPA/WPA match nflverse
  within tolerance on sample games.
