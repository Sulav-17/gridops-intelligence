"""Tests for M05 deterministic candidate training."""

import json
from collections.abc import Generator
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from pathlib import Path

import pytest
from pydantic import SecretStr
from sqlalchemy import select
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from gridops.config import Settings
from gridops.database import Base, make_engine, make_session_factory
from gridops.forecasting.candidate_models import (
    feature_vector_from_payload,
    payload_uses_no_target_actuals,
)
from gridops.forecasting.model_contracts import ModelSelectionStatus, ModelTrainingStatus
from gridops.forecasting.training import (
    CandidateTrainingConfig,
    load_candidate_rows,
    train_candidate_from_feature_snapshots,
)
from gridops.models import (
    BaselineForecastRun,
    BaselineMetricResult,
    FeatureSnapshotRow,
    FeatureSnapshotRun,
    ForecastIssue,
    IesoHourlyDemand,
    IngestionRun,
    ModelArtifact,
    ModelSelectionResult,
    ModelTrainingRun,
    RawSnapshot,
)

TEST_DATABASE_URL = "postgresql+psycopg://gridops:gridops@localhost:55432/gridops_test"
FEATURE_VERSION = "m04_c01_foundation"


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
    """Create a clean schema for candidate training tests."""

    Base.metadata.drop_all(live_postgres_engine)
    Base.metadata.create_all(live_postgres_engine)

    try:
        yield make_session_factory(live_postgres_engine)
    finally:
        Base.metadata.drop_all(live_postgres_engine)


def test_training_rejects_random_split_config() -> None:
    """Candidate training accepts only explicit time-window splits."""

    with pytest.raises(ValueError, match="time_window"):
        CandidateTrainingConfig(
            feature_version=FEATURE_VERSION,
            training_window_start_utc=datetime(2026, 1, 1, tzinfo=UTC),
            training_window_end_utc=datetime(2026, 1, 2, tzinfo=UTC),
            evaluation_window_start_utc=datetime(2026, 1, 2, tzinfo=UTC),
            evaluation_window_end_utc=datetime(2026, 1, 3, tzinfo=UTC),
            selected_baseline_name="same_hour_yesterday",
            split_strategy="random",
        )


def test_feature_extraction_excludes_target_actual_from_inputs() -> None:
    """Target actual fields are not part of candidate input features."""

    payload = _payload(datetime(2026, 1, 1, tzinfo=UTC), lag_1=Decimal("100.0"))
    payload["actual_demand_mw"] = "999.0"

    assert payload_uses_no_target_actuals(payload) is False

    clean_payload = _payload(datetime(2026, 1, 1, tzinfo=UTC), lag_1=Decimal("100.0"))
    vector = feature_vector_from_payload(clean_payload)

    assert vector is not None
    assert 999.0 not in vector


@pytest.mark.integration
def test_load_candidate_rows_uses_feature_snapshots_and_labels_only(
    clean_session_factory: sessionmaker[Session],
) -> None:
    """Training rows come from M04 feature snapshots joined to demand labels."""

    with clean_session_factory() as session:
        _seed_training_fixture(
            session, baseline_mae=Decimal("1000.0"), baseline_wape=Decimal("1.0")
        )
        rows = load_candidate_rows(
            session,
            feature_version=FEATURE_VERSION,
            window_start_utc=datetime(2026, 1, 1, tzinfo=UTC),
            window_end_utc=datetime(2026, 1, 4, tzinfo=UTC),
        )

    assert len(rows) == 3
    assert all(row.feature_snapshot_row_id is not None for row in rows)
    assert [row.target_interval_start_utc for row in rows] == sorted(
        row.target_interval_start_utc for row in rows
    )
    assert rows[0].actual_demand_mw == Decimal("210.000")


@pytest.mark.integration
def test_candidate_training_persists_run_artifact_metrics_and_selection(
    clean_session_factory: sessionmaker[Session],
    tmp_path: Path,
) -> None:
    """A deterministic candidate trains from snapshots and persists M05 outputs."""

    with clean_session_factory() as session:
        _seed_training_fixture(
            session, baseline_mae=Decimal("1000.0"), baseline_wape=Decimal("1.0")
        )
        result = train_candidate_from_feature_snapshots(
            session,
            config=_config(tmp_path, random_state=7),
        )
        session.commit()

        training_run = session.scalar(select(ModelTrainingRun))
        artifact = session.scalar(select(ModelArtifact))
        selection = session.scalar(select(ModelSelectionResult))

    assert result.training_run.status == ModelTrainingStatus.SUCCEEDED.value
    assert result.training_row_count == 3
    assert result.evaluation_row_count == 2
    assert training_run is not None
    assert training_run.metrics_summary_json is not None
    assert {"mae", "rmse", "wape", "bias"}.issubset(training_run.metrics_summary_json)
    assert artifact is not None
    assert Path(artifact.artifact_uri).exists()
    assert artifact.artifact_hash
    assert selection is not None
    assert selection.selection_status == ModelSelectionStatus.SELECTED.value


