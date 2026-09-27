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
from pathlib import Path

import polars as pl

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
_DRIVE = ["game_id", "fixed_drive"]
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
    # build semantics (shield_pbp/drives.py:374-375): yardline_100 of the drive's
    # first/last play; nflverse ships "SEA 20" strings that don't cast. nflverse files an
    # END QUARTER row under the next drive, so such a drive starts null (27 in 2002).
    "drive_start_yard_line": lambda: pl.col("yardline_100").first().over(_DRIVE),
    "drive_end_yard_line": lambda: pl.col("yardline_100").last().over(_DRIVE),
}
#: Null-typed in stub-only seasons (so nflverse's Float64 would leak through); the Shield
#: build and the published 2003/2004 assets type them Int64.
_INT64_YARDS = (
    "lateral_receiving_yards",
    "fumble_recovery_2_yards",
    "lateral_rushing_yards",
    "yards_after_catch",
)


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
    from sportsdataverse.nfl.shield_pbp.game_id import _nflverse_abbr

    nv = load_nfl_pbp([season])
    if not nv.schema["game_id"] == df.schema["game_id"] == pl.String:
        raise TypeError(
            f"game_id dtype: nflverse {nv.schema['game_id']} vs build {df.schema['game_id']}"
        )
    is_timeout = (pl.col("play_type_nfl") == "TIMEOUT").fill_null(False)
    is_marker = is_timeout | pl.col("desc").fill_null("").str.contains(_MARKER_DESC)
    nv = nv.filter(pl.col("game_id").is_in(sorted(thin)), ~is_marker)
    # nflverse team columns carry the modern LA/LAC/LV (game_id and every Shield season use
    # the era's STL/SD/OAK), and "" for no team on some 1999-2000 non-play rows
    team_cols = [
        c
        for c, dt in nv.schema.items()
        if dt == pl.String and (c in ("posteam", "defteam") or c.endswith("_team"))
    ]
    remap = {t: _nflverse_abbr(t, season) for t in ("LA", "LAC", "LV")} | {"": None}
    nv = nv.with_columns(pl.col(team_cols).replace(remap))
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


def _build_schedule_lookup(season: int) -> dict[str, dict]:
    """Build a ``{game_id: {roof, spread_line, total_line}}`` map for *season*.

    These game-level fields are absent from the Shield feed ``native_pbp`` parses;
    nflverse sources them from the schedule (Lee Sharpe's games file). Without
    them ``spread_line``/``total_line`` are null and ``vegas_wp`` falls back to a
    default spread (the 4th-down decision step is also skipped). Degrades to an
    empty map — leaving the fields null, the prior behavior — with a
    ``RuntimeWarning`` if the schedule can't be loaded; a betting-line lookup must
    never fail the build.
    """
    try:
        from sportsdataverse.nfl import load_nfl_schedule

        sched = load_nfl_schedule([season])
        if not isinstance(sched, pl.DataFrame):
            sched = pl.from_pandas(sched)
        keep = [c for c in ("game_id", "roof", "spread_line", "total_line") if c in sched.columns]
        if "game_id" not in keep:
            return {}
        # `keep` drops any column absent from the schedule, so row.get(...) below
        # returns None for a missing field (the intended null-degrade).
        return {
            row["game_id"]: {
                "roof": row.get("roof"),
                "spread_line": row.get("spread_line"),
                "total_line": row.get("total_line"),
            }
            for row in sched.select(keep).iter_rows(named=True)
        }
    except Exception as exc:  # network / schema / loader failure → degrade, never fail the build
        warnings.warn(
            f"native_pbp build: schedule lookup failed for {season} "
            f"({type(exc).__name__}: {exc}); spread_line/total_line will be null",
            RuntimeWarning,
            stacklevel=2,
        )
        return {}


def build_season(
    season: int,
    raw_dir: str | Path,
    out_dir: str | Path,
    *,
    enrich: bool = False,
    schedule_lookup: dict | None = None,
) -> Path:
    """Build one season's model-PBP parquet and write it to *out_dir*.

    Seasons up to 2002 swap Shield's thin (stub) games for nflverse pbp rows first; see
    :func:`_backfill_thin_games`.

    Args:
        season: NFL season year (e.g. 2024).
        raw_dir: Root directory of the committed per-game JSON library.
            Per-game files are expected at ``{raw_dir}/{season}/*.json``.
        out_dir: Output directory.  The file is written as
            ``{out_dir}/model_pbp_{season}.parquet``.
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

    Returns:
        Path to the written parquet file.
    """
    raw_dir = Path(raw_dir)
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    df = _build_season(season, raw_dir=raw_dir, schedule_lookup=schedule_lookup)
    df = _backfill_thin_games(df, season, raw_dir)

    if enrich and df.height:
        from sportsdataverse.nfl.ep_wp import enrich_nfl_pbp

        df = enrich_nfl_pbp(df, method="lead_diff")

    out_path = out_dir / f"model_pbp_{season}.parquet"
    df.write_parquet(out_path)
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
            )
            print(f"wrote {out_path}")
    elif args.cmd == "build-playstats":
        seasons = _parse_season_range(args.seasons)
        for season in seasons:
            out_path = build_playstats_season(season, raw_dir=args.raw_dir, out_dir=args.out)
            print(f"wrote {out_path}")
    return 0
