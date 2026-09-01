"""models/manifest.yaml is the single home for the model list (Track C step 2).

Per-row biting guards: the manifest, models/REGISTRY.md, the publish routing
maps, and the numbered nfl_model_build stage scripts must all agree. Deleting
a model from any one of them goes red here.
"""

import re
from importlib import import_module
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "models" / "manifest.yaml"
REGISTRY = ROOT / "models" / "REGISTRY.md"
STAGES_DIR = ROOT / "python" / "nfl_model_build"

KNOWN_TAGS = {"nfl_model_artifacts", "nfl_4th_down_models"}

# Registry rows for artifacts NOT trained in this repo (honest TODO rows) --
# excluded from the reverse check deliberately; adding one here is a decision.
EXTERNAL_ARTIFACTS = {"qbr_model.ubj"}


def _suites() -> dict:
    return yaml.safe_load(MANIFEST.read_text(encoding="utf-8"))["suites"]


def _stage_files() -> list[Path]:
    return sorted(STAGES_DIR.glob("nfl_model_[0-9][0-9]_*.py"))


def test_manifest_parses_with_two_suites():
    assert set(_suites()) == {"play_level", "decision_models"}


def test_every_model_has_artifact_stage_known_tag_and_feature_file():
    for suite, spec in _suites().items():
        for model, m in spec["models"].items():
            assert m["artifact"], f"{suite}/{model} missing artifact"
            assert m["release_tag"] in KNOWN_TAGS, f"{suite}/{model} unknown tag"
            stage = ROOT / m["stage"]
            assert stage.is_file(), f"{suite}/{model} stage script missing: {m['stage']}"
            assert stage.stem.endswith(f"_{model}"), f"{suite}/{model} stage name mismatch"
            if model != "punt":  # distribution artifact, no feature set
                feat = ROOT / m["features"]
                assert feat.is_file(), f"{suite}/{model} missing {m['features']}"


def test_stage_scripts_and_manifest_agree_bidirectionally():
    stage_models = {p.stem.split("_", 3)[3] for p in _stage_files()}
    manifest_models = {m for spec in _suites().values() for m in spec["models"]}
    assert stage_models == manifest_models, (
        f"stage-only={stage_models - manifest_models}, "
        f"manifest-only={manifest_models - stage_models}"
    )


def test_stage_modules_import_and_expose_main():
    for p in _stage_files():
        mod = import_module(f"nfl_model_build.{p.stem}")
        assert callable(getattr(mod, "main", None)), f"{p.stem} has no main()"


def test_registry_and_manifest_agree_per_artifact():
    registry = REGISTRY.read_text(encoding="utf-8")
    manifest_artifacts = {
        m["artifact"] for spec in _suites().values() for m in spec["models"].values()
    }
    # every manifest artifact is a registry row...
    for art in sorted(manifest_artifacts):
        assert art in registry, f"manifest artifact {art} has no REGISTRY.md row"
    # ...and every artifact-looking token in the registry is in the manifest
    # (a model added to the registry without a manifest entry goes red too).
    for art in set(re.findall(r"[a-z0-9_]+\.(?:ubj|parquet)", registry)):
        if "pbp" not in art and art not in EXTERNAL_ARTIFACTS:
            assert art in manifest_artifacts, f"registry names {art}, manifest does not"


def test_decision_models_match_publish_routing():
    from nfl_model_publish.decision_models_artifacts import (
        DECISION_MODELS_BUNDLE_ARTIFACTS,
        DECISION_MODELS_RELEASE_MAP,
    )

    routed = set(DECISION_MODELS_RELEASE_MAP) | set(DECISION_MODELS_BUNDLE_ARTIFACTS)
    manifest = {m["artifact"] for m in _suites()["decision_models"]["models"].values()}
    assert manifest == routed, (
        "decision_models manifest and publish routing diverged: "
        f"manifest-only={manifest - routed}, routing-only={routed - manifest}"
    )
