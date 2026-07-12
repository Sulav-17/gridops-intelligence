"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import {
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import { ApiClientError, loadDashboardData } from "@/lib/api-client";
import type {
  DashboardData,
  ForecastResponse,
  Metric,
  SourceHealthItem,
  SystemStatusResponse,
} from "@/lib/contracts";

export type Screen = "overview" | "forecasts" | "quality" | "performance" | "status" | "alerts" | "scenarios" | "briefing";

const screenMetadata: Record<Screen, { title: string; context: string }> = {
  overview: { title: "Operational overview", context: "Persisted forecast and source-health evidence" },
  forecasts: { title: "Forecasts", context: "Day-ahead demand forecast outputs" },
  quality: { title: "Data quality", context: "Latest persisted source-health results" },
  performance: { title: "Model performance", context: "Persisted baseline, monitoring, and drift evidence" },
  status: { title: "System status", context: "Safe service readiness and operational timestamps" },
  alerts: { title: "Alerts", context: "Persisted deterministic attention signals" },
  scenarios: { title: "Scenarios", context: "Bounded deterministic simulations" },
  briefing: { title: "Briefing", context: "Persisted deterministic briefing facts" },
};

export function DashboardPage({ screen }: { screen: Screen }) {
  const [data, setData] = useState<DashboardData | null>(null);
  const [error, setError] = useState<ApiClientError | null>(null);

  useEffect(() => {
    let active = true;
    loadDashboardData()
      .then((result) => {
        if (active) setData(result);
      })
      .catch((reason: unknown) => {
        if (active) {
          setError(
            reason instanceof ApiClientError
              ? reason
              : new ApiClientError("The dashboard data could not be loaded.", "network"),
          );
        }
      });
    return () => {
      active = false;
    };
  }, []);

  const metadata = screenMetadata[screen];
  return (
    <AppShell screen={screen} demoMode={data?.system.demo_mode ?? process.env.NEXT_PUBLIC_GRIDOPS_DEMO_MODE === "true"}>
      <header className="page-heading">
        <div>
          <p className="eyebrow">Ontario electricity demand operations</p>
          <h1>{metadata.title}</h1>
          <p>{metadata.context}</p>
        </div>
        {data?.data_source === "fixture_demo" ? <DemoDataLabel /> : null}
      </header>
      {error ? <UnavailableState error={error} /> : null}
      {!data && !error ? <LoadingState /> : null}
      {data ? <ScreenContent screen={screen} data={data} /> : null}
    </AppShell>
  );
}

export function AppShell({
  children,
  screen,
  demoMode,
}: {
  children: React.ReactNode;
  screen: Screen;
  demoMode: boolean;
}) {
  return (
    <div className="app-shell">
      <a className="skip-link" href="#main-content">Skip to content</a>
      <aside className="sidebar" aria-label="Primary navigation">
        <Brand />
        <Navigation current={screen} />
        <LimitationsPanel />
      </aside>
      <main id="main-content" className="main-content">
        <div className="mobile-bar"><Brand compact /><Navigation current={screen} compact /></div>
        {demoMode ? <div className="demo-banner" role="status">Public demonstration mode — records may be fixture-backed and are not live IESO operations.</div> : null}
        {children}
      </main>
    </div>
  );
}

function Brand({ compact = false }: { compact?: boolean }) {
  return <div className={compact ? "brand compact-brand" : "brand"}><span className="brand-mark" aria-hidden="true">G</span><span><strong>GridOps</strong><small>Intelligence</small></span></div>;
}

