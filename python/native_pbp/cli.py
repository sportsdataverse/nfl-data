"""CLI for building model-PBP parquet files from the committed nfl/raw library.

Usage::

    python -m native_pbp build --seasons 2022:2024 --raw-dir .cache/nfl_raw --out out/model_pbp

Pass ``--enrich`` to run the EP/WP/CP/xYAC enrichment (the canonical
``nfl_model_pbp`` dataset) before each season's parquet is written::

    python -m native_pbp build --seasons 2023:2024 --raw-dir nfl/raw \\
        --out out/model_pbp --enrich

``build-playstats`` builds the long-format play-stats table (reference §13's
``build_playstats`` port) instead of the wide pbp frame::

    python -m native_pbp build-playstats --seasons 2022:2024 \\
        --raw-dir nfl/raw --out out/playstats
"""

from __future__ import annotations

import argparse
import warnings
from datetime import datetime, timezone
from pathlib import Path

import polars as pl
from nfl_espn_build.config import processing_version

from native_pbp.build import build_season as _build_season
from native_pbp.playstats import build_playstats_season as _build_playstats_season

#: api.nfl.com weekly-game-details ships only drive summaries for these seasons:
#: driveChart.plays is GAME_START/END_GAME plus a stray play for every 2000-2001 game,
#: 2002 weeks 1-15 and six late-1999 games (live re-probe 2026-09-27). nflverse pbp covers
#: them; from 2003 every Shield game is full.
#: Backfilled rows come from nflverse-data `pbp` (https://github.com/nflverse/nflverse-data),
#: © nflverse contributors, CC BY 4.0 (https://creativecommons.org/licenses/by/4.0/); credit
#: nflverse in the nfl_model_pbp release notes for 1999-2002.
_THIN_SHIELD_LAST_SEASON = 2002
#: ponytail: a play-count heuristic. Full games log ~150+ plays and the thin payloads 1-70,
#: so a real game under 100 plays would be swapped for nflverse's rows and a thin payload of
#: 100+ kept. Upgrade path: compare against the payload's own sum(driveChart.drives[].plays).
_MIN_GAME_PLAYS = 100
#: nflverse rows the Shield build drops as TIMEOUT markers (timeouts and two-minute
#: warnings). 2001+ nflverse types them play_type_nfl "TIMEOUT" (play_type "no_play");
#: 1999-2000 carry only the desc, with play_type and often timeout null. A real play that
#: nflverse also flags timeout == 1 opens with its clock, "(3:52) ...", and is kept.
_MARKER_DESC = r"(?i)^\s*(timeout\b|two-minute warning)"
#: Build columns nflverse lacks (or ships in another shape) but can derive.
#: ponytail: tackled_for_loss / touchdown are 0/1 flags standing in for per-play stat-id
#: counts -- exact except on multi-TFL / multi-TD plays. The other Shield-only columns
#: (extra_point_*/field_goal_*/two_point_* flags, misc_yards, lateral recovery yards,
#: def_tackles_for_loss_yards, play_seq, shield_play_type, special_teams_play_type) stay
#: null for backfilled games.
_DERIVED = {
    # the build's 1/0, 0 when posteam is null (shield_pbp/parse.py:504)
    "home": lambda: (pl.col("posteam") == pl.col("home_team")).fill_null(False),
    "def_tackles_for_loss": lambda: pl.col("tackled_for_loss"),
    "td_ids_touchdown": lambda: pl.col("touchdown"),
}
#: Null-typed in stub-only seasons (so nflverse's Float64 would leak through); the Shield
#: build and the published 2003/2004 assets type them Int64.
_INT64_YARDS = (
    "lateral_receiving_yards",
    "fumble_recovery_2_yards",
    "lateral_rushing_yards",
    "yards_after_catch",
)


def _type_null_columns(df: pl.DataFrame) -> pl.DataFrame:
    """Give every all-null (``Null``-typed) column the dtype it has in the seasons that carry it.

    A column no play of the season fills (2003-2026 ``tackle_with_assist_2_*``, 2005 ``air_yards``,
    ...) is built as polars' ``Null`` type and was published that way, which readers that check a
    schema contract refuse. Yards are Int64 in every published season and names / ids / teams String,
    so those are cast: that covers every Null column of the 1999-2026 release. Another all-null
    column (a test build's ``desc``, ``roof`` without a schedule lookup) is left as it is.
    """
    target = {}
    for c, dt in df.schema.items():
        if dt != pl.Null:
            continue
        if c in _INT64_YARDS or c.endswith("_yards"):
            target[c] = pl.Int64
        elif c.endswith(("_id", "_name", "_team")):
            target[c] = pl.String
    return df.with_columns([pl.col(c).cast(dt) for c, dt in target.items()])


