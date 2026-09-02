"""Stage 11 — punt distribution artifact (punt_data.parquet).

Thin numbered pipeline for ONE model: the training logic lives in
``model_training`` (shared, single implementation); this file owns the model's
operability — fingerprint skip/--force, gate rc, ledger append.

Usage::

    python -m nfl_model_11_punt [--force] ...
    scripts/nfl_models.sh 11
"""

from __future__ import annotations

from pathlib import Path

#: Seasons the reality gate scores the surface against (the most recent N of
#: PUNT_SEASONS). Three keeps ~6.5k punts -- enough that the per-yardline
#: empirical CDFs are not sampling noise -- while staying recent enough that
#: era drift in punt coverage would actually show up.
RECENT_SEASONS_FOR_GATE = 3


def main(argv: list[str] | None = None) -> int:
    from model_training._stage import decision_parser, run_stage

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
        oracle = V.validate_punt(punt_df, punt_weights=weights)
        print(f"[punt] oracle parity: {oracle}")

        # Second, independent gate: does the surface still describe how punts
        # actually land? The oracle gate above cannot see this -- a surface can
        # reproduce the frozen R distribution perfectly and still have drifted
        # away from the modern game. NOTE: with PUNT_SEASONS = full history these
        # seasons are INSIDE the training span, so this reads as "the surface
        # describes recent punting", not as out-of-sample generalization; pass a
        # genuinely held-out frame to validate_punt_holdout for that.
        recent = sorted(PUNT_SEASONS)[-RECENT_SEASONS_FOR_GATE:]
        holdout = raw.filter(pl.col("season").is_in(recent)).select(
            "desc", "play_type", "yardline_100", "kick_distance", "return_yards"
        )
        reality = V.validate_punt_holdout(punt_df, holdout)
        print(f"[punt] holdout seasons {recent}: {reality}")

        merged = {f"oracle_{k}": v for k, v in oracle.items() if k != "gate_pass"}
        merged.update({f"holdout_{k}": v for k, v in reality.items() if k != "gate_pass"})
        merged["oracle_gate_pass"] = oracle["gate_pass"]
        merged["holdout_gate_pass"] = reality["gate_pass"]
        # run_stage keys the stage rc off "gate_pass": both must hold.
        merged["gate_pass"] = bool(oracle["gate_pass"] and reality["gate_pass"])
        return merged

    from model_training.decision_models.pipeline import PUNT_SEASONS

    return run_stage(
        name="punt",
        suite="decision_models",
        force=args.force,
        config={
            "model": "punt",
            "seasons": [min(PUNT_SEASONS), max(PUNT_SEASONS)],
            "source": args.source,
            "nrounds": args.nrounds,
        },
        artifacts=[out_dir / "punt_data.parquet"],
        train=train,
        smoke=args.nrounds is not None,
        soft_gate=False,
    )


if __name__ == "__main__":
    raise SystemExit(main())
