"""Simple fixture-mode ingestion runner for M02."""

import argparse
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

from sqlalchemy.orm import Session

from gridops.config import Settings
from gridops.database import make_engine, make_session_factory
from gridops.ingestion.loaders.ieso_demand import load_ieso_hourly_demand
from gridops.ingestion.loaders.weather_forecasts import load_weather_forecasts
from gridops.ingestion.loaders.weather_observations import load_weather_observations
from gridops.ingestion.parsers.ieso_demand import parse_ieso_hourly_demand
from gridops.ingestion.parsers.weather_forecasts import parse_weather_forecasts
from gridops.ingestion.parsers.weather_observations import parse_weather_observations
from gridops.ingestion.raw_store import RawSnapshotMetadata, RawSnapshotStore, persist_raw_snapshot
from gridops.ingestion.runs import (
    mark_ingestion_run_failed,
    mark_ingestion_run_succeeded,
    start_ingestion_run,
    utc_now,
)
from gridops.models import IngestionRun, RawSnapshot
from gridops.sources import SourceDefinition, get_source_definition


@dataclass(frozen=True, slots=True)
class FixtureRunResult:
    """Outcome of one fixture ingestion run."""

    ingestion_run_id: int
    status: str
    records_seen: int
    records_loaded: int


@dataclass(frozen=True, slots=True)
class SourceBinding:
    """Bind a CLI source name to its registry, parser, and loader behavior."""

    registry_name: str


SOURCE_BINDINGS: dict[str, SourceBinding] = {
    "ieso-demand": SourceBinding(registry_name="ieso-hourly-demand"),
    "weather-observations": SourceBinding(registry_name="weather-observations"),
    "weather-forecasts": SourceBinding(registry_name="weather-forecasts"),
}


def run_fixture_ingestion(
    *,
    source_name: str,
    fixture_path: Path,
    raw_root: Path,
    settings: Settings | None = None,
) -> FixtureRunResult:
    """Run one fixture ingestion command and persist run status."""

    source = _source_definition_for_cli_name(source_name)
    resolved_settings = settings if settings is not None else Settings()
    engine = make_engine(resolved_settings)
    session_factory = make_session_factory(engine)

    try:
        with session_factory() as session:
            ingestion_run = start_ingestion_run(session, source=source, mode="fixture")
            ingestion_run_id = ingestion_run.id
            session.commit()

        try:
            payload = fixture_path.read_bytes()
            metadata = RawSnapshotMetadata(
                retrieval_identifier=f"fixture://{fixture_path.as_posix()}",
                source_url=None,
                retrieved_at_utc=utc_now(),
            )

            with session_factory() as session:
                ingestion_run = session.get_one(IngestionRun, ingestion_run_id)
                snapshot = persist_raw_snapshot(
                    session,
                    store=RawSnapshotStore(raw_root),
                    source=source,
                    ingestion_run=ingestion_run,
                    payload=payload,
                    metadata=metadata,
                ).snapshot
                records_seen, records_loaded = _parse_and_load(
                    session=session,
                    cli_source_name=source_name,
                    source=source,
                    payload=payload,
                    ingestion_run=ingestion_run,
                    snapshot=snapshot,
                )
                mark_ingestion_run_succeeded(
                    ingestion_run,
                    records_seen=records_seen,
                    records_loaded=records_loaded,
                )
                session.commit()

            return FixtureRunResult(
                ingestion_run_id=ingestion_run_id,
                status="succeeded",
                records_seen=records_seen,
                records_loaded=records_loaded,
            )
        except Exception as exc:
            with session_factory() as session:
                ingestion_run = session.get_one(IngestionRun, ingestion_run_id)
                mark_ingestion_run_failed(ingestion_run, exc)
                session.commit()

            return FixtureRunResult(
                ingestion_run_id=ingestion_run_id,
                status="failed",
                records_seen=0,
                records_loaded=0,
            )
    finally:
        engine.dispose()


def main(argv: Sequence[str] | None = None) -> int:
    """Run fixture ingestion from the command line."""

    args = _parse_args(argv)
    result = run_fixture_ingestion(
        source_name=args.source,
        fixture_path=args.path,
        raw_root=args.raw_root,
    )
    print(
        " ".join(
            (
                f"ingestion_run_id={result.ingestion_run_id}",
                f"status={result.status}",
                f"records_seen={result.records_seen}",
                f"records_loaded={result.records_loaded}",
            )
        )
    )
    return 0 if result.status == "succeeded" else 1


def _parse_args(argv: Sequence[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run M02 fixture ingestion.")
    parser.add_argument(
        "--source",
        required=True,
        choices=sorted(SOURCE_BINDINGS),
        help="Fixture source to ingest.",
    )
    parser.add_argument(
        "--mode",
        required=True,
        choices=["fixture"],
        help="Only fixture mode is implemented in M02.",
    )
    parser.add_argument("--path", required=True, type=Path, help="Path to a local fixture file.")
    parser.add_argument(
        "--raw-root",
        type=Path,
        default=Path("data/raw"),
        help="Directory for immutable raw payload files.",
    )
    return parser.parse_args(argv)


def _source_definition_for_cli_name(source_name: str) -> SourceDefinition:
    try:
        binding = SOURCE_BINDINGS[source_name]
    except KeyError as exc:
        raise ValueError(f"unsupported source: {source_name}") from exc

    return get_source_definition(binding.registry_name)


def _parse_and_load(
    *,
    session: Session,
    cli_source_name: str,
    source: SourceDefinition,
    payload: bytes,
    ingestion_run: IngestionRun,
    snapshot: RawSnapshot,
) -> tuple[int, int]:
    if cli_source_name == "ieso-demand":
        ieso_records = parse_ieso_hourly_demand(payload)
        ieso_result = load_ieso_hourly_demand(
            session,
            records=ieso_records,
            ingestion_run=ingestion_run,
            raw_snapshot=snapshot,
        )
        return ieso_result.records_seen, ieso_result.records_inserted

    if cli_source_name == "weather-observations":
        observation_records = parse_weather_observations(payload, source_name=source.name)
        observation_result = load_weather_observations(
            session,
            records=observation_records,
            ingestion_run=ingestion_run,
            raw_snapshot=snapshot,
        )
        return observation_result.records_seen, observation_result.records_inserted

    if cli_source_name == "weather-forecasts":
        forecast_records = parse_weather_forecasts(payload, source_name=source.name)
        forecast_result = load_weather_forecasts(
            session,
            records=forecast_records,
            ingestion_run=ingestion_run,
            raw_snapshot=snapshot,
        )
        return forecast_result.records_seen, forecast_result.records_inserted

    raise ValueError(f"unsupported source: {cli_source_name}")


if __name__ == "__main__":
    raise SystemExit(main())
