# Expected Points (EP)

## Overview

The Expected Points (EP) model estimates the expected next-score value for the
team in possession at the **start of a play**, given game state. It is the
foundation of the NFL analytics stack: EP differences between consecutive plays
define **Expected Points Added (EPA)**. Every play-by-play row carries an `ep`
column plus the seven next-score class probabilities. The model is a faithful
re-implementation of the nflfastR EP model (nflverse `fastrmodels`, Ben Baldwin).

## Model features

**18 features**, all known at the **start of the play** — no look-ahead. Each
row is one scrimmage play; the label is the *next scoring event* in the same
half (`next_score_class`).

| Feature | Type | What it encodes |
|---|---|---|
| `half_seconds_remaining` | numeric | Seconds left in the half — fewer expected possessions to score late. |
| `yardline_100` | numeric | Distance (1–99) to the opponent's end zone — the strongest field-position signal. |
| `ydstogo` | numeric | Yards to go for a first down. |
| `down1` … `down4` | one-hot | Current down (4 columns). |
| `home` | binary | Possession team is home. |
| `dome` / `retractable` / `outdoors` | binary | Stadium-type one-hots (roof/exposure) — NFL EP carries a weather/venue proxy CFB does not. |
| `era0` … `era4` | one-hot | Rule era (cuts **2001 / 2005 / 2013 / 2017** → ≤2001, 2002–05, 2006–13, 2014–17, ≥2018) — captures scoring-environment drift across 26 seasons. |
| `posteam_timeouts_remaining` | numeric | Possession-team timeouts left. |
| `defteam_timeouts_remaining` | numeric | Defense timeouts left. |

## The model

**Algorithm.** XGBoost gradient-boosted trees, `objective=multi:softprob` over
`num_class=7`, `eval_metric=mlogloss`, `eta=0.025`, `max_depth=5` — the
`fastrmodels` EP recipe. The 7 class probabilities are dotted with the
nflfastR point map to produce a scalar EP:

`{Touchdown:+7, Opp_Touchdown:−7, Field_Goal:+3, Opp_Field_Goal:−3, Safety:+2, Opp_Safety:−2, No_Score:0}`

(class order `0=TD, 1=Opp_TD, 2=FG, 3=Opp_FG, 4=Safety, 5=Opp_Safety, 6=No_Score`).
Retrained on the **full 1999–2025 history (1,195,636 plays)** reshaped from
`nfl-raw` to nflfastR parity.

**Evaluation.** Two lenses — see [Parity](parity.md) for the nflfastR-parity gate
and the LOSO calibration below.

## Calibration

A 7-class softprob model is checked **per next-score class** — each class
probability binned against whether that class was the realized next score (the
nflfastR / cfbscrapR signature). This is a **probability-scale** reliability
check, directly comparable to the WP and CP numbers. On the **1999–2025**
leave-one-season-out pool (1,195,636 plays) the **per-class weighted calibration
error is 0.0058** — on par with WP (0.0026) and better than CP (0.0136). The
high-variance modal class (`No_Score`, 0.012) carries most of the error; the rare
scoring classes (safeties, 0.003) are tight.

![](figures/ep_class_calibration.png)

::: {.callout-note}
## Why not a single points-scale number
Binning the scalar `ep` against realized next-score *value* reads ≈0.07 **points**,
but that is dominated by the absolute level of the next-score label — nflfastR's
own `ep` sits the same ~0.1 points above the realized-next-score mean — so it is
**not** comparable to the probability-scale figures above, nor to WP/CP. The
per-class reliability and the parity (`ep` r 0.996) are the honest, comparable
signals; the model is not miscalibrated.
:::

![](figures/ep_by_yardline.png)

The EP-by-yardline curve is the nflfastR signature: expected points rises
smoothly from own-goal-line to a sharp red-zone climb, with the start-of-drive
discontinuity at the touchback line.

## Feature importance

By XGBoost gain, `yardline_100` dominates (field position is the backbone of EP),
followed by `half_seconds_remaining` and the down one-hots; the era and stadium
one-hots apply level shifts (scoring environment, dome scoring) rather than
driving the surface. This ordering matches the nflfastR EP post.

## Limitations

EP is a **start-of-play** quantity; it does not know the result of the current
play (that is what EPA captures). Top-1 class accuracy is inherently capped by
irreducible next-score noise, not miscalibration — the model is well-calibrated
in aggregate even where individual outcomes are unpredictable. The 7-class point
map is fixed, and the model is blind to personnel and in-play participants by
design.

## Provenance

| field | value |
|---|---|
| `model_type` | ep |
| `objective` | multi:softprob (num_class=7) |
| `features` | 18 (see above) |
| `label` | next_score_class |
| `training_seasons` | 1999–2025 |
| `n_training_rows` | 1,195,636 |
| `hyperparameters` | eta=0.025, max_depth=5 |
| `lineage` | nflfastR EP model · nflverse `fastrmodels` (Ben Baldwin) |
| `parity` | `ep` r 0.996 · `epa` r 0.994 |
