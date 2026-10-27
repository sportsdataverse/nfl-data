"""The nfl_model_pbp processing-version manifest (offline: ``gh`` is a fake release)."""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import polars as pl
import pytest
from nfl_espn_build.config import SCHEMA_REV, processing_version
from nfl_model_publish import cli
from nfl_model_publish import pbp_manifest as pm

TAG, REPO = "nfl_model_pbp", "owner/repo"


class FakeRelease:
    """``gh release view|download|upload`` over a dict of asset name -> local file."""

    def __init__(self, store: Path, *, fail_view: bool = False):
        self.store, self.fail_view, self.calls = store, fail_view, []
        store.mkdir(parents=True, exist_ok=True)

    def __call__(self, args: list[str]) -> str:
        self.calls.append(args)
        verb = args[1]
        if verb == "view":
            if self.fail_view:
                raise subprocess.CalledProcessError(1, ["gh", *args], stderr="HTTP 502")
            return json.dumps({"assets": [{"name": p.name} for p in self.store.iterdir()]})
        if verb == "download":
            name, dest = args[args.index("--pattern") + 1], args[args.index("--dir") + 1]
            shutil.copy(self.store / name, Path(dest) / name)
        elif verb == "upload":
            shutil.copy(args[3], self.store / Path(args[3]).name)
        return ""


def _parquet(d: Path, season: int, stamp: str | None, rows: int = 3) -> Path:
    d.mkdir(parents=True, exist_ok=True)
    p = d / f"model_pbp_{season}.parquet"
    meta = (
        {"processing_version": stamp, "generated_at_utc": "2026-10-27 00:00:00 UTC"}
        if stamp
        else None
    )
    pl.DataFrame({"play_id": list(range(rows))}).write_parquet(p, metadata=meta)
    return p


def _manifest(rows: dict[int, str]) -> pl.DataFrame:
    return pl.DataFrame(
        {
            "season": list(rows),
            "row_count": [1] * len(rows),
            "processing_version": list(rows.values()),
            "generated_at_utc": [""] * len(rows),
        },
        schema=pm.MANIFEST_SCHEMA,
    )


def test_schema_rev_reads_the_stamp_tail():
    assert pm.schema_rev("0.2.0+699409c9.7") == 7
    assert pm.schema_rev("0.2.0+8") == 8  # a PyPI install has no sha segment
    assert pm.schema_rev("0.2.0b1+abc.12") == 12
    assert pm.schema_rev(None) is None
    assert pm.schema_rev("0.2.0") is None


def test_publish_upserts_into_the_published_manifest(tmp_path):
    """A one-season reprocess dir must not clobber the other seasons' rows."""
    gh = FakeRelease(tmp_path / "release")
    _manifest({2023: "old+1", 2024: "old+1"}).write_csv(gh.store / pm.MANIFEST)
    work = tmp_path / "w"
    _parquet(work, 2024, "0.2.0+abc.9", rows=5)

    pm.publish_manifest(work, TAG, REPO, gh=gh)

    got = pl.read_csv(gh.store / pm.MANIFEST, schema_overrides=pm.MANIFEST_SCHEMA)
    assert got.rows() == [
        (2023, 1, "old+1", ""),
        (2024, 5, "0.2.0+abc.9", "2026-10-27 00:00:00 UTC"),
    ]


def test_first_publish_starts_the_manifest(tmp_path):
    gh = FakeRelease(tmp_path / "release")
    pm.publish_manifest(_parquet(tmp_path / "w", 1999, "v+1").parent, TAG, REPO, gh=gh)
    assert pl.read_csv(gh.store / pm.MANIFEST)["season"].to_list() == [1999]


def test_a_failed_listing_raises_instead_of_reading_as_no_manifest(tmp_path):
    """Taken for 'no manifest yet', a 502 would upload a one-row manifest over all of them."""
    gh = FakeRelease(tmp_path / "release", fail_view=True)
    with pytest.raises(subprocess.CalledProcessError):
        pm.publish_manifest(_parquet(tmp_path / "w", 2024, "v+1").parent, TAG, REPO, gh=gh)
    assert not any(c[1] == "upload" for c in gh.calls)


def test_an_unstamped_parquet_is_refused(tmp_path):
    with pytest.raises(ValueError, match="no processing_version"):
        pm.upsert(pl.DataFrame(schema=pm.MANIFEST_SCHEMA), [_parquet(tmp_path, 2024, None)])


def test_stale_seasons_are_missing_or_on_another_stamp():
    m = _manifest({2022: "cur", 2023: "old", 2024: "cur"})
    assert pm.stale_seasons(m, [2021, 2022, 2023, 2024], current="cur") == [2021, 2023]


def test_rev_gate_flags_missing_and_mixed_seasons():
    cur = processing_version()
    old = f"0.1.9+deadbeef.{SCHEMA_REV - 1}"
    m = _manifest({2023: cur, 2024: old, 2025: f"0.2.0+other.{SCHEMA_REV}"})

    problems = pm.rev_problems(m, [2022, 2023, 2024, 2025])

    assert problems == [
        f"2022: not in {pm.MANIFEST}",
        f"2024: {old} (SCHEMA_REV {SCHEMA_REV - 1}, want {SCHEMA_REV})",
    ]  # 2025: another sdv-py commit on the same SCHEMA_REV passes
    assert pm.rev_problems(m, [2023, 2025]) == []


def test_pbp_publish_writes_the_manifest_after_the_parquets(tmp_path, monkeypatch):
    gh = FakeRelease(tmp_path / "release")
    work = tmp_path / "w"
    _parquet(work, 2024, "v+1")
    order: list[str] = []
    monkeypatch.setattr(
        cli,
        "upload_artifacts",
        lambda *a, **k: order.append("parquets") or {"files": ["x"], "uploaded": 1, "tag": TAG},
    )
    monkeypatch.setattr(pm, "_gh", lambda args: order.append(args[1]) or gh(args))

    assert cli.main(["pbp", "--parquet-dir", str(work), "--repo", REPO]) == 0
    assert order == ["parquets", "view", "upload"]  # no manifest yet, so nothing to download
    assert (gh.store / pm.MANIFEST).exists()

    order.clear()
    cli.main(["pbp", "--parquet-dir", str(work), "--repo", REPO, "--no-manifest"])
    assert order == ["parquets"]


def test_check_cli_exits_1_on_a_stale_season(tmp_path, monkeypatch, capsys):
    gh = FakeRelease(tmp_path / "release")
    _manifest({2024: processing_version(), 2025: "0.1.0+1"}).write_csv(gh.store / pm.MANIFEST)
    monkeypatch.setattr(pm, "_gh", gh)

    assert cli.main(["pbp-manifest", "--check", "2024", "--repo", REPO]) == 0
    assert cli.main(["pbp-manifest", "--check", "2024:2025", "--repo", REPO]) == 1
    assert "2025: 0.1.0+1" in capsys.readouterr().out

    assert cli.main(["pbp-manifest", "--stale", "2023:2025", "--repo", REPO]) == 0
    assert capsys.readouterr().out.split() == ["2023", "2025"]