function Navigation({ current, compact = false }: { current: Screen; compact?: boolean }) {
  const items: Array<{ label: string; href?: string; screen?: Screen; pending?: boolean }> = [
    { label: "Overview", href: "/", screen: "overview" },
    { label: "Forecasts", href: "/forecasts", screen: "forecasts" },
    { label: "Alerts", href: "/alerts", screen: "alerts" },
    { label: "Data Quality", href: "/data-quality", screen: "quality" },
    { label: "Scenarios", href: "/scenarios", screen: "scenarios" },
    { label: "Briefing", href: "/briefing", screen: "briefing" },
    { label: "Model Performance", href: "/model-performance", screen: "performance" },
    { label: "System Status", href: "/system-status", screen: "status" },
    { label: "Documentation", href: "/documentation" },
  ];
  return <nav className={compact ? "navigation compact-navigation" : "navigation"}>{items.map((item) => item.pending ? <span className="nav-item disabled" aria-disabled="true" key={item.label}>{item.label}<small>C03</small></span> : <Link className={`nav-item ${item.screen === current ? "active" : ""}`} href={item.href ?? "/"} key={item.label} aria-current={item.screen === current ? "page" : undefined}>{item.label}</Link>)}</nav>;
}

function LimitationsPanel() {
  return <section className="limitations-panel" aria-labelledby="limitations-title"><h2 id="limitations-title">Decision-support limits</h2><p>Not a grid-control system, official IESO forecast, emergency category, or trading signal.</p><Link href="/documentation">Review limitations</Link></section>;
}

function ScreenContent({ screen, data }: { screen: Screen; data: DashboardData }) {
  if (screen === "overview") return <OverviewScreen data={data} />;
  if (screen === "forecasts") return <ForecastScreen forecast={data.forecast} />;
  if (screen === "quality") return <QualityScreen datasets={data.quality.datasets} />;
  if (screen === "performance") return <PerformanceScreen data={data} />;
  return <SystemStatusScreen system={data.system} />;
}

export function OverviewScreen({ data }: { data: DashboardData }) {
  const forecast = data.overview.forecast;
  if (!forecast) return <EmptyState title="No persisted forecast is available" detail="The overview will populate after a successful production forecast run is persisted." />;
  const largestRamp = largestRampFor(forecast);
  return <div className="screen-grid"><section className="card card-wide"><div className="card-header"><div><p className="eyebrow">Latest successful production forecast</p><h2>{forecast.model_name}</h2></div><StatusBadge value={forecast.quality_status ?? "not assessed"} /></div><dl className="metric-grid"><Metric label="Forecast issued" value={formatOntarioTime(forecast.forecast_issue_time_utc)} /><Metric label="Forecast horizon" value={`${forecast.horizon_interval_count} hourly intervals`} /><Metric label="Expected peak" value={forecast.peak ? formatMw(forecast.peak.peak_demand_mw) : "Not persisted"} /><Metric label="Peak interval" value={forecast.peak ? formatOntarioTime(forecast.peak.peak_target_interval_start_utc) : "Not persisted"} /><Metric label="Largest ramp" value={largestRamp ? `${formatMw(largestRamp.absolute_ramp_mw)} / hour` : "Not persisted"} /><Metric label="Forecast run" value={`#${forecast.forecast_run_id}`} /></dl></section><section className="card"><p className="eyebrow">Operational attention</p><h2>{data.overview.active_alert_count} active</h2><p>Worst persisted severity: <StatusBadge value={data.overview.worst_current_alert_severity ?? "none"} /></p><p className="muted">Alert details are introduced in C03.</p></section><section className="card"><p className="eyebrow">Briefing</p><h2>{data.overview.latest_briefing ? "Available" : "Not generated"}</h2><p>{data.overview.latest_briefing ? `Latest deterministic facts: ${formatOntarioTime(data.overview.latest_briefing.generated_at_utc)}` : "No persisted deterministic briefing is available."}</p></section><section className="card card-wide"><div className="card-header"><div><p className="eyebrow">Source health</p><h2>Latest persisted quality outcomes</h2></div><span className="fixture-note">{data.data_source === "fixture_demo" ? "Fixture-backed demonstration data" : "Backend records"}</span></div><SourceHealthSummary datasets={data.overview.source_health} /></section><section className="card card-wide"><p className="eyebrow">Known limitation</p><h2>Intervals may be unavailable</h2><p>Prediction intervals are shown only when persisted P10 and P90 values are available. This forecast contains {forecast.intervals_available ? "persisted interval values." : "P50-only values; no interval band is inferred."}</p></section></div>;
}

