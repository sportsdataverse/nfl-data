"""G-NFL-1: the pre-upload gate for REPROCESS run #1 (sdv-py quality program).

Runs on the rebuilt ``espn_nfl_pbp`` season files and must read 0 defects before
``PUBLISH=1`` uploads anything (ClaudeCowork ``plans/2026-10-08-sdv-py-quality-refactor/
plan-v2/REPROCESS.md``, run #1). Each check counts violating rows (or games); a season
passes when every count is 0.

    uv run python -m nfl_espn_build.gate --pbp-dir out/espn_nfl/pbp -s 2002 -e 2026

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
#: Rows that are not plays: a timeout or period marker after the last snap (ESPN logs the
#: timeouts called around an overtime walk-off touchdown AFTER it) scores EPA 0 by design.
_NOT_A_PLAY = r"(?i)^(timeout|end (of )?(period|half|game|regulation)|two[- ]minute warning)"
#: The 2005 season holds 266-286 games (C-NF-11: the file once held 17).
_GAMES_2005 = (266, 286)
#: ``penalty_1st_conv`` exists on > 0 rows a season from 2017 (C-M1).
_PENALTY_CONV_FROM = 2017


def _checks(pbp: pl.DataFrame, season: int) -> dict[str, int]:
    rush = pl.col("rush") == True  # noqa: E712
    yds = pl.col("yds_rushed")
    out: dict[str, int] = {}

    # opportunity_run is exactly a carry that reached 4 yards (was wrong on 88.5% of rushes)
    out["opportunity_run"] = pbp.filter(rush & (pl.col("opportunity_run") != (yds >= 4)).fill_null(True)).height

    # the three line-yards parts sum to the carry on every 4+ carry (C-H1 / C-NF-3)
    parts = pl.col("line_yards") + pl.col("second_level_yards") + pl.col("open_field_yards")
    out["line_yards_parts"] = pbp.filter(rush & (yds >= 4) & ((parts - yds).abs() > 1e-6).fill_null(True)).height

    # every game's last row carries end_of_half; a non-scoring last play scores epa == -ep
    last = pbp.sort(["game_id", "game_play_number"]).group_by("game_id", maintain_order=True).last()
    out["last_row_end_of_half_null"] = last.filter(pl.col("end_of_half").is_null()).height
    last_play = (
        pbp.filter(~pl.col("type.text").fill_null("").str.contains(_NOT_A_PLAY))
        .sort(["game_id", "game_play_number"])
        .group_by("game_id", maintain_order=True)
        .last()
    )
    out["last_play_epa_not_minus_ep"] = last_play.filter(
        (pl.col("scoring_play") != True)  # noqa: E712
        & pl.col("EP_start").is_not_null()
        & ((pl.col("EPA") + pl.col("EP_start")).abs() > 1e-6)
    ).height

    # td_play is false on every unscored reversed / nullified row
    out["td_play_unscored_reversal"] = pbp.filter(
        pl.col("text").str.contains(_REVERSED)
        & (pl.col("scoring_play") != True)  # noqa: E712
        & (pl.col("td_play") == True)  # noqa: E712
    ).height

    if season >= _PENALTY_CONV_FROM:
        out["penalty_1st_conv_absent"] = int((pbp["penalty_1st_conv"] == True).sum() == 0)  # noqa: E712
    if season == 2005:
        n = pbp["game_id"].n_unique()
        out["games_2005_out_of_range"] = int(not (_GAMES_2005[0] <= n <= _GAMES_2005[1]))
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
        counts = _checks(pl.read_parquet(f), season)
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
