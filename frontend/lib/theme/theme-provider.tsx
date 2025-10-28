"use client";

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";

type ColorTheme = "light" | "dark";
export type ThemeSetting = ColorTheme | "system";

interface ThemeContextValue {
  theme: ThemeSetting;
  resolvedTheme: ColorTheme;
  setTheme: (theme: ThemeSetting) => void;
  toggleTheme: () => void;
}

const STORAGE_KEY = "truecivic-theme";
const COOKIE_KEY = "truecivic-theme";

const ThemeContext = createContext<ThemeContextValue | undefined>(undefined);

function resolveTheme(setting: ThemeSetting, mediaQuery: MediaQueryList | null): ColorTheme {
  if (setting === "system") {
    return mediaQuery && mediaQuery.matches ? "dark" : "light";
  }
  return setting;
}

function applyDocumentTheme(theme: ColorTheme) {
  if (typeof document === "undefined") {
    return;
  }
  document.documentElement.dataset.theme = theme;
  document.documentElement.style.colorScheme = theme;
}

function persistTheme(theme: ThemeSetting) {
  try {
    localStorage.setItem(STORAGE_KEY, theme);
  } catch (error) {
    if (process.env.NODE_ENV !== "production") {
      // eslint-disable-next-line no-console -- surfaced during development only
      console.warn("Unable to persist theme to localStorage", error);
    }
  }
  const maxAgeSeconds = 60 * 60 * 24 * 365;
  document.cookie = `${COOKIE_KEY}=${theme}; path=/; max-age=${maxAgeSeconds}; SameSite=Lax`;
}

function readStoredTheme(): ThemeSetting | null {
  try {
    const stored = localStorage.getItem(STORAGE_KEY);
    if (!stored) {
      return null;
    }
    if (stored === "light" || stored === "dark" || stored === "system") {
      return stored;
    }
  } catch (error) {
    if (process.env.NODE_ENV !== "production") {
      // eslint-disable-next-line no-console -- surfaced during development only
      console.warn("Unable to read theme from localStorage", error);
    }
  }
  return null;
}

export interface ThemeProviderProps {
  children: React.ReactNode;
  initialTheme?: ThemeSetting;
}

export function ThemeProvider({ children, initialTheme = "system" }: ThemeProviderProps) {
  const mediaQueryRef = useRef<MediaQueryList | null>(null);
  const [theme, setThemeState] = useState<ThemeSetting>(initialTheme);
  const [resolvedTheme, setResolvedTheme] = useState<ColorTheme>(() => {
    if (typeof window === "undefined") {
      return initialTheme === "dark" ? "dark" : "light";
    }
    const mediaQuery = window.matchMedia("(prefers-color-scheme: dark)");
    return resolveTheme(initialTheme, mediaQuery);
  });

  useEffect(() => {
    if (typeof window === "undefined") {
      return;
    }
    mediaQueryRef.current = window.matchMedia("(prefers-color-scheme: dark)");
    const stored = readStoredTheme();
    if (stored) {
      setThemeState(stored);
    }
  }, []);

  useEffect(() => {
    const mediaQuery = mediaQueryRef.current;

    const update = () => {
      const resolved = resolveTheme(theme, mediaQuery);
      setResolvedTheme(resolved);
      applyDocumentTheme(resolved);
    };

    update();

    if (theme === "system" && mediaQuery) {
      mediaQuery.addEventListener("change", update);
      return () => mediaQuery.removeEventListener("change", update);
    }

    return undefined;
  }, [theme]);

  const setTheme = useCallback((value: ThemeSetting) => {
    setThemeState(value);
    persistTheme(value);
  }, []);

  const toggleTheme = useCallback(() => {
    const next: ColorTheme = resolvedTheme === "dark" ? "light" : "dark";
    setTheme(next);
  }, [resolvedTheme, setTheme]);

  const contextValue = useMemo<ThemeContextValue>(
    () => ({
      theme,
      resolvedTheme,
      setTheme,
      toggleTheme,
    }),
    [theme, resolvedTheme, setTheme, toggleTheme],
  );

  return <ThemeContext.Provider value={contextValue}>{children}</ThemeContext.Provider>;
}

export function useTheme(): ThemeContextValue {
  const value = useContext(ThemeContext);
  if (!value) {
    throw new Error("useTheme must be used within a ThemeProvider");
  }
  return value;
}

export function ThemeScript({ initialTheme = "system" }: { initialTheme?: ThemeSetting }) {
  const script = `(() => {
  const STORAGE_KEY = '${STORAGE_KEY}';
  const COOKIE_KEY = '${COOKIE_KEY}';
  const getCookieTheme = () => {
    const match = document.cookie.match(new RegExp('(?:^|; )' + COOKIE_KEY + '=([^;]*)'));
    return match ? decodeURIComponent(match[1]) : null;
  };
  const getStoredTheme = () => {
    try {
      const value = localStorage.getItem(STORAGE_KEY);
      if (value === 'light' || value === 'dark' || value === 'system') {
        return value;
      }
    } catch (error) {}
    return null;
  };
  const prefersDark = () => window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches;
  let theme = getStoredTheme() || getCookieTheme() || '${initialTheme}';
  if (theme === 'system') {
    theme = prefersDark() ? 'dark' : 'light';
  }
  if (theme !== 'light' && theme !== 'dark') {
    theme = 'light';
  }
  document.documentElement.dataset.theme = theme;
  document.documentElement.style.colorScheme = theme;
})();`;

  return <script suppressHydrationWarning dangerouslySetInnerHTML={{ __html: script }} />;
}
