# nflfastR → Python porting reference

Source repo (read-only, sibling checkout): `nflverse-dev/nflfastR/R/`. All line
numbers below are from the `R/*.R` files as they exist in that checkout on
2026-07-03. This document is the single authoritative spec for porting the
listed functions to Python — no elision on hardcoded data tables; logic
functions are transcribed verbatim with a port-contract summary appended.

---

## §1 helper_scrape_nfl.R :: fix_bad_games (lines 358–421) and fix_posteams (lines 423–462)

```r
# helper function to manually fill in fields for problematic games
fix_bad_games <- function(pbp) {
  fixed <- pbp |>
    dplyr::mutate(
      #if team has the ball and scored, make them the scoring team
      td_team = dplyr::if_else(
        .data$drive_how_ended_description == 'Touchdown' &
          !is.na(.data$td_team),
        .data$posteam,
        .data$td_team
      ),
      #if team defensive team score, fill in the right team
      td_team = dplyr::if_else(
        #game involving the jags
        #defensive TD
        .data$drive_how_ended_description != 'Touchdown' &
          !is.na(.data$td_team),
        #if home team has ball, then away team scored, otherwise home team scored
        dplyr::if_else(
          .data$posteam == .data$home_team,
          .data$away_team,
          .data$home_team
        ),
        .data$td_team
      ),
      # fill in return team
      return_team = dplyr::if_else(
        !is.na(.data$return_team),
        dplyr::if_else(
          # if the home team has the ball, return team is away team (this is before we flip posteam for kickoffs)
          .data$posteam == .data$home_team,
          .data$away_team,
          .data$home_team
        ),
        .data$return_team
      ),
      fumble_recovery_1_team = dplyr::if_else(
        !is.na(.data$fumble_recovery_1_team),
        # assign possession based on fumble_lost
        dplyr::case_when(
          .data$fumble_lost == 1 &
            .data$posteam == .data$home_team ~ .data$away_team,
          .data$fumble_lost == 1 &
            .data$posteam == .data$away_team ~ .data$home_team,
          .data$fumble_lost == 0 &
            .data$posteam == .data$home_team ~ .data$home_team,
          .data$fumble_lost == 0 &
            .data$posteam == .data$away_team ~ .data$away_team
        ),
        .data$fumble_recovery_1_team
      ),
      timeout_team = dplyr::if_else(
        # if there's a timeout in the affected seasons
        !is.na(.data$timeout_team),
        # extract from play description
        stringr::str_extract(
          .data$play_description,
          "(?<=Timeout #[1-3] by )[:upper:]+"
        ),
        .data$timeout_team
      )
    )

  return(fixed)
}

fix_posteams <- function(pbp) {
  # Data source switch in 2023 introduced new problems
  # 1. Definition of posteam on kick offs changed to receiving team. That's our
  #    definition and we swap teams later.
  # 2. Posteam doesn't change on the PAT after defensive TD
  #
  # We adjust both things here
  # We need the variable pre_play_by_play which usually looks like "KC  1-10  NYJ 40"
  if ("pre_play_by_play" %in% names(pbp)) {
    # Let's be as explicit as possible about what we want to extract from the string
    # It's really only the first valid team abbreviation followed by a blank space
    valid_team_abbrs <- paste(
      nflfastR::teams_colors_logos$team_abbr,
      collapse = " |"
    )
    posteam_regex <- paste0("^", valid_team_abbrs, "(?=[:space:])")

    pbp <- pbp |>
      dplyr::mutate(
        parsed_posteam = stringr::str_extract(
          .data$pre_play_by_play,
          posteam_regex
        ) |>
          stringr::str_trim(),
        posteam = dplyr::case_when(
          stringr::str_detect(
            .data$play_description,
            "^Timeout "
          ) ~ NA_character_,
          is.na(.data$parsed_posteam) ~ .data$posteam,
          .data$play_description == "GAME" ~ NA_character_,
          TRUE ~ .data$parsed_posteam
        ),
        # drop helper
        parsed_posteam = NULL
      )
  }

  pbp
}
```

**Port contract**

- `fix_bad_games(pbp)` — called only when `home_team == away_team` was
  detected in the raw NFL feed (`get_pbp_nfl`, line 46 `bad_game <- 1`), i.e. a
  small, enumerable set of historically broken games. It repairs 4 columns in
  place, no new columns, no row filter, order-preserving:
  - `td_team` (Utf8) — reassigned from `posteam`/`home_team`/`away_team` based
    on `drive_how_ended_description` and current `fumble_lost`.
  - `return_team` (Utf8) — reassigned from `home_team`/`away_team` using
    `posteam == home_team`.
  - `fumble_recovery_1_team` (Utf8) — reassigned via a 4-branch case on
    `fumble_lost` × `posteam == home/away`.
  - `timeout_team` (Utf8) — re-extracted from `play_description` with regex
    `(?<=Timeout #[1-3] by )[:upper:]+` (lookbehind — **polars/Rust regex has
    no lookaround**; port as a capture group + strip prefix, or
    `str.extract(r"Timeout #[1-3] by ([A-Z]+)", 1)`).
  - No grouping; row-wise `if_else`/`case_when` only. Depends on
    `posteam`/`home_team`/`away_team` already being populated (this runs after
    `fix_posteams()` in `get_pbp_nfl`, see line 303–308).

- `fix_posteams(pbp)` — runs unconditionally inside `get_pbp_nfl` right before
  the `bad_game` branch (pipeline position: line 303). No-ops if
  `pre_play_by_play` column is absent (defensive check for older/alternate
  feeds).
  - External data dependency: `nflfastR::teams_colors_logos$team_abbr` — a
    **released package dataset** (not sysdata), built by
    `data-raw/teams_colors_logos.R` via `nflreadr::load_teams()`. Schema for
    the one column used here: `team_abbr` (Utf8, one row per current + former
    franchise abbreviation, ~36 rows). For a Python port, vendor the
    equivalent of `nflreadr::load_teams()$team_abbr` (nflreadr ships this as a
    static CSV under `nflverse-data`; see cross-cutting notes for the exact
    release asset).
  - Regex uses a **lookahead** `(?=[:space:])` (portable to polars `(?=\s)` is
    fine — lookAHEAD is supported by Rust regex; only lookBEHIND is
    unsupported). Builds `posteam_regex <- "^TEAM1 |TEAM2 |...(?=[:space:])"`
    from the team abbreviation list, then extracts + trims.
  - Output: overwrites `posteam` (Utf8) in-place using a 3-branch
    `case_when`: `NA` on `"^Timeout "` prefixed descriptions, unchanged
    passthrough when the regex found nothing, `NA` on the literal `"GAME"`
    row, otherwise the parsed value. Drops the temporary `parsed_posteam`
    column.

---

## §2 helper_add_nflscrapr_mutations.R :: fix_scrambles (lines 797–818) and restore_kickoff_attempt (lines 898–904)

```r
fix_scrambles <- function(pbp) {
  # skip below code if <= 2005 is not in the data
  if (min(pbp$season) > 2005) {
    return(pbp)
  }

  pbp |>
    dplyr::mutate(
      scramble_id = paste0(.data$game_id, "_", .data$play_id),
      qb_scramble = dplyr::if_else(
        .data$scramble_id %in% scramble_fix,
        1,
        .data$qb_scramble
      )
    ) |>
    dplyr::select(-"scramble_id")

  # Some notes on the scramble_fix:
  # This marks scrambles in the 1999 - 2005 season using charting data
  # Because NFL did not put scramble in play description during this season
  # Data from Aaron Schatz!
}
```

```r
# we overwrite kickoff_attempt for kickoffs with penalties because
# those mess with ep/epa/wp/wpa. Since this is inconsistent compared to
# all other *_attempt variables, we will restore kickoff_attempt after
# models are applied. That's done with a temporary copy of kickoff_attempt.
# See #556, #202, #199 for example
restore_kickoff_attempt <- function(pbp) {
  pbp |>
    dplyr::mutate(
      kickoff_attempt = .data$copy_of_kickoff_attempt,
      copy_of_kickoff_attempt = NULL
    )
}
```

**Port contract**

- `fix_scrambles(pbp)` — no-ops entirely (`return(pbp)` unchanged) if
  `min(season) > 2005`; otherwise builds a row key `f"{game_id}_{play_id}"`
  and flips `qb_scramble` to `1` wherever that key is in the `scramble_fix`
  set. Called from inside `add_nflscrapr_mutations` (line 747, right before
  `make_model_mutations()`), i.e. **after** `qb_scramble` has already been
  string-detected from `play_description` (line 410–414) and **after**
  `play_type`/`qb_dropback` have already been derived from the un-fixed
  `qb_scramble` (lines 423–445) — this is a parity-critical ordering detail:
  the 1999–2005 charting-data scramble fix does NOT retroactively change
  `play_type` or `qb_dropback` for those rows; it only flips the raw
  `qb_scramble` flag downstream of where those columns were already computed
  in the same pipe.
  - Output: `qb_scramble` (0/1 numeric) mutated; no other columns added or
    removed (temp `scramble_id` dropped).
  - **External data dependency — `scramble_fix`.** This is a `sysdata.rda`
    object (`R/sysdata.rda`, loaded automatically into the package
    namespace), NOT a runtime HTTP/CSV fetch as the task brief guessed. It is
    a plain character vector of **5,830** `"{game_id}_{play_id}"` strings,
    generated once at package-build time by `data-raw/build_scramble_fix.R`
    from three vendored Football-Outsiders/Aaron-Schatz charting-data
    spreadsheets checked into `data-raw/`:
    - `data-raw/scrambles_2005.xlsx` (2005 season)
    - `data-raw/Scrambles 1999-2004 UPDATE for NFLfastR.xlsx` (1999–2004,
      filtered to `type %in% c("scramble", "assume scramble")`)
    - `data-raw/Scrambles.1999-2003.FURTHER.UPDATE.for.NFLfastR.xlsx` — a
      **correction** list: plays in this file are excluded from the final
      `scramble_fix` vector (they were miscoded as scrambles and are actually
      rushes; see nflfastR issue #475). The build script left-joins these
      corrected `game_id_play_id` values as `no_scramble_id` and filters them
      out of the combined `d` frame before taking `unique(d$scramble_id)`.
    - The build script also hardcodes one more exclusion:
      `filter(scramble_id != "2005_09_CIN_BAL_1725")`.
    - Build join keys: `week, away_team, home_team, posteam, qtr, down,
      ydstogo, time, season` against `nflfastR::load_pbp(1999:2005)` filtered
      to plausible-scramble rows (`!is.na(rusher_player_id) | penalty == 1`,
      `is.na(passer_player_id)`, `is.na(receiver_player_id)`); team names are
      normalized through `team_name_fn` before the join; `time` is
      zero-padded to `"MM:SS"`.
    - Final schema: `character(5830)`, no other columns — just the
      `"{game_id}_{play_id}"` key. Saved via
      `saveRDS(scramble_fix, "data-raw/scramble_fix.rds")` and then bundled
      into `R/sysdata.rda` for runtime use (`usethis::use_data(...,
      internal = TRUE)` semantics — not shown in the vendored file list but
      implied by the object living in `sysdata.rda`).
    - **Vendored for this port**: the full, complete 5,830-row list has been
      extracted from `R/sysdata.rda` and committed alongside this document at
      `docs/superpowers/plans/2026-07-03-nflfastr-scramble-fix.csv` (single
      column `scramble_id`, one row per game_id_play_id key). Load it as a
      Python `set[str]` and test set membership on
      `f"{game_id}_{play_id}"` — do not attempt to regenerate from the Excel
      files; the correction pass (`s3` exclusions) makes an independent
      re-derivation from those spreadsheets NOT equivalent unless the same
      exclusion logic is reproduced exactly.

- `restore_kickoff_attempt(pbp)` — trivial rename: copies
  `copy_of_kickoff_attempt` (created in `add_nflscrapr_mutations`, line 235,
  as a snapshot of `kickoff_attempt` **before** it gets overwritten for
  penalty-replayed kickoffs at lines 236–247) back onto `kickoff_attempt`,
  then drops the temp column. Runs near the very end of the top-level
  pipeline (`top-level_scraper.R` line 466, after `add_series_data()`) so
  that EP/WP/CP model application — which needs the "logical" kickoff flag
  including plays replayed for penalty — sees the inflated flag, while the
  final published `kickoff_attempt` matches the NFL's own attempt count.

---

## §3 helper_additional_functions.R :: fix_weird_pass_plays (lines 641–661)

```r
# Function that fixes false "pass" positives in some hard coded plays where
# the parser logic reached its limit
fix_weird_pass_plays <- function(pass, game_id, play_id) {
  combined_id <- paste(game_id, play_id, sep = "_")
  false_positives <- c(
    "1999_01_ARI_PHI_1611",
    "1999_01_SF_JAX_1788",
    "1999_01_SF_JAX_2081",
    "1999_11_ATL_TB_1740",
    "2001_09_MIN_PHI_1307",
    "2001_14_NE_BUF_452",
    "2002_16_PIT_TB_527",
    "2003_02_HOU_NO_3924",
    "2003_15_PIT_NYJ_873",
    "2004_05_BUF_NYJ_2555",
    "2005_07_SD_PHI_321",
    "2011_02_STL_NYG_1369",
    "2016_05_NE_CLE_912",
    "2016_06_CAR_NO_2690",
    "2020_10_BAL_NE_2013"
  )
  data.table::fifelse(combined_id %chin% false_positives, 0, pass, pass)
}
```

**Port contract**

- Pure function, no external data dependency — the 15-row `false_positives`
  list above is transcribed complete (verify count: 15 game_id_play_id keys).
- Signature: `fix_weird_pass_plays(pass: int, game_id: str, play_id: int) ->
  int`, vectorized over the pbp frame (`data.table::fifelse` is a vectorized
  ternary; in polars this is
  `pl.when(pl.concat_str(["game_id", "play_id"], separator="_").is_in(false_positives)).then(0).otherwise(pl.col("pass"))`).
  `%chin%` is `data.table`'s fast character-`%in%`; semantically identical to
  `%in%` for this purpose.
  - Called from `clean_pbp` (line 185): `pass =
    fix_weird_pass_plays(.data$pass, .data$game_id, .data$play_id)` — i.e.
    this is a **post-hoc override** applied after `pass` has already been
    derived from `desc` regex detection (§14 below) and after the
    backward/lateral-pass and kickoff exclusions. It only ever forces `pass`
    from `1` → `0` on these 15 specific plays; it never sets `pass` to `1`.

---

## §4 utils.R :: time_to_seconds (lines 132–135), plus every quarter/half/game_seconds_remaining computation site

```r
# take a time string of the format "MM:SS" and convert it to seconds
time_to_seconds <- function(time) {
  as.numeric(strptime(time, format = "%M:%S")) -
    as.numeric(strptime("0", format = "%S"))
}
```

**Port contract for `time_to_seconds`**: input is a display clock string
`"MM:SS"` representing time **remaining** in the quarter (nflfastR's `time`
column, NOT time elapsed). `strptime(..., "%M:%S")` parses it against
today's date at `00:MM:SS`; subtracting `strptime("0", "%S")` (today at
`00:00:00`) yields the number of seconds represented by `MM:SS` — i.e. this
is just `minutes*60 + seconds`, done through POSIXct arithmetic instead of a
direct split so that malformed strings become `NA` the same way R's date
parser fails silently to `NA`. Python port:
`int(m) * 60 + int(s)` after `time.split(":")`, propagating `None`/`NaN` for
unparseable input (empty string, `None`, non-`"MM:SS"` shape) to match
`strptime`'s `NA`-on-failure semantics exactly — do NOT raise on bad input.

### Site 1 — `helper_scrape_nfl.R :: get_pbp_nfl`, `quarter_end` derivation (precursor to the clock fields) — lines 201–205

```r
      quarter_end = dplyr::if_else(
        stringr::str_detect(.data$play_description, "END QUARTER"),
        1,
        0
      ),
```

`get_pbp_nfl` itself does **not** compute `quarter_seconds_remaining`,
`half_seconds_remaining`, or `game_seconds_remaining` — it only derives the
`quarter_end` flag (from the literal `"END QUARTER"` substring in
`play_description`) and does two hardcoded per-play clock-string typo fixes
(below) that the seconds-remaining computation later consumes.

### Site 2 — `helper_scrape_nfl.R :: get_pbp_nfl`, hardcoded raw-clock-string corrections — lines 261–265

```r
      time = dplyr::case_when(
        id == '2012_04_NO_GB' & .data$play_id == 1085 ~ '3:34',
        id == '2012_16_BUF_MIA' & .data$play_id == 2571 ~ '8:31',
        TRUE ~ .data$time
      ),
```

**Port contract**: these 2 hardcoded overrides must be applied to the raw
`time` string **before** any `time_to_seconds` call touches these two plays;
transcribe verbatim (2 rows only, complete).

### Site 3 — `helper_add_nflscrapr_mutations.R :: add_nflscrapr_mutations`, null-clock imputation + quarter_seconds_remaining — lines 25–39

```r
    dplyr::mutate(
      # Modify the time column for the quarter end:
      time = dplyr::if_else(
        .data$quarter_end == 1 |
          (.data$play_description == "END GAME" & is.na(.data$time)),
        "00:00",
        .data$time
      ),
      time = dplyr::if_else(
        .data$play_description == 'GAME',
        "15:00",
        .data$time
      ),
      # Create a column with the time in seconds remaining for the quarter:
      quarter_seconds_remaining = time_to_seconds(.data$time),
```

**Port contract**: this is the canonical null-clock imputation. Two rules,
applied in this exact order, before `time_to_seconds()` is ever called:
1. Any row with `quarter_end == 1` (i.e. `desc` contains `"END QUARTER"`), OR
   a `desc == "END GAME"` row whose `time` is missing → force `time =
   "00:00"` (0 seconds remaining in the quarter).
2. Any row with `desc == 'GAME'` (the synthetic kickoff-of-game marker row) →
   force `time = "15:00"` (900 seconds remaining — start of Q1).
3. THEN `quarter_seconds_remaining <- time_to_seconds(time)` for every row
   using the (possibly just-overwritten) `time` string.
   This mutate block runs immediately after de-duplication
   (`group_by(game_id, quarter, time, play_description, down) |>
   slice(1)`) and immediately before the definitive play ordering
   (`arrange(order_sequence, quarter, !is.na(quarter_seconds_remaining),
   -quarter_seconds_remaining, !is.na(drive), drive, index, .by_group =
   TRUE)` — note `quarter_seconds_remaining` is itself one of the **sort
   keys** used to place plays within a quarter, so it must be computed before
   ordering, and the `!is.na(...)` / `-value` pairing means NA-clock rows
   sort **first** within their quarter, ties broken descending by seconds
   remaining).

### Site 4 — `helper_add_nflscrapr_mutations.R :: add_nflscrapr_mutations`, half_seconds_remaining / game_seconds_remaining — lines 343–355

```r
      # Create a column with the time in seconds remaining for each half:
      half_seconds_remaining = dplyr::if_else(
        .data$quarter %in% c(1, 3),
        .data$quarter_seconds_remaining + 900,
        .data$quarter_seconds_remaining
      ),
      # Create a column with the time in seconds remaining for the game:
      game_seconds_remaining = dplyr::if_else(
        .data$quarter %in% c(1, 2, 3, 4),
        .data$quarter_seconds_remaining +
          (900 * (4 - as.numeric(.data$quarter))),
        .data$quarter_seconds_remaining
      ),
```

**Port contract**: derived directly and only from `quarter_seconds_remaining`
+ `quarter` (renamed `qtr` later at line 718 via
`dplyr::rename(qtr = "quarter")` — note: at this point in the pipe the
column is still named `quarter`).
- `half_seconds_remaining = quarter_seconds_remaining + 900` when `quarter
  ∈ {1, 3}` (first quarter of each half), else `= quarter_seconds_remaining`
  (quarter ∈ {2, 4, 5+/OT}).
- `game_seconds_remaining = quarter_seconds_remaining + 900*(4 - quarter)`
  for `quarter ∈ {1,2,3,4}` (regulation), else `=
  quarter_seconds_remaining` (i.e. **OT quarters (qtr ≥ 5) get
  `game_seconds_remaining == quarter_seconds_remaining`** — there is no
  "game clock" concept once regulation ends; this is a common gotcha for a
  from-scratch port that assumes game_seconds_remaining is always
  monotonically defined over 3600s).
- No further recomputation or imputation of these three columns occurs
  anywhere else in `helper_scrape_nfl.R` or `helper_add_nflscrapr_mutations.R`
  — downstream consumers (`add_ep_variables`, `add_wp_variables`, xYAC, CP)
  only ever *offset* `half_seconds_remaining`/`game_seconds_remaining` by
  fixed constants for hypothetical alternate plays (missed FG, kickoff,
  air-yards-adjusted down), never recompute them from `time`/`quarter` again.

---

## §5 helper_add_ep_wp.R :: add_air_yac_ep_variables, add_air_yac_ep, add_air_yac_wp_variables, add_air_yac_wp

### add_air_yac_ep (lines 13–47) — wrapper / all-NA short-circuit

```r
add_air_yac_ep <- function(pbp) {
  if (nrow(pbp |> dplyr::filter(!is.na(.data$air_yards))) == 0) {
    out <- pbp |>
      dplyr::mutate(
        air_epa = NA_real_,
        yac_epa = NA_real_,
        comp_air_epa = NA_real_,
        comp_yac_epa = NA_real_,
        home_team_comp_air_epa = NA_real_,
        away_team_comp_air_epa = NA_real_,
        home_team_comp_yac_epa = NA_real_,
        away_team_comp_yac_epa = NA_real_,
        total_home_comp_air_epa = NA_real_,
        total_away_comp_air_epa = NA_real_,
        total_home_comp_yac_epa = NA_real_,
        total_away_comp_yac_epa = NA_real_,
        home_team_raw_air_epa = NA_real_,
        away_team_raw_air_epa = NA_real_,
        home_team_raw_yac_epa = NA_real_,
        away_team_raw_yac_epa = NA_real_,
        total_home_raw_air_epa = NA_real_,
        total_away_raw_air_epa = NA_real_,
        total_home_raw_yac_epa = NA_real_,
        total_away_raw_yac_epa = NA_real_
      )
    user_message(
      "No non-NA air_yards detected. air_yac_ep variables set to NA",
      "info"
    )
  } else {
    out <- pbp |> add_air_yac_ep_variables()
    user_message("added air_yac_ep variables", "done")
  }
  return(out)
}
```

### add_air_yac_wp (lines 55–89) — wrapper / all-NA short-circuit

```r
add_air_yac_wp <- function(pbp) {
  if (nrow(pbp |> dplyr::filter(!is.na(.data$air_yards))) == 0) {
    out <- pbp |>
      dplyr::mutate(
        air_wpa = NA_real_,
        yac_wpa = NA_real_,
        comp_air_wpa = NA_real_,
        comp_yac_wpa = NA_real_,
        home_team_comp_air_wpa = NA_real_,
        away_team_comp_air_wpa = NA_real_,
        home_team_comp_yac_wpa = NA_real_,
        away_team_comp_yac_wpa = NA_real_,
        total_home_comp_air_wpa = NA_real_,
        total_away_comp_air_wpa = NA_real_,
        total_home_comp_yac_wpa = NA_real_,
        total_away_comp_yac_wpa = NA_real_,
        home_team_raw_air_wpa = NA_real_,
        away_team_raw_air_wpa = NA_real_,
        home_team_raw_yac_wpa = NA_real_,
        away_team_raw_yac_wpa = NA_real_,
        total_home_raw_air_wpa = NA_real_,
        total_away_raw_air_wpa = NA_real_,
        total_home_raw_yac_wpa = NA_real_,
        total_away_raw_yac_wpa = NA_real_
      )
    user_message(
      "No non-NA air_yards detected. air_yac_wp variables set to NA",
      "info"
    )
  } else {
    out <- pbp |> add_air_yac_wp_variables()
    user_message("added air_yac_wp variables", "done")
  }
  return(out)
}
```

### add_air_yac_ep_variables (lines 1345–1584)

