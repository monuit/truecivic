import "./globals.css";
import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "TrueCivic",
  description: "Parliamentary intelligence across jurisdictions",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
