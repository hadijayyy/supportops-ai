import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "SupportOps AI — NovaCart Resolution Console",
  description: "Evidence-bound AI support workflows with deterministic safety controls.",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
