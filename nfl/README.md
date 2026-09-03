# `nfl/` — the committed data tree

Built datasets, committed to git. This is the first mirror of the publish
contract; the second is the GitHub release on `sportsdataverse-data`. Until
2026-09-03 this repo had only the second, and every built artifact lived in the
gitignored `out/` staging directory — which is how the vintage divergence below
went unnoticed.

`out/` remains staging: a build writes there, and only reviewed output is
promoted here. Nothing downstream should read `out/`.

## What is here

| path | contents | source |
|---|---|---|
| `model_pbp/model_pbp_{season}.parquet` | enriched play-by-play — the `nfl_model_pbp` dataset | built from `nfl-raw` by `python/nfl_data_02_model_pbp.py build --enrich` |
| `ratings_weekly/nfl_ratings_weekly_{season}.parquet` | per-week as-of team ratings, 1999-2025 | `python/nfl_data_05_ratings_weekly.py` |

`ratings_weekly` is complete (27 seasons, 1999-2025, 12 columns, schema stable
across the span). `model_pbp` carries 2023 and 2024 only — see below.

## Vintage: three column widths for the same rows

Measured 2026-09-03 on season 2024, which is **47,366 rows in all three**:

| source | columns |
|---|---:|
| `out/model_pbp_2024.parquet` (stale build output, dated 2026-06-18) | 120 |
| published `nfl_model_pbp` release asset | 257 |
| **this tree — built from `nfl-raw` with current code** | **326** |

The build committed here is a strict superset of the published asset
(`only_in_published = 0`); it adds 69 columns the release does not carry
(`air_wpa`, `comp_air_epa`, `comp_yac_wpa`, `drive_end_transition`,
`drive_first_downs`, …). Nothing was lost between vintages — **the release is
simply an older run than the code that produces it.**

Consequences a reader should know before using either:

- The two agree on the 257 columns they share, so most code moves between them
  unchanged. Only code touching one of the 69 tree-only columns breaks — and
  since `sportsdataverse.nfl.load_nfl_model_pbp` reads the release, that is the
  shape of the failure: a `ColumnNotFoundError` on a column that exists here and
  not there, not a wholesale incompatibility.
- The validation schema snapshot in sportsdataverse-py is pinned at the
  **120-column** vintage — the oldest of the three — which is why its cron was
  reporting 277 `unexpected column` findings
  ([sportsdataverse-py#415](https://github.com/sportsdataverse/sportsdataverse-py/issues/415)).
- Only 2023 and 2024 are committed here because those are the seasons that
  exist as verified rebuilds. **The remaining seasons are deliberately absent
  rather than copied from the release** — committing the 257-column assets
  beside 326-column rebuilds would put two vintages in one directory and make
  the tree lie about its own schema.

Tracking: [nfl-data#34](https://github.com/sportsdataverse/nfl-data/issues/34).
The resolution is a full-range rebuild + republish so release and code agree,
after which this tree extends to every season and the schema snapshot pins to
one number.

## Rebuilding

Both stages are numbered, so the driver is the shortest path -- it resolves the
venv, runs from the repo root, and sets `PYTHONPATH` for you:

```sh
NFL_DATA_ARGS="build --seasons 2024 --raw-dir ../nfl-raw/nfl/raw --out nfl/model_pbp --enrich" \
    scripts/nfl_data.sh 02
NFL_DATA_ARGS="--seasons 1999:2025 --out nfl/ratings_weekly" scripts/nfl_data.sh 05
```

The equivalent module form, run **from the repo root**. `PYTHONPATH=python` is
what makes `-m` resolve, and omitting it is the usual reason these fail:

```sh
PYTHONPATH=python python -m nfl_data_02_model_pbp build --seasons 2024 \
    --raw-dir ../nfl-raw/nfl/raw --out nfl/model_pbp --enrich
PYTHONPATH=python python -m nfl_data_05_ratings_weekly \
    --seasons 1999:2025 --out nfl/ratings_weekly
```

`--seasons` is REQUIRED on stage 05, and both stages default `--out` to `out/`
-- which is how these datasets ended up staged rather than committed.

A season takes a couple of minutes: the enrichment scores EP/WP/CP/xYAC per
play. `--raw-dir` points at the sibling `nfl-raw` checkout; on a runner, fetch
the per-game JSON over `raw.githubusercontent.com` instead of cloning it — that
repo is far too large to check out inside a job.

## Coverage caveat carried from the source

Seasons **2000, 2001 and 2002 are near-empty at the source** and a rebuild will
reproduce that exactly: the NFL Shield feed serves drive-level and scoring data
for those three years but almost no play-level rows (2000 has 955 rows across
258 games against ~44,000 in adjacent seasons). It is an upstream gap, not a
build defect, and it is unrelated to the vintage question above. Use
`load_nfl_pbp(source="nflverse")` for 2000-2002.
