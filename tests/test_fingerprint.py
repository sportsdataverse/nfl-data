"""Unit tests for the fingerprint + ledger helpers (Track C steps 3 + 5)."""

import json
from pathlib import Path

from model_training import fingerprint as fp


def _tree(tmp_path: Path) -> Path:
    sub = tmp_path / "pkg"
    sub.mkdir()
    (sub / "a.py").write_text("X = 1\n", encoding="utf-8")
    return sub


def test_compute_is_stable_and_sensitive(tmp_path):
    sub = _tree(tmp_path)
    base = fp.compute(sub, {"seasons": [2020, 2024]})
    assert base == fp.compute(sub, {"seasons": [2020, 2024]})
    assert base != fp.compute(sub, {"seasons": [2020, 2025]})  # config change
    (sub / "a.py").write_text("X = 2\n", encoding="utf-8")
    assert base != fp.compute(sub, {"seasons": [2020, 2024]})  # code change


def test_should_skip_requires_match_and_artifacts(tmp_path):
    store = tmp_path / ".fingerprints.json"
    art = tmp_path / "m.ubj"
    fp.record(store, "ep", "abc")
    assert not fp.should_skip(store, "ep", "abc", [art])  # artifact missing
    art.write_bytes(b"x")
    assert fp.should_skip(store, "ep", "abc", [art])
    assert not fp.should_skip(store, "ep", "abc", [art], force=True)
    assert not fp.should_skip(store, "ep", "zzz", [art])  # fingerprint moved
    assert not fp.should_skip(store, "wp", "abc", [art])  # unknown key


def test_record_merges_keys(tmp_path):
    store = tmp_path / ".fingerprints.json"
    fp.record(store, "ep", "a")
    fp.record(store, "cp", "b")
    assert json.loads(store.read_text()) == {"ep": "a", "cp": "b"}


def test_append_ledger_stamps_ts_and_appends(tmp_path):
    ledger = tmp_path / "ledger.jsonl"
    fp.append_ledger(ledger, {"model": "ep", "in_published_data": False})
    fp.append_ledger(ledger, {"model": "cp", "in_published_data": False})
    lines = [json.loads(x) for x in ledger.read_text().splitlines()]
    assert [x["model"] for x in lines] == ["ep", "cp"]
    assert all("ts" in x and not x["in_published_data"] for x in lines)
