# track7 — Python training port for the NFL model suite (xpass + nfl4th 4th-down)

Faithful Python retrains of the NFL models that sdv-py currently uses as
R-converted artifacts. Each trainer is validated against the converted R
artifact (the **parity oracle**). Mirror the structure of
`model_training/track6_nfl_ep_wp/` (constants / features / ingest / trainer /
validate / pipeline). Era cuts: era0 ≤2001, era1 2002-2005, era2 2006-2013,
era3 2014-2017, era4 >2017. Roof → retractable/dome/outdoors via
`make_model_mutations` (already in track6 `features.py` — reuse it).
`posteam_spread = home? spread_line : -spread_line`; `home_total=(spread+total)/2`,
`away_total=(total-spread)/2`, `posteam_total` per posteam.

All XGBoost hyperparameters below are verbatim from the R training scripts —
**re-read the R for exactness**: `nfl4th/data-raw/_go_for_it_and_2pt_models.R`
(fd, two_pt), `nfl4th/data-raw/_punt_and_fg_models.R` (fg, punt),
`nflfastR/data-raw/` + `nflverse-pbp/models/train_dropback_model.R` (xpass),
`nflfastR/data-raw/MODELS.R` + `_tune_spread_wp.R` (wp).

## 1. xpass — binary:logistic
- Data: nflverse pbp, season≥2006; filter `play_type∈{no_play,pass,run}` + posteam/down/timeouts/yardline_100/score_differential not-null.
- Label: `pass` (dropback 0/1).
- Features (17, order): down, ydstogo, yardline_100, qtr, wp, vegas_wp, era2, era3, era4, score_differential, home, half_seconds_remaining, posteam_timeouts_remaining, defteam_timeouts_remaining, outdoors, retractable, dome. (`wp`/`vegas_wp` from nflverse-reference pbp.)
- Params: eta=.015, gamma=2, subsample=.8, colsample_bytree=.8, max_depth=7, min_child_weight=0.9, base_score=mean(label), eval_metric=[error,logloss], nrounds=1121, seed=2013.
- Oracle: `xpass_model.ubj` (predict on a held-out season; target corr ≥0.99).

## 2. fd_model — multi:softprob, num_class=76 (go-for-it gain distribution)
- Data: pbp 2014:2019; filter `down∈{3,4}, qb_kneel==0, (rush==1|pass==1), week<=17, posteam/yardline_100/score_differential not-null, play_type_nfl∈{RUSH,PASS,SACK} | first_down_penalty==1`.
- Label: `yards_gained` (defensive-PF first downs recoded), clamp [-10,65], `label = yards_gained + 10` (class 0..75).
- Features (11, order): down, ydstogo, yardline_100, era3, era4, outdoors, retractable, dome, posteam_spread, total_line, posteam_total.
- Params: num_class=76, eval_metric=mlogloss, eta=.01, gamma=2, subsample=.8, colsample_bytree=.8, max_depth=2, min_child_weight=0.8, nrounds=1124, seed=2013.
- Oracle: `fd_model.ubj` (compare class distributions / mean predicted gain; corr ≥0.99 on mean gain).

## 3. two_pt_model — binary:logistic
- Data: pbp 2010:2019; filter `is.na(down), two_point_conv_result not-null, yardline_100==2, (rush==1|pass==1), week<=17, posteam/yardline_100/score_differential not-null`.
- Label: `two_point_conv_result=='success'` → 1.
- Features (9, order): era2, era3, era4, outdoors, retractable, dome, posteam_spread, total_line, posteam_total.
- Params: eval_metric=logloss, eta=0.0576, gamma=0.0006930406, subsample=0.395, colsample_bytree=0.444, max_depth=8, min_child_weight=2, monotone_constraints="(0,0,0,0,0,0,1,0,1)", nrounds=21.
- Oracle: `two_pt_model.ubj`.

## 4. fg_model — **NEW: train as binary:logistic XGBoost** (was an mgcv GAM)
- Data: nflverse pbp 2014:current; filter `play_type_nfl=='FIELD_GOAL'` (FG attempts).
- Label: `sp` (field goal made; if `sp` absent derive `field_goal_result=='made'`).
- Features: `yardline_100` + the 4-level `fg_model_roof` one-hot (`fg_roof=(roof=='outdoors')`, `fg_era=(season>=2020)`, roof∈{00,01,10,11}) — i.e. features `yardline_100, fg_roof, fg_era` (or the 4 one-hot dummies). No weather.
- Params: binary:logistic, eval_metric=logloss, shallow (max_depth=3-4), modest eta, high min_child_weight (FG curve is smooth); tune nrounds by 5-fold CV.
- Oracle: `fg_model_grid.parquet` (the GAM grid). Validate by predicting over the yardline×roof×era grid and comparing FG% to the grid; **expect ~0.99 corr, NOT exact** (XGB step-approximates the spline) — report max abs FG% diff. Gate ≥0.98 corr.

## 5. wp_model — nfl4th home-WP (binary:logistic) — ATTEMPT, else document
- This is nfl4th's home-WP model (11 features: home_receive_2h_ko, spread_time, home_posteam, half_seconds_remaining, game_seconds_remaining, Diff_Time_Ratio, home_score_differential, home_ep, ydstogo, home_yardline_100, home_timeouts_remaining). Its exact training (cal_data + label = posteam/home won) is in `nflfastR/data-raw/MODELS.R`/`_tune_spread_wp.R` / guga31bb fourth_calculator. Dig the recipe; if cleanly reproducible, train + validate vs `wp_model.ubj`. If the recipe/cal_data is not obtainable, **skip + document** (keep the converted artifact) — do NOT block track7 on it.

## 6. punt_data — empirical distribution (NOT a model) → Python builder
- Build the punt landing distribution from pbp punts: per punt `yardline_after = yardline_100 - kick_distance + return_yards` (end-zone NA→20; BLOCKED NA→yardline_100; cap 100; 0→1); flags blocked / return_td(=yardline_after==100) / muff(fumble_lost, 0 if blocked). Group by yardline_100: coarse-bin muffed/blocked/td pct; KDE (scipy.stats.gaussian_kde 2D, or a binned histogram — document the choice) over (yardline_100, yardline_after) excluding blocked+td; per yardline normalize pct; add block(yardline_after=999→yardline_100)+td(=100) outlier rows rescaled by 1-(block+td); duplicate rows for muff∈{0,1} weighted by bin_muffed_pct; renormalize per yardline; `filter(yardline_100>30)`. Output cols: yardline_100, yardline_after, pct, muff.
- Oracle: `punt_data.parquet` (compare the per-yardline landing distributions; KDE bandwidth causes small divergence — gate on KS/total-variation distance small).

## Parity oracles (the converted R artifacts)
Local copies: `<sdv-py-stats>/dev/nfl4th_artifacts/` (`fd_model.ubj`, `two_pt_model.ubj`, `xpass_model.ubj`, `official/fd_model.ubj`, `official/two_pt_model.ubj`, `official/wp_model.ubj`, `fg_model_grid.parquet`, `punt_data.parquet`). Also published: `nfl_model_artifacts` (xpass) + `nfl_4th_down_models` (fd, wp).
