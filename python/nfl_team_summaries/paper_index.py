"""Stage 09 -- ``nfl_paper_index_games``, and the season luck columns on ``nfl_team_summaries``.

The model is ``sportsdataverse.paper_index`` (Game on Paper's Paper Index: each
side's deserved-win share of a game from eight performance margins). The NFL
weights were fitted there and nothing is refitted here; this module adds no
formula. The NFL twin of cfbfastR-cfb-data's stage 67 (#138). It owns the
producer parts only:

* :func:`paper_index_games_table` -- the sdv-py rows for one season of
  ``espn_nfl_pbp``, unchanged, plus ``paper_index_span``. One row per team per
  SCORED game: completed, with a winner, both sides at 20 or more scrimmage
  snaps, both teams franchises (no Pro Bowl). A TIE has no row -- sdv-py drops
  it, so it is neither a game nor a win nor a loss anywhere downstream.
  Preseason, regular season and postseason alike: ``season_type`` 1 / 2 / 3
  says which (ESPN's library carries preseason games from 2026; the fit never
  saw one).
* :func:`season_games` -- the rows the summaries' luck columns sum: only the
  games the summaries' plays cover, cut by the plays' own game ids.
* :func:`attach_luck` -- sdv-py's ``deserved_wins`` roll-up of those rows joined
  onto the season's ``team_summaries``: ``deserved_wins``, ``luck_wins``
  (wins - deserved), ``luck_z``, their ranks, ``paper_index_games_n`` and
  ``paper_index_span``.

Input. The Paper Index reads ESPN-shape columns (``EPA_success``, ``havoc``,
``scoring_opp``, ``drive.isScore`` ...) that ``nfl_model_pbp`` does not carry,
so unlike stages 06-08 this one reads ``espn_nfl_pbp`` (2002-, ``FLOOR``): a
local ``play_by_play_{season}.parquet`` when ``--pbp-dir`` holds one, else the
release asset. Stage 06's tables are cut from ``nfl_model_pbp`` and keyed on
nflverse game ids; ``espn_nfl_pbp`` carries each game's ``nflverse_game_id``,
which is how one id list cuts both.

``paper_index_span`` (from sdv-py's ``TRAIN_SEASONS`` / ``HOLDOUT_SEASONS``, read
at call time, never copied): ``train`` -- that season's games were part of the
fit, so its shares are IN-SAMPLE; ``holdout`` -- scored out of sample at fit
time, though not fully clean (the EP model behind the EPA, success and
explosiveness inputs and the field-position curve were trained on spans that
include it); ``out_of_span`` -- never seen by the fit, never evaluated.

LEAKAGE: every column in :data:`LUCK_COLUMNS` is derived from game OUTCOMES (the
weights were fitted on who won, and ``luck_wins`` subtracts from the real win
count). None of them may be a model feature or a play metric. They are attached
AFTER ``build_team_summaries``, so the conference percentiles and
``league_averages`` in there never see them, and ``league_averages`` excludes
them by name as well; ``tests/test_paper_index.py`` fails if either is undone.

Usage::

    python -m nfl_data_09_paper_index_games --seasons 2025 --pbp-dir out/espn_nfl/pbp --out out/nfl_paper_index_games
"""

from __future__ import annotations

import argparse
import io
import logging
import sys
import warnings
from pathlib import Path

import polars as pl

from nfl_team_summaries.build import ESPN_FIRST_SEASON, _rank

TAG = "nfl_paper_index_games"
STEM = "paper_index_games"
LEAGUE = "nfl"

#: first season built: the first ``espn_nfl_pbp`` season
FLOOR = ESPN_FIRST_SEASON

RELEASE_URL = (
    "https://github.com/sportsdataverse/sportsdataverse-data/releases/download/"
    "espn_nfl_pbp/play_by_play_{season}.parquet"
)

#: the released pbp's id columns; all Int64 there, and published unchanged
_ID_COLUMNS = ("game_id", "pos_team_id", "homeTeamId", "awayTeamId")