```r
add_air_yac_ep_variables <- function(pbp_data) {
  #testing
  #pbp_data <- g

  # Final all pass attempts that are not sacks:
  pass_plays_i <- which(
    !is.na(pbp_data$air_yards) & pbp_data$play_type == 'pass'
  )
  pass_pbp_data <- pbp_data[pass_plays_i, ]

  # Using the air_yards need to update the following:
  # - yrdline100
  # - TimeSecs_Remaining
  # - ydstogo
  # - down
  # - timeouts

  # Get everything set up for calculation
  pass_pbp_data <- pass_pbp_data |>
    dplyr::mutate(
      posteam_timeouts_pre = .data$posteam_timeouts_remaining,
      defeam_timeouts_pre = .data$defteam_timeouts_remaining
    ) |>
    # Rename the old columns to update for calculating the EP from the air:
    dplyr::rename(
      old_yrdline100 = .data$yardline_100,
      old_ydstogo = .data$ydstogo,
      old_TimeSecs_Remaining = .data$half_seconds_remaining,
      old_down = .data$down
    ) |>
    dplyr::mutate(
      Turnover_Ind = dplyr::if_else(
        .data$old_down == 4 & .data$air_yards < .data$old_ydstogo,
        1,
        0
      ),
      yardline_100 = dplyr::if_else(
        .data$Turnover_Ind == 0,
        .data$old_yrdline100 - .data$air_yards,
        100 - (.data$old_yrdline100 - .data$air_yards)
      ),
      ydstogo = dplyr::if_else(
        .data$air_yards >= .data$old_ydstogo |
          .data$Turnover_Ind == 1,
        10,
        .data$old_ydstogo - .data$air_yards
      ),
      down = dplyr::if_else(
        .data$air_yards >= .data$old_ydstogo |
          .data$Turnover_Ind == 1,
        1,
        as.numeric(.data$old_down) + 1
      ),
      half_seconds_remaining = .data$old_TimeSecs_Remaining - 5.704673,
      down1 = dplyr::if_else(.data$down == 1, 1, 0),
      down2 = dplyr::if_else(.data$down == 2, 1, 0),
      down3 = dplyr::if_else(.data$down == 3, 1, 0),
      down4 = dplyr::if_else(.data$down == 4, 1, 0),
      posteam_timeouts_remaining = dplyr::if_else(
        .data$Turnover_Ind == 1,
        .data$defeam_timeouts_pre,
        .data$posteam_timeouts_pre
      ),
      defteam_timeouts_remaining = dplyr::if_else(
        .data$Turnover_Ind == 1,
        .data$posteam_timeouts_pre,
        .data$defeam_timeouts_pre
      )
    )

  #get EP predictions
  pass_pbp_data_preds <- get_preds(pass_pbp_data)

  # Convert to air EP:
  pass_pbp_data_preds <- dplyr::mutate(
    pass_pbp_data_preds,
    airEP = (.data$Opp_Safety * -2) +
      (.data$Opp_Field_Goal * -3) +
      (.data$Opp_Touchdown * -7) +
      (.data$Safety * 2) +
      (.data$Field_Goal * 3) +
      (.data$Touchdown * 7)
  )

  # Return back to the passing data:
  pass_pbp_data$airEP <- pass_pbp_data_preds$airEP

  # For the plays that have TimeSecs_Remaining 0 or less, set airEP to 0:
  pass_pbp_data$airEP[which(pass_pbp_data$half_seconds_remaining <= 0)] <- 0

  # Calculate the airEPA based on 4 scenarios:
  pass_pbp_data$airEPA <- with(
    pass_pbp_data,
    ifelse(
      old_yrdline100 - air_yards <= 0,
      7 - ep,
      ifelse(
        old_yrdline100 - air_yards > 99,
        -2 - ep,
        ifelse(Turnover_Ind == 1, (-1 * airEP) - ep, airEP - ep)
      )
    )
  )

  # If the play is a two-point conversion then change the airEPA to NA since
  # no air yards are provided:
  pass_pbp_data$airEPA <- with(
    pass_pbp_data,
    ifelse(two_point_attempt == 1, NA, airEPA)
  )
  # Calculate the yards after catch EPA:
  pass_pbp_data <- dplyr::mutate(
    pass_pbp_data,
    yacEPA = .data$epa - .data$airEPA
  )

  # if Yards after catch is 0 make yacEPA set to 0:
  pass_pbp_data$yacEPA <- ifelse(
    pass_pbp_data$penalty == 0 &
      pass_pbp_data$yards_after_catch == 0 &
      pass_pbp_data$complete_pass == 1,
    0,
    pass_pbp_data$yacEPA
  )

  # if Yards after catch is 0 make airEPA set to EPA:
  pass_pbp_data$airEPA <- ifelse(
    pass_pbp_data$penalty == 0 &
      pass_pbp_data$yards_after_catch == 0 &
      pass_pbp_data$complete_pass == 1,
    pass_pbp_data$epa,
    pass_pbp_data$airEPA
  )

  # Now add airEPA and yacEPA to the original dataset:
  pbp_data$airEPA <- NA
  pbp_data$yacEPA <- NA
  pbp_data$airEPA[pass_plays_i] <- pass_pbp_data$airEPA
  pbp_data$yacEPA[pass_plays_i] <- pass_pbp_data$yacEPA

  # Now change the names to be the right style, calculate the completion form
  # of the variables, as well as the cumulative totals and return:
  pbp_data |>
    dplyr::rename(air_epa = "airEPA", yac_epa = "yacEPA") |>
    dplyr::group_by(.data$game_id) |>
    dplyr::mutate(
      comp_air_epa = dplyr::if_else(.data$complete_pass == 1, .data$air_epa, 0),
      comp_yac_epa = dplyr::if_else(.data$complete_pass == 1, .data$yac_epa, 0),
      home_team_comp_air_epa = dplyr::if_else(
        .data$posteam == .data$home_team,
        .data$comp_air_epa,
        -.data$comp_air_epa
      ),
      away_team_comp_air_epa = dplyr::if_else(
        .data$posteam == .data$away_team,
        .data$comp_air_epa,
        -.data$comp_air_epa
      ),
      home_team_comp_yac_epa = dplyr::if_else(
        .data$posteam == .data$home_team,
        .data$comp_yac_epa,
        -.data$comp_yac_epa
      ),
      away_team_comp_yac_epa = dplyr::if_else(
        .data$posteam == .data$away_team,
        .data$comp_yac_epa,
        -.data$comp_yac_epa
      ),
      home_team_comp_air_epa = dplyr::if_else(
        is.na(.data$home_team_comp_air_epa),
        0,
        .data$home_team_comp_air_epa
      ),
      away_team_comp_air_epa = dplyr::if_else(
        is.na(.data$away_team_comp_air_epa),
        0,
        .data$away_team_comp_air_epa
      ),
      home_team_comp_yac_epa = dplyr::if_else(
        is.na(.data$home_team_comp_yac_epa),
        0,
        .data$home_team_comp_yac_epa
      ),
      away_team_comp_yac_epa = dplyr::if_else(
        is.na(.data$away_team_comp_yac_epa),
        0,
        .data$away_team_comp_yac_epa
      ),
      total_home_comp_air_epa = cumsum(.data$home_team_comp_air_epa),
      total_away_comp_air_epa = cumsum(.data$away_team_comp_air_epa),
      total_home_comp_yac_epa = cumsum(.data$home_team_comp_yac_epa),
      total_away_comp_yac_epa = cumsum(.data$away_team_comp_yac_epa),
      # Same but for raw - not just completions:
      home_team_raw_air_epa = dplyr::if_else(
        .data$posteam == .data$home_team,
        .data$air_epa,
        -.data$air_epa
      ),
      away_team_raw_air_epa = dplyr::if_else(
        .data$posteam == .data$away_team,
        .data$air_epa,
        -.data$air_epa
      ),
      home_team_raw_yac_epa = dplyr::if_else(
        .data$posteam == .data$home_team,
        .data$yac_epa,
        -.data$yac_epa
      ),
      away_team_raw_yac_epa = dplyr::if_else(
        .data$posteam == .data$away_team,
        .data$yac_epa,
        -.data$yac_epa
      ),
      home_team_raw_air_epa = dplyr::if_else(
        is.na(.data$home_team_raw_air_epa),
        0,
        .data$home_team_raw_air_epa
      ),
      away_team_raw_air_epa = dplyr::if_else(
        is.na(.data$away_team_raw_air_epa),
        0,
        .data$away_team_raw_air_epa
      ),
      home_team_raw_yac_epa = dplyr::if_else(
        is.na(.data$home_team_raw_yac_epa),
        0,
        .data$home_team_raw_yac_epa
      ),
      away_team_raw_yac_epa = dplyr::if_else(
        is.na(.data$away_team_raw_yac_epa),
        0,
        .data$away_team_raw_yac_epa
      ),
      total_home_raw_air_epa = cumsum(.data$home_team_raw_air_epa),
      total_away_raw_air_epa = cumsum(.data$away_team_raw_air_epa),
      total_home_raw_yac_epa = cumsum(.data$home_team_raw_yac_epa),
      total_away_raw_yac_epa = cumsum(.data$away_team_raw_yac_epa)
    ) |>
    dplyr::ungroup()
}
```

### add_air_yac_wp_variables (lines 1591–2036)

```r
add_air_yac_wp_variables <- function(pbp_data) {
  #testing
  #pbp_data <- g

  # Change the names to reflect the old style - will update this later on:
  pbp_data <- pbp_data |>
    dplyr::mutate(
      posteam_timeouts_pre = .data$posteam_timeouts_remaining,
      defeam_timeouts_pre = .data$defteam_timeouts_remaining
    )

  # Final all pass attempts that are not sacks:
  pass_plays_i <- which(
    !is.na(pbp_data$air_yards) & pbp_data$play_type == 'pass'
  )
  pass_pbp_data <- pbp_data[pass_plays_i, ]

  pass_pbp_data <- pass_pbp_data |>
    dplyr::mutate(
      half_seconds_remaining = .data$half_seconds_remaining - 5.704673,
      game_seconds_remaining = .data$game_seconds_remaining - 5.704673,
      Diff_Time_Ratio = .data$score_differential /
        (exp(-4 * .data$elapsed_share)),
      Turnover_Ind = dplyr::if_else(
        .data$down == 4 & .data$air_yards < .data$ydstogo,
        1,
        0
      ),
      Diff_Time_Ratio = dplyr::if_else(
        .data$Turnover_Ind == 1,
        -1 * .data$Diff_Time_Ratio,
        .data$Diff_Time_Ratio
      ),
      posteam_timeouts_remaining = dplyr::if_else(
        .data$Turnover_Ind == 1,
        .data$defeam_timeouts_pre,
        .data$posteam_timeouts_pre
      ),
      defteam_timeouts_remaining = dplyr::if_else(
        .data$Turnover_Ind == 1,
        .data$posteam_timeouts_pre,
        .data$defeam_timeouts_pre
      )
    )

  # Calculate the airWP:
  pass_pbp_data$airWP <- get_preds_wp(pass_pbp_data)

  # Now for plays marked with Turnover_Ind, use 1 - airWP to flip back to the original
  # team with possession:
  pass_pbp_data$airWP <- ifelse(
    pass_pbp_data$Turnover_Ind == 1,
    1 - pass_pbp_data$airWP,
    pass_pbp_data$airWP
  )

  # For the plays that have TimeSecs_Remaining 0 or less, set airWP to 0:
  pass_pbp_data$airWP[which(pass_pbp_data$half_seconds_remaining <= 0)] <- 0
  pass_pbp_data$airWP[which(pass_pbp_data$game_seconds_remaining <= 0)] <- 0

  # Calculate the airWPA and yacWPA:
  pass_pbp_data <- dplyr::mutate(
    pass_pbp_data,
    airWPA = .data$airWP - .data$wp,
    yacWPA = .data$wpa - .data$airWPA
  )

  # If the play is a two-point conversion then change the airWPA to NA since
  # no air yards are provided:
  pass_pbp_data$airWPA <- with(
    pass_pbp_data,
    ifelse(two_point_attempt == 1, NA, airWPA)
  )
  pass_pbp_data$yacWPA <- with(
    pass_pbp_data,
    ifelse(two_point_attempt == 1, NA, yacWPA)
  )

  # Check to see if there is any overtime plays, if so then need to calculate
  # by essentially taking the same process as the airEP calculation and using
  # the resulting probabilities for overtime:

  # First check if there's any overtime plays:
  if (any(pass_pbp_data$qtr == 5 | pass_pbp_data$qtr == 6)) {
    # Find the rows that are overtime:
    pass_overtime_i <- which(pass_pbp_data$qtr == 5 | pass_pbp_data$qtr == 6)
    pass_overtime_df <- pass_pbp_data[pass_overtime_i, ]

    # Find the rows that are overtime:

    # Need to generate same overtime scenario data as before in the wp function:
    # Find the rows that are overtime:
    overtime_i <- which(pbp_data$qtr == 5 | pbp_data$qtr == 6)

    overtime_df <- pbp_data[overtime_i, ]

    # Separate routine for overtime:

    # Create a column that is just the first drive of overtime repeated:
    overtime_df$First_Drive <- rep(
      min(overtime_df$drive, na.rm = TRUE),
      nrow(overtime_df)
    )

    # Calculate the difference in drive number
    overtime_df <- dplyr::mutate(
      overtime_df,
      Drive_Diff = .data$drive - .data$First_Drive
    )

    # Create an indicator column that means the posteam is losing by 3 and
    # its the second drive of overtime:
    overtime_df$One_FG_Game <- ifelse(
      overtime_df$score_differential == -3 &
        overtime_df$Drive_Diff == 1,
      1,
      0
    )

    # Now create a copy of the dataset to then make the EP predictions for when
    # a field goal is scored and its not sudden death:
    overtime_df_ko <- overtime_df

    overtime_df_ko$yardline_100 <- with(
      overtime_df_ko,
      ifelse(
        game_year < 2016 |
          (game_year == 2016 & game_month < 4),
        80,
        75
      )
    )

    # Now first down:
    overtime_df_ko$down1 <- rep(1, nrow(overtime_df_ko))
    overtime_df_ko$down2 <- rep(0, nrow(overtime_df_ko))
    overtime_df_ko$down3 <- rep(0, nrow(overtime_df_ko))
    overtime_df_ko$down4 <- rep(0, nrow(overtime_df_ko))
    # 10 ydstogo:
    overtime_df_ko$ydstogo <- rep(10, nrow(overtime_df_ko))

    # Get the predictions from the EP model and calculate the necessary probability:
    if (nrow(overtime_df_ko) > 1) {
      overtime_df_ko_preds <- get_preds(overtime_df_ko)
    } else {
      overtime_df_ko_preds <- get_preds(overtime_df_ko)
    }

    overtime_df_ko_preds <- dplyr::mutate(
      overtime_df_ko_preds,
      Win_Back = .data$No_Score +
        .data$Opp_Field_Goal +
        .data$Opp_Safety +
        .data$Opp_Touchdown
    )

    # Calculate the two possible win probability types, Sudden Death and one Field Goal:
    overtime_df$Sudden_Death_WP <- overtime_df$fg_prob +
      overtime_df$td_prob +
      overtime_df$safety_prob
    overtime_df$One_FG_WP <- overtime_df$td_prob +
      (overtime_df$fg_prob * overtime_df_ko_preds$Win_Back)

    # Find all Pass Attempts that are also actual plays in overtime:
    overtime_pass_plays_i <- which(
      overtime_df$play_type == "pass" &
        !is.na(overtime_df$air_yards)
    )

    overtime_pass_df <- overtime_df[overtime_pass_plays_i, ]
    overtime_df_ko_preds_pass <- overtime_df_ko_preds[overtime_pass_plays_i, ]

    # Using the AirYards need to update the following:
    # - yardline_100
    # - half_seconds_remaining
    # - ydstogo
    # - down

    # First rename the old columns to update for calculating the EP from the air:
    overtime_pass_df <- dplyr::rename(
      overtime_pass_df,
      old_yrdline100 = "yardline_100",
      old_ydstogo = "ydstogo",
      old_TimeSecs_Remaining = "half_seconds_remaining",
      old_down = "down"
    )

    # Create an indicator column for the air yards failing to convert the first down:
    overtime_pass_df$Turnover_Ind <- ifelse(
      overtime_pass_df$old_down == 4 &
        overtime_pass_df$air_yards < overtime_pass_df$old_ydstogo,
      1,
      0
    )
    # Adjust the field position variables:
    overtime_pass_df$yardline_100 <- ifelse(
      overtime_pass_df$Turnover_Ind == 0,
      overtime_pass_df$old_yrdline100 - overtime_pass_df$air_yards,
      100 - (overtime_pass_df$old_yrdline100 - overtime_pass_df$air_yards)
    )

    overtime_pass_df$ydstogo <- ifelse(
      overtime_pass_df$air_yards >= overtime_pass_df$old_ydstogo |
        overtime_pass_df$Turnover_Ind == 1,
      10,
      overtime_pass_df$old_ydstogo - overtime_pass_df$air_yards
    )

    overtime_pass_df$down <- ifelse(
      overtime_pass_df$air_yards >= overtime_pass_df$old_ydstogo |
        overtime_pass_df$Turnover_Ind == 1,
      1,
      as.numeric(overtime_pass_df$old_down) + 1
    )

    # Adjust the time with the average incomplete pass time:
    overtime_pass_df$half_seconds_remaining <- overtime_pass_df$old_TimeSecs_Remaining -
      5.704673

    overtime_pass_df <- overtime_pass_df |>
      dplyr::mutate(
        down1 = dplyr::if_else(.data$down == 1, 1, 0),
        down2 = dplyr::if_else(.data$down == 2, 1, 0),
        down3 = dplyr::if_else(.data$down == 3, 1, 0),
        down4 = dplyr::if_else(.data$down == 4, 1, 0)
      )

    # Get the predictions from the EP model and calculate the necessary probability:
    if (nrow(overtime_df_ko) > 1) {
      overtime_pass_data_preds <- get_preds(overtime_pass_df)
    } else {
      overtime_pass_data_preds <- get_preds(overtime_pass_df)
    }

    # For the turnover plays flip the scoring probabilities:
    overtime_pass_data_preds <- dplyr::mutate(
      overtime_pass_data_preds,
      old_Opp_Field_Goal = .data$Opp_Field_Goal,
      old_Opp_Safety = .data$Opp_Safety,
      old_Opp_Touchdown = .data$Opp_Touchdown,
      old_Field_Goal = .data$Field_Goal,
      old_Safety = .data$Safety,
      old_Touchdown = .data$Touchdown
    )
    overtime_pass_data_preds$Opp_Field_Goal <- ifelse(
      overtime_pass_df$Turnover_Ind == 1,
      overtime_pass_data_preds$old_Field_Goal,
      overtime_pass_data_preds$Opp_Field_Goal
    )
    overtime_pass_data_preds$Opp_Safety <- ifelse(
      overtime_pass_df$Turnover_Ind == 1,
      overtime_pass_data_preds$old_Safety,
      overtime_pass_data_preds$Opp_Safety
    )
    overtime_pass_data_preds$Opp_Touchdown <- ifelse(
      overtime_pass_df$Turnover_Ind == 1,
      overtime_pass_data_preds$old_Touchdown,
      overtime_pass_data_preds$Opp_Touchdown
    )
    overtime_pass_data_preds$Field_Goal <- ifelse(
      overtime_pass_df$Turnover_Ind == 1,
      overtime_pass_data_preds$old_Opp_Field_Goal,
      overtime_pass_data_preds$Field_Goal
    )
    overtime_pass_data_preds$Safety <- ifelse(
      overtime_pass_df$Turnover_Ind == 1,
      overtime_pass_data_preds$old_Opp_Safety,
      overtime_pass_data_preds$Safety
    )
    overtime_pass_data_preds$Touchdown <- ifelse(
      overtime_pass_df$Turnover_Ind == 1,
      overtime_pass_data_preds$old_Opp_Touchdown,
      overtime_pass_data_preds$Touchdown
    )

    # Calculate the two possible win probability types, Sudden Death and one Field Goal:
    pass_overtime_df$Sudden_Death_airWP <- with(
      overtime_pass_data_preds,
      Field_Goal + Touchdown + Safety
    )
    pass_overtime_df$One_FG_airWP <- overtime_pass_data_preds$Touchdown +
      (overtime_pass_data_preds$Field_Goal * overtime_df_ko_preds_pass$Win_Back)

    # Decide which win probability to use:
    pass_overtime_df$airWP <- ifelse(
      overtime_pass_df$game_year >= 2012 &
        (overtime_pass_df$Drive_Diff == 0 |
          (overtime_pass_df$Drive_Diff == 1 &
            overtime_pass_df$One_FG_Game == 1)),
      pass_overtime_df$One_FG_airWP,
      pass_overtime_df$Sudden_Death_airWP
    )

    # For the plays that have TimeSecs_Remaining 0 or less, set airWP to 0:
    pass_overtime_df$airWP[which(
      overtime_pass_df$half_seconds_remaining <= 0
    )] <- 0

    # Calculate the airWPA and yacWPA:
    pass_overtime_df <- dplyr::mutate(
      pass_overtime_df,
      airWPA = .data$airWP - .data$wp,
      yacWPA = .data$wpa - .data$airWPA
    )

    # If the play is a two-point conversion then change the airWPA to NA since
    # no air yards are provided:
    pass_overtime_df$airWPA <- with(
      pass_overtime_df,
      ifelse(two_point_attempt == 1, NA, airWPA)
    )
    pass_overtime_df$yacWPA <- with(
      pass_overtime_df,
      ifelse(two_point_attempt == 1, NA, yacWPA)
    )

    pass_overtime_df <- pass_pbp_data[pass_overtime_i, ]

    # Now update the overtime rows in the original pass_pbp_data for airWPA and yacWPA:
    pass_pbp_data$airWPA[pass_overtime_i] <- pass_overtime_df$airWPA
    pass_pbp_data$yacWPA[pass_overtime_i] <- pass_overtime_df$yacWPA
  }

  # if Yards after catch is 0 make yacWPA set to 0:
  pass_pbp_data$yacWPA <- ifelse(
    pass_pbp_data$penalty == 0 &
      pass_pbp_data$yards_after_catch == 0 &
      pass_pbp_data$complete_pass == 1,
    0,
    pass_pbp_data$yacWPA
  )
  # if Yards after catch is 0 make airWPA set to WPA:
  pass_pbp_data$airWPA <- ifelse(
    pass_pbp_data$penalty == 0 &
      pass_pbp_data$yards_after_catch == 0 &
      pass_pbp_data$complete_pass == 1,
    pass_pbp_data$wpa,
    pass_pbp_data$airWPA
  )

  # Now add airWPA and yacWPA to the original dataset:
  pbp_data$airWPA <- NA
  pbp_data$yacWPA <- NA
  pbp_data$airWPA[pass_plays_i] <- pass_pbp_data$airWPA
  pbp_data$yacWPA[pass_plays_i] <- pass_pbp_data$yacWPA

  # Now change the names to be the right style, calculate the completion form
  # of the variables, as well as the cumulative totals and return:
  pbp_data |>
    dplyr::rename(air_wpa = "airWPA", yac_wpa = "yacWPA") |>
    dplyr::group_by(.data$game_id) |>
    dplyr::mutate(
      comp_air_wpa = dplyr::if_else(.data$complete_pass == 1, .data$air_wpa, 0),
      comp_yac_wpa = dplyr::if_else(.data$complete_pass == 1, .data$yac_wpa, 0),
      home_team_comp_air_wpa = dplyr::if_else(
        .data$posteam == .data$home_team,
        .data$comp_air_wpa,
        -.data$comp_air_wpa
      ),
      away_team_comp_air_wpa = dplyr::if_else(
        .data$posteam == .data$away_team,
        .data$comp_air_wpa,
        -.data$comp_air_wpa
      ),
      home_team_comp_yac_wpa = dplyr::if_else(
        .data$posteam == .data$home_team,
        .data$comp_yac_wpa,
        -.data$comp_yac_wpa
      ),
      away_team_comp_yac_wpa = dplyr::if_else(
        .data$posteam == .data$away_team,
        .data$comp_yac_wpa,
        -.data$comp_yac_wpa
      ),
      home_team_comp_air_wpa = dplyr::if_else(
        is.na(.data$home_team_comp_air_wpa),
        0,
        .data$home_team_comp_air_wpa
      ),
      away_team_comp_air_wpa = dplyr::if_else(
        is.na(.data$away_team_comp_air_wpa),
        0,
        .data$away_team_comp_air_wpa
      ),
      home_team_comp_yac_wpa = dplyr::if_else(
        is.na(.data$home_team_comp_yac_wpa),
        0,
        .data$home_team_comp_yac_wpa
      ),
      away_team_comp_yac_wpa = dplyr::if_else(
        is.na(.data$away_team_comp_yac_wpa),
        0,
        .data$away_team_comp_yac_wpa
      ),
      total_home_comp_air_wpa = cumsum(.data$home_team_comp_air_wpa),
      total_away_comp_air_wpa = cumsum(.data$away_team_comp_air_wpa),
      total_home_comp_yac_wpa = cumsum(.data$home_team_comp_yac_wpa),
      total_away_comp_yac_wpa = cumsum(.data$away_team_comp_yac_wpa),
      # Same but for raw - not just completions:
      home_team_raw_air_wpa = dplyr::if_else(
        .data$posteam == .data$home_team,
        .data$air_wpa,
        -.data$air_wpa
      ),
      away_team_raw_air_wpa = dplyr::if_else(
        .data$posteam == .data$away_team,
        .data$air_wpa,
        -.data$air_wpa
      ),
      home_team_raw_yac_wpa = dplyr::if_else(
        .data$posteam == .data$home_team,
        .data$yac_wpa,
        -.data$yac_wpa
      ),
      away_team_raw_yac_wpa = dplyr::if_else(
        .data$posteam == .data$away_team,
        .data$yac_wpa,
        -.data$yac_wpa
      ),
      home_team_raw_air_wpa = dplyr::if_else(
        is.na(.data$home_team_raw_air_wpa),
        0,
        .data$home_team_raw_air_wpa
      ),
      away_team_raw_air_wpa = dplyr::if_else(
        is.na(.data$away_team_raw_air_wpa),
        0,
        .data$away_team_raw_air_wpa
      ),
      home_team_raw_yac_wpa = dplyr::if_else(
        is.na(.data$home_team_raw_yac_wpa),
        0,
        .data$home_team_raw_yac_wpa
      ),
      away_team_raw_yac_wpa = dplyr::if_else(
        is.na(.data$away_team_raw_yac_wpa),
        0,
        .data$away_team_raw_yac_wpa
      ),
      total_home_raw_air_wpa = cumsum(.data$home_team_raw_air_wpa),
      total_away_raw_air_wpa = cumsum(.data$away_team_raw_air_wpa),
      total_home_raw_yac_wpa = cumsum(.data$home_team_raw_yac_wpa),
      total_away_raw_yac_wpa = cumsum(.data$away_team_raw_yac_wpa)
    ) |>
    dplyr::ungroup()
}
```

### add_ep_variables (lines 267–804) — the totals computed here feed the consolidated column list below

