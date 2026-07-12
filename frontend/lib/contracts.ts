export type IsoTimestamp = string;

export interface ForecastPrediction {
  prediction_id: number;
  target_interval_start_utc: IsoTimestamp;
  target_interval_end_utc: IsoTimestamp;
  lead_hour: number;
  p10_demand_mw: string | null;
  p50_demand_mw: string;
  p90_demand_mw: string | null;
  actual_demand_mw: string | null;
  prediction_type: string;
}

export interface ForecastPeak {
  peak_output_id: number;
  peak_demand_mw: string;
  peak_target_interval_start_utc: IsoTimestamp;
  peak_target_interval_end_utc: IsoTimestamp;
  peak_lead_hour: number;
}

export interface ForecastRamp {
  ramp_output_id: number;
  target_interval_start_utc: IsoTimestamp;
  previous_target_interval_start_utc: IsoTimestamp;
  forecast_ramp_mw: string;
  absolute_ramp_mw: string;
}

export interface ForecastResponse {
  forecast_run_id: number;
  forecast_issue_time_utc: IsoTimestamp;
  horizon_start_utc: IsoTimestamp | null;
  horizon_end_utc: IsoTimestamp | null;
  horizon_interval_count: number;
  model_artifact_id: number | null;
  model_name: string;
  model_type: string;
  model_version: string;
  feature_version: string;
  quality_status: string | null;
  intervals_available: boolean;
  predictions: ForecastPrediction[];
  peak: ForecastPeak | null;
  ramps: ForecastRamp[];
  limitations: {
    true_prediction_intervals_guaranteed: boolean;
    p10_p90_may_be_null: boolean;
  };
}

export interface SourceHealthItem {
  dataset_name: string;
  latest_quality_run_status: string;
  worst_severity: string | null;
  is_blocked: boolean;
  check_counts_by_status?: Record<string, number>;
  latest_checked_at_utc?: IsoTimestamp | null;
  safe_failure_summaries?: string[];
}

export interface QualityHealthResponse {
  datasets: SourceHealthItem[];
}

export interface OverviewResponse {
  forecast: ForecastResponse | null;
  active_alert_count: number;
  worst_current_alert_severity: string | null;
  source_health: SourceHealthItem[];
  latest_briefing: {
    briefing_run_id: number;
    generated_at_utc: IsoTimestamp;
    summary: Record<string, unknown> | null;
  } | null;
}

export interface Metric {
  metric_result_id: number;
  metric_name: string;
  metric_value: string;
  metric_unit: string | null;
  evaluation_window_start_utc: IsoTimestamp | null;
  evaluation_window_end_utc: IsoTimestamp | null;
  created_at_utc: IsoTimestamp;
  row_count?: number;
  model_artifact_id?: number | null;
  model_name?: string;
  model_version?: string;
  feature_version?: string;
}

export interface DriftSummary {
  drift_summary_id: number;
  model_artifact_id: number | null;
  model_name: string;
  model_version: string;
  feature_version: string;
  feature_name: string;
  drift_metric_name: string;
  drift_score: string | null;
  baseline_window_start_utc: IsoTimestamp;
  baseline_window_end_utc: IsoTimestamp;
  comparison_window_start_utc: IsoTimestamp;
  comparison_window_end_utc: IsoTimestamp;
  summary: Record<string, unknown> | null;
  created_at_utc: IsoTimestamp;
}

export interface ModelPerformanceResponse {
  production_metrics: Metric[];
  baseline: {
    baseline_forecast_run_id: number;
    baseline_name: string;
    metrics: Metric[];
  } | null;
  drift_summaries: DriftSummary[];
  limitations: {
    metrics_are_persisted_not_presentation_calculated: boolean;
    peak_error_available: boolean;
    ramp_error_available: boolean;
  };
}

export interface SystemStatusResponse {
  status: "ready" | "not_ready";
  database: "ready" | "not_ready";
  demo_mode: boolean;
  latest_runs: {
    ingestion: IsoTimestamp | null;
    quality: IsoTimestamp | null;
    forecast: IsoTimestamp | null;
    alert_evaluation: IsoTimestamp | null;
    briefing: IsoTimestamp | null;
  };
}

export interface DashboardData {
  overview: OverviewResponse;
  forecast: ForecastResponse | null;
  quality: QualityHealthResponse;
  performance: ModelPerformanceResponse;
  system: SystemStatusResponse;
  data_source: "backend" | "fixture_demo";
}
