import { fixtureDemoData } from "@/lib/demo-data";
import type {
  DashboardData,
  ForecastResponse,
  ModelPerformanceResponse,
  OverviewResponse,
  QualityHealthResponse,
  SystemStatusResponse,
} from "@/lib/contracts";

const DEFAULT_TIMEOUT_MS = 8_000;

export class ApiClientError extends Error {
  constructor(
    message: string,
    readonly kind: "network" | "timeout" | "http" | "invalid_response",
    readonly status?: number,
  ) {
    super(message);
  }
}

export interface ApiClientOptions {
  baseUrl?: string;
  timeoutMs?: number;
  fetchImpl?: typeof fetch;
}

export class GridOpsApiClient {
  private readonly baseUrl: string;
  private readonly timeoutMs: number;
  private readonly fetchImpl: typeof fetch;

  constructor(options: ApiClientOptions = {}) {
    this.baseUrl = (options.baseUrl ?? process.env.NEXT_PUBLIC_GRIDOPS_API_BASE_URL ?? "").replace(/\/$/, "");
    this.timeoutMs = options.timeoutMs ?? DEFAULT_TIMEOUT_MS;
    this.fetchImpl = options.fetchImpl ?? fetch;
  }

  getOverview(): Promise<OverviewResponse> {
    return this.request("/dashboard/overview", isOverviewResponse);
  }

  getLatestForecast(): Promise<ForecastResponse | null> {
    return this.request("/forecasts/latest", isForecastResponse).catch((error: unknown) => {
      if (error instanceof ApiClientError && error.status === 404) {
        return null;
      }
      throw error;
    });
  }

  getQualityHealth(): Promise<QualityHealthResponse> {
    return this.request("/quality/health", isQualityHealthResponse);
  }

  getModelPerformance(): Promise<ModelPerformanceResponse> {
    return this.request("/model-performance/latest", isModelPerformanceResponse);
  }

  getSystemStatus(): Promise<SystemStatusResponse> {
    return this.request("/system/status", isSystemStatusResponse);
  }

  private async request<T>(path: string, isResponse: (value: unknown) => value is T): Promise<T> {
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), this.timeoutMs);
    let response: Response;
    try {
      response = await this.fetchImpl(`${this.baseUrl}${path}`, {
        headers: { Accept: "application/json" },
        signal: controller.signal,
      });
    } catch (error) {
      if (error instanceof DOMException && error.name === "AbortError") {
        throw new ApiClientError("The backend request timed out.", "timeout");
      }
      throw new ApiClientError("The backend is unavailable.", "network");
    } finally {
      clearTimeout(timeout);
    }

    if (!response.ok) {
      throw new ApiClientError(
        response.status === 404 ? "The requested data is not available." : "The backend request failed.",
        "http",
        response.status,
      );
    }

    let body: unknown;
    try {
      body = await response.json();
    } catch {
      throw new ApiClientError("The backend returned invalid JSON.", "invalid_response");
    }
    if (!isResponse(body)) {
      throw new ApiClientError("The backend response did not match the dashboard contract.", "invalid_response");
    }
    return body;
  }
}

export async function loadDashboardData(options: {
  client?: GridOpsApiClient;
  useDemoData?: boolean;
} = {}): Promise<DashboardData> {
  const client = options.client ?? new GridOpsApiClient();
  const useDemoData = options.useDemoData ?? process.env.NEXT_PUBLIC_GRIDOPS_USE_DEMO_DATA === "true";
  try {
    const [overview, forecast, quality, performance, system] = await Promise.all([
      client.getOverview(),
      client.getLatestForecast(),
      client.getQualityHealth(),
      client.getModelPerformance(),
      client.getSystemStatus(),
    ]);
    return { overview, forecast, quality, performance, system, data_source: "backend" };
  } catch (error) {
    if (useDemoData && error instanceof ApiClientError) {
      return fixtureDemoData;
    }
    throw error;
  }
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function isForecastResponse(value: unknown): value is ForecastResponse {
  return isRecord(value) && typeof value.forecast_run_id === "number" && Array.isArray(value.predictions) && Array.isArray(value.ramps) && isRecord(value.limitations);
}

function isOverviewResponse(value: unknown): value is OverviewResponse {
  return isRecord(value) && "forecast" in value && typeof value.active_alert_count === "number" && Array.isArray(value.source_health);
}

function isQualityHealthResponse(value: unknown): value is QualityHealthResponse {
  return isRecord(value) && Array.isArray(value.datasets);
}

function isModelPerformanceResponse(value: unknown): value is ModelPerformanceResponse {
  return isRecord(value) && Array.isArray(value.production_metrics) && Array.isArray(value.drift_summaries) && isRecord(value.limitations);
}

function isSystemStatusResponse(value: unknown): value is SystemStatusResponse {
  return isRecord(value) && typeof value.status === "string" && typeof value.database === "string" && isRecord(value.latest_runs);
}
