"""Deterministic M06 briefing fact generation."""

from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from gridops.decision.evidence import normalize_evidence, utc_timestamp
from gridops.models import (
    Alert,
    BriefingFact,
    BriefingRun,
    ForecastPeakOutput,
    ForecastRampOutput,
    ProductionForecastPrediction,
    ProductionForecastRun,
    ScenarioRun,
)
from gridops.quality.source_health import summarize_source_health

BRIEFING_VERSION = "m06_c02_briefing_facts_v1"


@dataclass(frozen=True, slots=True)
class BriefingGenerationResult:
    """Persisted deterministic briefing facts."""

    briefing_run: BriefingRun
    facts: tuple[BriefingFact, ...]


def generate_briefing(
    session: Session,
    *,
    production_forecast_run_id: int,
    generated_at_utc: datetime,
) -> BriefingGenerationResult:
    """Generate and persist deterministic briefing facts for one forecast run."""

    generated_at = utc_timestamp(generated_at_utc)
    forecast_run = _require_forecast_run(session, production_forecast_run_id)
    facts = _fact_payloads(session, forecast_run)
    briefing_run = BriefingRun(
        production_forecast_run_id=forecast_run.id,
        status="succeeded",
        briefing_version=BRIEFING_VERSION,
        generated_at_utc=generated_at,
        summary_json={
            "fact_count": len(facts),
            "generated_from": "structured_persisted_records",
            "narrative_generated": False,
        },
    )
    session.add(briefing_run)
    session.flush()

    persisted = []
    for fact_type, value, evidence in facts:
        fact = BriefingFact(
            briefing_run_id=briefing_run.id,
            fact_type=fact_type,
            fact_value_json=_json_dict(value),
            evidence_json=_json_dict(evidence),
            created_at_utc=generated_at,
        )
        session.add(fact)
        persisted.append(fact)
    session.flush()
    return BriefingGenerationResult(briefing_run=briefing_run, facts=tuple(persisted))


def latest_briefing(session: Session) -> BriefingRun | None:
    """Return the latest successful briefing run."""

    return session.scalar(
        select(BriefingRun)
        .where(BriefingRun.status == "succeeded")
        .order_by(BriefingRun.generated_at_utc.desc(), BriefingRun.id.desc())
    )