@pytest.mark.integration
def test_candidate_not_selected_when_gate_fails(
    clean_session_factory: sessionmaker[Session],
    tmp_path: Path,
) -> None:
    """Gate failure is persisted as rejected even after successful training."""

    with clean_session_factory() as session:
        _seed_training_fixture(
            session, baseline_mae=Decimal("0.000001"), baseline_wape=Decimal("0.000001")
        )
        result = train_candidate_from_feature_snapshots(
            session,
            config=_config(tmp_path, random_state=7),
        )
        session.commit()

        selection = session.scalar(select(ModelSelectionResult))

    assert result.training_run.status == ModelTrainingStatus.SUCCEEDED.value
    assert selection is not None
    assert selection.selection_status == ModelSelectionStatus.REJECTED.value
    assert selection.selection_status != ModelSelectionStatus.SELECTED.value


@pytest.mark.integration
def test_insufficient_data_fails_gracefully(
    clean_session_factory: sessionmaker[Session],
    tmp_path: Path,
) -> None:
    """Insufficient feature/label rows fail with a persisted reason."""

    with clean_session_factory() as session:
        _seed_training_fixture(
            session,
            baseline_mae=Decimal("1000.0"),
            baseline_wape=Decimal("1.0"),
            training_count=1,
            evaluation_count=1,
        )
        result = train_candidate_from_feature_snapshots(
            session,
            config=_config(tmp_path, random_state=7),
        )
        session.commit()

        training_run = session.scalar(select(ModelTrainingRun))
        artifact_count = len(session.scalars(select(ModelArtifact)).all())

    assert result.training_run.status == ModelTrainingStatus.FAILED.value
    assert training_run is not None
    assert training_run.safe_error_detail is not None
    assert "insufficient" in training_run.safe_error_detail
    assert artifact_count == 0


@pytest.mark.integration
def test_training_is_deterministic_with_fixed_random_state(
    clean_session_factory: sessionmaker[Session],
    tmp_path: Path,
) -> None:
    """The same fixed random_state produces stable candidate metrics."""

    with clean_session_factory() as session:
        _seed_training_fixture(
            session, baseline_mae=Decimal("1000.0"), baseline_wape=Decimal("1.0")
        )
        first = train_candidate_from_feature_snapshots(
            session,
            config=_config(tmp_path / "first", random_state=11, model_version="first"),
        )
        for selection in session.scalars(select(ModelSelectionResult)).all():
            session.delete(selection)
        session.flush()
        for artifact in session.scalars(select(ModelArtifact)).all():
            session.delete(artifact)
        session.flush()
        second = train_candidate_from_feature_snapshots(
            session,
            config=_config(tmp_path / "second", random_state=11, model_version="second"),
        )

    assert first.candidate_metrics == second.candidate_metrics


def _config(
    artifact_dir: Path,
    *,
    random_state: int,
    model_version: str = "m05-c03-test",
) -> CandidateTrainingConfig:
    return CandidateTrainingConfig(
        feature_version=FEATURE_VERSION,
        training_window_start_utc=datetime(2026, 1, 1, tzinfo=UTC),
        training_window_end_utc=datetime(2026, 1, 4, tzinfo=UTC),
        evaluation_window_start_utc=datetime(2026, 1, 4, tzinfo=UTC),
        evaluation_window_end_utc=datetime(2026, 1, 6, tzinfo=UTC),
        selected_baseline_name="same_hour_yesterday",
        random_state=random_state,
        artifact_dir=artifact_dir,
        model_version=model_version,
        created_at_utc=datetime(2026, 7, 10, 12, tzinfo=UTC),
    )


