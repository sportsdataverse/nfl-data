# Expected Yards After Catch (xYAC)

## Overview

The xYAC model predicts the **distribution of yards gained after the catch** on a
completed pass, given the throw geometry and game state at the moment of the
catch. It is a faithful re-implementation of the nflfastR `add_xyac` model — a
**76-class multinomial** over post-catch gain — and feeds the expected-YAC
surface (`xyac_epa`, `xyac_mean_yardage`) used to decompose a completion into its
air vs after-catch contributions.

## Model features

**19 features** — the [CP](cpoe.md) feature set plus `distance_to_goal`. The
label is the post-catch yardage bucketed into 76 ordinal classes. Like CP, xYAC
depends on `air_yards` charting (2006+), so only `era2..4` are carried.

| Feature | Type | What it encodes |
|---|---|---|
| `air_yards` | numeric | Air distance to the catch point — sets where YAC starts. |
| `distance_to_goal` | numeric | Yards from the catch point to the end zone — **caps** achievable YAC near the goal line. |
| `distance_to_sticks` | numeric | `air_yards − ydstogo`. |
| `yardline_100` / `ydstogo` | numeric | Field position and yards to go at the snap. |
| `air_is_zero` / `pass_middle` / `qb_hit` | binary | Screen/behind-LOS, over-the-middle, pressure indicators. |
| `down1` … `down4` | one-hot | Current down. |
| `home` | binary | Possession team is home. |
| `dome` / `retractable` / `outdoors` | binary | Stadium-type one-hots. |
| `era2` … `era4` | one-hot | Rule era from 2006. |

## The model

**Algorithm.** XGBoost, `objective=multi:softprob` over **`num_class=76`**,
`eta=0.025`, `max_depth=4` — the nflfastR `add_xyac` recipe. The 76-class
distribution over post-catch gain is the model output; expected YAC and
`xyac_epa` are recovered by combining the class distribution with the EP surface
at each resulting yard line. Trained on **222,020 completed passes (2006–2025)**.

**Evaluation.** Faithful port of nflfastR `add_xyac` — the 76-class multinomial
reproduces the nflverse YAC distribution. xYAC is a **download-on-demand** model
(the ~34 MB artifact is fetched and cached rather than bundled in
`sportsdataverse`).

## Calibration Results

xYAC calibration is the predicted-vs-realized post-catch yardage check (mean
predicted YAC vs mean realized YAC, binned by `air_yards`). It is generated
separately from the EP/WP/CP report (the 76-class multinomial has its own
extraction), from the trained xYAC model against a held-out season.

## Feature importance

`air_yards` and `distance_to_goal` dominate — air depth sets the YAC starting
point and the goal line caps it — with `air_is_zero` / `pass_middle` separating
screens and crossers (high-YAC archetypes) from contested downfield throws.

## Limitations

xYAC is blind to the broken-tackle / open-field athleticism that drives the YAC
tail, so it captures the *situation-and-geometry-explainable* mean, not a specific
receiver's elusiveness. The 76-class window clips extreme returns. Because it
depends on `air_yards`, it is a 2006+ surface. Unlike EP/WP/CP it is **not bundled**
in `sportsdataverse` — it is download-on-demand and cached on first use.

## Provenance

| field | value |
|---|---|
| `model_type` | xyac |
| `objective` | multi:softprob (num_class=76) |
| `features` | 19 (CP set + `distance_to_goal`) |
| `label` | post-catch yardage (76 ordinal classes) |
| `training_seasons` | 2006–2025 |
| `n_training_rows` | 222,020 |
| `hyperparameters` | eta=0.025, max_depth=4 |
| `lineage` | nflfastR `add_xyac` |
| `distribution` | download-on-demand (not bundled in sportsdataverse) |
