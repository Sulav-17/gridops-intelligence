"""Local model artifact persistence for M05."""

import hashlib
import os
import pickle
import re
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session

from gridops.forecasting.model_contracts import ModelArtifactStatus
from gridops.models import ModelArtifact

DEFAULT_ARTIFACT_DIR = Path("artifacts/models")
ARTIFACT_DIR_ENV_VAR = "GRIDOPS_ARTIFACT_DIR"
ARTIFACT_HASH_ALGORITHM = "sha256"


@dataclass(frozen=True, slots=True)
class SavedArtifact:
    """Result of writing a local model artifact."""

    artifact_path: Path
    artifact_uri: str
    artifact_hash: str
    byte_size: int


def resolve_artifact_dir(base_dir: Path | str | None = None) -> Path:
    """Return the configured local artifact directory."""

    if base_dir is not None:
        return Path(base_dir)

    configured_dir = os.environ.get(ARTIFACT_DIR_ENV_VAR)
    if configured_dir:
        return Path(configured_dir)

    return DEFAULT_ARTIFACT_DIR


def save_artifact(
    artifact: object,
    *,
    model_name: str,
    model_version: str,
    base_dir: Path | str | None = None,
) -> SavedArtifact:
    """Serialize an artifact locally and compute its content hash."""

    artifact_dir = resolve_artifact_dir(base_dir)
    artifact_dir.mkdir(parents=True, exist_ok=True)

    artifact_path = artifact_dir / _artifact_file_name(model_name, model_version)
    with artifact_path.open("wb") as artifact_file:
        pickle.dump(artifact, artifact_file, protocol=pickle.HIGHEST_PROTOCOL)

    artifact_hash = compute_artifact_hash(artifact_path)

    return SavedArtifact(
        artifact_path=artifact_path,
        artifact_uri=artifact_path.as_posix(),
        artifact_hash=artifact_hash,
        byte_size=artifact_path.stat().st_size,
    )


def load_artifact(artifact_uri: str | Path) -> Any:
    """Load a local artifact previously written by ``save_artifact``."""

    with Path(artifact_uri).open("rb") as artifact_file:
        return pickle.load(artifact_file)


def compute_artifact_hash(artifact_path: str | Path) -> str:
    """Return the SHA-256 hash for a local artifact file."""

    digest = hashlib.sha256()
    with Path(artifact_path).open("rb") as artifact_file:
        for chunk in iter(lambda: artifact_file.read(1024 * 1024), b""):
            digest.update(chunk)

    return digest.hexdigest()


def persist_model_artifact_metadata(
    session: Session,
    *,
    model_name: str,
    model_type: str,
    model_version: str,
    feature_version: str,
    artifact_uri: str,
    artifact_hash: str,
    training_window_start_utc: datetime,
    training_window_end_utc: datetime,
    evaluation_window_start_utc: datetime,
    evaluation_window_end_utc: datetime,
    model_training_run_id: int | None = None,
    status: ModelArtifactStatus = ModelArtifactStatus.AVAILABLE,
    parameters: dict[str, object] | None = None,
    metrics_summary: dict[str, object] | None = None,
    lineage_metadata: dict[str, object] | None = None,
    created_at_utc: datetime | None = None,
) -> ModelArtifact:
    """Persist metadata for a local model artifact."""

    created_at = _coerce_aware_utc(created_at_utc) if created_at_utc is not None else utc_now()
    artifact = ModelArtifact(
        model_training_run_id=model_training_run_id,
        model_name=model_name,
        model_type=model_type,
        model_version=model_version,
        feature_version=feature_version,
        artifact_uri=artifact_uri,
        artifact_hash=artifact_hash,
        status=status.value,
        training_window_start_utc=_coerce_aware_utc(training_window_start_utc),
        training_window_end_utc=_coerce_aware_utc(training_window_end_utc),
        evaluation_window_start_utc=_coerce_aware_utc(evaluation_window_start_utc),
        evaluation_window_end_utc=_coerce_aware_utc(evaluation_window_end_utc),
        parameters_json=parameters,
        metrics_summary_json=metrics_summary,
        lineage_metadata=lineage_metadata,
        created_at_utc=created_at,
    )
    session.add(artifact)
    session.flush()

    return artifact


def utc_now() -> datetime:
    """Return the current aware UTC timestamp."""

    return datetime.now(UTC)


def _artifact_file_name(model_name: str, model_version: str) -> str:
    safe_model_name = _safe_path_part(model_name)
    safe_model_version = _safe_path_part(model_version)

    return f"{safe_model_name}-{safe_model_version}.pkl"


def _safe_path_part(value: str) -> str:
    if not value:
        raise ValueError("artifact path parts must be non-empty")

    return re.sub(r"[^A-Za-z0-9_.-]+", "-", value).strip("-")


def _coerce_aware_utc(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("artifact timestamps must be timezone-aware")

    return value.astimezone(UTC)
