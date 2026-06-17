"""model_card.json sidecar for trained NFL models.

Matches the cfbfastR rb_eval model-card pattern: a JSON sidecar written next to
each ``.ubj`` capturing the training contract (features, label, seasons, row
count, hyperparameters, data source, train date) plus an optional metrics
snapshot. Lets a consumer audit what a shipped model was trained on without
loading it.
"""
from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence


def write_model_card(
    model_path: Path | str,
    *,
    model_type: str,
    features: Sequence[str],
    label: str,
    seasons: Sequence[int],
    n_rows: int,
    hyperparams: Dict[str, Any],
    source: str,
    metrics: Optional[Dict[str, Any]] = None,
    extra: Optional[Dict[str, Any]] = None,
) -> Path:
    """Write ``<model_path>.json`` describing how a model was trained.

    Args:
        model_path: Path to the ``.ubj`` model (the card is its ``.json`` sibling).
        model_type: One of ``ep`` / ``wp_spread`` / ``wp_naive`` / ``cp``.
        features: Ordered feature names the model expects.
        label: Target column name.
        seasons: Training seasons (min/max recorded as the range).
        n_rows: Number of training rows.
        hyperparams: The model's hyperparameter dict (from constants).
        source: ``native`` (nfl/raw reconstruction) or ``nflverse``.
        metrics: Optional metrics snapshot (e.g. LOSO calibration error, Brier).
        extra: Optional extra keys merged into the card.

    Returns:
        Path to the written ``.json`` card.
    """
    try:
        import xgboost
        xgb_version = xgboost.__version__
    except Exception:  # noqa: BLE001
        xgb_version = "unknown"

    seasons = sorted(int(s) for s in seasons)
    card: Dict[str, Any] = {
        "model_type": model_type,
        "xgboost_version": xgb_version,
        "objective": hyperparams.get("objective"),
        "features": list(features),
        "n_features": len(features),
        "label": label,
        "training_seasons": [seasons[0], seasons[-1]] if seasons else None,
        "n_training_rows": int(n_rows),
        "hyperparameters": dict(hyperparams),
        "source": source,
        "trained_date": date.today().isoformat(),
    }
    if metrics:
        card["metrics"] = metrics
    if extra:
        card.update(extra)

    card_path = Path(model_path).with_suffix(".json")
    card_path.parent.mkdir(parents=True, exist_ok=True)
    card_path.write_text(json.dumps(card, indent=2), encoding="utf-8")
    return card_path
