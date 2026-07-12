import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import {
  AlertDetailPage,
  AlertsPage,
  BriefingPage,
  PageHeading,
  ScenarioResult,
  ScenariosPage,
  validateScenario,
} from "@/components/decision-support";
import {
  fixtureAlertDetail,
  fixtureAlerts,
  fixtureBriefing,
  fixtureDemoData,
  fixtureScenario,
} from "@/lib/demo-data";

function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

function installFetch(overrides: Record<string, Response | Promise<Response>> = {}) {
  const fetchMock = vi.fn((input: RequestInfo | URL) => {
    const path = String(input);
    if (overrides[path]) return overrides[path];
    if (path.endsWith("/alerts")) return Promise.resolve(jsonResponse({ alerts: fixtureAlerts }));
    if (path.endsWith(`/alerts/${fixtureAlertDetail.alert_id}`)) return Promise.resolve(jsonResponse(fixtureAlertDetail));
    if (path.endsWith("/forecasts/latest")) return Promise.resolve(jsonResponse(fixtureDemoData.forecast));
    if (path.endsWith("/scenarios")) return Promise.resolve(jsonResponse(fixtureScenario));
    if (path.endsWith("/briefings/latest")) return Promise.resolve(jsonResponse(fixtureBriefing));
    return Promise.resolve(jsonResponse({ detail: "not found" }, 404));
  });
  vi.stubGlobal("fetch", fetchMock);
  return fetchMock;
}

afterEach(() => vi.unstubAllGlobals());

describe("decision-support screens", () => {
  it("labels fixture-backed decision-support fallback data", () => {
    render(<PageHeading title="Alerts" context="Persisted evidence" fixture />);

    expect(screen.getByText("Fixture-backed demonstration data")).toBeTruthy();
  });

  it("renders persisted alerts and their evidence summaries", async () => {
    installFetch();
    render(<AlertsPage />);

    expect(await screen.findByText("High forecast demand")).toBeTruthy();
    expect(screen.getByText(/threshold mw: 19000.000/i)).toBeTruthy();
    expect(screen.getAllByRole("link", { name: /view persisted evidence/i })[0]?.getAttribute("href")).toBe("/alerts/301");
  });

  it("renders an alert empty state", async () => {
    installFetch({ "/alerts": Promise.resolve(jsonResponse({ alerts: [] })) });
    render(<AlertsPage />);

    expect(await screen.findByText("No alerts are available")).toBeTruthy();
  });

  it("renders immutable alert evidence and lifecycle history", async () => {
    installFetch();
    render(<AlertDetailPage alertId={301} />);

    expect(await screen.findByText("Current deterministic evidence")).toBeTruthy();
    expect(screen.getAllByText(/observed_forecast_mw/).length).toBeGreaterThan(0);
    expect(screen.getByText(/created → open/i)).toBeTruthy();
    expect(screen.getByText(/Alert created from persisted rule evaluation/)).toBeTruthy();
  });

  it("submits a valid bounded scenario and presents the returned simulation", async () => {
    const fetchMock = installFetch();
    render(<ScenariosPage />);

    const button = await screen.findByRole("button", { name: "Run simulation" });
    const loadGrowthInput = document.querySelector<HTMLInputElement>('input[name="demand_growth_percent"]');
    expect(loadGrowthInput).not.toBeNull();
    fireEvent.change(loadGrowthInput!, { target: { value: "2" } });
    fireEvent.click(button);

    expect(await screen.findByText("Simulation result #901")).toBeTruthy();
    const scenarioCall = fetchMock.mock.calls.find(([input]) => String(input).endsWith("/scenarios"));
    expect(scenarioCall).toBeDefined();
  });

  it.each([
    ["demand_growth_percent", "10.01", "between -10 and 10"],
    ["added_load_mw", "2000.01", "between -2000 and 2000"],
    ["temperature_delta_c", "-10.01", "between -10 and 10"],
    ["humidity_delta_percent", "30.01", "between -30 and 30"],
  ])("rejects out-of-bounds %s before requesting a scenario", (name, value, expected) => {
    const data = new FormData();
    data.set("scenario_type", "demand_growth");
    data.set(name, value);

    expect(validateScenario(data)).toBe(`${name.replaceAll("_", " ")} must be ${expected}.`);
  });

  it("rejects non-finite scenario input before requesting a scenario", () => {
    const data = new FormData();
    data.set("scenario_type", "demand_growth");
    data.set("demand_growth_percent", "Infinity");

    expect(validateScenario(data)).toBe("demand growth percent must be a finite number.");
  });

  it("prevents duplicate scenario submissions while pending", async () => {
    let resolveScenario: ((response: Response) => void) | undefined;
    const pendingResponse = new Promise<Response>((resolve) => { resolveScenario = resolve; });
    const fetchMock = installFetch({ "/scenarios": pendingResponse });
    render(<ScenariosPage />);

    const button = await screen.findByRole("button", { name: "Run simulation" });
    fireEvent.click(button);
    fireEvent.click(button);
    expect((screen.getByRole("button", { name: /running simulation/i }) as HTMLButtonElement).disabled).toBe(true);
    expect(fetchMock.mock.calls.filter(([input]) => String(input).endsWith("/scenarios"))).toHaveLength(1);

    resolveScenario?.(jsonResponse(fixtureScenario));
    expect(await screen.findByText("Simulation result #901")).toBeTruthy();
  });

  it.each([400, 403])("shows a safe server error for scenario status %i", async (status) => {
    installFetch({ "/scenarios": Promise.resolve(jsonResponse({ detail: "internal implementation detail" }, status)) });
    render(<ScenariosPage />);

    fireEvent.click(await screen.findByRole("button", { name: "Run simulation" }));
    const alert = await screen.findByRole("alert");
    expect(alert.textContent).toContain(status === 403 ? "not available in the public demonstration" : "scenario could not be created");
    expect(alert.textContent).not.toContain("internal implementation detail");
  });

  it("labels scenario output as a limited deterministic simulation", () => {
    render(<ScenarioResult result={fixtureScenario} />);

    expect(screen.getByText(/simulations, not official forecasts/i)).toBeTruthy();
    expect(screen.getByText(/deterministic approximation/i)).toBeTruthy();
    expect(screen.getByText(/without affecting values/i)).toBeTruthy();
  });

  it("renders persisted briefing facts and its empty state", async () => {
    installFetch();
    const view = render(<BriefingPage />);
    expect(await screen.findByText("expected peak")).toBeTruthy();
    expect(screen.getByText(/does not infer or generate narrative/i)).toBeTruthy();
    view.unmount();

    installFetch({ "/briefings/latest": Promise.resolve(jsonResponse({ detail: "briefing not found" }, 404)) });
    render(<BriefingPage />);
    expect(await screen.findByText("No persisted briefing is available")).toBeTruthy();
  });

  it("renders no prohibited public controls", async () => {
    installFetch();
    render(<><AlertsPage /><ScenariosPage /><BriefingPage /></>);

    await waitFor(() => expect(screen.getAllByText("High forecast demand").length).toBeGreaterThan(0));
    const text = document.body.textContent ?? "";
    for (const prohibited of ["Evaluate alerts", "Acknowledge alert", "Resolve alert", "Generate briefing", "Run ingestion", "Train model", "Run inference", "Promote model"]) {
      expect(text).not.toContain(prohibited);
    }
  });
});
