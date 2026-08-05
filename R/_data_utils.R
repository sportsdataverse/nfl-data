# Shared helpers for nflverse nfl-data creation scripts.
# Pure-ish reshape + IO helpers; network isolated to fetch_* so reshape fns stay testable.
# Ported from cfbfastR-cfb-data with NFL-specific adaptations:
#   - No RAW_BASE (nfl-data is publish-only; raw lives in nfl-raw repo)
#   - PUBLISH_REPOS targets sportsdataverse-data

PUBLISH_REPOS <- c("sportsdataverse/sportsdataverse-data")

# JSON-encode any list-columns (nested participant/name lists) to character so arrow/csv
# can serialize them. Keeps all data, parquet/csv/rds share one schema.
stringify_list_cols <- function(df) {
  for (nm in names(df)) {
    col <- df[[nm]]
    if (is.list(col) && !is.data.frame(col)) {
      df[[nm]] <- vapply(col, function(x) {
        if (is.null(x) || length(x) == 0 || (length(x) == 1 && is.na(x[[1]]))) return(NA_character_)
        tryCatch(as.character(jsonlite::toJSON(x, auto_unbox = TRUE, null = "null", na = "null")),
                 error = function(e) paste(unlist(x), collapse = "|"))
      }, character(1))
    }
  }
  df
}

# Write parquet + rds + gzipped csv under nfl/{dataset}/ and append a manifest row.
write_dataset <- function(df, dataset, season, stem) {
  if (is.null(df) || nrow(df) == 0) {
    cli::cli_alert_info("{dataset} {season}: 0 rows, skipping write")
    return(invisible(NULL))
  }
  df <- stringify_list_cols(df)
  base <- file.path("nfl", dataset)
  for (sub in c("parquet", "rds", "csv")) dir.create(file.path(base, sub), recursive = TRUE, showWarnings = FALSE)
  arrow::write_parquet(df, file.path(base, "parquet", sprintf("%s_%d.parquet", stem, season)))
  saveRDS(df, file.path(base, "rds", sprintf("%s_%d.rds", stem, season)))
  readr::write_csv(df, file.path(base, "csv", sprintf("%s_%d.csv.gz", stem, season)))
  .append_manifest(dataset, season, nrow(df))
  invisible(df)
}

.append_manifest <- function(dataset, season, row_count) {
  f <- file.path("nfl", dataset, sprintf("nfl_%s_in_data_repo.csv", dataset))
  row <- data.frame(season = as.integer(season), row_count = as.integer(row_count),
                    generated_at_utc = format(Sys.time(), tz = "UTC", usetz = TRUE),
                    stringsAsFactors = FALSE)
  if (file.exists(f)) {
    old <- readr::read_csv(f, show_col_types = FALSE)
    row <- dplyr::bind_rows(old[old$season != season, , drop = FALSE], row)
  }
  row <- row[order(row$season), , drop = FALSE]
  readr::write_csv(row, f)
}

# Upload one file to BOTH publish repos under a release tag (idempotent overwrite),
# creating the release first if it does not exist. See .ensure_release_visible() for the
# piggyback cache / eventual-consistency handling that makes a cold self-create reliable.
pb_upload_both <- function(file, tag, repos = PUBLISH_REPOS, token = Sys.getenv("GITHUB_PAT")) {
  for (repo in repos) {
    # Make publishing self-sufficient when releases_init has not run: ensure the release
    # exists AND is visible in the (eventually-consistent, memoised) releases listing
    # before uploading. pb_upload() looks the release up via that same listing, so the
    # key is to leave the cache warmed to the CORRECT state -- i.e. poll until the tag
    # appears, then DON'T bust the cache again before pb_upload(). (Busting it right
    # before the upload re-fetches a still-propagating empty list -> "Could not find".)
    if (.ensure_release_visible(repo, tag, token)) {
      tryCatch(
        piggyback::pb_upload(file = file, repo = repo, tag = tag, overwrite = TRUE, .token = token),
        error = function(e) cli::cli_alert_danger("pb_upload {repo}@{tag} {basename(file)}: {conditionMessage(e)}")
      )
    } else {
      cli::cli_alert_danger("pb_upload {repo}@{tag} {basename(file)}: release never became visible")
    }
  }
}

# Ensure a release for `tag` exists on `repo` and is visible in pb_releases(), creating
# it if missing. Returns TRUE once visible (leaving the releases cache warmed to the
# correct state for an immediate pb_upload), FALSE if it never appears within the budget.
.ensure_release_visible <- function(repo, tag, token, tries = 24, wait = 5) {
  # Bust BOTH memoised caches: pb_releases() backs our visibility check, but pb_upload()
  # resolves the release via pb_info() -- forgetting only pb_releases leaves pb_upload
  # reading a stale "no release" and failing with "Could not find <tag>".
  bust <- function() {
    try(memoise::forget(piggyback::pb_releases), silent = TRUE)
    try(memoise::forget(piggyback::pb_info), silent = TRUE)
  }
  for (i in seq_len(tries)) {
    bust()
    visible <- tryCatch(
      isTRUE(tag %in% suppressWarnings(piggyback::pb_releases(repo = repo, .token = token))$tag_name),
      error = function(e) FALSE
    )
    if (visible) {
      bust()  # drop the pb_releases read we just cached so pb_upload's pb_info() re-fetches fresh
      return(TRUE)
    }
    # not visible yet: (re)attempt create (422-warns if it actually exists) then wait
    suppressWarnings(tryCatch(
      piggyback::pb_release_create(repo = repo, tag = tag, name = tag, .token = token),
      error = function(e) invisible(NULL)
    ))
    if (i == 1L) {
      cli::cli_alert_info(
        "Waiting for release {.val {tag}} on {.val {repo}} to propagate (GitHub list lag)..."
      )
    }
    Sys.sleep(wait)
  }
  FALSE
}

# Publish all three formats for a dataset+season to both repos.
publish_dataset <- function(dataset, season, stem, tag) {
  base <- file.path("nfl", dataset)
  specs <- list(
    list(sub = "parquet", fn = sprintf("%s_%d.parquet", stem, season)),
    list(sub = "rds",     fn = sprintf("%s_%d.rds", stem, season)),
    list(sub = "csv",     fn = sprintf("%s_%d.csv.gz", stem, season))
  )
  for (s in specs) {
    f <- file.path(base, s$sub, s$fn)
    if (file.exists(f)) pb_upload_both(f, tag)
  }
}
