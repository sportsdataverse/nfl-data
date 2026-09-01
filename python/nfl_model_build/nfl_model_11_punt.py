"""Stage 11 — punt distribution artifact (punt_data.parquet).

Thin numbered pipeline for ONE model: the training logic lives in
``model_training`` (shared, single implementation); this file owns the model's
operability — fingerprint skip/--force, gate rc, ledger append.

Usage::

    python -m nfl_model_build.nfl_model_11_punt [--force] ...
    scripts/nfl_models.sh 11
"""
from __future__ import annotations

from pathlib import Path


def main(argv: list[str] | None = None) -> int:
    from nfl_model_build._stage import decision_parser, run_stage

    args = decision_parser("nfl_model_11_punt").parse_args(argv)
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    def train():
        import polars as pl
        from model_training.decision_models import validate as V
        from model_training.decision_models.ingest import load_training_pbp
        from model_training.decision_models.pipeline import PUNT_SEASONS
        from model_training.decision_models.trainer import build_punt_data

        raw = load_training_pbp(PUNT_SEASONS, source=args.source)
        punt_df = build_punt_data(raw, output_path=out_dir / "punt_data.parquet")
        weights = {
            float(r["yardline_100"]): float(r["n"])
            for r in raw.filter(pl.col("play_type_nfl") == "PUNT")
            .group_by(pl.col("yardline_100").cast(pl.Float64))
            .agg(pl.len().alias("n"))
            .iter_rows(named=True)
        }
        return V.validate_punt(punt_df, punt_weights=weights)

    from model_training.decision_models.pipeline import PUNT_SEASONS

    return run_stage(
        name="punt", suite="decision_models", force=args.force,
        config={"model": "punt", "seasons": [min(PUNT_SEASONS), max(PUNT_SEASONS)],
                "source": args.source, "nrounds": args.nrounds},
        artifacts=[out_dir / "punt_data.parquet"],
        train=train, smoke=args.nrounds is not None, soft_gate=False,
    )


if __name__ == "__main__":
    raise SystemExit(main())