def _backfill_thin_games(df: pl.DataFrame, season: int, raw_dir: str | Path) -> pl.DataFrame:
    """Swap Shield stub games for nflverse pbp rows conformed to the build schema.

    Only seasons up to ``_THIN_SHIELD_LAST_SEASON``: later seasons pass through with no
    nflverse fetch, so a live or partial current-season game is never taken for a stub.
    A game with fewer than ``_MIN_GAME_PLAYS`` rows is replaced by its nflverse rows (minus
    the timeout / two-minute-warning markers the Shield build drops); a game with no play
    data anywhere (a raw shell, or a stub nflverse lacks) is dropped. Prints one line per
    season with the backfilled count and the games with no data.
    """
    if season > _THIN_SHIELD_LAST_SEASON or df.height == 0:
        return df
    counts = df.group_by("game_id").len()
    full = counts.filter(pl.col("len") >= _MIN_GAME_PLAYS)["game_id"]
    raw_games = {p.stem for p in Path(raw_dir, str(season)).glob(f"{season}_*.json")}
    thin = (raw_games | set(counts["game_id"])) - set(full)
    if not thin:
        return df

    from sportsdataverse.nfl import load_nfl_pbp

    nv = load_nfl_pbp([season])
    if not nv.schema["game_id"] == df.schema["game_id"] == pl.String:
        raise TypeError(
            f"game_id dtype: nflverse {nv.schema['game_id']} vs build {df.schema['game_id']}"
        )
    is_timeout = (pl.col("play_type_nfl") == "TIMEOUT").fill_null(False)
    is_marker = is_timeout | pl.col("desc").fill_null("").str.contains(_MARKER_DESC)
    nv = nv.filter(pl.col("game_id").is_in(sorted(thin)), ~is_marker)
    # nflverse and the Shield build both name relocated clubs by their modern LA/LAC/LV in the
    # team columns (sportsdataverse-py #1028); nflverse has "" for no team on some 1999-2000 non-play rows
    team_cols = [
        c
        for c, dt in nv.schema.items()
        if dt == pl.String and (c in ("posteam", "defteam") or c.endswith("_team"))
    ]
    nv = nv.with_columns(pl.col(team_cols).replace({"": None}))
    target = {c: pl.Int64 if c in _INT64_YARDS else dt for c, dt in df.schema.items()}
    # polars' strict cast truncates 1.5 -> 1 silently: refuse a fractional float bound for Int64
    to_int = [
        c
        for c, dt in target.items()
        if dt.is_integer() and c not in _DERIVED and c in nv.columns and nv.schema[c].is_float()
    ]
    fractional = nv.select((pl.col(to_int) % 1 != 0).sum()).row(0, named=True)
    if any(fractional.values()):
        bad = {c: n for c, n in fractional.items() if n}
        raise ValueError(f"model_pbp {season}: fractional nflverse values in Int64 columns: {bad}")
    cols = []
    for c, dt in target.items():
        expr = _DERIVED[c]() if c in _DERIVED else pl.col(c) if c in nv.columns else pl.lit(None)
        # a stub-only season leaves many build columns Null-typed: keep nflverse's dtype there
        # (a cast to Null wipes the values); the diagonal_relaxed concat unifies the rest
        cols.append((expr if dt == pl.Null else expr.cast(dt)).alias(c))
    backfill = nv.select(cols)
    lost = sorted(thin - set(backfill["game_id"]))
    print(
        f"model_pbp {season}: backfilled {backfill['game_id'].n_unique()} thin Shield game(s) "
        f"from nflverse pbp; no play data anywhere: {lost}"
    )
    kept = df.filter(pl.col("game_id").is_in(full.implode()))
    return pl.concat([kept, backfill], how="diagonal_relaxed").sort("game_id", maintain_order=True)


#: nflfastR ``clean_pbp``'s player columns that nfl_model_pbp ships (nflverse pbp names and order).
_PLAYER_ID_COLUMNS = ("passer", "passer_id", "rusher", "rusher_id", "receiver", "receiver_id")

