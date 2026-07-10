"""Tests for M05 production forecast output generation."""

import json
from collections.abc import Generator, Sequence
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path

import pytest
from pydantic import SecretStr
from sqlalchemy import select
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from gridops.config import Settings
from gridops.database import Base, make_engine, make_session_factory
from gridops.forecasting.artifacts import persist_model_artifact_metadata, save_artifact
from gridops.forecasting.forecast_outputs import (
    ForecastGenerationConfig,
    generate_forecast_from_selected_artifact,
)
from gridops.forecasting.model_contracts import (
    ForecastRunStatus,
    ModelArtifactStatus,
    ModelSelectionStatus,
    ModelTrainingStatus,
)
from gridops.models import (
    FeatureSnapshotRow,
    FeatureSnapshotRun,
    ForecastIssue,
    ForecastPeakOutput,
    ForecastRampOutput,
    ModelArtifact,
    ModelSelectionResult,
    ModelTrainingRun,
    ProductionForecastPrediction,
    ProductionForecastRun,
)

TEST_DATABASE_URL = "postgresql+psycopg://gridops:gridops@localhost:55432/gridops_test"
FEATURE_VERSION = "m04_c01_foundation"
ISSUE_TIME = datetime(2026, 1, 10, 15, tzinfo=UTC)
CREATED_AT = datetime(2026, 7, 10, 12, tzinfo=UTC)


class DeterministicForecastModel:
    """Tiny pickle-safe model for deterministic forecast-output tests."""

    def predict(self, x_values: Sequence[Sequence[float]]) -> list[float]:
        """Predict from the lag_1 feature plus a constant."""

        return [features[6] + 10.0 for features in x_values]


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
    """Create a clean schema for forecast output tests."""

    Base.metadata.drop_all(live_postgres_engine)
    Base.metadata.create_all(live_postgres_engine)

    try:
        yield make_session_factory(live_postgres_engine)
    finally:
        Base.metadata.drop_all(live_postgres_engine)


@pytest.mark.integration
def test_selected_artifact_generates_forecast_predictions(
    clean_session_factory: sessionmaker[Session],
    tmp_path: Path,
) -> None:
    """A selected artifact can generate persisted production forecast predictions."""

    with clean_session_factory() as session:
        artifact = _seed_artifact_and_selection(session, tmp_path, selected=True)
        snapshot_run = _seed_feature_snapshot(session, lag_values=(100, 130, 120))

        result = generate_forecast_from_selected_artifact(
            session,
            config=_config(artifact.id),
        )
        session.commit()

        predictions = list(session.scalars(select(ProductionForecastPrediction)).all())
        forecast_run = session.scalar(select(ProductionForecastRun))

    assert result.forecast_run.status == ForecastRunStatus.SUCCEEDED.value
    assert forecast_run is not None
    assert forecast_run.feature_snapshot_run_id == snapshot_run.id
    assert len(predictions) == 3
    assert [prediction.p50_demand_mw for prediction in predictions] == [
        Decimal("110.000"),
        Decimal("140.000"),
        Decimal("130.000"),
    ]


@pytest.mark.integration
def test_unselected_artifact_is_not_used(
    clean_session_factory: sessionmaker[Session],
    tmp_path: Path,
) -> None:
    """Rejected or unselected artifacts fail safely and produce no predictions."""

    with clean_session_factory() as session:
        artifact = _seed_artifact_and_selection(session, tmp_path, selected=False)
        _seed_feature_snapshot(session, lag_values=(100, 130, 120))

        result = generate_forecast_from_selected_artifact(
            session,
            config=_config(artifact.id),
        )
        session.commit()

        prediction_count = len(session.scalars(select(ProductionForecastPrediction)).all())

    assert result.forecast_run.status == ForecastRunStatus.BLOCKED.value
    assert result.forecast_run.safe_error_detail is not None
    assert "not selected" in result.forecast_run.safe_error_detail
    assert prediction_count == 0


