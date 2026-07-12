"""Deterministic M06 alert rule evaluation."""

from datetime import datetime
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from gridops.decision.alert_schemas import (
    DEFAULT_POLICY_VERSION,
    FORECAST_DEVIATION_CRITICAL_MW,
    FORECAST_DEVIATION_WARNING_MW,
    HIGH_DEMAND_CRITICAL_MW,
    HIGH_DEMAND_WARNING_MW,
    RAMP_CRITICAL_MW,
    RAMP_WARNING_MW,
    AlertCandidate,
    AlertSeverity,
    AlertType,
)
from gridops.decision.evidence import alert_fingerprint, normalize_evidence, utc_timestamp
from gridops.models import (
    ForecastRampOutput,
    ProductionForecastPrediction,
    ProductionForecastRun,
)
from gridops.quality.source_health import DatasetSourceHealthSummary, summarize_source_health

ACTIVE_COMPONENT_TYPES = {
    AlertType.HIGH_DEMAND,
    AlertType.RAMP,
    AlertType.FORECAST_DEVIATION,
    AlertType.SOURCE_HEALTH,
}
SEVERITY_RANK = {
    AlertSeverity.INFO: 0,
    AlertSeverity.WATCH: 1,
    AlertSeverity.WARNING: 2,
    AlertSeverity.CRITICAL: 3,
}


def evaluate_alert_candidates(
    session: Session,
    *,
    production_forecast_run_id: int,
    generated_at_utc: datetime,
    policy_version: str = DEFAULT_POLICY_VERSION,
) -> tuple[AlertCandidate, ...]:
    """Evaluate deterministic alert candidates for one production forecast run."""

    generated_at = utc_timestamp(generated_at_utc)
    forecast_run = _require_forecast_run(session, production_forecast_run_id)
    candidates: list[AlertCandidate] = []
    candidates.extend(
        high_demand_alert_candidates(
            session,
            forecast_run=forecast_run,
            generated_at_utc=generated_at,
            policy_version=policy_version,
        )
    )
    candidates.extend(
        ramp_alert_candidates(
            session,
            forecast_run=forecast_run,
            generated_at_utc=generated_at,
            policy_version=policy_version,
        )
    )
    candidates.extend(
        forecast_deviation_alert_candidates(
            session,
            forecast_run=forecast_run,
            generated_at_utc=generated_at,
            policy_version=policy_version,
        )
    )
    candidates.extend(
        source_health_alert_candidates(
            session,
            forecast_run=forecast_run,
            generated_at_utc=generated_at,
            policy_version=policy_version,
        )
    )
    candidates.extend(
        combined_context_alert_candidates(
            forecast_run=forecast_run,
            component_candidates=tuple(candidates),
            generated_at_utc=generated_at,
            policy_version=policy_version,
        )
    )
    return tuple(candidates)


def high_demand_alert_candidates(
    session: Session,
    *,
    forecast_run: ProductionForecastRun,
    generated_at_utc: datetime,
    policy_version: str = DEFAULT_POLICY_VERSION,
) -> tuple[AlertCandidate, ...]:
    """Detect forecasted demand above fixed deterministic thresholds."""

    predictions = _forecast_predictions(session, forecast_run.id)
    candidates = []
    for prediction in predictions:
        forecast_value = _forecast_value(prediction)
        if forecast_value is None or forecast_value < HIGH_DEMAND_WARNING_MW:
            continue
        severity = (
            AlertSeverity.CRITICAL
            if forecast_value >= HIGH_DEMAND_CRITICAL_MW
            else AlertSeverity.WARNING
        )
        threshold = (
            HIGH_DEMAND_CRITICAL_MW
            if severity is AlertSeverity.CRITICAL
            else HIGH_DEMAND_WARNING_MW
        )
        evidence: dict[str, object] = {
            "alert_rule_name": "high_demand_fixed_threshold",
            "alert_type": AlertType.HIGH_DEMAND.value,
            "alert_severity": severity.value,
            "policy_version": policy_version,
            "production_forecast_run_id": forecast_run.id,
            "forecast_issue_time_utc": forecast_run.forecast_issue_time_utc,
            "target_interval_start_utc": prediction.target_interval_start_utc,
            "target_interval_end_utc": prediction.target_interval_end_utc,
            "forecast_value_mw": forecast_value,
            "threshold_mw": threshold,
            "comparison_result": "forecast_value_mw >= threshold_mw",
            "prediction_id": prediction.id,
            "prediction_type": prediction.prediction_type,
            "p10_demand_mw": prediction.p10_demand_mw,
            "p50_demand_mw": prediction.p50_demand_mw,
            "p90_demand_mw": prediction.p90_demand_mw,
            "point_forecast_demand_mw": prediction.point_forecast_demand_mw,
            "generated_at_utc": generated_at_utc,
            "explanation": "Forecasted Ontario demand exceeds the documented fixed threshold.",
        }
        fingerprint = alert_fingerprint(
            {
                "rule_name": "high_demand_fixed_threshold",
                "policy_version": policy_version,
                "production_forecast_run_id": forecast_run.id,
                "target_interval_start_utc": prediction.target_interval_start_utc,
                "threshold_mw": threshold,
            }
        )
        candidates.append(
            _candidate(
                alert_type=AlertType.HIGH_DEMAND,
                severity=severity,
                rule_name="high_demand_fixed_threshold",
                rule_version=policy_version,
                title="High forecast demand",
                explanation="Forecasted demand exceeds the fixed M06 decision-support threshold.",
                evidence=evidence,
                fingerprint=fingerprint,
                forecast_run=forecast_run,
                target_interval_start_utc=prediction.target_interval_start_utc,
                target_interval_end_utc=prediction.target_interval_end_utc,
            )
        )
    return tuple(candidates)


