# Expected Pass (`xpass_model`)

## Overview

The expected-pass model estimates the probability that a scrimmage play is a
**dropback (pass)** given pre-snap game state — a measure of how *predictable* an
offense's tendency is. It is the nflfastR xpass surface, where
**`pass_oe = 100 · (pass − xpass)`** is the pass-rate over expected: positive when
an offense passes more than situation-average. A full-history (1999–2025) retrain
following the nflverse dropback recipe.

## Model features

**19 features**, pre-snap; one row per scrimmage play (1999–2025). The binary
label is `pass` (dropback). Note it consumes the [WP surfaces](wp_spread.md)
(`wp`, `vegas_wp`) as features.

| Feature | What it encodes |
|---|---|
| `down`, `ydstogo`, `yardline_100`, `qtr` | Down/distance/field position/quarter — the tendency backbone. |
| `wp`, `vegas_wp` | In-game win probability (game-script urgency). |
| `score_differential`, `half_seconds_remaining` | Score/clock context. |
| `home` | Possession team is home. |
| `posteam_timeouts_remaining`, `defteam_timeouts_remaining` | Timeouts. |
| `era0`..`era4` | Rule-era one-hot (cuts 2001/2005/2013/2017) — era-aware across all of 1999–2025. |
| `outdoors`, `retractable`, `dome` | Stadium-type one-hots. |

## The model

**Algorithm.** XGBoost, `objective=binary:logistic`, **1,121 rounds**,
`eta=0.015`, `gamma=2`, `max_depth=7`, `min_child_weight=0.9`,
`subsample/colsample=0.8`, `base_score=mean(label)`, `seed=2013` — verbatim from
the nflverse dropback-model recipe. The predicted
probability is `xpass`; **`pass_oe = 100 · (pass − xpass)`** is the actionable
residual.

**Evaluation.** Full-history retrain on 892,122 plays. Parity-vs-nflverse is
**informational** (the nflverse oracle trains on 2006+): P(pass) corr **0.989** —
see [Parity](parity.md).

## Limitations

xpass is **pre-snap**: no personnel, formation, motion, or no-huddle signal, so it
captures the situation-explainable part of tendency only. Two offenses in
identical game state get the same xpass — the *team* tendency lives in `pass_oe`,
not in xpass itself.

## Provenance

| field | value |
|---|---|
| `model_type` | xpass |
| `objective` | binary:logistic |
| `features` | 19 (era0..4 + `wp` / `vegas_wp`) |
| `label` | pass (dropback) |
| `training_seasons` | 1999–2025 (892,122 plays) |
| `hyperparameters` | eta=0.015, max_depth=7, nrounds=1121 |
| `lineage` | nflverse dropback model |
| `parity` | P(pass) corr 0.989 (informational; full-history vs nflverse 2006+) |
| `distribution` | bundled in sportsdataverse |
