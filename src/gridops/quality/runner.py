"""Simple persisted quality runner for M03."""

import argparse
from collections import defaultdict
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import cast

from sqlalchemy import select
from sqlalchemy.orm import Session

from gridops.config import Settings
from gridops.database import make_engine, make_session_factory
from gridops.models import (
    IesoHourlyDemand,
    IngestionRun,
    QualityRun,
    RawSnapshot,
    WeatherForecast,
    WeatherObservation,
)
from gridops.quality.blocking import decide_run_blocking
from gridops.quality.checks import QualityCheckResult, failed_result, skipped_result
from gridops.quality.contracts import DATASET_CONTRACTS, QualityCheckCategory, QualitySeverity
from gridops.quality.ieso_demand import (
    IesoDemandQualityRecord,
    check_ieso_continuity,
    check_ieso_demand_range,
    check_ieso_dst_alignment,
    check_ieso_freshness,
    check_ieso_required_columns,
    check_ieso_required_values,
    check_ieso_source_hour_completeness,
    check_ieso_timestamps,
    check_ieso_unique_current_source_keys,
)
from gridops.quality.results import (
    mark_quality_run_failed,
    mark_quality_run_succeeded,
    start_quality_run,
    store_quality_result,
)
from gridops.quality.source_metadata import (
    IngestionRunQualityRecord,
    RawSnapshotQualityRecord,
    check_ingestion_run_metadata,
    check_raw_snapshot_metadata,
)
from gridops.quality.weather import (
    WeatherForecastQualityRecord,
    WeatherObservationQualityRecord,
    check_weather_forecast_freshness,
    check_weather_forecast_ranges,
    check_weather_forecast_required_columns,
    check_weather_forecast_required_values,
    check_weather_forecast_timestamps,
    check_weather_forecast_unique_current_source_keys,
    check_weather_forecast_valid_time_completeness,
    check_weather_observation_continuity,
    check_weather_observation_freshness,
    check_weather_observation_ranges,
    check_weather_observation_required_columns,
    check_weather_observation_required_values,
    check_weather_observation_timestamps,
    check_weather_observation_unique_current_source_keys,
)

SUPPORTED_DATASETS = tuple(sorted(DATASET_CONTRACTS))
_HOURLY_STEP = timedelta(hours=1)


@dataclass(frozen=True, slots=True)
class QualityRunnerResult:
    """Outcome of one persisted quality evaluation."""

    quality_run_id: int
    dataset_name: str
    status: str
    persisted_result_count: int
    is_blocked: bool
    blocking_result_count: int


def run_quality_checks(
    *,
    dataset_name: str,
    checked_window_start_utc: datetime | None = None,
    checked_window_end_utc: datetime | None = None,
    now_utc: datetime | None = None,
    settings: Settings | None = None,
) -> QualityRunnerResult:
    """Execute persisted quality checks for one supported dataset."""

    if dataset_name not in DATASET_CONTRACTS:
        raise ValueError(f"unsupported quality dataset: {dataset_name}")

    resolved_now = _coerce_aware_utc(now_utc, name="now_utc") if now_utc is not None else None
    resolved_settings = settings if settings is not None else Settings()
    engine = make_engine(resolved_settings)
    session_factory = make_session_factory(engine)

    try:
        with session_factory() as session:
            quality_run = start_quality_run(
                session,
                dataset_name=dataset_name,
                started_at_utc=resolved_now,
                checked_window_start_utc=checked_window_start_utc,
                checked_window_end_utc=checked_window_end_utc,
            )
            quality_run_id = quality_run.id
            session.commit()

        try:
            with session_factory() as session:
                quality_run = session.get_one(QualityRun, quality_run_id)
                results = _evaluate_dataset(
                    session=session,
                    dataset_name=dataset_name,
                    checked_window_start_utc=checked_window_start_utc,
                    checked_window_end_utc=checked_window_end_utc,
                    now_utc=resolved_now,
                )
                persisted_results = [
                    store_quality_result(
                        session,
                        quality_run=quality_run,
                        check_name=result.check_name,
                        check_category=result.check_category,
                        severity=result.severity,
                        status=result.status,
                        observed_value=result.observed_value,
                        expected_value=result.expected_value,
                        affected_record_count=result.affected_record_count,
                        safe_detail=result.safe_detail,
                        is_blocking=result.is_blocking,
                    )
                    for result in results
                ]
                mark_quality_run_succeeded(quality_run, completed_at_utc=resolved_now)
                decision = decide_run_blocking(quality_run, persisted_results)
                session.commit()

                return QualityRunnerResult(
                    quality_run_id=quality_run_id,
                    dataset_name=dataset_name,
                    status=quality_run.status,
                    persisted_result_count=len(persisted_results),
                    is_blocked=decision.is_blocked,
                    blocking_result_count=decision.blocking_result_count,
                )
        except Exception as exc:
            with session_factory() as session:
                quality_run = session.get_one(QualityRun, quality_run_id)
                mark_quality_run_failed(quality_run, exc, completed_at_utc=resolved_now)
                session.commit()

            return QualityRunnerResult(
                quality_run_id=quality_run_id,
                dataset_name=dataset_name,
                status="failed",
                persisted_result_count=0,
                is_blocked=True,
                blocking_result_count=1,
            )
    finally:
        engine.dispose()