export function ForecastScreen({ forecast }: { forecast: ForecastResponse | null }) {
  if (!forecast) return <EmptyState title="No forecast is available" detail="The latest forecast endpoint returned no successful production forecast." />;
  const showIntervals = forecast.predictions.length > 0 && forecast.predictions.every((row) => row.p10_demand_mw !== null && row.p90_demand_mw !== null);
  const chartRows = forecast.predictions.map((row) => ({ ...row, label: formatOntarioHour(row.target_interval_start_utc), p50: Number(row.p50_demand_mw), actual: row.actual_demand_mw === null ? undefined : Number(row.actual_demand_mw), p10: row.p10_demand_mw === null ? undefined : Number(row.p10_demand_mw), p90: row.p90_demand_mw === null ? undefined : Number(row.p90_demand_mw) }));
  const ramp = largestRampFor(forecast);
  return <div className="screen-grid"><section className="card card-wide forecast-chart"><div className="card-header"><div><p className="eyebrow">P50 hourly demand forecast</p><h2>Ontario time shown; API timestamps remain UTC</h2></div><span className="run-id">Run #{forecast.forecast_run_id}</span></div><div className="chart-wrap" aria-label="Hourly demand forecast chart"><ResponsiveContainer width="100%" height={330}><LineChart data={chartRows} margin={{ top: 10, right: 20, left: 4, bottom: 4 }}><CartesianGrid strokeDasharray="3 3" stroke="#d5dedb" /><XAxis dataKey="label" minTickGap={20} /><YAxis width={64} tickFormatter={(value) => `${Math.round(value / 1000)}k`} /><Tooltip formatter={(value) => formatTooltipValue(value)} /><Legend />{showIntervals ? <><Line type="monotone" dataKey="p10" name="P10" stroke="#879b94" strokeDasharray="4 4" dot={false} /><Line type="monotone" dataKey="p90" name="P90" stroke="#879b94" strokeDasharray="4 4" dot={false} /></> : null}<Line type="monotone" dataKey="p50" name="P50 forecast" stroke="#147a68" strokeWidth={3} dot={false} /><Line type="monotone" dataKey="actual" name="Actual demand" stroke="#213f3a" strokeWidth={2} dot={false} connectNulls /></LineChart></ResponsiveContainer></div></section><section className="card"><p className="eyebrow">Peak demand</p><h2>{forecast.peak ? formatMw(forecast.peak.peak_demand_mw) : "Not persisted"}</h2><p>{forecast.peak ? formatOntarioTime(forecast.peak.peak_target_interval_start_utc) : "No peak output record."}</p></section><section className="card"><p className="eyebrow">Largest ramp</p><h2>{ramp ? formatMw(ramp.absolute_ramp_mw) : "Not persisted"}</h2><p>{ramp ? `${formatOntarioTime(ramp.previous_target_interval_start_utc)} to ${formatOntarioTime(ramp.target_interval_start_utc)}` : "No ramp output record."}</p></section><section className="card card-wide"><div className="card-header"><div><p className="eyebrow">Forecast record</p><h2>{forecast.model_name} · {forecast.model_version}</h2></div><StatusBadge value={forecast.quality_status ?? "not assessed"} /></div><dl className="metric-grid"><Metric label="Issue time" value={formatOntarioTime(forecast.forecast_issue_time_utc)} /><Metric label="Feature version" value={forecast.feature_version} /><Metric label="Model artifact" value={forecast.model_artifact_id ? `#${forecast.model_artifact_id}` : "Not recorded"} /><Metric label="Actual demand" value={forecast.predictions.some((row) => row.actual_demand_mw !== null) ? "Available for selected intervals" : "Not available"} /></dl>{!showIntervals ? <p className="notice">Prediction intervals are unavailable for this persisted forecast. No P10/P90 band has been estimated from P50 values.</p> : <p className="notice success">Persisted P10 and P90 values are displayed; they are not browser-calculated.</p>}</section></div>;
}

