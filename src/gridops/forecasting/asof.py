"""Point-in-time-safe as-of joins for M04 feature snapshots."""

from collections.abc import Iterable
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from gridops.forecasting.issue_contract import require_aware_utc_datetime
from gridops.models import WeatherForecast, WeatherObservation


def select_latest_weather_observations_asof(
    session: Session,
    *,
    forecast_issue_time_utc: datetime,
    station_ids: Iterable[str] | None = None,
) -> dict[str, WeatherObservation]:
    """Return latest current observation at or before issue time per station."""

    issue_time = require_aware_utc_datetime(forecast_issue_time_utc)
    query = (
        select(WeatherObservation)
        .where(
            WeatherObservation.is_current.is_(True),
            WeatherObservation.observed_at_utc <= issue_time,
        )
        .order_by(
            WeatherObservation.source_station_id,
            WeatherObservation.observed_at_utc.desc(),
            WeatherObservation.id.desc(),
        )
    )
    if station_ids is not None:
        query = query.where(WeatherObservation.source_station_id.in_(tuple(station_ids)))

    latest_by_station: dict[str, WeatherObservation] = {}
    for row in session.scalars(query):
        latest_by_station.setdefault(row.source_station_id, row)

    return latest_by_station


def select_archived_weather_forecasts_asof(
    session: Session,
    *,
    forecast_issue_time_utc: datetime,
    valid_times_utc: Iterable[datetime],
    locations: Iterable[str] | None = None,
    variables: Iterable[str] | None = None,
) -> dict[tuple[str, str, datetime], WeatherForecast]:
    """Return latest current archived forecast issued at or before issue time.

    Selection is per ``(location, variable, valid_time_utc)`` with deterministic
    tie-breaking by latest issue time and highest persisted row id.
    """

    issue_time = require_aware_utc_datetime(forecast_issue_time_utc)
    valid_times = tuple(require_aware_utc_datetime(value) for value in valid_times_utc)
    if not valid_times:
        return {}

    query = (
        select(WeatherForecast)
        .where(
            WeatherForecast.is_current.is_(True),
            WeatherForecast.issue_time_utc <= issue_time,
            WeatherForecast.valid_time_utc.in_(valid_times),
        )
        .order_by(
            WeatherForecast.forecast_location,
            WeatherForecast.variable_name,
            WeatherForecast.valid_time_utc,
            WeatherForecast.issue_time_utc.desc(),
            WeatherForecast.id.desc(),
        )
    )
    if locations is not None:
        query = query.where(WeatherForecast.forecast_location.in_(tuple(locations)))
    if variables is not None:
        query = query.where(WeatherForecast.variable_name.in_(tuple(variables)))

    latest_by_key: dict[tuple[str, str, datetime], WeatherForecast] = {}
    for row in session.scalars(query):
        key = (row.forecast_location, row.variable_name, row.valid_time_utc)
        latest_by_key.setdefault(key, row)

    return latest_by_key
