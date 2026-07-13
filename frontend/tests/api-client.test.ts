import { describe, expect, it } from "vitest";

import { GridOpsApiClient, loadDashboardData } from "@/lib/api-client";
import { fixtureDemoData } from "@/lib/demo-data";

function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });
}

describe("GridOpsApiClient", () => {
  it("returns typed dashboard data from successful backend responses", async () => {
    const client = new GridOpsApiClient({
      baseUrl: "https://gridops.test",
      fetchImpl: async (input) => {
        const path = String(input);
        if (path.endsWith("/dashboard/overview")) return jsonResponse(fixtureDemoData.overview);
        if (path.endsWith("/forecasts/latest")) return jsonResponse(fixtureDemoData.forecast);
        if (path.endsWith("/quality/health")) return jsonResponse(fixtureDemoData.quality);
        if (path.endsWith("/model-performance/latest")) return jsonResponse(fixtureDemoData.performance);
        return jsonResponse(fixtureDemoData.system);
      },
    });

    const data = await loadDashboardData({ client });

    expect(data.data_source).toBe("backend");
    expect(data.forecast?.forecast_run_id).toBe(701);
    expect(data.quality.datasets).toHaveLength(3);
  });

  it("reports a safe backend failure without silently substituting data", async () => {
    const client = new GridOpsApiClient({
      fetchImpl: async () => jsonResponse({ detail: "unavailable" }, 503),
    });

    await expect(client.getOverview()).rejects.toMatchObject({
      kind: "http",
      status: 503,
    });
  });

  it("uses fixture demo data only when explicitly enabled", async () => {
    const client = new GridOpsApiClient({ fetchImpl: async () => { throw new TypeError("offline"); } });

    const data = await loadDashboardData({ client, useDemoData: true });

    expect(data).toBe(fixtureDemoData);
    expect(data.data_source).toBe("fixture_demo");
  });

  it("uses fixture fallback after a backend failure when the public environment flag is enabled", async () => {
    const originalValue = process.env.NEXT_PUBLIC_GRIDOPS_USE_DEMO_DATA;
    process.env.NEXT_PUBLIC_GRIDOPS_USE_DEMO_DATA = "true";
    const client = new GridOpsApiClient({ fetchImpl: async () => { throw new TypeError("offline"); } });

    try {
      await expect(loadDashboardData({ client })).resolves.toBe(fixtureDemoData);
    } finally {
      if (originalValue === undefined) delete process.env.NEXT_PUBLIC_GRIDOPS_USE_DEMO_DATA;
      else process.env.NEXT_PUBLIC_GRIDOPS_USE_DEMO_DATA = originalValue;
    }
  });
});