@pytest.mark.integration
def test_p50_persists_and_p10_p90_remain_nullable(
    clean_session_factory: sessionmaker[Session],
    tmp_path: Path,
) -> None:
    """P50 is populated while P10/P90 remain null until true quantiles exist."""

    with clean_session_factory() as session:
        artifact = _seed_artifact_and_selection(session, tmp_path, selected=True)
        _seed_feature_snapshot(session, lag_values=(100, 130, 120))

        generate_forecast_from_selected_artifact(session, config=_config(artifact.id))
        session.commit()

        prediction = session.scalar(
            select(ProductionForecastPrediction).order_by(ProductionForecastPrediction.lead_hour)
        )

    assert prediction is not None
    assert prediction.p50_demand_mw == Decimal("110.000")
    assert prediction.point_forecast_demand_mw is None
    assert prediction.p10_demand_mw is None
    assert prediction.p90_demand_mw is None


@pytest.mark.integration
def test_peak_and_ramp_outputs_are_correct(
    clean_session_factory: sessionmaker[Session],
    tmp_path: Path,
) -> None:
    """Peak and ramp summaries are derived from persisted P50 predictions."""

    with clean_session_factory() as session:
        artifact = _seed_artifact_and_selection(session, tmp_path, selected=True)
        _seed_feature_snapshot(session, lag_values=(100, 130, 120))

        result = generate_forecast_from_selected_artifact(session, config=_config(artifact.id))
        session.commit()

        peak = session.scalar(select(ForecastPeakOutput))
        ramps = list(
            session.scalars(
                select(ForecastRampOutput).order_by(ForecastRampOutput.target_interval_start_utc)
            ).all()
        )

    assert result.peak_output is not None
    assert peak is not None
    assert peak.peak_demand_mw == Decimal("140.000")
    assert peak.peak_lead_hour == 2
    assert [ramp.forecast_ramp_mw for ramp in ramps] == [Decimal("30.000"), Decimal("-10.000")]
    assert [ramp.absolute_ramp_mw for ramp in ramps] == [Decimal("30.000"), Decimal("10.000")]


@pytest.mark.integration
def test_lineage_fields_persist(
    clean_session_factory: sessionmaker[Session],
    tmp_path: Path,
) -> None:
    """Forecast run and prediction lineage preserve artifact, training, issue, and snapshot ids."""

    with clean_session_factory() as session:
        artifact = _seed_artifact_and_selection(session, tmp_path, selected=True)
        snapshot_run = _seed_feature_snapshot(session, lag_values=(100, 130, 120))

        generate_forecast_from_selected_artifact(session, config=_config(artifact.id))
        session.commit()

        forecast_run = session.scalar(select(ProductionForecastRun))
        prediction = session.scalar(select(ProductionForecastPrediction))

    assert forecast_run is not None
    assert prediction is not None
    assert forecast_run.lineage_metadata is not None
    assert forecast_run.lineage_metadata["model_artifact_id"] == artifact.id
    assert forecast_run.lineage_metadata["model_training_run_id"] == artifact.model_training_run_id
    assert forecast_run.lineage_metadata["feature_snapshot_run_id"] == snapshot_run.id
    assert forecast_run.lineage_metadata["feature_version"] == FEATURE_VERSION
    assert forecast_run.lineage_metadata["forecast_issue_time_utc"] == ISSUE_TIME.isoformat()
    assert prediction.lineage_metadata is not None
    assert prediction.lineage_metadata["model_artifact_id"] == artifact.id


@pytest.mark.integration
def test_blocked_feature_snapshot_fails_safely(
    clean_session_factory: sessionmaker[Session],
    tmp_path: Path,
) -> None:
    """Blocked snapshots produce a blocked forecast run and no predictions."""

    with clean_session_factory() as session:
        artifact = _seed_artifact_and_selection(session, tmp_path, selected=True)
        _seed_blocked_feature_snapshot(session)

        result = generate_forecast_from_selected_artifact(
            session,
            config=_config(artifact.id),
        )
        session.commit()

        prediction_count = len(session.scalars(select(ProductionForecastPrediction)).all())

    assert result.forecast_run.status == ForecastRunStatus.BLOCKED.value
    assert result.forecast_run.safe_error_detail is not None
    assert "blocked" in result.forecast_run.safe_error_detail
    assert prediction_count == 0