def ramp_alert_candidates(
    session: Session,
    *,
    forecast_run: ProductionForecastRun,
    generated_at_utc: datetime,
    policy_version: str = DEFAULT_POLICY_VERSION,
) -> tuple[AlertCandidate, ...]:
    """Detect large adjacent forecast ramps using M05 ramp outputs where available."""

    ramp_rows = list(
        session.scalars(
            select(ForecastRampOutput)
            .where(ForecastRampOutput.production_forecast_run_id == forecast_run.id)
            .order_by(ForecastRampOutput.target_interval_start_utc)
        ).all()
    )
    ramp_inputs = (
        _ramp_inputs_from_outputs(session, ramp_rows)
        if ramp_rows
        else _calculated_ramps(session, forecast_run.id)
    )

    candidates = []
    for item in ramp_inputs:
        absolute_ramp = item["absolute_ramp_mw"]
        if not isinstance(absolute_ramp, Decimal) or absolute_ramp < RAMP_WARNING_MW:
            continue
        severity = (
            AlertSeverity.CRITICAL if absolute_ramp >= RAMP_CRITICAL_MW else AlertSeverity.WARNING
        )
        threshold = RAMP_CRITICAL_MW if severity is AlertSeverity.CRITICAL else RAMP_WARNING_MW
        ramp_value = item["forecast_ramp_mw"]
        if not isinstance(ramp_value, Decimal):
            continue
        direction = "up" if ramp_value > 0 else "down"
        evidence: dict[str, object] = {
            "alert_rule_name": "large_adjacent_forecast_ramp",
            "alert_type": AlertType.RAMP.value,
            "alert_severity": severity.value,
            "policy_version": policy_version,
            "production_forecast_run_id": forecast_run.id,
            "forecast_issue_time_utc": forecast_run.forecast_issue_time_utc,
            "prior_interval_start_utc": item["previous_target_interval_start_utc"],
            "target_interval_start_utc": item["target_interval_start_utc"],
            "target_interval_end_utc": item["target_interval_end_utc"],
            "ramp_value_mw": ramp_value,
            "absolute_ramp_mw": absolute_ramp,
            "threshold_mw": threshold,
            "direction": direction,
            "ramp_source": item["ramp_source"],
            "generated_at_utc": generated_at_utc,
            "explanation": "Adjacent forecast intervals have a large expected demand change.",
        }
        fingerprint = alert_fingerprint(
            {
                "rule_name": "large_adjacent_forecast_ramp",
                "policy_version": policy_version,
                "production_forecast_run_id": forecast_run.id,
                "target_interval_start_utc": item["target_interval_start_utc"],
                "threshold_mw": threshold,
            }
        )
        candidates.append(
            _candidate(
                alert_type=AlertType.RAMP,
                severity=severity,
                rule_name="large_adjacent_forecast_ramp",
                rule_version=policy_version,
                title="Large forecast ramp",
                explanation="Adjacent forecast intervals exceed the fixed M06 ramp threshold.",
                evidence=evidence,
                fingerprint=fingerprint,
                forecast_run=forecast_run,
                target_interval_start_utc=_datetime_value(item["target_interval_start_utc"]),
                target_interval_end_utc=_datetime_value(item["target_interval_end_utc"]),
            )
        )
    return tuple(candidates)


