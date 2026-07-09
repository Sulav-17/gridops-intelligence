"""Tests for M03 quality contract definitions."""

import pytest

from gridops.quality.contracts import (
    DATASET_CONTRACTS,
    QualityCheckCategory,
    QualityResultStatus,
    QualityRunStatus,
    QualitySeverity,
    get_dataset_contract,
)


def test_quality_enum_values_are_stable() -> None:
    """Quality enums expose the approved M03 vocabulary."""

    assert [severity.value for severity in QualitySeverity] == [
        "info",
        "warning",
        "error",
        "critical",
    ]
    assert [status.value for status in QualityRunStatus] == [
        "running",
        "succeeded",
        "failed",
    ]
    assert [status.value for status in QualityResultStatus] == [
        "passed",
        "failed",
        "skipped",
        "error",
    ]
    assert [category.value for category in QualityCheckCategory] == [
        "schema",
        "completeness",
        "continuity",
        "uniqueness",
        "range",
        "freshness",
        "timestamp",
        "dst",
        "source_metadata",
    ]


def test_dataset_contracts_cover_existing_m02_tables() -> None:
    """M03-C01 defines contracts only for storage that already exists."""

    assert set(DATASET_CONTRACTS) == {
        "ieso_hourly_demand",
        "weather_observations",
        "weather_forecasts",
        "raw_snapshots",
        "ingestion_runs",
    }

    for dataset_name, contract in DATASET_CONTRACTS.items():
        assert contract.dataset_name == dataset_name
        assert contract.table_name == dataset_name
        assert contract.required_fields
        assert contract.primary_key_fields
        assert set(contract.primary_key_fields).issubset(contract.required_fields)


def test_dataset_contracts_preserve_source_native_fields() -> None:
    """Contracts record source-native fields needed by later quality checks."""

    demand = get_dataset_contract("ieso_hourly_demand")
    observations = get_dataset_contract("weather_observations")
    forecasts = get_dataset_contract("weather_forecasts")

    assert demand.source_native_fields == ("source_service_date", "source_hour_ending")
    assert observations.source_native_fields == ("source_native_timestamp",)
    assert forecasts.source_native_fields == (
        "source_native_issue_time",
        "source_native_valid_time",
    )


def test_get_dataset_contract_rejects_unknown_dataset() -> None:
    """Unsupported datasets fail clearly."""

    with pytest.raises(ValueError, match="unsupported quality dataset"):
        get_dataset_contract("gold_features")
