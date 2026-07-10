"""Deterministic candidate model helpers for M05."""

import json
from collections.abc import Mapping, Sequence
from decimal import Decimal
from typing import Protocol, cast

FEATURE_NAMES = (
    "target_hour_utc",
    "day_of_week",
    "month",
    "is_weekend",
    "hour_sin",
    "hour_cos",
    "lag_1h_mw",
    "lag_2h_mw",
    "lag_24h_mw",
    "lag_48h_mw",
    "lag_168h_mw",
    "rolling_mean_mw",
    "rolling_min_mw",
    "rolling_max_mw",
    "rolling_std_mw",
    "recent_ramp_mw",
)
TARGET_LIKE_FEATURE_NAMES = frozenset(
    {
        "actual_demand_mw",
        "target_actual_demand_mw",
        "target_demand_mw",
        "label_demand_mw",
    }
)


class CandidateRegressor(Protocol):
    """Small protocol for sklearn-style regressors used by training."""

    def fit(self, x_values: Sequence[Sequence[float]], y_values: Sequence[float]) -> object:
        """Fit the regressor."""

    def predict(self, x_values: Sequence[Sequence[float]]) -> Sequence[float]:
        """Predict target values."""


def make_gradient_boosting_candidate(*, random_state: int = 42) -> CandidateRegressor:
    """Create the default deterministic sklearn candidate model."""

    from sklearn.ensemble import GradientBoostingRegressor  # type: ignore[import-untyped]

    return cast(
        CandidateRegressor,
        GradientBoostingRegressor(random_state=random_state, n_estimators=30, max_depth=2),
    )


def feature_vector_from_payload(payload: Mapping[str, object]) -> list[float] | None:
    """Extract the approved M04 feature vector from a snapshot payload."""

    calendar = payload.get("calendar")
    demand = payload.get("demand")
    if not isinstance(calendar, dict) or not isinstance(demand, dict):
        return None

    raw_values: list[object] = [
        calendar.get("target_hour_utc"),
        calendar.get("day_of_week"),
        calendar.get("month"),
        1 if calendar.get("is_weekend") else 0,
        calendar.get("hour_sin"),
        calendar.get("hour_cos"),
        demand.get("lag_1h_mw"),
        demand.get("lag_2h_mw"),
        demand.get("lag_24h_mw"),
        demand.get("lag_48h_mw"),
        demand.get("lag_168h_mw"),
        demand.get("rolling_mean_mw"),
        demand.get("rolling_min_mw"),
        demand.get("rolling_max_mw"),
        demand.get("rolling_std_mw"),
        demand.get("recent_ramp_mw"),
    ]
    if any(value is None for value in raw_values):
        return None

    vector = []
    for value in raw_values:
        if not isinstance(value, int | float | str | Decimal):
            return None
        vector.append(float(value))

    return vector


def payload_uses_no_target_actuals(payload: Mapping[str, object]) -> bool:
    """Return whether a feature payload avoids known target-label fields."""

    return not _contains_target_like_key(payload)


def parse_feature_payload(lineage_metadata: str | None) -> dict[str, object]:
    """Parse a persisted M04 feature snapshot payload."""

    parsed = json.loads(lineage_metadata or "{}")
    if not isinstance(parsed, dict):
        return {}

    return parsed


def _contains_target_like_key(value: object) -> bool:
    if isinstance(value, Mapping):
        for key, child in value.items():
            if str(key) in TARGET_LIKE_FEATURE_NAMES:
                return True
            if _contains_target_like_key(child):
                return True
    elif isinstance(value, Sequence) and not isinstance(value, str | bytes):
        return any(_contains_target_like_key(child) for child in value)

    return False