#: how sdv-py's keep-floor UserWarning starts (a regex, matched at the start of
#: the message); stage 09 turns it into an error. The stage test replays the real
#: warning, so a reworded message upstream fails there instead of passing here.
_KEEP_FLOOR_WARNING = r"paper_index_games: inputs computable for"

#: every column :func:`attach_luck` adds to ``team_summaries``, in output order.
#: All outcome-derived: see LEAKAGE in the module docstring.
LUCK_COLUMNS: tuple[str, ...] = (
    "deserved_wins",
    "luck_wins",
    "luck_z",
    "luck_wins_rank",
    "luck_z_rank",
    "paper_index_games_n",
    "paper_index_span",
)

#: what :func:`attach_luck` rolls up when a season has no ESPN library (before ``FLOOR``)
_NO_GAMES = pl.DataFrame(
    schema={
        "season": pl.Int64,
        "team_id": pl.Int64,
        "won": pl.Boolean,
        "paper_share": pl.Float64,
    }
)


def _sdv():
    """``sportsdataverse.paper_index``, imported at call time.

    Stage 06 imports this module and stages 07 / 08 import stage 06's CLI, so a
    module-level import would stop all three on an sdv-py older than the port
    (sportsdataverse-py #661): a checkout whose venv has not been synced since the
    lock moved. Only a call that needs the Paper Index fails there.
    """
    import sportsdataverse.paper_index as pi

    return pi


def paper_index_span(season: int) -> str:
    """``train`` / ``holdout`` / ``out_of_span``: where ``season`` sits against the fit."""
    pi = _sdv()
    (t0, t1), (h0, h1) = pi.TRAIN_SEASONS[LEAGUE], pi.HOLDOUT_SEASONS[LEAGUE]
    if t0 <= season <= t1:
        return "train"
    return "holdout" if h0 <= season <= h1 else "out_of_span"


def load_espn_pbp(season: int, source_dir: str | Path | None = None) -> pl.DataFrame:
    """One season of ``espn_nfl_pbp``, the columns this stage reads: a local
    ``play_by_play_{season}.parquet`` if ``source_dir`` holds one, else the release
    asset. A download failure raises."""
    cols = [*_sdv().PBP_COLUMNS, "nflverse_game_id"]
    if source_dir is not None:
        local = Path(source_dir) / f"play_by_play_{season}.parquet"
        if local.exists():
            return pl.read_parquet(local, columns=cols)
    import requests

    resp = requests.get(RELEASE_URL.format(season=season), timeout=300)
    resp.raise_for_status()
    return pl.read_parquet(io.BytesIO(resp.content), columns=cols)


def paper_index_games_table(pbp: pl.DataFrame, season: int) -> pl.DataFrame:
    """sdv-py ``paper_index_games`` rows for ONE season's ``pbp``, plus ``paper_index_span``.

    ``game_id`` / ``team_id`` are the ESPN ids, Int64 as released, then sdv-py's
    ``GAMES_SCHEMA``, then the label. Empty (same columns) when the season has no
    scored game yet.

    Raises:
        ValueError: ``pbp`` has no rows, holds another season, or lacks a column the
            sdv-py function reads -- an empty or foreign file must not become the
            season's table.
        TypeError: an id column is not Int64 (the released pbp's dtype).
    """
    pi = _sdv()
    if pbp.height == 0:
        raise ValueError(f"espn_nfl_pbp {season} has no rows")
    seasons = pbp["season"].unique().to_list()
    if seasons != [season]:
        raise ValueError(f"espn_nfl_pbp {season} holds season(s) {seasons}, expected {season}")
    for c in _ID_COLUMNS:
        if c in pbp.columns and pbp.schema[c] != pl.Int64:
            raise TypeError(
                f"{c} is {pbp.schema[c]}: the released pbp carries Int64 ids and "
                f"{TAG} publishes them unchanged"
            )
    games = pi.paper_index_games(
        pbp.select([c for c in pi.PBP_COLUMNS if c in pbp.columns]), LEAGUE
    )
    return games.with_columns(paper_index_span=pl.lit(paper_index_span(season)))


