"""Simple M06 decision-support runner commands."""

import argparse
import json
from collections.abc import Sequence
from datetime import datetime
from decimal import Decimal

from gridops.config import Settings
from gridops.database import make_engine, make_session_factory, session_scope
from gridops.decision.alert_engine import evaluate_and_persist_alerts
from gridops.decision.briefing_facts import generate_briefing, utc_now
from gridops.decision.evidence import normalize_evidence
from gridops.decision.scenario_engine import run_scenario
from gridops.decision.scenario_schemas import ScenarioRequest, ScenarioType


def main(argv: Sequence[str] | None = None) -> int:
    """Run the M06 decision-support command line."""

    parser = _parser()
    args = parser.parse_args(argv)

    settings = Settings()
    engine = make_engine(settings)
    session_factory = make_session_factory(engine)
    try:
        with session_scope(session_factory) as session:
            if args.command == "evaluate-alerts":
                alert_result = evaluate_and_persist_alerts(
                    session,
                    production_forecast_run_id=args.forecast_run_id,
                    generated_at_utc=_parse_datetime(args.generated_at_utc),
                )
                payload = {
                    "command": "evaluate-alerts",
                    "evaluation_run_id": alert_result.evaluation_run.id,
                    "created_count": alert_result.created_count,
                    "reused_count": alert_result.reused_count,
                    "alert_ids": [alert.id for alert in alert_result.alerts],
                }
            elif args.command == "run-scenario":
                scenario_type = _scenario_type(args)
                scenario_result = run_scenario(
                    session,
                    request=ScenarioRequest(
                        production_forecast_run_id=args.forecast_run_id,
                        scenario_type=scenario_type,
                        generated_at_utc=_parse_datetime(args.generated_at_utc),
                        demand_growth_percent=_parse_decimal(args.load_growth_percent),
                        added_load_mw=_parse_decimal(args.added_load_mw),
                        temperature_delta_c=_parse_decimal(args.temperature_delta_c),
                        humidity_delta_percent=_parse_decimal(args.humidity_delta_percent),
                    ),
                )
                payload = {
                    "command": "run-scenario",
                    "scenario_run_id": scenario_result.scenario_run.id,
                    "scenario_type": scenario_result.scenario_run.scenario_type,
                    "result_row_count": len(scenario_result.result_rows),
                }
            elif args.command == "generate-briefing":
                briefing_result = generate_briefing(
                    session,
                    production_forecast_run_id=args.forecast_run_id,
                    generated_at_utc=_parse_datetime(args.generated_at_utc),
                )
                payload = {
                    "command": "generate-briefing",
                    "briefing_run_id": briefing_result.briefing_run.id,
                    "fact_count": len(briefing_result.facts),
                }
            else:
                raise ValueError(f"unsupported command: {args.command}")
        print(json.dumps(normalize_evidence(payload), sort_keys=True))
        return 0
    finally:
        engine.dispose()


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="GridOps M06 decision-support runner")
    subparsers = parser.add_subparsers(dest="command", required=True)

    alerts = subparsers.add_parser("evaluate-alerts")
    alerts.add_argument("--forecast-run-id", type=int, required=True)
    alerts.add_argument("--generated-at-utc")

    scenario = subparsers.add_parser("run-scenario")
    scenario.add_argument("--forecast-run-id", type=int, required=True)
    scenario.add_argument(
        "--scenario-type",
        choices=[item.value for item in ScenarioType],
    )
    scenario.add_argument("--load-growth-percent")
    scenario.add_argument("--added-load-mw")
    scenario.add_argument("--temperature-delta-c")
    scenario.add_argument("--humidity-delta-percent")
    scenario.add_argument("--generated-at-utc")

    briefing = subparsers.add_parser("generate-briefing")
    briefing.add_argument("--forecast-run-id", type=int, required=True)
    briefing.add_argument("--generated-at-utc")

    return parser


def _scenario_type(args: argparse.Namespace) -> ScenarioType:
    if args.scenario_type:
        return ScenarioType(args.scenario_type)
    has_weather = args.temperature_delta_c is not None or args.humidity_delta_percent is not None
    has_load = args.load_growth_percent is not None or args.added_load_mw is not None
    if has_weather and has_load:
        return ScenarioType.COMBINED_WEATHER_LOAD
    if has_weather:
        return ScenarioType.WEATHER_ADJUSTMENT
    return ScenarioType.DEMAND_GROWTH


def _parse_datetime(value: str | None) -> datetime:
    if value is None:
        return utc_now()
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError("runner timestamps must be timezone-aware")
    return parsed


def _parse_decimal(value: str | None) -> Decimal | None:
    if value is None:
        return None
    return Decimal(value)


if __name__ == "__main__":
    raise SystemExit(main())
