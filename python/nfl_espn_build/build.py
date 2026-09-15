"""Per-season dataset build: cached finals -> reshape -> drift-safe union -> parquet.

Outputs land under ``{out}/{dataset}/{stem}_{season}.parquet`` (``out/`` is
git-ignored in this repo; the release tag is the distribution channel, as for
every other nfl-data dataset). A season is read from the cache ONCE and every
requested dataset is cut from it.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import polars as pl

from nfl_espn_build import tendencies as _tendencies
from nfl_espn_build.config import REGISTRY, DatasetSpec
from nfl_espn_build.ingest import EspnStore
from nfl_espn_build.process import load_season_finals
from nfl_espn_build.reshape import bind_games, flat_block_frame
from nfl_espn_build.reshapers import RESHAPERS
from nfl_espn_build.tendencies import (
    FRANCHISE_TEAM_IDS,
    coach_careers,
    coach_tendencies,
    season_plays,
    team_tendencies,
)

log = logging.getLogger(__name__)


def _resolve_block(game: dict[str, Any], path: tuple[str, ...]) -> Any:
    node: Any = game
    for k in path:
        if not isinstance(node, dict):
            return None
        node = node.get(k)
    return node


# The processor puts a team ID in `pos_team` / `def_pos_team` -- a name-shaped
# column. As in the cfb family, the id moves to `<col>_id` and `<col>` becomes
# the display name, so the column means what it is named (and the espn_cfb_*
# consumers -- game-on-paper's Paper Index fit reads `pos_team_id` -- work
# unchanged).
_TEAM_ID_COLS = ("pos_team", "def_pos_team")


def is_exhibition(game: dict[str, Any]) -> bool:
    """Whether a final is the Pro Bowl: a side that is not one of the 32 franchises."""
    try:
        comps = game["header"]["competitions"][0]["competitors"]
    except (KeyError, IndexError, TypeError):
        return False
    ids = {int((c.get("team") or {}).get("id") or 0) for c in comps or []}
    return bool(ids) and not ids <= FRANCHISE_TEAM_IDS


def team_names(finals: list[dict[str, Any]]) -> pl.DataFrame:
    """``(team_id, team_name)`` over every final's header competitors."""
    rows: dict[int, str] = {}
    for game in finals:
        try:
            comps = game["header"]["competitions"][0]["competitors"]
        except (KeyError, IndexError, TypeError):
            continue
        for c in comps or []:
            team = c.get("team") or {}
            tid, name = team.get("id"), team.get("displayName")
            if tid is not None and name:
                rows.setdefault(int(tid), str(name))
    return pl.DataFrame(
        {"team_id": list(rows.keys()), "team_name": list(rows.values())},
        schema={"team_id": pl.Int64, "team_name": pl.Utf8},
    )


def resolve_team_names(df: pl.DataFrame, names: pl.DataFrame) -> pl.DataFrame:
    """Split ``pos_team`` / ``def_pos_team`` into ``<col>_id`` + readable ``<col>``.

    No-op when the frame carries neither column. The id column sits adjacent
    to the name in the original position, so the column order stays readable.
    """
    present = [c for c in _TEAM_ID_COLS if c in df.columns]
    if not present or df.height == 0:
        return df
    # an empty lookup still yields the normalized shape: ids in <col>_id, null names
    order: list[str] = []
    for col in df.columns:
        order.extend([f"{col}_id", col] if col in present else [col])
    for col in present:
        df = df.with_columns(pl.col(col).cast(pl.Int64, strict=False).alias(f"{col}_id")).drop(col)
        df = df.join(
            names.rename({"team_id": f"{col}_id", "team_name": col}), on=f"{col}_id", how="left"
        )
    return df.select(order)


