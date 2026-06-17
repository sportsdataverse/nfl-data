"""Ingest nflverse play-by-play data for EP/WP/CP model training.

Usage:
    from model_training.track6_nfl_ep_wp.ingest import download_pbp
    download_pbp(seasons=list(range(2012, 2025)), output_dir=Path("data"))
"""
from __future__ import annotations

from pathlib import Path
from typing import List

import polars as pl


# ---------------------------------------------------------------------------
# Required columns — superset of all EP/WP/CP source + label columns
# ---------------------------------------------------------------------------

REQUIRED_COLUMNS: list[str] = [
    # identifiers / ordering
    "game_id",
    "play_id",
    "qtr",
    "game_half",
    # EP/WP feature sources
    "down",
    "yardline_100",
    "ydstogo",
    "half_seconds_remaining",
    "game_seconds_remaining",
    "posteam_timeouts_remaining",
    "defteam_timeouts_remaining",
    "posteam",
    "defteam",
    "home_team",
    "season",
    "roof",
    "spread_line",
    "score_differential",
    # EP label sources
    "sp",
    "touchdown",
    "td_team",
    "field_goal_result",
    "safety",
    # WP label sources
    "result",
    "home_score",
    "away_score",
    # CP feature sources
    "air_yards",
    "pass_location",
    "complete_pass",
    "incomplete_pass",
    "interception",
    "receiver_player_id",
    "receiver_player_name",
    "qb_hit",
]


def validate_pbp(df: pl.DataFrame) -> None:
    """Raise ValueError if the DataFrame is missing required columns or has no rows.

    Args:
        df: Raw nflverse PBP DataFrame.

    Raises:
        ValueError: On missing columns or empty frame.
    """
    if df.height == 0:
        raise ValueError("PBP frame is empty — likely a failed download or wrong season range.")

    missing = [c for c in REQUIRED_COLUMNS if c not in df.columns]
    if missing:
        raise ValueError(
            f"PBP frame is missing required columns: {missing}. "
            "Ensure nflverse-compatible data is loaded."
        )


def _load_nfl_pbp(seasons: List[int], **kwargs) -> pl.DataFrame:
    """Thin wrapper around sportsdataverse so tests can monkeypatch it."""
    from sportsdataverse.nfl import load_nfl_pbp
    from sportsdataverse.nfl import update_config

    update_config(cache_mode="off")
    return load_nfl_pbp(seasons=seasons, **kwargs)


def download_pbp(
    seasons: List[int],
    *,
    output_dir: Path = Path("data"),
) -> list[Path]:
    """Download nflverse PBP for the given seasons and save as parquet files.

    Files are saved as ``{output_dir}/pbp_{season}.parquet``. Existing files are
    overwritten so re-running is idempotent.

    Args:
        seasons: List of NFL seasons (e.g. ``list(range(2012, 2025))``).
        output_dir: Directory for output parquet files. Created if absent.

    Returns:
        List of paths to written parquet files.

    Example:
        Quick start::

            from pathlib import Path
            from model_training.track6_nfl_ep_wp.ingest import download_pbp
            paths = download_pbp([2023, 2024], output_dir=Path("data"))
            print(paths)
    """
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    written: list[Path] = []
    for season in seasons:
        print(f"[ingest] downloading season {season}...")
        df = _load_nfl_pbp([season])
        validate_pbp(df)
        out = output_dir / f"pbp_{season}.parquet"
        df.write_parquet(str(out))
        print(f"[ingest] saved {out} ({df.height:,} rows, {df.width} cols)")
        written.append(out)

    return written


def build_schedule_lookup(seasons: List[int]) -> dict:
    """Build ``{game_id: {"roof", "spread_line"}}`` from sdv-py schedules.

    These two game-level fields are the only inputs the native Shield
    reconstruction cannot derive from the raw feed; the nflverse schedule (a
    small, stable table) supplies them, mirroring nflfastR's own join.

    Args:
        seasons: Seasons to pull schedule rows for.

    Returns:
        Mapping of nflverse game_id -> {"roof", "spread_line"}. Empty when the
        schedule cannot be loaded.
    """
    try:
        from sportsdataverse.nfl import load_nfl_schedule
    except Exception:  # noqa: BLE001
        return {}
    sched = load_nfl_schedule(seasons=seasons)
    if not isinstance(sched, pl.DataFrame):
        sched = pl.from_pandas(sched)
    have = [c for c in ("game_id", "roof", "spread_line") if c in sched.columns]
    if "game_id" not in have:
        return {}
    out: dict = {}
    for row in sched.select(have).iter_rows(named=True):
        out[row["game_id"]] = {"roof": row.get("roof"), "spread_line": row.get("spread_line")}
    return out


def load_native_pbp(
    seasons: List[int],
    *,
    raw_dir: Path = Path("nfl/raw"),
    use_schedule: bool = True,
    validate: bool = True,
) -> pl.DataFrame:
    """Reconstruct PBP natively from the committed ``nfl/raw`` Shield library.

    The self-sufficient alternative to :func:`download_pbp` / :func:`load_local_pbp`:
    builds nflverse-shape play-by-play from the repo's own raw JSON (no nflverse
    PBP dependency). ``roof`` / ``spread_line`` come from a light schedule join
    when ``use_schedule`` is True.

    Args:
        seasons: Seasons to build.
        raw_dir: Root of the committed per-game library.
        use_schedule: Join roof/spread_line from sdv-py schedules (else left null).
        validate: Run :func:`validate_pbp` on the result.

    Returns:
        Concatenated polars DataFrame carrying the Track 6 REQUIRED_COLUMNS.

    Example:
        Train EP off native data::

            from model_training.track6_nfl_ep_wp.ingest import load_native_pbp
            from model_training.track6_nfl_ep_wp.label import build_ep_training_set
            df = load_native_pbp([2022, 2023, 2024])
            ep = build_ep_training_set(df)
    """
    from native_pbp.build import build_season

    lookup = build_schedule_lookup(seasons) if use_schedule else {}
    frames: list[pl.DataFrame] = []
    for season in seasons:
        df = build_season(season, raw_dir=raw_dir, schedule_lookup=lookup)
        if df.height:
            frames.append(df)
    if not frames:
        raise ValueError(f"No native PBP built for seasons {seasons} under {raw_dir}.")
    out = pl.concat(frames, how="diagonal_relaxed")
    if validate:
        validate_pbp(out)
    return out


def load_local_pbp(seasons: List[int], data_dir: Path = Path("data")) -> pl.DataFrame:
    """Load previously-downloaded PBP parquets from disk.

    Args:
        seasons: Seasons to load.
        data_dir: Directory containing ``pbp_{season}.parquet`` files.

    Returns:
        Concatenated polars DataFrame.

    Raises:
        FileNotFoundError: If a season file is missing.
    """
    frames: list[pl.DataFrame] = []
    for season in seasons:
        path = Path(data_dir) / f"pbp_{season}.parquet"
        if not path.exists():
            raise FileNotFoundError(
                f"No local PBP found for season {season} at {path}. "
                "Run download_pbp() first."
            )
        frames.append(pl.read_parquet(str(path)))
    return pl.concat(frames, how="diagonal_relaxed")