@pytest.mark.integration
def test_required_feature_mismatch_fails_safely(
    clean_session_factory: sessionmaker[Session],
    tmp_path: Path,
) -> None:
    """Missing model inputs are reported without persisting partial predictions."""

    with clean_session_factory() as session:
        artifact = _seed_artifact_and_selection(session, tmp_path, selected=True)
        _seed_feature_snapshot(session, lag_values=(100, 130, 120), missing_required_feature=True)

        result = generate_forecast_from_selected_artifact(
            session,
            config=_config(artifact.id),
        )
        session.commit()

        prediction_count = len(session.scalars(select(ProductionForecastPrediction)).all())

    assert result.forecast_run.status == ForecastRunStatus.BLOCKED.value
    assert result.forecast_run.safe_error_detail is not None
    assert "missing required model inputs" in result.forecast_run.safe_error_detail
    assert prediction_count == 0


@pytest.mark.integration
def test_forecast_output_is_deterministic_for_fixed_artifact_and_features(
    clean_session_factory: sessionmaker[Session],
    tmp_path: Path,
) -> None:
    """A fixed model artifact and feature snapshot produce stable P50 values."""

    with clean_session_factory() as session:
        artifact = _seed_artifact_and_selection(session, tmp_path, selected=True)
        _seed_feature_snapshot(session, lag_values=(100, 130, 120))

        first = generate_forecast_from_selected_artifact(session, config=_config(artifact.id))
        first_values = [prediction.p50_demand_mw for prediction in first.predictions]
        _delete_forecast_outputs(session)
        second = generate_forecast_from_selected_artifact(session, config=_config(artifact.id))
        second_values = [prediction.p50_demand_mw for prediction in second.predictions]

    assert first_values == second_values


def _config(artifact_id: int) -> ForecastGenerationConfig:
    return ForecastGenerationConfig(
        model_artifact_id=artifact_id,
        forecast_issue_time_utc=ISSUE_TIME,
        horizon_hours=3,
        created_at_utc=CREATED_AT,
        build_missing_feature_snapshot=False,
    )


def _seed_artifact_and_selection(
    session: Session,
    artifact_dir: Path,
    *,
    selected: bool,
) -> ModelArtifact:
    training_run = ModelTrainingRun(
        model_name="deterministic_test_model",
        model_type="test_model",
        model_version="m05-c04",
        feature_version=FEATURE_VERSION,
        status=ModelTrainingStatus.SUCCEEDED.value,
        training_window_start_utc=datetime(2026, 1, 1, tzinfo=UTC),
        training_window_end_utc=datetime(2026, 1, 5, tzinfo=UTC),
        evaluation_window_start_utc=datetime(2026, 1, 5, tzinfo=UTC),
        evaluation_window_end_utc=datetime(2026, 1, 6, tzinfo=UTC),
        started_at_utc=CREATED_AT,
        completed_at_utc=CREATED_AT,
        created_at_utc=CREATED_AT,
    )
    session.add(training_run)
    session.flush()
    saved_artifact = save_artifact(
        DeterministicForecastModel(),
        model_name="deterministic_test_model",
        model_version="m05-c04",
        base_dir=artifact_dir,
    )
    artifact = persist_model_artifact_metadata(
        session,
        model_training_run_id=training_run.id,
        model_name="deterministic_test_model",
        model_type="test_model",
        model_version="m05-c04",
        feature_version=FEATURE_VERSION,
        artifact_uri=saved_artifact.artifact_uri,
        artifact_hash=saved_artifact.artifact_hash,
        status=ModelArtifactStatus.AVAILABLE,
        training_window_start_utc=datetime(2026, 1, 1, tzinfo=UTC),
        training_window_end_utc=datetime(2026, 1, 5, tzinfo=UTC),
        evaluation_window_start_utc=datetime(2026, 1, 5, tzinfo=UTC),
        evaluation_window_end_utc=datetime(2026, 1, 6, tzinfo=UTC),
        created_at_utc=CREATED_AT,
    )
    selection = ModelSelectionResult(
        model_training_run_id=training_run.id,
        model_artifact_id=artifact.id,
        model_name=artifact.model_name,
        model_type=artifact.model_type,
        model_version=artifact.model_version,
        feature_version=artifact.feature_version,
        selection_status=(
            ModelSelectionStatus.SELECTED.value if selected else ModelSelectionStatus.REJECTED.value
        ),
        selection_reason="test selection",
        training_window_start_utc=datetime(2026, 1, 1, tzinfo=UTC),
        training_window_end_utc=datetime(2026, 1, 5, tzinfo=UTC),
        evaluation_window_start_utc=datetime(2026, 1, 5, tzinfo=UTC),
        evaluation_window_end_utc=datetime(2026, 1, 6, tzinfo=UTC),
        candidate_metrics_json={"mae": 1.0},
        baseline_metrics_json={"same_hour_yesterday": {"mae": 2.0}},
        created_at_utc=CREATED_AT,
    )
    session.add(selection)
    session.flush()

    return artifact


