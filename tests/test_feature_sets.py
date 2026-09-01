"""features/<model>_v1.yaml ordered-equality gates (feature-set registry step 2).

v1 describes exactly what ships: each YAML's ordered ``columns`` must equal the
code constant it was generated from. The constant remains the authority until
the dependency is inverted (recorded follow-up); this gate is what lets the
registry earn that authority. Reordering two columns in a YAML must go red.
"""

from importlib import import_module
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]

MODELS = {
    "ep": "model_training.play_level.constants.EP_FEATURES",
    "wp_spread": "model_training.play_level.constants.WP_SPREAD_FEATURES",
    "wp_naive": "model_training.play_level.constants.WP_NAIVE_FEATURES",
    "cp": "model_training.play_level.constants.CP_FEATURES",
    "xyac": "model_training.play_level.constants.XYAC_FEATURES",
    "xpass": "model_training.decision_models.constants.XPASS_FEATURES",
    "fd": "model_training.decision_models.constants.FD_FEATURES",
    "two_pt": "model_training.decision_models.constants.TWO_PT_FEATURES",
    "fg": "model_training.decision_models.constants.FG_FEATURES",
    "wp": "model_training.decision_models.constants.WP_FEATURES",
}


def _constant(dotted: str) -> list[str]:
    mod_path, name = dotted.rsplit(".", 1)
    return getattr(import_module(mod_path), name)


@pytest.mark.parametrize("model", sorted(MODELS))
def test_feature_yaml_matches_code_constant(model):
    path = ROOT / "features" / f"{model}_v1.yaml"
    assert path.is_file(), f"missing {path.name}"
    doc = yaml.safe_load(path.read_text(encoding="utf-8"))
    assert doc["model"] == model
    assert doc["source_constant"] == MODELS[model]
    expected = _constant(MODELS[model])
    assert doc["columns"] == expected, (
        f"{path.name} columns diverged from {MODELS[model]} "
        "(order matters — boosters are positional)"
    )
