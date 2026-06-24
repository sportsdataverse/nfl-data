"""CLI entrypoint for the NFL EP/WP/CP training pipeline.

Supports three subcommands:

    train   — run the full training pipeline (EP + WP-spread + WP-naive + CP)
    validate — run the EP/WP parity gate against nflfastR reference values
    fetch   — build the raw JSON file library from the NFL Shield API

Usage examples::

    # Train all models on 2012-2024 seasons, downloading PBP first:
    uv run python -m model_training.play_level train \\
        --seasons 2012 2024 --download

    # Train without downloading (PBP already on disk):
    uv run python -m model_training.play_level train \\
        --seasons 2020 2021 2022 2023 2024

    # Validate saved models against 2022-2023 reference seasons:
    uv run python -m model_training.play_level validate \\
        --ep-model models/ep_model.ubj \\
        --wp-model models/wp_spread.ubj \\
        --sample-seasons 2022 2023

    # Fetch raw weekly JSON from NFL API for 2023-2024:
    uv run python -m model_training.play_level fetch \\
        --seasons 2023 2024 --season-types REG POST
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Windows consoles default to cp1252, which cannot encode the Unicode arrows/symbols
# in our progress output -> UnicodeEncodeError mid-run. Force UTF-8 stdout/stderr at
# entry so `python -m ...` works regardless of the console codepage.
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")


def _parse_season_range(values: list[str]) -> list[int]:
    """Convert 1 or 2 season args into a list.

    If a single value is given it is used as-is (one season).
    If two values are given they are treated as an inclusive range.
    More than two values are returned as-is (explicit list).
    """
    seasons = [int(v) for v in values]
    if len(seasons) == 2:
        start, end = seasons
        return list(range(start, end + 1))
    return seasons


def _train_xyac_model(seasons: list[int], args: argparse.Namespace) -> Path:
    """Build the xYAC training set and train + save the 76-class xYAC model.

    Mirrors the CP path but is invoked from the CLI (not run_full_pipeline) so the
    xYAC model can be trained alongside the others or on its own via ``--xyac-only``.
    """
    from .constants import XYAC_FEATURES, XYAC_HYPERPARAMS
    from .label import build_xyac_training_set
    from .pipeline import _resolve_pbp
    from .trainer import train_xyac

    models_dir = Path(args.models_dir)
    models_dir.mkdir(parents=True, exist_ok=True)
    xyac_path = Path(args.xyac_model)
    if not xyac_path.is_absolute() and xyac_path.parent == Path("."):
        xyac_path = models_dir / xyac_path.name
    xyac_path.parent.mkdir(parents=True, exist_ok=True)

    print(f"[train] loading PBP for xYAC (source={args.source})...")
    df = _resolve_pbp(seasons, Path(args.data_dir), args.download, args.source)
    print(f"[train] building xYAC training set from {df.height:,} plays...")
    xyac_df = build_xyac_training_set(df)
    print(f"[train] xYAC: {xyac_df.height:,} completed passes → training (76-class)")
    train_xyac(xyac_df, output_path=xyac_path)

    # Write a model_card.json sidecar, mirroring the pipeline's other models.
    try:
        from .model_card import write_model_card
        write_model_card(xyac_path, model_type="xyac", features=XYAC_FEATURES,
                         label="label", seasons=seasons, n_rows=xyac_df.height,
                         hyperparams=XYAC_HYPERPARAMS, source=args.source)
    except Exception as exc:  # noqa: BLE001
        print(f"[train] (xYAC model card skipped: {exc})")
    print(f"[train] xYAC model saved → {xyac_path}")
    return xyac_path


def _cmd_train(args: argparse.Namespace) -> int:
    seasons = _parse_season_range(args.seasons)
    print(f"[train] seasons={seasons[0]}–{seasons[-1]}  download={args.download}")

    if args.xyac_only:
        _train_xyac_model(seasons, args)
        return 0

    from .pipeline import run_full_pipeline

    paths = run_full_pipeline(
        seasons=seasons,
        data_dir=Path(args.data_dir),
        models_dir=Path(args.models_dir),
        download=args.download,
        source=args.source,
    )

    print("[train] Models saved (+ model_card.json sidecars):")
    for key, path in paths.items():
        print(f"  {key:12s} → {path}")

    # xYAC is trained from the CLI (not run_full_pipeline) so it stays optional + the
    # core EP/WP/CP pipeline contract is unchanged. Train it unless suppressed.
    if not args.no_xyac:
        xyac_path = _train_xyac_model(seasons, args)
        print(f"  {'xyac':12s} → {xyac_path}")
    return 0


def _cmd_report(args: argparse.Namespace) -> int:
    from .report import run_report

    seasons = _parse_season_range(args.seasons)
    print(f"[report] seasons={seasons[0]}–{seasons[-1]}  source={args.source}  out={args.out_dir}")
    metrics = run_report(
        seasons=seasons,
        source=args.source,
        out_dir=Path(args.out_dir),
        data_dir=Path(args.data_dir),
        nrounds=args.nrounds,
        make_figures=not args.no_figures,
    )
    print(f"[report] EP cal_error={metrics['ep']['cal_error']:.4f}  "
          f"WP cal_error={metrics['wp']['cal_error']:.4f} brier={metrics['wp']['brier']:.4f}  "
          f"CP cal_error={metrics['cp']['cal_error']['overall']:.4f} brier={metrics['cp']['brier']:.4f}")
    print(f"[report] wrote metrics.json + report.md (+ figures) to {args.out_dir}")
    return 0


def _cmd_validate(args: argparse.Namespace) -> int:
    from .validate import run_parity_gate

    result = run_parity_gate(
        ep_model_path=Path(args.ep_model),
        wp_model_path=Path(args.wp_model),
        sample_seasons=list(args.sample_seasons),
        data_dir=Path(args.data_dir),
        ep_correlation_threshold=args.ep_threshold,
        wp_brier_threshold=args.wp_threshold,
    )

    return 0 if result["overall_pass"] else 1


def _cmd_fetch(args: argparse.Namespace) -> int:
    from .fetcher import build_raw_library

    seasons = _parse_season_range(args.seasons)
    season_types = tuple(args.season_types)
    print(f"[fetch] seasons={seasons[0]}–{seasons[-1]}  types={season_types}")

    paths = build_raw_library(
        seasons=seasons,
        output_dir=Path(args.output_dir),
        season_types=season_types,
        resume=not args.no_resume,
    )

    print(f"[fetch] {len(paths)} file(s) written to {args.output_dir}")
    return 0


def _build_parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(
        prog="python -m model_training.play_level",
        description="NFL EP/WP/CP model training pipeline",
    )
    sub = root.add_subparsers(dest="command", required=True)

    # ------------------------------------------------------------------ train
    p_train = sub.add_parser("train", help="Train all EP/WP/CP models")
    p_train.add_argument(
        "--seasons", nargs="+", required=True, metavar="YEAR",
        help="One season, two seasons as a range (e.g. 2012 2024), or a list",
    )
    p_train.add_argument("--data-dir", default="data", metavar="DIR",
                         help="Directory with (or to receive) PBP parquet files")
    p_train.add_argument("--models-dir", default="models", metavar="DIR",
                         help="Directory where .ubj model files are written")
    p_train.add_argument("--download", action="store_true",
                         help="Download PBP from nflverse before training")
    p_train.add_argument("--source", choices=["nflverse", "native"], default="nflverse",
                         help="PBP source: nflverse parquet or native nfl/raw reconstruction")
    p_train.add_argument("--xyac-model", default="models/xyac_model.ubj", metavar="PATH",
                         help="Path for the trained 76-class xYAC model (default models/xyac_model.ubj)")
    p_train.add_argument("--xyac-only", action="store_true",
                         help="Train ONLY the xYAC model (skip EP/WP/CP)")
    p_train.add_argument("--no-xyac", action="store_true",
                         help="Skip the xYAC model (train only EP/WP/CP)")

    # ----------------------------------------------------------------- report
    p_report = sub.add_parser("report", help="LOSO calibration report (tables + figures + metrics)")
    p_report.add_argument("--seasons", nargs="+", required=True, metavar="YEAR",
                          help="One season, two as a range, or an explicit list")
    p_report.add_argument("--source", choices=["nflverse", "native"], default="native",
                          help="PBP source (default native)")
    p_report.add_argument("--out-dir", default="reports", metavar="DIR",
                          help="Directory for figures, calibration tables, metrics.json, report.md")
    p_report.add_argument("--data-dir", default="data", metavar="DIR",
                          help="PBP parquet cache (nflverse source only)")
    p_report.add_argument("--nrounds", type=int, default=None, metavar="N",
                          help="Per-fold boosting rounds (small=quick; default canonical)")
    p_report.add_argument("--no-figures", action="store_true",
                          help="Skip PNG generation (write tables + metrics only)")

    # --------------------------------------------------------------- validate
    p_val = sub.add_parser("validate", help="Run EP/WP parity gate")
    p_val.add_argument("--ep-model", required=True, metavar="PATH",
                       help="Path to ep_model.ubj")
    p_val.add_argument("--wp-model", required=True, metavar="PATH",
                       help="Path to wp_spread.ubj")
    p_val.add_argument("--sample-seasons", nargs="+", type=int, required=True,
                       metavar="YEAR", help="Seasons to compare against nflfastR")
    p_val.add_argument("--data-dir", default="data", metavar="DIR",
                       help="Directory containing PBP parquet files")
    p_val.add_argument("--ep-threshold", type=float, default=0.98, metavar="R",
                       help="Minimum Pearson r for EP gate (default 0.98)")
    p_val.add_argument("--wp-threshold", type=float, default=0.20, metavar="BS",
                       help="Maximum Brier score for WP gate (default 0.20)")

    # ------------------------------------------------------------------ fetch
    p_fetch = sub.add_parser("fetch", help="Build raw JSON library from NFL API")
    p_fetch.add_argument(
        "--seasons", nargs="+", required=True, metavar="YEAR",
        help="One season, two seasons as a range, or explicit list",
    )
    p_fetch.add_argument("--output-dir", default="data/raw", metavar="DIR",
                         help="Root directory for raw JSON files")
    p_fetch.add_argument(
        "--season-types", nargs="+", default=["REG", "POST"],
        metavar="TYPE", help="Season types to fetch (default: REG POST)",
    )
    p_fetch.add_argument("--no-resume", action="store_true",
                         help="Re-fetch files even if they already exist on disk")

    return root


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    if args.command == "train":
        return _cmd_train(args)
    if args.command == "report":
        return _cmd_report(args)
    if args.command == "validate":
        return _cmd_validate(args)
    if args.command == "fetch":
        return _cmd_fetch(args)

    parser.print_help()
    return 1


if __name__ == "__main__":
    sys.exit(main())