def main(argv: Sequence[str] | None = None) -> int:
    """Run persisted quality checks from the command line."""

    args = _parse_args(argv)
    result = run_quality_checks(
        dataset_name=args.dataset,
        checked_window_start_utc=args.checked_window_start_utc,
        checked_window_end_utc=args.checked_window_end_utc,
        now_utc=args.now_utc,
    )
    print(
        " ".join(
            (
                f"quality_run_id={result.quality_run_id}",
                f"dataset={result.dataset_name}",
                f"status={result.status}",
                f"persisted_results={result.persisted_result_count}",
                f"is_blocked={str(result.is_blocked).lower()}",
                f"blocking_result_count={result.blocking_result_count}",
            )
        )
    )
    return 0 if result.status == "succeeded" and not result.is_blocked else 1


def _parse_args(argv: Sequence[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run M03 quality checks.")
    parser.add_argument(
        "--dataset",
        required=True,
        choices=SUPPORTED_DATASETS,
        help="Supported dataset to evaluate and persist.",
    )
    parser.add_argument(
        "--checked-window-start-utc",
        type=_parse_utc_datetime,
        help="Optional checked-window start in ISO 8601 UTC form.",
    )
    parser.add_argument(
        "--checked-window-end-utc",
        type=_parse_utc_datetime,
        help="Optional checked-window end in ISO 8601 UTC form.",
    )
    parser.add_argument(
        "--now-utc",
        type=_parse_utc_datetime,
        help="Optional fixed UTC clock for deterministic freshness checks and run timestamps.",
    )
    return parser.parse_args(argv)


def _evaluate_dataset(
    *,
    session: Session,
    dataset_name: str,
    checked_window_start_utc: datetime | None,
    checked_window_end_utc: datetime | None,
    now_utc: datetime | None,
) -> list[QualityCheckResult]:
    resolved_now = now_utc if now_utc is not None else datetime.now(UTC)

    if dataset_name == "ieso_hourly_demand":
        return _evaluate_ieso_hourly_demand(
            session=session,
            checked_window_start_utc=checked_window_start_utc,
            checked_window_end_utc=checked_window_end_utc,
            now_utc=resolved_now,
        )
    if dataset_name == "weather_observations":
        return _evaluate_weather_observations(
            session=session,
            checked_window_start_utc=checked_window_start_utc,
            checked_window_end_utc=checked_window_end_utc,
            now_utc=resolved_now,
        )
    if dataset_name == "weather_forecasts":
        return _evaluate_weather_forecasts(
            session=session,
            checked_window_start_utc=checked_window_start_utc,
            checked_window_end_utc=checked_window_end_utc,
            now_utc=resolved_now,
        )
    if dataset_name == "raw_snapshots":
        return _evaluate_raw_snapshots(
            session=session,
            checked_window_start_utc=checked_window_start_utc,
            checked_window_end_utc=checked_window_end_utc,
        )
    if dataset_name == "ingestion_runs":
        return _evaluate_ingestion_runs(
            session=session,
            checked_window_start_utc=checked_window_start_utc,
            checked_window_end_utc=checked_window_end_utc,
        )

    raise ValueError(f"unsupported quality dataset: {dataset_name}")


def _evaluate_ieso_hourly_demand(
    *,
    session: Session,
    checked_window_start_utc: datetime | None,
    checked_window_end_utc: datetime | None,
    now_utc: datetime,
) -> list[QualityCheckResult]:
    statement = select(IesoHourlyDemand).order_by(
        IesoHourlyDemand.interval_start_utc,
        IesoHourlyDemand.id,
    )
    if checked_window_start_utc is not None:
        statement = statement.where(IesoHourlyDemand.interval_end_utc > checked_window_start_utc)
    if checked_window_end_utc is not None:
        statement = statement.where(IesoHourlyDemand.interval_start_utc < checked_window_end_utc)

    records = list(session.scalars(statement).all())
    if not records:
        return [
            _no_rows_result("ieso_hourly_demand", checked_window_start_utc, checked_window_end_utc)
        ]

    quality_records = cast(list[IesoDemandQualityRecord], records)
    results = [
        check_ieso_required_columns(IesoHourlyDemand.__table__.columns.keys()),
        check_ieso_required_values(quality_records),
        check_ieso_unique_current_source_keys(quality_records),
        check_ieso_demand_range(quality_records),
        check_ieso_timestamps(quality_records),
        check_ieso_freshness(quality_records, now_utc=now_utc),
    ]

    window = _resolved_window(
        start=checked_window_start_utc,
        end=checked_window_end_utc,
        timestamps_start=(record.interval_start_utc for record in records if record.is_current),
        timestamps_end=(record.interval_end_utc for record in records if record.is_current),
    )
    if window is None:
        results.append(
            _unsupported_window_result(
                dataset_name="ieso_hourly_demand",
                check_name="ieso_windowed_checks",
                detail="unable to derive a checked UTC window from current demand rows",
            )
        )
        return results

    window_start_utc, window_end_utc = window
    results.extend(
        [
            check_ieso_continuity(
                quality_records,
                window_start_utc=window_start_utc,
                window_end_utc=window_end_utc,
            ),
            check_ieso_source_hour_completeness(
                quality_records,
                window_start_utc=window_start_utc,
                window_end_utc=window_end_utc,
            ),
            check_ieso_dst_alignment(
                quality_records,
                window_start_utc=window_start_utc,
                window_end_utc=window_end_utc,
            ),
        ]
    )
    return results


def _evaluate_weather_observations(
    *,
    session: Session,
    checked_window_start_utc: datetime | None,
    checked_window_end_utc: datetime | None,
    now_utc: datetime,
) -> list[QualityCheckResult]:
    statement = select(WeatherObservation).order_by(
        WeatherObservation.observed_at_utc,
        WeatherObservation.id,
    )
    if checked_window_start_utc is not None:
        statement = statement.where(WeatherObservation.observed_at_utc >= checked_window_start_utc)
    if checked_window_end_utc is not None:
        statement = statement.where(WeatherObservation.observed_at_utc < checked_window_end_utc)

    records = list(session.scalars(statement).all())
    if not records:
        return [
            _no_rows_result(
                "weather_observations", checked_window_start_utc, checked_window_end_utc
            )
        ]

    quality_records = cast(list[WeatherObservationQualityRecord], records)
    results = [
        check_weather_observation_required_columns(WeatherObservation.__table__.columns.keys()),
        check_weather_observation_required_values(quality_records),
        check_weather_observation_unique_current_source_keys(quality_records),
        check_weather_observation_ranges(quality_records),
        check_weather_observation_timestamps(quality_records),
        check_weather_observation_freshness(quality_records, now_utc=now_utc),
    ]

    records_by_station: dict[str, list[WeatherObservation]] = defaultdict(list)
    for record in records:
        if record.is_current and record.source_station_id is not None:
            records_by_station[record.source_station_id].append(record)

    if not records_by_station:
        results.append(
            _unsupported_window_result(
                dataset_name="weather_observations",
                check_name="weather_observation_continuity",
                detail="no current station-scoped weather observation rows available",
            )
        )
        return results

    for station_id, station_records in sorted(records_by_station.items()):
        window = _resolved_window(
            start=checked_window_start_utc,
            end=checked_window_end_utc,
            timestamps_start=(record.observed_at_utc for record in station_records),
            timestamps_end=(record.observed_at_utc + _HOURLY_STEP for record in station_records),
        )
        if window is None:
            results.append(
                _unsupported_window_result(
                    dataset_name="weather_observations",
                    check_name="weather_observation_continuity",
                    detail=f"unable to derive hourly continuity window for station {station_id}",
                )
            )
            continue
        results.append(
            check_weather_observation_continuity(
                cast(list[WeatherObservationQualityRecord], station_records),
                station_id=station_id,
                window_start_utc=window[0],
                window_end_utc=window[1],
            )
        )

    return results


def _evaluate_weather_forecasts(
    *,
    session: Session,
    checked_window_start_utc: datetime | None,
    checked_window_end_utc: datetime | None,
    now_utc: datetime,
) -> list[QualityCheckResult]:
    statement = select(WeatherForecast).order_by(
        WeatherForecast.issue_time_utc,
        WeatherForecast.valid_time_utc,
        WeatherForecast.id,
    )
    if checked_window_start_utc is not None:
        statement = statement.where(WeatherForecast.valid_time_utc >= checked_window_start_utc)
    if checked_window_end_utc is not None:
        statement = statement.where(WeatherForecast.valid_time_utc < checked_window_end_utc)

    records = list(session.scalars(statement).all())
    if not records:
        return [
            _no_rows_result("weather_forecasts", checked_window_start_utc, checked_window_end_utc)
        ]

    quality_records = cast(list[WeatherForecastQualityRecord], records)
    results = [
        check_weather_forecast_required_columns(WeatherForecast.__table__.columns.keys()),
        check_weather_forecast_required_values(quality_records),
        check_weather_forecast_unique_current_source_keys(quality_records),
        check_weather_forecast_ranges(quality_records),
        check_weather_forecast_timestamps(quality_records),
        check_weather_forecast_freshness(quality_records, now_utc=now_utc),
    ]

    grouped_records: dict[tuple[str, str, datetime], list[WeatherForecast]] = defaultdict(list)
    for record in records:
        if (
            record.is_current
            and record.forecast_location is not None
            and record.variable_name is not None
        ):
            grouped_records[
                (
                    record.forecast_location,
                    record.variable_name,
                    record.issue_time_utc,
                )
            ].append(record)

    if not grouped_records:
        results.append(
            _unsupported_window_result(
                dataset_name="weather_forecasts",
                check_name="weather_forecast_valid_time_completeness",
                detail="no current forecast groups available for completeness evaluation",
            )
        )
        return results

    for (forecast_location, variable_name, issue_time_utc), group_records in sorted(
        grouped_records.items(),
        key=lambda item: (item[0][0], item[0][1], item[0][2]),
    ):
        valid_times = sorted(record.valid_time_utc for record in group_records)
        expected_valid_times = _hourly_points(
            start=valid_times[0],
            end_exclusive=valid_times[-1] + _HOURLY_STEP,
        )
        results.append(
            check_weather_forecast_valid_time_completeness(
                cast(list[WeatherForecastQualityRecord], group_records),
                forecast_location=forecast_location,
                variable_name=variable_name,
                issue_time_utc=issue_time_utc,
                expected_valid_times_utc=expected_valid_times,
            )
        )

    return results


def _evaluate_raw_snapshots(
    *,
    session: Session,
    checked_window_start_utc: datetime | None,
    checked_window_end_utc: datetime | None,
) -> list[QualityCheckResult]:
    statement = select(RawSnapshot).order_by(RawSnapshot.retrieved_at_utc, RawSnapshot.id)
    if checked_window_start_utc is not None:
        statement = statement.where(RawSnapshot.retrieved_at_utc >= checked_window_start_utc)
    if checked_window_end_utc is not None:
        statement = statement.where(RawSnapshot.retrieved_at_utc < checked_window_end_utc)

    records = list(session.scalars(statement).all())
    if not records:
        return [_no_rows_result("raw_snapshots", checked_window_start_utc, checked_window_end_utc)]

    return [check_raw_snapshot_metadata(cast(list[RawSnapshotQualityRecord], records))]


def _evaluate_ingestion_runs(
    *,
    session: Session,
    checked_window_start_utc: datetime | None,
    checked_window_end_utc: datetime | None,
) -> list[QualityCheckResult]:
    statement = select(IngestionRun).order_by(IngestionRun.started_at_utc, IngestionRun.id)
    if checked_window_start_utc is not None:
        statement = statement.where(IngestionRun.started_at_utc >= checked_window_start_utc)
    if checked_window_end_utc is not None:
        statement = statement.where(IngestionRun.started_at_utc < checked_window_end_utc)

    records = list(session.scalars(statement).all())
    if not records:
        return [_no_rows_result("ingestion_runs", checked_window_start_utc, checked_window_end_utc)]

    return [check_ingestion_run_metadata(cast(list[IngestionRunQualityRecord], records))]


def _resolved_window(
    *,
    start: datetime | None,
    end: datetime | None,
    timestamps_start: Iterable[datetime],
    timestamps_end: Iterable[datetime],
) -> tuple[datetime, datetime] | None:
    if start is not None:
        start = _coerce_aware_utc(start, name="checked_window_start_utc")
    if end is not None:
        end = _coerce_aware_utc(end, name="checked_window_end_utc")

    starts = [_coerce_aware_utc(value, name="record window start") for value in timestamps_start]
    ends = [_coerce_aware_utc(value, name="record window end") for value in timestamps_end]

    resolved_start = start if start is not None else (min(starts) if starts else None)
    resolved_end = end if end is not None else (max(ends) if ends else None)
    if resolved_start is None or resolved_end is None or resolved_start >= resolved_end:
        return None
    return resolved_start, resolved_end


def _hourly_points(*, start: datetime, end_exclusive: datetime) -> list[datetime]:
    values: list[datetime] = []
    cursor = _coerce_aware_utc(start, name="start")
    resolved_end = _coerce_aware_utc(end_exclusive, name="end_exclusive")
    while cursor < resolved_end:
        values.append(cursor)
        cursor += _HOURLY_STEP
    return values


def _no_rows_result(
    dataset_name: str,
    checked_window_start_utc: datetime | None,
    checked_window_end_utc: datetime | None,
) -> QualityCheckResult:
    scope = _format_scope(checked_window_start_utc, checked_window_end_utc)
    return failed_result(
        dataset_name=dataset_name,
        check_name="dataset_rows_present",
        check_category=QualityCheckCategory.COMPLETENESS,
        severity=QualitySeverity.CRITICAL,
        observed_value=f"0 rows{scope}",
        expected_value="at least 1 row in checked scope",
        affected_record_count=0,
        safe_detail=f"no persisted rows available for {dataset_name}{scope}",
    )


def _unsupported_window_result(
    *,
    dataset_name: str,
    check_name: str,
    detail: str,
) -> QualityCheckResult:
    return skipped_result(
        dataset_name=dataset_name,
        check_name=check_name,
        check_category=QualityCheckCategory.COMPLETENESS,
        observed_value="checked window unavailable",
        expected_value="windowed completeness or continuity evaluation",
        safe_detail=detail,
    )


def _format_scope(
    checked_window_start_utc: datetime | None,
    checked_window_end_utc: datetime | None,
) -> str:
    if checked_window_start_utc is None and checked_window_end_utc is None:
        return ""

    start_text = (
        checked_window_start_utc.isoformat() if checked_window_start_utc is not None else "*"
    )
    end_text = checked_window_end_utc.isoformat() if checked_window_end_utc is not None else "*"
    return f" within [{start_text}, {end_text})"


def _parse_utc_datetime(value: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise argparse.ArgumentTypeError(f"invalid ISO 8601 datetime: {value}") from exc

    try:
        return _coerce_aware_utc(parsed, name="CLI datetime")
    except ValueError as exc:
        raise argparse.ArgumentTypeError(str(exc)) from exc


def _coerce_aware_utc(value: datetime, *, name: str) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{name} must be timezone-aware UTC")
    return value.astimezone(UTC)


if __name__ == "__main__":
    raise SystemExit(main())