```r
add_ep_variables <- function(pbp_data) {
  #testing
  #pbp_data <- g

  #this function is below
  base_ep_preds <- get_preds(pbp_data)

  # ----------------------------------------------------------------------------
  # ---- special case: deal with FG attempts
  # Now make another dataset that to get the EP probabilities from a missed FG:
  missed_fg_data <- pbp_data
  # Subtract 5.065401 from TimeSecs:
  missed_fg_data$half_seconds_remaining <- missed_fg_data$half_seconds_remaining -
    5.065401

  # Correct the yrdline100:
  missed_fg_data$yardline_100 <- 100 - (missed_fg_data$yardline_100 + 8)
  # Now first down:
  missed_fg_data$down1 <- rep(1, nrow(pbp_data))
  missed_fg_data$down2 <- rep(0, nrow(pbp_data))
  missed_fg_data$down3 <- rep(0, nrow(pbp_data))
  missed_fg_data$down4 <- rep(0, nrow(pbp_data))
  # 10 ydstogo:
  missed_fg_data$ydstogo <- rep(10, nrow(pbp_data))

  # Get the new predicted probabilites:
  if (nrow(missed_fg_data) > 1) {
    missed_fg_ep_preds <- get_preds(missed_fg_data)
  } else {
    missed_fg_ep_preds <- get_preds(missed_fg_data)
  }

  # Find the rows where TimeSecs_Remaining became 0 or negative and make all the probs equal to 0:
  end_game_i <- which(missed_fg_data$half_seconds_remaining <= 0)
  missed_fg_ep_preds[end_game_i, ] <- rep(0, ncol(missed_fg_ep_preds))

  # if the half ends, no one scored
  missed_fg_ep_preds[end_game_i, "No_Score"] <- 1

  # Get the probability of making the field goal:
  make_fg_prob <- as.numeric(mgcv::predict.bam(
    fastrmodels::fg_model,
    newdata = pbp_data,
    type = "response"
  ))

  # Multiply each value of the missed_fg_ep_preds by the 1 - make_fg_prob
  missed_fg_ep_preds <- missed_fg_ep_preds * (1 - make_fg_prob)
  # Find the FG attempts:
  fg_attempt_i <- which(pbp_data$play_type == "field_goal")

  # Now update the probabilities for the FG attempts (also includes Opp_Field_Goal probability from missed_fg_ep_preds)
  base_ep_preds[fg_attempt_i, "Field_Goal"] <- make_fg_prob[fg_attempt_i] +
    missed_fg_ep_preds[fg_attempt_i, "Opp_Field_Goal"]
  # Update the other columns based on the opposite possession:
  base_ep_preds[fg_attempt_i, "Touchdown"] <- missed_fg_ep_preds[
    fg_attempt_i,
    "Opp_Touchdown"
  ]
  base_ep_preds[fg_attempt_i, "Opp_Field_Goal"] <- missed_fg_ep_preds[
    fg_attempt_i,
    "Field_Goal"
  ]
  base_ep_preds[fg_attempt_i, "Opp_Touchdown"] <- missed_fg_ep_preds[
    fg_attempt_i,
    "Touchdown"
  ]
  base_ep_preds[fg_attempt_i, "Safety"] <- missed_fg_ep_preds[
    fg_attempt_i,
    "Opp_Safety"
  ]
  base_ep_preds[fg_attempt_i, "Opp_Safety"] <- missed_fg_ep_preds[
    fg_attempt_i,
    "Safety"
  ]
  base_ep_preds[fg_attempt_i, "No_Score"] <- missed_fg_ep_preds[
    fg_attempt_i,
    "No_Score"
  ]

  # ----------------------------------------------------------------------------------
  # ---- special case: deal with kickoffs
  # Calculate the EP for receiving a touchback (from the point of view for recieving team)
  # and update the columns for Kickoff plays:
  kickoff_data <- pbp_data

  # Change the yard line to be 80 for 2009-2015 and 75 otherwise
  # (accounting for the fact that Jan 2016 is in the 2015 season:
  kickoff_data$yardline_100 <- with(kickoff_data, ifelse(season < 2016, 80, 75))
  # Now first down:
  kickoff_data$down1 <- rep(1, nrow(pbp_data))
  kickoff_data$down2 <- rep(0, nrow(pbp_data))
  kickoff_data$down3 <- rep(0, nrow(pbp_data))
  kickoff_data$down4 <- rep(0, nrow(pbp_data))
  # 10 ydstogo:
  kickoff_data$ydstogo <- rep(10, nrow(pbp_data))

  # Get the new predicted probabilites:
  kickoff_preds <- get_preds(kickoff_data)

  # Find the kickoffs:
  kickoff_i <- which(
    pbp_data$play_type == "kickoff" | pbp_data$kickoff_attempt == 1
  )

  # Now update the probabilities:
  base_ep_preds[kickoff_i, "Field_Goal"] <- kickoff_preds[
    kickoff_i,
    "Field_Goal"
  ]
  base_ep_preds[kickoff_i, "Touchdown"] <- kickoff_preds[kickoff_i, "Touchdown"]
  base_ep_preds[kickoff_i, "Opp_Field_Goal"] <- kickoff_preds[
    kickoff_i,
    "Opp_Field_Goal"
  ]
  base_ep_preds[kickoff_i, "Opp_Touchdown"] <- kickoff_preds[
    kickoff_i,
    "Opp_Touchdown"
  ]
  base_ep_preds[kickoff_i, "Safety"] <- kickoff_preds[kickoff_i, "Safety"]
  base_ep_preds[kickoff_i, "Opp_Safety"] <- kickoff_preds[
    kickoff_i,
    "Opp_Safety"
  ]
  base_ep_preds[kickoff_i, "No_Score"] <- kickoff_preds[kickoff_i, "No_Score"]

  # ----------------------------------------------------------------------------------
  # Insert probabilities of 0 for everything but No_Score for QB Kneels that
  # occur on the possession team's side of the field:
  # Find these QB Kneels:
  qb_kneels_i <- which(
    pbp_data$play_type == "qb_kneel" & pbp_data$yardline_100 > 50
  )

  # Now update the probabilities:
  base_ep_preds[qb_kneels_i, "Field_Goal"] <- 0
  base_ep_preds[qb_kneels_i, "Touchdown"] <- 0
  base_ep_preds[qb_kneels_i, "Opp_Field_Goal"] <- 0
  base_ep_preds[qb_kneels_i, "Opp_Touchdown"] <- 0
  base_ep_preds[qb_kneels_i, "Safety"] <- 0
  base_ep_preds[qb_kneels_i, "Opp_Safety"] <- 0
  base_ep_preds[qb_kneels_i, "No_Score"] <- 1

  # ----------------------------------------------------------------------------------
  # Create two new columns, ExPoint_Prob and TwoPoint_Prob, for the PAT events:
  base_ep_preds$ExPoint_Prob <- 0
  base_ep_preds$TwoPoint_Prob <- 0

  # Find the indices for these types of plays:
  extrapoint_i <- which(
    (pbp_data$play_type == "extra_point" |
      pbp_data$play_type_nfl == "XP_KICK") &
      (is.na(pbp_data$play_type_nfl) | pbp_data$play_type_nfl != "PAT2")
  )
  twopoint_i <- which(pbp_data$two_point_attempt == 1)

  #new: special case for PAT or kickoff with penalty
  #for inserting NAs
  st_penalty_i_1 <- which(
    # pat: prior play was TD or PAT or Timeout and next play is PAT and this play isn't a td and it's not a regular down
    (pbp_data$touchdown == 0 &
      is.na(pbp_data$down) &
      (dplyr::lag(pbp_data$touchdown) == 1 |
        dplyr::lag(pbp_data$play_type_nfl) == "XP_KICK" |
        dplyr::lag(pbp_data$timeout) == 1) &
      (dplyr::lead(pbp_data$two_point_attempt) == 1 |
        dplyr::lead(pbp_data$extra_point_attempt) == 1 |
        dplyr::lead(pbp_data$play_type_nfl) == "XP_KICK")) |
      #kickoff: prior play was PAT and next play is kickoff
      ((dplyr::lag(pbp_data$two_point_attempt) == 1 |
        dplyr::lag(pbp_data$extra_point_attempt) == 1) &
        dplyr::lead(pbp_data$kickoff_attempt == 1))
  )

  st_penalty_i_2 <- which(
    is.na(dplyr::lead(pbp_data$down)) &
      # has a key term in desc
      (((stringr::str_detect(pbp_data$desc, 'Kick formation') &
        is.na(pbp_data$down) &
        pbp_data$play_type == 'no_play') |
        (stringr::str_detect(pbp_data$desc, 'Pass formation') &
          is.na(pbp_data$down) &
          pbp_data$play_type == 'no_play') |
        (stringr::str_detect(pbp_data$desc, 'kicks onside') &
          is.na(pbp_data$down) &
          pbp_data$play_type == 'no_play') |
        (stringr::str_detect(pbp_data$desc, 'Offside on Free Kick') &
          is.na(pbp_data$down) &
          pbp_data$play_type == 'no_play') |
        (stringr::str_detect(pbp_data$desc, 'TWO-POINT CONVERSION')) &
          # down is NA and play type no play and next play isn't a kickoff
          is.na(pbp_data$down) &
          pbp_data$play_type == 'no_play' &
          dplyr::lead(pbp_data$kickoff_attempt) == 0))
  )

  # Assign the make_fg_probs of the extra-point PATs:
  base_ep_preds$ExPoint_Prob[extrapoint_i] <- make_fg_prob[extrapoint_i]

  # Assign the TwoPoint_Prob with the historical success rate:
  base_ep_preds$TwoPoint_Prob[twopoint_i] <- 0.4735

  # ----------------------------------------------------------------------------------
  # Insert NAs for timeouts and end of play rows:
  missing_i <- which(
    (pbp_data$timeout == 1 &
      pbp_data$play_type == "no_play" &
      !stringr::str_detect(pbp_data$desc, ' pass ') &
      !stringr::str_detect(pbp_data$desc, ' sacked ') &
      !stringr::str_detect(pbp_data$desc, ' scramble ') &
      !stringr::str_detect(pbp_data$desc, ' punts ') &
      !stringr::str_detect(pbp_data$desc, ' up the middle ') &
      !stringr::str_detect(pbp_data$desc, ' left end ') &
      !stringr::str_detect(pbp_data$desc, ' left guard ') &
      !stringr::str_detect(pbp_data$desc, ' left tackle ') &
      !stringr::str_detect(pbp_data$desc, ' right end ') &
      !stringr::str_detect(pbp_data$desc, ' right guard ') &
      !stringr::str_detect(pbp_data$desc, ' right tackle ')) |
      is.na(pbp_data$play_type)
  )

  # Now update the probabilities for missing and PATs:
  base_ep_preds$Field_Goal[c(
    missing_i,
    extrapoint_i,
    twopoint_i,
    st_penalty_i_1,
    st_penalty_i_2
  )] <- 0
  base_ep_preds$Touchdown[c(
    missing_i,
    extrapoint_i,
    twopoint_i,
    st_penalty_i_1,
    st_penalty_i_2
  )] <- 0
  base_ep_preds$Opp_Field_Goal[c(
    missing_i,
    extrapoint_i,
    twopoint_i,
    st_penalty_i_1,
    st_penalty_i_2
  )] <- 0
  base_ep_preds$Opp_Touchdown[c(
    missing_i,
    extrapoint_i,
    twopoint_i,
    st_penalty_i_1,
    st_penalty_i_2
  )] <- 0
  base_ep_preds$Safety[c(
    missing_i,
    extrapoint_i,
    twopoint_i,
    st_penalty_i_1,
    st_penalty_i_2
  )] <- 0
  base_ep_preds$Opp_Safety[c(
    missing_i,
    extrapoint_i,
    twopoint_i,
    st_penalty_i_1,
    st_penalty_i_2
  )] <- 0
  base_ep_preds$No_Score[c(
    missing_i,
    extrapoint_i,
    twopoint_i,
    st_penalty_i_1,
    st_penalty_i_2
  )] <- 0

  # Rename the events to all have _Prob at the end of them:
  base_ep_preds <- dplyr::rename(
    base_ep_preds,
    Field_Goal_Prob = "Field_Goal",
    Touchdown_Prob = "Touchdown",
    Opp_Field_Goal_Prob = "Opp_Field_Goal",
    Opp_Touchdown_Prob = "Opp_Touchdown",
    Safety_Prob = "Safety",
    Opp_Safety_Prob = "Opp_Safety",
    No_Score_Prob = "No_Score"
  )

  # Join them together:
  pbp_data <- cbind(pbp_data, base_ep_preds)

  # Calculate the ExpPts:
  pbp_data_ep <- dplyr::mutate(
    pbp_data,
    ExpPts = (0 * .data$No_Score_Prob) +
      (-3 * .data$Opp_Field_Goal_Prob) +
      (-2 * .data$Opp_Safety_Prob) +
      (-7 * .data$Opp_Touchdown_Prob) +
      (3 * .data$Field_Goal_Prob) +
      (2 * .data$Safety_Prob) +
      (7 * .data$Touchdown_Prob) +
      (1 * .data$ExPoint_Prob) +
      (2 * .data$TwoPoint_Prob)
  )

  #just going to set these to NA bc we have no way of calculating EPA for them
  if (length(st_penalty_i_1) > 0) {
    pbp_data_ep$ExpPts[st_penalty_i_1] <- NA_real_
  }

  if (length(st_penalty_i_2) > 0) {
    pbp_data_ep$ExpPts[st_penalty_i_2] <- NA_real_
  }

  pbp_data_ep$ExpPts[missing_i] <- NA_real_

  #################################################################
  # Calculate EPA:

  ### Adding Expected Points Added (EPA) column

  # Create multiple types of EPA columns
  # for each of the possible cases,
  # grouping by GameID (will then just use
  # an ifelse statement to decide which one
  # to use as the final EPA):
  pbp_data_ep |>
    dplyr::group_by(.data$game_id) |>
    dplyr::mutate(
      # Now conditionally assign the EPA, first for possession team
      # touchdowns:
      ep = .data$ExpPts,
      tmp_posteam = .data$posteam
    ) |>
    tidyr::fill(
      .data$ep,
      .direction = "up"
    ) |>
    tidyr::fill(
      .data$tmp_posteam,
      .direction = "up"
    ) |>
    dplyr::mutate(
      # get epa for non-scoring plays
      home_ep = dplyr::if_else(
        .data$tmp_posteam == .data$home_team,
        .data$ep,
        -.data$ep
      ),
      home_epa = dplyr::lead(.data$home_ep) - .data$home_ep,
      epa = dplyr::if_else(
        .data$tmp_posteam == .data$home_team,
        .data$home_epa,
        -.data$home_epa
      ),

      # td
      epa = dplyr::if_else(
        !is.na(.data$td_team),
        dplyr::if_else(
          .data$td_team == .data$posteam,
          7 - .data$ep,
          -7 - .data$ep
        ),
        .data$epa
      ),
      # Offense field goal:
      epa = dplyr::if_else(
        is.na(.data$td_team) & .data$field_goal_made == 1,
        3 - .data$ep,
        .data$epa,
        missing = .data$epa
      ),
      # Offense extra-point:
      epa = dplyr::if_else(
        is.na(.data$td_team) &
          .data$field_goal_made == 0 &
          .data$extra_point_good == 1,
        1 - .data$ep,
        .data$epa,
        missing = .data$epa
      ),
      # Offense two-point conversion:
      epa = dplyr::if_else(
        is.na(.data$td_team) &
          .data$field_goal_made == 0 &
          .data$extra_point_good == 0 &
          (.data$two_point_rush_good == 1 |
            .data$two_point_pass_good == 1 |
            .data$two_point_pass_reception_good == 1),
        2 - .data$ep,
        .data$epa,
        missing = .data$epa
      ),
      # Failed PAT (both 1 and 2):
      epa = dplyr::if_else(
        is.na(.data$td_team) &
          .data$field_goal_made == 0 &
          .data$extra_point_good == 0 &
          ((.data$extra_point_failed == 1 |
            .data$extra_point_blocked == 1 |
            .data$extra_point_aborted == 1) |
            (.data$two_point_rush_failed == 1 |
              .data$two_point_pass_failed == 1 |
              .data$two_point_pass_reception_failed == 1)),
        0 - .data$ep,
        .data$epa,
        missing = .data$epa
      ),
      # Opponent scores defensive 2 point:
      epa = dplyr::if_else(
        .data$defensive_two_point_conv == 1,
        -2 - .data$ep,
        .data$epa,
        missing = .data$epa
      ),
      # Safety:
      epa = dplyr::case_when(
        !is.na(.data$safety_team) & .data$safety_team == .data$posteam ~ 2 -
          .data$ep,
        !is.na(.data$safety_team) & .data$safety_team == .data$defteam ~ -2 -
          .data$ep,
        TRUE ~ .data$epa
      )
    ) |>
    # Now rename each of the expected points columns to match the style of
    # the updated code:
    dplyr::rename(
      no_score_prob = "No_Score_Prob",
      opp_fg_prob = "Opp_Field_Goal_Prob",
      opp_safety_prob = "Opp_Safety_Prob",
      opp_td_prob = "Opp_Touchdown_Prob",
      fg_prob = "Field_Goal_Prob",
      safety_prob = "Safety_Prob",
      td_prob = "Touchdown_Prob",
      extra_point_prob = "ExPoint_Prob",
      two_point_conversion_prob = "TwoPoint_Prob"
    ) |>
    # Create columns with cumulative epa totals for both teams:
    dplyr::mutate(
      # helper for end of game
      end_game = ifelse(
        stringr::str_detect(tolower(.data$desc), "(end of game)|(end game)"),
        1,
        0
      ),

      # Change epa for plays occurring at end of half with no scoring
      # plays to be just the difference between 0 and starting ep:
      epa = dplyr::if_else(
        ((.data$qtr == 2 &
          (dplyr::lead(.data$qtr) == 3 |
            dplyr::lead(.data$desc) == "END QUARTER 2")) |
          (.data$qtr == 4 &
            (dplyr::lead(.data$qtr) == 5 |
              dplyr::lead(.data$desc) == "END QUARTER 4" |
              dplyr::lead(.data$end_game) == 1))) &
          .data$sp == 0 &
          !is.na(.data$play_type),
        0 - .data$ep,
        .data$epa
      ),
      # last play of OT
      epa = dplyr::if_else(
        .data$qtr > 4 & dplyr::lead(.data$end_game) == 1 & .data$sp == 0,
        0 - .data$ep,
        .data$epa
      ),
      epa = dplyr::if_else(.data$desc == "END QUARTER 2", NA_real_, .data$epa),
      epa = dplyr::if_else(.data$end_game == 1, NA_real_, .data$epa),
      ep = dplyr::if_else(.data$desc == "END QUARTER 2", NA_real_, .data$ep),
      ep = dplyr::if_else(.data$end_game == 1, NA_real_, .data$ep),
      home_team_epa = dplyr::if_else(
        .data$posteam == .data$home_team,
        .data$epa,
        -.data$epa
      ),
      away_team_epa = dplyr::if_else(
        .data$posteam == .data$away_team,
        .data$epa,
        -.data$epa
      ),
      home_team_epa = dplyr::if_else(
        is.na(.data$home_team_epa),
        0,
        .data$home_team_epa
      ),
      away_team_epa = dplyr::if_else(
        is.na(.data$away_team_epa),
        0,
        .data$away_team_epa
      ),
      total_home_epa = cumsum(.data$home_team_epa),
      total_away_epa = cumsum(.data$away_team_epa),
      # Same thing but separating passing and rushing:
      home_team_rush_epa = dplyr::if_else(
        .data$play_type == "run",
        .data$home_team_epa,
        0
      ),
      away_team_rush_epa = dplyr::if_else(
        .data$play_type == "run",
        .data$away_team_epa,
        0
      ),
      home_team_rush_epa = dplyr::if_else(
        is.na(.data$home_team_rush_epa),
        0,
        .data$home_team_rush_epa
      ),
      away_team_rush_epa = dplyr::if_else(
        is.na(.data$away_team_rush_epa),
        0,
        .data$away_team_rush_epa
      ),
      total_home_rush_epa = cumsum(.data$home_team_rush_epa),
      total_away_rush_epa = cumsum(.data$away_team_rush_epa),
      home_team_pass_epa = dplyr::if_else(
        .data$play_type == "pass",
        .data$home_team_epa,
        0
      ),
      away_team_pass_epa = dplyr::if_else(
        .data$play_type == "pass",
        .data$away_team_epa,
        0
      ),
      home_team_pass_epa = dplyr::if_else(
        is.na(.data$home_team_pass_epa),
        0,
        .data$home_team_pass_epa
      ),
      away_team_pass_epa = dplyr::if_else(
        is.na(.data$away_team_pass_epa),
        0,
        .data$away_team_pass_epa
      ),
      total_home_pass_epa = cumsum(.data$home_team_pass_epa),
      total_away_pass_epa = cumsum(.data$away_team_pass_epa)
    ) |>
    dplyr::ungroup()
}
```

### prepare_wp_data (lines 219–262) — required precursor to add_wp_variables

```r
prepare_wp_data <- function(pbp) {
  if (any(is.na(pbp$spread_line))) {
    broken_games <- pbp |>
      dplyr::filter(is.na(.data$spread_line)) |>
      dplyr::pull(.data$game_id) |>
      unique() |>
      sort()
    cli::cli_alert_danger(
      "The following game{?s} {?is/are} missing valid spread lines: {.val {broken_games}}."
    )
    cli::cli_alert_warning(
      "nflfastR will manually set the spread for the home team to {.val 1.5} points!"
    )
    cli::cli_alert_warning(
      "If you see this, please reach out to the package maintainers {.url https://github.com/nflverse/nflfastR/issues}"
    )
    pbp$spread_line[is.na(pbp$spread_line)] <- 1.5
  }

  pbp <- pbp |>
    dplyr::group_by(.data$game_id) |>
    dplyr::mutate(
      receive_2h_ko = dplyr::if_else(
        .data$qtr <= 2 &
          .data$posteam == dplyr::first(stats::na.omit(.data$defteam)),
        1,
        0
      )
    ) |>
    dplyr::ungroup() |>
    dplyr::mutate(
      posteam_spread = dplyr::if_else(
        .data$home == 1,
        .data$spread_line,
        -1 * .data$spread_line
      ),
      elapsed_share = (3600 - .data$game_seconds_remaining) / 3600,
      spread_time = .data$posteam_spread * exp(-4 * .data$elapsed_share),
      Diff_Time_Ratio = .data$score_differential /
        (exp(-4 * .data$elapsed_share))
    )

  return(pbp)
}
```

### add_wp_variables (lines 809–1327)

```r
add_wp_variables <- function(pbp_data) {
  #testing only
  # pbp_data <- g

  # Initialize the df to store predicted win probability
  OffWinProb <- rep(NA_real_, nrow(pbp_data))
  OffWinProb_spread <- rep(NA_real_, nrow(pbp_data))

  pbp_data <- pbp_data |>
    prepare_wp_data()

  # First check if there's any overtime plays:
  if (any(pbp_data$qtr > 4)) {
    # Find the rows that are overtime:
    overtime_i <- which(pbp_data$qtr > 4)

    # Separate the dataset into regular_df and overtime_df:
    overtime_df <- pbp_data[overtime_i, ]

    # Separate routine for overtime:

    # Create a column that is just the first drive of overtime repeated:
    overtime_df$First_Drive <- rep(
      min(overtime_df$drive, na.rm = TRUE),
      nrow(overtime_df)
    )

    # Calculate the difference in drive number
    overtime_df <- dplyr::mutate(
      overtime_df,
      Drive_Diff = .data$drive - .data$First_Drive
    )

    # Create an indicator column that means the posteam is losing by 3 and
    # its the second drive of overtime:
    overtime_df$One_FG_Game <- ifelse(
      overtime_df$score_differential == -3 &
        overtime_df$Drive_Diff == 1,
      1,
      0
    )

    # Now create a copy of the dataset to then make the EP predictions for when
    # a field goal is scored and its not sudden death:
    overtime_df_ko <- overtime_df

    overtime_df_ko$yrdline100 <- with(
      overtime_df_ko,
      ifelse(
        game_year < 2016 |
          (game_year == 2016 & game_month < 4),
        80,
        75
      )
    )

    # Now first down:
    overtime_df_ko$down1 <- rep(1, nrow(overtime_df_ko))
    overtime_df_ko$down2 <- rep(0, nrow(overtime_df_ko))
    overtime_df_ko$down3 <- rep(0, nrow(overtime_df_ko))
    overtime_df_ko$down4 <- rep(0, nrow(overtime_df_ko))
    # 10 ydstogo:
    overtime_df_ko$ydstogo <- rep(10, nrow(overtime_df_ko))

    # Get the predictions from the EP model and calculate the necessary probability:
    overtime_df_ko_preds <- get_preds(overtime_df_ko)

    overtime_df_ko_preds <- dplyr::mutate(
      overtime_df_ko_preds,
      Win_Back = .data$No_Score +
        .data$Opp_Field_Goal +
        .data$Opp_Safety +
        .data$Opp_Touchdown
    )

    # Calculate the two possible win probability types, Sudden Death and one Field Goal:
    overtime_df$Sudden_Death_WP <- overtime_df$fg_prob +
      overtime_df$td_prob +
      overtime_df$safety_prob
    overtime_df$One_FG_WP <- overtime_df$td_prob +
      (overtime_df$fg_prob * overtime_df_ko_preds$Win_Back)

    # Decide which win probability to use:
    OffWinProb[overtime_i] <- ifelse(
      overtime_df$game_year >= 2012 &
        (overtime_df$Drive_Diff == 0 |
          (overtime_df$Drive_Diff == 1 & overtime_df$One_FG_Game == 1)),
      overtime_df$One_FG_WP,
      overtime_df$Sudden_Death_WP
    )
    OffWinProb_spread[overtime_i] <- OffWinProb[overtime_i]
  }

  #regulation plays
  regular_i <- which(pbp_data$qtr <= 4)

  # df of just the regulation plays:
  regular_df <- pbp_data[regular_i, ]

  # do predictions for the regular df
  OffWinProb[regular_i] <- get_preds_wp(regular_df)
  OffWinProb_spread[regular_i] <- get_preds_wp_spread(regular_df)

  ## set to NA WP for plays down is missing
  # for kickoffs and PATs, these will get overwritten by the fixes after this

  down_na <- which(is.na(pbp_data$down))
  OffWinProb[down_na] <- NA_real_
  OffWinProb_spread[down_na] <- NA_real_

  ## start PAT fix

  make_pat_prob <- as.numeric(
    mgcv::predict.bam(
      fastrmodels::fg_model,
      newdata = pbp_data |>
        mutate(
          yardline_100 = ifelse(.data$season >= 2015, 15, 3)
        ),
      type = "response"
    )
  )

  # plays with 1 point PAT attempts
  pat_i <- which(
    (pbp_data$kickoff_attempt == 0 &
      !(stringr::str_detect(pbp_data$desc, 'Onside Kick')) &
      (stringr::str_detect(pbp_data$desc, 'Kick formation')) &
      is.na(pbp_data$down)) |
      # or has PAT indicators
      stringr::str_detect(pbp_data$desc, 'extra point') |
      !is.na(pbp_data$extra_point_result)
  )

  # plays with 2 point PAT attempts
  two_pt_i <- which(
    (pbp_data$kickoff_attempt == 0 &
      !(stringr::str_detect(pbp_data$desc, 'Onside Kick')) &
      (stringr::str_detect(pbp_data$desc, 'Pass formation')) &
      is.na(pbp_data$down)) |
      # or has PAT indicators
      stringr::str_detect(pbp_data$desc, 'TWO-POINT CONVERSION ATTEMPT') |
      !is.na(pbp_data$two_point_conv_result)
  )

  # some rare 2 point PAT attempts have duplicated matches in 1 point PAT attempts
  # so we remove them in the next line
  pat_i <- pat_i[!pat_i %in% two_pt_i]

  # make df of post-PAT plays
  pat_data <- pbp_data |>
    dplyr::mutate(
      # swap timeouts
      to_pos = .data$posteam_timeouts_remaining,
      to_def = .data$defteam_timeouts_remaining,
      posteam_timeouts_remaining = .data$to_def,
      defteam_timeouts_remaining = .data$to_pos,
      # swap score
      score_differential = -.data$score_differential,
      # 1st and 10
      down = 1,
      ydstogo = 10,
      # flip receive_2h_ko var
      receive_2h_ko = case_when(
        .data$qtr <= 2 & .data$receive_2h_ko == 0 ~ 1,
        .data$qtr <= 2 & .data$receive_2h_ko == 1 ~ 0,
        TRUE ~ .data$receive_2h_ko
      ),
      # switch posteam
      posteam = if_else(
        .data$home_team == .data$posteam,
        .data$away_team,
        .data$home_team
      ),
      yardline_100 = 75
    ) |>
    dplyr::mutate(
      home = case_when(
        .data$home == 0 ~ 1,
        .data$home == 1 ~ 0
      ),
      posteam_spread = dplyr::if_else(
        .data$home == 1,
        .data$spread_line,
        -1 * .data$spread_line
      ),
      elapsed_share = (3600 - .data$game_seconds_remaining) / 3600,
      spread_time = .data$posteam_spread * exp(-4 * .data$elapsed_share)
    )

  ## start with spread version
  # get pat if 0, 1, or 2
  pat_0 <- get_preds_wp_spread(pat_data |> add_esdtr())
  pat_1 <- get_preds_wp_spread(
    pat_data |>
      dplyr::mutate(score_differential = .data$score_differential - 1) |>
      add_esdtr()
  )
  pat_2 <- get_preds_wp_spread(
    pat_data |>
      dplyr::mutate(score_differential = .data$score_differential - 2) |>
      add_esdtr()
  )

  # Using nflscrapR version of 2pt make prob on 2nd line here
  pat_go_for_1 <- 1 - (make_pat_prob * pat_1 + (1 - make_pat_prob) * pat_0)
  pat_go_for_2 <- 1 - (0.4735 * pat_2 + (1 - 0.4735) * pat_0)

  OffWinProb_spread[two_pt_i] <- pat_go_for_2[two_pt_i]
  OffWinProb_spread[pat_i] <- pat_go_for_1[pat_i]

  ## repeat for non-spread version
  # get pat if 0, 1, or 2
  pat_0 <- get_preds_wp(pat_data |> add_esdtr())
  pat_1 <- get_preds_wp(
    pat_data |>
      dplyr::mutate(score_differential = .data$score_differential - 1) |>
      add_esdtr()
  )
  pat_2 <- get_preds_wp(
    pat_data |>
      dplyr::mutate(score_differential = .data$score_differential - 2) |>
      add_esdtr()
  )

  # Using nflscrapR version of 2pt make prob on 2nd line here
  pat_go_for_1 <- 1 - (make_pat_prob * pat_1 + (1 - make_pat_prob) * pat_0)
  pat_go_for_2 <- 1 - (0.4735 * pat_2 + (1 - 0.4735) * pat_0)

  OffWinProb[two_pt_i] <- pat_go_for_2[two_pt_i]
  OffWinProb[pat_i] <- pat_go_for_1[pat_i]

  ## end PAT fix

  ## now we need to fix WP on kickoffs, which will be WP associated with touchback
  kickoff_data <- pbp_data

  # Change the yard line to be 80 for 2009-2015 and 75 otherwise
  kickoff_data$yardline_100 <- with(kickoff_data, ifelse(season < 2016, 80, 75))
  # Now first down:
  kickoff_data$down <- rep(1, nrow(pbp_data))
  kickoff_data$down1 <- rep(1, nrow(pbp_data))
  kickoff_data$down2 <- rep(0, nrow(pbp_data))
  kickoff_data$down3 <- rep(0, nrow(pbp_data))
  kickoff_data$down4 <- rep(0, nrow(pbp_data))
  # 10 ydstogo:
  kickoff_data$ydstogo <- rep(10, nrow(pbp_data))

  # Get the new predicted probabilites:
  kickoff_preds <- get_preds_wp(kickoff_data)
  kickoff_preds_spread <- get_preds_wp_spread(kickoff_data)

  # Find the kickoffs in regulation:
  kickoff_i <- which(
    (pbp_data$play_type == "kickoff" | pbp_data$kickoff_attempt == 1) &
      pbp_data$qtr <= 4
  )

  # Now update the probabilities:
  OffWinProb[kickoff_i] <- kickoff_preds[kickoff_i]
  OffWinProb_spread[kickoff_i] <- kickoff_preds_spread[kickoff_i]

  ## end fix for kickoffs

  # Now create the win probability columns and return:
  pbp_data <- pbp_data |>
    dplyr::mutate(
      wp = OffWinProb,
      vegas_wp = OffWinProb_spread,
      # for figuring out posteam on NA posteam lines
      tmp_posteam = .data$posteam
    ) |>
    tidyr::fill(
      .data$wp,
      .direction = "up"
    ) |>
    tidyr::fill(
      .data$vegas_wp,
      .direction = "up"
    ) |>
    tidyr::fill(
      .data$tmp_posteam,
      .direction = "up"
    ) |>
    dplyr::group_by(.data$game_id) |>
    dplyr::mutate(
      #add columns for home WP
      home_wp = dplyr::if_else(
        .data$tmp_posteam == .data$home_team,
        .data$wp,
        1 - .data$wp
      ),
      vegas_home_wp = dplyr::if_else(
        .data$tmp_posteam == .data$home_team,
        .data$vegas_wp,
        1 - .data$vegas_wp
      ),

      # convenience to mark end of game
      end_game = ifelse(
        stringr::str_detect(tolower(.data$desc), "(end of game)|(end game)"),
        1,
        0
      ),

      # convenience for marking home win prob on last line
      final_value = dplyr::case_when(
        .data$home_score > .data$away_score ~ 1,
        .data$away_score > .data$home_score ~ 0,
        .data$home_score == .data$away_score ~ .5
      ),

      #make 1 or 0 the final win prob
      vegas_home_wp = dplyr::if_else(
        .data$end_game == 1,
        .data$final_value,
        .data$vegas_home_wp
      ),

      # can we make this and the above into a function? feels like a lot of repitition
      home_wp = dplyr::if_else(
        .data$end_game == 1,
        .data$final_value,
        .data$home_wp
      ),

      away_wp = 1 - .data$home_wp,

      # make wp of posteam on last line NA because there's no posteam
      vegas_wp = dplyr::if_else(
        .data$end_game == 1,
        NA_real_,
        .data$vegas_wp
      ),

      wp = dplyr::if_else(
        .data$end_game == 1,
        NA_real_,
        .data$wp
      ),

      def_wp = 1 - .data$wp,

      # make wpa
      vegas_home_wpa = dplyr::lead(.data$vegas_home_wp) - .data$vegas_home_wp,
      vegas_wpa = dplyr::if_else(
        .data$tmp_posteam == .data$home_team,
        .data$vegas_home_wpa,
        -.data$vegas_home_wpa
      ),
      vegas_wpa = dplyr::if_else(
        stringr::str_detect(
          tolower(.data$desc),
          "( kneels )|(end of game)|(end game)"
        ),
        NA_real_,
        .data$vegas_wpa
      ),

      # home wpa isn't saved but needed for next line
      home_wpa = dplyr::lead(.data$home_wp) - .data$home_wp,
      wpa = dplyr::if_else(
        .data$tmp_posteam == .data$home_team,
        .data$home_wpa,
        -.data$home_wpa
      ),
      wpa = dplyr::if_else(
        stringr::str_detect(
          tolower(.data$desc),
          "( kneels )|(end of game)|(end game)"
        ),
        NA_real_,
        .data$wpa
      )
    ) |>
    dplyr::ungroup()

  # Home and Away post:

  pbp_data$home_wp_post <- ifelse(
    pbp_data$posteam == pbp_data$home_team,
    pbp_data$home_wp + pbp_data$wpa,
    pbp_data$home_wp - pbp_data$wpa
  )
  pbp_data$away_wp_post <- ifelse(
    pbp_data$posteam == pbp_data$away_team,
    pbp_data$away_wp + pbp_data$wpa,
    pbp_data$away_wp - pbp_data$wpa
  )

  # If next thing is end of game, and post score differential is tied because it's
  # overtime then make both the home_wp_post and away_wp_post equal to 0:
  pbp_data <- pbp_data |>
    dplyr::mutate(
      home_wp_post = dplyr::if_else(
        .data$qtr == 5 &
          stringr::str_detect(
            tolower(dplyr::lead(.data$desc)),
            "(end of game)|(end game)"
          ) &
          .data$score_differential_post == 0,
        0,
        .data$home_wp_post
      ),
      away_wp_post = dplyr::if_else(
        .data$qtr == 5 &
          stringr::str_detect(
            tolower(dplyr::lead(.data$desc)),
            "(end of game)|(end game)"
          ) &
          .data$score_differential_post == 0,
        0,
        .data$away_wp_post
      )
    )

  # For plays with playtype of End of Game, use the previous play's WP_post columns
  # as the pre and post, since those are already set to be 1 and 0:

  pbp_data$home_wp_post <- with(
    pbp_data,
    ifelse(
      stringr::str_detect(tolower(desc), "(end of game)|(end game)"),
      dplyr::lag(home_wp_post),
      ifelse(
        dplyr::lag(play_type) == "no_play" & play_type == "no_play",
        dplyr::lag(home_wp_post),
        home_wp_post
      )
    )
  )

  pbp_data$away_wp_post <- with(
    pbp_data,
    ifelse(
      stringr::str_detect(tolower(desc), "(end of game)|(end game)"),
      dplyr::lag(away_wp_post),
      ifelse(
        dplyr::lag(play_type) == "no_play" & play_type == "no_play",
        dplyr::lag(away_wp_post),
        away_wp_post
      )
    )
  )

  # Now drop the unnecessary columns, rename variables back, and return:
  pbp_data |>
    dplyr::group_by(.data$game_id) |>
    dplyr::mutate(
      # Generate columns to keep track of cumulative rushing and
      # passing WPA values:
      home_team_wpa = dplyr::if_else(
        .data$posteam == .data$home_team,
        .data$wpa,
        -.data$wpa
      ),
      away_team_wpa = dplyr::if_else(
        .data$posteam == .data$away_team,
        .data$wpa,
        -.data$wpa
      ),
      home_team_wpa = dplyr::if_else(
        is.na(.data$home_team_wpa),
        0,
        .data$home_team_wpa
      ),
      away_team_wpa = dplyr::if_else(
        is.na(.data$away_team_wpa),
        0,
        .data$away_team_wpa
      ),
      # Same thing but separating passing and rushing:
      home_team_rush_wpa = dplyr::if_else(
        .data$play_type == "run",
        .data$home_team_wpa,
        0
      ),
      away_team_rush_wpa = dplyr::if_else(
        .data$play_type == "run",
        .data$away_team_wpa,
        0
      ),
      home_team_rush_wpa = dplyr::if_else(
        is.na(.data$home_team_rush_wpa),
        0,
        .data$home_team_rush_wpa
      ),
      away_team_rush_wpa = dplyr::if_else(
        is.na(.data$away_team_rush_wpa),
        0,
        .data$away_team_rush_wpa
      ),
      total_home_rush_wpa = cumsum(.data$home_team_rush_wpa),
      total_away_rush_wpa = cumsum(.data$away_team_rush_wpa),
      home_team_pass_wpa = dplyr::if_else(
        .data$play_type == "pass",
        .data$home_team_wpa,
        0
      ),
      away_team_pass_wpa = dplyr::if_else(
        .data$play_type == "pass",
        .data$away_team_wpa,
        0
      ),
      home_team_pass_wpa = dplyr::if_else(
        is.na(.data$home_team_pass_wpa),
        0,
        .data$home_team_pass_wpa
      ),
      away_team_pass_wpa = dplyr::if_else(
        is.na(.data$away_team_pass_wpa),
        0,
        .data$away_team_pass_wpa
      ),
      total_home_pass_wpa = cumsum(.data$home_team_pass_wpa),
      total_away_pass_wpa = cumsum(.data$away_team_pass_wpa)
    ) |>
    dplyr::ungroup()
}

# helper function to get expected score diff to time ratio
# needed after flipping teams in WP for getting PAT WP
add_esdtr <- function(data) {
  data |>
    dplyr::mutate(
      Diff_Time_Ratio = .data$score_differential /
        (exp(-4 * .data$elapsed_share))
    )
}
```