def _seed_feature_snapshot(
    session: Session,
    *,
    lag_values: tuple[int, ...],
    missing_required_feature: bool = False,
) -> FeatureSnapshotRun:
    issue = _forecast_issue(session)
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
    for index, lag_value in enumerate(lag_values, start=1):
        target_start = ISSUE_TIME + timedelta(hours=index)
        payload = _payload(target_start, Decimal(lag_value))
        if missing_required_feature and index == 1:
            payload["demand"]["lag_1h_mw"] = None  # type: ignore[index]
        row = FeatureSnapshotRow(
            feature_snapshot_run_id=snapshot_run.id,
            forecast_issue_time_utc=ISSUE_TIME,
            target_interval_start_utc=target_start,
            target_interval_end_utc=target_start + timedelta(hours=1),
            lead_hour=index,
            feature_version=FEATURE_VERSION,
            quality_status="usable",
            lineage_metadata=json.dumps(payload, sort_keys=True),
        )
        session.add(row)
    session.flush()

    return snapshot_run


def _seed_blocked_feature_snapshot(session: Session) -> FeatureSnapshotRun:
    issue = _forecast_issue(session)
    snapshot_run = FeatureSnapshotRun(
        forecast_issue_id=issue.id,
        feature_version=FEATURE_VERSION,
        status="blocked",
        quality_status="blocked",
        started_at_utc=CREATED_AT,
        completed_at_utc=CREATED_AT,
        safe_error_detail="blocked by test",
    )
    session.add(snapshot_run)
    session.flush()

    return snapshot_run


def _forecast_issue(session: Session) -> ForecastIssue:
    issue = ForecastIssue(
        forecast_issue_time_utc=ISSUE_TIME,
        horizon_length_hours=3,
        forecast_type="day_ahead_hourly_ontario_demand",
        feature_version=FEATURE_VERSION,
        point_in_time_safety_rule="features_must_be_available_at_or_before_forecast_issue_time_utc",
        status="ready",
        quality_blocking_behavior="block_on_m03_error_or_critical",
        created_at_utc=CREATED_AT,
    )
    session.add(issue)
    session.flush()

    return issue


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


def _delete_forecast_outputs(session: Session) -> None:
    for ramp in session.scalars(select(ForecastRampOutput)).all():
        session.delete(ramp)
    for peak in session.scalars(select(ForecastPeakOutput)).all():
        session.delete(peak)
    for prediction in session.scalars(select(ProductionForecastPrediction)).all():
        session.delete(prediction)
    for run in session.scalars(select(ProductionForecastRun)).all():
        session.delete(run)
    session.flush()
