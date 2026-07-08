"""Loader for parsed IESO hourly demand records."""

from dataclasses import dataclass
from datetime import date, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from gridops.ingestion.parsers.ieso_demand import ParsedIesoDemandRecord
from gridops.ingestion.runs import utc_now
from gridops.models import IesoHourlyDemand, IngestionRun, RawSnapshot


@dataclass(frozen=True, slots=True)
class IesoDemandLoadResult:
    """Summarize a silver IESO demand load operation."""

    records_seen: int
    records_inserted: int
    records_unchanged: int
    records_superseded: int


def load_ieso_hourly_demand(
    session: Session,
    *,
    records: list[ParsedIesoDemandRecord],
    ingestion_run: IngestionRun,
    raw_snapshot: RawSnapshot,
    superseded_at_utc: datetime | None = None,
) -> IesoDemandLoadResult:
    """Load parsed IESO hourly demand records idempotently."""

    inserted = 0
    unchanged = 0
    superseded = 0
    revision_timestamp = superseded_at_utc if superseded_at_utc is not None else utc_now()

    for record in records:
        service_date = date.fromisoformat(record.source_service_date)
        current = _get_current_record(session, service_date, record.source_hour_ending)

        if current is not None and current.row_hash_sha256 == record.row_hash_sha256:
            unchanged += 1
            continue

        reusable_revision = _get_existing_revision(
            session,
            service_date,
            record.source_hour_ending,
            record.row_hash_sha256,
        )

        if current is not None:
            current.is_current = False
            current.superseded_at_utc = revision_timestamp
            superseded += 1

        if reusable_revision is not None:
            reusable_revision.is_current = True
            reusable_revision.superseded_at_utc = None
            reusable_revision.ingestion_run_id = ingestion_run.id
            reusable_revision.source_snapshot_id = raw_snapshot.id
            continue

        session.add(
            IesoHourlyDemand(
                source_service_date=service_date,
                source_hour_ending=record.source_hour_ending,
                interval_start_utc=record.interval_start_utc,
                interval_end_utc=record.interval_end_utc,
                demand_mw=record.demand_mw,
                source_snapshot_id=raw_snapshot.id,
                ingestion_run_id=ingestion_run.id,
                row_hash_sha256=record.row_hash_sha256,
                is_current=True,
                superseded_at_utc=None,
            )
        )
        inserted += 1

    session.flush()

    return IesoDemandLoadResult(
        records_seen=len(records),
        records_inserted=inserted,
        records_unchanged=unchanged,
        records_superseded=superseded,
    )


def _get_current_record(
    session: Session,
    service_date: date,
    hour_ending: int,
) -> IesoHourlyDemand | None:
    return session.execute(
        select(IesoHourlyDemand).where(
            IesoHourlyDemand.source_service_date == service_date,
            IesoHourlyDemand.source_hour_ending == hour_ending,
            IesoHourlyDemand.is_current.is_(True),
        )
    ).scalar_one_or_none()


def _get_existing_revision(
    session: Session,
    service_date: date,
    hour_ending: int,
    row_hash_sha256: str,
) -> IesoHourlyDemand | None:
    return session.execute(
        select(IesoHourlyDemand).where(
            IesoHourlyDemand.source_service_date == service_date,
            IesoHourlyDemand.source_hour_ending == hour_ending,
            IesoHourlyDemand.row_hash_sha256 == row_hash_sha256,
        )
    ).scalar_one_or_none()
