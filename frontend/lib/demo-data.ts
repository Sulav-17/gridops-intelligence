import type { AlertDetail, AlertSummary, BriefingResponse, DashboardData, ScenarioResponse } from "@/lib/contracts";

const ISSUE_TIME = "2026-07-12T10:00:00Z";

export const fixtureDemoData: DashboardData = {
  data_source: "fixture_demo",
  forecast: {
    forecast_run_id: 701,
    forecast_issue_time_utc: ISSUE_TIME,
    horizon_start_utc: "2026-07-12T11:00:00Z",
    horizon_end_utc: "2026-07-13T11:00:00Z",
    horizon_interval_count: 24,
    model_artifact_id: 41,
    model_name: "fixture_gradient_boosting",
    model_type: "sklearn_gradient_boosting",
    model_version: "m05-demo-1",
    feature_version: "m04_c01_foundation",
    quality_status: "trusted_fixture_demo",
    intervals_available: false,
    predictions: Array.from({ length: 24 }, (_, index) => {
      const target = new Date(Date.parse("2026-07-12T11:00:00Z") + index * 3_600_000);
      const forecast = 18250 + Math.round(1300 * Math.sin(((index - 7) / 24) * Math.PI));
      return {
        prediction_id: 800 + index,
        target_interval_start_utc: target.toISOString(),
        target_interval_end_utc: new Date(target.getTime() + 3_600_000).toISOString(),
        lead_hour: index + 1,
        p10_demand_mw: null,
        p50_demand_mw: `${forecast}.000`,
        p90_demand_mw: null,
        actual_demand_mw: index < 4 ? `${forecast - 85 + index * 32}.000` : null,
        prediction_type: "p50_only",
      };
    }),
    peak: {
      peak_output_id: 72,
      peak_demand_mw: "19550.000",
      peak_target_interval_start_utc: "2026-07-12T19:00:00Z",
      peak_target_interval_end_utc: "2026-07-12T20:00:00Z",
      peak_lead_hour: 9,
    },
    ramps: [
      {
        ramp_output_id: 52,
        target_interval_start_utc: "2026-07-12T16:00:00Z",
        previous_target_interval_start_utc: "2026-07-12T15:00:00Z",
        forecast_ramp_mw: "460.000",
        absolute_ramp_mw: "460.000",
      },
    ],
    limitations: {
      true_prediction_intervals_guaranteed: false,
      p10_p90_may_be_null: true,
    },
  },
  overview: {
    forecast: null,
    active_alert_count: 2,
    worst_current_alert_severity: "warning",
    source_health: [
      { dataset_name: "ieso_hourly_demand", latest_quality_run_status: "succeeded", worst_severity: null, is_blocked: false },
      { dataset_name: "weather_observations", latest_quality_run_status: "succeeded", worst_severity: "warning", is_blocked: false },
      { dataset_name: "weather_forecasts", latest_quality_run_status: "succeeded", worst_severity: null, is_blocked: false },
    ],
    latest_briefing: {
      briefing_run_id: 91,
      generated_at_utc: "2026-07-12T10:15:00Z",
      summary: { narrative_generated: false, generated_from: "fixture-backed demonstration records" },
    },
  },
  quality: {
    datasets: [
      { dataset_name: "ieso_hourly_demand", latest_quality_run_status: "succeeded", worst_severity: null, is_blocked: false, check_counts_by_status: { passed: 8 }, latest_checked_at_utc: "2026-07-12T10:05:00Z", safe_failure_summaries: [] },
      { dataset_name: "weather_observations", latest_quality_run_status: "succeeded", worst_severity: "warning", is_blocked: false, check_counts_by_status: { passed: 6, failed: 1 }, latest_checked_at_utc: "2026-07-12T10:04:00Z", safe_failure_summaries: ["Fixture observation freshness is limited to the demonstration window."] },
      { dataset_name: "weather_forecasts", latest_quality_run_status: "succeeded", worst_severity: null, is_blocked: false, check_counts_by_status: { passed: 7 }, latest_checked_at_utc: "2026-07-12T10:04:00Z", safe_failure_summaries: [] },
    ],
  },
  performance: {
    production_metrics: [
      { metric_result_id: 301, metric_name: "mae", metric_value: "315.000000", metric_unit: "MW", evaluation_window_start_utc: "2026-07-01T00:00:00Z", evaluation_window_end_utc: "2026-07-08T00:00:00Z", created_at_utc: "2026-07-12T10:00:00Z", row_count: 168, model_artifact_id: 41, model_name: "fixture_gradient_boosting", model_version: "m05-demo-1", feature_version: "m04_c01_foundation" },
      { metric_result_id: 302, metric_name: "rmse", metric_value: "401.000000", metric_unit: "MW", evaluation_window_start_utc: "2026-07-01T00:00:00Z", evaluation_window_end_utc: "2026-07-08T00:00:00Z", created_at_utc: "2026-07-12T10:00:00Z", row_count: 168, model_artifact_id: 41, model_name: "fixture_gradient_boosting", model_version: "m05-demo-1", feature_version: "m04_c01_foundation" },
    ],
    baseline: { baseline_forecast_run_id: 201, baseline_name: "same_hour_yesterday", metrics: [{ metric_result_id: 203, metric_name: "mae", metric_value: "355.000000", metric_unit: "MW", evaluation_window_start_utc: "2026-07-01T00:00:00Z", evaluation_window_end_utc: "2026-07-08T00:00:00Z", created_at_utc: "2026-07-12T09:00:00Z" }] },
    drift_summaries: [{ drift_summary_id: 401, model_artifact_id: 41, model_name: "fixture_gradient_boosting", model_version: "m05-demo-1", feature_version: "m04_c01_foundation", feature_name: "temperature_c", drift_metric_name: "absolute_mean_difference", drift_score: "0.420000", baseline_window_start_utc: "2026-06-01T00:00:00Z", baseline_window_end_utc: "2026-06-08T00:00:00Z", comparison_window_start_utc: "2026-07-01T00:00:00Z", comparison_window_end_utc: "2026-07-08T00:00:00Z", summary: { status: "calculated" }, created_at_utc: "2026-07-12T10:00:00Z" }],
    limitations: { metrics_are_persisted_not_presentation_calculated: true, peak_error_available: false, ramp_error_available: false },
  },
  system: { status: "ready", database: "ready", demo_mode: true, latest_runs: { ingestion: "2026-07-12T09:55:00Z", quality: "2026-07-12T10:05:00Z", forecast: ISSUE_TIME, alert_evaluation: "2026-07-12T10:10:00Z", briefing: "2026-07-12T10:15:00Z" } },
};

