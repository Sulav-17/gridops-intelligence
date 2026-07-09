"""Point-in-time feature snapshot generation for M04."""

import json
import math
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from gridops.forecasting.asof import (
    select_archived_weather_forecasts_asof,
    select_latest_weather_observations_asof,
)
from gridops.forecasting.horizons import ForecastHorizonTarget, generate_hourly_horizon
from gridops.forecasting.issue_contract import ForecastIssueContract, require_aware_utc_datetime
from gridops.models import (
    FeatureSnapshotRow,
    FeatureSnapshotRun,
    ForecastIssue,
    IesoHourlyDemand,
    WeatherForecast,
    WeatherObservation,
)
from gridops.quality.blocking import BlockingDecision, get_blocking_decision

DEFAULT_ROLLING_WINDOW_HOURS = 24
QUALITY_BLOCKING_BEHAVIOR = "block_on_m03_error_or_critical"
FEATURE_SNAPSHOT_PAYLOAD_VERSION = "m04_c02_feature_payload_v1"
REQUIRED_FEATURE_DATASETS = (
    "ieso_hourly_demand",
    "weather_observations",
    "weather_forecasts",
)


@dataclass(frozen=True, slots=True)
class CalendarFeatures:
    """Deterministic target-interval calendar features."""

    target_hour_utc: int
    day_of_week: int
    month: int
    season: str
    is_weekend: bool
    hour_sin: float
    hour_cos: float


@dataclass(frozen=True, slots=True)
class DemandFeatures:
    """Leakage-safe demand features for one target interval."""

    lag_1h_mw: Decimal | None
    lag_2h_mw: Decimal | None
    lag_24h_mw: Decimal | None
    lag_48h_mw: Decimal | None
    lag_168h_mw: Decimal | None
    rolling_mean_mw: Decimal | None
    rolling_min_mw: Decimal | None
    rolling_max_mw: Decimal | None
    rolling_std_mw: Decimal | None
    recent_ramp_mw: Decimal | None
    source_row_ids: tuple[int, ...]


@dataclass(frozen=True, slots=True)
class FeatureSnapshotTarget:
    """In-memory feature row before optional persistence."""

    horizon_target: ForecastHorizonTarget
    calendar_features: CalendarFeatures
    demand_features: DemandFeatures
    weather_observation_ids: tuple[int, ...]
    weather_forecast_ids: tuple[int, ...]
    payload: dict[str, object]


@dataclass(frozen=True, slots=True)
class PersistedFeatureSnapshot:
    """Persisted feature snapshot run and rows."""

    forecast_issue: ForecastIssue
    snapshot_run: FeatureSnapshotRun
    rows: tuple[FeatureSnapshotRow, ...]
    blocking_decisions: tuple[BlockingDecision, ...]


def build_feature_snapshot_targets(
    session: Session,
    *,
    contract: ForecastIssueContract,
    rolling_window_hours: int = DEFAULT_ROLLING_WINDOW_HOURS,
) -> list[FeatureSnapshotTarget]:
    """Build leakage-safe in-memory feature rows for one forecast issue."""

    issue_time = require_aware_utc_datetime(contract.forecast_issue_time_utc)
    horizon = generate_hourly_horizon(contract)
    demand_history = _load_current_demand_history(session, issue_time)
    observations = select_latest_weather_observations_asof(
        session,
        forecast_issue_time_utc=issue_time,
    )
    forecasts = select_archived_weather_forecasts_asof(
        session,
        forecast_issue_time_utc=issue_time,
        valid_times_utc=[target.target_interval_start_utc for target in horizon],
    )

    return [
        _build_target_features(
            target,
            demand_history=demand_history,
            observations=observations,
            forecasts=forecasts,
            rolling_window_hours=rolling_window_hours,
        )
        for target in horizon
    ]


