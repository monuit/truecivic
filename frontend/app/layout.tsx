import "./globals.css";
import type { Metadata } from "next";
import { cookies } from "next/headers";

import { SiteFooter } from "../components/layout/site-footer";
import { SiteHeader } from "../components/layout/site-header";
import { ThemeProvider, ThemeScript, type ThemeSetting } from "../lib/theme/theme-provider";

// MARK: Metadata helpers
function resolveMetadataBase() {
  const raw = process.env.NEXT_PUBLIC_BASE_URL;
  if (!raw) {
    return undefined;
  }
  try {
    return new URL(raw);
  } catch (error) {
    if (process.env.NODE_ENV !== "production") {
      // eslint-disable-next-line no-console -- surfaced during development
      console.warn("Invalid NEXT_PUBLIC_BASE_URL", error);
    }
    return undefined;
  }
}

export const metadata: Metadata = {
  metadataBase: resolveMetadataBase(),
  title: {
    default: "truecivic",
    template: "%s | truecivic",
  },
  description: "Keep tabs on Canada's Parliament with debates, votes, and bills.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  const themeCookie = cookies().get("truecivic-theme")?.value;
  const initialTheme: ThemeSetting = themeCookie === "light" || themeCookie === "dark" || themeCookie === "system" ? (themeCookie as ThemeSetting) : "system";
  return (
    <html lang="en">
      <body className="site-body">
        <ThemeScript initialTheme={initialTheme} />
        <ThemeProvider initialTheme={initialTheme}>
          <SiteHeader />
          <div className="site-content">
            <div className="site-notifications" aria-live="polite" />
            {children}
          </div>
          <SiteFooter />
        </ThemeProvider>
      </body>
    </html>
  );
}