def forecast_deviation_alert_candidates(
    session: Session,
    *,
    forecast_run: ProductionForecastRun,
    generated_at_utc: datetime,
    policy_version: str = DEFAULT_POLICY_VERSION,
) -> tuple[AlertCandidate, ...]:
    """Detect deviation from the previous succeeded production forecast run."""

    candidates = []
    for prediction in _forecast_predictions(session, forecast_run.id):
        previous = _previous_prediction_for_target(session, forecast_run, prediction)
        current_value = _forecast_value(prediction)
        previous_value = _forecast_value(previous) if previous is not None else None
        if current_value is None or previous is None or previous_value is None:
            continue
        deviation = current_value - previous_value
        absolute_deviation = abs(deviation)
        if absolute_deviation < FORECAST_DEVIATION_WARNING_MW:
            continue
        severity = (
            AlertSeverity.CRITICAL
            if absolute_deviation >= FORECAST_DEVIATION_CRITICAL_MW
            else AlertSeverity.WARNING
        )
        threshold = (
            FORECAST_DEVIATION_CRITICAL_MW
            if severity is AlertSeverity.CRITICAL
            else FORECAST_DEVIATION_WARNING_MW
        )
        evidence: dict[str, object] = {
            "alert_rule_name": "previous_forecast_deviation",
            "alert_type": AlertType.FORECAST_DEVIATION.value,
            "alert_severity": severity.value,
            "policy_version": policy_version,
            "production_forecast_run_id": forecast_run.id,
            "forecast_issue_time_utc": forecast_run.forecast_issue_time_utc,
            "target_interval_start_utc": prediction.target_interval_start_utc,
            "target_interval_end_utc": prediction.target_interval_end_utc,
            "forecast_value_mw": current_value,
            "comparison_source": "previous_succeeded_production_forecast_run",
            "comparison_forecast_run_id": previous.production_forecast_run_id,
            "comparison_prediction_id": previous.id,
            "comparison_value_mw": previous_value,
            "deviation_mw": deviation,
            "absolute_deviation_mw": absolute_deviation,
            "threshold_mw": threshold,
            "generated_at_utc": generated_at_utc,
            "explanation": "Forecast changed materially from the previous succeeded run.",
        }
        fingerprint = alert_fingerprint(
            {
                "rule_name": "previous_forecast_deviation",
                "policy_version": policy_version,
                "production_forecast_run_id": forecast_run.id,
                "comparison_forecast_run_id": previous.production_forecast_run_id,
                "target_interval_start_utc": prediction.target_interval_start_utc,
                "threshold_mw": threshold,
            }
        )
        candidates.append(
            _candidate(
                alert_type=AlertType.FORECAST_DEVIATION,
                severity=severity,
                rule_name="previous_forecast_deviation",
                rule_version=policy_version,
                title="Forecast deviation from previous run",
                explanation="Forecast value differs from the previous succeeded forecast run.",
                evidence=evidence,
                fingerprint=fingerprint,
                forecast_run=forecast_run,
                target_interval_start_utc=prediction.target_interval_start_utc,
                target_interval_end_utc=prediction.target_interval_end_utc,
            )
        )
    return tuple(candidates)


def source_health_alert_candidates(
    session: Session,
    *,
    forecast_run: ProductionForecastRun,
    generated_at_utc: datetime,
    policy_version: str = DEFAULT_POLICY_VERSION,
) -> tuple[AlertCandidate, ...]:
    """Surface important M03 source-health context without replacing M03 checks."""

    candidates = []
    for summary in summarize_source_health(session):
        severity = _source_health_alert_severity(summary)
        if severity is None:
            continue
        evidence: dict[str, object] = {
            "alert_rule_name": "source_health_context",
            "alert_type": AlertType.SOURCE_HEALTH.value,
            "alert_severity": severity.value,
            "policy_version": policy_version,
            "production_forecast_run_id": forecast_run.id,
            "forecast_issue_time_utc": forecast_run.forecast_issue_time_utc,
            "dataset_name": summary.dataset_name,
            "latest_quality_run_status": summary.latest_quality_run_status,
            "worst_severity": summary.worst_severity,
            "is_blocked": summary.is_blocked,
            "check_counts_by_status": summary.check_counts_by_status,
            "latest_checked_at_utc": summary.latest_checked_at_utc,
            "safe_failure_summaries": summary.safe_failure_summaries,
            "source_health_status": "blocked" if summary.is_blocked else "attention",
            "generated_at_utc": generated_at_utc,
            "explanation": "M03 source-health context indicates attention is needed.",
        }
        fingerprint = alert_fingerprint(
            {
                "rule_name": "source_health_context",
                "policy_version": policy_version,
                "production_forecast_run_id": forecast_run.id,
                "dataset_name": summary.dataset_name,
                "latest_checked_at_utc": summary.latest_checked_at_utc,
                "worst_severity": summary.worst_severity,
                "is_blocked": summary.is_blocked,
            }
        )
        candidates.append(
            _candidate(
                alert_type=AlertType.SOURCE_HEALTH,
                severity=severity,
                rule_name="source_health_context",
                rule_version=policy_version,
                title=f"Source-health context for {summary.dataset_name}",
                explanation="Persisted M03 source-health state indicates decision-support context.",
                evidence=evidence,
                fingerprint=fingerprint,
                forecast_run=forecast_run,
                target_interval_start_utc=None,
                target_interval_end_utc=None,
            )
        )
    return tuple(candidates)


