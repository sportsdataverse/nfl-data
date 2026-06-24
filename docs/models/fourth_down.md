# Fourth-Down Yards (`fd_model`)

## Overview

The fourth-down yards model predicts the **distribution of yards gained** on a
go-for-it (or third-down) attempt — the core of the **nfl4th** decision surface.
From the 76-class gain distribution we derive P(first down) for any
distance-to-go, then combine it with the EP/WP surfaces to compute the
**go / punt / field-goal / two-point** expected-value comparison. It is a
faithful Python retrain of nfl4th's go-for-it model, validated against the
converted nflverse artifact.

## Model features

**14 features**; one row per 3rd/4th-down scrimmage play (1999–2025, `qb_kneel==0`,
`week<=17`). The label is `yards_gained` clamped to **[−10, 65]** and shifted into
**76 ordinal classes** (`label = yards_gained + 10`).

| Feature | Type | What it encodes |
|---|---|---|
| `down` | numeric | Current down (3 or 4). |
| `ydstogo` | numeric | Yards to go — the conversion threshold. |
| `yardline_100` | numeric | Field position (compresses the gain distribution near the goal line). |
| `era0`..`era4` | one-hot | Rule-era one-hot (cuts 2001/2005/2013/2017) — era-aware across 1999–2025. |
| `outdoors` / `retractable` / `dome` | binary | Stadium-type one-hots. |
| `posteam_spread` | numeric | Possession-team spread (game-script context). |
| `total_line` | numeric | Game total (pace / offensive-environment proxy). |
| `posteam_total` | numeric | Possession-team implied total. |

## The model

**Algorithm.** XGBoost, `objective=multi:softprob` over **76 classes**, **1,124
rounds**, `eta=0.01`, `max_depth=2`, `gamma=2`, `subsample=0.8`,
`colsample_bytree=0.8`, `min_child_weight=0.8` — verbatim from the nfl4th R recipe.
P(first down) for any distance-to-go is recovered by summing class probabilities
for gains ≥ the distance.

**Evaluation.** Parity against the converted nflverse artifact: **mean-gain
correlation 0.9974** (gate ≥0.99) — see [Parity](parity.md).

## Decision surface

`fd_model` is one input to nfl4th's 4th-down EV comparison; the others are
[`fg_model`](fg.md), [`two_pt_model`](two_pt.md), the [punt distribution](punt.md),
and the [nfl4th home-WP](nfl4th_wp.md). Each option's EV is computed by mapping its
outcome distribution through the WP surface and picking the highest-WP action.

## Limitations

The label is recorded `yards_gained`, which can disagree with the official result
on penalty/lateral plays — label noise at the tails. The gain window is clipped
to [−10, 65]. It predicts a *yardage distribution*, not the binary decision; the
decision EV is computed downstream. Trained on 2014–2019, so era coverage is the
modern game only.

## Provenance

| field | value |
|---|---|
| `model_type` | fd (fourth-down yards) |
| `objective` | multi:softprob (num_class=76) |
| `features` | 14 (era0..4 + see above) |
| `label` | yards_gained + 10 (clamped −10..65) |
| `training_seasons` | 1999–2025 (182,138 plays) |
| `hyperparameters` | eta=0.01, max_depth=2, nrounds=1124 |
| `lineage` | nfl4th go-for-it model |
| `parity` | mean-gain corr 0.986 (informational; full-history vs nfl4th 2014–19) |
| `distribution` | download-on-demand (large 76-class model) |
