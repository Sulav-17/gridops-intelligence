import Link from "next/link";

export default function DocumentationPage() {
  return (
    <main className="documentation-page">
      <p className="eyebrow">GridOps Intelligence</p>
      <h1>Dashboard limitations</h1>
      <p>
        This dashboard displays persisted decision-support records. It does not control the
        grid, replace IESO forecasts, issue reliability declarations, or provide trading
        recommendations.
      </p>
      <ul>
        <li>Prediction intervals are shown only when P10 and P90 are persisted.</li>
        <li>Fixture-backed demo data is synthetic demonstration data, not live ingestion.</li>
        <li>Scenarios are simulations, not forecasts.</li>
        <li>Alerts are internal attention conditions, not official IESO categories.</li>
      </ul>
      <Link href="/">Return to overview</Link>
    </main>
  );
}
