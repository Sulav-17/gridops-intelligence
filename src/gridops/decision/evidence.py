"""Alert evidence normalization and deterministic fingerprints."""

import hashlib
import json
from datetime import UTC, datetime
from decimal import Decimal

FINGERPRINT_VERSION = "m06_alert_fingerprint_v1"


def alert_fingerprint(parts: dict[str, object]) -> str:
    """Return a stable business fingerprint for deterministic alert identity."""

    payload = normalize_evidence({"fingerprint_version": FINGERPRINT_VERSION, **parts})
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def normalize_evidence(value: object) -> object:
    """Convert evidence values into JSON-safe deterministic shapes."""

    if isinstance(value, datetime):
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("alert evidence datetimes must be timezone-aware")
        return value.astimezone(UTC).isoformat()
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, dict):
        return {str(key): normalize_evidence(item) for key, item in sorted(value.items())}
    if isinstance(value, (list, tuple)):
        return [normalize_evidence(item) for item in value]
    if isinstance(value, str | int | float | bool) or value is None:
        return value
    return str(value)


def utc_timestamp(value: datetime) -> datetime:
    """Validate and coerce a timestamp to aware UTC."""

    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("alert timestamps must be timezone-aware")

    return value.astimezone(UTC)
