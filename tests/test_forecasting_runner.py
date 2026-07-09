"""Tests for the M04 forecasting runner."""

import json
from pathlib import Path

import pytest

from gridops.forecasting.runner import build_parser, run


def test_runner_help_or_argument_parsing_works() -> None:
    """The runner exposes the expected subcommands."""

    parser = build_parser()
    args = parser.parse_args(
        [
            "build-features",
            "--forecast-issue-time-utc",
            "2026-07-09T15:00:00Z",
            "--dry-run",
        ]
    )

    assert args.command == "build-features"
    assert args.dry_run is True


def test_dry_run_build_features_output_is_deterministic(capsys: pytest.CaptureFixture[str]) -> None:
    """Dry-run feature building emits deterministic JSON without touching live sources."""

    exit_code = run(
        [
            "build-features",
            "--forecast-issue-time-utc",
            "2026-07-09T15:00:00Z",
            "--horizon-hours",
            "2",
            "--feature-version",
            "test_feature_version",
            "--dry-run",
        ]
    )

    payload = json.loads(capsys.readouterr().out)
    assert exit_code == 0
    assert payload == {
        "command": "build-features",
        "feature_version": "test_feature_version",
        "forecast_issue_time_utc": "2026-07-09T15:00:00+00:00",
        "horizon_hours": 2,
        "mode": "dry-run",
        "status": "preview",
        "would_persist": False,
    }


def test_dry_run_run_backtest_output_is_deterministic(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Dry-run backtesting emits deterministic window summaries."""

    exit_code = run(
        [
            "run-backtest",
            "--training-start-utc",
            "2026-07-01T00:00:00Z",
            "--start-utc",
            "2026-07-08T00:00:00Z",
            "--end-utc",
            "2026-07-10T00:00:00Z",
            "--minimum-training-history-hours",
            "24",
            "--horizon-hours",
            "24",
            "--step-hours",
            "24",
            "--models",
            "same_hour_yesterday",
            "same_hour_last_week",
            "--dry-run",
        ]
    )

    payload = json.loads(capsys.readouterr().out)
    assert exit_code == 0
    assert payload["command"] == "run-backtest"
    assert payload["mode"] == "dry-run"
    assert payload["models"] == ["same_hour_yesterday", "same_hour_last_week"]
    assert payload["window_count"] == 2
    assert payload["windows"][0]["forecast_issue_time_utc"] == "2026-07-08T00:00:00+00:00"


def test_runner_report_dry_run_is_deterministic(capsys: pytest.CaptureFixture[str]) -> None:
    """Report dry-run safely summarizes implemented M04 capabilities."""

    exit_code = run(["report", "--dry-run"])

    payload = json.loads(capsys.readouterr().out)
    assert exit_code == 0
    assert payload["command"] == "report"
    assert payload["mode"] == "dry-run"
    assert payload["production_capabilities"] == []
    assert "baselines" in payload["implemented_capabilities"]


def test_runner_report_reads_output_file(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Report command can summarize prior JSON runner output."""

    input_path = tmp_path / "backtest.json"
    input_path.write_text(
        json.dumps({"command": "run-backtest", "status": "preview", "window_count": 2}),
        encoding="utf-8",
    )

    exit_code = run(["report", "--input-path", str(input_path)])

    payload = json.loads(capsys.readouterr().out)
    assert exit_code == 0
    assert payload["input_command"] == "run-backtest"
    assert payload["window_count"] == 2


def test_runner_does_not_expose_production_forecast_api_behavior() -> None:
    """Runner subcommands stay in M04 evaluation scope."""

    help_text = build_parser().format_help().lower()

    assert "forecast-api" not in help_text
    assert "serve" not in help_text
    assert "mlflow" not in help_text
