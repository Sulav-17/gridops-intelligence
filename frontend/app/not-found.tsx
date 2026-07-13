import Link from "next/link";

export default function NotFound() {
  return (
    <main className="fallback-page">
      <p className="eyebrow">404</p>
      <h1>Page not found</h1>
      <p>The requested dashboard page is not available.</p>
      <Link href="/">Return to the operational overview</Link>
    </main>
  );
}
