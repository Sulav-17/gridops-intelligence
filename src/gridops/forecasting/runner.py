"""Simple forecasting runner for M04 evaluation workflows."""

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from gridops.config import Settings
from gridops.database import make_engine, make_session_factory
from gridops.forecasting.backtesting import BacktestConfig, generate_backtest_windows
from gridops.forecasting.baselines import BASELINE_NAMES
from gridops.forecasting.feature_snapshots import persist_feature_snapshot
from gridops.forecasting.issue_contract import (
    DEFAULT_FORECASTING_FEATURE_VERSION,
    DEFAULT_HORIZON_HOURS,
    ForecastIssueContract,
    require_aware_utc_datetime,
)


def build_parser() -> argparse.ArgumentParser:
    """Build the forecasting runner argument parser."""

    parser = argparse.ArgumentParser(
        prog="python -m gridops.forecasting.runner",
        description="Run deterministic M04 forecasting evaluation helpers.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    build_features = subparsers.add_parser(
        "build-features",
        help="Build or preview point-in-time feature snapshot rows.",
    )
    build_features.add_argument("--forecast-issue-time-utc", required=True)
    build_features.add_argument("--horizon-hours", type=int, default=DEFAULT_HORIZON_HOURS)
    build_features.add_argument(
        "--feature-version",
        default=DEFAULT_FORECASTING_FEATURE_VERSION,
    )
    build_features.add_argument("--generated-at-utc")
    build_features.add_argument("--output-path")
    build_features.add_argument("--dry-run", action="store_true")

    run_backtest = subparsers.add_parser(
        "run-backtest",
        help="Preview deterministic M04 backtest windows.",
    )
    run_backtest.add_argument("--start-utc", required=True)
    run_backtest.add_argument("--end-utc", required=True)
    run_backtest.add_argument("--training-start-utc", required=True)
    run_backtest.add_argument("--horizon-hours", type=int, default=DEFAULT_HORIZON_HOURS)
    run_backtest.add_argument("--step-hours", type=int, default=24)
    run_backtest.add_argument("--minimum-training-history-hours", type=int, default=168)
    run_backtest.add_argument("--final-test-period-start-utc")
    run_backtest.add_argument("--final-test-period-end-utc")
    run_backtest.add_argument(
        "--window-strategy", choices=("expanding", "rolling"), default="expanding"
    )
    run_backtest.add_argument("--rolling-training-window-hours", type=int)
    run_backtest.add_argument(
        "--models", nargs="+", choices=BASELINE_NAMES, default=list(BASELINE_NAMES)
    )
    run_backtest.add_argument("--output-path")
    run_backtest.add_argument("--dry-run", action="store_true")

    report = subparsers.add_parser(
        "report",
        help="Summarize M04 forecasting evaluation capabilities or a JSON runner output.",
    )
    report.add_argument("--input-path")
    report.add_argument("--output-path")
    report.add_argument("--dry-run", action="store_true")

    return parser


def run(argv: list[str] | None = None) -> int:
    """Run the forecasting CLI and return a process-style exit code."""

    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command == "build-features":
        payload = _build_features_payload(args)
    elif args.command == "run-backtest":
        payload = _run_backtest_payload(args)
    elif args.command == "report":
        payload = _report_payload(args)
    else:
        parser.error(f"unsupported command: {args.command}")

    _emit_payload(payload, output_path=args.output_path)
    return 0


def main() -> None:
    """Console entry point."""

    raise SystemExit(run())


def _build_features_payload(args: argparse.Namespace) -> dict[str, Any]:
    issue_time = _parse_utc(args.forecast_issue_time_utc)
    generated_at = _parse_utc(args.generated_at_utc) if args.generated_at_utc else issue_time
    contract = ForecastIssueContract(
        forecast_issue_time_utc=issue_time,
        horizon_length_hours=args.horizon_hours,
        feature_version=args.feature_version,
    )
    if args.dry_run:
        return {
            "command": "build-features",
            "mode": "dry-run",
            "forecast_issue_time_utc": contract.forecast_issue_time_utc.isoformat(),
            "horizon_hours": contract.horizon_length_hours,
            "feature_version": contract.feature_version,
            "would_persist": False,
            "status": "preview",
        }

    engine = make_engine(Settings())
    try:
        session_factory = make_session_factory(engine)
        with session_factory() as session:
            result = persist_feature_snapshot(
                session,
                contract=contract,
                generated_at_utc=generated_at,
            )
            session.commit()
            return {
                "command": "build-features",
                "mode": "database",
                "forecast_issue_id": result.forecast_issue.id,
                "feature_snapshot_run_id": result.snapshot_run.id,
                "status": result.snapshot_run.status,
                "quality_status": result.snapshot_run.quality_status,
                "row_count": len(result.rows),
            }
    finally:
        engine.dispose()


def _run_backtest_payload(args: argparse.Namespace) -> dict[str, Any]:
    config = BacktestConfig(
        training_start_utc=_parse_utc(args.training_start_utc),
        evaluation_start_utc=_parse_utc(args.start_utc),
        evaluation_end_utc=_parse_utc(args.end_utc),
        forecast_horizon_hours=args.horizon_hours,
        step_hours=args.step_hours,
        minimum_training_history_hours=args.minimum_training_history_hours,
        final_test_period_start_utc=(
            _parse_utc(args.final_test_period_start_utc)
            if args.final_test_period_start_utc
            else None
        ),
        final_test_period_end_utc=(
            _parse_utc(args.final_test_period_end_utc) if args.final_test_period_end_utc else None
        ),
        window_strategy=args.window_strategy,
        rolling_training_window_hours=args.rolling_training_window_hours,
    )
    windows = generate_backtest_windows(config)
    return {
        "command": "run-backtest",
        "mode": "dry-run" if args.dry_run else "preview",
        "models": list(args.models),
        "window_strategy": config.window_strategy,
        "window_count": len(windows),
        "final_test_period": {
            "start_utc": (
                config.final_test_period_start_utc.isoformat()
                if config.final_test_period_start_utc
                else None
            ),
            "end_utc": (
                config.final_test_period_end_utc.isoformat()
                if config.final_test_period_end_utc
                else None
            ),
        },
        "windows": [
            {
                "window_index": window.window_index,
                "training_window_start_utc": window.training_window_start_utc.isoformat(),
                "training_window_end_utc": window.training_window_end_utc.isoformat(),
                "forecast_issue_time_utc": window.forecast_issue_time_utc.isoformat(),
                "evaluation_window_start_utc": window.evaluation_window_start_utc.isoformat(),
                "evaluation_window_end_utc": window.evaluation_window_end_utc.isoformat(),
                "forecast_horizon_hours": window.forecast_horizon_hours,
            }
            for window in windows
        ],
        "status": "preview",
    }


def _report_payload(args: argparse.Namespace) -> dict[str, Any]:
    if args.input_path:
        input_payload = json.loads(Path(args.input_path).read_text(encoding="utf-8"))
        return {
            "command": "report",
            "mode": "file",
            "input_command": input_payload.get("command"),
            "status": input_payload.get("status", "unknown"),
            "window_count": input_payload.get("window_count"),
            "row_count": input_payload.get("row_count"),
        }

    return {
        "command": "report",
        "mode": "dry-run" if args.dry_run else "summary",
        "status": "preview",
        "implemented_capabilities": [
            "forecast_issue_contract",
            "point_in_time_feature_snapshots",
            "asof_joins",
            "baselines",
            "backtest_windows",
            "metrics",
            "slice_reports",
        ],
        "production_capabilities": [],
        "message": "M04 evaluation foundation is implemented; production forecasting is deferred to M05.",
    }


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