fixtureDemoData.overview.forecast = fixtureDemoData.forecast;

export const fixtureAlerts: AlertSummary[] = [
  { alert_id: 301, alert_type: "high_demand", severity: "warning", state: "open", rule_name: "high_demand_fixed_threshold", title: "High forecast demand", explanation: "Persisted fixed-threshold alert evidence.", production_forecast_run_id: 701, forecast_issue_time_utc: ISSUE_TIME, target_interval_start_utc: "2026-07-12T19:00:00Z", target_interval_end_utc: "2026-07-12T20:00:00Z", opened_at_utc: "2026-07-12T10:10:00Z", updated_at_utc: "2026-07-12T10:10:00Z", current_evidence: { threshold_mw: "19000.000", observed_forecast_mw: "19550.000" } },
  { alert_id: 302, alert_type: "forecast_ramp", severity: "watch", state: "acknowledged", rule_name: "large_adjacent_forecast_ramp", title: "Large adjacent forecast ramp", explanation: "Persisted ramp rule evidence.", production_forecast_run_id: 701, forecast_issue_time_utc: ISSUE_TIME, target_interval_start_utc: "2026-07-12T16:00:00Z", target_interval_end_utc: "2026-07-12T17:00:00Z", opened_at_utc: "2026-07-12T10:10:00Z", updated_at_utc: "2026-07-12T10:12:00Z", current_evidence: { threshold_mw: "400.000", absolute_ramp_mw: "460.000" } },
];
export const fixtureAlertDetail: AlertDetail = { ...fixtureAlerts[0], evidence_records: [{ alert_evidence_id: 501, alert_evaluation_run_id: 81, generated_at_utc: "2026-07-12T10:10:00Z", evidence: fixtureAlerts[0].current_evidence }], lifecycle_history: [{ lifecycle_history_id: 601, from_state: null, to_state: "open", transition_reason: "Alert created from persisted rule evaluation.", changed_at_utc: "2026-07-12T10:10:00Z" }] };
export const fixtureScenario: ScenarioResponse = { scenario_id: 901, scenario_type: "combined_weather_load", production_forecast_run_id: 701, status: "succeeded", scenario_version: "m06_c02_scenario_v1", generated_at_utc: "2026-07-12T10:20:00Z", assumptions: [{ assumption_name: "temperature_delta_c", assumption_value: "2.000", assumption_unit: "C", assumption_json: null }, { assumption_name: "demand_growth_percent", assumption_value: "1.000", assumption_unit: "percent", assumption_json: null }], limitations: { scenario_outputs_are_predictions: false, weather_scenarios_use_deterministic_approximation: true, humidity_delta_percent_does_not_change_values: true }, summary: { peak_change_mw: "345.500", largest_ramp_change_mw: "4.600" }, result_rows: [{ target_interval_start_utc: "2026-07-12T19:00:00Z", target_interval_end_utc: "2026-07-12T20:00:00Z", base_value_mw: "19550.000", scenario_value_mw: "19895.500", delta_mw: "345.500", row_metadata: {} }] };
export const fixtureBriefing: BriefingResponse = { briefing_id: 91, production_forecast_run_id: 701, status: "succeeded", briefing_version: "m06_c02_briefing_v1", generated_at_utc: "2026-07-12T10:15:00Z", summary: { narrative_generated: false }, facts: [{ fact_type: "expected_peak", fact_value: { peak_demand_mw: "19550.000", peak_hour: "2026-07-12T19:00:00Z" }, evidence: { source: "forecast_peak_output" } }, { fact_type: "confidence_limitations", fact_value: { limitation: "True prediction intervals are unavailable." }, evidence: { source: "forecast_limitations" } }] };