def combined_context_alert_candidates(
    *,
    forecast_run: ProductionForecastRun,
    component_candidates: tuple[AlertCandidate, ...],
    generated_at_utc: datetime,
    policy_version: str = DEFAULT_POLICY_VERSION,
) -> tuple[AlertCandidate, ...]:
    """Create combined-context alerts from deterministic component signals."""

    source_health = [
        candidate
        for candidate in component_candidates
        if candidate.alert_type is AlertType.SOURCE_HEALTH
    ]
    demand_or_ramp = [
        candidate
        for candidate in component_candidates
        if candidate.alert_type in {AlertType.HIGH_DEMAND, AlertType.RAMP}
    ]
    candidates = []
    for component in demand_or_ramp:
        if not source_health:
            continue
        linked_source = max(source_health, key=lambda item: SEVERITY_RANK[item.severity])
        severity = _max_severity(component.severity, linked_source.severity)
        evidence: dict[str, object] = {
            "alert_rule_name": "combined_forecast_and_source_health_context",
            "alert_type": AlertType.COMBINED_CONTEXT.value,
            "alert_severity": severity.value,
            "policy_version": policy_version,
            "production_forecast_run_id": forecast_run.id,
            "forecast_issue_time_utc": forecast_run.forecast_issue_time_utc,
            "target_interval_start_utc": component.target_interval_start_utc,
            "target_interval_end_utc": component.target_interval_end_utc,
            "component_alerts": [
                {
                    "alert_type": component.alert_type.value,
                    "severity": component.severity.value,
                    "fingerprint": component.fingerprint,
                    "rule_name": component.rule_name,
                },
                {
                    "alert_type": linked_source.alert_type.value,
                    "severity": linked_source.severity.value,
                    "fingerprint": linked_source.fingerprint,
                    "rule_name": linked_source.rule_name,
                },
            ],
            "generated_at_utc": generated_at_utc,
            "explanation": "Forecast attention signal is accompanied by source-health context.",
        }
        fingerprint = alert_fingerprint(
            {
                "rule_name": "combined_forecast_and_source_health_context",
                "policy_version": policy_version,
                "production_forecast_run_id": forecast_run.id,
                "component_fingerprints": [component.fingerprint, linked_source.fingerprint],
            }
        )
        candidates.append(
            _candidate(
                alert_type=AlertType.COMBINED_CONTEXT,
                severity=severity,
                rule_name="combined_forecast_and_source_health_context",
                rule_version=policy_version,
                title="Combined forecast and source-health context",
                explanation="A forecast attention signal occurs with M03 source-health context.",
                evidence=evidence,
                fingerprint=fingerprint,
                forecast_run=forecast_run,
                target_interval_start_utc=component.target_interval_start_utc,
                target_interval_end_utc=component.target_interval_end_utc,
            )
        )
    return tuple(candidates)