export function QualityScreen({ datasets }: { datasets: SourceHealthItem[] }) {
  if (datasets.length === 0) return <EmptyState title="No quality runs are available" detail="Quality health will appear after persisted checks have completed." />;
  return <section className="card card-wide"><div className="card-header"><div><p className="eyebrow">Source health</p><h2>Latest persisted quality checks</h2></div><span className="fixture-note">Fixture-backed records are not live ingestion proof</span></div><div className="table-scroll"><table><thead><tr><th>Dataset</th><th>Latest run</th><th>Severity</th><th>Blocking</th><th>Check counts</th><th>Checked</th><th>Safe notes</th></tr></thead><tbody>{datasets.map((dataset) => <tr key={dataset.dataset_name}><td><strong>{dataset.dataset_name}</strong></td><td><StatusBadge value={dataset.latest_quality_run_status} /></td><td><StatusBadge value={dataset.worst_severity ?? "healthy"} /></td><td>{dataset.is_blocked ? <span className="blocked">Blocked</span> : "Not blocked"}</td><td>{formatCounts(dataset.check_counts_by_status)}</td><td>{dataset.latest_checked_at_utc ? formatOntarioTime(dataset.latest_checked_at_utc) : "Not checked"}</td><td>{dataset.safe_failure_summaries?.length ? dataset.safe_failure_summaries.join(" ") : "—"}</td></tr>)}</tbody></table></div></section>;
}

export function PerformanceScreen({ data }: { data: DashboardData }) {
  const performance = data.performance;
  const hasEvidence = performance.production_metrics.length > 0 || performance.baseline !== null || performance.drift_summaries.length > 0;
  if (!hasEvidence) return <EmptyState title="No persisted model evidence is available" detail="This view does not calculate browser-side performance metrics." />;
  return <div className="screen-grid"><section className="card card-wide"><p className="eyebrow">Production performance</p><h2>Persisted M05 metrics</h2><MetricTable metrics={performance.production_metrics} /><p className="notice">Metrics are displayed exactly as persisted by the backend; this screen does not infer a model comparison.</p></section><section className="card card-wide"><p className="eyebrow">Latest successful baseline</p><h2>{performance.baseline?.baseline_name ?? "Not available"}</h2>{performance.baseline ? <MetricTable metrics={performance.baseline.metrics} /> : <p>No persisted successful baseline run is available.</p>}</section><section className="card card-wide"><p className="eyebrow">Drift monitoring</p><h2>Latest persisted feature summaries</h2>{performance.drift_summaries.length ? <div className="table-scroll"><table><thead><tr><th>Feature</th><th>Metric</th><th>Score</th><th>Comparison window</th><th>Model version</th></tr></thead><tbody>{performance.drift_summaries.map((item) => <tr key={item.drift_summary_id}><td>{item.feature_name}</td><td>{item.drift_metric_name}</td><td>{item.drift_score ?? "No data"}</td><td>{formatOntarioTime(item.comparison_window_start_utc)} – {formatOntarioTime(item.comparison_window_end_utc)}</td><td>{item.model_version}</td></tr>)}</tbody></table></div> : <p>No persisted drift summary is available.</p>}</section><section className="card card-wide limitations-card"><h2>Unavailable error metrics</h2><p>{performance.limitations.peak_error_available ? "Persisted peak error evidence is available." : "Peak error is not persisted and is not displayed."}</p><p>{performance.limitations.ramp_error_available ? "Persisted ramp error evidence is available." : "Ramp error is not persisted and is not displayed."}</p></section></div>;
}

export function SystemStatusScreen({ system }: { system: SystemStatusResponse }) {
  return <div className="screen-grid"><section className="card card-wide"><div className="card-header"><div><p className="eyebrow">Service connectivity</p><h2>Safe status contract</h2></div><StatusBadge value={system.status} /></div><dl className="metric-grid"><Metric label="API" value={system.status} /><Metric label="Database readiness" value={system.database} /><Metric label="Demo mode" value={system.demo_mode ? "Enabled" : "Disabled"} /></dl><p className="notice">This screen intentionally excludes connection strings, hostnames, credentials, container names, and private paths.</p></section><section className="card card-wide"><p className="eyebrow">Latest operational records</p><h2>Persisted run timestamps</h2><div className="timestamp-grid">{Object.entries(system.latest_runs).map(([name, value]) => <div key={name}><span>{name.replace("_", " ")}</span><strong>{value ? formatOntarioTime(value) : "No persisted run"}</strong></div>)}</div></section></div>;
}