#: What ``clean_nfl_pbp`` reads to resolve those six; the rest of its inputs default.
_PLAYER_ID_INPUTS = (
    "game_id",
    "play_id",
    "season",
    "posteam",
    "home_team",
    "desc",
    "qb_scramble",
    "passer_player_name",
    "passer_player_id",
    "rusher_player_name",
    "rusher_player_id",
    "receiver_player_name",
    "receiver_player_id",
    "fumbled_1_player_name",
    "fumbled_1_player_id",
)


def _add_player_ids(df: pl.DataFrame) -> pl.DataFrame:
    """Append nflfastR ``clean_pbp``'s ``passer`` / ``rusher`` / ``receiver`` names and ids.

    ``clean_pbp`` names each player from ``desc`` and gives the name the mode stat id within
    (posteam, season), which is why this runs on a whole season. That fills the 2003-2008
    incompletions, whose Shield stats carry no pass target, and it moves a 1999-2005 charted
    scramble's QB from ``rusher`` to ``passer`` (nflfastR #536; nflverse's 1999-2004 pbp
    release predates that fix). sdv-py's port (``clean_nfl_pbp``) runs on a copy of the
    columns it needs, so none of the columns it would also rewrite (``desc``, ``success``,
    team codes, ...) change here.

    Known difference from nflverse: nflfastR tells 2020 HOU's David Johnson (#31) and Duke
    Johnson (#25) apart by the jersey number in ``desc``. The Shield ``desc`` carries none, so
    their 35 carries share one ``rusher_id``.
    """
    from sportsdataverse.nfl import clean_nfl_pbp

    if df.height == 0:
        return df.with_columns([pl.lit(None, pl.String).alias(c) for c in _PLAYER_ID_COLUMNS])
    src = df.select([c for c in _PLAYER_ID_INPUTS if c in df.columns])
    # clean_nfl_pbp requires epa and home_team (for success / home_opening_kickoff);
    # neither feeds a player column, so nulls do
    src = src.with_columns(epa=pl.lit(None, pl.Float64))
    if "home_team" not in src.columns:
        src = src.with_columns(home_team=pl.lit(None, pl.String))
    # An all-null column is Null-typed, which clean_nfl_pbp's string and numeric ops reject.
    numeric = {"season": pl.Int64, "play_id": pl.Int64, "qb_scramble": pl.Int64}
    src = src.with_columns(
        [pl.col(c).cast(numeric.get(c, pl.String)) for c, dt in src.schema.items() if dt == pl.Null]
    )
    out = clean_nfl_pbp(src)  # keeps the input row order (it restores it after its joins)
    if out.height != df.height:
        raise ValueError(f"clean_nfl_pbp returned {out.height} rows for {df.height}")
    return df.with_columns([out[c] for c in _PLAYER_ID_COLUMNS])


#: nflfastR ``add_game_data``'s schedule columns (R/helper_add_game_data.R), schedule names.
#: ``total`` is the final combined score (``total_line`` is the betting line).
_SCHEDULE_GAME_COLUMNS = (
    "old_game_id",
    "gameday",
    "location",
    "total",
    "div_game",
    "surface",
    "temp",
    "wind",
    "home_coach",
    "away_coach",
    "stadium_id",
    "stadium",
)
#: add_game_data writes the schedule's ``stadium`` as ``game_stadium`` and ``gameday`` as
#: ``game_date``; pbp's own ``stadium`` is the Shield payload's venue (see _game_payload).
_SCHEDULE_RENAME = {"gameday": "game_date", "stadium": "game_stadium"}
_INT_GAME_COLUMNS = ("total", "div_game", "temp", "wind")
#: The 16 game columns nfl_model_pbp ships, in nflverse pbp order.
_GAME_COLUMNS = (
    "old_game_id",
    "game_date",
    "start_time",
    "stadium",
    "stadium_id",
    "game_stadium",
    "weather",
    "location",
    "total",
    "div_game",
    "surface",
    "temp",
    "wind",
    "home_coach",
    "away_coach",
    "nfl_api_id",
)
_JERSEY_COLUMNS = (
    "passer_jersey_number",
    "rusher_jersey_number",
    "receiver_jersey_number",
    "jersey_number",
)


