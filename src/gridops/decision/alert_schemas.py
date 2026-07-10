"""Typed M06 alert contracts."""

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from enum import StrEnum


class AlertType(StrEnum):
    """Supported deterministic alert categories."""

    HIGH_DEMAND = "high_demand"
    RAMP = "ramp"
    FORECAST_DEVIATION = "forecast_deviation"
    SOURCE_HEALTH = "source_health"
    COMBINED_CONTEXT = "combined_context"


class AlertSeverity(StrEnum):
    """Decision-support severity levels."""

    INFO = "info"
    WATCH = "watch"
    WARNING = "warning"
    CRITICAL = "critical"


class AlertLifecycleState(StrEnum):
    """Lifecycle states for persisted alerts."""

    OPEN = "open"
    ACKNOWLEDGED = "acknowledged"
    RESOLVED = "resolved"
    SUPPRESSED = "suppressed"
    EXPIRED = "expired"


class AlertEvaluationStatus(StrEnum):
    """Lifecycle status for one evaluation run."""

    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"


@dataclass(frozen=True, slots=True)
class AlertRulePolicy:
    """Static threshold policy for one alert rule."""

    rule_name: str
    alert_type: AlertType
    severity: AlertSeverity
    threshold_mw: Decimal | None
    rule_version: str


@dataclass(frozen=True, slots=True)
class AlertCandidate:
    """A deterministic alert candidate emitted by rule evaluation."""

    alert_type: AlertType
    severity: AlertSeverity
    rule_name: str
    rule_version: str
    title: str
    explanation: str
    evidence: dict[str, object]
    fingerprint: str
    production_forecast_run_id: int | None
    forecast_issue_time_utc: datetime | None
    target_interval_start_utc: datetime | None
    target_interval_end_utc: datetime | None


DEFAULT_POLICY_VERSION = "m06_c01_alert_policy_v1"

HIGH_DEMAND_WARNING_MW = Decimal("24000.000")
HIGH_DEMAND_CRITICAL_MW = Decimal("26000.000")
RAMP_WARNING_MW = Decimal("1000.000")
RAMP_CRITICAL_MW = Decimal("1500.000")
FORECAST_DEVIATION_WARNING_MW = Decimal("750.000")
FORECAST_DEVIATION_CRITICAL_MW = Decimal("1250.000")
