"""Tests for M05 model-selection gates."""

from collections.abc import Generator
from datetime import UTC, datetime

import pytest
from pydantic import SecretStr
from sqlalchemy import select
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from gridops.config import Settings
from gridops.database import Base, make_engine, make_session_factory
from gridops.forecasting.model_contracts import ModelSelectionStatus
from gridops.forecasting.model_selection import (
    evaluate_model_selection_gate,
    persist_model_selection_result,
)
from gridops.models import ModelSelectionResult

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
def clean_session_factory(
    live_postgres_engine: Engine,
) -> Generator[sessionmaker[Session], None, None]:
    """Create a clean schema for model-selection persistence tests."""

    Base.metadata.drop_all(live_postgres_engine)
    Base.metadata.create_all(live_postgres_engine)

    try:
        yield make_session_factory(live_postgres_engine)
    finally:
        Base.metadata.drop_all(live_postgres_engine)


def test_gate_passes_when_candidate_beats_baseline() -> None:
    """A candidate is selected when required metrics and lineage pass."""

    decision = evaluate_model_selection_gate(
        candidate_metrics={"mae": 9.0, "wape": 0.08},
        baseline_metrics={"same_hour_yesterday": {"mae": 10.0, "wape": 0.1}},
        selected_baseline_name="same_hour_yesterday",
        lineage_metadata=_lineage(),
    )

    assert decision.selected is True
    assert decision.selection_status is ModelSelectionStatus.SELECTED


def test_gate_fails_when_candidate_misses_mae() -> None:
    """Candidate MAE must be no worse than the selected baseline MAE."""

    decision = evaluate_model_selection_gate(
        candidate_metrics={"mae": 11.0, "wape": 0.08},
        baseline_metrics={"same_hour_yesterday": {"mae": 10.0, "wape": 0.1}},
        selected_baseline_name="same_hour_yesterday",
        lineage_metadata=_lineage(),
    )

    assert decision.selected is False
    assert decision.selection_status is ModelSelectionStatus.REJECTED
    assert "MAE" in decision.reason


def test_gate_fails_when_wape_misses() -> None:
    """Candidate WAPE must be no worse when candidate and baseline WAPE exist."""

    decision = evaluate_model_selection_gate(
        candidate_metrics={"mae": 9.0, "wape": 0.12},
        baseline_metrics={"same_hour_yesterday": {"mae": 10.0, "wape": 0.1}},
        selected_baseline_name="same_hour_yesterday",
        lineage_metadata=_lineage(),
    )

    assert decision.selected is False
    assert "WAPE" in decision.reason


def test_gate_fails_when_lineage_is_incomplete() -> None:
    """Required lineage fields must be present before selection."""

    lineage = _lineage()
    lineage.pop("feature_version")

    decision = evaluate_model_selection_gate(
        candidate_metrics={"mae": 9.0, "wape": 0.08},
        baseline_metrics={"same_hour_yesterday": {"mae": 10.0, "wape": 0.1}},
        selected_baseline_name="same_hour_yesterday",
        lineage_metadata=lineage,
    )

    assert decision.selected is False
    assert "feature_version" in decision.reason


def test_gate_fails_when_slice_sanity_failure_is_present() -> None:
    """Slice sanity failures prevent selection even when aggregate metrics pass."""

    decision = evaluate_model_selection_gate(
        candidate_metrics={"mae": 9.0, "wape": 0.08, "slice_sanity_failures": ["lead_hour_24"]},
        baseline_metrics={"same_hour_yesterday": {"mae": 10.0, "wape": 0.1}},
        selected_baseline_name="same_hour_yesterday",
        lineage_metadata=_lineage(),
    )

    assert decision.selected is False
    assert "slice sanity" in decision.reason


@pytest.mark.integration
def test_selection_reason_is_persisted_and_failed_model_is_not_selected(
    clean_session_factory: sessionmaker[Session],
) -> None:
    """Rejected gate decisions persist as rejected, not selected."""

    decision = evaluate_model_selection_gate(
        candidate_metrics={"mae": 11.0, "wape": 0.08},
        baseline_metrics={"same_hour_yesterday": {"mae": 10.0, "wape": 0.1}},
        selected_baseline_name="same_hour_yesterday",
        lineage_metadata=_lineage(),
    )

    with clean_session_factory() as session:
        result = persist_model_selection_result(
            session,
            decision=decision,
            model_name="candidate_tree",
            model_type="sklearn_placeholder",
            model_version="m05-c02",
            feature_version="m04_c01_foundation",
            candidate_metrics={"mae": 11.0, "wape": 0.08},
            baseline_metrics={"same_hour_yesterday": {"mae": 10.0, "wape": 0.1}},
            training_window_start_utc=datetime(2026, 1, 1, tzinfo=UTC),
            training_window_end_utc=datetime(2026, 2, 1, tzinfo=UTC),
            evaluation_window_start_utc=datetime(2026, 2, 1, tzinfo=UTC),
            evaluation_window_end_utc=datetime(2026, 2, 8, tzinfo=UTC),
            lineage_metadata=_lineage(),
            created_at_utc=datetime(2026, 7, 10, 12, tzinfo=UTC),
        )
        session.commit()

        persisted = session.scalar(
            select(ModelSelectionResult).where(ModelSelectionResult.id == result.id)
        )

    assert persisted is not None
    assert persisted.selection_status == ModelSelectionStatus.REJECTED.value
    assert persisted.selection_status != ModelSelectionStatus.SELECTED.value
    assert "MAE" in persisted.selection_reason


def _lineage() -> dict[str, object]:
    return {
        "model_name": "candidate_tree",
        "model_version": "m05-c02",
        "feature_version": "m04_c01_foundation",
        "training_window_start_utc": "2026-01-01T00:00:00Z",
        "training_window_end_utc": "2026-02-01T00:00:00Z",
        "evaluation_window_start_utc": "2026-02-01T00:00:00Z",
        "evaluation_window_end_utc": "2026-02-08T00:00:00Z",
    }
