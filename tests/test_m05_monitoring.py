"""Tests for M05 performance and drift monitoring foundations."""

import json
from collections.abc import Generator
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

import pytest
from pydantic import SecretStr
from sqlalchemy import select
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from gridops.config import Settings
from gridops.database import Base, make_engine, make_session_factory
from gridops.forecasting.monitoring import (
    NO_DATA_FEATURE_NAME,
    DriftMonitoringConfig,
    PerformanceMonitoringConfig,
    summarize_feature_drift,
    summarize_model_performance,
)
from gridops.models import (
    FeatureSnapshotRow,
    FeatureSnapshotRun,
    ForecastIssue,
    IesoHourlyDemand,
    IngestionRun,
    ModelArtifact,
    ModelDriftSummary,
    ModelPerformanceSummary,
    ProductionForecastPrediction,
    ProductionForecastRun,
    RawSnapshot,
)

TEST_DATABASE_URL = "postgresql+psycopg://gridops:gridops@localhost:55432/gridops_test"
FEATURE_VERSION = "m04_c01_foundation"
CREATED_AT = datetime(2026, 7, 10, 12, tzinfo=UTC)


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
def clean_session_factory(
    live_postgres_engine: Engine,
) -> Generator[sessionmaker[Session], None, None]:
    """Create a clean schema for monitoring tests."""

    Base.metadata.drop_all(live_postgres_engine)
    Base.metadata.create_all(live_postgres_engine)

    try:
        yield make_session_factory(live_postgres_engine)
    finally:
        Base.metadata.drop_all(live_postgres_engine)


@pytest.mark.integration
def test_performance_summary_calculation_and_persistence(
    clean_session_factory: sessionmaker[Session],
) -> None:
    """Forecast-vs-actual summaries persist MAE, RMSE, WAPE, and bias."""

    with clean_session_factory() as session:
        artifact = _seed_artifact(session)
        _seed_forecast_predictions_and_actuals(
            session,
            artifact,
            predictions=(Decimal("100.000"), Decimal("130.000")),
            actuals=(Decimal("110.000"), Decimal("120.000")),
        )

        summaries = summarize_model_performance(
            session,
            config=PerformanceMonitoringConfig(
                model_artifact_id=artifact.id,
                evaluation_window_start_utc=datetime(2026, 1, 2, tzinfo=UTC),
                evaluation_window_end_utc=datetime(2026, 1, 2, 2, tzinfo=UTC),
                created_at_utc=CREATED_AT,
            ),
        )
        session.commit()

        persisted = list(session.scalars(select(ModelPerformanceSummary)).all())

    assert {summary.metric_name for summary in summaries} == {"mae", "rmse", "wape", "bias"}
    assert {summary.metric_name for summary in persisted} == {"mae", "rmse", "wape", "bias"}
    mae = next(summary for summary in persisted if summary.metric_name == "mae")
    assert mae.metric_value == Decimal("10.000000")
    assert mae.row_count == 2
    assert mae.lineage_metadata is not None
    assert mae.lineage_metadata["actual_source"] == "ieso_hourly_demand"


@pytest.mark.integration
def test_drift_summary_calculation_and_persistence(
    clean_session_factory: sessionmaker[Session],
) -> None:
    """Feature drift summaries persist deterministic absolute mean differences."""

    with clean_session_factory() as session:
        artifact = _seed_artifact(session)
        _seed_feature_rows(session, start=datetime(2026, 1, 1, tzinfo=UTC), lags=(100, 100))
        _seed_feature_rows(session, start=datetime(2026, 1, 3, tzinfo=UTC), lags=(120, 120))

        summaries = summarize_feature_drift(
            session,
            config=DriftMonitoringConfig(
                model_artifact_id=artifact.id,
                baseline_window_start_utc=datetime(2026, 1, 1, tzinfo=UTC),
                baseline_window_end_utc=datetime(2026, 1, 1, 2, tzinfo=UTC),
                comparison_window_start_utc=datetime(2026, 1, 3, tzinfo=UTC),
                comparison_window_end_utc=datetime(2026, 1, 3, 2, tzinfo=UTC),
                created_at_utc=CREATED_AT,
            ),
        )
        session.commit()

        persisted = list(session.scalars(select(ModelDriftSummary)).all())

    assert len(summaries) == 16
    assert len(persisted) == 16
    lag_1 = next(summary for summary in persisted if summary.feature_name == "lag_1h_mw")
    assert lag_1.drift_metric_name == "absolute_mean_difference"
    assert lag_1.drift_score == Decimal("20.000000")
    assert lag_1.summary_json is not None
    assert lag_1.summary_json["status"] == "calculated"


