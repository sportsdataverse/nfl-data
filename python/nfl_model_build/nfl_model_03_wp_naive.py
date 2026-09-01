"""Stage 03 — WP model, naive (no-spread) variant.

Thin numbered pipeline for ONE model: the training logic lives in
``model_training`` (shared, single implementation); this file owns the model's
operability — fingerprint skip/--force, gate rc, ledger append.

Usage::

    python -m nfl_model_build.nfl_model_03_wp_naive [--force] ...
    scripts/nfl_models.sh 03
"""
from __future__ import annotations

from pathlib import Path


def main(argv: list[str] | None = None) -> int:
    from nfl_model_build._stage import parse_seasons, play_level_parser, run_stage

    args = play_level_parser("nfl_model_03_wp_naive").parse_args(argv)
    seasons = parse_seasons(args.seasons)

    def train():
        from model_training.play_level.pipeline import run_wp_pipeline

        run_wp_pipeline(seasons, variant="naive", data_dir=Path(args.data_dir),
             models_dir=Path(args.models_dir), download=args.download)
        return None  # gate = `python -m model_training.play_level validate` (EP/WP parity)

    return run_stage(
        name="wp_naive", suite="play_level", force=args.force,
        config={"model": "wp_naive", "seasons": seasons, "source": "nflverse"},
        artifacts=[Path(args.models_dir) / "wp_naive.ubj"],
        train=train,
    )


if __name__ == "__main__":
    raise SystemExit(main())
