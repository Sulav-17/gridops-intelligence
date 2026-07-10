"""Simple M05 production forecasting runner boundaries."""

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from gridops.config import Settings
from gridops.database import make_engine, make_session_factory
from gridops.forecasting.forecast_outputs import (
    ForecastGenerationConfig,
    generate_forecast_from_selected_artifact,
)
from gridops.forecasting.issue_contract import require_aware_utc_datetime
from gridops.forecasting.monitoring import (
    DriftMonitoringConfig,
    PerformanceMonitoringConfig,
    summarize_feature_drift,
    summarize_model_performance,
)
from gridops.forecasting.training import (
    CandidateTrainingConfig,
    train_candidate_from_feature_snapshots,
)


def build_parser() -> argparse.ArgumentParser:
    """Build the M05 production runner argument parser."""

    parser = argparse.ArgumentParser(
        prog="python -m gridops.forecasting.production_runner",
        description="Run deterministic M05 training, forecast, and monitoring helpers.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    train = subparsers.add_parser(
        "train-candidate",
        help="Train or preview a deterministic candidate from M04 feature snapshots.",
    )
    train.add_argument("--feature-version", required=True)
    train.add_argument("--training-start-utc", required=True)
    train.add_argument("--training-end-utc", required=True)
    train.add_argument("--evaluation-start-utc", required=True)
    train.add_argument("--evaluation-end-utc", required=True)
    train.add_argument("--selected-baseline-name", required=True)
    train.add_argument("--model-name")
    train.add_argument("--model-type")
    train.add_argument("--model-version")
    train.add_argument("--artifact-dir")
    train.add_argument("--created-at-utc")
    train.add_argument("--dry-run", action="store_true")
    train.add_argument("--output-path")

    forecast = subparsers.add_parser(
        "generate-forecast",
        help="Generate or preview forecast outputs from a selected model artifact.",
    )
    forecast.add_argument("--model-artifact-id", type=int, required=True)
    forecast.add_argument("--forecast-issue-time-utc", required=True)
    forecast.add_argument("--horizon-hours", type=int, default=24)
    forecast.add_argument("--created-at-utc")
    forecast.add_argument("--dry-run", action="store_true")
    forecast.add_argument("--output-path")

    monitoring = subparsers.add_parser(
        "summarize-monitoring",
        help="Summarize or preview M05 performance and drift monitoring foundations.",
    )
    monitoring.add_argument("--model-artifact-id", type=int, required=True)
    monitoring.add_argument("--evaluation-start-utc", required=True)
    monitoring.add_argument("--evaluation-end-utc", required=True)
    monitoring.add_argument("--baseline-start-utc", required=True)
    monitoring.add_argument("--baseline-end-utc", required=True)
    monitoring.add_argument("--comparison-start-utc", required=True)
    monitoring.add_argument("--comparison-end-utc", required=True)
    monitoring.add_argument("--feature-version")
    monitoring.add_argument("--created-at-utc")
    monitoring.add_argument("--dry-run", action="store_true")
    monitoring.add_argument("--output-path")

    return parser


def run(argv: list[str] | None = None) -> int:
    """Run the production forecasting CLI and return a process-style exit code."""

    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command == "train-candidate":
        payload = _train_candidate_payload(args)
    elif args.command == "generate-forecast":
        payload = _generate_forecast_payload(args)
    elif args.command == "summarize-monitoring":
        payload = _summarize_monitoring_payload(args)
    else:
        parser.error(f"unsupported command: {args.command}")

    _emit_payload(payload, output_path=args.output_path)
    return 0


def main() -> None:
    """Console entry point."""

    raise SystemExit(run())


def _train_candidate_payload(args: argparse.Namespace) -> dict[str, Any]:
    config = CandidateTrainingConfig(
        feature_version=args.feature_version,
        training_window_start_utc=_parse_utc(args.training_start_utc),
        training_window_end_utc=_parse_utc(args.training_end_utc),
        evaluation_window_start_utc=_parse_utc(args.evaluation_start_utc),
        evaluation_window_end_utc=_parse_utc(args.evaluation_end_utc),
        selected_baseline_name=args.selected_baseline_name,
        model_name=args.model_name or "gradient_boosting_candidate",
        model_type=args.model_type or "sklearn_gradient_boosting_regressor",
        model_version=args.model_version or "m05_c03_candidate_v1",
        artifact_dir=args.artifact_dir,
        created_at_utc=_parse_utc(args.created_at_utc) if args.created_at_utc else None,
    )
    if args.dry_run:
        return {
            "command": "train-candidate",
            "mode": "dry-run",
            "would_persist": False,
            "feature_version": config.feature_version,
            "selected_baseline_name": config.selected_baseline_name,
            "training_window_start_utc": config.training_window_start_utc.isoformat(),
            "training_window_end_utc": config.training_window_end_utc.isoformat(),
            "evaluation_window_start_utc": config.evaluation_window_start_utc.isoformat(),
            "evaluation_window_end_utc": config.evaluation_window_end_utc.isoformat(),
            "status": "preview",
        }

    engine = make_engine(Settings())
    try:
        session_factory = make_session_factory(engine)
        with session_factory() as session:
            result = train_candidate_from_feature_snapshots(session, config=config)
            session.commit()
            return {
                "command": "train-candidate",
                "mode": "database",
                "model_training_run_id": result.training_run.id,
                "model_artifact_id": result.artifact.id if result.artifact else None,
                "model_selection_result_id": (
                    result.selection_result.id if result.selection_result else None
                ),
                "training_row_count": result.training_row_count,
                "evaluation_row_count": result.evaluation_row_count,
                "status": result.training_run.status,
            }
    finally:
        engine.dispose()


