"""Hardcoded per-game repairs, ported from nflfastR's ``helper_scrape_nfl.R``.

Port of reference doc §1 (``fix_bad_games`` lines 358-421 and ``fix_posteams``
lines 423-462). In nflfastR both run inside ``get_pbp_nfl`` on a *single* game's
frame: ``fix_posteams()`` runs unconditionally first, then ``fix_bad_games()``
runs only when that game's raw feed had ``home_team == away_team`` (a scrape
bug flagged as ``bad_game <- 1`` at parse time — not a fixed list of game_ids;
it is re-derived at runtime from the frame's own ``home_team``/``away_team``
columns, which is exactly how :func:`apply_game_repairs` gates it here so it
stays safe to call on a concatenated multi-game frame).

Column availability at this pipeline stage (called immediately after
:func:`native_pbp.parse.parse_game`, before description/features/labels):

* ``fix_bad_games`` mutates four columns in nflfastR: ``td_team``,
  ``return_team``, ``fumble_recovery_1_team``, ``timeout_team``. Of those,
  **``td_team`` is deferred** — both of its R branches key on
  ``drive_how_ended_description``, a column the native Shield parser never
  produces at (or after) this stage, so there is no way to distinguish the
  offensive-TD case from the defensive-TD case without guessing. The other
  three columns (``return_team``, ``fumble_recovery_1_team``,
  ``timeout_team``) are fully ported. ``timeout_team``'s R source column is
  ``play_description``; the native frame's equivalent is ``desc`` (see
  ``native_pbp/parse.py``), so the regex is applied against ``desc``.
* ``fix_posteams`` re-derives ``posteam`` from a ``pre_play_by_play`` column
  (a ``"KC  1-10  NYJ 40"``-shaped narrative string) when present, else it is
  a no-op — literally, per the R source's own defensive
  ``if ("pre_play_by_play" %in% names(pbp))`` gate. The native Shield pipeline
  never emits a ``pre_play_by_play`` column (that field belongs to the older
  NFL GameCenter narrative-log scrape format ``helper_scrape_nfl.R`` targets,
  not the modern Shield API payload the native parser reads), so this port
  only implements the defensive gate; the regex-extraction branch is
  **deferred** — it is unreachable dead code for this pipeline, and faithfully
  reproducing the R regex's alternation-precedence quirk (the ``^`` anchor and
  the trailing lookahead each bind to only one alternative in the team-abbr
  disjunction, not all of them) with no real ``pre_play_by_play`` fixture to
  validate against would be guessing rather than porting.
"""
from __future__ import annotations

import polars as pl

# Columns fix_bad_games can actually repair with what the native frame carries
# at this pipeline stage (td_team is deferred — see module docstring).
_BAD_GAME_REPAIR_COLUMNS = ("return_team", "fumble_recovery_1_team", "timeout_team")


def fix_posteams(df: pl.DataFrame) -> pl.DataFrame:
    """Re-derive ``posteam`` from a ``pre_play_by_play`` narrative column.

    No-ops (returns ``df`` unchanged) when ``pre_play_by_play`` is absent —
    always true for the native Shield pipeline. See the module docstring for
    why the present-column branch is deferred rather than implemented.

    Args:
        df: A play-level frame, one or more games.

    Returns:
        ``df`` unchanged (the only reachable path for this port).
    """
    if "pre_play_by_play" not in df.columns:
        return df
    # Deferred — see module docstring. Left as a no-op rather than guessed at.
    return df