def build_paper_index_games(season: int, pbp_dir: str | Path | None = None) -> pl.DataFrame:
    """``nfl_paper_index_games`` for ``season`` (:func:`paper_index_games_table`).

    Raises:
        ValueError: sdv-py's keep-floor warning fired (inputs computable for fewer
            than 98% of the completed, decided games). A warning there; here it
            would publish a season with games missing, so the stage fails. No full
            season 2002-2026 trips it; on a week-by-week cut only 2002 weeks 1-3 do
            (a truncated feed among the first 13-43 decided games), so a single
            broken game early in a season will stop this stage, and only this stage.
    """
    pbp = load_espn_pbp(season, pbp_dir)
    with warnings.catch_warnings():
        warnings.filterwarnings("error", message=_KEEP_FLOOR_WARNING, category=UserWarning)
        try:
            return paper_index_games_table(pbp, season)
        except UserWarning as feed_loss:
            raise ValueError(f"paper_index_games {season}: {feed_loss}") from feed_loss


def season_games(
    season: int, game_ids: pl.Series, pbp_dir: str | Path | None = None
) -> pl.DataFrame:
    """The Paper Index rows the luck columns sum: ``season``'s scored games among ``game_ids``.

    ``game_ids`` are the nflverse game ids of the plays stage 06 aggregates (its
    season-type filter already applied), so ONE id list decides which games the play
    metrics and the luck columns cover: a playoff game's share is in
    ``nfl_paper_index_games`` and in no regular-season table. Before ``FLOOR`` there
    is no ESPN library and the frame is empty.

    ``espn_nfl_pbp`` is published by another workflow than ``nfl_model_pbp``. When
    it is behind, the games it lacks are simply not summed -- ``paper_index_games_n``
    is the count that did enter -- and a warning says how many.

    Raises:
        TypeError: ``game_ids`` is not text (nflverse ids are).
        ValueError: a scored game carries no ``nflverse_game_id`` or two of them (it
            could not be placed, and a partial sum must not be published); or the
            pbp holds regular-season or postseason games yet none of ``game_ids`` --
            the ids stopped agreeing, or the file is another season's.
    """
    if season < FLOOR:
        return _NO_GAMES
    if game_ids.dtype != pl.Utf8:
        raise TypeError(f"game_ids is {game_ids.dtype}: nflverse game ids are text")
    pbp = load_espn_pbp(season, pbp_dir)
    games = paper_index_games_table(pbp, season)
    wanted = game_ids.unique()
    # the scored games' nflverse ids, one per game or the game cannot be placed
    ids = (
        pbp.select("game_id", "nflverse_game_id")
        .unique()
        .join(games.select("game_id").unique(), on="game_id", how="semi")
    )
    unplaced = ids.filter(pl.col("nflverse_game_id").is_null() | pl.col("game_id").is_duplicated())
    if unplaced.height:
        raise ValueError(
            f"espn_nfl_pbp {season}: scored game(s) {sorted(unplaced['game_id'].unique())[:5]} "
            "carry no single nflverse_game_id; refusing a luck sum that would leave them out"
        )
    kept = games.join(ids, on="game_id", how="left", validate="m:1").filter(
        pl.col("nflverse_game_id").is_in(wanted.implode())
    )
    if kept.height == 0 and games.filter(pl.col("season_type") != 1).height:
        raise ValueError(
            f"espn_nfl_pbp {season} holds none of the {wanted.len()} games the "
            "summaries cover, though it has regular-season or postseason games: the "
            "nflverse ids no longer agree, or this is not the season's file"
        )
    missing = (~wanted.is_in(pbp["nflverse_game_id"].unique().implode())).sum()
    if missing:
        logging.warning(
            "season %s: espn_nfl_pbp lacks %d of the %d games the summaries cover; the luck "
            "columns sum the rest (paper_index_games_n)",
            season,
            missing,
            wanted.len(),
        )
    return kept.drop("nflverse_game_id")


