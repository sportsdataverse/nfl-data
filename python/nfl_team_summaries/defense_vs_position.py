"""Stage 08 -- ``nfl_defense_vs_position``: what each defense allowed to QBs, RBs, WRs and TEs.

One row per ``(season, team_id, position_group)`` for the DEFENSE, from one season
of ``nfl_model_pbp`` plus that season's roster (``load_nfl_rosters``, the roster
stage 06 reads). The NFL twin of cfbfastR-cfb-data's stage 66. The rows are
``sportsdataverse.defense_vs_position(pbp, rosters, "nfl")``'s, passed through
unchanged -- its population too: regular season AND postseason, as in stage 07,
where stage 06's tables are regular season only. The producer adds only what it
owns:

* ``team_id`` as stage 06 carries it: the ESPN team id, Int64, through the
  vendored crosswalk (an unknown abbreviation raises), with ``pos_team`` (the
  nflverse abbreviation), ``team_name``, ``division`` and ``conference`` beside
  it. Player ids are gsis ids, text on both sides of the roster join; a float
  id in the pbp or the roster raises instead of joining through ``"12345.0"``.
* ``unattributed_target_share``: of the passes thrown against the defense
  (dropbacks that are neither sacks nor scrambles), the share on which the pbp
  names NO receiver. Those throws reach the QB row and no WR or TE row, so the
  WR and TE rates are **on targets naming a receiver**. Measured on the released
  seasons (2026-10-04), league-wide: 1-4% from 2009 on (throwaways; 4.1% in 2024,
  4.4% in 2025), 2-4% in 1999-2001, 9% in 2002 and **38-41% in 2003-2008**, when
  the pbp carries no receiver id on ANY incompletion or interception: in those
  six seasons a WR or TE row is completions only and its rates read high. The
  share is repeated on the defense's WR and TE rows and null on QB and RB.
  Nothing is imputed.
* ``<metric>_pct``: the percentile among qualifiers (``qualified``, the 3-game
  floor) within ``(season, position_group)``, over every team in the league,
  0-100 and oriented so that HIGHER = BETTER DEFENSE for every metric. A
  non-qualifier, a null metric and a cohort under ``MIN_COHORT_TEAMS`` get
  null, and none of them counts toward ``n``.

Direction of each metric (which end is the better defense):

====================================  ==============  =========================
metric                                better defense  a high ``_pct`` means
====================================  ==============  =========================
``epa_per_play_allowed``              LOWER           allowed less EPA per play
``success_rate_allowed``              LOWER           allowed fewer successes
``explosive_rate_allowed``            LOWER           allowed fewer explosives
``rush_yards_per_carry_allowed`` RB   LOWER           allowed fewer yards/carry
``yards_per_target_allowed`` WR, TE   LOWER           allowed fewer yards/target
``sack_rate_allowed`` QB              HIGHER          sacked the QB more often
====================================  ==============  =========================

``sack_rate_allowed`` is sacks per dropback the defense GOT, so it is the one
reversed column. The percentile is the F5 cohort helper's Weibull position,
``100 * (n + 1 - rank) / (n + 1)`` with rank 1 the best defense.

Floor: ``FLOOR`` (1999), the first ``nfl_model_pbp`` season. The roster does not
bind: measured over 1999-2025, at least 99.8% of carries and of named targets
join a roster position in every season. An earlier season is not built.

Publishing follows stage 07: only the season files this run wrote are uploaded.

Usage::

    python -m nfl_data_08_defense_vs_position --seasons 2025 --pbp-dir out/model_pbp --out out/nfl_defense_vs_position
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

import polars as pl
from sportsdataverse.defense_vs_position import OUTPUT_SCHEMA as _T1_SCHEMA

# ponytail: _plays is sdv-py's private population filter; importing it keeps the
# share on exactly the plays the rows count. uv.lock pins the commit; if sdv-py
# renames it this import fails at build time -- ask for a public name then.
from sportsdataverse.defense_vs_position import PBP_COLUMNS, _plays, defense_vs_position

from nfl_team_summaries.__main__ import REPO, _parse_seasons
from nfl_team_summaries.build import MIN_COHORT_TEAMS, _attach_cohort_percentiles, _teams_lookup
from nfl_team_summaries.crosswalk import attach_team_ids
from nfl_team_summaries.input import load_model_pbp, load_rosters

TAG = "nfl_defense_vs_position"
STEM = "defense_vs_position"

#: first season built: the first ``nfl_model_pbp`` season (the roster never binds)
FLOOR = 1999

#: metric -> True when a HIGHER value is the better defense (see the module table)
PCT_METRICS: dict[str, bool] = {
    "epa_per_play_allowed": False,
    "success_rate_allowed": False,
    "explosive_rate_allowed": False,
    "sack_rate_allowed": True,
    "rush_yards_per_carry_allowed": False,
    "yards_per_target_allowed": False,
}

_KEYS = ("season", "team_id")
#: the names stage 06's tables carry next to ``team_id``
_TEAM_COLS = ("pos_team", "team_name", "division", "conference")
#: what the stage reads off the pbp: sdv-py's columns plus the scramble flag
_PBP_COLS = (*PBP_COLUMNS["nfl"], "qb_scramble")

OUTPUT_SCHEMA: dict[str, pl.DataType] = {
    "season": pl.Int64(),
    "team_id": pl.Int64(),
    **{c: pl.Utf8() for c in _TEAM_COLS},
    **{c: t for c, t in _T1_SCHEMA.items() if c not in _KEYS},
    "unattributed_target_share": pl.Float64(),
    **{f"{m}_pct": pl.Float64() for m in PCT_METRICS},
}


def _unattributed_target_share(pbp: pl.DataFrame) -> pl.DataFrame:
    """Per ``(season, defteam)``: the share of passes thrown that name no receiver."""
    # sdv-py counts a scramble as a dropback; it is not a throw, so it leaves
    # before sdv-py's own population filter runs
    thrown = _plays(
        pbp.filter(pl.col("qb_scramble").fill_null(0) != 1).select(PBP_COLUMNS["nfl"]), "nfl"
    ).filter((pl.col("dropback") == True) & (pl.col("sack") == False))
    return thrown.group_by(_KEYS).agg(
        unattributed_target_share=pl.col("receiver_id").is_null().mean()
    )


def _attach_percentiles(df: pl.DataFrame) -> pl.DataFrame:
    """``<metric>_pct`` among qualifiers within ``position_group`` (one season)."""
    eligible = pl.col("qualified") == True
    ranks = {
        f"{m}_rank": pl.when(eligible)
        .then(pl.col(m))
        .rank(method="average", descending=higher_is_better)
        .over("position_group")
        for m, higher_is_better in PCT_METRICS.items()
    }
    return _attach_cohort_percentiles(
        df.with_columns(**ranks),
        cohort="position_group",
        rank_cols=list(ranks),
        suffix="_pct",
        min_cohort=MIN_COHORT_TEAMS,
    ).drop(list(ranks))


def defense_vs_position_table(pbp: pl.DataFrame, rosters: pl.DataFrame) -> pl.DataFrame:
    """The published table for ONE season's ``nfl_model_pbp`` and roster.

    Raises ``TypeError`` on a float team, game or player id (pbp or roster) and
    ``ValueError`` on a defense abbreviation the crosswalk does not know.
    """
    rows = defense_vs_position(pbp.select(PBP_COLUMNS["nfl"]), rosters, "nfl")
    if rows.height == 0:
        return pl.DataFrame(schema=OUTPUT_SCHEMA)
    share = _unattributed_target_share(pbp)
    for k in _KEYS:  # both sides still carry sdv-py's key: the nflverse abbreviation
        assert rows.schema[k] == share.schema[k], f"{k} {rows.schema[k]} != {share.schema[k]}"
    out = rows.join(share, on=_KEYS, how="left", validate="m:1").with_columns(
        unattributed_target_share=pl.when(pl.col("position_group").is_in(["WR", "TE"])).then(
            pl.col("unattributed_target_share")
        )
    )
    # stage 06's key: the ESPN id as text off the crosswalk (an unknown abbreviation
    # raises), then an integer parse -- strict, never through a float
    out = attach_team_ids(out.rename({"team_id": "defteam"}), "defteam", "team").with_columns(
        pl.col("team_id").cast(pl.Int64)
    )
    teams = _teams_lookup()
    assert out.schema["team_id"] == teams.schema["team_id"], (
        f"team_id {out.schema['team_id']} != {teams.schema['team_id']}"
    )
    out = (
        _attach_percentiles(out.join(teams, on="team_id", how="left", validate="m:1"))
        .select(list(OUTPUT_SCHEMA))
        .sort(*_KEYS, "position_group")
    )
    assert out.schema == pl.Schema(OUTPUT_SCHEMA), out.schema
    # two abbreviations of one franchise in a season would repeat a key
    assert out.select(*_KEYS, "position_group").is_duplicated().sum() == 0
    return out


def build_defense_vs_position(season: int, pbp_dir: str | Path | None = None) -> pl.DataFrame:
    """``nfl_defense_vs_position`` for ``season`` (:data:`OUTPUT_SCHEMA`).

    Reads the season's ``nfl_model_pbp`` (``pbp_dir`` if it holds the file, else
    the release asset) and its roster. Before ``FLOOR`` it loads nothing, logs
    why and returns the empty contract frame.
    """
    if season < FLOOR:
        logging.warning(
            "season %s: not built, nfl_model_pbp starts in %s (rosters carry positions throughout)",
            season,
            FLOOR,
        )
        return pl.DataFrame(schema=OUTPUT_SCHEMA)
    # the model_pbp schema is uniform across seasons; a missing column fails here, at the boundary
    pbp = load_model_pbp(season, pbp_dir).select(_PBP_COLS)
    stray = sorted(set(pbp["season"].unique()) - {season})
    if stray:
        # the percentile cohort is ONE season's position group
        raise ValueError(f"model_pbp_{season} holds season(s) {stray}, expected {season}")
    return defense_vs_position_table(pbp, load_rosters(season))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m nfl_data_08_defense_vs_position", description=__doc__.split("\n\n")[0]
    )
    parser.add_argument("--seasons", required=True, help="Single year (2025) or range (1999:2025).")
    parser.add_argument(
        "--out",
        default="out/nfl_defense_vs_position",
        help=f"Output dir: {STEM}_{{season}}.parquet.",
    )
    parser.add_argument(
        "--pbp-dir",
        default=None,
        help="Directory holding model_pbp_{season}.parquet (else the release asset).",
    )
    parser.add_argument(
        "--publish",
        action="store_true",
        help=f"Upload each season file written by THIS run to {TAG} on {REPO}.",
    )
    parser.add_argument(
        "--dry-run", action="store_true", help="With --publish: print what would upload."
    )
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args(argv)
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO, format="%(levelname)s %(message)s"
    )

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    for season in _parse_seasons(args.seasons):
        table = build_defense_vs_position(season, args.pbp_dir)
        if table.height == 0:
            logging.warning("season %s: no rows; nothing written", season)
            continue
        path = out / f"{STEM}_{season}.parquet"
        table.write_parquet(path)
        logging.info("wrote %s (%d rows x %d cols)", path, table.height, table.width)
        written.append(path)

    if args.publish:
        from nfl_model_publish.artifacts import upload_artifacts

        # one exact file per call: a stale season sitting in --out is never re-uploaded
        for path in written:
            result = upload_artifacts(
                path.parent, TAG, REPO, pattern=path.name, dry_run=args.dry_run
            )
            logging.info("published %d asset(s) to %s@%s", result["uploaded"], REPO, TAG)
    return 0


if __name__ == "__main__":
    sys.exit(main())
