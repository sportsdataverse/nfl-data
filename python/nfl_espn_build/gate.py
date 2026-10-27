"""G-NFL-1: the pre-upload gate for REPROCESS run #1 (sdv-py quality program).

Runs on the rebuilt ``espn_nfl_pbp`` season files and must read 0 defects before
``PUBLISH=1`` uploads anything (ClaudeCowork ``plans/2026-10-08-sdv-py-quality-refactor/
plan-v2/REPROCESS.md``, run #1). Each check counts violating rows (or games); a season
passes when every count is 0.

    uv run python -m nfl_espn_build.gate --pbp-dir out/espn_nfl/pbp --raw-dir ../nfl-raw -s 2002 -e 2026

Exit 0 when every season passes, 1 otherwise; one line per season and check either way.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import polars as pl

#: Reversal language in the play text. A scored row follows sdv-py's
#: ``_touchdown_did_not_stand`` (#840: a nullified TD followed by a try, or a reversal INTO
#: a touchdown, keeps ``td_play``), so only UNSCORED rows are held to ``td_play == False``.
_REVERSED = r"(?i)\b(reversed|nullified)\b"
#: A reversal INTO a touchdown: the text reports the touchdown after the reversal ("...REVERSED. ... recovers
#: at TEN 0. TOUCHDOWN."). ESPN leaves some of those unscored, but the play scored, so td_play holds.
_REVERSED_INTO_TD = r"(?i)\breversed\b.*\btouchdown\b"
#: ...unless the touchdown it reports did not stand either ("REVERSED ... TOUCHDOWN NULLIFIED by penalty").
_TD_DID_NOT_STAND = r"(?i)\btouchdown\b.*\b(nullified|no play)\b"
#: Completed games a season may skip for having no play text, and games it may keep as truncated feeds (no row carries
#: game_play_number), at the counts measured on nfl-raw 2026-10-27. A season over either count lost games the gate
#: cannot otherwise see: the expected set below comes from the same raw library the processor reads.
_STUB_GAMES = {2005: 251}
_STUB_GAMES_DEFAULT = 2
_PARTIAL_GAMES = {2002: 2, 2003: 12, 2004: 6, 2007: 1}
#: A try. sdv-py scores it on its own row (6.92 then the try's points), so a game that ends on one ends on a
#: scored play whose EPA is its points less the try's EP, never -EP.
_TRY = r"(?i)(extra point|two[- ]point|\b2pt\b)"
#: Rows that are not plays: a timeout or period marker after the last snap (ESPN logs the
#: timeouts called around an overtime walk-off touchdown AFTER it) scores EPA 0 by design.
_NOT_A_PLAY = r"(?i)^(timeout|end (of )?(period|half|game|regulation)|two[- ]minute warning)"
#: ``penalty_1st_conv`` exists on > 0 rows a season from 2017 (C-M1).
_PENALTY_CONV_FROM = 2017


def expected_games(raw_dir: str | Path, season: int) -> tuple[set[int], int, int]:
    """Every completed event of ``season`` whose ESPN plays carry text: the games a season file must hold.

    Replaces the fixed 2005 bound (C-NF-11): ESPN serves no play text for 2005 (17 of 268 games have it, on
    the site API and Core alike, probed 2026-10-27), so a rescrape cannot fill it, and every other season can
    lose games the same way. A stub game is skipped by the processor; a truncated ("partial") one is kept.
    """
    from nfl_espn_build.ingest import EspnStore
    from nfl_espn_build.process import status_state, summary_has_play_text

    store = EspnStore(str(Path(raw_dir) / "nfl" / "espn"))
    out, stubs, missing = set(), 0, 0
    for ev in store.season_events(season):
        summary = store.summary(season, int(ev["espn_event_id"]))
        if summary is None:
            missing += 1  # a crosswalked event the library has no summary for: a scrape gap
        elif status_state(summary) == "post":
            if summary_has_play_text(summary):
                out.add(int(ev["espn_event_id"]))
            else:
                stubs += 1
    return out, stubs, missing


def _checks(
    pbp: pl.DataFrame, season: int, expected: tuple[set[int], int, int] | None = None
) -> dict[str, int]:
    rush = pl.col("rush") == True  # noqa: E712
    yds = pl.col("yds_rushed")
    out: dict[str, int] = {}

    # opportunity_run is exactly a carry that reached 4 yards (was wrong on 88.5% of rushes)
    out["opportunity_run"] = pbp.filter(rush & (pl.col("opportunity_run") != (yds >= 4)).fill_null(True)).height

    # the three line-yards parts sum to the carry on every 4+ carry (C-H1 / C-NF-3)
    parts = pl.col("line_yards") + pl.col("second_level_yards") + pl.col("open_field_yards")
    out["line_yards_parts"] = pbp.filter(rush & (yds >= 4) & ((parts - yds).abs() > 1e-6).fill_null(True)).height

    # every game's last row carries end_of_half; a non-scoring last play scores epa == -ep. A truncated
    # ESPN feed (the processor's "partial": no row carries game_play_number) has no end to check.
    real = pl.col("game_play_number").is_not_null().any().over("game_id")
    n_partial = pbp.filter(~real)["game_id"].n_unique()
    out["partial_games_over_observed"] = max(0, n_partial - _PARTIAL_GAMES.get(season, 0))
    last = (
        pbp.filter(real)
        .sort(["game_id", "game_play_number"])
        .group_by("game_id", maintain_order=True)
        .last()
    )
    out["last_row_end_of_half_null"] = last.filter(pl.col("end_of_half").is_null()).height
    kind = pl.col("type.text").fill_null("")
    last_play = (
        pbp.filter(real & ~kind.str.contains(_NOT_A_PLAY) & ~kind.str.contains(_TRY))
        .sort(["game_id", "game_play_number"])
        .group_by("game_id", maintain_order=True)
        .last()
    )
    out["last_play_epa_not_minus_ep"] = last_play.filter(
        (pl.col("scoring_play") != True)  # noqa: E712
        & pl.col("EP_start").is_not_null()
        & ((pl.col("EPA") + pl.col("EP_start")).abs() > 1e-6)
    ).height

    # td_play is false on every unscored reversed / nullified row, unless the reversal went into a touchdown
    out["td_play_unscored_reversal"] = pbp.filter(
        pl.col("text").str.contains(_REVERSED)
        & ~(pl.col("text").str.contains(_REVERSED_INTO_TD) & ~pl.col("text").str.contains(_TD_DID_NOT_STAND))
        & (pl.col("scoring_play") != True)  # noqa: E712
        & (pl.col("td_play") == True)  # noqa: E712
    ).height

    if season >= _PENALTY_CONV_FROM:
        out["penalty_1st_conv_absent"] = int((pbp["penalty_1st_conv"] == True).sum() == 0)  # noqa: E712
    if expected is not None:
        games, stubs, missing = expected
        # the season file holds exactly the games the raw library can give (missing + extra), and the library lost
        # no more games to stub feeds or absent summaries than it held when the counts were measured
        have = set(pbp["game_id"].cast(pl.Int64).unique().to_list())
        out["games_vs_raw"] = len(games ^ have)
        out["stub_games_over_observed"] = max(0, stubs - _STUB_GAMES.get(season, _STUB_GAMES_DEFAULT))
        out["raw_summaries_missing"] = missing
    return out


def _qbr_feature_names_match() -> bool:
    """The bundled QBR booster is re-saved in the trainer's feature order (2.7, gap-C-083)."""
    import importlib.resources as resources

    import xgboost as xgb
    from sportsdataverse.nfl import model_vars

    booster = xgb.Booster()
    booster.load_model(str(resources.files("sportsdataverse.nfl") / "models" / "qbr_model.ubj"))
    return list(booster.feature_names or []) == list(model_vars.qbr_vars)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--pbp-dir", default="out/espn_nfl/pbp")
    ap.add_argument("--raw-dir", required=True, help="nfl-raw checkout: each season's expected games")
    ap.add_argument("-s", "--start", type=int, required=True)
    ap.add_argument("-e", "--end", type=int)
    args = ap.parse_args(argv)
    ok = _qbr_feature_names_match()
    print(f"qbr booster feature_names == qbr_vars: {ok}")
    for season in range(args.start, (args.end or args.start) + 1):
        f = Path(args.pbp_dir) / f"play_by_play_{season}.parquet"
        if not f.exists():
            print(f"{season}: MISSING {f}")
            ok = False
            continue
        counts = _checks(pl.read_parquet(f), season, expected_games(args.raw_dir, season))
        bad = {k: v for k, v in counts.items() if v}
        ok &= not bad
        print(
            f"{season}: {'PASS' if not bad else 'FAIL'} "
            + " ".join(f"{k}={v}" for k, v in counts.items())
        )
    print("G-NFL-1:", "PASS" if ok else "FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
