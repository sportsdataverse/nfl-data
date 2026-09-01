"""Stage 09 — FG model (field-goal make probability).

Thin numbered pipeline for ONE model: the training logic lives in
``model_training`` (shared, single implementation); this file owns the model's
operability — fingerprint skip/--force, gate rc, ledger append.

Usage::

    python -m nfl_model_09_fg [--force] ...
    scripts/nfl_models.sh 09
"""
from __future__ import annotations

from pathlib import Path


def main(argv: list[str] | None = None) -> int:
    from model_training._stage import decision_parser, run_stage

    args = decision_parser("nfl_model_09_fg").parse_args(argv)
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    def train():
        from model_training.decision_models import validate as V
        from model_training.decision_models.features import make_model_mutations, prepare_fg_data
        from model_training.decision_models.ingest import load_training_pbp
        from model_training.decision_models.pipeline import FG_SEASONS
        from model_training.decision_models.trainer import train_fg

        df = prepare_fg_data(make_model_mutations(load_training_pbp(FG_SEASONS, source=args.source)))
        print(f"[fg] training on {df.height:,} attempts...")
        model = train_fg(df, nrounds=args.nrounds, cv_select=False,
                         output_path=out_dir / "fg_model.ubj")
        return V.validate_fg(model, attempts=df)

    from model_training.decision_models.pipeline import FG_SEASONS

    return run_stage(
        name="fg", suite="decision_models", force=args.force,
        config={"model": "fg", "seasons": [min(FG_SEASONS), max(FG_SEASONS)],
                "source": args.source, "nrounds": args.nrounds},
        artifacts=[out_dir / "fg_model.ubj"],
        train=train, smoke=args.nrounds is not None, soft_gate=False,
    )


if __name__ == "__main__":
    raise SystemExit(main())
