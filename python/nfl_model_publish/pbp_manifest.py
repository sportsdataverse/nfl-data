"""The ``nfl_model_pbp`` processing-version stamp and its per-season manifest.

Every ``model_pbp_<season>.parquet`` carries :func:`nfl_espn_build.config.processing_version`
(``<sdv-py version>+[<sdv-py git sha>.]<SCHEMA_REV>``) in its file-level metadata, written by
``native_pbp.cli.build_season``. The tag carries one manifest, ``nfl_model_pbp_in_data_repo.csv``
(one row per season: ``row_count``, ``processing_version``, ``generated_at_utc``), the same shape as
the ``espn_nfl_*`` manifests. The daily cron republishes only the current season, so after a schema
change the older seasons keep the old shape, and ``load_nfl_pbp``'s ``diagonal_relaxed`` concat
mixes them silently; the manifest is what makes that visible.

The reprocess works in a fresh per-season dir, so the manifest is read back from the release,
upserted and re-uploaded rather than written from a local dir (a local one would hold one season and
clobber the rest). An asset listing that fails RAISES: a failed read taken for "no manifest yet"
would upload a one-row manifest over the published one.
"""

from __future__ import annotations

import json
import subprocess
import tempfile
from pathlib import Path

import polars as pl
from nfl_espn_build.config import SCHEMA_REV, processing_version

from .artifacts import GH_TIMEOUT_SECONDS

MANIFEST = "nfl_model_pbp_in_data_repo.csv"
MANIFEST_SCHEMA: dict[str, type[pl.DataType]] = {
    "season": pl.Int64,
    "row_count": pl.Int64,
    "processing_version": pl.Utf8,
    "generated_at_utc": pl.Utf8,
}


def schema_rev(stamp: str | None) -> int | None:
    """The trailing ``SCHEMA_REV`` of a stamp (``0.2.0+699409c9.7`` -> 7); ``None`` if unreadable."""
    tail = (stamp or "").rsplit("+", 1)[-1].rsplit(".", 1)[-1]
    return int(tail) if "+" in (stamp or "") and tail.isdigit() else None


def parquet_stamp(path: str | Path) -> dict[str, str]:
    """The ``processing_version`` / ``season`` / ``generated_at_utc`` file metadata of a parquet."""
    return pl.read_parquet_metadata(path)


def _gh(args: list[str]) -> str:
    return subprocess.run(
        ["gh", *args], check=True, capture_output=True, text=True, timeout=GH_TIMEOUT_SECONDS
    ).stdout


def release_assets(tag: str, repo: str, *, gh=None) -> set[str]:
    """The tag's asset names. ``gh`` (``(args) -> stdout``) is injectable; a failed listing raises."""
    out = (gh or _gh)(["release", "view", tag, "--repo", repo, "--json", "assets"])
    return {a["name"] for a in json.loads(out)["assets"]}


def published_seasons(assets: set[str], seasons: list[int]) -> list[int]:
    """The ``seasons`` with a ``model_pbp_<season>.parquet`` on the tag.

    The gate's span: from March to the first game the current season has no asset yet, and a
    season with nothing published has no shape to mix.
    """
    return [s for s in seasons if f"model_pbp_{s}.parquet" in assets]


def fetch_manifest(tag: str, repo: str, *, gh=None) -> pl.DataFrame:
    """The published manifest; an empty frame only when the tag has no manifest asset.

    ``gh`` (``(args) -> stdout``) is injectable for tests. A failed listing or download raises.
    """
    gh = gh or _gh
    if MANIFEST not in release_assets(tag, repo, gh=gh):
        return pl.DataFrame(schema=MANIFEST_SCHEMA)
    with tempfile.TemporaryDirectory() as d:
        gh(["release", "download", tag, "--repo", repo, "--pattern", MANIFEST, "--dir", d])
        return pl.read_csv(Path(d) / MANIFEST, schema_overrides=MANIFEST_SCHEMA)


def upsert(manifest: pl.DataFrame, parquets: list[Path]) -> pl.DataFrame:
    """Replace each parquet's season row with the stamp read from its own metadata.

    Raises ``ValueError`` on a parquet with no stamp: a manifest row has to describe the file
    that was published, never the library that happens to be installed at upload time.
    """
    rows = []
    for p in parquets:
        meta = parquet_stamp(p)
        if not meta.get("processing_version"):
            raise ValueError(f"{p.name}: no processing_version in its parquet metadata; rebuild it")
        rows.append(
            {
                "season": int(p.stem.rsplit("_", 1)[-1]),
                "row_count": pl.scan_parquet(p).select(pl.len()).collect().item(),
                "processing_version": meta["processing_version"],
                "generated_at_utc": meta.get("generated_at_utc", ""),
            }
        )
    new = pl.DataFrame(rows, schema=MANIFEST_SCHEMA)
    kept = manifest.filter(~pl.col("season").is_in(new["season"].implode()))
    return pl.concat([kept, new]).sort("season")


def publish_manifest(
    parquet_dir: str | Path, tag: str, repo: str, *, gh=None, dry_run: bool = False
) -> Path:
    """Upsert the seasons of ``parquet_dir``'s ``model_pbp_*.parquet`` into the release manifest.

    Run AFTER the parquets themselves are uploaded, so a row never names a file that is not there.
    """
    # ponytail: read-modify-write with no lock; the 20:00 UTC cron (current season) and a reprocess
    # writing at the same moment can drop one row. Keep a reprocess clear of the cron window; a lock
    # (the git_pull flock, or a release-level mutex) if they ever have to overlap.
    out = Path(parquet_dir) / MANIFEST
    if dry_run:
        print(f"[dry-run] would upsert {out.name} on {repo}:{tag}")
        return out
    gh = gh or _gh
    parquets = sorted(Path(parquet_dir).glob("model_pbp_*.parquet"))
    upsert(fetch_manifest(tag, repo, gh=gh), parquets).write_csv(out)
    gh(["release", "upload", tag, str(out), "--repo", repo, "--clobber"])
    return out


def stale_seasons(
    manifest: pl.DataFrame, seasons: list[int], current: str | None = None
) -> list[int]:
    """Seasons with no manifest row or a stamp other than the installed ``processing_version()``."""
    current = current or processing_version()
    have = dict(zip(manifest["season"].to_list(), manifest["processing_version"].to_list()))
    return [s for s in seasons if have.get(s) != current]


def rev_problems(manifest: pl.DataFrame, seasons: list[int], rev: int = SCHEMA_REV) -> list[str]:
    """Why ``seasons`` are not all on ``SCHEMA_REV`` ``rev``; empty when they are.

    The gate before a multi-season publish is called done: a season missing from the manifest was
    never stamped (built before the stamp existed), and one on another rev has the old shape.
    Compares SCHEMA_REV, not the whole stamp, so a sdv-py commit that moves no output (the cron
    installs git main) does not hold the gate shut; a commit that does move output bumps SCHEMA_REV.
    """
    have = dict(zip(manifest["season"].to_list(), manifest["processing_version"].to_list()))
    out = [f"{s}: not in {MANIFEST}" for s in seasons if s not in have]
    out += [
        f"{s}: {have[s]} (SCHEMA_REV {schema_rev(have[s])}, want {rev})"
        for s in seasons
        if s in have and schema_rev(have[s]) != rev
    ]
    return out