def fix_bad_games(df: pl.DataFrame) -> pl.DataFrame:
    """Row-wise corrections for games where the raw feed had ``home_team == away_team``.

    Faithful (partial — see module docstring) port of nflfastR's
    ``fix_bad_games``. Applies its mutation to every row passed in
    unconditionally (matching the R function, which itself does not check the
    ``bad_game`` condition — the caller does); :func:`apply_game_repairs` is
    what scopes the correction to only the affected game's rows on a
    multi-game frame.

    Args:
        df: A play-level frame carrying (a subset of) ``posteam``,
            ``home_team``, ``away_team``, ``fumble_lost``, ``return_team``,
            ``fumble_recovery_1_team``, ``timeout_team``, ``desc``.

    Returns:
        ``df`` with any of ``return_team`` / ``fumble_recovery_1_team`` /
        ``timeout_team`` present recomputed; columns absent from ``df`` (or
        missing a required dependency) are left untouched. ``td_team`` is
        never mutated (deferred).
    """
    exprs: list[pl.Expr] = []
    cols = set(df.columns)

    if {"return_team", "posteam", "home_team", "away_team"} <= cols:
        exprs.append(
            pl.when(pl.col("return_team").is_not_null())
            .then(
                pl.when(pl.col("posteam") == pl.col("home_team"))
                .then(pl.col("away_team"))
                .otherwise(pl.col("home_team"))
            )
            .otherwise(pl.col("return_team"))
            .alias("return_team")
        )

    if {"fumble_recovery_1_team", "fumble_lost", "posteam", "home_team", "away_team"} <= cols:
        # Games with zero fumbles leave this column 100%-null, which polars infers
        # as dtype Null (not Utf8) — cast explicitly so the when/otherwise chain
        # doesn't hit a Null/String supertype mismatch at collect time.
        exprs.append(
            pl.when(pl.col("fumble_recovery_1_team").is_not_null())
            .then(
                pl.when((pl.col("fumble_lost") == 1) & (pl.col("posteam") == pl.col("home_team")))
                .then(pl.col("away_team"))
                .when((pl.col("fumble_lost") == 1) & (pl.col("posteam") == pl.col("away_team")))
                .then(pl.col("home_team"))
                .when((pl.col("fumble_lost") == 0) & (pl.col("posteam") == pl.col("home_team")))
                .then(pl.col("home_team"))
                .when((pl.col("fumble_lost") == 0) & (pl.col("posteam") == pl.col("away_team")))
                .then(pl.col("away_team"))
                .otherwise(pl.lit(None, dtype=pl.Utf8))
            )
            .otherwise(pl.col("fumble_recovery_1_team").cast(pl.Utf8))
            .alias("fumble_recovery_1_team")
        )

    if {"timeout_team", "desc"} <= cols:
        exprs.append(
            pl.when(pl.col("timeout_team").is_not_null())
            .then(pl.col("desc").cast(pl.Utf8).str.extract(r"Timeout #[1-3] by ([A-Z]+)", 1))
            .otherwise(pl.col("timeout_team").cast(pl.Utf8))
            .alias("timeout_team")
        )

    if not exprs:
        return df
    return df.with_columns(exprs)


def apply_game_repairs(df: pl.DataFrame) -> pl.DataFrame:
    """Apply :func:`fix_posteams` then the gated :func:`fix_bad_games` repair.

    Idempotent and safe on a concatenated multi-game frame: the
    ``home_team == away_team`` "bad game" condition is derived per-row (these
    two columns are already game-constant, set once per game by
    :func:`native_pbp.parse.parse_game`), so only the affected game's rows are
    touched — every other row is returned byte-identical.

    Args:
        df: The post-``parse_game`` play frame (one or many games).

    Returns:
        ``df`` with ``posteam`` (via :func:`fix_posteams`, currently always a
        no-op — see module docstring) and, for any game whose rows show
        ``home_team == away_team``, ``return_team`` /
        ``fumble_recovery_1_team`` / ``timeout_team`` repaired.
    """
    if df.height == 0:
        return df

    df = fix_posteams(df)

    if not {"home_team", "away_team"} <= set(df.columns):
        return df
    repair_cols = [c for c in _BAD_GAME_REPAIR_COLUMNS if c in df.columns]
    if not repair_cols:
        return df

    bad_game = (
        pl.col("home_team").is_not_null()
        & pl.col("away_team").is_not_null()
        & (pl.col("home_team") == pl.col("away_team"))
    )
    fixed = fix_bad_games(df)
    return df.with_columns(
        [pl.when(bad_game).then(fixed[c]).otherwise(pl.col(c)).alias(c) for c in repair_cols]
    )
