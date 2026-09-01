"""Stage 05 — xYAC model (76-class yards-after-catch).

Thin numbered pipeline for ONE model: the training logic lives in
``model_training`` (shared, single implementation); this file owns the model's
operability — fingerprint skip/--force, gate rc, ledger append.

Usage::

    python -m nfl_model_build.nfl_model_05_xyac [--force] ...
    scripts/nfl_models.sh 05
"""
from __future__ import annotations

from pathlib import Path


def main(argv: list[str] | None = None) -> int:
    from nfl_model_build._stage import parse_seasons, play_level_parser, run_stage

    args = play_level_parser("nfl_model_05_xyac", xyac=True).parse_args(argv)
    seasons = parse_seasons(args.seasons)

    def train():
        # Reuse the CLI's xyac path (handles source= + writes the model card).
        from model_training.play_level.__main__ import _train_xyac_model

        _train_xyac_model(seasons, args)
        return None

    xyac_path = Path(args.xyac_model)
    if not xyac_path.is_absolute() and xyac_path.parent == Path("."):
        xyac_path = Path(args.models_dir) / xyac_path.name
    return run_stage(
        name="xyac", suite="play_level", force=args.force,
        config={"model": "xyac", "seasons": seasons, "source": args.source},
        artifacts=[xyac_path],
        train=train,
    )


if __name__ == "__main__":
    raise SystemExit(main())
