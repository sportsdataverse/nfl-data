"""CLI for building model-PBP parquet files from the committed nfl/raw library.

Usage::

    python -m native_pbp build --seasons 2022:2024 --raw-dir .cache/nfl_raw --out out/model_pbp

Pass ``--enrich`` to run the EP/WP/CP/xYAC enrichment (the canonical
``nfl_model_pbp`` dataset) before each season's parquet is written::

    python -m native_pbp build --seasons 2023:2024 --raw-dir nfl/raw \\
        --out out/model_pbp --enrich
"""
from __future__ import annotations

import argparse
import warnings
from pathlib import Path

import polars as pl

from native_pbp.build import build_season as _build_season


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

    if enrich and df.height:
        from sportsdataverse.nfl.ep_wp import enrich_nfl_pbp

        df = enrich_nfl_pbp(df, method="lead_diff")

    out_path = out_dir / f"model_pbp_{season}.parquet"
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
    return 0
