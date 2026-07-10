"""Alert evaluation and persistence engine."""

from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from gridops.decision.alert_lifecycle import record_initial_state
from gridops.decision.alert_rules import evaluate_alert_candidates
from gridops.decision.alert_schemas import (
    DEFAULT_POLICY_VERSION,
    AlertCandidate,
    AlertEvaluationStatus,
    AlertLifecycleState,
)
from gridops.decision.evidence import utc_timestamp
from gridops.models import Alert, AlertEvaluationRun, AlertEvidence

ACTIVE_STATES = (AlertLifecycleState.OPEN.value, AlertLifecycleState.ACKNOWLEDGED.value)


@dataclass(frozen=True, slots=True)
class AlertEvaluationResult:
    """Persisted result from one alert evaluation run."""

    evaluation_run: AlertEvaluationRun
    alerts: tuple[Alert, ...]
    created_count: int
    reused_count: int


def evaluate_and_persist_alerts(
    session: Session,
    *,
    production_forecast_run_id: int,
    generated_at_utc: datetime,
    policy_version: str = DEFAULT_POLICY_VERSION,
) -> AlertEvaluationResult:
    """Evaluate deterministic alert rules and persist alert/evidence records."""

    generated_at = utc_timestamp(generated_at_utc)
    evaluation_run = AlertEvaluationRun(
        production_forecast_run_id=production_forecast_run_id,
        policy_version=policy_version,
        status=AlertEvaluationStatus.RUNNING.value,
        started_at_utc=generated_at,
        metadata_json={"source": "gridops.decision.alert_engine"},
    )
    session.add(evaluation_run)
    session.flush()

    try:
        candidates = evaluate_alert_candidates(
            session,
            production_forecast_run_id=production_forecast_run_id,
            generated_at_utc=generated_at,
            policy_version=policy_version,
        )
        created = 0
        reused = 0
        alerts = []
        for candidate in candidates:
            alert = _active_alert_by_fingerprint(session, candidate.fingerprint)
            if alert is None:
                alert = _create_alert(session, candidate, generated_at)
                created += 1
            else:
                _refresh_existing_alert(alert, candidate, generated_at)
                reused += 1
            _persist_evidence(
                session,
                alert=alert,
                candidate=candidate,
                evaluation_run=evaluation_run,
                generated_at_utc=generated_at,
            )
            alerts.append(alert)

        evaluation_run.status = AlertEvaluationStatus.SUCCEEDED.value
        evaluation_run.completed_at_utc = generated_at
        session.flush()
        return AlertEvaluationResult(
            evaluation_run=evaluation_run,
            alerts=tuple(alerts),
            created_count=created,
            reused_count=reused,
        )
    except Exception as exc:
        evaluation_run.status = AlertEvaluationStatus.FAILED.value
        evaluation_run.completed_at_utc = generated_at
        evaluation_run.safe_error_detail = str(exc)[:1000]
        session.flush()
        raise


def _active_alert_by_fingerprint(session: Session, fingerprint: str) -> Alert | None:
    return session.scalar(
        select(Alert)
        .where(
            Alert.fingerprint == fingerprint,
            Alert.state.in_(ACTIVE_STATES),
        )
        .order_by(Alert.id.desc())
    )


def _create_alert(
    session: Session,
    candidate: AlertCandidate,
    generated_at_utc: datetime,
) -> Alert:
    alert = Alert(
        alert_type=candidate.alert_type.value,
        severity=candidate.severity.value,
        state=AlertLifecycleState.OPEN.value,
        fingerprint=candidate.fingerprint,
        rule_name=candidate.rule_name,
        rule_version=candidate.rule_version,
        title=candidate.title,
        explanation=candidate.explanation,
        production_forecast_run_id=candidate.production_forecast_run_id,
        forecast_issue_time_utc=candidate.forecast_issue_time_utc,
        target_interval_start_utc=candidate.target_interval_start_utc,
        target_interval_end_utc=candidate.target_interval_end_utc,
        opened_at_utc=generated_at_utc,
        updated_at_utc=generated_at_utc,
        current_evidence_json=candidate.evidence,
    )
    session.add(alert)
    session.flush()
    record_initial_state(
        session,
        alert=alert,
        changed_at_utc=generated_at_utc,
        reason="created_by_alert_evaluation",
    )
    return alert


def _refresh_existing_alert(
    alert: Alert,
    candidate: AlertCandidate,
    generated_at_utc: datetime,
) -> None:
    alert.severity = candidate.severity.value
    alert.title = candidate.title
    alert.explanation = candidate.explanation
    alert.current_evidence_json = candidate.evidence
    alert.updated_at_utc = generated_at_utc


def _persist_evidence(
    session: Session,
    *,
    alert: Alert,
    candidate: AlertCandidate,
    evaluation_run: AlertEvaluationRun,
    generated_at_utc: datetime,
) -> AlertEvidence:
    evidence = AlertEvidence(
        alert_id=alert.id,
        alert_evaluation_run_id=evaluation_run.id,
        evidence_json=candidate.evidence,
        generated_at_utc=generated_at_utc,
    )
    session.add(evidence)
    session.flush()
    return evidence
