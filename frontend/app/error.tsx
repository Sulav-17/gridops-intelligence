"use client";

export default function ErrorPage({ reset }: { error: Error & { digest?: string }; reset: () => void }) {
  return (
    <main className="fallback-page">
      <p className="eyebrow">Unavailable</p>
      <h1>Dashboard page could not load</h1>
      <p>Retry the page, or enable the explicit fixture-backed fallback for a local demonstration.</p>
      <button type="button" onClick={reset}>Try again</button>
    </main>
  );
}