def _build_schedule_lookup(season: int) -> dict[str, dict]:
    """Build a ``{game_id: {roof, spread_line, total_line, <game columns>}}`` map for *season*.

    These game-level fields are absent from the Shield feed ``native_pbp`` parses;
    nflverse sources them from the schedule (Lee Sharpe's games file). Without
    them ``spread_line``/``total_line`` are null and ``vegas_wp`` falls back to a
    default spread (the 4th-down decision step is also skipped). The
    ``_SCHEDULE_GAME_COLUMNS`` ride along for :func:`_add_game_columns`. Degrades to an
    empty map — leaving the fields null, the prior behavior — with a
    ``RuntimeWarning`` if the schedule can't be loaded; a betting-line lookup must
    never fail the build.
    """
    try:
        from sportsdataverse.nfl import load_nfl_schedule

        sched = load_nfl_schedule([season])
        if not isinstance(sched, pl.DataFrame):
            sched = pl.from_pandas(sched)
        want = ("game_id", "roof", "spread_line", "total_line", *_SCHEDULE_GAME_COLUMNS)
        keep = [c for c in want if c in sched.columns]
        if "game_id" not in keep:
            return {}
        # `keep` drops any column absent from the schedule, so a reader's .get(...)
        # returns None for a missing field (the intended null-degrade).
        return {row.pop("game_id"): row for row in sched.select(keep).iter_rows(named=True)}
    except Exception as exc:  # network / schema / loader failure → degrade, never fail the build
        warnings.warn(
            f"native_pbp build: schedule lookup failed for {season} "
            f"({type(exc).__name__}: {exc}); spread_line/total_line will be null",
            RuntimeWarning,
            stacklevel=2,
        )
        return {}


#: nflverse publishes weekly rosters from this season; before it only the season roster.
_FIRST_WEEKLY_ROSTER_SEASON = 2002


def _build_jersey_lookup(season: int) -> pl.DataFrame | None:
    """``(gsis_id, week, jersey_number)`` for *season* from the nflverse rosters.

    nflfastR reads jersey numbers off ``desc`` ("12-T.Brady"); the Shield ``desc`` has
    none, so they come from the rosters, keyed on gsis id (never on a name). Rows with a
    ``week`` are the weekly roster (2002+; a trade or renumbering changes the number
    mid-season); rows with a null ``week`` are the season roster, the fallback for a
    player-week the weekly roster lacks. A key with two numbers keeps one row with a null
    number, so it stays null rather than falling back to the season roster.
    Degrades to ``None`` (null jersey columns) with a ``RuntimeWarning`` if a roster
    can't be loaded.
    """

    def _one_number(r: pl.DataFrame, key: list[str]) -> pl.DataFrame:
        r = r.filter(
            pl.col("gsis_id").is_not_null() & pl.col("jersey_number").is_not_null()
        ).unique()
        ambiguous = pl.len().over(key) > 1
        return r.with_columns(
            pl.when(ambiguous.not_()).then("jersey_number").alias("jersey_number")
        ).unique()

    try:
        from sportsdataverse.nfl import load_nfl_rosters, load_nfl_weekly_rosters

        cols = [pl.col("gsis_id").cast(pl.String), pl.col("jersey_number").cast(pl.Int64)]
        out = _one_number(load_nfl_rosters([season]).select(cols), ["gsis_id"]).select(
            "gsis_id", pl.lit(None, pl.Int64).alias("week"), "jersey_number"
        )
        if season >= _FIRST_WEEKLY_ROSTER_SEASON:
            weekly = load_nfl_weekly_rosters([season]).select(
                cols[0], pl.col("week").cast(pl.Int64), cols[1]
            )
            out = pl.concat([_one_number(weekly, ["gsis_id", "week"]), out])
        return out
    except Exception as exc:  # network / schema / loader failure → degrade, never fail the build
        warnings.warn(
            f"native_pbp build: roster lookup failed for {season} "
            f"({type(exc).__name__}: {exc}); jersey numbers will be null",
            RuntimeWarning,
            stacklevel=2,
        )
        return None


