# Idempotently create the nfl_* release tags on the sportsdataverse-data publish repo.
# Run once (with GITHUB_PAT / SDV_GH_TOKEN that can write to the repo) before the first
# data run. "Already exists" errors are expected and ignored.
suppressPackageStartupMessages({ library(piggyback); library(cli) })

REPOS <- c("sportsdataverse/sportsdataverse-data")

TAGS <- list(
  nfl_model_pbp         = "NFL compiled play-by-play (EP/WP/QBR enriched; Python-built).",
  nfl_model_artifacts   = "NFL model artifacts (EP/WP-spread/WP-naive/CP .ubj) + model cards."
)

token <- Sys.getenv("GITHUB_PAT")
for (repo in REPOS) {
  for (tag in names(TAGS)) {
    tryCatch(
      piggyback::pb_release_create(repo = repo, tag = tag, name = tag,
                                   body = TAGS[[tag]], .token = token),
      error = function(e) cli::cli_alert_info("{repo}@{tag}: {conditionMessage(e)}")
    )
  }
}
cli::cli_alert_success("release tag init complete")
