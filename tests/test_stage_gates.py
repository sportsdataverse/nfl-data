"""Stage outcome labels + the loud-skip contract (``model_training._stage``).

Two review-escaping defects these pin:

* a documented SOFT gate (two_pt) printed a bare ``PASS`` when it passed —
  indistinguishable from a hard-gate pass. Every surface (console, ledger,
  report.md, train-all summary) must say ``SOFT PASS`` / ``SOFT FAIL``.
* a model that could not train (nfl4th wp without ``cal_data.rds``) returned
  ``{"skipped": True}`` and the stage / suite exited 0 — success reported while
  training nothing. A skip now fails unless the caller opts in, and is written
  to the ledger as ``status: SKIPPED`` either way.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from model_training import _stage


@pytest.mark.parametrize(
    ("gates", "soft", "smoke", "expected"),
    [
        (None, False, False, "NO GATE"),
        ({"correlation": 0.9}, False, False, "NO GATE"),
        ({"gate_pass": True}, False, False, "PASS"),
        ({"gate_pass": False}, False, False, "FAIL"),
        ({"gate_pass": False}, False, True, "FAIL (smoke run, tolerated)"),
        ({"gate_pass": True}, True, False, "SOFT PASS"),
        ({"gate_pass": False}, True, False, "SOFT FAIL"),
        ({"gate_pass": False}, True, True, "SOFT FAIL"),
        ({"skipped": True, "reason": "x"}, False, False, "SKIPPED"),
    ],
)
def test_gate_status_vocabulary(gates, soft, smoke, expected):
    assert _stage.gate_status(gates, soft_gate=soft, smoke=smoke) == expected


def test_soft_gate_never_reads_as_a_hard_pass():
    """The only label containing 'PASS' for a soft gate carries the SOFT prefix."""
    assert _stage.gate_status({"gate_pass": True}, soft_gate=True) != "PASS"
    assert _stage.gate_status({"gate_pass": True}, soft_gate=True).startswith("SOFT ")


@pytest.fixture
def stage_env(tmp_path, monkeypatch):
    """Route the ledger to tmp; artifacts live in tmp too (fingerprint store beside them)."""
    ledger = tmp_path / "ledger.jsonl"
    monkeypatch.setattr(_stage, "LEDGER", ledger)
    out = tmp_path / "out"
    out.mkdir()
    return ledger, out


def _last_ledger_line(ledger: Path) -> dict:
    return json.loads(ledger.read_text(encoding="utf-8").strip().splitlines()[-1])


def _run(out, train, **kw):
    return _stage.run_stage(
        name="wp",
        suite="decision_models",
        config={"model": "wp", "test": str(out)},
        artifacts=[out / "wp_model.ubj"],
        train=train,
        force=True,
        **kw,
    )


def test_skip_fails_the_stage_and_is_ledgered(stage_env, capsys):
    ledger, out = stage_env
    rc = _run(out, lambda: {"skipped": True, "reason": "cal_data.rds not found"})
    assert rc == 1
    entry = _last_ledger_line(ledger)
    assert entry["status"] == "SKIPPED"
    assert entry["gates"]["reason"] == "cal_data.rds not found"
    text = capsys.readouterr().out
    assert "SKIPPED: cal_data.rds not found" in text
    assert "--allow-skip" in text


def test_allow_skip_exits_zero_but_still_ledgers_skipped(stage_env):
    ledger, out = stage_env
    rc = _run(out, lambda: {"skipped": True, "reason": "no file"}, allow_skip=True)
    assert rc == 0
    assert _last_ledger_line(ledger)["status"] == "SKIPPED"


def test_skip_does_not_record_a_fingerprint(stage_env):
    """A skipped model trained nothing, so the next run must not be able to skip on 'unchanged'."""
    _ledger, out = stage_env
    _run(out, lambda: {"skipped": True, "reason": "no file"}, allow_skip=True)
    store = out / _stage.fp.FINGERPRINT_STORE
    assert not store.exists() or "wp" not in json.loads(store.read_text(encoding="utf-8"))


def _trainer(out, result):
    def train():
        (out / "wp_model.ubj").write_bytes(b"x")
        return result

    return train


@pytest.mark.parametrize(
    ("result", "soft", "rc", "label"),
    [
        ({"gate_pass": True}, True, 0, "SOFT PASS"),
        ({"gate_pass": False}, True, 0, "SOFT FAIL"),
        ({"gate_pass": True}, False, 0, "PASS"),
        ({"gate_pass": False}, False, 1, "FAIL"),
    ],
)
def test_gate_labels_reach_console_and_ledger(stage_env, capsys, result, soft, rc, label):
    ledger, out = stage_env
    assert _run(out, _trainer(out, result), soft_gate=soft) == rc
    text = capsys.readouterr().out
    assert f"parity gate: {label}" in text
    if soft:
        assert "never a hard-gate pass" in text
    assert _last_ledger_line(ledger)["status"] == label


def test_train_all_wp_block_fails_loud_without_cal_data(tmp_path, monkeypatch):
    from model_training.decision_models import pipeline

    def missing(_path=None):
        raise FileNotFoundError("cal_data.rds not found at /nowhere")

    monkeypatch.setattr(pipeline, "load_wp_cal_data", missing)
    with pytest.raises(FileNotFoundError, match="--allow-missing-cal-data"):
        pipeline._train_wp_block(tmp_path, None, None, allow_missing=False)
    result, artifact = pipeline._train_wp_block(tmp_path, None, None, allow_missing=True)
    assert result == {"skipped": True, "reason": "cal_data.rds not found at /nowhere"}
    assert artifact is None


def test_report_labels_soft_gate_and_skip(tmp_path):
    from model_training.decision_models.pipeline import _write_report

    results = {
        "two_pt": {"correlation": 0.806, "gate_pass": False, "feature_names_ok": True},
        "wp": {"skipped": True, "reason": "cal_data.rds not found"},
        "xpass": {"correlation": 0.9895, "gate_pass": False, "feature_names_ok": True},
    }
    path = tmp_path / "report.md"
    _write_report(path, results, None)
    text = path.read_text(encoding="utf-8")
    assert "| two_pt | P(success) corr | 0.8060 | ≥0.99 (SOFT gate) | SOFT FAIL |" in text
    assert "| wp | P(win) corr | — | ≥0.99 | SKIPPED (cal_data.rds not found) |" in text
    assert "| xpass | P(pass) corr | 0.9895 | ≥0.99 | FAIL |" in text
    results["two_pt"]["gate_pass"] = True
    _write_report(path, results, None)
    assert "| SOFT PASS |" in path.read_text(encoding="utf-8")