function MetricTable({ metrics }: { metrics: Metric[] }) {
  if (!metrics.length) return <p>No persisted metrics are available.</p>;
  return <div className="table-scroll"><table><thead><tr><th>Metric</th><th>Value</th><th>Window</th><th>Model / feature</th></tr></thead><tbody>{metrics.map((metric) => <tr key={metric.metric_result_id}><td>{metric.metric_name.toUpperCase()}</td><td>{metric.metric_value} {metric.metric_unit ?? ""}</td><td>{metric.evaluation_window_start_utc && metric.evaluation_window_end_utc ? `${formatOntarioTime(metric.evaluation_window_start_utc)} – ${formatOntarioTime(metric.evaluation_window_end_utc)}` : "Not recorded"}</td><td>{metric.model_name ? `${metric.model_name} · ${metric.model_version ?? ""} · ${metric.feature_version ?? ""}` : "Baseline evidence"}</td></tr>)}</tbody></table></div>;
}

function SourceHealthSummary({ datasets }: { datasets: SourceHealthItem[] }) {
  if (!datasets.length) return <p>No source-health result has been persisted.</p>;
  return <div className="source-health-summary">{datasets.map((dataset) => <div key={dataset.dataset_name}><strong>{dataset.dataset_name}</strong><span><StatusBadge value={dataset.is_blocked ? "blocked" : dataset.worst_severity ?? dataset.latest_quality_run_status} /></span></div>)}</div>;
}

function Metric({ label, value }: { label: string; value: string }) { return <div><dt>{label}</dt><dd>{value}</dd></div>; }

function StatusBadge({ value }: { value: string }) { return <span className={`status-badge status-${value.toLowerCase().replace(/[^a-z]+/g, "-")}`}>{value.replaceAll("_", " ")}</span>; }

function DemoDataLabel() { return <span className="fixture-note">Fixture-backed demonstration data</span>; }

function LoadingState() { return <section className="card loading-state" aria-live="polite"><h2>Loading persisted dashboard data</h2><p>Retrieving the selected operational records.</p></section>; }

function UnavailableState({ error }: { error: ApiClientError }) { return <section className="card unavailable-state" role="alert"><h2>Dashboard data is unavailable</h2><p>{error.kind === "timeout" ? "The backend did not respond before the dashboard timeout." : error.message}</p><p>Retry when the backend is available, or explicitly enable the fixture-backed demo fallback for local demonstration.</p></section>; }

function EmptyState({ title, detail }: { title: string; detail: string }) { return <section className="card empty-state"><h2>{title}</h2><p>{detail}</p></section>; }

function largestRampFor(forecast: ForecastResponse) { return [...forecast.ramps].sort((first, second) => Number(second.absolute_ramp_mw) - Number(first.absolute_ramp_mw))[0] ?? null; }

function formatMw(value: string) { return `${Number(value).toLocaleString("en-CA", { maximumFractionDigits: 0 })} MW`; }

function formatCounts(counts?: Record<string, number>) { return counts ? Object.entries(counts).map(([name, count]) => `${count} ${name}`).join(", ") : "Not recorded"; }

function formatTooltipValue(value: unknown) { const numeric = Array.isArray(value) ? value[0] : value; return numeric === undefined ? "—" : `${Number(numeric).toLocaleString("en-CA")} MW`; }

function formatOntarioHour(value: string) { return new Intl.DateTimeFormat("en-CA", { hour: "2-digit", hour12: false, timeZone: "America/Toronto" }).format(new Date(value)); }

export function formatOntarioTime(value: string) { return new Intl.DateTimeFormat("en-CA", { year: "numeric", month: "short", day: "numeric", hour: "2-digit", minute: "2-digit", timeZone: "America/Toronto", timeZoneName: "short" }).format(new Date(value)); }
