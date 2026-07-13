import { render, screen } from "@testing-library/react";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { describe, expect, it } from "vitest";

import {
  AppShell,
  ForecastScreen,
  OverviewIntroduction,
  OverviewScreen,
  PerformanceScreen,
  QualityScreen,
  SystemStatusScreen,
} from "@/components/dashboard";
import AboutPage from "@/app/about/page";
import { fixtureDemoData } from "@/lib/demo-data";

describe("dashboard screens", () => {
  it("loads the global dashboard stylesheet from the root layout", () => {
    const layoutSource = readFileSync(resolve(process.cwd(), "app/layout.tsx"), "utf8");

    expect(layoutSource).toContain('import "./globals.css";');
  });

  it("enables decision-support navigation without mutation controls", () => {
    render(<AppShell screen="overview" demoMode={true}><div>content</div></AppShell>);

    expect(screen.getAllByRole("link", { name: "Forecasts" }).length).toBeGreaterThan(0);
    expect(screen.getAllByText("Alerts").length).toBeGreaterThan(0);
    expect(screen.getAllByRole("link", { name: "Alerts" }).length).toBeGreaterThan(0);
    expect(screen.getAllByRole("link", { name: "Scenarios" }).length).toBeGreaterThan(0);
    expect(screen.getAllByRole("link", { name: "Briefing" }).length).toBeGreaterThan(0);
    expect(screen.getAllByRole("link", { name: "About" }).length).toBeGreaterThan(0);
    expect(screen.queryByText(/evaluate alerts/i)).toBeNull();
    expect(screen.queryByText(/generate briefing/i)).toBeNull();
    expect(screen.getByText(/Public demonstration mode/)).toBeTruthy();
  });

  it("renders the public overview introduction without internal delivery wording", () => {
    const view = render(<OverviewIntroduction />);

    expect(screen.getByRole("heading", { name: "Ontario electricity demand intelligence" })).toBeTruthy();
    expect(screen.getByRole("link", { name: "Explore forecasts" })).toBeTruthy();
    expect(screen.getByRole("link", { name: "Learn how it works" })).toBeTruthy();
    expect(view.container.textContent).not.toMatch(/C03|milestone|chunk|implementation phase/i);
  });

  it("renders the About page, how-it-works flow, and demo explanation", () => {
    render(<AboutPage />);

    expect(screen.getByRole("heading", { name: "How GridOps Intelligence works" })).toBeTruthy();
    expect(screen.getByRole("heading", { name: "How it works" })).toBeTruthy();
    expect(screen.getByText("Data ingestion")).toBeTruthy();
    expect(screen.getByRole("heading", { name: "Demo mode" })).toBeTruthy();
    expect(screen.getByText(/not live IESO data/i)).toBeTruthy();
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
