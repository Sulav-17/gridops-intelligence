"""Tests for M04 point-in-time feature snapshots."""

import json
from collections.abc import Generator
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from pathlib import Path

import pytest
from pydantic import SecretStr
from sqlalchemy import func, select
from sqlalchemy.engine import Engine

from gridops.config import Settings
from gridops.database import Base, make_engine, make_session_factory
from gridops.forecasting.feature_snapshots import (
    make_calendar_features,
    make_demand_features,
    persist_feature_snapshot,
)
from gridops.forecasting.issue_contract import ForecastIssueContract
from gridops.models import (
    FeatureSnapshotRow,
    IesoHourlyDemand,
    QualityRun,
)
from gridops.quality.contracts import (
    QualityCheckCategory,
    QualityResultStatus,
    QualitySeverity,
)
from gridops.quality.results import (
    mark_quality_run_succeeded,
    start_quality_run,
    store_quality_result,
)

TEST_DATABASE_URL = "postgresql+psycopg://gridops:gridops@localhost:55432/gridops_test"


@pytest.fixture
def live_postgres_engine() -> Generator[Engine, None, None]:
    """Create an engine for the Docker-backed test database."""

    settings = Settings(database_url=SecretStr(TEST_DATABASE_URL))
    engine = make_engine(settings)

    try:
        yield engine
    finally:
        engine.dispose()


@pytest.fixture
def clean_engine(live_postgres_engine: Engine) -> Generator[Engine, None, None]:
    """Create a clean schema for point-in-time feature tests."""

    Base.metadata.drop_all(live_postgres_engine)
    Base.metadata.create_all(live_postgres_engine)

    try:
        yield live_postgres_engine
    finally:
        Base.metadata.drop_all(live_postgres_engine)


def test_demand_lag_features_do_not_use_target_or_future_demand() -> None:
    """Demand lag features only use demand available by forecast issue time."""

    issue_time = datetime(2026, 7, 9, 15, tzinfo=UTC)
    target_start = datetime(2026, 7, 9, 16, tzinfo=UTC)
    history = [
        _demand_row(1, datetime(2026, 7, 9, 14, tzinfo=UTC), Decimal("140.0")),
        _demand_row(2, datetime(2026, 7, 9, 15, tzinfo=UTC), Decimal("999.0")),
        _demand_row(3, datetime(2026, 7, 9, 16, tzinfo=UTC), Decimal("1000.0")),
    ]

    features = make_demand_features(
        target_interval_start_utc=target_start,
        forecast_issue_time_utc=issue_time,
        demand_history=history,
    )

    assert features.lag_1h_mw is None
    assert features.lag_2h_mw == Decimal("140.0")
    assert Decimal("999.0") not in {
        features.lag_1h_mw,
        features.lag_2h_mw,
        features.lag_24h_mw,
    }


def test_rolling_features_do_not_use_future_values() -> None:
    """Rolling features are computed only from history known by issue time."""

    issue_time = datetime(2026, 7, 9, 15, tzinfo=UTC)
    target_start = datetime(2026, 7, 9, 16, tzinfo=UTC)
    history = [
        _demand_row(1, datetime(2026, 7, 9, 12, tzinfo=UTC), Decimal("100.0")),
        _demand_row(2, datetime(2026, 7, 9, 13, tzinfo=UTC), Decimal("110.0")),
        _demand_row(3, datetime(2026, 7, 9, 15, tzinfo=UTC), Decimal("999.0")),
    ]

    features = make_demand_features(
        target_interval_start_utc=target_start,
        forecast_issue_time_utc=issue_time,
        demand_history=history,
    )

    assert features.rolling_mean_mw == Decimal("105.0")
    assert features.rolling_min_mw == Decimal("100.0")
    assert features.rolling_max_mw == Decimal("110.0")
    assert features.recent_ramp_mw == Decimal("10.0")


def test_missing_lag_history_produces_nulls() -> None:
    """Unavailable lag history is represented as null, not invented values."""

    issue_time = datetime(2026, 7, 9, 15, tzinfo=UTC)
    target_start = datetime(2026, 7, 9, 16, tzinfo=UTC)

    features = make_demand_features(
        target_interval_start_utc=target_start,
        forecast_issue_time_utc=issue_time,
        demand_history=[],
    )

    assert features.lag_1h_mw is None
    assert features.lag_2h_mw is None
    assert features.rolling_mean_mw is None
    assert features.recent_ramp_mw is None


def test_calendar_features_are_deterministic() -> None:
    """Calendar features are stable UTC-derived values."""

    features = make_calendar_features(datetime(2026, 7, 11, 16, tzinfo=UTC))

    assert features.target_hour_utc == 16
    assert features.day_of_week == 5
    assert features.month == 7
    assert features.season == "summer"
    assert features.is_weekend is True
    assert features.hour_sin == pytest.approx(-0.866025403784)
    assert features.hour_cos == pytest.approx(-0.5)


