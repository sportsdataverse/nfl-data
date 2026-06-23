# NFL model artifacts — provenance (xpass + nfl4th fourth-down)

Provenance + reproduction for the NFL model artifacts that power
sportsdataverse-py's `xpass` enrichment and its nfl4th fourth-down decision
surface (`sportsdataverse/nfl/nfl_fourth_down.py`). These are **faithful ports
of the published nflverse models** — not retrained here.

## Artifacts

| Artifact | Source object | Algorithm | sdv-py tier | Published to |
|---|---|---|---|---|
| `xpass_model.ubj` | `fastrmodels::xpass_model` (`.rda`, raw xgb booster) | xgboost `binary:logistic`, 17 feat | download-on-demand | `sportsdataverse-data@nfl_model_artifacts` |
| `fd_model.ubj` | nfl4th `model_archive` release | xgboost `multi:softprob`, 76-class, 11 feat | download-on-demand (73 MB) | `sportsdataverse-data@nfl_4th_down_models` |
| `wp_model.ubj` | nfl4th `model_archive` release | xgboost win-prob, 11 feat | download-on-demand (7.6 MB) | `sportsdataverse-data@nfl_4th_down_models` |
| `two_pt_model.ubj` | nfl4th `model_archive` release | xgboost `binary:logistic`, 9 feat | **bundled** (`nfl/models/`) | (in wheel) |
| `fg_model_grid.parquet` | nfl4th `fg_model` (`mgcv::bam` GAM) | GAM → exact prediction grid | **bundled** | (in wheel) |
| `punt_data.parquet` | nfl4th `punt_data.rds` | punt landing-yardline distribution | **bundled** | (in wheel) |

The big xgboost boosters (`fd_model`, `two_pt_model`, `wp_model`) are taken
**directly** from nfl4th's official `model_archive` release `.ubj` assets — a
local re-conversion of the source objects produced byte-identical files, so the
official artifacts are used as-is (cleanest provenance). The GAM (`fg_model`)
cannot be serialized as xgboost, so it is exported as the exact prediction grid
(`yardline_100` 1..99 × `fg_model_roof` ∈ {00,01,10,11} → make prob); Python
does a lookup, reproducing the GAM exactly. `xpass_model` and `punt_data` are
converted from their R objects with `convert.R`.

## Reproduce

Requires R (xgboost, mgcv, arrow) + the nflverse R checkouts (`nfl4th`,
`fastrmodels`) and `gh`.

```sh
# official boosters (no conversion — fetch the published .ubj)
gh release download model_archive --repo nflverse/nfl4th \
  --pattern 'fd_model.ubj' --pattern 'two_pt_model.ubj' --pattern 'wp_model.ubj'

# the two R conversions (xpass .rda -> .ubj; fg GAM -> grid; punt .rds -> parquet)
Rscript convert.R   # edit the path constants at the top first
```

`convert.R` prints each model's class + feature order and writes the artifacts.

## Publish

```sh
gh release upload nfl_model_artifacts  xpass_model.ubj \
  --repo sportsdataverse/sportsdataverse-data --clobber
gh release upload nfl_4th_down_models  fd_model.ubj wp_model.ubj \
  --repo sportsdataverse/sportsdataverse-data --clobber
# two_pt_model.ubj / fg_model_grid.parquet / punt_data.parquet are committed to
# sdv-py under sportsdataverse/nfl/models/ (shipped in the wheel).
```

## Parity (validated in sdv-py)

- **xpass** vs nflverse 2023, fed nflverse's own `wp`/`vegas_wp`: corr **1.000000**,
  MAD 0 (byte-faithful).
- **fourth-down** vs nfl4th's own published per-play output
  (`pre_computed_go_boost`, 2022, 4,239 plays): `go_wp` **0.9998**, `fg_wp`
  **0.9996**, `punt_wp` **0.9997** (`go_boost` 0.984 — a first-difference SNR
  ceiling, not a port error).