def _seed_training_fixture(
    session: Session,
    *,
    baseline_mae: Decimal,
    baseline_wape: Decimal,
    training_count: int = 3,
    evaluation_count: int = 2,
) -> None:
    ingestion_run = IngestionRun(
        source_name="ieso-hourly-demand",
        source_type="ieso",
        mode="fixture",
        parser_version="test",
        status="succeeded",
        started_at_utc=datetime(2026, 1, 1, tzinfo=UTC),
        finished_at_utc=datetime(2026, 1, 1, tzinfo=UTC),
        records_seen=training_count + evaluation_count,
        records_loaded=training_count + evaluation_count,
    )
    session.add(ingestion_run)
    session.flush()
    snapshot = RawSnapshot(
        source_name="ieso-hourly-demand",
        source_type="ieso",
        retrieval_identifier="fixture://training.csv",
        source_url=None,
        retrieved_at_utc=datetime(2026, 1, 1, tzinfo=UTC),
        published_at_utc=None,
        content_hash_sha256="a" * 64,
        content_type="text/csv",
        parser_version="test",
        storage_path="training.csv",
        byte_size=10,
        ingestion_run_id=ingestion_run.id,
    )
    session.add(snapshot)
    session.flush()

    issue = ForecastIssue(
        forecast_issue_time_utc=datetime(2026, 1, 1, tzinfo=UTC),
        horizon_length_hours=24,
        forecast_type="day_ahead_hourly_ontario_demand",
        feature_version=FEATURE_VERSION,
        point_in_time_safety_rule="features_must_be_available_at_or_before_forecast_issue_time_utc",
        status="ready",
        quality_blocking_behavior="block_on_m03_error_or_critical",
        created_at_utc=datetime(2026, 1, 1, tzinfo=UTC),
    )
    session.add(issue)
    session.flush()
    snapshot_run = FeatureSnapshotRun(
        forecast_issue_id=issue.id,
        feature_version=FEATURE_VERSION,
        status="succeeded",
        quality_status="usable",
        started_at_utc=datetime(2026, 1, 1, tzinfo=UTC),
        completed_at_utc=datetime(2026, 1, 1, tzinfo=UTC),
    )
    session.add(snapshot_run)
    session.flush()

    target_starts = [
        datetime(2026, 1, 1, tzinfo=UTC) + timedelta(days=index)
        for index in range(training_count + evaluation_count)
    ]
    for index, target_start in enumerate(target_starts, start=1):
        actual = Decimal("200.000") + Decimal(index * 10)
        demand = IesoHourlyDemand(
            source_service_date=date(2026, 1, min(index, 28)),
            source_hour_ending=1,
            interval_start_utc=target_start,
            interval_end_utc=target_start + timedelta(hours=1),
            demand_mw=actual,
            source_snapshot_id=snapshot.id,
            ingestion_run_id=ingestion_run.id,
            row_hash_sha256=str(index).zfill(64),
            is_current=True,
            superseded_at_utc=None,
        )
        feature_row = FeatureSnapshotRow(
            feature_snapshot_run_id=snapshot_run.id,
            forecast_issue_time_utc=target_start - timedelta(hours=1),
            target_interval_start_utc=target_start,
            target_interval_end_utc=target_start + timedelta(hours=1),
            lead_hour=1,
            feature_version=FEATURE_VERSION,
            quality_status="usable",
            lineage_metadata=json.dumps(
                _payload(target_start, lag_1=actual - Decimal("5.000")),
                sort_keys=True,
            ),
        )
        session.add_all([demand, feature_row])

    baseline_run = BaselineForecastRun(
        baseline_name="same_hour_yesterday",
        feature_version=FEATURE_VERSION,
        status="succeeded",
        training_window_start_utc=datetime(2026, 1, 1, tzinfo=UTC),
        training_window_end_utc=datetime(2026, 1, 4, tzinfo=UTC),
        evaluation_window_start_utc=datetime(2026, 1, 4, tzinfo=UTC),
        evaluation_window_end_utc=datetime(2026, 1, 6, tzinfo=UTC),
        started_at_utc=datetime(2026, 7, 10, tzinfo=UTC),
        completed_at_utc=datetime(2026, 7, 10, tzinfo=UTC),
    )
    session.add(baseline_run)
    session.flush()
    session.add_all(
        [
            BaselineMetricResult(
                baseline_forecast_run_id=baseline_run.id,
                metric_name="mae",
                metric_value=baseline_mae,
                metric_unit="MW",
                evaluation_window_start_utc=datetime(2026, 1, 4, tzinfo=UTC),
                evaluation_window_end_utc=datetime(2026, 1, 6, tzinfo=UTC),
                created_at_utc=datetime(2026, 7, 10, tzinfo=UTC),
            ),
            BaselineMetricResult(
                baseline_forecast_run_id=baseline_run.id,
                metric_name="wape",
                metric_value=baseline_wape,
                metric_unit=None,
                evaluation_window_start_utc=datetime(2026, 1, 4, tzinfo=UTC),
                evaluation_window_end_utc=datetime(2026, 1, 6, tzinfo=UTC),
                created_at_utc=datetime(2026, 7, 10, tzinfo=UTC),
            ),
        ]
    )
    session.flush()


def _payload(target_start: datetime, *, lag_1: Decimal) -> dict[str, object]:
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
            "lag_1h_mw": str(lag_1),
            "lag_2h_mw": "190.000",
            "lag_24h_mw": "180.000",
            "lag_48h_mw": "170.000",
            "lag_168h_mw": "160.000",
            "rolling_mean_mw": "200.000",
            "rolling_min_mw": "150.000",
            "rolling_max_mw": "250.000",
            "rolling_std_mw": "10.000",
            "recent_ramp_mw": "5.000",
        },
        "weather_observations": {},
        "weather_forecasts": [],
    }
