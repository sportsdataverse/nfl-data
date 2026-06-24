# Win Probability — naive (`wp`)

## Overview

The naive Win Probability model answers *given only the game state, with no
betting-market information, how likely is the possession team to win?* It is the
spread model's sibling — identical except it **drops `spread_time`** — and is the
nflfastR `wp` surface: the right choice when a pregame spread is unavailable or
when you explicitly want a market-free WP.

## Model features

**11 features** — exactly the [spread model](wp_spread.md)'s set **minus
`spread_time`**: `receive_2h_ko`, `home`, `half_seconds_remaining`,
`game_seconds_remaining`, `Diff_Time_Ratio`, `score_differential`, `down`,
`ydstogo`, `yardline_100`, `posteam_timeouts_remaining`,
`defteam_timeouts_remaining`. Dropping the single market feature is the *only*
difference between the two WP heads, which is why they can be compared
head-to-head.

## The model

**Algorithm.** XGBoost, `objective=binary:logistic`, `eta=0.2`, `max_depth=4` —
the `fastrmodels` naive-WP recipe. Trained on the **full 1999–2025 history
(1,268,220 plays)**, the same frame as the spread model. The higher learning
rate / shallower trees reflect that, without the spread, there is less structured
signal to fit.

**Evaluation.** nflfastR parity: `wp` correlates **r 0.997** against nflverse
(see [Parity](parity.md)). LOSO calibration uses the same protocol as the spread
model.

## Calibration Results

Leave-one-season-out, pooled out-of-fold, the same binned-WP-vs-win-rate recipe
as the spread model. The naive and spread surfaces **diverge most early** (the
pregame spread carries the most information when game state carries the least)
and **converge late** as `spread_time` decays and both read the same near-final
state. The naive calibration figure is generated alongside the spread figure by
the NFL model-report tool.

## Feature importance

Without the market prior, `score_differential`, `yardline_100` and the clock
terms carry the model from the opening kickoff — precisely why the naive WP is
least confident (closest to 0.5) early and diverges most from the spread WP in
the first quarter.

## Limitations

Because it ignores the market, the naive model is *less sharp* early in games:
strictly less information than the spread model, so its log-loss and Brier are
worse. Use it only when you want a spread-free WP or lack a spread; for forecast
accuracy when a spread exists, prefer the [spread model](wp_spread.md). WPA
carries the same per-play noise caveat.

## Provenance

| field | value |
|---|---|
| `model_type` | wp_naive |
| `objective` | binary:logistic |
| `features` | 11 (spread set minus `spread_time`) |
| `label` | label (possession team wins) |
| `training_seasons` | 1999–2025 |
| `n_training_rows` | 1,268,220 |
| `hyperparameters` | eta=0.2, max_depth=4 |
| `lineage` | nflfastR naive-WP model · nflverse `fastrmodels` (Ben Baldwin) |
| `parity` | `wp` r 0.997 |
