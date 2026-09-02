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


# ---------------------------------------------------------------------------
# Fitted constants travel with the feature set: spread_time decay exponent
# ---------------------------------------------------------------------------

WP_FAMILY = ("wp_spread", "wp_naive", "wp")
_EXPONENT_CONSTANT = "model_training.play_level.constants.SPREAD_TIME_DECAY_EXPONENT"


@pytest.mark.parametrize("model", WP_FAMILY)
def test_wp_feature_yaml_registers_the_decay_exponent(model):
    """spread_time / Diff_Time_Ratio are DERIVED with a fitted exponent; the registry names it."""
    from model_training.play_level.constants import SPREAD_TIME_DECAY_EXPONENT

    doc = yaml.safe_load((ROOT / "features" / f"{model}_v1.yaml").read_text(encoding="utf-8"))
    dc = doc["derived_constants"]
    assert dc["source_constant"] == _EXPONENT_CONSTANT
    assert dc["spread_time_decay_exponent"] == SPREAD_TIME_DECAY_EXPONENT


def test_decay_exponent_trainer_equals_applier():
    """Trainer (nfl-data) and applier (sdv-py) read the same exponent.

    A retrain that changes it must land in BOTH repos; this is the assertion that
    the two agree, run on every nfl-data push (sdv-py is a dependency here).
    """
    from model_training.play_level.constants import SPREAD_TIME_DECAY_EXPONENT
    from sportsdataverse.nfl.model_vars import SPREAD_TIME_DECAY_EXPONENT as APPLIER_EXPONENT

    assert SPREAD_TIME_DECAY_EXPONENT == APPLIER_EXPONENT == -4.0


def test_wp_model_card_records_the_exponent(tmp_path):
    """The card the WP stages write carries the constant — assert the OUTPUT, not that code ran."""
    import json

    from model_training.play_level.constants import SPREAD_TIME_DECAY_EXPONENT
    from model_training.play_level.model_card import write_model_card
    from model_training.play_level.pipeline import wp_card_extra

    card_path = write_model_card(
        tmp_path / "wp_spread.ubj",
        model_type="wp_spread",
        features=["spread_time"],
        label="label",
        seasons=[1999, 2025],
        n_rows=1,
        hyperparams={"objective": "binary:logistic"},
        source="nflverse",
        extra=wp_card_extra(),
    )
    card = json.loads(card_path.read_text(encoding="utf-8"))
    assert (
        card["derived_feature_constants"]["spread_time_decay_exponent"]
        == SPREAD_TIME_DECAY_EXPONENT
    )