def persist_feature_snapshot(
    session: Session,
    *,
    contract: ForecastIssueContract,
    generated_at_utc: datetime,
    rolling_window_hours: int = DEFAULT_ROLLING_WINDOW_HOURS,
) -> PersistedFeatureSnapshot:
    """Persist one M04 feature snapshot using the C01 schema foundation."""

    generated_at = require_aware_utc_datetime(generated_at_utc)
    issue_time = require_aware_utc_datetime(contract.forecast_issue_time_utc)
    forecast_issue = _get_or_create_forecast_issue(
        session,
        contract=contract,
        created_at_utc=generated_at,
    )
    blocking_decisions = tuple(
        get_blocking_decision(session, dataset_name=dataset_name)
        for dataset_name in REQUIRED_FEATURE_DATASETS
    )
    blocked_decisions = [decision for decision in blocking_decisions if decision.is_blocked]

    if blocked_decisions:
        forecast_issue.status = "blocked"
        snapshot_run = FeatureSnapshotRun(
            forecast_issue_id=forecast_issue.id,
            feature_version=contract.feature_version,
            status="blocked",
            quality_status="blocked",
            started_at_utc=generated_at,
            completed_at_utc=generated_at,
            safe_error_detail=_blocking_summary(blocked_decisions),
        )
        session.add(snapshot_run)
        session.flush()
        return PersistedFeatureSnapshot(
            forecast_issue=forecast_issue,
            snapshot_run=snapshot_run,
            rows=(),
            blocking_decisions=blocking_decisions,
        )

    forecast_issue.status = "ready"
    targets = build_feature_snapshot_targets(
        session,
        contract=contract,
        rolling_window_hours=rolling_window_hours,
    )
    snapshot_run = FeatureSnapshotRun(
        forecast_issue_id=forecast_issue.id,
        feature_version=contract.feature_version,
        status="succeeded",
        quality_status="usable",
        started_at_utc=generated_at,
        completed_at_utc=generated_at,
        safe_error_detail=None,
    )
    session.add(snapshot_run)
    session.flush()

    rows = tuple(
        _persist_snapshot_row(
            session,
            snapshot_run=snapshot_run,
            target=target,
            issue_time=issue_time,
            feature_version=contract.feature_version,
        )
        for target in targets
    )
    session.flush()

    return PersistedFeatureSnapshot(
        forecast_issue=forecast_issue,
        snapshot_run=snapshot_run,
        rows=rows,
        blocking_decisions=blocking_decisions,
    )


def make_calendar_features(target_interval_start_utc: datetime) -> CalendarFeatures:
    """Create deterministic UTC calendar features for a target interval."""

    target_start = require_aware_utc_datetime(target_interval_start_utc)
    hour_angle = 2.0 * math.pi * (target_start.hour / 24.0)

    return CalendarFeatures(
        target_hour_utc=target_start.hour,
        day_of_week=target_start.weekday(),
        month=target_start.month,
        season=_season_for_month(target_start.month),
        is_weekend=target_start.weekday() >= 5,
        hour_sin=round(math.sin(hour_angle), 12),
        hour_cos=round(math.cos(hour_angle), 12),
    )


def make_demand_features(
    *,
    target_interval_start_utc: datetime,
    forecast_issue_time_utc: datetime,
    demand_history: Sequence[IesoHourlyDemand],
    rolling_window_hours: int = DEFAULT_ROLLING_WINDOW_HOURS,
) -> DemandFeatures:
    """Create demand lag and rolling features without future leakage."""

    target_start = require_aware_utc_datetime(target_interval_start_utc)
    issue_time = require_aware_utc_datetime(forecast_issue_time_utc)
    demand_by_start = {
        row.interval_start_utc: row
        for row in demand_history
        if row.is_current and row.interval_end_utc <= issue_time
    }

    lag_rows = {
        lag_hours: _safe_lag_row(
            demand_by_start,
            target_start=target_start,
            forecast_issue_time_utc=issue_time,
            lag_hours=lag_hours,
        )
        for lag_hours in (1, 2, 24, 48, 168)
    }
    rolling_rows = [
        row
        for row in sorted(
            demand_history,
            key=lambda value: (value.interval_end_utc, value.id or 0),
        )
        if row.is_current
        and row.interval_end_utc <= issue_time
        and row.interval_end_utc > issue_time - timedelta(hours=rolling_window_hours)
    ]
    rolling_values = [row.demand_mw for row in rolling_rows]
    source_row_ids = {
        row.id
        for row in (*lag_rows.values(), *rolling_rows)
        if row is not None and row.id is not None
    }

    return DemandFeatures(
        lag_1h_mw=_demand_value(lag_rows[1]),
        lag_2h_mw=_demand_value(lag_rows[2]),
        lag_24h_mw=_demand_value(lag_rows[24]),
        lag_48h_mw=_demand_value(lag_rows[48]),
        lag_168h_mw=_demand_value(lag_rows[168]),
        rolling_mean_mw=_mean(rolling_values),
        rolling_min_mw=min(rolling_values) if rolling_values else None,
        rolling_max_mw=max(rolling_values) if rolling_values else None,
        rolling_std_mw=_population_std(rolling_values),
        recent_ramp_mw=_recent_ramp(rolling_rows),
        source_row_ids=tuple(sorted(source_row_ids)),
    )