def _game_payload(raw_dir: str | Path, season: int) -> pl.DataFrame:
    """nflfastR's game-payload columns, one row per raw game file of *season*.

    ``nfl_api_id`` is the Shield game id, ``stadium`` the venue name, ``weather`` the
    summary's weather string (whitespace squished, as nflverse ships it) and
    ``start_time`` the actual kickoff, rendered like nflverse: US Eastern
    ``"9/5/24, 20:44:42"`` (seconds truncated).
    """
    import json

    rows = []
    for p in sorted(Path(raw_dir, str(season)).glob(f"{season}_*.json")):
        g = json.loads(p.read_text(encoding="utf-8"))
        s = g.get("summary") or {}
        rows.append(
            {
                "game_id": p.stem,
                "nfl_api_id": g.get("id"),
                "start_time": s.get("startTime"),
                "weather": s.get("weather"),
                "stadium": (g.get("venue") or {}).get("name"),
            }
        )
    df = pl.DataFrame(rows, schema=dict.fromkeys(rows[0] if rows else ["game_id"], pl.String))
    if not rows:
        return df
    kickoff = (
        pl.col("start_time")
        .str.replace(r"(\.\d+)?Z$", "")
        .str.to_datetime("%Y-%m-%dT%H:%M:%S", strict=False)
        .dt.replace_time_zone("UTC")
        .dt.convert_time_zone("America/New_York")
    )
    return df.with_columns(
        kickoff.dt.strftime("%-m/%-d/%y, %H:%M:%S").alias("start_time"),
        pl.col("weather").str.replace_all(r"\s+", " ").str.strip_chars(),
    )


def _add_game_columns(
    df: pl.DataFrame, season: int, raw_dir: str | Path, schedule_lookup: dict | None
) -> pl.DataFrame:
    """Append the 16 ``_GAME_COLUMNS`` (nflfastR ``add_game_data`` + its game payload fields).

    Schedule fields come from *schedule_lookup* (null without one) and the payload fields
    from the raw game files, both joined on ``game_id``.
    """
    sched_schema = {
        "game_id": pl.String,
        **{c: pl.Int64 if c in _INT_GAME_COLUMNS else pl.String for c in _SCHEDULE_GAME_COLUMNS},
    }
    sched = pl.DataFrame(
        [
            {"game_id": g, **{c: m.get(c) for c in _SCHEDULE_GAME_COLUMNS}}
            for g, m in (schedule_lookup or {}).items()
        ],
        schema=sched_schema,
    ).rename(_SCHEDULE_RENAME)
    games = _game_payload(raw_dir, season)
    if "nfl_api_id" not in games.columns:  # no raw files: payload columns stay null
        games = games.with_columns(
            pl.lit(None, pl.String).alias(c)
            for c in ("nfl_api_id", "start_time", "weather", "stadium")
        )
    out = df.drop(_GAME_COLUMNS, strict=False)
    for right in (sched, games):
        assert out.schema["game_id"] == right.schema["game_id"] == pl.String
        out = out.join(right, on="game_id", how="left", maintain_order="left")
    if out.height != df.height:
        raise ValueError(f"game-column join changed the row count: {df.height} -> {out.height}")
    return out.select(*[c for c in out.columns if c not in _GAME_COLUMNS], *_GAME_COLUMNS)


def _add_jersey_numbers(df: pl.DataFrame, jerseys: pl.DataFrame | None) -> pl.DataFrame:
    """``passer/rusher/receiver_jersey_number`` by (gsis id, week), else by gsis id from the
    season roster, and nflfastR's ``jersey_number`` (the passer's, else the rusher's)."""
    if jerseys is None:
        jerseys = pl.DataFrame(
            schema={"gsis_id": pl.String, "week": pl.Int64, "jersey_number": pl.Int64}
        )
    weekly = jerseys.filter(pl.col("week").is_not_null())
    season = jerseys.filter(pl.col("week").is_null()).drop("week")
    out = df.drop(_JERSEY_COLUMNS, strict=False)
    for role in ("passer", "rusher", "receiver"):
        k, col = f"{role}_id", f"{role}_jersey_number"
        # `_wk` marks a weekly-roster hit, even an ambiguous one (null number): only a player-week
        # the weekly roster lacks falls back to the season roster.
        wk = weekly.rename({"gsis_id": k, "jersey_number": col}).with_columns(_wk=pl.lit(True))
        ss = season.rename({"gsis_id": k, "jersey_number": "_ss"})
        for key, right in ((k, wk), ("week", wk), (k, ss)):
            assert out.schema[key] == right.schema[key], (key, out.schema[key], right.schema[key])
        out = (
            out.join(wk, on=[k, "week"], how="left", maintain_order="left")
            .join(ss, on=k, how="left", maintain_order="left")
            .with_columns(pl.when(pl.col("_wk").is_null()).then("_ss").otherwise(col).alias(col))
            .drop("_wk", "_ss")
        )
    if out.height != df.height:
        raise ValueError(f"jersey join changed the row count: {df.height} -> {out.height}")
    return out.with_columns(
        pl.coalesce("passer_jersey_number", "rusher_jersey_number").alias("jersey_number")
    )