@pytest.mark.integration
def test_feature_snapshot_rows_preserve_issue_target_lead_and_feature_version(
    clean_engine: Engine,
) -> None:
    """Persisted snapshot rows retain the C01 forecast issue contract fields."""

    session_factory = make_session_factory(clean_engine)
    issue_time = datetime(2026, 7, 9, 15, tzinfo=UTC)
    contract = ForecastIssueContract(forecast_issue_time_utc=issue_time, horizon_length_hours=2)

    with session_factory() as session:
        result = persist_feature_snapshot(
            session,
            contract=contract,
            generated_at_utc=datetime(2026, 7, 9, 15, 1, tzinfo=UTC),
        )
        session.commit()

        rows = list(
            session.scalars(select(FeatureSnapshotRow).order_by(FeatureSnapshotRow.lead_hour)).all()
        )

    assert result.snapshot_run.status == "succeeded"
    assert len(rows) == 2
    assert rows[0].forecast_issue_time_utc == issue_time
    assert rows[0].target_interval_start_utc == datetime(2026, 7, 9, 16, tzinfo=UTC)
    assert rows[0].target_interval_end_utc == datetime(2026, 7, 9, 17, tzinfo=UTC)
    assert rows[0].lead_hour == 1
    assert rows[0].feature_version == "m04_c01_foundation"
    assert rows[0].quality_status == "usable"
    assert rows[0].lineage_metadata is not None
    payload = json.loads(rows[0].lineage_metadata)
    assert payload["payload_version"] == "m04_c02_feature_payload_v1"
    assert payload["demand"]["lag_1h_mw"] is None


@pytest.mark.integration
def test_quality_blocked_data_marks_snapshot_unusable(clean_engine: Engine) -> None:
    """Blocked M03 quality state prevents trusted feature rows from being persisted."""

    session_factory = make_session_factory(clean_engine)
    issue_time = datetime(2026, 7, 9, 15, tzinfo=UTC)
    contract = ForecastIssueContract(forecast_issue_time_utc=issue_time, horizon_length_hours=2)

    with session_factory() as session:
        quality_run = start_quality_run(
            session,
            dataset_name="ieso_hourly_demand",
            started_at_utc=datetime(2026, 7, 9, 14, tzinfo=UTC),
        )
        store_quality_result(
            session,
            quality_run=quality_run,
            check_name="dataset_rows_present",
            check_category=QualityCheckCategory.COMPLETENESS,
            severity=QualitySeverity.CRITICAL,
            status=QualityResultStatus.FAILED,
            is_blocking=True,
            created_at_utc=datetime(2026, 7, 9, 14, 1, tzinfo=UTC),
        )
        mark_quality_run_succeeded(
            quality_run,
            completed_at_utc=datetime(2026, 7, 9, 14, 2, tzinfo=UTC),
        )

        result = persist_feature_snapshot(
            session,
            contract=contract,
            generated_at_utc=datetime(2026, 7, 9, 15, 1, tzinfo=UTC),
        )
        session.commit()

        persisted_row_count = session.scalar(select(func.count(FeatureSnapshotRow.id)))
        persisted_run = session.get(QualityRun, quality_run.id)

    assert result.snapshot_run.status == "blocked"
    assert result.snapshot_run.quality_status == "blocked"
    assert result.rows == ()
    assert persisted_row_count == 0
    assert persisted_run is not None


def test_no_production_forecasting_scope_added() -> None:
    """M04 feature work does not add M05 production forecasting scope."""

    project_root = Path(__file__).resolve().parents[1]
    pyproject = (project_root / "pyproject.toml").read_text(encoding="utf-8")

    assert "mlflow" not in pyproject.lower()
    assert "lightgbm" not in pyproject.lower()
    assert "xgboost" not in pyproject.lower()
    assert not (project_root / "src" / "gridops" / "forecasting" / "serving.py").exists()


def _demand_row(row_id: int, interval_start_utc: datetime, demand_mw: Decimal) -> IesoHourlyDemand:
    return IesoHourlyDemand(
        id=row_id,
        source_service_date=date(2026, 7, 9),
        source_hour_ending=row_id,
        interval_start_utc=interval_start_utc,
        interval_end_utc=interval_start_utc + timedelta(hours=1),
        demand_mw=demand_mw,
        source_snapshot_id=1,
        ingestion_run_id=1,
        row_hash_sha256=str(row_id).zfill(64),
        is_current=True,
        superseded_at_utc=None,
    )
