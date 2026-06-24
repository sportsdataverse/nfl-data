# Field Goal (`fg_model`)

## Overview

The field-goal model estimates the probability a placekick is **made**, given
the kick distance and roof/era context. It powers the field-goal branch of the
[nfl4th 4th-down decision](fourth_down.md): the EV of attempting a field goal is
this make probability times three points. It is a Python **XGBoost** retrain of
nfl4th's FG model — which was originally an **mgcv GAM spline** — validated
against the converted GAM grid.

## Model features

**7 features** (`yardline_100`, `fg_roof`, era0..era4); one row per FG attempt
(`play_type_nfl=='FIELD_GOAL'`, 1999–2025). The era one-hot replaces the old
binary `fg_era` so the make-prob curve is era-aware across all kicking eras.
The binary label is `sp` (field goal made).

| Feature | Type | What it encodes |
|---|---|---|
| `yardline_100` | numeric | Snap field position; kick distance is `yardline_100 + 17`. The dominant signal (**monotone ↓**). |
| `fg_roof` | binary | Outdoors (`roof=='outdoors'`) vs indoor/retractable. |
| `fg_era` | binary | Modern-kicking era (`season >= 2020`). |

## The model

**Algorithm.** XGBoost, `objective=binary:logistic`, shallow trees with a high
`min_child_weight` (the make curve is smooth), **monotone constraint `−1` on
`yardline_100`** (make probability must fall with distance). Replaces the
original mgcv GAM spline.

**Evaluation.** Because the booster step-approximates a spline, parity is scoped
to the **operating domain** (yardline×roof×era cells with ≥1 real attempt):
**corr 0.9802** there (gate ≥0.98), **freq-weighted corr 0.9880**. Full-grid corr
is lower by construction (0.9690) — the booster cannot reproduce the spline's
extrapolation into never-attempted cells; **max abs FG% diff 0.34**. See
[Parity](parity.md).

## Limitations

Distance is everything plus a coarse roof/era shift — **no kicker identity, wind,
or weather**. The step-function booster does not extrapolate the smooth GAM tail
past the attempted domain, so very long / never-attempted cells should be read
with caution (this is the freq-weighted vs full-grid corr gap).

## Provenance

| field | value |
|---|---|
| `model_type` | fg |
| `objective` | binary:logistic (monotone yardline ↓) |
| `features` | yardline_100, fg_roof, fg_era |
| `label` | sp (FG made) |
| `training_seasons` | 1999–2025 (23,919 attempts) |
| `lineage` | nfl4th field-goal model (was mgcv GAM) |
| `parity` | attempted-cells corr 0.971 · freq-weighted 0.986 (informational, era-aware full-history) |
| `distribution` | bundled in sportsdataverse |