def _fact_payloads(
    session: Session,
    forecast_run: ProductionForecastRun,
) -> list[tuple[str, dict[str, object], dict[str, object]]]:
    predictions = _predictions(session, forecast_run.id)
    facts: list[tuple[str, dict[str, object], dict[str, object]]] = []
    horizon_start = predictions[0].target_interval_start_utc if predictions else None
    horizon_end = predictions[-1].target_interval_end_utc if predictions else None
    facts.append(
        (
            "forecast_issue",
            {
                "forecast_issue_time_utc": forecast_run.forecast_issue_time_utc,
                "horizon_start_utc": horizon_start,
                "horizon_end_utc": horizon_end,
                "horizon_interval_count": len(predictions),
            },
            {
                "production_forecast_run_id": forecast_run.id,
                "source_table": "production_forecast_runs",
            },
        )
    )

    peak = session.scalar(
        select(ForecastPeakOutput).where(
            ForecastPeakOutput.production_forecast_run_id == forecast_run.id
        )
    )
    if peak is not None:
        facts.append(
            (
                "expected_peak",
                {
                    "peak_demand_mw": peak.peak_demand_mw,
                    "peak_target_interval_start_utc": peak.peak_target_interval_start_utc,
                    "peak_target_interval_end_utc": peak.peak_target_interval_end_utc,
                    "peak_lead_hour": peak.peak_lead_hour,
                },
                {
                    "forecast_peak_output_id": peak.id,
                    "source_table": "forecast_peak_outputs",
                },
            )
        )

    largest_ramp = session.scalar(
        select(ForecastRampOutput)
        .where(ForecastRampOutput.production_forecast_run_id == forecast_run.id)
        .order_by(ForecastRampOutput.absolute_ramp_mw.desc(), ForecastRampOutput.id)
    )
    if largest_ramp is not None:
        facts.append(
            (
                "largest_ramp",
                {
                    "target_interval_start_utc": largest_ramp.target_interval_start_utc,
                    "previous_target_interval_start_utc": largest_ramp.previous_target_interval_start_utc,
                    "forecast_ramp_mw": largest_ramp.forecast_ramp_mw,
                    "absolute_ramp_mw": largest_ramp.absolute_ramp_mw,
                },
                {
                    "forecast_ramp_output_id": largest_ramp.id,
                    "source_table": "forecast_ramp_outputs",
                },
            )
        )

    open_alerts = _open_alerts(session, forecast_run.id)
    facts.append(
        (
            "open_alert_summary",
            {
                "open_alert_count": len(open_alerts),
                "alerts": [
                    {
                        "alert_id": alert.id,
                        "alert_type": alert.alert_type,
                        "severity": alert.severity,
                        "target_interval_start_utc": alert.target_interval_start_utc,
                        "title": alert.title,
                    }
                    for alert in open_alerts
                ],
            },
            {
                "source_table": "alerts",
                "alert_ids": [alert.id for alert in open_alerts],
            },
        )
    )

    attention_hours = [
        {
            "target_interval_start_utc": alert.target_interval_start_utc,
            "alert_id": alert.id,
            "severity": alert.severity,
            "alert_type": alert.alert_type,
        }
        for alert in open_alerts
        if alert.target_interval_start_utc is not None
    ]
    facts.append(
        (
            "highest_attention_hours",
            {"attention_hours": attention_hours},
            {"source_table": "alerts", "alert_ids": [alert.id for alert in open_alerts]},
        )
    )

    source_health = summarize_source_health(session)
    facts.append(
        (
            "source_health_summary",
            {
                "datasets": [
                    {
                        "dataset_name": summary.dataset_name,
                        "latest_quality_run_status": summary.latest_quality_run_status,
                        "worst_severity": summary.worst_severity,
                        "is_blocked": summary.is_blocked,
                        "safe_failure_summaries": list(summary.safe_failure_summaries),
                    }
                    for summary in source_health
                ]
            },
            {"source_service": "gridops.quality.source_health.summarize_source_health"},
        )
    )

    quality_limitations = [
        {
            "dataset_name": summary.dataset_name,
            "worst_severity": summary.worst_severity,
            "is_blocked": summary.is_blocked,
            "safe_failure_summaries": list(summary.safe_failure_summaries),
        }
        for summary in source_health
        if summary.is_blocked or summary.worst_severity in {"warning", "error", "critical"}
    ]
    facts.append(
        (
            "quality_limitations",
            {"limitations": quality_limitations},
            {"source_service": "gridops.quality.source_health.summarize_source_health"},
        )
    )

    facts.append(
        (
            "model_confidence_limitations",
            {
                "true_prediction_intervals_available": False,
                "confidence_alerts_available": False,
                "reason": "M05 persists nullable P10/P90 fields but does not generate true intervals.",
            },
            {
                "source_contract": "docs/forecasting/FORECAST_OUTPUT_CONTRACT.md",
                "production_forecast_run_id": forecast_run.id,
            },
        )
    )

    scenarios = _recent_scenarios(session, forecast_run.id)
    facts.append(
        (
            "scenario_highlights",
            {
                "scenario_count": len(scenarios),
                "scenarios": [
                    {
                        "scenario_run_id": scenario.id,
                        "scenario_type": scenario.scenario_type,
                        "generated_at_utc": scenario.generated_at_utc,
                        "summary": scenario.summary_json,
                    }
                    for scenario in scenarios
                ],
            },
            {
                "source_table": "scenario_runs",
                "scenario_run_ids": [scenario.id for scenario in scenarios],
            },
        )
    )

    facts.append(
        (
            "known_limitations",
            {
                "claims_excluded": [
                    "official_grid_emergency_status",
                    "causal_explanation",
                    "trading_recommendation",
                    "replacement_for_ieso_forecast",
                ],
                "narrative_generated": False,
            },
            {"source_document": "KNOWN_LIMITATIONS.md"},
        )
    )

    return facts


def _predictions(
    session: Session,
    production_forecast_run_id: int,
) -> list[ProductionForecastPrediction]:
    return list(
        session.scalars(
            select(ProductionForecastPrediction)
            .where(
                ProductionForecastPrediction.production_forecast_run_id
                == production_forecast_run_id
            )
            .order_by(ProductionForecastPrediction.target_interval_start_utc)
        ).all()
    )


def _open_alerts(session: Session, production_forecast_run_id: int) -> list[Alert]:
    return list(
        session.scalars(
            select(Alert)
            .where(
                Alert.production_forecast_run_id == production_forecast_run_id,
                Alert.state.in_(("open", "acknowledged")),
            )
            .order_by(Alert.severity.desc(), Alert.target_interval_start_utc, Alert.id)
        ).all()
    )


def _recent_scenarios(session: Session, production_forecast_run_id: int) -> list[ScenarioRun]:
    return list(
        session.scalars(
            select(ScenarioRun)
            .where(
                ScenarioRun.production_forecast_run_id == production_forecast_run_id,
                ScenarioRun.status == "succeeded",
            )
            .order_by(ScenarioRun.generated_at_utc.desc(), ScenarioRun.id.desc())
            .limit(5)
        ).all()
    )


def _require_forecast_run(
    session: Session,
    production_forecast_run_id: int,
) -> ProductionForecastRun:
    forecast_run = session.get(ProductionForecastRun, production_forecast_run_id)
    if forecast_run is None:
        raise ValueError(f"production forecast run {production_forecast_run_id} does not exist")
    if forecast_run.status != "succeeded":
        raise ValueError(f"production forecast run is not succeeded: {forecast_run.status}")
    return forecast_run


def _json_dict(value: dict[str, object]) -> dict[str, object]:
    normalized = normalize_evidence(value)
    if not isinstance(normalized, dict):
        raise ValueError("normalized briefing payload must be a mapping")
    return normalized


def utc_now() -> datetime:
    """Return current aware UTC timestamp."""

    return datetime.now(UTC)
