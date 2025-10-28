"use client";

import { useEffect, useId, useState } from "react";

import { type ThemeSetting, useTheme } from "../../lib/theme/theme-provider";

const OPTIONS: Array<{ value: ThemeSetting; label: string }> = [
  { value: "light", label: "Light" },
  { value: "dark", label: "Dark" },
  { value: "system", label: "System" },
];

export function ThemeToggle() {
  const { theme, resolvedTheme, setTheme } = useTheme();
  const controlId = useId();
  const [isOpen, setIsOpen] = useState(false);
  const [isMounted, setIsMounted] = useState(false);

  useEffect(() => {
    setIsMounted(true);
  }, []);

  useEffect(() => {
    if (!isOpen) {
      return;
    }
    const close = (event: MouseEvent | KeyboardEvent) => {
      if (event instanceof KeyboardEvent && event.key !== "Escape") {
        return;
      }
      setIsOpen(false);
    };
    window.addEventListener("keydown", close);
    window.addEventListener("click", close);
    return () => {
      window.removeEventListener("keydown", close);
      window.removeEventListener("click", close);
    };
  }, [isOpen]);

  const formatThemeLabel = (value: ThemeSetting): string => {
    switch (value) {
      case "light":
        return "Light";
      case "dark":
        return "Dark";
      default:
        return "System";
    }
  };

  // Delay resolved theme label until after hydration to avoid server/client mismatch.
  const activeTheme =
    theme === "system"
      ? isMounted
        ? `System (${formatThemeLabel(resolvedTheme)})`
        : "System"
      : formatThemeLabel(theme);

  return (
    <div className="theme-toggle" data-state={isOpen ? "open" : "closed"}>
      <button
        type="button"
        aria-haspopup="listbox"
        aria-expanded={isOpen}
        aria-controls={controlId}
        onClick={(event) => {
          event.stopPropagation();
          setIsOpen((current) => !current);
        }}
      >
        <span className="theme-toggle__label">Theme</span>
        <span className="theme-toggle__value">{activeTheme}</span>
        <svg aria-hidden="true" width="12" height="12" viewBox="0 0 12 12">
          <path
            d="M2.47 4.22a.75.75 0 0 1 1.06 0L6 6.69l2.47-2.47a.75.75 0 1 1 1.06 1.06l-3 3a.75.75 0 0 1-1.06 0l-3-3a.75.75 0 0 1 0-1.06Z"
            fill="currentColor"
          />
        </svg>
      </button>
      {isOpen ? (
        <ul
          id={controlId}
          role="listbox"
          tabIndex={-1}
          className="theme-toggle__menu"
          onClick={(event) => event.stopPropagation()}
        >
          {OPTIONS.map((option) => (
            <li key={option.value} role="option" aria-selected={theme === option.value}>
              <button
                type="button"
                onClick={() => {
                  setTheme(option.value);
                  setIsOpen(false);
                }}
              >
                <span>{option.label}</span>
                {theme === option.value ? (
                  <svg aria-hidden="true" width="12" height="12" viewBox="0 0 12 12">
                    <path
                      d="M4.97 8.47 2.72 6.22a.75.75 0 0 1 1.06-1.06l1.69 1.69 2.75-2.75a.75.75 0 0 1 1.06 1.06l-3.28 3.28a.75.75 0 0 1-1.06 0Z"
                      fill="currentColor"
                    />
                  </svg>
                ) : null}
              </button>
            </li>
          ))}
        </ul>
      ) : null}
    </div>
  );
}
