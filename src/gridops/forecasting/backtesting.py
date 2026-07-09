"""Deterministic rolling and expanding backtest window definitions."""

from dataclasses import dataclass
from datetime import datetime, timedelta

from gridops.forecasting.issue_contract import require_aware_utc_datetime


@dataclass(frozen=True, slots=True)
class BacktestConfig:
    """Configuration for deterministic time-based backtesting."""

    training_start_utc: datetime
    evaluation_start_utc: datetime
    evaluation_end_utc: datetime
    forecast_horizon_hours: int = 24
    step_hours: int = 24
    minimum_training_history_hours: int = 168
    final_test_period_start_utc: datetime | None = None
    final_test_period_end_utc: datetime | None = None
    window_strategy: str = "expanding"
    rolling_training_window_hours: int | None = None

    def __post_init__(self) -> None:
        require_aware_utc_datetime(self.training_start_utc)
        require_aware_utc_datetime(self.evaluation_start_utc)
        require_aware_utc_datetime(self.evaluation_end_utc)
        if self.final_test_period_start_utc is not None:
            require_aware_utc_datetime(self.final_test_period_start_utc)
        if self.final_test_period_end_utc is not None:
            require_aware_utc_datetime(self.final_test_period_end_utc)
        if self.training_start_utc >= self.evaluation_start_utc:
            raise ValueError("training_start_utc must be before evaluation_start_utc")
        if self.evaluation_start_utc >= self.evaluation_end_utc:
            raise ValueError("evaluation_start_utc must be before evaluation_end_utc")
        if self.forecast_horizon_hours <= 0:
            raise ValueError("forecast_horizon_hours must be positive")
        if self.step_hours <= 0:
            raise ValueError("step_hours must be positive")
        if self.minimum_training_history_hours < 0:
            raise ValueError("minimum_training_history_hours cannot be negative")
        if self.window_strategy not in {"expanding", "rolling"}:
            raise ValueError("window_strategy must be expanding or rolling")
        if self.window_strategy == "rolling" and (
            self.rolling_training_window_hours is None or self.rolling_training_window_hours <= 0
        ):
            raise ValueError("rolling strategy requires positive rolling_training_window_hours")
        if (
            self.final_test_period_start_utc is not None
            and self.final_test_period_end_utc is not None
            and self.final_test_period_start_utc >= self.final_test_period_end_utc
        ):
            raise ValueError("final test period start must be before final test period end")


@dataclass(frozen=True, slots=True)
class BacktestWindow:
    """One deterministic backtest window."""

    training_window_start_utc: datetime
    training_window_end_utc: datetime
    forecast_issue_time_utc: datetime
    evaluation_window_start_utc: datetime
    evaluation_window_end_utc: datetime
    forecast_horizon_hours: int
    window_index: int


def generate_backtest_windows(config: BacktestConfig) -> list[BacktestWindow]:
    """Generate ordered time-based windows without random splitting."""

    evaluation_limit = config.evaluation_end_utc
    if config.final_test_period_start_utc is not None:
        evaluation_limit = min(evaluation_limit, config.final_test_period_start_utc)

    windows: list[BacktestWindow] = []
    issue_time = config.evaluation_start_utc
    while issue_time < evaluation_limit:
        if issue_time - config.training_start_utc >= timedelta(
            hours=config.minimum_training_history_hours
        ):
            training_start = _training_start_for_issue(config, issue_time)
            evaluation_end = min(
                issue_time + timedelta(hours=config.forecast_horizon_hours),
                evaluation_limit,
            )
            if issue_time < evaluation_end:
                windows.append(
                    BacktestWindow(
                        training_window_start_utc=training_start,
                        training_window_end_utc=issue_time,
                        forecast_issue_time_utc=issue_time,
                        evaluation_window_start_utc=issue_time,
                        evaluation_window_end_utc=evaluation_end,
                        forecast_horizon_hours=config.forecast_horizon_hours,
                        window_index=len(windows),
                    )
                )
        issue_time += timedelta(hours=config.step_hours)

    return windows


def _training_start_for_issue(config: BacktestConfig, issue_time: datetime) -> datetime:
    if config.window_strategy == "expanding":
        return config.training_start_utc

    assert config.rolling_training_window_hours is not None
    rolling_start = issue_time - timedelta(hours=config.rolling_training_window_hours)
    return max(config.training_start_utc, rolling_start)
