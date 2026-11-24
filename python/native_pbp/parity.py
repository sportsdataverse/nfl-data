"""Parity harness: diff the native reconstruction against nflverse load_nfl_pbp.

The correctness gate for the whole port. Joins on ``play_id`` (which aligns
exactly — native is a superset, since nflverse drops some admin/timeout rows)
and reports per-column match rates among rows where both sides are non-null.
``roof`` / ``spread_line`` for the native build are sourced from the nflverse
frame itself (the schedules data), closing the loop.

Live (downloads nflverse PBP): drive it from a gated test or a script.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

import polars as pl

from native_pbp.build import build_pbp

# column -> comparison mode ("exact" | "tol"); tol uses |a-b| < 0.5 for floats.
DEFAULT_PARITY_COLUMNS: Dict[str, str] = {
    "down": "exact",
    "ydstogo": "exact",
    "yardline_100": "exact",
    "qtr": "exact",
    "half_seconds_remaining": "exact",
    "game_seconds_remaining": "exact",
    "score_differential": "exact",
    "posteam_timeouts_remaining": "exact",
    "defteam_timeouts_remaining": "exact",
    "pass_attempt": "exact",
    "rush_attempt": "exact",
    "complete_pass": "exact",
    "interception": "exact",
    "air_yards": "tol",
    "touchdown": "exact",
}


def compare_frames(
    native: pl.DataFrame,
    nflverse: pl.DataFrame,
    columns: Optional[Dict[str, str]] = None,
) -> Dict[str, Any]:
    """Per-column match rates between native and nflverse on the play_id join.

    Args:
        native: A native build frame (one or more games).
        nflverse: nflverse PBP filtered to the same game(s).
        columns: ``{column: "exact"|"tol"}`` map; defaults to
            :data:`DEFAULT_PARITY_COLUMNS`.

    Returns:
        ``{"joined": int, "columns": {col: {"matched","compared","rate"}}}``.
    """
    columns = columns or DEFAULT_PARITY_COLUMNS
    native = native.with_columns(pl.col("play_id").cast(pl.Int64))
    nflverse = nflverse.with_columns(pl.col("play_id").cast(pl.Int64))

    avail = [c for c in columns if c in native.columns and c in nflverse.columns]
    j = native.select(["play_id"] + avail).join(
        nflverse.select(["play_id"] + [pl.col(c).alias(f"nv_{c}") for c in avail]),
        on="play_id",
        how="inner",
    )
    report: Dict[str, Any] = {"joined": j.height, "columns": {}}
    for c in avail:
        sub = j.filter(pl.col(c).is_not_null() & pl.col(f"nv_{c}").is_not_null())
        compared = sub.height
        if compared == 0:
            report["columns"][c] = {"matched": 0, "compared": 0, "rate": None}
            continue
        if columns[c] == "tol":
            matched = sub.filter(
                (pl.col(c).cast(pl.Float64) - pl.col(f"nv_{c}").cast(pl.Float64)).abs() < 0.5
            ).height
        else:
            matched = sub.filter(
                pl.col(c).cast(pl.Float64) == pl.col(f"nv_{c}").cast(pl.Float64)
            ).height
        report["columns"][c] = {
            "matched": matched,
            "compared": compared,
            "rate": matched / compared,
        }
    return report


def _load_nflverse(season: int) -> pl.DataFrame:
    """Load one season of nflverse PBP as polars (cache off)."""
    from sportsdataverse.nfl import load_nfl_pbp, update_config

    update_config(cache_mode="off")
    nv = load_nfl_pbp(seasons=[season])
    if not isinstance(nv, pl.DataFrame):
        nv = pl.from_pandas(nv)
    return nv


def run_parity(
    season: int,
    game_ids: Optional[List[str]] = None,
    raw_dir: str = "nfl/raw",
    columns: Optional[Dict[str, str]] = None,
) -> Dict[str, Any]:
    """Build native PBP for the given games and diff vs nflverse for the season.

    roof / spread_line for each native build are read from the nflverse frame
    (its schedules-derived columns). Returns a per-game + aggregate report.

    Args:
        season: NFL season year.
        game_ids: Specific game_ids to check; all of the season's nflverse games
            when None.
        raw_dir: Root of the committed per-game library.
        columns: Override the comparison column map.

    Returns:
        ``{"season", "games": {gid: report}, "aggregate": {col: rate}}``.
    """
    import json
    from pathlib import Path

    nv_all = _load_nflverse(season)
    if game_ids is None:
        game_ids = nv_all["game_id"].unique().to_list()

    games: Dict[str, Any] = {}
    for gid in game_ids:
        raw_path = Path(raw_dir) / str(season) / f"{gid}.json"
        if not raw_path.exists():
            continue
        nv_g = nv_all.filter(pl.col("game_id") == gid)
        roof = nv_g["roof"][0] if "roof" in nv_g.columns and nv_g.height else None
        spread = nv_g["spread_line"][0] if "spread_line" in nv_g.columns and nv_g.height else None
        native = build_pbp(
            json.loads(raw_path.read_text(encoding="utf-8")),
            roof=roof,
            spread_line=spread,
            game_id=gid,
        )
        if native.height:
            games[gid] = compare_frames(native, nv_g, columns=columns)

    # Aggregate match rate per column across games.
    agg: Dict[str, Dict[str, int]] = {}
    for rep in games.values():
        for col, st in rep["columns"].items():
            a = agg.setdefault(col, {"matched": 0, "compared": 0})
            a["matched"] += st["matched"]
            a["compared"] += st["compared"]
    aggregate = {
        col: (a["matched"] / a["compared"] if a["compared"] else None) for col, a in agg.items()
    }
    return {"season": season, "games": games, "aggregate": aggregate}


# ---------------------------------------------------------------------------
# Published mode: the released datasets vs nflverse, every season (handoff Part B).
#   nfl_model_pbp  <-> nflverse on (game_id, play_id); ours drops admin/timeout rows.
#   espn_nfl_pbp   <-> nflverse: ESPN ``id`` is "<espn game id><GSIS play_id>" and every row
#                      carries ``nflverse_game_id``, so stripping the prefix gives play_id.
# Every number in the report comes from these functions; nothing is typed by hand.
# ---------------------------------------------------------------------------

SDV_RELEASE_URL = (
    "https://github.com/sportsdataverse/sportsdataverse-data/releases/download/{tag}/{name}"
)
NFLVERSE_PBP_URL = (
    "https://github.com/nflverse/nflverse-data/releases/download/pbp/play_by_play_{season}.parquet"
)

#: dataset -> (release tag, asset name, first season)
PUBLISHED = {
    "model_pbp": ("nfl_model_pbp", "model_pbp_{season}.parquet", 1999),
    "espn_pbp": ("espn_nfl_pbp", "play_by_play_{season}.parquet", 2002),
}

#: espn_nfl_pbp column -> nflverse column (verified on 2024; booleans become 0/1 Float64)
ESPN_COLUMN_MAP: Dict[str, str] = {
    "period.number": "qtr",
    "start.down": "down",
    "start.distance": "ydstogo",
    "start.yardsToEndzone": "yardline_100",
    "EP_start": "ep",
    "EPA": "epa",
    "wp_before": "wp",
    "wpa": "wpa",
    "cp": "cp",
    "cpoe": "cpoe",
    "air_yards": "air_yards",
    "yds_receiving": "receiving_yards",
    "yds_rushed": "rushing_yards",
    "completion": "complete_pass",
    "int": "interception",
    "sack": "sack",
    "pass_attempt": "pass_attempt",
    "rush": "rush_attempt",
    "touchdown": "touchdown",
}

METRIC_COLUMNS = ("ep", "epa", "wp", "wpa", "cp", "cpoe")
_KEY = ["game_id", "play_id"]
_NV = "nv__"


def _keyed(df: pl.DataFrame, side: str) -> pl.DataFrame:
    """One dtype per join key at the boundary: game_id String, play_id Int64."""
    out = df.with_columns(pl.col("game_id").cast(pl.Utf8), pl.col("play_id").cast(pl.Int64))
    assert out.schema["game_id"] == pl.Utf8 and out.schema["play_id"] == pl.Int64, side
    return out


def _is_num(dt: pl.DataType) -> bool:
    return dt.is_numeric() or dt == pl.Boolean


def _match_exprs(c: str, ours_dt: pl.DataType, nv_dt: pl.DataType, tol: float):
    """(mode, a, b, eq) for one shared column; NaN is treated as null."""
    a, b = pl.col(c), pl.col(f"{_NV}{c}")
    if _is_num(ours_dt) and _is_num(nv_dt):
        a, b = a.cast(pl.Float64).fill_nan(None), b.cast(pl.Float64).fill_nan(None)
        if ours_dt.is_float() or nv_dt.is_float():
            return "tol", a, b, (a - b).abs() <= tol
        return "exact", a, b, a == b
    mode = "exact" if not (_is_num(ours_dt) or _is_num(nv_dt)) else "mixed"
    a, b = a.cast(pl.Utf8), b.cast(pl.Utf8)
    return mode, a, b, a == b


def _typed_counts(df: pl.DataFrame, col: str, name: str) -> pl.DataFrame:
    t = pl.col(col).cast(pl.Utf8) if col in df.columns else pl.lit(None, pl.Utf8)
    return (
        df.select(t.fill_null("(null)").alias("play_type"))
        .group_by("play_type")
        .agg(pl.len().alias(name))
    )


def compare_published(
    ours: pl.DataFrame,
    nflverse: pl.DataFrame,
    *,
    float_tol: float = 1e-4,
    top_n: int = 50,
    skip_columns: tuple = (),
) -> Dict[str, Any]:
    """Row coverage, per-column match rates and metric deltas, ours vs nflverse.

    Args:
        ours: One season of an SDV dataset in nflverse names (``game_id``, ``play_id``, ...).
        nflverse: The same season of nflverse ``play_by_play``.
        float_tol: Absolute tolerance for a float match.
        top_n: Plays kept per metric in ``deviations``.
        skip_columns: Shared columns left out of the per-column table.

    Returns:
        ``{"ours_rows", "nflverse_rows", "joined", "coverage", "columns", "metrics",
        "deviations", "missing"}``; the last five are polars frames. A column match counts
        both-null as a match and null-vs-value as a mismatch (``na_mismatch``).
    """
    o, n = _keyed(ours, "ours"), _keyed(nflverse, "nflverse")
    shared = [c for c in o.columns if c in n.columns and c not in _KEY]
    nv_cols = [pl.col(c).alias(f"{_NV}{c}") for c in shared]
    extra = [
        pl.col(c).alias(f"{_NV}{c}")
        for c in ("play_type", "desc")
        if c in n.columns and c not in shared
    ]
    j = o.select(_KEY + shared).join(n.select(_KEY + nv_cols + extra), on=_KEY, how="inner")

    cov = (
        _typed_counts(j, f"{_NV}play_type", "matched")
        .join(
            _typed_counts(o.join(n.select(_KEY), on=_KEY, how="anti"), "play_type", "ours_only"),
            on="play_type",
            how="full",
            coalesce=True,
        )
        .join(
            _typed_counts(
                n.join(o.select(_KEY), on=_KEY, how="anti"), "play_type", "nflverse_only"
            ),
            on="play_type",
            how="full",
            coalesce=True,
        )
        .with_columns(pl.col("matched", "ours_only", "nflverse_only").fill_null(0).cast(pl.Int64))
        .sort("matched", descending=True)
    )

    rows, aggs = [], []
    for c in shared:
        if c in skip_columns:
            continue
        mode, a, b, eq = _match_exprs(c, o.schema[c], n.schema[c], float_tol)
        rows.append((c, mode, str(o.schema[c]), str(n.schema[c])))
        aggs += [
            ((a.is_null() & b.is_null()) | (a.is_not_null() & b.is_not_null() & eq))
            .sum()
            .alias(f"m|{c}"),
            (a.is_null() ^ b.is_null()).sum().alias(f"na|{c}"),
            (a.is_null() & b.is_null()).sum().alias(f"bn|{c}"),
        ]
    s = j.select(aggs).row(0, named=True) if aggs else {}
    columns = pl.DataFrame(
        [
            {
                "column": c,
                "mode": mode,
                "ours_dtype": od,
                "nflverse_dtype": nd,
                "compared": j.height,
                "matched": int(s[f"m|{c}"] or 0),
                "na_mismatch": int(s[f"na|{c}"] or 0),
                "both_null": int(s[f"bn|{c}"] or 0),
                "rate": (int(s[f"m|{c}"] or 0) / j.height) if j.height else None,
            }
            for c, mode, od, nd in rows
        ],
        schema={
            "column": pl.Utf8,
            "mode": pl.Utf8,
            "ours_dtype": pl.Utf8,
            "nflverse_dtype": pl.Utf8,
            "compared": pl.Int64,
            "matched": pl.Int64,
            "na_mismatch": pl.Int64,
            "both_null": pl.Int64,
            "rate": pl.Float64,
        },
    )

    metrics, devs = [], []
    ptype = f"{_NV}play_type" if f"{_NV}play_type" in j.columns else None
    desc = f"{_NV}desc" if f"{_NV}desc" in j.columns else None
    for m in METRIC_COLUMNS:
        if m not in shared:
            continue
        sub = (
            j.select(
                *_KEY,
                (pl.col(ptype) if ptype else pl.lit(None, pl.Utf8))
                .cast(pl.Utf8)
                .alias("play_type"),
                (pl.col(desc) if desc else pl.lit(None, pl.Utf8)).cast(pl.Utf8).alias("desc"),
                pl.col(m).cast(pl.Float64).fill_nan(None).alias("ours"),
                pl.col(f"{_NV}{m}").cast(pl.Float64).fill_nan(None).alias("nflverse"),
            )
            .drop_nulls(["ours", "nflverse"])
            .with_columns((pl.col("ours") - pl.col("nflverse")).abs().alias("abs_diff"))
        )
        st = sub.select(
            pl.len().cast(pl.Int64).alias("n"),
            pl.col("abs_diff").mean().alias("mean_abs_diff"),
            pl.corr("ours", "nflverse").alias("r"),
            pl.col("ours").mean().alias("mean_ours"),
            pl.col("nflverse").mean().alias("mean_nflverse"),
        ).row(0, named=True)
        metrics.append({"metric": m, **st})
        devs.append(
            sub.sort("abs_diff", descending=True)
            .head(top_n)
            .with_columns(pl.lit(m).alias("metric"))
        )
    metrics_df = pl.DataFrame(
        metrics,
        schema={
            "metric": pl.Utf8,
            "n": pl.Int64,
            "mean_abs_diff": pl.Float64,
            "r": pl.Float64,
            "mean_ours": pl.Float64,
            "mean_nflverse": pl.Float64,
        },
    )
    dev_schema = {
        "game_id": pl.Utf8,
        "play_id": pl.Int64,
        "play_type": pl.Utf8,
        "desc": pl.Utf8,
        "ours": pl.Float64,
        "nflverse": pl.Float64,
        "abs_diff": pl.Float64,
        "metric": pl.Utf8,
    }
    deviations = pl.concat(devs) if devs else pl.DataFrame(schema=dev_schema)

    lacking = [c for c in n.columns if c not in o.columns]
    missing = pl.DataFrame(
        {
            "column": lacking,
            "nflverse_dtype": [str(n.schema[c]) for c in lacking],
            "nflverse_non_null": [n.height - n[c].null_count() for c in lacking],
        },
        schema={"column": pl.Utf8, "nflverse_dtype": pl.Utf8, "nflverse_non_null": pl.Int64},
    )
    return {
        "ours_rows": o.height,
        "nflverse_rows": n.height,
        "joined": j.height,
        "coverage": cov,
        "columns": columns,
        "metrics": metrics_df,
        "deviations": deviations,
        "missing": missing,
    }


def espn_to_nflverse(espn: pl.DataFrame, games: List[Dict[str, Any]]) -> pl.DataFrame:
    """espn_nfl_pbp in nflverse names: keys, posteam/defteam abbrs and :data:`ESPN_COLUMN_MAP`.

    Args:
        espn: One season of ``espn_nfl_pbp``.
        games: nfl-raw ``nfl/espn/crosswalk/games.json`` rows (ESPN team id -> nflverse abbr).

    Returns:
        ``game_id`` (nflverse), ``play_id`` (Int64), ``play_type`` (ESPN ``type.text``),
        ``posteam`` / ``defteam`` and every mapped column present.

    Raises:
        ValueError: If an ESPN play ``id`` does not start with its ``game_id``.
    """
    ids = espn.select(
        pl.col("id").cast(pl.Utf8).alias("i"), pl.col("game_id").cast(pl.Utf8).alias("g")
    )
    if not ids.select(pl.col("i").str.starts_with(pl.col("g")).all()).item():
        raise ValueError(
            "espn_nfl_pbp id does not start with its game_id; the play_id rule no longer holds"
        )
    teams = pl.DataFrame(
        [
            {
                "espn_game": int(g["espn_event_id"]),
                "team_id": int(g[f"{side}_espn_team_id"]),
                "abbr": g[f"{side}_nflverse"],
            }
            for g in games
            for side in ("home", "away")
        ],
        schema={"espn_game": pl.Int64, "team_id": pl.Int64, "abbr": pl.Utf8},
    ).unique(["espn_game", "team_id"])
    df = espn.with_columns(
        pl.col("game_id").cast(pl.Int64).alias("espn_game"),
        pl.col("pos_team_id").cast(pl.Int64),
        pl.col("def_pos_team_id").cast(pl.Int64),
        ids["i"].str.slice(ids["g"].str.len_chars()).cast(pl.Int64).alias("play_id"),
    )
    assert df.schema["pos_team_id"] == teams.schema["team_id"] == pl.Int64
    df = df.join(
        teams.rename({"team_id": "pos_team_id", "abbr": "posteam"}),
        on=["espn_game", "pos_team_id"],
        how="left",
    ).join(
        teams.rename({"team_id": "def_pos_team_id", "abbr": "defteam"}),
        on=["espn_game", "def_pos_team_id"],
        how="left",
    )
    mapped = [
        (pl.col(src).cast(pl.Float64) if df.schema[src] == pl.Boolean else pl.col(src)).alias(dst)
        for src, dst in ESPN_COLUMN_MAP.items()
        if src in df.columns
    ]
    return df.select(
        pl.col("nflverse_game_id").alias("game_id"),
        "play_id",
        pl.col("type.text").alias("play_type"),
        "posteam",
        "defteam",
        *mapped,
    )


def model_column_refs(columns: List[str], roots: Optional[List[Any]] = None) -> Dict[str, int]:
    """How many trainer source files name each column as a string literal.

    Ranks the nflverse columns we lack by model impact from the committed code, not by hand.
    ``roots`` defaults to ``python/model_training``.
    """
    from pathlib import Path

    roots = roots or [Path(__file__).resolve().parents[1] / "model_training"]
    texts = [p.read_text(encoding="utf-8") for r in roots for p in Path(r).rglob("*.py")]
    return {c: sum(1 for t in texts if f'"{c}"' in t or f"'{c}'" in t) for c in columns}


def fetch_parquet(url: str, path: Any, refresh: bool = False) -> Any:
    """Download ``url`` to ``path`` once (``refresh`` re-downloads); returns the path."""
    from pathlib import Path

    import requests

    path = Path(path)
    if refresh or not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        resp = requests.get(url, timeout=600)
        resp.raise_for_status()
        tmp = path.with_suffix(".tmp")
        tmp.write_bytes(resp.content)
        tmp.replace(path)
    return path


def load_season(
    dataset: str,
    season: int,
    cache_dir: Any,
    games: Optional[List[Dict[str, Any]]] = None,
    refresh: bool = False,
):
    """``(ours_in_nflverse_names, nflverse, stamp)`` for one season, from the published releases."""
    from pathlib import Path

    tag, name, _ = PUBLISHED[dataset]
    name = name.format(season=season)
    ours_path = fetch_parquet(
        SDV_RELEASE_URL.format(tag=tag, name=name), Path(cache_dir) / tag / name, refresh
    )
    nv_path = fetch_parquet(
        NFLVERSE_PBP_URL.format(season=season),
        Path(cache_dir) / "nflverse_pbp" / f"play_by_play_{season}.parquet",
        refresh,
    )
    stamp = pl.read_parquet_metadata(ours_path).get("processing_version")
    ours = pl.read_parquet(ours_path)
    if dataset == "espn_pbp":
        ours = espn_to_nflverse(
            ours, [g for g in (games or []) if int(g.get("season", season)) == season]
        )
    return ours, pl.read_parquet(nv_path), stamp


def _fmt(v: Any) -> str:
    if v is None:
        return ""
    if isinstance(v, float):
        return "" if v != v else f"{v:.4f}"  # NaN (a metric with n=0) prints blank
    return str(v)


def _md(df: pl.DataFrame) -> str:
    lines = ["| " + " | ".join(df.columns) + " |", "|" + "---|" * len(df.columns)]
    lines += ["| " + " | ".join(_fmt(v) for v in r) + " |" for r in df.iter_rows()]
    return "\n".join(lines)


def run_published_parity(
    datasets: List[str],
    seasons: List[int],
    cache_dir: Any,
    out_dir: Any,
    raw_dir: Any = "../nfl-raw",
    refresh: bool = False,
    float_tol: float = 1e-4,
    top_n: int = 50,
) -> Any:
    """Every season of each dataset vs nflverse; writes CSVs + ``README.md`` under ``out_dir``.

    Returns:
        The README path. Per dataset: ``summary`` / ``coverage`` / ``columns`` / ``metrics`` /
        ``deviations`` / ``missing`` CSVs, each with a ``season`` column.
    """
    import json
    import subprocess
    from datetime import datetime, timezone
    from pathlib import Path

    out_dir = Path(out_dir)
    games = None
    if "espn_pbp" in datasets:
        games = json.loads(
            (Path(raw_dir) / "nfl" / "espn" / "crosswalk" / "games.json").read_text(
                encoding="utf-8"
            )
        )
    try:
        sha = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            capture_output=True,
            text=True,
            cwd=Path(__file__).parent,
            check=True,
        ).stdout.strip()
    except Exception:  # noqa: BLE001 - provenance only
        sha = "unknown"
    md = [
        "# NFL pbp parity: published SDV datasets vs nflverse",
        "",
        f"Generated {datetime.now(timezone.utc):%Y-%m-%d %H:%M UTC} by `python -m native_pbp parity` "
        f"(nfl-data `{sha}`), float tolerance {float_tol}. Joined on `(game_id, play_id)`. A column match "
        "counts both-null as a match and null-vs-value as a mismatch. Every number below is computed by "
        "`native_pbp/parity.py`; the CSVs next to this file hold the full tables.",
    ]
    for ds in datasets:
        first = PUBLISHED[ds][2]
        tables: Dict[str, List[pl.DataFrame]] = {
            k: [] for k in ("coverage", "columns", "metrics", "deviations", "missing")
        }
        summary = []
        for season in [s for s in seasons if s >= first]:
            ours, nv, stamp = load_season(ds, season, cache_dir, games, refresh)
            rep = compare_published(
                ours,
                nv,
                float_tol=float_tol,
                top_n=top_n,
                skip_columns=("play_type",) if ds == "espn_pbp" else (),
            )
            cov = rep["coverage"]
            summary.append(
                {
                    "season": season,
                    "stamp": stamp,
                    "ours_rows": rep["ours_rows"],
                    "nflverse_rows": rep["nflverse_rows"],
                    "joined": rep["joined"],
                    "ours_only": int(cov["ours_only"].sum()),
                    "nflverse_only": int(cov["nflverse_only"].sum()),
                    "join_rate_of_nflverse": rep["joined"] / rep["nflverse_rows"]
                    if rep["nflverse_rows"]
                    else None,
                }
            )
            for k in tables:
                tables[k].append(rep[k].with_columns(pl.lit(season).alias("season")))
            print(
                f"[parity] {ds} {season}: joined {rep['joined']}/{rep['nflverse_rows']} stamp={stamp}",
                flush=True,
            )
        if not summary:
            continue
        d = out_dir / ds
        d.mkdir(parents=True, exist_ok=True)
        sm = pl.DataFrame(summary)
        sm.write_csv(d / "summary.csv")
        full = {k: pl.concat(v, how="diagonal_relaxed") for k, v in tables.items()}
        for k, v in full.items():
            v.write_csv(d / f"{k}.csv")

        cov_all = (
            full["coverage"]
            .group_by("play_type")
            .agg(pl.col("matched", "ours_only", "nflverse_only").sum())
            .sort("matched", descending=True)
        )
        col_all = (
            full["columns"]
            .group_by("column")
            .agg(
                pl.col("mode").first(),
                pl.col("ours_dtype").first(),
                pl.col("nflverse_dtype").first(),
                pl.col("compared", "matched", "na_mismatch").sum(),
            )
            .with_columns((pl.col("matched") / pl.col("compared")).alias("rate"))
            .sort(["rate", "column"])
        )
        perfect = col_all.filter(pl.col("rate") == 1.0).height
        met = full["metrics"]
        met_pooled = (
            met.group_by("metric")
            .agg(
                pl.col("n").sum(),
                ((pl.col("mean_abs_diff") * pl.col("n")).sum() / pl.col("n").sum()).alias(
                    "mean_abs_diff"
                ),
                pl.col("r").min().alias("r_min_season"),
                pl.col("r").median().alias("r_median_season"),
            )
            .sort("metric")
        )
        met_wide = (
            met.select("season", "metric", "mean_abs_diff", "r")
            .pivot(on="metric", index="season", values=["mean_abs_diff", "r"])
            .sort("season")
        )
        miss = (
            full["missing"]
            .group_by("column")
            .agg(
                pl.col("nflverse_dtype").first(),
                pl.len().alias("seasons_missing"),
                pl.col("nflverse_non_null").sum(),
            )
        )
        refs = model_column_refs(miss["column"].to_list())
        miss = miss.with_columns(
            pl.col("column")
            .replace_strict(refs, return_dtype=pl.Int64)
            .alias("model_files_naming_it")
        ).sort(["model_files_naming_it", "nflverse_non_null"], descending=True)
        used = miss.filter(pl.col("model_files_naming_it") > 0)

        md += [
            "",
            f"## `{PUBLISHED[ds][0]}` ({ds})",
            "",
            "### Rows by season",
            "",
            _md(sm),
            "",
            "### Row coverage by play_type (all seasons; matched and nflverse-only typed by nflverse, ours-only by ours)",
            "",
            _md(cov_all),
            "",
            f"### Per-column match (all seasons pooled): {perfect} of {col_all.height} shared columns match on every "
            "joined play; the rest, worst first",
            "",
            _md(col_all.filter(pl.col("rate") < 1.0)),
            "",
            "### EP / EPA / WP / WPA / CP / CPOE (both non-null)",
            "",
            _md(met_pooled),
            "",
            "By season:",
            "",
            _md(met_wide) if met.height else "(none)",
            "",
            f"Top {top_n} deviations per metric and season: `{ds}/deviations.csv`.",
            "",
            f"### nflverse columns we lack: {miss.height}; {used.height} are named in `python/model_training`",
            "",
            _md(used) if used.height else "(none)",
            "",
            "Full list: `" + ds + "/missing.csv`.",
        ]
    readme = out_dir / "README.md"
    out_dir.mkdir(parents=True, exist_ok=True)
    readme.write_text("\n".join(md) + "\n", encoding="utf-8")
    return readme