def _build_target_features(
    target: ForecastHorizonTarget,
    *,
    demand_history: Sequence[IesoHourlyDemand],
    observations: dict[str, WeatherObservation],
    forecasts: dict[tuple[str, str, datetime], WeatherForecast],
    rolling_window_hours: int,
) -> FeatureSnapshotTarget:
    calendar_features = make_calendar_features(target.target_interval_start_utc)
    demand_features = make_demand_features(
        target_interval_start_utc=target.target_interval_start_utc,
        forecast_issue_time_utc=target.forecast_issue_time_utc,
        demand_history=demand_history,
        rolling_window_hours=rolling_window_hours,
    )
    target_forecasts = [
        forecast
        for key, forecast in sorted(forecasts.items())
        if key[2] == target.target_interval_start_utc
    ]
    observation_ids = tuple(sorted(row.id for row in observations.values() if row.id is not None))
    forecast_ids = tuple(sorted(row.id for row in target_forecasts if row.id is not None))
    payload = _feature_payload(
        calendar_features=calendar_features,
        demand_features=demand_features,
        observations=observations,
        forecasts=target_forecasts,
    )

    return FeatureSnapshotTarget(
        horizon_target=target,
        calendar_features=calendar_features,
        demand_features=demand_features,
        weather_observation_ids=observation_ids,
        weather_forecast_ids=forecast_ids,
        payload=payload,
    )


def _load_current_demand_history(
    session: Session,
    forecast_issue_time_utc: datetime,
) -> list[IesoHourlyDemand]:
    return list(
        session.scalars(
            select(IesoHourlyDemand)
            .where(
                IesoHourlyDemand.is_current.is_(True),
                IesoHourlyDemand.interval_end_utc <= forecast_issue_time_utc,
            )
            .order_by(IesoHourlyDemand.interval_end_utc, IesoHourlyDemand.id)
        ).all()
    )


def _get_or_create_forecast_issue(
    session: Session,
    *,
    contract: ForecastIssueContract,
    created_at_utc: datetime,
) -> ForecastIssue:
    existing = session.scalar(
        select(ForecastIssue).where(
            ForecastIssue.forecast_issue_time_utc == contract.forecast_issue_time_utc,
            ForecastIssue.forecast_type == contract.forecast_type,
            ForecastIssue.feature_version == contract.feature_version,
        )
    )
    if existing is not None:
        return existing

    forecast_issue = ForecastIssue(
        forecast_issue_time_utc=contract.forecast_issue_time_utc,
        horizon_length_hours=contract.horizon_length_hours,
        forecast_type=contract.forecast_type,
        feature_version=contract.feature_version,
        point_in_time_safety_rule=contract.point_in_time_safety_rule,
        status="defined",
        quality_blocking_behavior=QUALITY_BLOCKING_BEHAVIOR,
        created_at_utc=created_at_utc,
    )
    session.add(forecast_issue)
    session.flush()

    return forecast_issue


def _persist_snapshot_row(
    session: Session,
    *,
    snapshot_run: FeatureSnapshotRun,
    target: FeatureSnapshotTarget,
    issue_time: datetime,
    feature_version: str,
) -> FeatureSnapshotRow:
    row = FeatureSnapshotRow(
        feature_snapshot_run_id=snapshot_run.id,
        forecast_issue_time_utc=issue_time,
        target_interval_start_utc=target.horizon_target.target_interval_start_utc,
        target_interval_end_utc=target.horizon_target.target_interval_end_utc,
        lead_hour=target.horizon_target.lead_hour,
        feature_version=feature_version,
        quality_status="usable",
        demand_source_row_id=_first_or_none(target.demand_features.source_row_ids),
        weather_observation_source_row_id=_first_or_none(target.weather_observation_ids),
        weather_forecast_source_row_id=_first_or_none(target.weather_forecast_ids),
        related_quality_run_id=None,
        lineage_metadata=json.dumps(target.payload, sort_keys=True),
    )
    session.add(row)

    return row