@pytest.mark.integration
def test_drift_summary_persists_honest_no_data_row(
    clean_session_factory: sessionmaker[Session],
) -> None:
    """When windows have no feature vectors, drift persists an explicit no-data summary."""

    with clean_session_factory() as session:
        artifact = _seed_artifact(session)

        summaries = summarize_feature_drift(
            session,
            config=DriftMonitoringConfig(
                model_artifact_id=artifact.id,
                baseline_window_start_utc=datetime(2026, 1, 1, tzinfo=UTC),
                baseline_window_end_utc=datetime(2026, 1, 2, tzinfo=UTC),
                comparison_window_start_utc=datetime(2026, 1, 3, tzinfo=UTC),
                comparison_window_end_utc=datetime(2026, 1, 4, tzinfo=UTC),
                created_at_utc=CREATED_AT,
            ),
        )
        session.commit()

        persisted = session.scalar(select(ModelDriftSummary))

    assert len(summaries) == 1
    assert persisted is not None
    assert persisted.feature_name == NO_DATA_FEATURE_NAME
    assert persisted.drift_score is None
    assert persisted.summary_json is not None
    assert persisted.summary_json["status"] == "no_data"


def _seed_artifact(session: Session) -> ModelArtifact:
    artifact = ModelArtifact(
        model_name="monitoring_test_model",
        model_type="test_model",
        model_version="m05-c05",
        feature_version=FEATURE_VERSION,
        artifact_uri="artifacts/models/monitoring-test.pkl",
        artifact_hash="b" * 64,
        status="available",
        training_window_start_utc=datetime(2026, 1, 1, tzinfo=UTC),
        training_window_end_utc=datetime(2026, 1, 2, tzinfo=UTC),
        evaluation_window_start_utc=datetime(2026, 1, 2, tzinfo=UTC),
        evaluation_window_end_utc=datetime(2026, 1, 3, tzinfo=UTC),
        created_at_utc=CREATED_AT,
    )
    session.add(artifact)
    session.flush()

    return artifact


