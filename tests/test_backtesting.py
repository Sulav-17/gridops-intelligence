"""Tests for deterministic M04 backtest windows."""

from datetime import UTC, datetime

from gridops.forecasting.backtesting import BacktestConfig, generate_backtest_windows


def test_expanding_backtest_windows_are_ordered_and_deterministic() -> None:
    """Expanding windows are ordered and use deterministic time boundaries."""

    config = BacktestConfig(
        training_start_utc=datetime(2026, 7, 1, tzinfo=UTC),
        evaluation_start_utc=datetime(2026, 7, 8, tzinfo=UTC),
        evaluation_end_utc=datetime(2026, 7, 10, tzinfo=UTC),
        forecast_horizon_hours=24,
        step_hours=24,
        minimum_training_history_hours=24,
    )

    windows = generate_backtest_windows(config)

    assert [window.window_index for window in windows] == [0, 1]
    assert [window.forecast_issue_time_utc for window in windows] == [
        datetime(2026, 7, 8, tzinfo=UTC),
        datetime(2026, 7, 9, tzinfo=UTC),
    ]
    assert all(window.training_window_start_utc == config.training_start_utc for window in windows)
    assert windows[0].training_window_end_utc == datetime(2026, 7, 8, tzinfo=UTC)


def test_rolling_backtest_windows_use_rolling_training_start() -> None:
    """Rolling windows respect the configured rolling training duration."""

    config = BacktestConfig(
        training_start_utc=datetime(2026, 7, 1, tzinfo=UTC),
        evaluation_start_utc=datetime(2026, 7, 8, tzinfo=UTC),
        evaluation_end_utc=datetime(2026, 7, 9, tzinfo=UTC),
        minimum_training_history_hours=24,
        window_strategy="rolling",
        rolling_training_window_hours=48,
    )

    windows = generate_backtest_windows(config)

    assert len(windows) == 1
    assert windows[0].training_window_start_utc == datetime(2026, 7, 6, tzinfo=UTC)
    assert windows[0].training_window_end_utc == datetime(2026, 7, 8, tzinfo=UTC)


def test_final_test_period_is_reserved_in_config() -> None:
    """Windows stop before the reserved final untouched test period."""

    config = BacktestConfig(
        training_start_utc=datetime(2026, 7, 1, tzinfo=UTC),
        evaluation_start_utc=datetime(2026, 7, 8, tzinfo=UTC),
        evaluation_end_utc=datetime(2026, 7, 12, tzinfo=UTC),
        step_hours=24,
        minimum_training_history_hours=24,
        final_test_period_start_utc=datetime(2026, 7, 10, tzinfo=UTC),
        final_test_period_end_utc=datetime(2026, 7, 12, tzinfo=UTC),
    )

    windows = generate_backtest_windows(config)

    assert config.final_test_period_start_utc is not None
    assert windows[-1].forecast_issue_time_utc == datetime(2026, 7, 9, tzinfo=UTC)
    assert all(
        window.evaluation_window_end_utc <= config.final_test_period_start_utc for window in windows
    )
