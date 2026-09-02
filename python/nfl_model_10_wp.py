"""Stage 10 — nfl4th WP model (home-perspective, cal_data.rds).

Thin numbered pipeline for ONE model: the training logic lives in
``model_training`` (shared, single implementation); this file owns the model's
operability — fingerprint skip/--force, gate rc, ledger append.

Usage::

    python -m nfl_model_10_wp [--force] ...
    scripts/nfl_models.sh 10
"""

from __future__ import annotations

from pathlib import Path


def main(argv: list[str] | None = None) -> int:
    from model_training._stage import decision_parser, run_stage

    args = decision_parser("nfl_model_10_wp").parse_args(argv)
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    def train():
        import polars as pl
        from model_training.decision_models import validate as V
        from model_training.decision_models.features import prepare_wp_data
        from model_training.decision_models.ingest import load_wp_cal_data
        from model_training.decision_models.pipeline import WP_HOLDOUT_SEASONS
        from model_training.decision_models.trainer import train_wp

        try:
            raw = load_wp_cal_data(None)
        except FileNotFoundError as exc:
            # run_stage makes this loud: ledger status=SKIPPED, rc 1 unless --allow-skip.
            return {"skipped": True, "reason": str(exc)}
        train_raw = (
            raw.filter(~pl.col("season").is_in(WP_HOLDOUT_SEASONS))
            if "season" in raw.columns
            else raw
        )
        hold_raw = (
            raw.filter(pl.col("season").is_in(WP_HOLDOUT_SEASONS))
            if "season" in raw.columns
            else raw
        )
        df = prepare_wp_data(train_raw)
        print(f"[wp] training on {df.height:,} plays...")
        model = train_wp(df, nrounds=args.nrounds, output_path=out_dir / "wp_model.ubj")
        return V.validate_wp(model, prepare_wp_data(hold_raw))

    return run_stage(
        name="wp",
        suite="decision_models",
        force=args.force,
        config={
            "model": "wp",
            "training_data": "cal_data.rds (2001-2020, MODELS.R)",
            "source": args.source,
            "nrounds": args.nrounds,
        },
        artifacts=[out_dir / "wp_model.ubj"],
        train=train,
        smoke=args.nrounds is not None,
        soft_gate=False,
        allow_skip=args.allow_skip,
    )


if __name__ == "__main__":
    raise SystemExit(main())
