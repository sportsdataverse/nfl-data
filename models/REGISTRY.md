# Model registry

One row per published or bundled model artifact this repo owns. The registry
lives here — not in CLAUDE.md (a table a test parses is repository data, not
agent instructions) and not in `docs/models/` (report generators regenerate
that directory). `tests/test_model_registry.py` fails the build when an
artifact in the publish maps has no row here.

Gates cite `docs/models/parity.md` (the nflfastR-parity oracle) and
`python/model_training/decision_models/validate.py` (the correlation
thresholds). Gates are never lowered; a scheduled run re-measures them
unchanged. "Retrain" = the annual `nfl_model_pipeline.yml` suite (cron
`0 6 1 3 *`, March 1 + dispatch) unless a row says otherwise.

## Play-level models → `nfl_model_artifacts`

Trained by `python -m model_training.play_level train` on the nflverse-parity
`model_pbp` corpus (1999–2025, era-aware). Artifacts last refreshed 2026-06
(the era-retrain ship, nfl-data#14).

| model | artifact(s) | release tag | training data | fitting script | gates at publish | last retrain | cadence |
|---|---|---|---|---|---|---|---|
| Expected Points | `ep_model.ubj` + `.json` | `nfl_model_artifacts` | model_pbp 1999–2025, era-aware | `model_training/play_level` | nflfastR parity r **0.996** (floor r 0.98) | 2026-06 | annual (Mar 1) |
| Win Probability (naive) | `wp_naive.ubj` + `.json` | `nfl_model_artifacts` | model_pbp 1999–2025, era-aware | `model_training/play_level` | nflfastR parity r **0.997**; WP Brier cap per parity.md | 2026-06 | annual (Mar 1) |
| Win Probability (spread) | `wp_spread.ubj` + `.json` | `nfl_model_artifacts` | model_pbp 1999–2025, era-aware | `model_training/play_level` | nflfastR parity r **0.998** (`vegas_wp`) | 2026-06 | annual (Mar 1) |
| Completion Probability | `cp_model.ubj` + `.json` | `nfl_model_artifacts` | model_pbp 1999–2025, era-aware | `model_training/play_level` | CPOE scale-correct vs nflfastR (percentage-point scale) | 2026-06 | annual (Mar 1) |
| Expected YAC | `xyac_model.ubj` + `.json` | `nfl_model_artifacts` | model_pbp 1999–2025, era-aware | `model_training/play_level` | 76-class faithful add_xyac reproduction (sdv-py #114) | 2026-06 | annual (Mar 1) |

## Decision models → `nfl_4th_down_models` / `nfl_model_artifacts`

Trained by `python -m model_training.decision_models train-all`; correlation
gates in `decision_models/validate.py`, measured values in parity.md.

| model | artifact(s) | release tag | training data | fitting script | gates at publish | last retrain | cadence |
|---|---|---|---|---|---|---|---|
| Expected Pass | `xpass_model.ubj` | `nfl_model_artifacts` | model_pbp 1999–2025, era-aware | `model_training/decision_models` | P(pass) corr **0.9895** (validate threshold 0.99, informational — era-aware divergence) | 2026-06 | annual (Mar 1) |
| Fourth-Down Yards | `fd_model.ubj` | `nfl_4th_down_models` | model_pbp 1999–2025, era-aware | `model_training/decision_models` | mean-gain corr **0.9856** (informational, era-aware) | 2026-06 | annual (Mar 1) |
| nfl4th Decision WP | `wp_model.ubj` | `nfl_4th_down_models` | nfl4th cal_data (reproduction, unchanged) | `model_training/decision_models` | P(win) corr **0.9947** | 2026-06 | annual (Mar 1) |

## Bundled-in-sdv-py artifacts (no release tag)

Copied into sdv-py's `sportsdataverse/nfl/models/` package data by
`nfl_model_publish decision_models-artifacts` (see
`DECISION_MODELS_BUNDLE_ARTIFACTS`); never uploaded to a release.

| model | artifact(s) | release tag | training data | fitting script | gates at publish | last retrain | cadence |
|---|---|---|---|---|---|---|---|
| Field Goal | `fg_model.ubj` | — (sdv-py bundle) | model_pbp 1999–2025, era-aware | `model_training/decision_models` | attempted-cells corr **0.971** (freq-wt 0.986) vs GAM grid | 2026-06 | annual (Mar 1) |
| Two-Point | `two_pt_model.ubj` | — (sdv-py bundle) | model_pbp 2010–2025 | `model_training/decision_models` | P(success) corr **0.806** (vintage drift documented in two_pt.md) | 2026-06 | annual (Mar 1) |
| Punt Outcome Distribution | `punt_data.parquet` | — (sdv-py bundle) | model_pbp punt outcomes | `model_training/decision_models` | distributional (see punt.md) | 2026-06 | annual (Mar 1) |

## Decision surfaces published as data

| model | artifact(s) | release tag | training data | fitting script | gates at publish | last retrain | cadence |
|---|---|---|---|---|---|---|---|
| NFL ratings (weekly vintages) | `nfl_ratings_weekly_{season}.parquet`, 1999–2025 | `nfl_ratings_weekly` | model_pbp season-to-date, `as_of_week` EXCLUSIVE (leak-safe, nfl-data#24) | `python/nfl_ratings_weekly` | vintage discipline: as-of split enforced in the builder | 2026-08-07 (backfill publish) | weekly in-season (Tue 10:00 UTC, Sep–Feb) |

## Documented but not trained here

| model | status |
|---|---|
| QBR (`qbr_model.ubj`) | card at `docs/models/qbr.md`; artifact ships in sdv-py's bundle. Fitting script: TODO (not in `model_training/`); last retrain: TODO. Add the row's facts when the trainer is located or ported into this repo. |
| dakota | derived metric (EPA + CPOE composite) — no artifact to register; see `docs/models/dakota.md`. |

## Operability (Track C steps 2–6)

- `models/manifest.yaml` — single home for the model/stage list (guarded by `tests/test_model_manifest.py`).
- One model = one numbered pipeline: `python/nfl_model_build/nfl_model_NN_<model>.py` (thin entries over `model_training`); run subsets with `scripts/nfl_models.sh`; CI = one job per stage (`nfl_model_pipeline.yml` matrix, `stages` dispatch input).
- `features/<model>_v1.yaml` — feature-set registry, ordered-equality-gated to the code constants (`tests/test_feature_sets.py`). Inverting the dependency (code reads the YAML) is a recorded follow-up.
- Fingerprints: each stage skips when `hash(code subtree, config)` is unchanged (`--force` to retrain); every trained model appends a `models/ledger.jsonl` line (`in_published_data` flips only when a reprocess ships the scores).
- Promoted artifacts are NOT committed here — release tags + the sdv-py bundle are the durable stores (gitignored deliberately).
