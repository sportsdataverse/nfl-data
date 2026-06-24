# nfl4th Decision WP (`wp_model`)

## Overview

The nfl4th decision WP is a **home-perspective** win-probability model used to
value 4th-down options: each candidate outcome ([go](fourth_down.md) /
[FG](fg.md) / [punt](punt.md) / [2-pt](two_pt.md)) is mapped to a resulting game
state and scored by this model, and the highest-WP action is recommended. It is a
Python retrain of the WP model nfl4th applies for 4th-down decisions, validated against
the converted nflverse artifact.

::: {.callout-important}
## This is **not** the core WP suite
The [core WP models](wp_spread.md) are **possession-team** WP (the nflfastR
`wp` / `vegas_wp` surface). This is nfl4th's **home-team** 11-feature WP, whose
contract comes from nfl4th's decision-WP model. The home-perspective transforms
are ported verbatim. The two
serve different layers — don't cross-wire them.
:::

## Model features

**11 features**, home perspective. The label is whether the home team won.

| Feature | What it encodes |
|---|---|
| `home_receive_2h_ko` | Home team receives the second-half kickoff. |
| `spread_time` | `home_spread · exp(−4 · elapsed_share)` — time-decayed line. |
| `home_posteam` | Home team is on offense. |
| `half_seconds_remaining` / `game_seconds_remaining` | Clock. |
| `Diff_Time_Ratio` | Score differential scaled by time. |
| `home_score_differential` | Home score margin. |
| `home_ep` | Home-perspective expected points (links to the EP model). |
| `ydstogo` | Yards to go. |
| `home_yardline_100` | Home-perspective field position. |
| `home_timeouts_remaining` | Home timeouts left. |

## The model

**Algorithm.** XGBoost, `objective=binary:logistic`, `eta=0.025`, `max_depth=5`,
`gamma=1`, `subsample/colsample=0.8`, **500 rounds** (a 500–2000 sweep all clears
0.99; corr-vs-oracle peaks at 500). Trained from nfl4th's win-probability
calibration frame (the frozen tuning frame nfl4th + nflfastR read).

**Evaluation.** Parity P(win) corr **0.9947** (gate ≥0.99) — see [Parity](parity.md).

## Limitations

It is the **decision-layer** WP, tuned to reproduce nfl4th's recommendations, not
a general-purpose live WP feed — for that use the [core WP](wp_spread.md). It
inherits the home-perspective framing and the EP model's drift through `home_ep`.

## Provenance

| field | value |
|---|---|
| `model_type` | wp (nfl4th home-perspective) |
| `objective` | binary:logistic |
| `features` | 11 (home perspective) |
| `label` | home team won |
| `hyperparameters` | eta=0.025, max_depth=5, nrounds=500 |
| `lineage` | nfl4th decision-WP model |
| `parity` | P(win) corr 0.9947 (gate ≥0.99) |