def _safe_lag_row(
    demand_by_start: dict[datetime, IesoHourlyDemand],
    *,
    target_start: datetime,
    forecast_issue_time_utc: datetime,
    lag_hours: int,
) -> IesoHourlyDemand | None:
    lag_start = target_start - timedelta(hours=lag_hours)
    row = demand_by_start.get(lag_start)
    if row is None or row.interval_end_utc > forecast_issue_time_utc:
        return None

    return row


def _feature_payload(
    *,
    calendar_features: CalendarFeatures,
    demand_features: DemandFeatures,
    observations: dict[str, WeatherObservation],
    forecasts: Sequence[WeatherForecast],
) -> dict[str, object]:
    return {
        "payload_version": FEATURE_SNAPSHOT_PAYLOAD_VERSION,
        "calendar": {
            "target_hour_utc": calendar_features.target_hour_utc,
            "day_of_week": calendar_features.day_of_week,
            "month": calendar_features.month,
            "season": calendar_features.season,
            "is_weekend": calendar_features.is_weekend,
            "hour_sin": calendar_features.hour_sin,
            "hour_cos": calendar_features.hour_cos,
        },
        "demand": {
            "lag_1h_mw": _json_decimal(demand_features.lag_1h_mw),
            "lag_2h_mw": _json_decimal(demand_features.lag_2h_mw),
            "lag_24h_mw": _json_decimal(demand_features.lag_24h_mw),
            "lag_48h_mw": _json_decimal(demand_features.lag_48h_mw),
            "lag_168h_mw": _json_decimal(demand_features.lag_168h_mw),
            "rolling_mean_mw": _json_decimal(demand_features.rolling_mean_mw),
            "rolling_min_mw": _json_decimal(demand_features.rolling_min_mw),
            "rolling_max_mw": _json_decimal(demand_features.rolling_max_mw),
            "rolling_std_mw": _json_decimal(demand_features.rolling_std_mw),
            "recent_ramp_mw": _json_decimal(demand_features.recent_ramp_mw),
            "source_row_ids": list(demand_features.source_row_ids),
        },
        "weather_observations": {
            station_id: {
                "row_id": row.id,
                "observed_at_utc": row.observed_at_utc.isoformat(),
                "temperature_c": _json_decimal(row.temperature_c),
                "relative_humidity_percent": _json_decimal(row.relative_humidity_percent),
                "wind_speed_kph": _json_decimal(row.wind_speed_kph),
                "precipitation_mm": _json_decimal(row.precipitation_mm),
            }
            for station_id, row in sorted(observations.items())
        },
        "weather_forecasts": [
            {
                "row_id": row.id,
                "forecast_location": row.forecast_location,
                "variable_name": row.variable_name,
                "issue_time_utc": row.issue_time_utc.isoformat(),
                "valid_time_utc": row.valid_time_utc.isoformat(),
                "variable_value": _json_decimal(row.variable_value),
                "variable_unit": row.variable_unit,
            }
            for row in forecasts
        ],
    }


def _season_for_month(month: int) -> str:
    if month in (12, 1, 2):
        return "winter"
    if month in (3, 4, 5):
        return "spring"
    if month in (6, 7, 8):
        return "summer"
    return "fall"


def _demand_value(row: IesoHourlyDemand | None) -> Decimal | None:
    return row.demand_mw if row is not None else None


def _mean(values: Sequence[Decimal]) -> Decimal | None:
    if not values:
        return None

    return sum(values) / Decimal(len(values))


def _population_std(values: Sequence[Decimal]) -> Decimal | None:
    if not values:
        return None

    mean = _mean(values)
    if mean is None:
        return None
    variance = sum((value - mean) ** 2 for value in values) / Decimal(len(values))

    return Decimal(str(math.sqrt(float(variance))))


def _recent_ramp(rows: Sequence[IesoHourlyDemand]) -> Decimal | None:
    if len(rows) < 2:
        return None

    return rows[-1].demand_mw - rows[-2].demand_mw


def _json_decimal(value: Decimal | None) -> str | None:
    return str(value) if value is not None else None


def _first_or_none(values: Sequence[int]) -> int | None:
    return values[0] if values else None


def _blocking_summary(decisions: Sequence[BlockingDecision]) -> str:
    summaries = []
    for decision in decisions:
        reasons = "; ".join(decision.blocking_reasons) or "blocked"
        summaries.append(f"{decision.dataset_name}: {reasons}")

    return " | ".join(summaries)[:1000]
