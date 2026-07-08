"""Static source registry for M02 ingestion contracts."""

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class SourceDefinition:
    """Describe a supported source without coupling it to a parser."""

    name: str
    source_type: str
    parser_version: str
    content_type: str


SOURCE_REGISTRY: dict[str, SourceDefinition] = {
    "ieso-hourly-demand": SourceDefinition(
        name="ieso-hourly-demand",
        source_type="electricity_demand",
        parser_version="ieso-hourly-demand:v1",
        content_type="text/csv",
    ),
    "weather-observations": SourceDefinition(
        name="weather-observations",
        source_type="weather_observation",
        parser_version="weather-observations:v1",
        content_type="text/csv",
    ),
    "weather-forecasts": SourceDefinition(
        name="weather-forecasts",
        source_type="weather_forecast",
        parser_version="weather-forecasts:v1",
        content_type="text/csv",
    ),
}


def get_source_definition(source_name: str) -> SourceDefinition:
    """Return a supported source definition or fail clearly."""

    try:
        return SOURCE_REGISTRY[source_name]
    except KeyError as exc:
        raise ValueError(f"unsupported source: {source_name}") from exc
