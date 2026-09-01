"""models/REGISTRY.md must carry one row per artifact this repo publishes.

The guard BITES per-artifact (delete the ep_model row and this fails) — the
cfbfastR-cfb-data lesson was a registry test that matched package names, so a
deleted row still passed. Required artifacts come from the importable publish
constants where they exist; the play-level set is asserted explicitly because
its filenames live in the trainer, not a publish map.
"""

from pathlib import Path

from nfl_model_publish.decision_models_artifacts import (
    DECISION_MODELS_BUNDLE_ARTIFACTS,
    DECISION_MODELS_RELEASE_MAP,
)

REGISTRY = Path(__file__).resolve().parents[1] / "models" / "REGISTRY.md"

#: play_level artifacts (trainer-owned filenames; .json sidecars ride along).
PLAY_LEVEL = [
    "ep_model.ubj",
    "wp_naive.ubj",
    "wp_spread.ubj",
    "cp_model.ubj",
    "xyac_model.ubj",
]

#: dataset-shaped decision surface (per-season parquet family).
DATA_SURFACES = ["nfl_ratings_weekly_{season}.parquet"]


def _table_rows() -> list[str]:
    text = REGISTRY.read_text(encoding="utf-8")
    return [ln for ln in text.splitlines() if ln.startswith("|") and "---" not in ln]


def test_registry_exists_and_has_tables():
    assert REGISTRY.is_file(), "models/REGISTRY.md is missing"
    assert len(_table_rows()) >= 10


def test_every_published_artifact_has_a_row():
    rows = _table_rows()
    required = (
        list(DECISION_MODELS_RELEASE_MAP)
        + list(DECISION_MODELS_BUNDLE_ARTIFACTS)
        + PLAY_LEVEL
        + DATA_SURFACES
    )
    missing = [a for a in required if not any(a in r for r in rows)]
    assert not missing, f"artifacts with no registry TABLE ROW: {missing}"


def test_release_map_tags_match_registry():
    """The tag named beside each mapped artifact's row must be the publish map's tag."""
    rows = _table_rows()
    for artifact, tag in DECISION_MODELS_RELEASE_MAP.items():
        row = next(r for r in rows if artifact in r)
        assert tag in row, f"{artifact}: registry row does not name its tag {tag}"


def test_bundle_artifacts_marked_tagless():
    rows = _table_rows()
    for artifact in DECISION_MODELS_BUNDLE_ARTIFACTS:
        row = next(r for r in rows if artifact in r)
        assert "sdv-py bundle" in row, f"{artifact}: bundle row must say it has no release tag"
