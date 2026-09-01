"""Stage 08 — two-point conversion model (soft gate).

Thin numbered pipeline for ONE model: the training logic lives in
``model_training`` (shared, single implementation); this file owns the model's
operability — fingerprint skip/--force, gate rc, ledger append.

Usage::

    python -m nfl_model_08_two_pt [--force] ...
    scripts/nfl_models.sh 08
"""
from __future__ import annotations

from pathlib import Path


def main(argv: list[str] | None = None) -> int:
    from model_training._stage import decision_parser, run_stage

    args = decision_parser("nfl_model_08_two_pt").parse_args(argv)
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    def train():
        from model_training.decision_models import validate as V
        from model_training.decision_models.features import (
            make_model_mutations,
            prepare_two_pt_data,
        )
        from model_training.decision_models.ingest import load_training_pbp
        from model_training.decision_models.pipeline import TWO_PT_SEASONS
        from model_training.decision_models.trainer import train_two_pt

        df = prepare_two_pt_data(make_model_mutations(load_training_pbp(TWO_PT_SEASONS, source=args.source)))
        print(f"[two_pt] training on {df.height:,} rows...")
        model = train_two_pt(df, nrounds=args.nrounds, output_path=out_dir / "two_pt_model.ubj")
        hold = prepare_two_pt_data(make_model_mutations(load_training_pbp(TWO_PT_SEASONS, source=args.source)))
        return V.validate_two_pt(model, hold)

    from model_training.decision_models.pipeline import TWO_PT_SEASONS

    return run_stage(
        name="two_pt", suite="decision_models", force=args.force,
        config={"model": "two_pt", "seasons": [min(TWO_PT_SEASONS), max(TWO_PT_SEASONS)],
                "source": args.source, "nrounds": args.nrounds},
        artifacts=[out_dir / "two_pt_model.ubj"],
        train=train, smoke=args.nrounds is not None, soft_gate=True,
    )


if __name__ == "__main__":
    raise SystemExit(main())
