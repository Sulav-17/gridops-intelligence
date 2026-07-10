"""Tests for M05 local model artifact persistence."""

from collections.abc import Generator
from datetime import UTC, datetime
from pathlib import Path

import pytest
from pydantic import SecretStr
from sqlalchemy import select
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from gridops.config import Settings
from gridops.database import Base, make_engine, make_session_factory
from gridops.forecasting.artifacts import (
    compute_artifact_hash,
    load_artifact,
    persist_model_artifact_metadata,
    save_artifact,
)
from gridops.forecasting.model_contracts import ModelArtifactStatus
from gridops.models import ModelArtifact

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
    """Create a clean schema for artifact metadata tests."""

    Base.metadata.drop_all(live_postgres_engine)
    Base.metadata.create_all(live_postgres_engine)

    try:
        yield make_session_factory(live_postgres_engine)
    finally:
        Base.metadata.drop_all(live_postgres_engine)


def test_artifact_save_creates_file_and_load_restores_data(tmp_path: Path) -> None:
    """Saving an artifact writes a local file that can be loaded back."""

    artifact_data = {"model": "schema-test", "coefficients": [1, 2, 3]}

    saved = save_artifact(
        artifact_data,
        model_name="candidate tree",
        model_version="m05-c02",
        base_dir=tmp_path,
    )
    loaded = load_artifact(saved.artifact_path)

    assert saved.artifact_path.exists()
    assert saved.byte_size > 0
    assert loaded == artifact_data


def test_artifact_hash_is_deterministic(tmp_path: Path) -> None:
    """The stored artifact hash is the SHA-256 hash of file bytes."""

    artifact_data = {"model": "schema-test", "coefficients": [1, 2, 3]}

    first = save_artifact(
        artifact_data,
        model_name="candidate_tree",
        model_version="m05-c02",
        base_dir=tmp_path / "first",
    )
    second = save_artifact(
        artifact_data,
        model_name="candidate_tree",
        model_version="m05-c02",
        base_dir=tmp_path / "second",
    )

    assert first.artifact_hash == second.artifact_hash
    assert first.artifact_hash == compute_artifact_hash(first.artifact_path)


@pytest.mark.integration
def test_artifact_metadata_can_persist_and_read(
    clean_session_factory: sessionmaker[Session],
    tmp_path: Path,
) -> None:
    """Artifact metadata persists to the M05 model_artifacts table."""

    created_at = datetime(2026, 7, 10, 12, tzinfo=UTC)
    saved = save_artifact(
        {"model": "metadata-test"},
        model_name="candidate_tree",
        model_version="m05-c02",
        base_dir=tmp_path,
    )

    with clean_session_factory() as session:
        artifact = persist_model_artifact_metadata(
            session,
            model_name="candidate_tree",
            model_type="sklearn_placeholder",
            model_version="m05-c02",
            feature_version="m04_c01_foundation",
            artifact_uri=saved.artifact_uri,
            artifact_hash=saved.artifact_hash,
            status=ModelArtifactStatus.AVAILABLE,
            training_window_start_utc=datetime(2026, 1, 1, tzinfo=UTC),
            training_window_end_utc=datetime(2026, 2, 1, tzinfo=UTC),
            evaluation_window_start_utc=datetime(2026, 2, 1, tzinfo=UTC),
            evaluation_window_end_utc=datetime(2026, 2, 8, tzinfo=UTC),
            parameters={"max_depth": 4},
            metrics_summary={"mae": 10.0},
            lineage_metadata={"feature_version": "m04_c01_foundation"},
            created_at_utc=created_at,
        )
        session.commit()

        persisted = session.scalar(select(ModelArtifact).where(ModelArtifact.id == artifact.id))

    assert persisted is not None
    assert persisted.artifact_uri == saved.artifact_uri
    assert persisted.artifact_hash == saved.artifact_hash
    assert persisted.status == ModelArtifactStatus.AVAILABLE.value
    assert persisted.metrics_summary_json == {"mae": 10.0}