def build_season(
    season: int,
    raw_dir: str | Path,
    out_dir: str | Path,
    *,
    enrich: bool = False,
    schedule_lookup: dict | None = None,
    jersey_lookup: pl.DataFrame | None = None,
) -> Path:
    """Build one season's model-PBP parquet and write it to *out_dir*.

    Seasons up to 2002 swap Shield's thin (stub) games for nflverse pbp rows first; see
    :func:`_backfill_thin_games`.

    Args:
        season: NFL season year (e.g. 2024).
        raw_dir: Root directory of the committed per-game JSON library.
            Per-game files are expected at ``{raw_dir}/{season}/*.json``.
        out_dir: Output directory.  The file is written as
            ``{out_dir}/model_pbp_{season}.parquet``, stamped with
            ``nfl_espn_build.config.processing_version()`` in its file-level metadata.
        enrich: When ``True``, run the nflfastR-faithful EP/WP/CP/xYAC
            enrichment (``sportsdataverse.nfl.ep_wp.enrich_nfl_pbp`` with
            ``method="lead_diff"``) on the build frame before writing it.
            The build frame already satisfies enrich's
            ``NFLVERSE_FRAME_CONTRACT``.  When ``False`` (default), the raw
            build frame is written unchanged.
        schedule_lookup: Optional ``{game_id: {roof, spread_line, total_line}}``
            map supplying the game-level fields the Shield feed omits. ``None``
            (default) leaves them null — kept null-by-default so unit tests stay
            hermetic; ``main()`` builds it from the nflverse schedule.
        jersey_lookup: Optional ``(gsis_id, week, jersey_number)`` frame for the jersey
            columns (:func:`_build_jersey_lookup`). ``None`` (default) leaves them null.

    Returns:
        Path to the written parquet file.
    """
    raw_dir = Path(raw_dir)
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    df = _build_season(season, raw_dir=raw_dir, schedule_lookup=schedule_lookup)
    df = _backfill_thin_games(df, season, raw_dir)
    df = _add_player_ids(df)

    if enrich and df.height:
        from sportsdataverse.nfl.ep_wp import enrich_nfl_pbp

        df = enrich_nfl_pbp(df, method="lead_diff")
    if df.height:
        df = _add_jersey_numbers(
            _add_game_columns(df, season, raw_dir, schedule_lookup), jersey_lookup
        )
    df = _type_null_columns(df)

    out_path = out_dir / f"model_pbp_{season}.parquet"
    # the stamp nfl_model_publish's manifest reads back: which library state cut this season
    df.write_parquet(
        out_path,
        metadata={
            "processing_version": processing_version(),
            "season": str(season),
            "generated_at_utc": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC"),
        },
    )
    return out_path


def build_playstats_season(
    season: int,
    raw_dir: str | Path,
    out_dir: str | Path,
) -> Path:
    """Build one season's long-format play-stats parquet and write it to *out_dir*.

    Args:
        season: NFL season year (e.g. 2024).
        raw_dir: Root directory of the committed per-game JSON library.
            Per-game files are expected at ``{raw_dir}/{season}/*.json``.
        out_dir: Output directory. The file is written as
            ``{out_dir}/play_stats_{season}.parquet`` (parity with nflverse's
            released ``play_stats_{season}.rds`` naming — reference §13).

    Returns:
        Path to the written parquet file.
    """
    raw_dir = Path(raw_dir)
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    df = _build_playstats_season(season, raw_dir=raw_dir)

    out_path = out_dir / f"play_stats_{season}.parquet"
    df.write_parquet(out_path)
    return out_path


def _parse_season_range(s: str) -> list[int]:
    """Parse ``'A:B'`` or ``'A'`` into a list of season integers (inclusive)."""
    if ":" in s:
        parts = s.split(":", 1)
        start, end = int(parts[0]), int(parts[1])
        return list(range(start, end + 1))
    return [int(s)]


def _nonneg_float(s: str) -> float:
    import math

    v = float(s)
    if not math.isfinite(v) or v < 0:
        raise argparse.ArgumentTypeError(f"must be a finite number >= 0, got {s!r}")
    return v


