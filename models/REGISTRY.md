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
| Win Probability (naive) | `wp_naive.ubj` + `.json` | `nfl_model_artifacts` | model_pbp 1999–2025, era-aware | `model_training/play_level` | nflfastR parity r **0.997**; WP Brier cap per parity.md; **not applied in overtime** — nflfastR scores `qtr > 4` with a closed form off the EP class probabilities and sets `vegas_wp = wp` (`add_wp_variables` L820-899), ported as `_apply_ot_wp_overlay` (sdv-py PR #435). Overtime `wp` MAE vs nflverse **0.014-0.052** over 10 seasons / 3,171 overtime plays (was 0.097-0.173 unported); gated in sdv-py on its committed five-era overtime fixture (`tests/fixtures/nfl_ep_wp/`, five whole overtime games) at MAE <= **0.035** / \|bias\| <= **0.030** / r >= **0.98**, set from the observed 0.0209 / -0.0149 / 0.9945 | 2026-06 | annual (Mar 1) |
| Win Probability (spread) | `wp_spread.ubj` + `.json` | `nfl_model_artifacts` | model_pbp 1999–2025, era-aware | `model_training/play_level` | nflfastR parity r **0.998** (`vegas_wp`); fitted `spread_time` decay exponent −4.0 recorded in the card (`derived_feature_constants`) + `features/wp_spread_v1.yaml`, gated trainer == registry == applier (`tests/test_feature_sets.py`); **not applied in overtime** — nflfastR scores `qtr > 4` with a closed form off the EP class probabilities and sets `vegas_wp = wp` (`add_wp_variables` L820-899), ported as `_apply_ot_wp_overlay` (sdv-py PR #435). Overtime `wp` MAE vs nflverse **0.014-0.052** over 10 seasons / 3,171 overtime plays (was 0.097-0.173 unported); gated in sdv-py on its committed five-era overtime fixture (`tests/fixtures/nfl_ep_wp/`, five whole overtime games) at MAE <= **0.035** / \|bias\| <= **0.030** / r >= **0.98**, set from the observed 0.0209 / -0.0149 / 0.9945 | 2026-06 | annual (Mar 1) |
| Completion Probability | `cp_model.ubj` + `.json` | `nfl_model_artifacts` | model_pbp 1999–2025, era-aware | `model_training/play_level` | CPOE scale-correct vs nflfastR (percentage-point scale) | 2026-06 | annual (Mar 1) |
| Expected YAC | `xyac_model.ubj` + `.json` | `nfl_model_artifacts` | model_pbp 1999–2025, era-aware | `model_training/play_level` | 76-class faithful add_xyac reproduction (sdv-py #114) | 2026-06 | annual (Mar 1) |

## Known limitations

- **Win probability in overtime is not a model output.** Following nflfastR,
  `qtr > 4` uses a closed form off the EP class probabilities
  (`Sudden_Death_WP = fg_prob + td_prob + safety_prob`, or
  `td_prob + fg_prob * Win_Back` on the first overtime drive from 2012), with
  `vegas_wp` set equal to `wp` — the spread model is not consulted. It is
  therefore **spread-blind in overtime by construction**, and any downstream
  consumer reading `vegas_wp` in overtime is reading the naive number.
  Fitting an overtime-specific WP model is **not supportable**: a WP model
  needs one label per game, and the whole both-possess era has 66 overtime
  games (2025 alone: 16) across 1,304 plays — too thin to gate. Measured
  1999-2025: 444 overtime games / 8,715 plays over five incompatible rules
  eras (pre-2012 sudden death, 2012 modified, 2017 10-minute, 2022 playoff
  both-possess, 2025 regular-season both-possess).
- **Two nflfastR WP overlays remain unported** on the nflverse path: the PAT /
  two-point fix (`add_wp_variables` L932-1041) and the regulation kickoff
  touchback re-score (L1043-1069). The residual overtime error localises to the
  rows the first covers — 2025 overtime `wp` MAE 0.024 on `down`-non-null rows
  against 0.083 on `down`-null rows.

## Decision models → `nfl_4th_down_models` / `nfl_model_artifacts`

Trained by `python -m model_training.decision_models train-all`; correlation
gates in `decision_models/validate.py`, measured values in parity.md.

| model | artifact(s) | release tag | training data | fitting script | gates at publish | last retrain | cadence |
|---|---|---|---|---|---|---|---|
| Expected Pass | `xpass_model.ubj` | `nfl_model_artifacts` | model_pbp 1999–2025, era-aware | `model_training/decision_models` | P(pass) corr **0.9895** (validate threshold 0.99, informational — era-aware divergence) | 2026-06 | annual (Mar 1) |
| Fourth-Down Yards | `fd_model.ubj` | `nfl_4th_down_models` | model_pbp 1999–2025, era-aware | `model_training/decision_models` | mean-gain corr **0.9856** (informational, era-aware) | 2026-06 | annual (Mar 1) |
| nfl4th Decision WP | `wp_model.ubj` | `nfl_4th_down_models` | nfl4th `cal_data.rds` 2001–2020 (reproduction, unchanged; window lags the main models) | `model_training/decision_models` | P(win) corr **0.9947**; a missing `cal_data.rds` FAILS the stage / `train-all` (rc 1) — `--allow-skip` / `--allow-missing-cal-data` records `status: SKIPPED` + reason in `models/ledger.jsonl` and report.md instead | 2026-06 | annual (Mar 1) |

## Bundled-in-sdv-py artifacts (no release tag)

Copied into sdv-py's `sportsdataverse/nfl/models/` package data by
`nfl_model_publish decision_models-artifacts` (see
`DECISION_MODELS_BUNDLE_ARTIFACTS`); never uploaded to a release.

| model | artifact(s) | release tag | training data | fitting script | gates at publish | last retrain | cadence |
|---|---|---|---|---|---|---|---|
| Field Goal | `fg_model.ubj` | — (sdv-py bundle) | model_pbp 1999–2025, era-aware | `model_training/decision_models` | attempted-cells corr **0.971** (freq-wt 0.986) vs GAM grid | 2026-06 | annual (Mar 1) |
| Two-Point | `two_pt_model.ubj` | — (sdv-py bundle) | model_pbp 2010–2025 | `model_training/decision_models` | **SOFT gate** — P(success) corr **0.806** vs the 0.99 floor (not lowered), recorded `SOFT FAIL` and tolerated by design (vintage drift documented in two_pt.md); labelled `SOFT PASS` / `SOFT FAIL` in CI, the ledger and report.md — never a hard-gate `PASS` | 2026-06 | annual (Mar 1) |
| Punt Outcome Distribution | `punt_data.parquet` | — (sdv-py bundle) | model_pbp punt outcomes | `model_training/decision_models` | **two** gates: oracle freq-wt TV **0.0652** (≤0.10) + reality freq-wt KS vs the last 3 seasons **0.1466** (≤0.22) and mean-landing gap **+2.48 yd** (≤3.5) — `validate_punt_holdout` | 2026-06 | annual (Mar 1) |

## Decision surfaces published as data

| model | artifact(s) | release tag | training data | fitting script | gates at publish | last retrain | cadence |
|---|---|---|---|---|---|---|---|
| NFL ratings (weekly vintages) | `nfl_ratings_weekly_{season}.parquet`, 1999–2025 | `nfl_ratings_weekly` | model_pbp season-to-date, `as_of_week` EXCLUSIVE (leak-safe, nfl-data#24) | `python/nfl_ratings_weekly` | vintage discipline: as-of split enforced in the builder | 2026-08-07 (backfill publish) | weekly in-season (Tue 10:00 UTC, Sep–Feb) |

## Documented but not trained here

| model | status |
|---|---|
| QBR (`qbr_model.ubj`) | card at `docs/models/qbr.md`; artifact ships in sdv-py's bundle. Fitting script: TODO (not in `model_training/`); last retrain: TODO. Add the row's facts when the trainer is located or ported into this repo. |
| dakota | derived metric (EPA + CPOE composite) — no artifact to register; see `docs/models/dakota.md`. **Gated** by `play_level.validate.validate_dakota` (opt-in: `python -m model_training.play_level validate … --dakota-seasons 2006 2025`). Measured on model_pbp 2006–2025, 488 passer-season pairs (2026-09-01): CPOE YoY r **0.7031** (floor 0.60) vs EPA/play's 0.4508 — the blend's premise; dakota YoY r **0.6820** (floor 0.58) at a **+0.2313** margin over EPA (floor 0.15); agreement with the published nflfastR GAM r **0.8542** (floor 0.80). **Recalibration cadence: re-run this gate whenever `ep` or `cp` retrains** — dakota consumes both and its coefficients are frozen constants in sdv-py that no retrain touches, so a drifting input silently changes the metric. Reported, not gated: the linear blend does **not** out-forecast raw EPA/play for next-season EPA/play (0.3007 vs 0.4508). |

## Operability (Track C steps 2–6)

- `models/manifest.yaml` — single home for the model/stage list (guarded by `tests/test_model_manifest.py`).
- One model = one numbered pipeline: `python/nfl_model_NN_<model>.py` (thin entries over `model_training`); run subsets with `scripts/nfl_models.sh`; CI = one job per stage (`nfl_model_pipeline.yml` matrix, `stages` dispatch input).
- `features/<model>_v1.yaml` — feature-set registry, ordered-equality-gated to the code constants (`tests/test_feature_sets.py`). Inverting the dependency (code reads the YAML) is a recorded follow-up.
- Fingerprints: each stage skips when `hash(code subtree, config)` is unchanged (`--force` to retrain); every trained model appends a `models/ledger.jsonl` line (`in_published_data` flips only when a reprocess ships the scores).
- Promoted artifacts are NOT committed here — release tags + the sdv-py bundle are the durable stores (gitignored deliberately).