class UsageCache:
    """Per-build memo of the build-time computations shared between datasets.

    ``create_usage_box`` per final (eleven usage datasets, one computation),
    the season's reshaped plays (both tendencies datasets) and the season's
    coach-per-game lookup.
    """

    def __init__(self, league: str = "nfl") -> None:
        self.league = league
        self._box: dict[int, dict[str, list[dict[str, Any]]]] = {}
        self._plays: pl.DataFrame | None = None
        self._coaches: dict[int, pl.DataFrame] = {}

    def plays(self, finals: list[dict[str, Any]]) -> pl.DataFrame:
        if self._plays is None:
            self._plays = season_plays(finals)
        return self._plays

    def coaches(self, season: int) -> pl.DataFrame:
        if season not in self._coaches:
            # resolved through the module so a test can stub the schedule lookup
            self._coaches[season] = _tendencies.coach_games(season)
        return self._coaches[season]

    def box(self, game: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
        key = int(game["id"])
        if key not in self._box:
            from sportsdataverse.football.usage_box import create_usage_box

            plays = game.get("plays") or []
            parts = game.get("play_participants") or []
            self._box[key] = create_usage_box(
                pl.from_dicts(plays, infer_schema_length=None) if plays else pl.DataFrame(),
                pl.from_dicts(parts, infer_schema_length=None) if parts else None,
                league=self.league,
            )
        return self._box[key]


def dataset_frame(
    spec: DatasetSpec, finals: list[dict[str, Any]], usage: UsageCache | None = None
) -> pl.DataFrame:
    """Build one dataset over a list of finals (one season, typically)."""
    frames: list[pl.DataFrame] = []
    usage = usage or UsageCache()
    if spec.tendencies in ("team", "coach"):
        plays = usage.plays(finals)
        if spec.tendencies == "team":
            df = team_tendencies(plays)
        else:
            season = int(plays["season"][0]) if plays.height else 0
            df = coach_tendencies(plays, usage.coaches(season))
        return resolve_team_names(df, team_names(finals))
    if spec.tendencies == "careers":
        raise ValueError("coach_careers is cut from the written coach seasons; use build_season")
    for game in finals:
        if spec.aggregate and is_exhibition(game):
            continue  # the Pro Bowl never enters a season leaderboard
        if spec.usage_section is not None:
            frames.append(flat_block_frame(usage.box(game).get(spec.usage_section), game))
        elif spec.block is not None:
            frames.append(flat_block_frame(_resolve_block(game, spec.block), game))
        else:
            frames.append(RESHAPERS[spec.reshaper](game))  # type: ignore[index]
    df = bind_games(frames)
    if df.height and spec.aggregate:
        from sportsdataverse.football.usage_box import aggregate_usage_box

        df = aggregate_usage_box(spec.usage_section, [df])  # type: ignore[arg-type]
    if df.height and "game_id" in df.columns:
        sort_keys = [c for c in ("season", "week", "game_id") if c in df.columns]
        df = df.sort(sort_keys, maintain_order=True)
    return resolve_team_names(df, team_names(finals))


def output_path(spec: DatasetSpec, season: int, out: str | Path) -> Path:
    if spec.tendencies == "careers":  # one file across seasons
        return Path(out) / spec.dataset / f"{spec.stem}.parquet"
    return Path(out) / spec.dataset / f"{spec.stem}_{season}.parquet"


def careers_frame(out: str | Path) -> pl.DataFrame:
    """``coach_careers`` from every ``coach_tendencies`` season parquet under ``out``."""
    spec = REGISTRY["coach_tendencies"]
    files = sorted((Path(out) / spec.dataset).glob(f"{spec.stem}_*.parquet"))
    seasons = [f.stem.rsplit("_", 1)[-1] for f in files]
    log.info("coach_careers: summing %d coach season(s) %s", len(files), seasons)
    return coach_careers(files)


def write_dataset(df: pl.DataFrame, spec: DatasetSpec, season: int, out: str | Path) -> Path | None:
    """Write the season parquet; ``None`` (and no file) for an empty frame."""
    path = output_path(spec, season, out)
    if df is None or df.height == 0:
        # never leave a previous cut behind for a season that now has no rows
        path.unlink(missing_ok=True)
        return None
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".parquet.tmp")
    df.write_parquet(tmp)
    tmp.replace(path)
    return path


def attach_crosswalk(finals: list[dict[str, Any]], store: EspnStore | None, season: int) -> None:
    """Overwrite each final's nflverse / Shield ids from the CURRENT crosswalk.

    The ids are stamped into the final at process time, but the crosswalk can
    improve (a matcher fix, a flex game getting its kickoff) without the game
    itself changing, so the build re-reads it rather than trusting the cache.
    """
    if store is None:
        return
    xw = {int(g["espn_event_id"]): g for g in store.season_events(season)}
    for final in finals:
        g = xw.get(int(final["id"]))
        if g is None:
            continue
        final["nflverse_game_id"] = g.get("game_id") or final.get("nflverse_game_id")
        final["shield_game_id"] = g.get("shield_game_id") or final.get("shield_game_id")


def build_season(
    datasets: list[str],
    season: int,
    *,
    cache_dir: str | Path,
    out: str | Path,
    store: EspnStore | None = None,
) -> dict[str, Path | None]:
    """Cut every requested dataset for one season from its cached finals."""
    finals = load_season_finals(cache_dir, season)
    attach_crosswalk(finals, store, season)
    log.info("season %s: %d cached finals", season, len(finals))
    written: dict[str, Path | None] = {}
    usage = UsageCache("nfl")
    for name in datasets:
        spec = REGISTRY[name]
        df = (
            careers_frame(out)
            if spec.tendencies == "careers"
            else dataset_frame(spec, finals, usage)
        )
        path = write_dataset(df, spec, season, out)
        written[name] = path
        log.info(
            "season %s %s: %d rows x %d cols -> %s",
            season,
            name,
            df.height,
            df.width,
            path if path else "(empty, not written)",
        )
    return written
