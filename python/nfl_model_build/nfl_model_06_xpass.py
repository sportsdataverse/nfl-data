"""Stage 06 — xpass model (dropback probability).

Thin numbered pipeline for ONE model: the training logic lives in
``model_training`` (shared, single implementation); this file owns the model's
operability — fingerprint skip/--force, gate rc, ledger append.

Usage::

    python -m nfl_model_build.nfl_model_06_xpass [--force] ...
    scripts/nfl_models.sh 06
"""
from __future__ import annotations

from pathlib import Path


def main(argv: list[str] | None = None) -> int:
    from nfl_model_build._stage import decision_parser, run_stage

    args = decision_parser("nfl_model_06_xpass").parse_args(argv)
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    def train():
        from model_training.decision_models import validate as V
        from model_training.decision_models.features import make_model_mutations, prepare_xpass_data
        from model_training.decision_models.ingest import load_training_pbp
        from model_training.decision_models.pipeline import HOLDOUT_SEASONS, XPASS_SEASONS
        from model_training.decision_models.trainer import train_xpass

        df = prepare_xpass_data(make_model_mutations(load_training_pbp(XPASS_SEASONS, source=args.source)))
        print(f"[xpass] training on {df.height:,} rows...")
        model = train_xpass(df, nrounds=args.nrounds, output_path=out_dir / "xpass_model.ubj")
        hold = prepare_xpass_data(make_model_mutations(load_training_pbp(HOLDOUT_SEASONS, source=args.source)))
        return V.validate_xpass(model, hold)

    from model_training.decision_models.pipeline import XPASS_SEASONS

    return run_stage(
        name="xpass", suite="decision_models", force=args.force,
        config={"model": "xpass", "seasons": [min(XPASS_SEASONS), max(XPASS_SEASONS)],
                "source": args.source, "nrounds": args.nrounds},
        artifacts=[out_dir / "xpass_model.ubj"],
        train=train, smoke=args.nrounds is not None, soft_gate=False,
    )


if __name__ == "__main__":
    raise SystemExit(main())
