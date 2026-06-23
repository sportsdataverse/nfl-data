#!/usr/bin/env Rscript
# Convert the nflverse R model objects that cannot be fetched as published .ubj
# into Python-loadable artifacts for sportsdataverse-py.
#
#   * xpass_model  (fastrmodels, raw xgb booster) -> xpass_model.ubj
#   * fg_model     (nfl4th, mgcv::bam GAM)         -> fg_model_grid.parquet
#   * punt_data    (nfl4th, data.frame)            -> punt_data.parquet
#
# The fd_model / two_pt_model / wp_model boosters are NOT converted here — they
# are taken directly from nfl4th's official `model_archive` release .ubj assets
# (a local re-conversion produced byte-identical files). See README.md.
#
# Edit the three path constants for your checkout, then: Rscript convert.R
suppressPackageStartupMessages({
  library(xgboost)
  library(mgcv)
  library(arrow)
})

OUT <- "."  # output dir for the artifacts
N4  <- "../../../nflverse-dev/nfl4th"        # nflverse/nfl4th checkout
FRM <- "../../../nflverse-dev/fastrmodels"   # nflverse/fastrmodels checkout
log <- function(...) cat(sprintf(...), "\n")

# ---------------------------------------------------------------------------
# 1. xpass_model -- fastrmodels raw xgb booster -> .ubj
#    feature order is fixed by nflfastR prepare_xpass_data() (no embedded names)
# ---------------------------------------------------------------------------
load(file.path(FRM, "data/xpass_model.rda"))  # -> xpass_model
xp <- if (is.raw(xpass_model)) xgb.Booster.complete(xgb.load.raw(xpass_model)) else xpass_model
xp_feats <- c(
  "down", "ydstogo", "yardline_100", "qtr", "wp", "vegas_wp",
  "era2", "era3", "era4", "score_differential", "home",
  "half_seconds_remaining", "posteam_timeouts_remaining",
  "defteam_timeouts_remaining", "outdoors", "retractable", "dome"
)
xgb.save(xp, file.path(OUT, "xpass_model.ubj"))
log("xpass_model.ubj written; %d features: %s", length(xp_feats), paste(xp_feats, collapse = ","))

# ---------------------------------------------------------------------------
# 2. fg_model -- mgcv bam GAM -> exact prediction grid parquet
#    formula: sp ~ s(yardline_100, by=interaction(fg_model_roof)) + fg_model_roof
#    keys: yardline_100 (int 1..99), fg_model_roof factor ("00","01","10","11")
#    Python does a lookup on (yardline_100, fg_model_roof) -> prob, which
#    reproduces the GAM exactly at every integer yardline.
# ---------------------------------------------------------------------------
load(file.path(N4, "data-raw/fg_model.Rdata"))  # -> fg_model
roof <- levels(fg_model$model$fg_model_roof)
if (is.null(roof)) roof <- c("00", "01", "10", "11")
grid <- expand.grid(
  yardline_100 = 1:99,
  fg_model_roof = factor(roof, levels = roof),
  stringsAsFactors = FALSE
)
grid$prob <- as.numeric(predict(fg_model, newdata = grid, type = "response"))
grid$fg_model_roof <- as.character(grid$fg_model_roof)
write_parquet(grid, file.path(OUT, "fg_model_grid.parquet"))
log("fg_model_grid.parquet written; %d rows; roof levels: %s", nrow(grid), paste(roof, collapse = ","))

# ---------------------------------------------------------------------------
# 3. punt_data -- nfl4th punt landing-yardline distribution -> parquet
#    cols: yardline_100 (range 31..99), yardline_after, pct, muff
#    Python joins on yardline_100; outside 31..99 there is no punt distribution
#    (the caller falls back to "no punt").
# ---------------------------------------------------------------------------
punt_df <- readRDS(file.path(N4, "data-raw/punt_data.rds"))
write_parquet(as.data.frame(punt_df), file.path(OUT, "punt_data.parquet"))
log("punt_data.parquet written; %d rows; cols: %s", nrow(punt_df), paste(names(punt_df), collapse = ","))

log("DONE")