def _candidate(
    *,
    alert_type: AlertType,
    severity: AlertSeverity,
    rule_name: str,
    rule_version: str,
    title: str,
    explanation: str,
    evidence: dict[str, object],
    fingerprint: str,
    forecast_run: ProductionForecastRun,
    target_interval_start_utc: datetime | None,
    target_interval_end_utc: datetime | None,
) -> AlertCandidate:
    normalized_evidence = normalize_evidence(evidence)
    if not isinstance(normalized_evidence, dict):
        raise ValueError("normalized alert evidence must be a mapping")

    return AlertCandidate(
        alert_type=alert_type,
        severity=severity,
        rule_name=rule_name,
        rule_version=rule_version,
        title=title,
        explanation=explanation,
        evidence=normalized_evidence,
        fingerprint=fingerprint,
        production_forecast_run_id=forecast_run.id,
        forecast_issue_time_utc=forecast_run.forecast_issue_time_utc,
        target_interval_start_utc=target_interval_start_utc,
        target_interval_end_utc=target_interval_end_utc,
    )


def _source_health_alert_severity(
    summary: DatasetSourceHealthSummary,
) -> AlertSeverity | None:
    if summary.latest_quality_run_status == "not_started":
        return None
    if summary.is_blocked or summary.latest_quality_run_status == "failed":
        return AlertSeverity.CRITICAL
    if summary.worst_severity == "critical":
        return AlertSeverity.CRITICAL
    if summary.worst_severity == "error":
        return AlertSeverity.WARNING
    if summary.worst_severity == "warning":
        return AlertSeverity.WATCH
    return None


def _max_severity(left: AlertSeverity, right: AlertSeverity) -> AlertSeverity:
    return left if SEVERITY_RANK[left] >= SEVERITY_RANK[right] else right


def _ramp_inputs_from_outputs(
    session: Session,
    ramp_rows: list[ForecastRampOutput],
) -> list[dict[str, object]]:
    predictions_by_start = {
        row.target_interval_start_utc: row
        for row in session.scalars(
            select(ProductionForecastPrediction).where(
                ProductionForecastPrediction.production_forecast_run_id
                == ramp_rows[0].production_forecast_run_id
            )
        ).all()
    }
    values: list[dict[str, object]] = []
    for ramp in ramp_rows:
        prediction = predictions_by_start.get(ramp.target_interval_start_utc)
        values.append(
            {
                "target_interval_start_utc": ramp.target_interval_start_utc,
                "target_interval_end_utc": (
                    prediction.target_interval_end_utc if prediction is not None else None
                ),
                "previous_target_interval_start_utc": ramp.previous_target_interval_start_utc,
                "forecast_ramp_mw": ramp.forecast_ramp_mw,
                "absolute_ramp_mw": ramp.absolute_ramp_mw,
                "ramp_source": "forecast_ramp_outputs",
            }
        )
    return values


def _calculated_ramps(
    session: Session,
    production_forecast_run_id: int,
) -> list[dict[str, object]]:
    predictions = _forecast_predictions(session, production_forecast_run_id)
    values: list[dict[str, object]] = []
    for previous, current in zip(predictions, predictions[1:], strict=False):
        previous_value = _forecast_value(previous)
        current_value = _forecast_value(current)
        if previous_value is None or current_value is None:
            continue
        ramp = current_value - previous_value
        values.append(
            {
                "target_interval_start_utc": current.target_interval_start_utc,
                "target_interval_end_utc": current.target_interval_end_utc,
                "previous_target_interval_start_utc": previous.target_interval_start_utc,
                "forecast_ramp_mw": ramp,
                "absolute_ramp_mw": abs(ramp),
                "ramp_source": "calculated_from_adjacent_predictions",
            }
        )
    return values


def _previous_prediction_for_target(
    session: Session,
    forecast_run: ProductionForecastRun,
    prediction: ProductionForecastPrediction,
) -> ProductionForecastPrediction | None:
    return session.scalar(
        select(ProductionForecastPrediction)
        .join(
            ProductionForecastRun,
            ProductionForecastPrediction.production_forecast_run_id == ProductionForecastRun.id,
        )
        .where(
            ProductionForecastRun.status == "succeeded",
            ProductionForecastRun.id != forecast_run.id,
            ProductionForecastRun.forecast_issue_time_utc < forecast_run.forecast_issue_time_utc,
            ProductionForecastPrediction.target_interval_start_utc
            == prediction.target_interval_start_utc,
        )
        .order_by(
            ProductionForecastRun.forecast_issue_time_utc.desc(),
            ProductionForecastRun.id.desc(),
        )
    )


def _forecast_predictions(
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


def _forecast_value(prediction: ProductionForecastPrediction | None) -> Decimal | None:
    if prediction is None:
        return None
    return prediction.p50_demand_mw or prediction.point_forecast_demand_mw


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


def _datetime_value(value: object) -> datetime | None:
    return value if isinstance(value, datetime) else None
