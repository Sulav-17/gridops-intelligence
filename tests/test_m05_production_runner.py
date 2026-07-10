"""Tests for the M05 production forecasting runner."""

import json

import pytest

from gridops.forecasting.production_runner import build_parser, run


def test_production_runner_argument_parsing_works() -> None:
    """The runner exposes the expected M05 production helper commands."""

    parser = build_parser()
    args = parser.parse_args(
        [
            "generate-forecast",
            "--model-artifact-id",
            "7",
            "--forecast-issue-time-utc",
            "2026-07-09T15:00:00Z",
            "--dry-run",
        ]
    )

    assert args.command == "generate-forecast"
    assert args.model_artifact_id == 7
    assert args.dry_run is True


def test_train_candidate_dry_run_behavior_is_deterministic(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Dry-run candidate training emits deterministic JSON and writes nothing."""

    exit_code = run(
        [
            "train-candidate",
            "--feature-version",
            "m04_c01_foundation",
            "--training-start-utc",
            "2026-01-01T00:00:00Z",
            "--training-end-utc",
            "2026-01-02T00:00:00Z",
            "--evaluation-start-utc",
            "2026-01-02T00:00:00Z",
            "--evaluation-end-utc",
            "2026-01-03T00:00:00Z",
            "--selected-baseline-name",
            "same_hour_yesterday",
            "--dry-run",
        ]
    )

    payload = json.loads(capsys.readouterr().out)
    assert exit_code == 0
    assert payload == {
        "command": "train-candidate",
        "evaluation_window_end_utc": "2026-01-03T00:00:00+00:00",
        "evaluation_window_start_utc": "2026-01-02T00:00:00+00:00",
        "feature_version": "m04_c01_foundation",
        "mode": "dry-run",
        "selected_baseline_name": "same_hour_yesterday",
        "status": "preview",
        "training_window_end_utc": "2026-01-02T00:00:00+00:00",
        "training_window_start_utc": "2026-01-01T00:00:00+00:00",
        "would_persist": False,
    }


def test_generate_forecast_dry_run_behavior_is_deterministic(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Dry-run forecast generation emits deterministic JSON and writes nothing."""

    exit_code = run(
        [
            "generate-forecast",
            "--model-artifact-id",
            "5",
            "--forecast-issue-time-utc",
            "2026-02-09T10:00:00Z",
            "--horizon-hours",
            "24",
            "--dry-run",
        ]
    )

    payload = json.loads(capsys.readouterr().out)
    assert exit_code == 0
    assert payload == {
        "command": "generate-forecast",
        "forecast_issue_time_utc": "2026-02-09T10:00:00+00:00",
        "horizon_hours": 24,
        "mode": "dry-run",
        "model_artifact_id": 5,
        "status": "preview",
        "would_persist": False,
    }


def test_summarize_monitoring_dry_run_behavior_is_deterministic(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Dry-run monitoring emits deterministic JSON and writes nothing."""

    exit_code = run(
        [
            "summarize-monitoring",
            "--model-artifact-id",
            "5",
            "--evaluation-start-utc",
            "2026-02-01T00:00:00Z",
            "--evaluation-end-utc",
            "2026-02-02T00:00:00Z",
            "--baseline-start-utc",
            "2026-01-01T00:00:00Z",
            "--baseline-end-utc",
            "2026-01-02T00:00:00Z",
            "--comparison-start-utc",
            "2026-02-01T00:00:00Z",
            "--comparison-end-utc",
            "2026-02-02T00:00:00Z",
            "--dry-run",
        ]
    )

    payload = json.loads(capsys.readouterr().out)
    assert exit_code == 0
    assert payload["command"] == "summarize-monitoring"
    assert payload["mode"] == "dry-run"
    assert payload["would_persist"] is False
    assert payload["model_artifact_id"] == 5


def test_production_runner_does_not_expose_future_scope() -> None:
    """Runner commands stay inside M05 and avoid M06/M07 product surfaces."""

    help_text = build_parser().format_help().lower()

    assert "alert" not in help_text
    assert "scenario" not in help_text
    assert "dashboard" not in help_text
    assert "deployment" not in help_text
    assert "briefing" not in help_text
    assert "serve" not in help_text
