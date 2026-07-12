import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import {
  AppShell,
  ForecastScreen,
  OverviewScreen,
  PerformanceScreen,
  QualityScreen,
  SystemStatusScreen,
} from "@/components/dashboard";
import { fixtureDemoData } from "@/lib/demo-data";

describe("dashboard screens", () => {
  it("renders navigation with C03 placeholders", () => {
    render(<AppShell screen="overview" demoMode={true}><div>content</div></AppShell>);

    expect(screen.getAllByRole("link", { name: "Forecasts" }).length).toBeGreaterThan(0);
    expect(screen.getAllByText("Alerts").length).toBeGreaterThan(0);
    expect(screen.getAllByText("C03").length).toBeGreaterThan(0);
    expect(screen.getByText(/Public demonstration mode/)).toBeTruthy();
  });

  it("renders the overview from persisted-contract data", () => {
    render(<OverviewScreen data={fixtureDemoData} />);

    expect(screen.getByText("Latest successful production forecast")).toBeTruthy();
    expect(screen.getByText("Fixture-backed demonstration data")).toBeTruthy();
    expect(screen.getByText(/Intervals may be unavailable/)).toBeTruthy();
  });

  it("renders P50 and actual demand without invented interval bands", () => {
    render(<ForecastScreen forecast={fixtureDemoData.forecast} />);

    expect(screen.getByText("P50 hourly demand forecast")).toBeTruthy();
    expect(screen.getByText("Actual demand")).toBeTruthy();
    expect(screen.getByText(/No P10\/P90 band has been estimated/)).toBeTruthy();
  });

  it("renders the quality empty state", () => {
    render(<QualityScreen datasets={[]} />);

    expect(screen.getByText("No quality runs are available")).toBeTruthy();
  });

  it("renders persisted model limitations without calculating metrics", () => {
    render(<PerformanceScreen data={fixtureDemoData} />);

    expect(screen.getByText("Peak error is not persisted and is not displayed.")).toBeTruthy();
    expect(screen.getByText("Ramp error is not persisted and is not displayed.")).toBeTruthy();
  });

  it("renders safe system status fields only", () => {
    const view = render(<SystemStatusScreen system={fixtureDemoData.system} />);

    expect(screen.getByText("Database readiness")).toBeTruthy();
    expect(screen.getByText(/excludes connection strings, hostnames, credentials/)).toBeTruthy();
    expect(view.container.textContent).not.toContain("localhost");
  });
});