def _generate_forecast_payload(args: argparse.Namespace) -> dict[str, Any]:
    config = ForecastGenerationConfig(
        model_artifact_id=args.model_artifact_id,
        forecast_issue_time_utc=_parse_utc(args.forecast_issue_time_utc),
        horizon_hours=args.horizon_hours,
        created_at_utc=_parse_utc(args.created_at_utc) if args.created_at_utc else None,
    )
    if args.dry_run:
        return {
            "command": "generate-forecast",
            "mode": "dry-run",
            "would_persist": False,
            "model_artifact_id": config.model_artifact_id,
            "forecast_issue_time_utc": config.forecast_issue_time_utc.isoformat(),
            "horizon_hours": config.horizon_hours,
            "status": "preview",
        }

    engine = make_engine(Settings())
    try:
        session_factory = make_session_factory(engine)
        with session_factory() as session:
            result = generate_forecast_from_selected_artifact(session, config=config)
            session.commit()
            return {
                "command": "generate-forecast",
                "mode": "database",
                "production_forecast_run_id": result.forecast_run.id,
                "prediction_count": len(result.predictions),
                "peak_output_id": result.peak_output.id if result.peak_output else None,
                "ramp_output_count": len(result.ramp_outputs),
                "status": result.forecast_run.status,
            }
    finally:
        engine.dispose()


def _summarize_monitoring_payload(args: argparse.Namespace) -> dict[str, Any]:
    performance_config = PerformanceMonitoringConfig(
        model_artifact_id=args.model_artifact_id,
        evaluation_window_start_utc=_parse_utc(args.evaluation_start_utc),
        evaluation_window_end_utc=_parse_utc(args.evaluation_end_utc),
        created_at_utc=_parse_utc(args.created_at_utc) if args.created_at_utc else None,
    )
    drift_config = DriftMonitoringConfig(
        model_artifact_id=args.model_artifact_id,
        baseline_window_start_utc=_parse_utc(args.baseline_start_utc),
        baseline_window_end_utc=_parse_utc(args.baseline_end_utc),
        comparison_window_start_utc=_parse_utc(args.comparison_start_utc),
        comparison_window_end_utc=_parse_utc(args.comparison_end_utc),
        feature_version=args.feature_version,
        created_at_utc=_parse_utc(args.created_at_utc) if args.created_at_utc else None,
    )
    if args.dry_run:
        return {
            "command": "summarize-monitoring",
            "mode": "dry-run",
            "would_persist": False,
            "model_artifact_id": args.model_artifact_id,
            "evaluation_window_start_utc": (
                performance_config.evaluation_window_start_utc.isoformat()
            ),
            "evaluation_window_end_utc": performance_config.evaluation_window_end_utc.isoformat(),
            "baseline_window_start_utc": drift_config.baseline_window_start_utc.isoformat(),
            "baseline_window_end_utc": drift_config.baseline_window_end_utc.isoformat(),
            "comparison_window_start_utc": drift_config.comparison_window_start_utc.isoformat(),
            "comparison_window_end_utc": drift_config.comparison_window_end_utc.isoformat(),
            "status": "preview",
        }

    engine = make_engine(Settings())
    try:
        session_factory = make_session_factory(engine)
        with session_factory() as session:
            performance = summarize_model_performance(session, config=performance_config)
            drift = summarize_feature_drift(session, config=drift_config)
            session.commit()
            return {
                "command": "summarize-monitoring",
                "mode": "database",
                "performance_summary_count": len(performance),
                "drift_summary_count": len(drift),
                "status": "succeeded",
            }
    finally:
        engine.dispose()


def _parse_utc(value: str) -> datetime:
    normalized = value.replace("Z", "+00:00")
    parsed = datetime.fromisoformat(normalized)
    return require_aware_utc_datetime(parsed).astimezone(UTC)


def _emit_payload(payload: dict[str, Any], *, output_path: str | None) -> None:
    rendered = json.dumps(payload, indent=2, sort_keys=True)
    if output_path:
        Path(output_path).write_text(rendered + "\n", encoding="utf-8")
    print(rendered)


if __name__ == "__main__":
    main()