### §5 consolidated output-columns list

**air/yac EPA family** (added by `add_air_yac_ep_variables`, all `Float64`,
`NA` when `add_air_yac_ep` short-circuits on all-NA `air_yards`):
`air_epa`, `yac_epa` (raw per-play; `air_epa` is the airEPA/airEP formula
above with 3 special cases: TD-if-air-yards-crossed-goal-line, `-2-ep` if
air-yards overshoot own endzone by >99, and the `Turnover_Ind` sign-flip on
4th-down incompletions that don't reach the sticks; `yac_epa = epa -
air_epa`. Both forced to `0`/`epa` respectively when
`yards_after_catch == 0 & complete_pass == 1 & penalty == 0`), `comp_air_epa`,
`comp_yac_epa` (= `air_epa`/`yac_epa` gated to `complete_pass==1`, else `0`),
`home_team_comp_air_epa`, `away_team_comp_air_epa`, `home_team_comp_yac_epa`,
`away_team_comp_yac_epa` (signed by `posteam==home/away`, `NA→0`),
`total_home_comp_air_epa`, `total_away_comp_air_epa`,
`total_home_comp_yac_epa`, `total_away_comp_yac_epa` (`cumsum` **within
`game_id`**), and the raw (non-completion-gated) mirror set:
`home_team_raw_air_epa`, `away_team_raw_air_epa`, `home_team_raw_yac_epa`,
`away_team_raw_yac_epa`, `total_home_raw_air_epa`, `total_away_raw_air_epa`,
`total_home_raw_yac_epa`, `total_away_raw_yac_epa`.

**air/yac WPA family** (added by `add_air_yac_wp_variables`, mirrors the EPA
family exactly, `airWP` computed via the WP model on an air-yards-projected
down/distance/field-position with a `Turnover_Ind` flip for failed
4th-down-and-air-yards, `airWPA = airWP - wp`, `yacWPA = wpa - airWPA`, with a
dedicated OT branch that redoes the Sudden-Death/One-FG WP blend used in
`add_wp_variables` on the air-yards-projected state): `air_wpa`, `yac_wpa`,
`comp_air_wpa`, `comp_yac_wpa`, `home_team_comp_air_wpa`,
`away_team_comp_air_wpa`, `home_team_comp_yac_wpa`, `away_team_comp_yac_wpa`,
`total_home_comp_air_wpa`, `total_away_comp_air_wpa`,
`total_home_comp_yac_wpa`, `total_away_comp_yac_wpa`,
`home_team_raw_air_wpa`, `away_team_raw_air_wpa`, `home_team_raw_yac_wpa`,
`away_team_raw_yac_wpa`, `total_home_raw_air_wpa`, `total_away_raw_air_wpa`,
`total_home_raw_yac_wpa`, `total_away_raw_yac_wpa`.

**Every `total_home_*`/`total_away_*` running total in the EP/WP surface, with
its exact formula and source function:**

| Column | Formula | Grouping | Source |
|---|---|---|---|
| `total_home_epa` | `cumsum(home_team_epa)`, `home_team_epa = epa if posteam==home_team else -epa` (NA→0) | `game_id` | `add_ep_variables` L735–756 |
| `total_away_epa` | `cumsum(away_team_epa)`, `away_team_epa = epa if posteam==away_team else -epa` (NA→0) | `game_id` | `add_ep_variables` L740–756 |
| `total_home_rush_epa` | `cumsum(home_team_rush_epa)`, `= home_team_epa if play_type=="run" else 0` | `game_id` | `add_ep_variables` L758–779 |
| `total_away_rush_epa` | `cumsum(away_team_rush_epa)`, `= away_team_epa if play_type=="run" else 0` | `game_id` | `add_ep_variables` L763–779 |
| `total_home_pass_epa` | `cumsum(home_team_pass_epa)`, `= home_team_epa if play_type=="pass" else 0` | `game_id` | `add_ep_variables` L780–801 |
| `total_away_pass_epa` | `cumsum(away_team_pass_epa)`, `= away_team_epa if play_type=="pass" else 0` | `game_id` | `add_ep_variables` L785–801 |
| `total_home_rush_wpa` | `cumsum(home_team_rush_wpa)`, `= home_team_wpa if play_type=="run" else 0` | `game_id` | `add_wp_variables` L1281–1302 |
| `total_away_rush_wpa` | `cumsum(away_team_rush_wpa)` | `game_id` | `add_wp_variables` L1286–1302 |
| `total_home_pass_wpa` | `cumsum(home_team_pass_wpa)`, `= home_team_wpa if play_type=="pass" else 0` | `game_id` | `add_wp_variables` L1303–1324 |
| `total_away_pass_wpa` | `cumsum(away_team_pass_wpa)` | `game_id` | `add_wp_variables` L1308–1324 |
| `total_home_comp_air_epa` / `total_away_comp_air_epa` / `total_home_comp_yac_epa` / `total_away_comp_yac_epa` | `cumsum` of the completion-gated signed air/yac epa | `game_id` | `add_air_yac_ep_variables` L1533–1536 |
| `total_home_raw_air_epa` / `total_away_raw_air_epa` / `total_home_raw_yac_epa` / `total_away_raw_yac_epa` | `cumsum` of the raw (ungated) signed air/yac epa | `game_id` | `add_air_yac_ep_variables` L1578–1581 |
| `total_home_comp_air_wpa` / `total_away_comp_air_wpa` / `total_home_comp_yac_wpa` / `total_away_comp_yac_wpa` | `cumsum` of the completion-gated signed air/yac wpa | `game_id` | `add_air_yac_wp_variables` L1985–1988 |
| `total_home_raw_air_wpa` / `total_away_raw_air_wpa` / `total_home_raw_yac_wpa` / `total_away_raw_yac_wpa` | `cumsum` of the raw (ungated) signed air/yac wpa | `game_id` | `add_air_yac_wp_variables` L2030–2033 |

**Port contract (whole §5)**:
- `ep`/`epa`/`wp`/`wpa`/`vegas_wp`/`vegas_wpa` are computed on the FULL
  concatenated multi-game frame but every `cumsum`/`lead`/`lag`/`fill` is
  `.over("game_id")` (or, for `home_wp_post`/`away_wp_post`, a row-wise
  `with()` that is NOT grouped — those two use plain `dplyr::lag`, which is
  safe only because the frame is pre-sorted by game then play order and the
  first row of each new game's `lag` reads across the game boundary but is
  immediately overwritten by the `end_game==1`/`GAME` row special-casing
  upstream; **a naive Python port must still explicitly boundary-guard this
  or shift-across-game-leak is possible** — see cross-cutting notes).
- `ep`/`ExpPts` for `st_penalty_i_1`/`st_penalty_i_2`/`missing_i` rows (STs
  penalty markers, timeouts as pseudo-plays) is set to `NA`, and `tidyr::fill
  (.direction = "up")` back-fills `ep`/`wp`/`tmp_posteam` from the next real
  play — port as a **backward fill grouped by `game_id`**, not a global fill.
- Depends on external models loaded via `load_model()`
  (`utils.R` L236–256): `fastrmodels::ep_model`, `fastrmodels::wp_model`,
  `fastrmodels::wp_model_spread`, `fastrmodels::fg_model` (also an `mgcv::bam`
  GAM, not XGBoost — `add_ep_variables`/`add_wp_variables` call
  `mgcv::predict.bam(fastrmodels::fg_model, ...)` directly, not through
  `get_preds`). All four models are a **hard external data dependency**
  (`fastrmodels` R package) — the equivalent trained-model artifacts already
  live in sdv-py's `nfl/models/*.ubj` per this repo's CLAUDE.md (18-feature EP
  / 12-feature wp_spread / 11-feature wp_naive / 18-feature cp) plus a
  bundled `fg_model`; the *exact* feature order matters
  (`ep_model_select`/`wp_model_select`/`wp_spread_model_select`, lines
  151–218, are transcribed above verbatim as the required column order).
- Constant `0.4735` = hardcoded historical 2-point-conversion success rate,
  used identically in `add_ep_variables` (`TwoPoint_Prob`) and
  `add_wp_variables` (`pat_go_for_2` blend) — same literal both places, not a
  model output.
- Constant `5.065401` = average seconds elapsed on a missed-FG-then-return
  play (subtracted from `half_seconds_remaining` before scoring the
  "opponent gets it at spot of kick" EP). Constant `5.704673` = average
  seconds elapsed on an incomplete/complete pass (subtracted from
  `half_seconds_remaining`/`game_seconds_remaining` in both the air-yac EP
  and air-yac WP functions — same literal, reused).
- Kickoff touchback yardline substitution: `season < 2016 → 80`,
  `else → 75` in `add_ep_variables`/`add_wp_variables` (uses `season`); the
  OT branches instead gate on `game_year < 2016 | (game_year==2016 &
  game_month < 4)` — **a subtly different condition** (month-aware for OT
  because OT games always occur within the same season but the season-year
  boundary crosses Jan) — transcribe both conditions distinctly, don't
  collapse them.

## §6 helper_additional_functions.R :: clean_pbp (lines 51–447) + team_name_fn (lines 499–515)

```r
clean_pbp <- function(pbp, ...) {
  if (nrow(pbp) == 0) {
    user_message("Nothing to clean. Return passed data frame.", "info")
    r <- pbp
  } else {
    user_message("Cleaning up play-by-play...", "todo")

    # drop existing values of clean_pbp
    pbp <- pbp |> dplyr::select(-dplyr::any_of(drop.cols))

    r <- pbp |>
      dplyr::mutate(
        aborted_play = dplyr::if_else(
          stringr::str_detect(.data$desc, 'Aborted'),
          1,
          0
        ),
        #get rid of extraneous spaces that mess with player name finding
        #if there is a space or dash, and then a capital letter, and then a period, and then a space, take out the space
        desc = stringr::str_replace_all(
          .data$desc,
          "(((\\s)|(\\-))[A-Z]\\.)\\s+",
          "\\1"
        ),
        success = dplyr::if_else(
          is.na(.data$epa),
          NA_real_,
          dplyr::if_else(.data$epa > 0, 1, 0)
        ),
        passer = stringr::str_extract(
          .data$desc,
          glue::glue('{big_parser}{pass_finder}')
        ),
        passer_jersey_number = stringr::str_extract(
          stringr::str_extract(
            .data$desc,
            glue::glue('{number_parser}{big_parser}{pass_finder}')
          ),
          "[:digit:]*"
        ) |>
          as.integer(),
        rusher = stringr::str_extract(
          .data$desc,
          glue::glue('{big_parser}{rush_finder}')
        ),
        rusher_jersey_number = stringr::str_extract(
          stringr::str_extract(
            .data$desc,
            glue::glue('{number_parser}{big_parser}{rush_finder}')
          ),
          "[:digit:]*"
        ) |>
          as.integer(),
        #get rusher_player_name as a measure of last resort
        #finds things like aborted snaps and "F.Last to NYG 44."
        rusher = dplyr::if_else(
          is.na(.data$rusher) &
            is.na(.data$passer) &
            !is.na(.data$rusher_player_name),
          .data$rusher_player_name,
          .data$rusher
        ),
        receiver = stringr::str_extract(
          .data$desc,
          glue::glue('{receiver_finder}{big_parser}')
        ),
        receiver_jersey_number = stringr::str_extract(
          stringr::str_extract(
            .data$desc,
            glue::glue('{receiver_number}{big_parser}')
          ),
          "[:digit:]*"
        ) |>
          as.integer(),
        #overwrite all these weird plays messing with the parser
        receiver = dplyr::case_when(
          stringr::str_detect(.data$desc, glue::glue('{abnormal_play}')) &
            !is.na(.data$receiver_player_name) ~ .data$receiver_player_name,
          TRUE ~ .data$receiver
        ),
        rusher = dplyr::case_when(
          stringr::str_detect(.data$desc, glue::glue('{abnormal_play}')) &
            !is.na(.data$rusher_player_name) ~ .data$rusher_player_name,
          TRUE ~ .data$rusher
        ),
        passer = dplyr::case_when(
          stringr::str_detect(.data$desc, glue::glue('{abnormal_play}')) &
            !is.na(.data$passer_player_name) ~ .data$passer_player_name,
          TRUE ~ .data$passer
        ),
        # fix the plays where scramble was fixed using charting data from 1999 to 2005
        passer = dplyr::case_when(
          is.na(.data$passer) &
            .data$qb_scramble == 1 &
            !is.na(.data$rusher) &
            .data$season <= 2005 ~ .data$rusher,
          TRUE ~ .data$passer
        ),
        # finally, for rusher, if there was already a passer (eg from scramble), set rusher to NA
        rusher = dplyr::if_else(
          !is.na(.data$passer),
          NA_character_,
          .data$rusher
        ),
        # if no pass is thrown, there shouldn't be a receiver
        receiver = dplyr::if_else(
          stringr::str_detect(.data$desc, ' pass '),
          .data$receiver,
          NA_character_
        ),
        # if there's a pass, sack, or scramble, it's a pass play...
        pass = dplyr::if_else(
          stringr::str_detect(.data$desc, "( pass )|(sacked)|(scramble)") |
            .data$qb_scramble == 1,
          1,
          0
        ),
        # ...unless it says "backward(s) pass" or "lateral pass" and there's a rusher
        pass = dplyr::if_else(
          stringr::str_detect(
            stringr::str_to_lower(.data$desc),
            "(backward pass)|(backwards pass)|(lateral pass)"
          ) &
            !is.na(.data$rusher),
          0,
          .data$pass
        ),
        # and make sure there's no pass on a kickoff (sometimes there's forward pass on kickoff but that's not a pass play)
        pass = dplyr::case_when(
          .data$kickoff_attempt == 1 ~ 0,
          TRUE ~ .data$pass
        ),
        # in very rare cases, the pass logic can fail. We do a hard coded overwrite here because it's not worth the time
        # to overthink the logic to catch weird play descriptions.
        pass = fix_weird_pass_plays(.data$pass, .data$game_id, .data$play_id),
        #if there's a rusher and it wasn't a QB kneel or pass play, it's a run play
        rush = dplyr::if_else(
          !is.na(.data$rusher) & .data$qb_kneel == 0 & .data$pass == 0,
          1,
          0
        ),
        #fix some common QBs with inconsistent names
        passer = dplyr::case_when(
          passer == "Jos.Allen" ~ "J.Allen",
          passer == "Alex Smith" | passer == "Ale.Smith" ~ "A.Smith",
          passer == "Ryan" & .data$posteam == "ATL" ~ "M.Ryan",
          passer == "Tr.Brown" ~ "T.Brown",
          passer == "Sh.Hill" ~ "S.Hill",
          passer == "Matt.Moore" | passer == "Mat.Moore" ~ "M.Moore",
          passer == "Jo.Freeman" ~ "J.Freeman",
          passer == "G.Minshew" ~ "G.Minshew II",
          passer == "R.Griffin" ~ "R.Griffin III",
          passer == "Randel El" ~ "A.Randle El",
          passer == "Randle El" ~ "A.Randle El",
          season <= 2003 & passer == "Van Pelt" ~ "A.Van Pelt",
          season > 2003 & passer == "Van Pelt" ~ "B.Van Pelt",
          passer == "Dom.Davis" ~ "D.Davis",
          TRUE ~ .data$passer
        ),
        rusher = dplyr::case_when(
          rusher == "D.Johnson" &
            posteam == "HOU" &
            season == 2020 &
            rusher_jersey_number == 31 ~ "Da.Johnson",
          rusher == "D.Johnson" &
            posteam == "HOU" &
            season == 2020 &
            rusher_jersey_number == 25 ~ "Du.Johnson",
          rusher == "Jos.Allen" ~ "J.Allen",
          rusher == "Alex Smith" | rusher == "Ale.Smith" ~ "A.Smith",
          rusher == "Ryan" & .data$posteam == "ATL" ~ "M.Ryan",
          rusher == "Tr.Brown" ~ "T.Brown",
          rusher == "Sh.Hill" ~ "S.Hill",
          rusher == "Matt.Moore" | rusher == "Mat.Moore" ~ "M.Moore",
          rusher == "Jo.Freeman" ~ "J.Freeman",
          rusher == "G.Minshew" ~ "G.Minshew II",
          rusher == "R.Griffin" ~ "R.Griffin III",
          rusher == "Randel El" ~ "A.Randle El",
          rusher == "Randle El" ~ "A.Randle El",
          season <= 2003 & rusher == "Van Pelt" ~ "A.Van Pelt",
          season > 2003 & rusher == "Van Pelt" ~ "B.Van Pelt",
          rusher == "Dom.Davis" ~ "D.Davis",
          TRUE ~ rusher
        ),
        receiver = dplyr::case_when(
          receiver == "F.R" ~ "F.Jones",
          receiver_player_name == "D.Wells" &
            receiver_player_id == "00-0017421" ~ "D.Wells",
          receiver_player_name == "D.Hayes" &
            receiver_player_id == "00-0007144" ~ "D.Hayes",
          receiver_player_name == "DanielThomas" ~ "D.Thomas",
          receiver_player_name == "JulioJones" ~ "J.Jones",
          receiver_player_name == "Andre' Davis" ~ "A.Davis",
          receiver_player_name == "A.al-Jabbar" ~ "A.al-Jabbar",
          receiver_player_name == "A.St. Brown" ~ "A.St. Brown",
          TRUE ~ receiver
        ),
        first_down = dplyr::if_else(
          .data$first_down_rush == 1 |
            .data$first_down_pass == 1 |
            .data$first_down_penalty == 1,
          1,
          0
        ),
        # easy filter: play is 1 if a "special teams" play, or 0 otherwise
        # with thanks to Lee Sharpe for the code
        special = dplyr::if_else(
          .data$play_type %in%
            c("extra_point", "field_goal", "kickoff", "punt"),
          1,
          0
        ),
        # easy filter: play is 1 if a "normal" play (including penalties), or 0 otherwise
        # with thanks to Lee Sharpe for the code
        play = dplyr::if_else(
          !is.na(.data$epa) &
            !is.na(.data$posteam) &
            .data$desc != "*** play under review ***" &
            substr(.data$desc, 1, 8) != "Timeout " &
            .data$play_type %in% c("no_play", "pass", "run"),
          1,
          0
        )
      ) |>
      #standardize team names (eg Chargers are always LAC even when they were playing in SD)
      dplyr::mutate_at(
        dplyr::vars(
          "posteam",
          "defteam",
          "home_team",
          "away_team",
          "timeout_team",
          "td_team",
          "return_team",
          "penalty_team",
          "side_of_field",
          "forced_fumble_player_1_team",
          "forced_fumble_player_2_team",
          "solo_tackle_1_team",
          "solo_tackle_2_team",
          "assist_tackle_1_team",
          "assist_tackle_2_team",
          "assist_tackle_3_team",
          "assist_tackle_4_team",
          "tackle_with_assist_1_team",
          "tackle_with_assist_2_team",
          "fumbled_1_team",
          "fumbled_2_team",
          "fumble_recovery_1_team",
          "fumble_recovery_2_team",
          "yrdln",
          "end_yard_line",
          "drive_start_yard_line",
          "drive_end_yard_line"
        ),
        team_name_fn
      ) |>

      #Seb's stuff for fixing player ids
      dplyr::mutate(index = 1:dplyr::n()) |> # to re-sort after all the group_bys

      dplyr::group_by(.data$passer, .data$posteam, .data$season) |>
      dplyr::mutate(
        passer_id = dplyr::if_else(
          is.na(.data$passer),
          NA_character_,
          custom_mode(.data$passer_player_id)
        )
      ) |>

      dplyr::group_by(.data$passer_id) |>
      dplyr::mutate(
        passer = dplyr::if_else(
          is.na(.data$passer_id),
          NA_character_,
          custom_mode(.data$passer)
        )
      ) |>

      dplyr::group_by(.data$rusher, .data$posteam, .data$season) |>
      dplyr::mutate(
        rusher_id = dplyr::if_else(
          is.na(.data$rusher),
          NA_character_,
          custom_mode(.data$rusher_player_id)
        )
      ) |>

      dplyr::group_by(.data$rusher_id) |>
      dplyr::mutate(
        rusher = dplyr::if_else(
          is.na(.data$rusher_id),
          NA_character_,
          custom_mode(.data$rusher)
        )
      ) |>

      dplyr::group_by(.data$receiver, .data$posteam, .data$season) |>
      dplyr::mutate(
        receiver_id = dplyr::if_else(
          is.na(.data$receiver),
          NA_character_,
          custom_mode(.data$receiver_player_id)
        )
      ) |>

      dplyr::group_by(.data$receiver_id) |>
      dplyr::mutate(
        receiver = dplyr::if_else(
          is.na(.data$receiver_id),
          NA_character_,
          custom_mode(.data$receiver)
        )
      ) |>

      dplyr::ungroup() |>
      dplyr::mutate(
        # if there's an aborted snap and qb didn't get a pass off,
        # then charge it to whoever charged with the fumble
        # this has to go after all the custom_mode stuff or it gets messed up
        rusher = dplyr::if_else(
          .data$aborted_play == 1 &
            is.na(.data$passer) &
            !is.na(.data$fumbled_1_player_name),
          .data$fumbled_1_player_name,
          .data$rusher
        ),
        rusher_id = dplyr::if_else(
          .data$aborted_play == 1 &
            is.na(.data$passer) &
            !is.na(.data$fumbled_1_player_id),
          .data$fumbled_1_player_id,
          .data$rusher_id
        ),

        name = dplyr::if_else(!is.na(.data$passer), .data$passer, .data$rusher),
        jersey_number = dplyr::if_else(
          !is.na(.data$passer_jersey_number),
          .data$passer_jersey_number,
          .data$rusher_jersey_number
        ),
        id = dplyr::if_else(
          !is.na(.data$passer_id),
          .data$passer_id,
          .data$rusher_id
        )
      ) |>
      dplyr::arrange(.data$index) |>
      dplyr::select(-"index") |>
      # add action player
      dplyr::mutate(
        fantasy_player_name = case_when(
          !is.na(.data$rusher_player_name) ~ .data$rusher_player_name,
          is.na(.data$rusher_player_name) &
            !is.na(.data$receiver_player_name) ~ .data$receiver_player_name,
          TRUE ~ NA_character_
        ),
        fantasy_player_id = case_when(
          !is.na(.data$rusher_player_id) ~ .data$rusher_player_id,
          is.na(.data$rusher_player_id) &
            !is.na(.data$receiver_player_id) ~ .data$receiver_player_id,
          TRUE ~ NA_character_
        ),
        fantasy = case_when(
          !is.na(.data$rusher) ~ .data$rusher,
          is.na(.data$rusher) & !is.na(.data$receiver) ~ .data$receiver,
          .data$qb_scramble == 1 ~ .data$passer,
          TRUE ~ NA_character_
        ),
        fantasy_id = case_when(
          !is.na(.data$rusher_id) ~ .data$rusher_id,
          is.na(.data$rusher_id) &
            !is.na(.data$receiver_id) ~ .data$receiver_id,
          .data$qb_scramble == 1 ~ .data$passer_id,
          TRUE ~ NA_character_
        ),
        out_of_bounds = dplyr::if_else(
          stringr::str_detect(.data$desc, "(ran ob)|(pushed ob)|(sacked ob)"),
          1,
          0
        )
      ) |>
      dplyr::group_by(.data$game_id) |>
      dplyr::mutate(
        home_opening_kickoff = dplyr::if_else(
          .data$home_team == dplyr::first(stats::na.omit(.data$posteam)),
          1,
          0
        )
      ) |>
      dplyr::ungroup()
  }

  message_completed("Cleaning completed", ...)

  return(r)
}

#these things are used in clean_pbp() above

# look for First[period or space]Last[maybe - or ' in last][maybe more letters in last][maybe Jr. or II or IV]
big_parser <- "(?<=)[A-Z][A-z]*+(\\.|\\s)+[A-Z][A-z]*+\\'*\\-*[A-Z]*+[a-z]*+(\\s((Jr.)|(Sr.)|I{2,3})|(IV))?"
# maybe some spaces and letters, and then a rush direction unless they fumbled
rush_finder <- "(?=\\s*[a-z]*+\\s*((FUMBLES) | (left end)|(left tackle)|(left guard)|(up the middle)|(right guard)|(right tackle)|(right end)))"
# maybe some spaces and letters, and then pass / sack / scramble
pass_finder <- "(?=\\s*[a-z]*+\\s*(( pass)|(sack)|(scramble)))"
# to or for, maybe a jersey number and a dash
receiver_finder <- "(?<=((to)|(for))\\s[:digit:]{0,2}\\-{0,1})"
# weird play finder
abnormal_play <- "(Lateral)|(lateral)|(pitches to)|(Direct snap to)|(New quarterback for)|(Aborted)|(backwards pass)|(Pass back to)|(Flea-flicker)"
# look for 1-2 numbers before a dash
number_parser <- "((?<=)[:digit:]{1,2}(-))?"
# special case for receivers
receiver_number <- "(?<=((to)|(for))\\s)[:digit:]{0,2}\\-{0,1}"

# These columns are being generated by clean_pbp and the function tries to drop
# them in case it is being used on a pbp dataset where the columns already exist
drop.cols <- c(
  "success",
  "passer",
  "rusher",
  "receiver",
  "pass",
  "rush",
  "special",
  "first_down",
  "play",
  "passer_id",
  "rusher_id",
  "receiver_id",
  "name",
  "id",
  "passer_jersey_number",
  "rusher_jersey_number",
  "receiver_jersey_number",
  "jersey_number",
  "aborted_play",
  "fantasy",
  "fantasy_id",
  "fantasy_player_name",
  "fantasy_player_id",
  "out_of_bounds"
)

# fixes team names on columns with yard line
# example: 'SD 49' --> 'LAC 49'
# thanks to awgymer for the contribution:
# https://github.com/nflverse/nflfastR/issues/29#issuecomment-654592195
team_name_fn <- function(var) {
  stringr::str_replace_all(
    var,
    c(
      "JAC" = "JAX",
      "STL" = "LA",
      "SL" = "LA",
      "LAR" = "LA",
      "ARZ" = "ARI",
      "BLT" = "BAL",
      "CLV" = "CLE",
      "HST" = "HOU",
      "SD" = "LAC",
      "OAK" = "LV"
    )
  )
}
```

**Port contract**

- Output columns added/overwritten by `clean_pbp` (all listed in `drop.cols`,
  which the function pre-strips on entry so it's idempotent/re-runnable):
  `success` (Float — `NA` if `epa` NA, else `1.0`/`0.0` on `epa>0`), `passer`,
  `passer_jersey_number`, `rusher`, `rusher_jersey_number`, `receiver`,
  `receiver_jersey_number` (regex-extracted from `desc`, then patched via the
  hardcoded name-fix `case_when` blocks — **transcribe every row of those
  blocks verbatim**, they are a parity-critical hardcoded lookup, not
  illustrative), `pass`, `rush` (0/1 int — this is where "pass"/"rush" are
  actually defined; see §14 note below — NOT in
  `add_nflscrapr_mutations`), `first_down`, `special`, `play` (0/1 gate
  flags), `passer_id`, `rusher_id`, `receiver_id`, `name`, `jersey_number`,
  `id`, `aborted_play`, `fantasy`, `fantasy_id`, `fantasy_player_name`,
  `fantasy_player_id`, `out_of_bounds`, plus `home_opening_kickoff` (0/1,
  **not** in `drop.cols` — a pre-existing column of this name from an earlier
  run is NOT stripped before recompute, a latent idempotency gap worth
  flagging in the Python port's tests).
- Regex constants `big_parser`/`rush_finder`/`pass_finder`/`receiver_finder`/
  `abnormal_play`/`number_parser`/`receiver_number` are **lookbehind/lookahead
  heavy** (`(?<=...)`, `(?=...)`) — none of these compile against
  polars/Rust regex directly. Python port should use the `re`/`regex` module
  (which supports lookaround) rather than trying to force these through
  polars string ops; if a polars-native path is required, each lookaround
  must be rewritten as an explicit capture group + slice, mirroring the
  project's documented `(?i)prefix(?-i: NAMES)` workaround pattern for the
  no-lookaround case only — full lookbehind still requires the `regex`
  package or a two-step extract-then-filter.
- Player-ID resolution is a **per-name-per-team-per-season mode vote**:
  group by `(passer, posteam, season)` then `passer_id = custom_mode(passer_player_id)`
  (skipping `NA`), then **re-group by `passer_id`** giving `passer =
  custom_mode(passer)` (i.e. canonicalizes the *name string* back from the
  *id* mode, ironing out name-string variants that map to the same id). Same
  two-pass pattern independently for `rusher`/`rusher_id` and
  `receiver`/`receiver_id`. `custom_mode` (from `utils.R`) drops `NA` then
  returns the most frequent value (first-occurring on ties, via
  `which.max(tabulate(match(x, unique(x))))`). This is order-sensitive on
  ties — Python port should replicate first-seen-wins tie-breaking, not
  `pandas.Series.mode()` (which sorts and returns all ties) or
  `collections.Counter.most_common` (arbitrary/insertion-order tie behavior
  differs by Python version).
  - An `index = 1:n()` column is added purely to `arrange(index)` back to
    original row order after all the `group_by`/`ungroup` churn — a polars
    port should use a stable row index and re-sort at the end identically
    (or rely on `group_by(..., maintain_order=True)` + a final no-op if the
    grouping/ungrouping doesn't reorder — but do not assume order is
    preserved without verifying, since dplyr's `group_by`+`mutate` is
    documented to preserve original row order while polars' default is
    unordered unless `maintain_order=True`).
- `team_name_fn(var)` — trivial `str_replace_all` over a fixed named-vector
  map (`JAC→JAX, STL→LA, SL→LA, LAR→LA, ARZ→ARI, BLT→BAL, CLV→CLE, HST→HOU,
  SD→LAC, OAK→LV`), applied to the 26 team-name columns in the `mutate_at`
  block above and independently re-used inside `get_pbp_nfl`
  (`helper_scrape_nfl.R` line 168–173, applied to every character column) and
  inside `data-raw/build_scramble_fix.R`. **This map has no sysdata
  dependency — it is fully self-contained in the function body and
  transcribed complete above (10 entries).** Port as a single dict + one
  vectorized string-replace (careful: order matters if any key is a
  substring of another value — here it isn't, all replacements are disjoint
  3-letter codes).
- No external ID map / sysdata object is referenced directly by `clean_pbp`
  itself; the *decoding* of "new-style" 2022+ player IDs to GSIS format is a
  **separate** downstream step (`decode_player_ids()`,
  `helper_decode_player_ids.R`) that depends on `nflreadr::load_players()` (a
  released nflverse crosswalk table, columns used: `gsis_id`, `esb_id`) — not
  invoked by `clean_pbp` itself, but typically chained after it in
  `build_nflfastR_pbp()` (see cross-cutting pipeline order).

## §7 helper_add_series_data.R :: add_series_data (lines 13–98)

```r
## series =
##  starts at 1, each new first down increments, numbers shared across both teams
##  NA: kickoffs, extra point/two point conversion attempts, non-plays, no posteam
## series_success =
##  1: scored touchdown, gained enough yards for first down
##  0: everything else
add_series_data <- function(pbp) {
  out <-
    pbp |>
    dplyr::mutate(
      old_posteam = .data$posteam,
      posteam = dplyr::case_when(
        # on kickoffs the kicking team is the defteam but this should be swapped
        # in terms of this function if the kickoff is recovered
        .data$kickoff_attempt == 1 &
          (.data$own_kickoff_recovery == 1 |
            .data$fumble_lost == 1) ~ .data$defteam,
        # if a kickoff has to be replayed due to a penalty and is then recovered,
        # the prior (reversed) kickoff shouldn't be a new drive/series
        stringr::str_detect(.data$desc, kickoff_finder) &
          .data$own_kickoff_recovery == 0 &
          dplyr::lead(.data$own_kickoff_recovery == 1) ~ .data$defteam,
        TRUE ~ .data$posteam
      )
    ) |>
    dplyr::group_by(.data$game_id, .data$game_half) |>
    dplyr::mutate(
      row = 1:dplyr::n(),
      new_series = dplyr::if_else(
        # a new drive
        .data$fixed_drive != dplyr::lag(.data$fixed_drive) |
          # or a first down on the prior play except touchdown plays
          ((dplyr::lag(.data$first_down_rush) == 1 |
            dplyr::lag(.data$first_down_pass) == 1 |
            dplyr::lag(.data$first_down_penalty) == 1) &
            dplyr::lag(.data$touchdown) == 0) |
          # or the first play
          .data$row == 1,
        1,
        0
      ),
      new_series = dplyr::if_else(is.na(.data$new_series), 0, .data$new_series)
    ) |>
    # now compute series number with cumsum (for the calculation NA are being relaced with 0)
    dplyr::group_by(.data$game_id) |>
    dplyr::mutate(
      series = cumsum(.data$new_series),
      tmp_result = dplyr::case_when(
        (.data$first_down_penalty == 1 |
          .data$first_down_rush == 1 |
          .data$first_down_pass == 1) &
          touchdown == 0 ~ "First down",
        .data$touchdown == 1 & .data$posteam == .data$td_team ~ "Touchdown",
        .data$touchdown == 1 & .data$posteam != .data$td_team ~ "Opp touchdown",
        .data$field_goal_result == "made" ~ "Field goal",
        .data$field_goal_result %in%
          c("blocked", "missed") ~ "Missed field goal",
        .data$safety == 1 ~ "Safety",
        .data$play_type == "punt" | .data$punt_attempt == 1 ~ "Punt",
        .data$interception == 1 | .data$fumble_lost == 1 ~ "Turnover",
        .data$down == 4 &
          .data$yards_gained < .data$ydstogo &
          .data$play_type != "no_play" ~ "Turnover on downs",
        .data$qb_kneel == 1 ~ "QB kneel",
        stringr::str_detect(
          .data$desc,
          "(END QUARTER 2)|(END QUARTER 4)|(END GAME)"
        ) ~ "End of half"
      )
    ) |>
    dplyr::group_by(.data$game_id, .data$series) |>
    dplyr::mutate(
      series_result = dplyr::if_else(
        # if it's end of half, take the first thing we see
        dplyr::last(stats::na.omit(.data$tmp_result)) == "End of half",
        dplyr::first(stats::na.omit(.data$tmp_result)),
        # otherwise take the last
        dplyr::last(stats::na.omit(.data$tmp_result))
      ),
      series_success = dplyr::if_else(
        .data$series_result %in% c("Touchdown", "First down"),
        1,
        0
      )
    ) |>
    dplyr::ungroup() |>
    dplyr::mutate(posteam = .data$old_posteam) |>
    dplyr::select(-"row", -"tmp_result", -"new_series", -"old_posteam")

  user_message("added series variables", "done")
  return(out)
}
```

**Port contract**

- Output columns: `series` (Int, 1-based, increments on each new first down
  or new drive, **shared numbering across both teams within a game** — not
  reset per-team), `series_result` (Utf8 category — one of `"First down"`,
  `"Touchdown"`, `"Opp touchdown"`, `"Field goal"`, `"Missed field goal"`,
  `"Safety"`, `"Punt"`, `"Turnover"`, `"Turnover on downs"`, `"QB kneel"`,
  `"End of half"`, or `NA`), `series_success` (0/1 Int — `1` iff
  `series_result ∈ {"Touchdown", "First down"}`).
  - Per the header comment: `series` is `NA` on kickoffs, PAT/2pt attempts,
    non-plays, and rows with no `posteam` (this NA-ness comes from
    `fixed_drive`/`down`/etc. being `NA` on those rows upstream, propagating
    through `tmp_result`/`series_result`, not from an explicit `NA` branch
    here).
- **Grouping / ordering**: uses a locally-swapped `posteam` (kickoffs
  attributed to the *returning* team when recovered by them, or to the
  original kicking team when a penalty forces a kickoff re-do) purely to
  compute `new_series`/`series`, then restores the real `posteam` at the end
  (`old_posteam` round-trip) — this local swap must NOT leak into any other
  output column. `new_series` grouping is `(game_id, game_half)` (so the
  "first play of the half" rule via `row == 1` works per half); `series`
  itself (`cumsum(new_series)`) groups only by `game_id` (continuous
  numbering across both halves of a game). `series_result`/`series_success`
  group by `(game_id, series)`.
- `series_result` resolution when a series spans an end-of-half boundary:
  `dplyr::last(na.omit(tmp_result))` is checked first — if that's `"End of
  half"`, the series result is instead `dplyr::first(na.omit(tmp_result))`
  (i.e. use the FIRST non-NA in-series result, not "End of half" itself);
  otherwise use the LAST non-NA result. This exactly mirrors the
  `fixed_drive_result` resolution logic in §8 below — same pattern, same
  precedence.
- Depends on `kickoff_finder` (module-level regex constant defined in
  `helper_add_nflscrapr_mutations.R` line 756:
  `"(Offside on Free Kick)|(Delay of Kickoff)|(Onside Kick formation)|(kicks onside)|( kicks [:digit:]+ yards from)"`)
  and on `fixed_drive` already being present on the frame — i.e.
  `add_series_data` must run **after** `add_drive_results` in the pipeline
  (confirmed by `top-level_scraper.R`: `add_drive_results() |>
  add_series_data()`).

---

## §8 helper_add_fixed_drives.R :: add_drive_results (lines 11–176)

```r
## fixed_drive =
##  starts at 1, each new drive, numbers shared across both teams
## fixed_drive_result =
##  result of  given drive
add_drive_results <- function(d) {
  drive_df <- d |>
    dplyr::mutate(
      old_posteam = .data$posteam,
      posteam = dplyr::case_when(
        # on kickoffs the kicking team is the defteam but this should be swapped
        # in terms of this function if the kickoff is recovered
        .data$kickoff_attempt == 1 &
          (.data$own_kickoff_recovery == 1 |
            .data$fumble_lost == 1) ~ .data$defteam,
        # if a kickoff has to be replayed due to a penalty and is then recovered,
        # the prior (reversed) kickoff shouldn't be a new drive/series
        stringr::str_detect(.data$desc, kickoff_finder) &
          .data$own_kickoff_recovery == 0 &
          dplyr::lead(.data$own_kickoff_recovery == 1) ~ .data$defteam,
        TRUE ~ .data$posteam
      )
    ) |>
    dplyr::group_by(.data$game_id, .data$game_half) |>
    dplyr::mutate(
      row = 1:dplyr::n(),
      new_drive = dplyr::if_else(
        # change in posteam
        .data$posteam != dplyr::lag(.data$posteam) |
          # change in posteam in t-2 and na posteam in t-1
          (.data$posteam != dplyr::lag(.data$posteam, 2) &
            is.na(dplyr::lag(.data$posteam))) |
          # change in posteam in t-3 and na posteam in t-1 and t-2
          (.data$posteam != dplyr::lag(.data$posteam, 3) &
            is.na(dplyr::lag(.data$posteam, 2)) &
            is.na(dplyr::lag(.data$posteam))),
        1,
        0
      ),
      # PAT after defensive TD is not a new drive
      new_drive = dplyr::if_else(
        dplyr::lag(.data$touchdown == 1) &
          (dplyr::lag(.data$posteam) != dplyr::lag(.data$td_team)) &
          # this last part is needed because otherwise it was overwriting
          # the existing value of new_drive with NA on plays following timeouts
          !is.na(dplyr::lag(.data$posteam)),
        0,
        .data$new_drive
      ),
      # PAT after defensive TD is not a new drive even if a Timeout follows the TD
      new_drive = dplyr::if_else(
        dplyr::lag(stringr::str_detect(
          .data$desc,
          "(Timeout)|(Two-Minute Warning)"
        )) &
          dplyr::lag(.data$touchdown == 1, 2L) &
          (dplyr::lag(.data$posteam, 2L) != dplyr::lag(.data$td_team, 2L)),
        0,
        .data$new_drive,
        missing = .data$new_drive
      ),
      # PAT after defensive TD is not a new drive even if 2 Timeouts follow the TD
      new_drive = dplyr::if_else(
        dplyr::lag(stringr::str_detect(
          .data$desc,
          "(Timeout)|(Two-Minute Warning)"
        )) &
          dplyr::lag(
            stringr::str_detect(.data$desc, "(Timeout)|(Two-Minute Warning)"),
            2L
          ) &
          dplyr::lag(.data$touchdown == 1, 3L) &
          (dplyr::lag(.data$posteam, 3L) != dplyr::lag(.data$td_team, 3L)),
        0,
        .data$new_drive,
        missing = .data$new_drive
      ),
      # if same team has the ball as prior play, but prior play was a punt with lost fumble, it's a new drive
      # or if the prior play was a lost fumble or interception
      new_drive = dplyr::if_else(
        # this line is to prevent it from overwriting already-defined new drives with NA
        # when there's a timeout on prior line bc if_else is obnoxious like that
        (.data$new_drive != 1 | is.na(.data$new_drive)) &
          (
            # same team has ball after lost fumble on punt, fg, pass or rush
            (.data$posteam == dplyr::lag(.data$posteam) &
              dplyr::lag(.data$fumble_lost) == 1 &
              dplyr::lag(.data$play_type) %in%
                c("punt", "pass", "run", "field_goal") &
              # but not if the play resulted in a touchdown because otherwise the
              # following extra point or 2pt conversion will be new drives
              dplyr::lag(.data$touchdown) == 0) |

              # same team has ball after lost fumble on punt, fg, pass or rush 2 plays earlier with prior play missing posteam
              (is.na(dplyr::lag(.data$posteam)) &
                # posteam is same as posteam 2 plays ago
                .data$posteam == dplyr::lag(.data$posteam, 2) &
                # lost fumble 2 plays ago
                dplyr::lag(.data$fumble_lost, 2) == 1 &
                dplyr::lag(.data$play_type, 2) %in%
                  c("punt", "pass", "run", "field_goal") &
                # but not if the lost fumble 2 plays ago resulted in a touchdown because otherwise the
                # following extra point or 2pt conversion will be new drives
                dplyr::lag(.data$touchdown, 2) == 0)
          ),
        1,
        .data$new_drive
      ),
      # first observation of a half is also a new drive
      new_drive = dplyr::if_else(.data$row == 1, 1, .data$new_drive),

      # if you recovered an onside kick or muffed return, it's a new drive
      new_drive = dplyr::case_when(
        .data$play_type == "kickoff" &
          (.data$own_kickoff_recovery == 1 | .data$fumble_lost == 1) ~ 1,
        TRUE ~ .data$new_drive
      ),

      # if it's a kickoff and the prior play was a safety, it's a new drive
      new_drive = dplyr::case_when(
        # safety prior play
        .data$kickoff_attempt == 1 & dplyr::lag(.data$safety) == 1 ~ 1,
        # safety 2 plays ago and timeout on previous play
        .data$kickoff_attempt == 1 &
          dplyr::lag(.data$safety, 2) == 1 &
          (is.na(dplyr::lag(.data$play_type)) |
            dplyr::lag(.data$play_type) == "no_play") ~ 1,
        TRUE ~ .data$new_drive
      ),

      # if there's a missing, make it not a new drive (0)
      new_drive = dplyr::if_else(is.na(.data$new_drive), 0, .data$new_drive)
    ) |>
    dplyr::group_by(.data$game_id) |>
    dplyr::mutate(
      fixed_drive = cumsum(.data$new_drive),
      tmp_result = dplyr::case_when(
        .data$touchdown == 1 & .data$posteam == .data$td_team ~ "Touchdown",
        .data$touchdown == 1 & .data$posteam != .data$td_team ~ "Opp touchdown",
        .data$field_goal_result == "made" ~ "Field goal",
        .data$field_goal_result %in%
          c("blocked", "missed") ~ "Missed field goal",
        .data$safety == 1 ~ "Safety",
        .data$play_type == "punt" | .data$punt_attempt == 1 ~ "Punt",
        .data$interception == 1 | .data$fumble_lost == 1 ~ "Turnover",
        .data$down == 4 &
          .data$yards_gained < .data$ydstogo &
          .data$play_type != "no_play" ~ "Turnover on downs",
        stringr::str_detect(
          .data$desc,
          "(END QUARTER 2)|(END QUARTER 4)|(END GAME)"
        ) ~ "End of half"
      )
    ) |>
    dplyr::group_by(.data$game_id, .data$fixed_drive) |>
    dplyr::mutate(
      fixed_drive_result = dplyr::if_else(
        # if it's end of half, take the first thing we see
        dplyr::last(stats::na.omit(.data$tmp_result)) == "End of half",
        dplyr::first(stats::na.omit(.data$tmp_result)),
        # otherwise take the last
        dplyr::last(stats::na.omit(.data$tmp_result))
      )
    ) |>
    dplyr::ungroup() |>
    dplyr::mutate(posteam = .data$old_posteam) |>
    dplyr::select(-"row", -"new_drive", -"tmp_result", -"old_posteam")

  user_message("added fixed drive variables", "done")
  return(drive_df)
}
```

**Port contract**

- Output columns:
  - `fixed_drive` (Int, 1-based, `cumsum(new_drive)` **grouped by `game_id`
    only** — numbering is shared across both teams and both halves of a
    game).
  - `fixed_drive_result` (Utf8 category — `"Touchdown"`, `"Opp touchdown"`,
    `"Field goal"`, `"Missed field goal"`, `"Safety"`, `"Punt"`,
    `"Turnover"`, `"Turnover on downs"`, `"End of half"` collapsed to
    whatever the FIRST non-NA in-drive result was, or `NA`) — **note: no
    `"QB kneel"` category here** (unlike `series_result` in §7, which does
    have one); this is a genuine divergence between the drive-level and
    series-level result vocab, not an oversight — transcribe as-is.
- **`new_drive` is a 6-rule cascade, evaluated in this exact order** (each
  rule only overrides `new_drive` when its own condition is true; earlier
  `1`s are not clobbered back to `0` except by the final NA-cleanup step):
  1. Base possession-change detection: `posteam != lag(posteam)`, OR
     `posteam != lag(posteam, 2)` when `lag(posteam)` is `NA` (single
     no-posteam gap), OR `posteam != lag(posteam, 3)` when both `lag(1)` and
     `lag(2)` are `NA` (two-play no-posteam gap, e.g. two consecutive
     timeouts).
  2. PAT-after-defensive-TD exception (no gap): if the immediately prior
     play was a touchdown scored by the team NOT holding the ball
     (`lag(posteam) != lag(td_team)`) and `lag(posteam)` isn't `NA`, force
     `new_drive = 0` (the PAT following a defensive/return TD stays part of
     the same drive numbering, not a new one).
  3. Same exception with exactly 1 intervening Timeout/Two-Minute-Warning
     row (`lag(desc detects Timeout|Two-Minute Warning)` at lag 1, TD at lag
     2) → force `0`, using `missing = new_drive` so an NA lag doesn't
     clobber an already-set value.
  4. Same exception with exactly 2 intervening Timeout/2-min-warning rows
     (checked at lag 1 AND lag 2, TD at lag 3) → force `0`.
  5. Lost-fumble-recovered-by-same-team-eventually exception: if
     `new_drive` isn't already `1`, AND (same `posteam` as immediately prior
     play, prior play was a lost fumble on `punt|pass|run|field_goal`, and
     that prior play wasn't itself a touchdown) OR the 2-play-back mirror of
     that same condition (accounting for one intervening NA-posteam row) →
     force `1` (a lost fumble recovered by the SAME team that fumbled it
     several plays later, after the ball briefly changed hands, still
     counts as a new drive for that team).
  6. `row == 1` (first play of the half) → force `1`.
  7. Kickoff self-possession special case: `play_type == "kickoff"` AND
     (`own_kickoff_recovery == 1` OR `fumble_lost == 1`) → force `1`
     (recovering your own onside kick, or muffing/losing the return, always
     starts a new drive even though `posteam` didn't change under the local
     kickoff-swap rule above).
  8. Kickoff-after-safety special case: `kickoff_attempt == 1` AND (safety
     on the immediately prior play, OR safety 2 plays back with either a
     missing or `"no_play"` `play_type` on the play in between) → force `1`.
  9. Final NA cleanup: any remaining `NA` in `new_drive` → `0`.
  - All of rules 1–9 are grouped by `(game_id, game_half)` (so `lag()` never
    crosses a half boundary); `fixed_drive`/`fixed_drive_result` computation
    afterward re-groups to `(game_id)` / `(game_id, fixed_drive)`
    respectively.
- Same `posteam` local-swap-then-restore trick as §7 (kickoff recovered by
  receiving team, or kickoff replayed for penalty), same `kickoff_finder`
  regex dependency, same `old_posteam` round-trip — **this function and
  `add_series_data` independently duplicate the identical posteam-swap
  block**; a Python port should factor it into one shared helper used by
  both, provided the two call sites are kept behaviorally identical (they
  are, verbatim, in the R source).
- Pipeline order: `add_drive_results()` runs BEFORE `add_series_data()` (see
  `top-level_scraper.R`), and `add_series_data`'s `new_series` rule 1
  depends on `fixed_drive` already existing — confirmed dependency, not
  interchangeable order.

## §9 aggregate_game_stats_def.R :: calculate_player_stats_def (lines 67–738)

Full verbatim source (deprecated function, superseded by `calculate_stats()`,
but still the parity reference for the def-stats aggregation formulas):

```r
calculate_player_stats_def <- function(pbp, weekly = FALSE) {
  lifecycle::deprecate_warn(
    "5.0",
    "calculate_player_stats_def()",
    "calculate_stats()"
  )

  # need newer version of nflreadr to use load_players
  rlang::check_installed("nflreadr (>= 1.3.0)")

  # Prepare data ------------------------------------------------------------

  suppressMessages({
    # 1. for "normal" plays: get plays that count in official stats
    # we exclude special teams and 2pts here for now
    data <- pbp |>
      dplyr::filter(
        !is.na(.data$down),
        .data$play_type %in% c("pass", "qb_kneel", "qb_spike", "run")
      ) |>
      nflfastR::decode_player_ids()

    # 2. filter penalty plays for penalty stats
    penalty_data <- pbp |>
      dplyr::filter(.data$penalty == 1) |>
      nflfastR::decode_player_ids()
  })

  stype <- data |>
    dplyr::select("season", "week", "season_type") |>
    dplyr::distinct()

  # Tackling stats -----------------------------------------------------------

  tackle_vars <- c(
    "solo_tackle_1_player_id",
    "tackle_for_loss_1_player_id",
    "assist_tackle_1_player_id",
    "tackle_with_assist_1_player_id",
    "solo_tackle_2_player_id",
    "forced_fumble_player_1_player_id",
    "assist_tackle_2_player_id",
    "forced_fumble_player_2_player_id"
  )

  # get tackling stats
  tackle_df <- data |>
    dplyr::select("season", "week", "defteam", dplyr::any_of(tackle_vars)) |>
    tidyr::pivot_longer(
      cols = dplyr::any_of(tackle_vars),
      names_to = "desc",
      values_to = "tackle_player_id",
      values_drop_na = TRUE
    ) |>
    dplyr::count(
      .data$tackle_player_id,
      .data$defteam,
      .data$season,
      .data$week,
      .data$desc
    ) |>
    dplyr::mutate(
      desc = stringr::str_remove_all(.data$desc, "_player_id") |>
        stringr::str_remove_all("_[0-9]")
    ) |>
    tidyr::pivot_wider(
      names_from = .data$desc,
      values_from = .data$n,
      values_fill = 0L,
      values_fn = sum
    ) |>
    add_column_if_missing(
      "solo_tackle",
      "tackle_with_assist",
      "tackle_for_loss",
      "assist_tackle",
      "forced_fumble_player"
    ) |>
    dplyr::mutate(
      tackles = .data$solo_tackle + .data$tackle_with_assist
    ) |>
    dplyr::select(
      "season",
      "week",
      "team" = "defteam",
      "player_id" = "tackle_player_id",
      "tackles",
      "tackles_solo" = "solo_tackle",
      "tackles_with_assist" = "tackle_with_assist",
      "tackle_assists" = "assist_tackle",
      "forced_fumbles" = "forced_fumble_player",
      "tackles_for_loss" = "tackle_for_loss"
    ) |>
    dplyr::group_by(.data$season, .data$week, .data$team, .data$player_id) |>
    dplyr::summarise(
      tackles = sum(.data$tackles, na.rm = TRUE),
      tackles_solo = sum(.data$tackles_solo, na.rm = TRUE),
      tackles_with_assist = sum(.data$tackles_with_assist, na.rm = TRUE),
      tackle_assists = sum(.data$tackle_assists, na.rm = TRUE),
      forced_fumbles = sum(.data$forced_fumbles, na.rm = TRUE),
      tackles_for_loss = sum(.data$tackles_for_loss, na.rm = TRUE)
    ) |>
    dplyr::ungroup()

  # get tackle for loss yards
  tackle_yards_df <- data |>
    dplyr::filter(
      .data$tackled_for_loss == 1,
      .data$fumble == 0,
      .data$sack == 0
    ) |>
    dplyr::select(
      "season",
      "week",
      "team" = "defteam",
      "tackle_for_loss_1_player_id",
      "tackle_for_loss_2_player_id",
      "yards_gained"
    ) |>
    tidyr::pivot_longer(
      cols = c("tackle_for_loss_1_player_id", "tackle_for_loss_2_player_id"),
      names_to = "desc",
      values_to = "player_id",
      values_drop_na = TRUE
    ) |>
    dplyr::group_by(.data$season, .data$week, .data$team, .data$player_id) |>
    dplyr::summarise(
      tfl_yards = sum(-.data$yards_gained, na.rm = TRUE)
    ) |>
    dplyr::ungroup()

  # Sack and QB Hits stats -----------------------------------------------------------

  # get sack and pressure stats
  pressure_df <- data |>
    dplyr::select(
      "season",
      "week",
      "team" = "defteam",
      dplyr::contains("sack_"),
      "yards_gained",
      dplyr::starts_with("qb_hit_"),
      -dplyr::contains("_name")
    ) |>
    tidyr::pivot_longer(
      cols = c(
        dplyr::contains("sack_"),
        dplyr::starts_with("qb_hit_")
      ),
      names_to = "desc",
      names_prefix = "sk_",
      values_to = "player_id",
      values_drop_na = TRUE
    ) |>
    dplyr::mutate(
      n = dplyr::case_when(
        .data$desc %in%
          c("half_sack_1_player_id", "half_sack_2_player_id") ~ 0.5,
        TRUE ~ 1
      ),
      desc = stringr::str_remove_all(.data$desc, "_player_id") |>
        stringr::str_remove_all("_[0-9]") |>
        stringr::str_remove("half_")
    ) |>
    dplyr::mutate(
      sack_yards = .data$n * .data$yards_gained * -1
    ) |>
    tidyr::pivot_wider(
      names_from = .data$desc,
      values_from = c(.data$n, .data$sack_yards),
      values_fn = sum,
      values_fill = 0L
    ) |>
    add_column_if_missing("n_sack", "n_qb_hit", "sack_yards_sack") |>
    dplyr::select(
      "season",
      "week",
      "team",
      "player_id",
      "sacks" = "n_sack",
      "qb_hit" = "n_qb_hit",
      "sack_yards" = "sack_yards_sack"
    ) |>
    dplyr::group_by(.data$season, .data$week, .data$team, .data$player_id) |>
    dplyr::summarise(
      sacks = sum(.data$sacks, na.rm = TRUE),
      qb_hit = sum(.data$qb_hit, na.rm = TRUE),
      sack_yards = sum(.data$sack_yards, na.rm = TRUE)
    ) |>
    dplyr::ungroup()

  # Interception and Deflection stats ---------------------------------------------------------

  # get int and def stats
  int_df <- data |>
    dplyr::select(
      "season",
      "week",
      "return_yards",
      "team" = "defteam",
      dplyr::starts_with("interception_"),
      dplyr::starts_with("pass_defense_"),
      -dplyr::contains("_name")
    ) |>
    tidyr::pivot_longer(
      cols = c(
        dplyr::starts_with("interception_"),
        dplyr::starts_with("pass_defense_")
      ),
      names_to = "desc",
      names_prefix = "int_",
      values_to = "db_player_id",
      values_drop_na = TRUE
    ) |>
    dplyr::mutate(
      n = 1,
      desc = stringr::str_remove_all(.data$desc, "_player_id") |>
        stringr::str_remove_all("_[0-9]")
    ) |>
    tidyr::pivot_wider(
      names_from = "desc",
      values_from = c("n", "return_yards"),
      values_fn = sum,
      values_fill = 0L
    ) |>
    add_column_if_missing(
      "n_interception",
      "n_pass_defense",
      "return_yards_interception"
    ) |>
    dplyr::select(
      "season",
      "week",
      "team",
      "player_id" = "db_player_id",
      "int" = "n_interception",
      "pass_defended" = "n_pass_defense",
      "int_yards" = "return_yards_interception"
    ) |>
    dplyr::group_by(.data$season, .data$week, .data$team, .data$player_id) |>
    dplyr::summarise(
      int = sum(.data$int, na.rm = TRUE),
      pass_defended = sum(.data$pass_defended, na.rm = TRUE),
      int_yards = sum(.data$int_yards, na.rm = TRUE)
    ) |>
    dplyr::ungroup()

  # Safety stats -----------------------------------------------------------

  safety_df <- data |>
    dplyr::filter(.data$safety == 1, !is.na(.data$safety_player_id)) |>
    dplyr::select(
      "season",
      "week",
      "team" = "defteam",
      "player_id" = "safety_player_id"
    ) |>
    dplyr::count(
      .data$season,
      .data$week,
      .data$team,
      .data$player_id,
      name = "safety"
    ) |>
    dplyr::group_by(.data$season, .data$week, .data$team, .data$player_id) |>
    dplyr::summarise(
      safety = sum(.data$safety, na.rm = TRUE)
    ) |>
    dplyr::ungroup()

  # Fumble stats -----------------------------------------------------------

  # get fumble stats for fumbles and own fumble recoveries
  fumble_df_own <- data |>
    dplyr::filter(.data$fumble == 1 | .data$fumble_lost == 1) |>
    dplyr::filter(
      .data$defteam == .data$fumbled_1_team |
        .data$defteam == .data$fumbled_2_team
    ) |>
    dplyr::mutate(
      fumbled_1_player_id = dplyr::if_else(
        .data$defteam == .data$fumbled_1_team,
        .data$fumbled_1_player_id,
        NA_character_,
        NA_character_
      )
    ) |>
    dplyr::select(
      "season",
      "week",
      dplyr::matches("^fumble.+team"),
      dplyr::matches("^fumble.+player_id")
    ) |>
    tidyr::pivot_longer(
      cols = dplyr::contains("fumble"),
      names_pattern = "(.+)_(team|player_id)",
      names_to = c("desc", ".value")
    ) |>
    dplyr::mutate(
      n = 1,
      desc = stringr::str_remove_all(.data$desc, "_[0-9]")
    ) |>
    tidyr::pivot_wider(
      names_from = .data$desc,
      values_from = .data$n,
      values_fn = sum,
      values_fill = 0L
    ) |>
    # Renaming fails if the columns don't exist. So we row bind a dummy tibble
    # including the relevant columns. The row will be filtered after renaming
    dplyr::bind_rows(
      tibble::tibble(
        player_id = NA_character_,
        fumbled = numeric(),
        fumble_recovery = numeric()
      )
    ) |>
    dplyr::rename(
      "fumble" = "fumbled",
      "fumble_recovery_own" = "fumble_recovery"
    ) |>
    dplyr::filter(!is.na(.data$player_id)) |>
    dplyr::group_by(.data$season, .data$week, .data$team, .data$player_id) |>
    dplyr::summarise(
      fumble = sum(.data$fumble, na.rm = TRUE),
      fumble_recovery_own = sum(.data$fumble_recovery_own, na.rm = TRUE)
    ) |>
    dplyr::ungroup()

  # get fumble stats for opponent recoveries
  fumble_df_opp <- data |>
    dplyr::filter(.data$fumble == 1 | .data$fumble_lost == 1) |>
    dplyr::filter(
      .data$defteam == .data$fumble_recovery_1_team |
        .data$defteam == .data$fumble_recovery_2_team
    ) |>
    dplyr::mutate(
      # use data.table fifelse because base ifelse changed data type to logical
      # if there are 0 rows
      fumble_recovery_1_player_id = data.table::fifelse(
        .data$defteam != .data$fumbled_1_team,
        .data$fumble_recovery_1_player_id,
        NA_character_
      ),
      fumble_recovery_2_player_id = data.table::fifelse(
        .data$defteam != .data$fumbled_2_team,
        .data$fumble_recovery_2_player_id,
        NA_character_
      )
    ) |>
    dplyr::select(
      "season",
      "week",
      dplyr::matches("^fumble_recovery.+team"),
      dplyr::matches("^fumble_recovery.+player_id")
    ) |>
    tidyr::pivot_longer(
      cols = dplyr::contains("fumble"),
      names_pattern = "(.+)_(team|player_id)",
      names_to = c("desc", ".value")
    ) |>
    dplyr::mutate(
      n = 1,
      desc = stringr::str_remove_all(.data$desc, "_[0-9]")
    ) |>
    tidyr::pivot_wider(
      names_from = .data$desc,
      values_from = .data$n,
      values_fn = sum,
      values_fill = 0L
    ) |>
    dplyr::filter(!is.na(.data$player_id)) |>
    add_column_if_missing("fumble_recovery") |>
    dplyr::rename("fumble_recovery_opp" = "fumble_recovery") |>
    dplyr::group_by(.data$season, .data$week, .data$team, .data$player_id) |>
    dplyr::summarise(
      fumble_recovery_opp = sum(.data$fumble_recovery_opp, na.rm = TRUE)
    ) |>
    dplyr::ungroup()

  # get fumble yards for own recoveries
  fumble_yds_own_data <- data |>
    dplyr::filter(.data$fumble == 1 | .data$fumble_lost == 1) |>
    dplyr::filter(
      .data$defteam == .data$fumbled_1_team |
        .data$defteam == .data$fumbled_2_team
    )

  fumble_yds_own_df <- fumble_yds_own_data |>
    dplyr::group_by(
      .data$season,
      .data$week,
      "team" = .data$fumble_recovery_1_team,
      "player_id" = .data$fumble_recovery_1_player_id
    ) |>
    dplyr::summarise(recovery_yards = sum(.data$fumble_recovery_1_yards)) |>
    dplyr::filter(!is.na(.data$player_id)) |> ### this happens when a fumble goes out of bounds. Noone gets yards --> NA/NA
    dplyr::bind_rows(
      fumble_yds_own_data |>
        dplyr::group_by(
          .data$season,
          .data$week,
          "team" = .data$fumble_recovery_2_team,
          "player_id" = .data$fumble_recovery_2_player_id
        ) |>
        dplyr::summarise(recovery_yards = sum(.data$fumble_recovery_2_yards)) |>
        dplyr::filter(!is.na(.data$player_id))
    ) |>
    dplyr::group_by(.data$season, .data$week, .data$team, .data$player_id) |>
    dplyr::summarise(fumble_recovery_yards_own = sum(.data$recovery_yards)) |>
    dplyr::ungroup()

  # get fumble yards for opp recoveries
  fumble_yds_opp_data <- data |>
    dplyr::filter(.data$fumble == 1 | .data$fumble_lost == 1) |>
    dplyr::filter(
      .data$defteam == .data$fumble_recovery_1_team,
      .data$defteam != .data$fumbled_1_team
    )

  fumble_yds_opp_df <- fumble_yds_opp_data |>
    dplyr::group_by(
      .data$season,
      .data$week,
      "team" = .data$fumble_recovery_1_team,
      "player_id" = .data$fumble_recovery_1_player_id
    ) |>
    dplyr::summarise(recovery_yards = sum(.data$fumble_recovery_1_yards)) |>
    dplyr::filter(!is.na(.data$player_id)) |>
    dplyr::bind_rows(
      fumble_yds_opp_data |>
        dplyr::group_by(
          .data$season,
          .data$week,
          "team" = .data$fumble_recovery_2_team,
          "player_id" = .data$fumble_recovery_2_player_id
        ) |>
        dplyr::summarise(recovery_yards = sum(.data$fumble_recovery_2_yards)) |>
        dplyr::filter(!is.na(.data$player_id))
    ) |>
    dplyr::group_by(.data$season, .data$week, .data$team, .data$player_id) |>
    dplyr::summarise(fumble_recovery_yards_opp = sum(.data$recovery_yards)) |>
    dplyr::ungroup()

  # Penalty stats -----------------------------------------------------------

  # get penalty stats
  penalty_df <- penalty_data |>
    dplyr::filter(
      !is.na(.data$penalty_player_id),
      .data$defteam == .data$penalty_team
    ) |>
    dplyr::select(
      "season",
      "week",
      "penalty_yards",
      "penalty_team",
      "penalty_player_id"
    ) |>
    tidyr::pivot_longer(
      cols = dplyr::contains("penalty"),
      names_pattern = "(.+)_(team|player_id|yards)",
      names_to = c("desc", ".value"),
      values_drop_na = TRUE
    ) |>
    dplyr::mutate(n = 1) |>
    tidyr::pivot_wider(
      names_from = .data$desc,
      values_from = c(.data$n, .data$yards),
      values_fn = sum,
      values_fill = 0L
    ) |>
    add_column_if_missing("n_penalty", "yards_penalty") |>
    dplyr::select(
      "season",
      "week",
      "team",
      "player_id",
      "penalty" = "n_penalty",
      "penalty_yards" = "yards_penalty"
    ) |>
    dplyr::group_by(.data$season, .data$week, .data$team, .data$player_id) |>
    dplyr::summarise(
      penalty = sum(.data$penalty, na.rm = TRUE),
      penalty_yards = sum(.data$penalty_yards, na.rm = TRUE)
    ) |>
    dplyr::ungroup()

  # Touchdown stats -----------------------------------------------------------

  # get defensive touchdowns
  touchdown_df <- data |>
    dplyr::filter(.data$touchdown == 1) |>
    dplyr::filter(.data$defteam == .data$td_team) |>
    dplyr::group_by(
      .data$season,
      .data$week,
      "team" = .data$td_team,
      "player_id" = .data$td_player_id
    ) |>
    dplyr::summarise(td = sum(.data$touchdown)) |>
    dplyr::ungroup()

  # Combine all stats -------------------------------------------------------

  # combine all the stats together

  player_df <- tackle_df |>
    dplyr::full_join(
      tackle_yards_df,
      by = c("season", "week", "player_id", "team")
    ) |>
    dplyr::full_join(
      pressure_df,
      by = c("season", "week", "player_id", "team")
    ) |>
    dplyr::full_join(int_df, by = c("season", "week", "player_id", "team")) |>
    dplyr::full_join(
      safety_df,
      by = c("season", "week", "player_id", "team")
    ) |>
    dplyr::full_join(
      fumble_df_own,
      by = c("season", "week", "player_id", "team")
    ) |>
    dplyr::full_join(
      fumble_df_opp,
      by = c("season", "week", "player_id", "team")
    ) |>
    dplyr::full_join(
      fumble_yds_own_df,
      by = c("season", "week", "player_id", "team")
    ) |>
    dplyr::full_join(
      fumble_yds_opp_df,
      by = c("season", "week", "player_id", "team")
    ) |>
    dplyr::full_join(
      penalty_df,
      by = c("season", "week", "player_id", "team")
    ) |>
    dplyr::full_join(
      touchdown_df,
      by = c("season", "week", "player_id", "team")
    ) |>
    dplyr::mutate_if(is.numeric, tidyr::replace_na, 0) |>
    dplyr::left_join(
      nflreadr::load_players() |>
        dplyr::select(
          "player_id" = "gsis_id",
          "player_display_name" = "display_name",
          "player_name" = "short_name",
          "position",
          "position_group",
          "headshot_url" = "headshot"
        ),
      by = "player_id"
    ) |>
    dplyr::left_join(stype, by = c("season", "week")) |>
    dplyr::select(dplyr::any_of(c(
      # game information
      "season",
      "week",
      "season_type",

      # id information
      "player_id",
      "player_name",
      "player_display_name",
      "position",
      "position_group",
      "headshot_url",
      "team",

      # tackle stats
      "def_tackles" = "tackles",
      "def_tackles_solo" = "tackles_solo",
      "def_tackles_with_assist" = "tackles_with_assist",
      "def_tackle_assists" = "tackle_assists",
      "def_tackles_for_loss" = "tackles_for_loss",
      "def_tackles_for_loss_yards" = "tfl_yards",
      "def_fumbles_forced" = "forced_fumbles",

      # pressure stats
      "def_sacks" = "sacks",
      "def_sack_yards" = "sack_yards",
      "def_qb_hits" = "qb_hit",

      # coverage stats
      "def_interceptions" = "int",
      "def_interception_yards" = "int_yards",
      "def_pass_defended" = "pass_defended",

      # misc stats
      "def_tds" = "td",
      "def_fumbles" = "fumble",
      "def_fumble_recovery_own" = "fumble_recovery_own",
      "def_fumble_recovery_yards_own" = "fumble_recovery_yards_own",
      "def_fumble_recovery_opp" = "fumble_recovery_opp",
      "def_fumble_recovery_yards_opp" = "fumble_recovery_yards_opp",
      "def_safety" = "safety",
      "def_penalty" = "penalty",
      "def_penalty_yards" = "penalty_yards"
    ))) |>
    dplyr::filter(!is.na(.data$player_id)) |>
    dplyr::arrange(.data$player_id, .data$season, .data$week)

  # if user doesn't want week-by-week input, aggregate the whole df
  if (isFALSE(weekly)) {
    player_df <- player_df |>
      dplyr::group_by(.data$player_id, .data$team) |>
      dplyr::summarise(
        player_name = custom_mode(.data$player_name),
        player_display_name = custom_mode(.data$player_display_name),
        games = dplyr::n(),
        position = custom_mode(.data$position),
        position_group = custom_mode(.data$position_group),
        headshot_url = custom_mode(.data$headshot_url),
        def_tackles = sum(.data$def_tackles),
        def_tackles_solo = sum(.data$def_tackles_solo),
        def_tackles_with_assist = sum(.data$def_tackles_with_assist),
        def_tackle_assists = sum(.data$def_tackle_assists),
        def_tackles_for_loss = sum(.data$def_tackles_for_loss),
        def_tackles_for_loss_yards = sum(.data$def_tackles_for_loss_yards),
        def_fumbles_forced = sum(.data$def_fumbles_forced),
        def_sacks = sum(.data$def_sacks),
        def_sack_yards = sum(.data$def_sack_yards),
        def_qb_hits = sum(.data$def_qb_hits),
        def_interceptions = sum(.data$def_interceptions),
        def_interception_yards = sum(.data$def_interception_yards),
        def_pass_defended = sum(.data$def_pass_defended),
        def_tds = sum(.data$def_tds),
        def_fumbles = sum(.data$def_fumbles),
        def_fumble_recovery_own = sum(.data$def_fumble_recovery_own),
        def_fumble_recovery_yards_own = sum(
          .data$def_fumble_recovery_yards_own
        ),
        def_fumble_recovery_opp = sum(.data$def_fumble_recovery_opp),
        def_fumble_recovery_yards_opp = sum(
          .data$def_fumble_recovery_yards_opp
        ),
        def_safety = sum(.data$def_safety),
        def_penalty = sum(.data$def_penalty),
        def_penalty_yards = sum(.data$def_penalty_yards)
      ) |>
      dplyr::ungroup() |>
      dplyr::select(
        "player_id",
        "player_name",
        "player_display_name",
        "games",
        "position",
        "position_group",
        "headshot_url",
        "team",
        dplyr::everything()
      )
  }

  player_df
}

# This function checks if the variables in ... exists as column
# names in the argument .data. If not, it adds those columns and assigns
# them the value in the argument value
add_column_if_missing <- function(.data, ..., value = 0L) {
  dots <- rlang::list2(...)
  new_cols <- dots[!dots %in% names(.data)]
  .data[, unlist(new_cols)] <- value
  .data
}
```

**Output columns (weekly grain), each with aggregation formula**

| Column | Formula |
|---|---|
| `season`, `week`, `season_type` | passthrough / joined from `stype` distinct |
| `player_id`, `player_name`, `player_display_name`, `position`, `position_group`, `headshot_url` | joined from `nflreadr::load_players()` on `player_id == gsis_id` |
| `team` | the `defteam` on the qualifying play (every sub-frame keys on `defteam`) |
| `def_tackles` | `solo_tackle + tackle_with_assist`, summed over the week |
| `def_tackles_solo` | count of rows where player appears in `solo_tackle_{1,2}_player_id` |
| `def_tackles_with_assist` | count of rows in `tackle_with_assist_1_player_id` |
| `def_tackle_assists` | count of rows in `assist_tackle_{1,2}_player_id` |
| `def_tackles_for_loss` | count of rows in `tackle_for_loss_1_player_id` (pivoted from `tackle_vars`) |
| `def_tackles_for_loss_yards` | `sum(-yards_gained)` over rows where `tackled_for_loss==1 & fumble==0 & sack==0`, pivoted long over `tackle_for_loss_{1,2}_player_id` |
| `def_fumbles_forced` | count of rows in `forced_fumble_player_{1,2}_player_id` |
| `def_sacks` | `sum(n)` where full sack = `1`, half sack (`half_sack_{1,2}_player_id`) = `0.5` |
| `def_sack_yards` | `sum(n * yards_gained * -1)` (yards lost on the sack, half-credited on half-sacks) |
| `def_qb_hits` | count of rows in `qb_hit_{1,2}_player_id` |
| `def_interceptions` | count of rows in `interception_player_id` (pivoted from `interception_`/`pass_defense_` prefixed cols with `names_prefix="int_"` — NOTE: this prefix strip only literally matches columns actually starting with `int_`, i.e. effectively only `interception_player_id`; `pass_defense_*` columns pass through unprefixed-stripped, see gotcha below) |
| `def_interception_yards` | `sum(return_yards)` gated to interception rows |
| `def_pass_defended` | count of rows in `pass_defense_{1,2}_player_id` |
| `def_tds` | count of rows where `touchdown==1 & defteam==td_team`, grouped on `td_player_id` |
| `def_fumbles` | count of rows where defender's team fumbled (`fumbled_{1,2}_team == defteam`), i.e. the defender was themselves the fumbler (turnover on a return, etc.) |
| `def_fumble_recovery_own` | count of rows where `fumble_recovery_{1,2}_team == defteam` AND that recovery was of the defense's OWN fumble (`fumbled_{1,2}_player_id` nulled out via the `defteam == fumbled_1_team` in/else in the mutate above) |
| `def_fumble_recovery_yards_own` | `sum(fumble_recovery_{1,2}_yards)` restricted to the "own" recovery rows (row-bound `1` and `2` slot frames unioned before the final group-sum) |
| `def_fumble_recovery_opp` | count of rows where `fumble_recovery_{1,2}_team == defteam` AND `defteam != fumbled_{1,2}_team` (recovered the OFFENSE's fumble) |
| `def_fumble_recovery_yards_opp` | `sum(fumble_recovery_{1,2}_yards)` restricted to opponent-fumble-recovery rows, additionally filtered to slot 1 only having the extra guard `defteam != fumbled_1_team` (slot 2 doesn't re-check that guard — see gotcha below) |
| `def_safety` | count of rows where `safety==1 & !is.na(safety_player_id)`, keyed on `safety_player_id` |
| `def_penalty` | count of rows where `penalty==1 & defteam==penalty_team & !is.na(penalty_player_id)` |
| `def_penalty_yards` | `sum(penalty_yards)` on the same penalty rows |

- `weekly=FALSE` (season aggregate) re-sums every one of the above over
  `(player_id, team)`, adds `games = n()` (distinct week-rows for that
  player/team), and re-derives `player_name`/`player_display_name`/
  `position`/`position_group`/`headshot_url` via `custom_mode` (see §6 for
  the exact tie-break semantics of `custom_mode`) rather than carrying the
  first value — a player who changed listed position mid-season gets the
  modal position, not the most-recent one.
- **Non-obvious block, transcribed verbatim above**: the `fumble_df_own`
  pivot uses `dplyr::bind_rows(tibble::tibble(player_id = NA_character_,
  fumbled = numeric(), fumble_recovery = numeric()))` purely as a
  **column-existence guarantee** so the subsequent `dplyr::rename(fumble =
  "fumbled", fumble_recovery_own = "fumble_recovery")` never errors on a
  small/edge-case input frame that happened not to produce one of those two
  pivoted columns — Python/polars port needs the equivalent of
  `add_column_if_missing` (also transcribed verbatim above) rather than this
  dummy-row trick; do not literally port the dummy `bind_rows` row (it would
  need to be filtered back out and is R-idiom-specific).
- **Gotcha (asymmetric guard)**: `fumble_yds_opp_data` filters `defteam ==
  fumble_recovery_1_team, defteam != fumbled_1_team` (slot 1 only) but then
  its recovery-yards accumulation unions in a **slot-2 group-by** that does
  NOT re-apply an equivalent `defteam != fumbled_2_team` filter at the
  `fumble_yds_opp_data` construction step — the slot-2 branch inherits
  whatever rows passed the slot-1 filter. This is exactly as coded in the
  4-year-shipped R source; replicate it as-is rather than "fixing" it
  symmetric, since the shipped published dataset reflects this exact
  (possibly slightly under/over-inclusive for the rare double-fumble-recovery
  play) behavior.
- `nflreadr::load_players()` — external released nflverse crosswalk,
  columns used: `gsis_id`, `display_name`, `short_name`, `position`,
  `position_group`, `headshot`.

## §10 aggregate_game_stats_kicking.R :: calculate_player_stats_kicking (lines 32–264)

```r
calculate_player_stats_kicking <- function(pbp, weekly = FALSE) {
  lifecycle::deprecate_warn(
    "5.0",
    "calculate_player_stats_kicking()",
    "calculate_stats()"
  )

  # need newer version of nflreadr to use load_players
  rlang::check_installed("nflreadr (>= 1.3.0)")

  # First, creating a grouping variable object to toggle the weekly argument w/
  grp_vars <- if (isTRUE(weekly)) {
    list("season", "week", "season_type", "player_id", "team")
  } else if (isFALSE(weekly)) {
    list("player_id", "team")
  }
  grp_vars <- lapply(grp_vars, as.symbol)

  # Filtering down / creating a base dataset
  df_fg_or_pat <- pbp |>
    dplyr::group_by(.data$game_id, .data$posteam) |>
    dplyr::filter(
      .data$field_goal_attempt == 1 |
        .data$extra_point_attempt == 1 |
        .data$fixed_drive == max(.data$fixed_drive, na.rm = TRUE)
    ) |>
    dplyr::ungroup() |>
    dplyr::filter(!is.na(.data$kicker_player_id)) |>
    dplyr::select(
      "game_id",
      "season",
      "week",
      "season_type",
      "team" = "posteam",
      "player_name" = "kicker_player_name",
      "player_id" = "kicker_player_id",
      "dist" = "kick_distance",
      "field_goal_attempt",
      "fg_res" = "field_goal_result",
      "extra_point_attempt",
      "pat_res" = "extra_point_result",
      "fixed_drive",
      "score_differential"
    )

  # Field-goal relevant columns
  df_field_goals <- df_fg_or_pat |>
    dplyr::filter(.data$field_goal_attempt == 1) |>
    dplyr::group_by(!!!grp_vars) |>
    dplyr::mutate(
      temp_made_idx = .data$fg_res == "made",
      temp_miss_idx = .data$fg_res == "missed",
      temp_block_idx = .data$fg_res == "blocked"
    ) |>
    dplyr::summarise(
      games_fg = list(unique(.data$game_id)),
      fg_made = sum(.data$temp_made_idx, na.rm = TRUE),
      fg_att = sum(.data$field_goal_attempt, na.rm = TRUE),
      fg_missed = sum(.data$temp_miss_idx, na.rm = TRUE),
      fg_blocked = sum(.data$temp_block_idx, na.rm = TRUE),
      fg_long = if (any(.data$temp_made_idx, na.rm = TRUE)) {
        max(.data$dist[.data$temp_made_idx], na.rm = TRUE)
      } else {
        NA_real_
      },
      fg_pct = round(.data$fg_made / .data$fg_att, 3L),
      fg_made_0_19 = sum(
        dplyr::between(.data$dist[.data$temp_made_idx], 0, 19),
        na.rm = TRUE
      ),
      fg_made_20_29 = sum(
        dplyr::between(.data$dist[.data$temp_made_idx], 20, 29),
        na.rm = TRUE
      ),
      fg_made_30_39 = sum(
        dplyr::between(.data$dist[.data$temp_made_idx], 30, 39),
        na.rm = TRUE
      ),
      fg_made_40_49 = sum(
        dplyr::between(.data$dist[.data$temp_made_idx], 40, 49),
        na.rm = TRUE
      ),
      fg_made_50_59 = sum(
        dplyr::between(.data$dist[.data$temp_made_idx], 50, 59),
        na.rm = TRUE
      ),
      fg_made_60_ = sum(.data$dist[.data$temp_made_idx] >= 60, na.rm = TRUE),
      fg_missed_0_19 = sum(
        dplyr::between(.data$dist[.data$temp_miss_idx], 0, 19),
        na.rm = TRUE
      ),
      fg_missed_20_29 = sum(
        dplyr::between(.data$dist[.data$temp_miss_idx], 20, 29),
        na.rm = TRUE
      ),
      fg_missed_30_39 = sum(
        dplyr::between(.data$dist[.data$temp_miss_idx], 30, 39),
        na.rm = TRUE
      ),
      fg_missed_40_49 = sum(
        dplyr::between(.data$dist[.data$temp_miss_idx], 40, 49),
        na.rm = TRUE
      ),
      fg_missed_50_59 = sum(
        dplyr::between(.data$dist[.data$temp_miss_idx], 50, 59),
        na.rm = TRUE
      ),
      fg_missed_60_ = sum(.data$dist[.data$temp_miss_idx] >= 60, na.rm = TRUE),
      fg_made_list = paste(
        stats::na.omit(.data$dist[.data$temp_made_idx]),
        collapse = ";"
      ),
      fg_missed_list = paste(
        stats::na.omit(.data$dist[.data$temp_miss_idx]),
        collapse = ";"
      ),
      fg_blocked_list = paste(
        stats::na.omit(.data$dist[.data$temp_block_idx]),
        collapse = ";"
      ),
      fg_made_distance = sum(.data$dist[.data$temp_made_idx], na.rm = TRUE),
      fg_missed_distance = sum(.data$dist[.data$temp_miss_idx], na.rm = TRUE),
      fg_blocked_distance = sum(.data$dist[.data$temp_block_idx], na.rm = TRUE),
      .groups = "drop"
    )

  # Extra points
  df_pat <- df_fg_or_pat |>
    dplyr::filter(.data$extra_point_attempt == 1) |>
    dplyr::group_by(!!!grp_vars) |>
    dplyr::summarise(
      games_pat = list(unique(.data$game_id)),
      pat_made = sum(.data$pat_res == "good", na.rm = TRUE),
      pat_att = sum(.data$extra_point_attempt, na.rm = TRUE),
      pat_missed = sum(.data$pat_res == "failed", na.rm = TRUE),
      pat_blocked = sum(.data$pat_res == "blocked", na.rm = TRUE),
      pat_pct = round(.data$pat_made / .data$pat_att, 3L),
      .groups = "drop"
    )

  # The Game Winning kicks distance include up to one value at the weekly level
  # but can include multiple across the season. This is one way to account for that.
  # the downside is that the column names change depending on if it is weekly vs
  # seasonal.
  if (weekly) {
    gw_dist_name <- "gwfg_distance"
  } else {
    gw_dist_name <- "gwfg_distance_list"
  }

  # See the above note. I wonder if this should also include field goals that tie
  # the game but I kept the filter dplyr::between(score_differential, -2, 0) the way
  # that is was previously. If you do include field goals that send the game into OT,
  # then you'll probably need to include the gwfg_distance AND gwfg_distance_list columns
  # in the weekly data
  game_winners <- df_fg_or_pat |>
    dplyr::group_by(.data$game_id, .data$team) |>
    dplyr::filter(.data$fixed_drive == max(.data$fixed_drive, na.rm = TRUE)) |>
    dplyr::ungroup() |>
    dplyr::filter(
      .data$field_goal_attempt == 1,
      dplyr::between(.data$score_differential, -2, 0)
    ) |>
    dplyr::group_by(!!!grp_vars) |>
    dplyr::summarise(
      games_gwfg = list(unique(.data$game_id)),
      gwfg_att = dplyr::n(),
      !!gw_dist_name := if (weekly) {
        .data$dist
      } else {
        paste(stats::na.omit(.data$dist), collapse = ";")
      },
      gwfg_made = sum(.data$fg_res == "made", na.rm = TRUE),
      gwfg_missed = sum(.data$fg_res == "missed", na.rm = TRUE),
      gwfg_blocked = sum(.data$fg_res == "blocked", na.rm = TRUE),
      .groups = "drop"
    )

  # Prepping data to merge-in player names
  df_player_names <- nflreadr::load_players() |>
    dplyr::select(
      "player_id" = "gsis_id",
      "player_display_name" = "display_name",
      "player_name" = "short_name",
      "position",
      "position_group",
      "headshot_url" = "headshot"
    )

  # Joining all the data together and organizing the first few columns.
  full_kicks <- df_field_goals |>
    dplyr::full_join(df_pat, as.character(grp_vars)) |>
    dplyr::full_join(game_winners, as.character(grp_vars)) |>
    dplyr::left_join(df_player_names, "player_id") |>
    dplyr::group_by(!!!grp_vars) |>
    dplyr::mutate(
      games = length(unique(unlist(c(
        .data$games_fg,
        .data$games_pat,
        .data$games_gwfg
      ))))
    ) |>
    dplyr::ungroup() |>
    dplyr::select(
      dplyr::any_of(c("season", "week", "season_type")),
      "player_id",
      "team",
      "player_name",
      "player_display_name",
      "games",
      "position",
      "position_group",
      "headshot_url",
      dplyr::everything(),
      -c("games_fg", "games_pat", "games_gwfg")
    ) |>
    # replace "" with NA
    dplyr::mutate_all(~ replace(.x, nchar(.x) == 0 | is.nan(.x), NA)) |>
    # replace NA in attempt columns with 0
    dplyr::mutate_at(
      c("fg_att", "pat_att", "gwfg_att"),
      ~ tidyr::replace_na(.x, 0)
    )

  if (weekly) {
    full_kicks |>
      dplyr::select(-"games") |>
      dplyr::arrange(.data$player_id, .data$season, .data$week)
  } else {
    full_kicks |>
      dplyr::arrange(.data$player_id)
  }
}
```

**Output columns, each with aggregation formula**

| Column | Formula |
|---|---|
| `season`, `week`, `season_type` | only present when `weekly=TRUE` (dropped from `grp_vars` otherwise) |
| `player_id`, `team`, `player_name`, `player_display_name`, `position`, `position_group`, `headshot_url` | joined from `nflreadr::load_players()` on `player_id == gsis_id`, plus `team = posteam` on the qualifying kick play |
| `games` | `length(unique(unlist(games_fg, games_pat, games_gwfg)))` — distinct `game_id`s across ALL THREE kick-type sub-frames combined, computed post-join (dropped again from the `weekly=TRUE` output, kept for `weekly=FALSE`) |
| `fg_made` / `fg_att` / `fg_missed` / `fg_blocked` | counts of `field_goal_attempt==1` rows by `fg_res` |
| `fg_long` | `max(dist)` over made kicks, `NA` if 0 made |
| `fg_pct` | `round(fg_made / fg_att, 3)` |
| `fg_made_0_19` … `fg_made_50_59` | `sum(between(dist, lo, hi))` over made kicks, 5 fixed 10-yard buckets |
| `fg_made_60_` | `sum(dist >= 60)` over made kicks |
| `fg_missed_0_19` … `fg_missed_50_59`, `fg_missed_60_` | same 6 buckets over missed kicks |
| `fg_made_list` / `fg_missed_list` / `fg_blocked_list` | `;`-joined string of every distance in that bucket (NA-omitted) — **list-as-string encoding**, not a real list column; a Python port has the option of keeping the true list or matching this string format for column-for-column parity with the released dataset — prefer keeping the exact `;`-joined string format for drop-in parity |
| `fg_made_distance` / `fg_missed_distance` / `fg_blocked_distance` | `sum(dist)` over each bucket |
| `pat_made` / `pat_att` / `pat_missed` / `pat_blocked` | counts of `extra_point_attempt==1` rows by `pat_res` (`"good"`/`"failed"`/`"blocked"`) |
| `pat_pct` | `round(pat_made / pat_att, 3)` |
| `gwfg_att` | `n()` of FG attempts on the LAST fixed_drive of a game for that team where `score_differential ∈ [-2, 0]` (i.e. a potential game-winning/game-tying kick on the team's final possession) |
| `gwfg_distance` (weekly) / `gwfg_distance_list` (season) | weekly: raw `dist` value(s) as a list-column (one row can have a list if a game had a distinct within-week structure); season: `;`-joined string, `NA`-omitted — **column name itself changes based on the `weekly` flag**, a deliberate API wart to preserve, not a bug |
| `gwfg_made` / `gwfg_missed` / `gwfg_blocked` | counts of `fg_res` within the game-winning-attempt subset |

- Base filter for the working frame `df_fg_or_pat`: **grouped by `(game_id,
  posteam)`**, keep a row if it's a FG attempt, OR an XP attempt, OR its
  `fixed_drive == max(fixed_drive)` for that team in that game (this last
  clause is what feeds the game-winning-kick logic — it retains every play
  of the team's final drive, not just kicks, then the downstream
  `game_winners` block re-filters to `field_goal_attempt==1` within that
  retained set).
- Final cleanup: `mutate_all(~ replace(.x, nchar(.x)==0 | is.nan(.x), NA))`
  — blanket empty-string/NaN → NA across every column (note: `nchar(.x)` on
  a numeric column in R coerces to string first, so this also strings-then-
  measures numeric columns; a polars port should apply this per-dtype:
  `pl.col(Utf8).str.len_chars()==0` → null for string columns, `is_nan()`
  → null for float columns), THEN `fg_att`/`pat_att`/`gwfg_att` specifically
  get their post-blanket-NA back-filled to `0` (so attempt counts are never
  null, only the rate/distance columns can be null when a player attempted
  zero of that kick type).
- `nflreadr::load_players()` — same external crosswalk dependency as §9.

## §11 calculate_series_conversion_rates.R :: calculate_series_conversion_rates (lines 84–191)

```r
calculate_series_conversion_rates <- function(pbp, weekly = FALSE) {
  if (isTRUE(weekly)) {
    grp <- c("season", "team", "week")
  } else if (isFALSE(weekly)) {
    grp <- c("season", "team")
  }
  grp_vars <- lapply(grp, as.symbol)

  # Offense -----------------------------------------------------------------

  off_series <- pbp |>
    dplyr::filter(
      !is.na(.data$down),
      .data$series_result != "QB kneel"
      # .data$rush == 1 | .data$pass == 1
    ) |>
    dplyr::group_by(
      .data$season,
      .data$week,
      team = .data$posteam,
      .data$series
    ) |>
    dplyr::summarise(
      conversion = dplyr::first(.data$series_success),
      result = dplyr::first(.data$series_result),
      last_down = dplyr::last(.data$down),
      .groups = "drop"
    )

  offense <- off_series |>
    dplyr::group_by(!!!grp_vars) |>
    dplyr::summarise(
      off_n = dplyr::n(),
      off_scr = mean(.data$conversion),
      off_scr_1st = mean(.data$last_down == 1 * .data$conversion),
      off_scr_2nd = mean(.data$last_down == 2 * .data$conversion),
      off_scr_3rd = mean(.data$last_down == 3 * .data$conversion),
      off_scr_4th = mean(.data$last_down == 4 * .data$conversion),
      off_1st = mean(.data$result == "First down"),
      off_td = mean(.data$result == "Touchdown"),
      off_fg = mean(.data$result %in% c("Field goal", "Missed field goal")),
      off_punt = mean(.data$result == "Punt"),
      off_to = mean(
        .data$result %in%
          c(
            "Turnover on downs",
            "Turnover",
            "Opp touchdown",
            "Safety",
            "End of half"
          )
      ),
      .groups = "drop"
    )

  # Defense -----------------------------------------------------------------

  def_series <- pbp |>
    dplyr::filter(
      !is.na(.data$down),
      .data$series_result != "QB kneel"
      # .data$rush == 1 | .data$pass == 1
    ) |>
    dplyr::group_by(
      .data$season,
      .data$week,
      team = .data$defteam,
      .data$series
    ) |>
    dplyr::summarise(
      conversion = dplyr::first(.data$series_success),
      result = dplyr::first(.data$series_result),
      last_down = dplyr::last(.data$down),
      .groups = "drop"
    )

  defense <- def_series |>
    dplyr::group_by(!!!grp_vars) |>
    dplyr::summarise(
      def_n = dplyr::n(),
      def_scr = mean(.data$conversion),
      def_scr_1st = mean(.data$last_down == 1 * .data$conversion),
      def_scr_2nd = mean(.data$last_down == 2 * .data$conversion),
      def_scr_3rd = mean(.data$last_down == 3 * .data$conversion),
      def_scr_4th = mean(.data$last_down == 4 * .data$conversion),
      def_1st = mean(.data$result == "First down"),
      def_td = mean(.data$result == "Touchdown"),
      def_fg = mean(.data$result %in% c("Field goal", "Missed field goal")),
      def_punt = mean(.data$result == "Punt"),
      def_to = mean(
        .data$result %in%
          c(
            "Turnover on downs",
            "Turnover",
            "Opp touchdown",
            "Safety",
            "End of half"
          )
      ),
      .groups = "drop"
    )

  # Offense + Defense -------------------------------------------------------

  combined <- dplyr::full_join(offense, defense, by = grp)

  combined
}
```

**Port contract**

- Output columns (repeated for `off_*`/`def_*` mirror pairs, keyed by
  `posteam`/`defteam` respectively): `off_n`/`def_n` (series count, QB-kneel
  series excluded, `down IS NOT NULL` required — this is what excludes
  kickoffs/PAT/2pt/non-plays/no-posteam per the §7 docstring), `off_scr`/
  `def_scr` = `mean(series_success)` across that team's series, `off_scr_1st`
  … `off_scr_4th` = `mean(last_down==N * conversion)` **(operator precedence
  note: `last_down == 1 * conversion` parses as `last_down == (1 *
  conversion)`, i.e. `1*conversion` is just `conversion` (0 or 1) so this is
  literally `mean(last_down == conversion)` — NOT `mean((last_down==1) *
  conversion)` as the column name implies!** This is almost certainly an
  unintended R operator-precedence bug baked into a shipped, released
  function; **transcribe the exact (buggy) formula for parity** —
  `last_down == conversion` compares a down number (1–4) to a 0/1 success
  flag, which is `TRUE` only when `last_down == 0` (never) or `last_down ==
  1 & conversion == 1`. So in practice `off_scr_1st` = share of series where
  the series ended on 1st down AND succeeded, `off_scr_2nd` = share where
  `last_down == 2 & conversion==1`... wait — re-derive carefully: the
  literal computed boolean is `last_down == (N * conversion)`. When
  `conversion == 0`, `N*conversion == 0`, so the comparison becomes
  `last_down == 0` (always `FALSE` since `down` is 1–4). When
  `conversion == 1`, `N*conversion == N`, so the comparison becomes
  `last_down == N`. Net effect: **`off_scr_Nth` = mean(conversion==1 &
  last_down==N)**, i.e. it DOES functionally compute "fraction of all series
  that succeeded on down N" — the naming survives even though the
  expression is written in a confusing non-idiomatic way
  (`last_down == N * conversion` rather than the presumably-intended
  `(last_down == N) * conversion`, which would have summed/averaged to the
  same real number by coincidence of `conversion` being 0/1 — **so the
  formula is accidentally correct**, but the R expression as literally
  written must still be transcribed exactly and re-derived this way in
  Python, e.g. `(last_down == n) & (conversion == 1)`, since a careless
  transliteration to `last_down == n * conversion` in Python would be
  identically correct too (same operator precedence in Python) — flag this
  for the porting engineer as understood-but-confusing, not a discrepancy to
  "fix").
- `off_1st`/`def_1st` = `mean(result == "First down")`; `off_td`/`def_td` =
  `mean(result == "Touchdown")`; `off_fg`/`def_fg` = `mean(result %in%
  c("Field goal", "Missed field goal"))`; `off_punt`/`def_punt` =
  `mean(result == "Punt")`; `off_to`/`def_to` = `mean(result %in%
  c("Turnover on downs", "Turnover", "Opp touchdown", "Safety", "End of
  half"))`.
- Grouping: per-series conversion/result/last_down are first collapsed with
  `dplyr::first()`/`dplyr::last()` over `(season, week, team, series)` — this
  requires the frame to already be in play order within a series (relies on
  the pipeline's established play ordering, not an independent sort here).
  Then the team-level rates are `mean()` over `(season, team)` or `(season,
  team, week)` depending on the `weekly` flag.
- `combined <- dplyr::full_join(offense, defense, by = grp)` — a team with
  offensive series in a week but literally zero defensive series (or vice
  versa, essentially never happens in real data but is structurally
  possible) gets `NA` in the missing side rather than the row being dropped.

---

## §12 calculate_standings.R :: calculate_standings + .compute_standings (lines 40–189)

```r
calculate_standings <- function(
  nflverse_object,
  tiebreaker_depth = 3,
  playoff_seeds = NULL
) {
  lifecycle::deprecate_warn(
    "5.1.0",
    "calculate_standings()",
    "nflseedR::nfl_standings()"
  )

  if (!inherits(nflverse_object, "nflverse_data")) {
    cli::cli_abort(
      "The function argument {.arg nflverse_object} has to be
                   of class {.cls nflverse_data}"
    )
  }

  rlang::check_installed(
    "nflseedR",
    "to compute standings.",
    compare = ">=",
    version = "1.0.2"
  )

  type <- attr(nflverse_object, "nflverse_type")

  if (type == "play by play data") {
    .standings_from_pbp(
      nflverse_object,
      tiebreaker_depth = tiebreaker_depth,
      playoff_seeds = playoff_seeds
    )
  } else if (type == "games and schedules") {
    .standings_from_games(
      nflverse_object,
      tiebreaker_depth = tiebreaker_depth,
      playoff_seeds = playoff_seeds
    )
  } else {
    cli::cli_abort(
      "Can only handle nflverse_type {.val play by play data} or
                   {.val games and schedules} and not {.val {type}}"
    )
  }
}

.standings_from_pbp <- function(pbp, tiebreaker_depth, playoff_seeds) {
  g <- pbp |>
    dplyr::filter(.data$season_type == "REG") |>
    dplyr::group_by(.data$game_id) |>
    dplyr::summarise(
      sim = dplyr::first(.data$season),
      game_type = dplyr::first(.data$season_type),
      week = dplyr::first(.data$week),
      away_team = dplyr::first(.data$away_team),
      home_team = dplyr::first(.data$home_team),
      result = dplyr::last(.data$home_score) - dplyr::last(.data$away_score)
    ) |>
    dplyr::ungroup() |>
    dplyr::select(-"game_id")

  if (is.null(playoff_seeds)) {
    g6 <- g |>
      dplyr::filter(.data$sim %in% 1999:2019)
    g7 <- g |>
      dplyr::filter(.data$sim >= 2020)
    dplyr::bind_rows(
      .compute_standings(
        g6,
        tiebreaker_depth = tiebreaker_depth,
        playoff_seeds = 6
      ),
      .compute_standings(
        g7,
        tiebreaker_depth = tiebreaker_depth,
        playoff_seeds = 7
      )
    )
  } else {
    .compute_standings(
      g,
      tiebreaker_depth = tiebreaker_depth,
      playoff_seeds = playoff_seeds
    )
  }
}

.standings_from_games <- function(games, tiebreaker_depth, playoff_seeds) {
  g <- games |>
    dplyr::filter(.data$game_type == "REG", !is.na(.data$result)) |>
    dplyr::select(
      "sim" = "season",
      "game_type",
      "week",
      "away_team",
      "home_team",
      "result"
    )

  if (is.null(playoff_seeds)) {
    g6 <- g |>
      dplyr::filter(.data$sim %in% 1999:2019)
    g7 <- g |>
      dplyr::filter(.data$sim >= 2020)
    dplyr::bind_rows(
      .compute_standings(
        g6,
        tiebreaker_depth = tiebreaker_depth,
        playoff_seeds = 6
      ),
      .compute_standings(
        g7,
        tiebreaker_depth = tiebreaker_depth,
        playoff_seeds = 7
      )
    )
  } else {
    .compute_standings(
      g,
      tiebreaker_depth = tiebreaker_depth,
      playoff_seeds = playoff_seeds
    )
  }
}

.compute_standings <- function(games, tiebreaker_depth, playoff_seeds) {
  if (nrow(games) == 0) {
    return(data.frame())
  }
  suppressMessages({
    div <- nflseedR::compute_division_ranks(
      games,
      tiebreaker_depth = tiebreaker_depth
    )
    conf <- nflseedR::compute_conference_seeds(
      div,
      h2h = div$h2h,
      tiebreaker_depth = tiebreaker_depth,
      playoff_seeds = playoff_seeds
    )
  })
  conf$standings |>
    dplyr::select(-"exit", -"wins") |>
    dplyr::select("sim":"division", "div_rank", "seed", dplyr::everything()) |>
    dplyr::rename("season" = "sim", "wins" = "true_wins") |>
    dplyr::arrange(.data$season, .data$division, .data$div_rank, .data$seed) |>
    tibble::as_tibble()
}
```

**Port contract**

- **`calculate_standings` is deprecated (since nflfastR 5.1.0) in favor of
  `nflseedR::nfl_standings()`, and — critically — it does NOT implement the
  NFL tiebreaker rules itself.** All of division-rank computation
  (`nflseedR::compute_division_ranks`) and conference-seed computation with
  head-to-head/strength-of-victory/strength-of-schedule/common-games
  tiebreakers (`nflseedR::compute_conference_seeds`) are delegated entirely
  to the **external `nflseedR` R package** (min version `>= 1.0.2`, enforced
  via `rlang::check_installed`). There is no tiebreaker logic to transcribe
  from this file — it is 100% a thin dispatch + reshape wrapper around
  `nflseedR`. **A faithful Python port of the actual tiebreaker rules must
  port `nflseedR::compute_division_ranks` / `compute_conference_seeds`
  (a separate R package, github.com/nflverse/nflseedR), not anything in
  `nflfastR`.** Flag this to the porting team explicitly — do not attempt to
  reverse-engineer tiebreakers from this file, they aren't here.
- `calculate_standings` dispatches on `attr(nflverse_object,
  "nflverse_type")` (set by `make_nflverse_data()`, `utils.R` line 154–160)
  to one of two input-shape adapters, both of which reduce to a common
  `(sim, game_type, week, away_team, home_team, result)` schema before
  calling `.compute_standings`:
  - `.standings_from_pbp`: filters `season_type == "REG"`, collapses each
    `game_id` to one row via `first(season)`, `first(season_type)`,
    `first(week)`, `first(away_team)`, `first(home_team)`, and **`result =
    last(home_score) - last(away_score)`** (last row's cumulative score
    columns — depends on the frame already carrying running `home_score`/
    `away_score` and being in play order within `game_id`).
  - `.standings_from_games`: filters `game_type == "REG" & !is.na(result)`,
    straight column rename/select (`season→sim`).
- **Season-range playoff-seed split**: when `playoff_seeds` is not supplied,
  the function auto-splits into two independent `.compute_standings` calls —
  seasons `1999:2019` get `playoff_seeds = 6` (pre-2020 6-team-per-conference
  playoff format), seasons `>= 2020` get `playoff_seeds = 7` (post-2020
  7-team format, the actual rule change year) — then `bind_rows`s the two
  results. This 2020 cutover constant (`playoff_seeds: 6 → 7`) is the one
  piece of nflfastR-specific domain knowledge in this file and must be
  preserved verbatim in a port even though the tiebreaker math itself lives
  elsewhere.
- Output columns (from `conf$standings`, an `nflseedR` object, after
  `nflfastR`'s reshape): drops `exit`/`wins` (nflseedR's own win-count column
  before nflfastR's own rename), reorders to put `sim:division` (renamed
  `season`), `div_rank`, `seed` first, then everything else from
  `nflseedR`, renames `sim→season` and `true_wins→wins`, sorted by
  `(season, division, div_rank, seed)`. The exact full column set is
  **entirely determined by whatever `nflseedR::compute_conference_seeds()`
  emits** in the installed nflseedR version — this file does not enumerate
  them; a Python port needs to either re-implement nflseedR's standings
  output schema or treat NFL standings/tiebreakers as an explicit
  out-of-scope dependency on a separate porting effort.

## §13 build_playstats.R :: build_playstats + calculate_stats.R :: load_playstats

### build_playstats (lines 1–105)

```r
build_playstats <- function(
  seasons = nflreadr::most_recent_season(),
  stat_ids = 1:1000,
  dir = getOption("nflfastR.raw_directory", default = NULL),
  skip_local = FALSE
) {
  if (is_sequential()) {
    cli::cli_alert_info(
      "It is recommended to use parallel processing when using this function. \\
        Please consider running {.code future::plan(\"multisession\")}! \\
        Will go on sequentially...",
      wrap = TRUE
    )
  }

  games <- nflreadr::load_schedules(seasons = seasons) |>
    dplyr::filter(!is.na(.data$result)) |>
    dplyr::pull(.data$game_id)

  p <- progressr::progressor(along = games)

  l <- furrr::future_map(
    games,
    function(id, p = NULL, dir, skip_local) {
      if (id %in% c("2000_03_SD_KC", "2000_06_BUF_MIA", "1999_01_BAL_STL")) {
        cli::cli_alert_warning(
          "We are missing raw game data of {.val {id}}. Skipping."
        )
        return(data.frame())
      }
      season <- substr(id, 1, 4)
      raw_data <- load_raw_game(id, dir = dir, skip_local = skip_local)
      if (season <= 2000) {
        drives <- raw_data[[1]][["drives"]] |>
          purrr::keep(is.list)
        out <- tibble::tibble(d = drives) |>
          tidyr::unnest_wider("d") |>
          tidyr::unnest_longer("plays") |>
          tidyr::unnest_wider("plays", names_sep = "_") |>
          dplyr::select("playId" = "plays_id", "playStats" = "plays_players") |>
          dplyr::mutate(
            playId = uniquify_ids(.data$playId)
          ) |>
          tidyr::unnest_longer("playStats") |>
          tidyr::unnest_longer("playStats") |>
          tidyr::unnest_wider("playStats") |>
          dplyr::mutate(
            playId = as.integer(.data$playId),
            statId = as.integer(.data$statId),
            yards = as.integer(.data$yards),
            team.id = NA_character_
          ) |>
          dplyr::select(-"sequence") |>
          dplyr::rename(
            team.abbreviation = "clubcode",
            gsis.Player.id = "playStats_id"
          ) |>
          tidyr::nest(
            playStats = c(
              "statId",
              "yards",
              "playerName",
              "team.id",
              "team.abbreviation",
              "gsis.Player.id"
            )
          )
      } else {
        out <- raw_data$data$viewer$gameDetail$plays[, c("playId", "playStats")]
      }
      out$game_id <- as.character(id)
      p(sprintf("ID=%s", as.character(id)))
      out
    },
    p = p,
    dir = dir,
    skip_local = skip_local
  )

  out <- data.table::rbindlist(l) |>
    tidyr::unnest(cols = c("playStats")) |>
    janitor::clean_names() |>
    dplyr::filter(.data$stat_id %in% stat_ids) |>
    dplyr::mutate(
      season = as.integer(substr(.data$game_id, 1, 4)),
      week = as.integer(substr(.data$game_id, 6, 7))
    ) |>
    decode_player_ids() |>
    dplyr::select(
      "game_id",
      "season",
      "week",
      "play_id",
      "stat_id",
      "yards",
      "team_abbr" = "team_abbreviation",
      "player_name",
      "gsis_player_id",
    ) |>
    dplyr::mutate_if(
      .predicate = is.character,
      .funs = ~ dplyr::na_if(.x, "")
    )
  out
}
```

### load_playstats (calculate_stats.R, lines 678–698)

```r
load_playstats <- function(seasons = nflreadr::most_recent_season()) {
  if (isTRUE(seasons)) {
    seasons <- seq(1999, nflreadr::most_recent_season())
  }

  stopifnot(
    is.numeric(seasons),
    seasons >= 1999,
    seasons <= nflreadr::most_recent_season()
  )

  urls <- paste0(
    "https://github.com/nflverse/nflverse-pbp/releases/download/playstats/play_stats_",
    seasons,
    ".rds"
  )

  out <- nflreadr::load_from_url(urls, seasons = TRUE, nflverse = FALSE)

  out
}
```

**Port contract**

- `build_playstats(seasons, stat_ids=1:1000, dir=NULL, skip_local=FALSE)` is
  the **producer**: it re-derives the raw per-play stat-attribution table
  (`play_stats_{season}.rds`, one row per `(game_id, play_id, stat_id,
  player)`) directly from the raw scraped game JSON (`load_raw_game`), NOT
  from the already-built pbp frame — this is the same raw source
  `get_pbp_nfl` consumes (`raw_data$data$viewer$gameDetail$plays[,
  c("playId", "playStats")]` for 2001+ seasons), but taken through a
  different unnest path here that flattens ALL stat IDs (not just the ones
  `sum_play_stats` collapses into named pbp columns).
  - **Hardcoded skip-list** (3 games with permanently missing raw data —
    transcribe complete): `"2000_03_SD_KC"`, `"2000_06_BUF_MIA"`,
    `"1999_01_BAL_STL"`.
  - **Season ≤ 2000 branch** uses a structurally different raw JSON shape
    (`raw_data[[1]][["drives"]]`, nested `plays`/`playStats`/`players`
    lists) requiring `purrr::keep(is.list)` to drop non-list drive entries,
    then a `tidyr::unnest_wider`/`unnest_longer` chain, plus
    `uniquify_ids()` (from `utils.R`, disambiguates fractional play IDs like
    `2767.375` by progressively multiplying by 10/100/... until integers
    are unique within the game) applied to `playId` — **this old-format
    branch is schema-incompatible with the 2001+ branch until the final
    `rbindlist`**, since it builds a re-nested `playStats` list-column with
    a fixed 6-field schema (`statId, yards, playerName, team.id,
    team.abbreviation, gsis.Player.id`) specifically so the shapes match for
    concatenation.
  - Final output schema: `game_id` (Utf8), `season`/`week` (Int, parsed from
    `game_id`), `play_id` (Int), `stat_id` (Int, filtered to `stat_ids`
    param, default keeps everything `1:1000`), `yards` (Int), `team_abbr`
    (Utf8), `player_name` (Utf8), `gsis_player_id` (Utf8, post
    `decode_player_ids()` — see §6 note on that dependency). Empty strings
    coerced to `NA` across all character columns as the final step.
  - **`build_playstats` is a producer/publish-pipeline function** (writes
    the artifact that then gets uploaded to the
    `nflverse/nflverse-pbp` release under tag `playstats` — not shown
    verbatim in this file, but implied by `load_playstats`'s URL pattern
    below); a consumer-side Python port only needs `load_playstats`'s
    contract, not necessarily `build_playstats` itself, unless the port also
    owns re-deriving this artifact from raw JSON.
- `load_playstats(seasons)` is the **consumer**: downloads
  `https://github.com/nflverse/nflverse-pbp/releases/download/playstats/play_stats_{season}.rds`
  per requested season (one file per season, `seasons=TRUE` sentinel expands
  to the full `1999:most_recent_season()` range) via
  `nflreadr::load_from_url(urls, seasons=TRUE, nflverse=FALSE)`. This IS the
  external data dependency the task brief anticipated for §13: a **released,
  versioned RDS file per season**, not something to regenerate at pbp-build
  time — `add_nflscrapr_mutations`/`clean_pbp`/etc. do NOT call
  `load_playstats`; it's consumed separately by `calculate_stats()`
  (the modern, non-deprecated replacement for `calculate_player_stats_def`/
  `_kicking`/etc.) to attribute stats that aren't already columns on the pbp
  frame. **Vendoring note**: a Python port needs an RDS reader (e.g.
  `pyreadr` or converting once to Parquet) for these season files, or a
  one-time re-export to Parquet on the nflverse-data side — the files are
  hosted at a stable, versioned GitHub Releases URL (`nflverse-pbp` repo,
  `playstats` tag), one `.rds` per season from 1999 to present, no schema
  version negotiation beyond `most_recent_season()` bounds-checking.

## §14 helper_add_nflscrapr_mutations.R :: qb_dropback, qb_scramble, qb_kneel, qb_spike, pass, rush, play_type mapping

### qb_kneel / qb_spike / qb_scramble / shotgun / no_huddle (lines 400–418)

```r
      # Indicator columns for both QB kneels, spikes, scrambles,
      # no huddle, shotgun plays:
      qb_kneel = dplyr::if_else(
        stringr::str_detect(.data$play_description, " kneels ") &
          .data$kickoff_attempt != 1,
        1,
        0
      ),
      qb_spike = stringr::str_detect(.data$play_description, " spiked ") |>
        as.numeric(),
      qb_scramble = stringr::str_detect(
        .data$play_description,
        " scrambles "
      ) |>
        as.numeric(),
      shotgun = stringr::str_detect(.data$play_description, "Shotgun") |>
        as.numeric(),
      no_huddle = stringr::str_detect(.data$play_description, "No Huddle") |>
        as.numeric(),
```

### play_type mapping — translate_play_type_nfl (lines 820–891), and its call site (lines 423–436)

```r
      # Create a play type column: either pass, run, field_goal, extra_point,
      # kickoff, punt, qb_kneel, qb_spike, or no_play (which includes timeouts and
      # penalties):
      play_type = translate_play_type_nfl(
        .data$play_type_nfl,
        qb_spike = .data$qb_spike,
        qb_kneel = .data$qb_kneel,
        pass_attempt = .data$pass_attempt,
        rush_attempt = .data$rush_attempt,
        punt_attempt = .data$punt_attempt,
        field_goal_attempt = .data$field_goal_attempt,
        penalty = .data$penalty,
        is_penalty_enforced_between_downs = stringr::str_detect(
          tolower(.data$play_description),
          "enforced between downs"
        )
      ),
```

```r
translate_play_type_nfl <- function(
  play_type_nfl,
  qb_spike,
  qb_kneel,
  pass_attempt,
  rush_attempt,
  punt_attempt,
  field_goal_attempt,
  penalty,
  is_penalty_enforced_between_downs
) {
  # I want the arg name to be descriptive, but I want a short variable name
  # for the code below
  x <- play_type_nfl

  out <- dplyr::case_when(
    x == "COMMENT" ~ NA_character_,
    x == "END_GAME" ~ NA_character_,
    x == "END_QUARTER" ~ NA_character_,
    x == "FIELD_GOAL" ~ "field_goal",
    x == "FREE_KICK" ~ "kickoff",
    x == "GAME_START" ~ NA_character_,
    x == "INTERCEPTION" ~ "pass",
    x == "KICK_OFF" ~ "kickoff",
    x == "PASS" ~ "pass",
    x == "PAT2" & pass_attempt == 1 ~ "pass",
    x == "PAT2" & rush_attempt == 1 ~ "run",
    x == "PENALTY" &
      pass_attempt == 1 &
      is_penalty_enforced_between_downs ~ "pass",
    x == "PENALTY" &
      rush_attempt == 1 &
      is_penalty_enforced_between_downs ~ "run",
    x == "PENALTY" ~ "no_play",
    x == "PUNT" ~ "punt",
    x == "RUSH" ~ "run",
    x == "SACK" ~ "pass",
    x == "TIMEOUT" ~ "no_play",
    x == "XP_KICK" ~ "extra_point",

    # UNSPECIFIED is a mix of all sorts of weird plays
    x == "UNSPECIFIED" & penalty == 1 ~ "no_play",

    # the following lines imply penalty == 0 because penalty == 1 triggers above
    x == "UNSPECIFIED" & pass_attempt == 1 ~ "pass",
    x == "UNSPECIFIED" & rush_attempt == 1 ~ "run",
    x == "UNSPECIFIED" & punt_attempt == 1 ~ "punt",
    x == "UNSPECIFIED" & field_goal_attempt == 1 ~ "field_goal",

    # most of the remaining UNSPECIFIED plays will be declined penalties
    # from punt or fg formation. These don't really count as play so we define
    # them as no_play
    x == "UNSPECIFIED" ~ "no_play",

    # default
    TRUE ~ ""
  )

  # every play_type_nfl that we do not catch in the above cases
  # will be an empty string. We try to resolve these as good as we can
  # also need to replace passes and runs that were spikes and kneel downs
  dplyr::case_when(
    out == "" & penalty == 1 ~ "no_play",
    out == "" & pass_attempt == 1 ~ "pass",
    out == "" & rush_attempt == 1 ~ "run",
    out == "" & punt_attempt == 1 ~ "punt",
    out == "" & field_goal_attempt == 1 ~ "field_goal",
    qb_spike == 1 & out %in% c("pass", "run") ~ "qb_spike",
    qb_kneel == 1 & out %in% c("pass", "run") ~ "qb_kneel",
    TRUE ~ out
  )
}
```

### qb_dropback (lines 438–445)

```r
      # Indicator for QB dropbacks (exclude spikes and kneels):
      qb_dropback = dplyr::if_else(
        .data$play_type == "pass" |
          (.data$play_type == "run" &
            .data$qb_scramble == 1),
        1,
        0
      ),
```

**Port contract**

- `qb_kneel` (0/1): `desc` contains literal `" kneels "` AND
  `kickoff_attempt != 1` (guards against a kneel-adjacent kickoff narrative
  false-positive). `qb_spike`/`qb_scramble`/`shotgun`/`no_huddle` (all 0/1):
  plain `str_detect` on fixed literals `" spiked "`, `" scrambles "`,
  `"Shotgun"`, `"No Huddle"` — no lookaround, straightforward
  `str.contains` port. **Important ordering note**: these are computed from
  raw `play_description` BEFORE `fix_scrambles()` runs later in the same
  pipe (§2) — the charting-data scramble backfill for 1999–2005 only flips
  `qb_scramble`, it does not retroactively touch `qb_dropback` or
  `play_type` which are derived immediately below from the pre-fix value.
- `play_type` (Utf8 category: `"pass"`, `"run"`, `"punt"`, `"field_goal"`,
  `"extra_point"`, `"kickoff"`, `"no_play"`, `"qb_spike"`, `"qb_kneel"`, or
  `NA`) — `translate_play_type_nfl` is a **pure two-pass `case_when`
  cascade**, transcribed complete above (18 first-pass branches + 7
  second-pass fallback/override branches). First pass maps the raw NFL feed
  `play_type_nfl` enum (`COMMENT, END_GAME, END_QUARTER, FIELD_GOAL,
  FREE_KICK, GAME_START, INTERCEPTION, KICK_OFF, PASS, PAT2, PENALTY, PUNT,
  RUSH, SACK, TIMEOUT, XP_KICK, UNSPECIFIED`) to the canonical `play_type`
  vocabulary, with `PAT2`/`PENALTY`/`UNSPECIFIED` needing side-channel
  `pass_attempt`/`rush_attempt`/`punt_attempt`/`field_goal_attempt`/
  `penalty`/`is_penalty_enforced_between_downs` flags to disambiguate.
  Second pass catches every `play_type_nfl` value NOT in the first pass's
  enum (falls through to `""` via the final `TRUE ~ ""`), resolves it via
  the same attempt flags, and — **critically, this runs regardless of
  whether the first or second pass produced the value** — overrides `"pass"`
  or `"run"` to `"qb_spike"`/`"qb_kneel"` whenever the corresponding
  indicator flag is set (checked last, so a spike/kneel always wins over a
  plain pass/run classification even if the first pass already resolved it).
  `is_penalty_enforced_between_downs` is computed at the call site as
  `str_detect(tolower(desc), "enforced between downs")` — transcribe that
  computation alongside the call, not just the function signature.
- `qb_dropback` (0/1): `play_type == "pass"` OR (`play_type == "run"` AND
  `qb_scramble == 1`) — i.e. sacks and pass attempts count, scrambles count
  (they're classified `play_type == "run"` but originated as a dropback),
  QB kneels/spikes do NOT count (excluded by construction since
  `play_type` for those is `"qb_kneel"`/`"qb_spike"`, never `"pass"`/`"run"`
  once the override in `translate_play_type_nfl`'s second pass has fired).
- **`pass` and `rush` are NOT defined in `add_nflscrapr_mutations` / this
  file at all** — despite living in the same conceptual "play
  classification" neighborhood as `qb_dropback`/`play_type`, they are
  computed later in the pipeline inside `clean_pbp()`
  (`helper_additional_functions.R`, lines 162–191, transcribed complete in
  §6 above) from `desc` regex detection of `" pass "`/`"sacked"`/`"scramble"`
  plus the `qb_scramble` flag, with explicit exclusions for
  backward/lateral passes and kickoffs, and a final hardcoded
  `fix_weird_pass_plays()` override (§3). **A from-scratch porting engineer
  who assumes `pass`/`rush` live next to `qb_dropback`/`play_type` in the
  same module will look in the wrong file — flag this explicitly**: `pass`/
  `rush` require `clean_pbp` to have already run (which itself requires
  `epa` to exist, since `clean_pbp`'s `success` column depends on `epa`,
  meaning `clean_pbp` runs strictly after the full EP/WP pipeline in
  `build_nflfastR_pbp()`'s function chain, not immediately after
  `add_nflscrapr_mutations`).

---

## Cross-cutting notes

**R → Python / polars gotchas observed across all 14 sections**

- **1-indexing vs 0-indexing.** Every `1:dplyr::n()` / `1:nrow()` index
  column (`clean_pbp`'s `index`, `add_nflscrapr_mutations`'s `pbp |>
  dplyr::mutate(index = 1:dplyr::n())`, `add_drive_results`'s/
  `add_series_data`'s `row = 1:dplyr::n()`) is **1-based**. A polars
  `with_row_index()` port is 0-based by default — any code comparing
  `row == 1` (first play of half, §7/§8) must compare to `0` after a direct
  `with_row_index()` port, or add 1 to match R semantics exactly if the
  value itself is retained/exported.
- **`dplyr::group_by()` + `mutate()` preserves original row order**; polars
  `group_by()` does NOT preserve order unless `maintain_order=True` is
  passed (and even then, operations that materialize a new frame per group
  and re-concat can still reorder rows within a group differently than
  dplyr's row-preserving mutate). Every `lag()`/`lead()`/`cumsum()` in this
  codebase (§1/§2/§4/§5/§7/§8/§9 aggregation, `add_nflscrapr_mutations`'s
  timeout/score running totals) implicitly assumes the frame stays in
  play-order-within-group; a polars port must either use `.over()` window
  expressions (which respect existing frame order, not group order) or
  explicitly re-sort after any `group_by().agg()`.
- **`na.rm=TRUE` / `stats::na.omit()` semantics.** R's `sum(x, na.rm=TRUE)`
  treats an all-NA vector as summing to `0`; polars `sum()` on an all-null
  Series returns `null`, not `0`, unless the column is explicitly
  `.fill_null(0)` first. This bites hardest in §9/§10's many `sum(...,
  na.rm=TRUE)` aggregations — a player-week with zero qualifying plays for a
  given stat family should end up `0` (matching R), which in polars
  requires an explicit `.fill_null(0)` pass, not reliance on `sum()`'s
  default behavior. Similarly, `dplyr::first(stats::na.omit(x))` /
  `dplyr::last(stats::na.omit(x))` (§7/§8's `fixed_drive_result`/
  `series_result` resolution) drop NAs before taking first/last — polars
  `.drop_nulls().first()`/`.last()` inside a `.over()` or `.agg()` context
  is the direct equivalent, but naive `.first()`/`.last()` without the
  drop-nulls step will pick up a null instead of the intended
  first/last-*non-null*.
- **`stringr`/base-R regex vs polars/Rust regex — lookaround support
  differs by engine, not just by "polars vs not-polars".** Base R
  `stringr::str_detect`/`str_extract` (used throughout §1, §2, §3, §6, §8,
  §14 — e.g. `clean_pbp`'s `big_parser`/`rush_finder`/`receiver_finder`,
  `fix_bad_games`'s `(?<=Timeout #[1-3] by )`, `fix_posteams`'s
  `(?=[:space:])`) is backed by ICU/PCRE-like regex with full lookaround
  (both lookahead AND lookbehind) support. Polars string ops are backed by
  Rust's `regex` crate, which has **no lookaround support at all** (neither
  lookahead nor lookbehind — this project's CLAUDE.md documents a lookahead
  workaround `(?i)prefix(?-i: NAMES)` for the case-toggle trick, but that
  does not help with genuine lookbehind assertions like `clean_pbp`'s
  parsers). Any function in this document using `(?<=...)` MUST be ported
  either via Python's `re`/`regex` module (both support lookbehind) applied
  outside the hot polars path, or rewritten as capture-group extraction +
  post-hoc slicing if a pure-polars pipeline is required. Do not attempt a
  literal 1:1 regex transcription into a polars `.str.extract()` call for
  any of: `clean_pbp`'s 7 parser constants, `fix_bad_games`'s timeout-team
  extractor, `add_nflscrapr_mutations`'s `tmp_timeout` extractor
  (`"(?<=by\\s)[:upper:]{2,3}(?=\\s)"`).
- **`dplyr::case_when` evaluates ALL branches' conditions for every row and
  takes the first `TRUE`, but does NOT short-circuit on already-matched
  rows within the same `case_when` call** — this matters for
  `translate_play_type_nfl`'s two-pass structure (§14): the SECOND
  `case_when` call explicitly re-checks `out == ""` for every row (not just
  unresolved ones) as its own independent condition, which is why it's
  written as two sequential calls rather than one — a polars
  `pl.when().then().otherwise()` chain has the same "first match wins,
  evaluated top to bottom" semantics as `case_when`, so this one ports
  cleanly, but a naive engineer might try to "optimize" by merging the two
  passes into one chain, which would break the qb_spike/qb_kneel override
  (which needs `out` from the first pass's *resolved* value, including the
  fallback resolution from the second pass' own earlier branches, before
  the override branches evaluate).
- **`data.table::fifelse` vs base `ifelse`**: several places
  (`fix_weird_pass_plays`, `calculate_player_stats_def`'s
  `fumble_recovery_1_player_id` construction) deliberately use
  `data.table::fifelse` instead of base `ifelse` specifically because base
  `ifelse` **silently coerces the result to `logical`/loses type** when the
  input vector has 0 rows (an edge case that bit production before) —
  `fifelse` preserves type. This has no bearing on a Python port (Python
  ternaries don't have this footgun) but explains why the R source
  deliberately picks one conditional-assignment function over the other in
  specific spots — don't read anything semantic into the choice beyond
  "type-safety on empty input."
- **`tidyr::fill(..., .direction = "up")` is a *grouped* backward-fill.**
  Used in `add_ep_variables` (`ep`, `tmp_posteam`) and `add_wp_variables`
  (`wp`, `vegas_wp`, `tmp_posteam`) to propagate a value from the next
  *real* play backward onto preceding pseudo-play rows (timeouts, STs
  penalty markers) that were deliberately set to `NA`. This must be grouped
  by `game_id` in a Python port (`.over("game_id")` semantics don't
  directly support fill — use `pl.col(...).fill_null(strategy="backward")`
  within a `.over()` context, or an explicit per-game loop/window).
- **Kickoff/PAT/timeout pseudo-play boundary handling recurs identically
  across at least 4 functions** (`add_drive_results`, `add_series_data`,
  `add_ep_variables`'s `st_penalty_i_1`/`st_penalty_i_2`, and the posteam-
  swap block duplicated verbatim in both §7 and §8) — these all encode the
  same underlying domain fact (a defensive/return touchdown's PAT is
  attributed to the scoring team, not the team that had the ball at snap;
  a kickoff replayed for penalty isn't a "real" prior play) via slightly
  different mechanisms (regex on `desc`, `lag`/`lead` chains, or explicit
  `case_when`). A Python port should resist the temptation to unify these
  into one shared abstraction unless the unification is proven
  behaviorally identical against real fixture data across all 4 sites —
  the R source itself does NOT share this logic (copy-pasted with minor
  variations), so byte-for-byte parity testing per call site is the safer
  initial port strategy; refactor only after parity is locked in with
  tests.
- **Cumulative/running-total columns are ALWAYS `.over("game_id")`, never
  global** — every `total_home_*`/`total_away_*` column in §5, the
  `total_home_score`/`total_away_score`/`total_home_timeouts_used`/
  `total_away_timeouts_used` columns in `add_nflscrapr_mutations`, and
  `fixed_drive`/`series` in §7/§8 all reset per game. Concatenating
  multiple games into one polars frame and computing any of these without
  an explicit `.over("game_id")` (or equivalent per-game grouping) silently
  leaks state across game boundaries — this is the single most consequential
  gotcha for a from-scratch port and should be a dedicated parity test
  (concat 2+ games, assert each cumulative column resets to its game-start
  value at the first row of every subsequent game).

**Inventory of external data files that must be vendored**

| Name | Source | Schema | Approx size |
|---|---|---|---|
| `scramble_fix` (sysdata) | Built from 3 vendored Excel files in `data-raw/` (Aaron Schatz / Football Outsiders charting data); NOT a runtime fetch. **Full list already vendored for this port** at `docs/superpowers/plans/2026-07-03-nflfastr-scramble-fix.csv` | single column `scramble_id` = `"{game_id}_{play_id}"` | 5,830 rows, ~140KB CSV |
| `nflfastR::teams_colors_logos` | Released package data, built via `nflreadr::load_teams()` (`data-raw/teams_colors_logos.R`) | ~36 rows × team metadata; only `team_abbr` used by `fix_posteams` | small (~36 rows) |
| `nflreadr::load_players()` | Released nflverse crosswalk (hosted on nflverse-data releases) | columns used across this doc: `gsis_id`, `esb_id`, `display_name`, `short_name`, `position`, `position_group`, `headshot` | one row per known NFL player, low tens of thousands of rows |
| `nflreadr::load_schedules()` | Released nflverse schedules/games table | columns used: `game_id`, `old_game_id`, `away_score`, `home_score`, `location`, `result`, `total`, `spread_line`, `total_line`, `div_game`, `roof`, `surface`, `temp`, `wind`, `home_coach`, `away_coach`, `stadium`, `stadium_id`, `gameday`, `season`, `game_type`, `week` | one row per game, 1999–present |
| `play_stats_{season}.rds` | `https://github.com/nflverse/nflverse-pbp/releases/download/playstats/play_stats_{season}.rds`, one file per season 1999–present | `game_id, season, week, play_id, stat_id, yards, team_abbr, player_name, gsis_player_id` | per-season RDS, moderate size (thousands of rows/season) |
| `fastrmodels::ep_model` / `wp_model` / `wp_model_spread` / `fg_model` (`mgcv::bam`) / `xpass_model` / `xyac_model` / `cp_model` | External R package `fastrmodels` (xgboost `.ubj`/raw-vector models + one `mgcv::bam` GAM) | model artifacts, not tabular data — sdv-py already carries equivalent trained artifacts under `nfl/models/*.ubj` per this repo's CLAUDE.md; verify feature order against `ep_model_select`/`wp_model_select`/`wp_spread_model_select` (§5) before treating as drop-in |
| `nflseedR` (whole package) | External R package, github.com/nflverse/nflseedR | division-rank + conference-seed standings computation, incl. all NFL tiebreaker rules | out of scope for this document — see §12 |
| `default_play` (sysdata) | `data-raw/default_play.R` / `data-raw/pbp_defaultplay.rds` | one placeholder full-schema row (~370 columns) used by `write_pbp()` to seed an empty DB table's column types | 1 row, ~370 cols — not needed for parity math, only for DB bootstrapping |

