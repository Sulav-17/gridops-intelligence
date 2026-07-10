"""Alert lifecycle transition helpers."""

from datetime import datetime

from sqlalchemy.orm import Session

from gridops.decision.alert_schemas import AlertLifecycleState
from gridops.decision.evidence import utc_timestamp
from gridops.models import Alert, AlertLifecycleHistory

VALID_TRANSITIONS: dict[AlertLifecycleState, frozenset[AlertLifecycleState]] = {
    AlertLifecycleState.OPEN: frozenset(
        {
            AlertLifecycleState.ACKNOWLEDGED,
            AlertLifecycleState.RESOLVED,
            AlertLifecycleState.SUPPRESSED,
            AlertLifecycleState.EXPIRED,
        }
    ),
    AlertLifecycleState.ACKNOWLEDGED: frozenset(
        {
            AlertLifecycleState.RESOLVED,
            AlertLifecycleState.SUPPRESSED,
            AlertLifecycleState.EXPIRED,
        }
    ),
    AlertLifecycleState.RESOLVED: frozenset(),
    AlertLifecycleState.SUPPRESSED: frozenset(),
    AlertLifecycleState.EXPIRED: frozenset(),
}


def record_initial_state(
    session: Session,
    *,
    alert: Alert,
    changed_at_utc: datetime,
    reason: str,
) -> AlertLifecycleHistory:
    """Persist the immutable initial lifecycle row for an alert."""

    history = AlertLifecycleHistory(
        alert_id=alert.id,
        from_state=None,
        to_state=alert.state,
        transition_reason=reason,
        changed_at_utc=utc_timestamp(changed_at_utc),
    )
    session.add(history)
    session.flush()
    return history


def transition_alert_state(
    session: Session,
    *,
    alert: Alert,
    to_state: AlertLifecycleState,
    changed_at_utc: datetime,
    reason: str | None = None,
) -> AlertLifecycleHistory:
    """Move an alert to a valid lifecycle state and persist immutable history."""

    changed_at = utc_timestamp(changed_at_utc)
    current = AlertLifecycleState(alert.state)
    if to_state not in VALID_TRANSITIONS[current]:
        raise ValueError(f"invalid alert lifecycle transition: {current.value} -> {to_state.value}")

    alert.state = to_state.value
    alert.updated_at_utc = changed_at
    if to_state in {
        AlertLifecycleState.RESOLVED,
        AlertLifecycleState.SUPPRESSED,
        AlertLifecycleState.EXPIRED,
    }:
        alert.resolved_at_utc = changed_at

    history = AlertLifecycleHistory(
        alert_id=alert.id,
        from_state=current.value,
        to_state=to_state.value,
        transition_reason=reason,
        changed_at_utc=changed_at,
    )
    session.add(history)
    session.flush()
    return history