def attach_luck(team_data: pl.DataFrame, games: pl.DataFrame, season: int) -> pl.DataFrame:
    """Join the season's deserved wins and luck onto a ``team_summaries`` frame.

    ``games`` is :func:`season_games` output. The sums are sdv-py ``deserved_wins``;
    ``luck_wins + deserved_wins`` is the team's wins over the ``paper_index_games_n``
    games counted (a tie and a game the Paper Index cannot score are in neither).
    A team with no scored game gets ``paper_index_games_n = 0`` and null luck.
    Ranks are over the frame's teams that have a value, 1 = the luckiest, as the
    table's other ranks of a metric that can be absent.

    Raises:
        ValueError: ``games`` carries another season, or scored a team the frame has
            no row for (the team ids stopped agreeing).
        TypeError: ``team_id`` is not the same integer type on both sides.
    """
    # Sorted before the sums: float addition is not associative, and a join or a
    # filter upstream does not promise a row order. On a fixed frame the roll-up is
    # then bit-stable; the shares themselves are not (sdv-py's group_by reductions
    # move in the last bit from run to run), so compare sums with a tolerance.
    order = [c for c in ("team_id", "game_id") if c in games.columns]
    luck = _sdv().deserved_wins(games.sort(order))
    stray = sorted(set(luck["season"].unique()) - {season})
    if stray:
        raise ValueError(f"paper index games for {season} carry other seasons: {stray}")
    key, src = team_data.schema["team_id"], luck.schema["team_id"]
    if key != src or not key.is_integer():
        raise TypeError(
            f"team_id is {key} on team_summaries and {src} on the Paper Index rows: both "
            "are the ESPN id as an integer, never a float and never cast to meet"
        )
    orphans = luck.join(team_data, on="team_id", how="anti")
    if orphans.height:
        raise ValueError(
            f"{season}: Paper Index team(s) {sorted(orphans['team_id'])} have no "
            "team_summaries row; refusing to drop their games from the table"
        )
    luck = luck.select(
        "team_id", "deserved_wins", "luck_wins", "luck_z", paper_index_games_n=pl.col("games")
    )
    return (
        team_data.join(luck, on="team_id", how="left", validate="1:1")
        .with_columns(
            paper_index_games_n=pl.col("paper_index_games_n").fill_null(0),
            luck_wins_rank=_rank("luck_wins", descending=True),
            luck_z_rank=_rank("luck_z", descending=True),
            paper_index_span=pl.lit(paper_index_span(season)),
        )
        .select(*team_data.columns, *LUCK_COLUMNS)
    )


def main(argv: list[str] | None = None) -> int:
    # stage 06's CLI imports this module, so its names are taken here, not at the top
    from nfl_team_summaries.__main__ import REPO, _parse_seasons

    parser = argparse.ArgumentParser(
        prog="python -m nfl_data_09_paper_index_games", description=__doc__.split("\n\n")[0]
    )
    parser.add_argument("--seasons", required=True, help="Single year (2025) or range (2002:2025).")
    parser.add_argument(
        "--out", default=f"out/{TAG}", help=f"Output dir: {STEM}_{{season}}.parquet."
    )
    parser.add_argument(
        "--pbp-dir",
        default=None,
        help="Directory holding espn_nfl_pbp's play_by_play_{season}.parquet (else the release asset).",
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
        if season < FLOOR:
            logging.warning("season %s: not built, espn_nfl_pbp starts in %s", season, FLOOR)
            continue
        table = build_paper_index_games(season, args.pbp_dir)
        if table.height == 0:
            logging.warning("season %s: no scored game yet; nothing written", season)
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