def _seed_forecast_predictions_and_actuals(
    session: Session,
    artifact: ModelArtifact,
    *,
    predictions: tuple[Decimal, ...],
    actuals: tuple[Decimal, ...],
) -> None:
    ingestion_run = IngestionRun(
        source_name="ieso-hourly-demand",
        source_type="ieso",
        mode="fixture",
        parser_version="test",
        status="succeeded",
        started_at_utc=CREATED_AT,
        finished_at_utc=CREATED_AT,
        records_seen=len(actuals),
        records_loaded=len(actuals),
    )
    session.add(ingestion_run)
    session.flush()
    snapshot = RawSnapshot(
        source_name="ieso-hourly-demand",
        source_type="ieso",
        retrieval_identifier="fixture://monitoring.csv",
        source_url=None,
        retrieved_at_utc=CREATED_AT,
        published_at_utc=None,
        content_hash_sha256="c" * 64,
        content_type="text/csv",
        parser_version="test",
        storage_path="monitoring.csv",
        byte_size=10,
        ingestion_run_id=ingestion_run.id,
    )
    session.add(snapshot)
    forecast_run = ProductionForecastRun(
        model_artifact_id=artifact.id,
        model_name=artifact.model_name,
        model_type=artifact.model_type,
        model_version=artifact.model_version,
        feature_version=artifact.feature_version,
        forecast_issue_time_utc=datetime(2026, 1, 1, 12, tzinfo=UTC),
        status="succeeded",
        started_at_utc=CREATED_AT,
        completed_at_utc=CREATED_AT,
        created_at_utc=CREATED_AT,
    )
    session.add(forecast_run)
    session.flush()

    for index, (prediction_value, actual_value) in enumerate(
        zip(predictions, actuals, strict=True),
        start=1,
    ):
        target_start = datetime(2026, 1, 2, tzinfo=UTC) + timedelta(hours=index - 1)
        demand = IesoHourlyDemand(
            source_service_date=date(2026, 1, 2),
            source_hour_ending=index,
            interval_start_utc=target_start,
            interval_end_utc=target_start + timedelta(hours=1),
            demand_mw=actual_value,
            source_snapshot_id=snapshot.id,
            ingestion_run_id=ingestion_run.id,
            row_hash_sha256=str(index).zfill(64),
            is_current=True,
        )
        prediction = ProductionForecastPrediction(
            production_forecast_run_id=forecast_run.id,
            forecast_issue_time_utc=forecast_run.forecast_issue_time_utc,
            target_interval_start_utc=target_start,
            target_interval_end_utc=target_start + timedelta(hours=1),
            lead_hour=index,
            p50_demand_mw=prediction_value,
            prediction_type="p50_only",
            created_at_utc=CREATED_AT,
        )
        session.add_all([demand, prediction])
    session.flush()


def _seed_feature_rows(
    session: Session,
    *,
    start: datetime,
    lags: tuple[int, ...],
) -> None:
    issue = ForecastIssue(
        forecast_issue_time_utc=start - timedelta(hours=1),
        horizon_length_hours=len(lags),
        forecast_type="day_ahead_hourly_ontario_demand",
        feature_version=FEATURE_VERSION,
        point_in_time_safety_rule="features_must_be_available_at_or_before_forecast_issue_time_utc",
        status="ready",
        quality_blocking_behavior="block_on_m03_error_or_critical",
        created_at_utc=CREATED_AT,
    )
    session.add(issue)
    session.flush()
    snapshot_run = FeatureSnapshotRun(
        forecast_issue_id=issue.id,
        feature_version=FEATURE_VERSION,
        status="succeeded",
        quality_status="usable",
        started_at_utc=CREATED_AT,
        completed_at_utc=CREATED_AT,
    )
    session.add(snapshot_run)
    session.flush()
    for index, lag in enumerate(lags, start=1):
        target_start = start + timedelta(hours=index - 1)
        row = FeatureSnapshotRow(
            feature_snapshot_run_id=snapshot_run.id,
            forecast_issue_time_utc=issue.forecast_issue_time_utc,
            target_interval_start_utc=target_start,
            target_interval_end_utc=target_start + timedelta(hours=1),
            lead_hour=index,
            feature_version=FEATURE_VERSION,
            quality_status="usable",
            lineage_metadata=json.dumps(_payload(target_start, Decimal(lag)), sort_keys=True),
        )
        session.add(row)
    session.flush()


def _payload(target_start: datetime, lag_1h_mw: Decimal) -> dict[str, object]:
    return {
        "payload_version": "m04_c02_feature_payload_v1",
        "calendar": {
            "target_hour_utc": target_start.hour,
            "day_of_week": target_start.weekday(),
            "month": target_start.month,
            "season": "winter",
            "is_weekend": target_start.weekday() >= 5,
            "hour_sin": 0.0,
            "hour_cos": 1.0,
        },
        "demand": {
            "lag_1h_mw": str(lag_1h_mw),
            "lag_2h_mw": "90.000",
            "lag_24h_mw": "80.000",
            "lag_48h_mw": "70.000",
            "lag_168h_mw": "60.000",
            "rolling_mean_mw": "100.000",
            "rolling_min_mw": "50.000",
            "rolling_max_mw": "150.000",
            "rolling_std_mw": "5.000",
            "recent_ramp_mw": "2.000",
        },
        "weather_observations": {},
        "weather_forecasts": [],
    }
