"""Raw snapshot file storage and metadata persistence."""

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from gridops.ingestion.hashing import sha256_bytes
from gridops.models import IngestionRun, RawSnapshot
from gridops.sources import SourceDefinition
from gridops.time_utils import to_utc


@dataclass(frozen=True, slots=True)
class RawSnapshotMetadata:
    """Metadata needed to preserve source retrieval evidence."""

    retrieval_identifier: str | None
    source_url: str | None
    retrieved_at_utc: datetime
    published_at_utc: datetime | None = None


@dataclass(frozen=True, slots=True)
class RawSnapshotPersistenceResult:
    """Result of persisting raw snapshot bytes and metadata."""

    snapshot: RawSnapshot
    created: bool


class RawSnapshotStore:
    """Store immutable raw payload bytes below a local root directory."""

    def __init__(self, root: Path) -> None:
        self.root = root

    def write_payload(self, *, source_name: str, payload: bytes) -> str:
        """Write payload bytes by source and hash, returning a relative path."""

        content_hash = sha256_bytes(payload)
        safe_source_name = _safe_path_segment(source_name)
        relative_path = Path(safe_source_name) / f"{content_hash}.bin"
        absolute_path = self.root / relative_path

        absolute_path.parent.mkdir(parents=True, exist_ok=True)

        try:
            with absolute_path.open("xb") as file:
                file.write(payload)
        except FileExistsError:
            pass

        return relative_path.as_posix()


def persist_raw_snapshot(
    session: Session,
    *,
    store: RawSnapshotStore,
    source: SourceDefinition,
    ingestion_run: IngestionRun,
    payload: bytes,
    metadata: RawSnapshotMetadata,
) -> RawSnapshotPersistenceResult:
    """Persist raw payload metadata, deduping identical payloads per source."""

    content_hash = sha256_bytes(payload)
    existing = session.execute(
        select(RawSnapshot).where(
            RawSnapshot.source_name == source.name,
            RawSnapshot.content_hash_sha256 == content_hash,
        )
    ).scalar_one_or_none()

    if existing is not None:
        return RawSnapshotPersistenceResult(snapshot=existing, created=False)

    storage_path = store.write_payload(source_name=source.name, payload=payload)
    snapshot = RawSnapshot(
        source_name=source.name,
        source_type=source.source_type,
        retrieval_identifier=metadata.retrieval_identifier,
        source_url=metadata.source_url,
        retrieved_at_utc=to_utc(metadata.retrieved_at_utc),
        published_at_utc=(
            to_utc(metadata.published_at_utc) if metadata.published_at_utc is not None else None
        ),
        content_hash_sha256=content_hash,
        content_type=source.content_type,
        parser_version=source.parser_version,
        storage_path=storage_path,
        byte_size=len(payload),
        ingestion_run_id=ingestion_run.id,
    )
    session.add(snapshot)
    session.flush()

    return RawSnapshotPersistenceResult(snapshot=snapshot, created=True)


def _safe_path_segment(value: str) -> str:
    """Return a conservative path segment for source-owned raw files."""

    safe = "".join(
        character if character.isalnum() or character in "-_" else "_" for character in value
    )
    return safe or "source"
