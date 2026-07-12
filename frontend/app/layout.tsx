import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "GridOps Intelligence",
  description: "Operational energy demand forecasting and decision-support dashboard.",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return <html lang="en"><body>{children}</body></html>;
}
