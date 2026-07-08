"""Tests for source registry contracts."""

import pytest

from gridops.sources import get_source_definition


def test_source_registry_exposes_m02_sources() -> None:
    """The M02 source names resolve to stable source metadata."""

    ieso = get_source_definition("ieso-hourly-demand")
    observations = get_source_definition("weather-observations")
    forecasts = get_source_definition("weather-forecasts")

    assert ieso.source_type == "electricity_demand"
    assert observations.source_type == "weather_observation"
    assert forecasts.source_type == "weather_forecast"
    assert ieso.parser_version == "ieso-hourly-demand:v1"


def test_source_registry_rejects_unknown_source() -> None:
    """Unsupported sources fail explicitly."""

    with pytest.raises(ValueError, match="unsupported source"):
        get_source_definition("forecasting")