def _nonneg_int(s: str) -> int:
    v = int(s)
    if v < 0:
        raise argparse.ArgumentTypeError(f"must be >= 0, got {s!r}")
    return v


def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(prog="native_pbp")
    sub = ap.add_subparsers(dest="cmd", required=True)
    b = sub.add_parser("build", help="Build model-PBP parquet for a range of seasons.")
    b.add_argument(
        "--seasons",
        required=True,
        help="Season or range, e.g. '2024' or '2010:2024' (inclusive).",
    )
    b.add_argument(
        "--raw-dir",
        default=".cache/nfl_raw",
        help="Root of the committed per-game JSON library (default: .cache/nfl_raw).",
    )
    b.add_argument(
        "--out",
        required=True,
        help="Output directory for the model_pbp_{season}.parquet files.",
    )
    b.add_argument(
        "--enrich",
        action="store_true",
        help=(
            "Run the EP/WP/CP/xYAC enrichment (enrich_nfl_pbp, method='lead_diff') "
            "on each season before writing — the canonical nfl_model_pbp dataset."
        ),
    )

    ps = sub.add_parser(
        "build-playstats",
        help="Build long-format play-stats parquet for a range of seasons (reference §13).",
    )
    ps.add_argument(
        "--seasons",
        required=True,
        help="Season or range, e.g. '2024' or '2010:2024' (inclusive).",
    )
    ps.add_argument(
        "--raw-dir",
        default=".cache/nfl_raw",
        help="Root of the committed per-game JSON library (default: .cache/nfl_raw).",
    )
    ps.add_argument(
        "--out",
        required=True,
        help="Output directory for the play_stats_{season}.parquet files.",
    )

    pp = sub.add_parser(
        "parity",
        help="Published nfl_model_pbp / espn_nfl_pbp vs nflverse, every season: README + CSVs.",
    )
    pp.add_argument("--seasons", required=True, help="Season or range, e.g. '2024' or '1999:2025'.")
    pp.add_argument("--dataset", choices=["model_pbp", "espn_pbp", "both"], default="both")
    pp.add_argument(
        "--cache-dir", default=".cache/parity", help="Where release parquets are cached."
    )
    pp.add_argument("--out", required=True, help="Report directory (README.md + per-dataset CSVs).")
    pp.add_argument("--raw-dir", default="../nfl-raw", help="nfl-raw checkout (ESPN crosswalk).")
    pp.add_argument("--refresh", action="store_true", help="Re-download cached release parquets.")
    pp.add_argument(
        "--espn-first-season",
        type=int,
        default=None,
        help="Compare espn_pbp from this season (default 2006; its play ids embed the GSIS "
        "play_id only from 2006, so earlier joins are coincidental).",
    )
    pp.add_argument(
        "--float-tol", type=_nonneg_float, default=1e-4, help="Finite, >= 0 (0 = exact)."
    )
    pp.add_argument(
        "--top-n",
        type=_nonneg_int,
        default=50,
        help="Deviation plays kept per metric and season (>= 0).",
    )
    return ap


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    if args.cmd == "build":
        seasons = _parse_season_range(args.seasons)
        for season in seasons:
            out_path = build_season(
                season,
                raw_dir=args.raw_dir,
                out_dir=args.out,
                enrich=args.enrich,
                schedule_lookup=_build_schedule_lookup(season),
                jersey_lookup=_build_jersey_lookup(season),
            )
            print(f"wrote {out_path}")
    elif args.cmd == "build-playstats":
        seasons = _parse_season_range(args.seasons)
        for season in seasons:
            out_path = build_playstats_season(season, raw_dir=args.raw_dir, out_dir=args.out)
            print(f"wrote {out_path}")
    elif args.cmd == "parity":
        from native_pbp.parity import run_published_parity

        datasets = ["model_pbp", "espn_pbp"] if args.dataset == "both" else [args.dataset]
        readme = run_published_parity(
            datasets,
            _parse_season_range(args.seasons),
            args.cache_dir,
            args.out,
            raw_dir=args.raw_dir,
            refresh=args.refresh,
            float_tol=args.float_tol,
            top_n=args.top_n,
            first_seasons=None
            if args.espn_first_season is None
            else {"espn_pbp": args.espn_first_season},
        )
        print(f"wrote {readme}")
    return 0
