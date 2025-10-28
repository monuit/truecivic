"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";

import { ThemeToggle } from "../common/theme-toggle";

// MARK: Types
interface SiteHeaderProps {
  searchAction?: string;
  searchPlaceholder?: string;
}

interface NavLink {
  label: string;
  href: string;
}

// MARK: Constants
const NAV_LINKS: NavLink[] = [
  { label: "MPs", href: "/politicians" },
  { label: "Bills", href: "/bills" },
  { label: "Debates", href: "/debates" },
  { label: "Committees", href: "/committees" },
  { label: "Votes", href: "/votes" },
  { label: "Alerts", href: "/alerts" },
  { label: "About", href: "/about" },
  { label: "Labs", href: "/labs" },
];

// MARK: Component
export function SiteHeader({ searchAction = "/search", searchPlaceholder }: SiteHeaderProps) {
  const [searchVisible, setSearchVisible] = useState(false);

  const closeSearch = useCallback(() => setSearchVisible(false), []);
  const toggleSearch = useCallback(() => setSearchVisible((current) => !current), []);

  useEffect(() => {
    if (!searchVisible) {
      return undefined;
    }
    function handleEscape(event: KeyboardEvent) {
      if (event.key === "Escape") {
        closeSearch();
      }
    }
    window.addEventListener("keydown", handleEscape);
    return () => window.removeEventListener("keydown", handleEscape);
  }, [closeSearch, searchVisible]);

  return (
    <header className="site-header" data-search-visible={searchVisible}>
      <div className="site-header__bar">
        <div className="site-header__logo">
          <Link href="/" className="site-header__logotype">
            truecivic
          </Link>
        </div>
        <nav className="site-header__menu" aria-label="Primary navigation">
          <ul>
            {NAV_LINKS.map((link) => (
              <li key={link.href}>
                <Link href={link.href}>{link.label}</Link>
              </li>
            ))}
          </ul>
        </nav>
        <div className="site-header__actions">
          <ThemeToggle />
          <button
            type="button"
            className="site-header__search-toggle"
            onClick={toggleSearch}
            aria-expanded={searchVisible}
            aria-controls="global-search-panel"
          >
            <span>Search</span>
            <svg aria-hidden="true" width="16" height="16" viewBox="0 0 16 16">
              <path d="M7 0a7 7 0 0 1 5.52 11.33l3.08 3.07-1.41 1.42-3.08-3.08A7 7 0 1 1 7 0Zm0 2a5 5 0 1 0 0 10 5 5 0 0 0 0-10Z" />
            </svg>
          </button>
        </div>
      </div>
      <div className="site-header__search" id="global-search-panel">
        <div className="site-header__search-inner">
          <form action={searchAction} method="get" className="site-header__search-form">
            <label htmlFor="global-search-input" className="visually-hidden">
              Search truecivic
            </label>
            <input
              id="global-search-input"
              name="q"
              type="search"
              placeholder={searchPlaceholder || "Enter a word, name, or postal code"}
              autoComplete="off"
            />
            <button type="submit">Search</button>
            <button type="button" className="site-header__search-close" onClick={closeSearch}>
              Close
            </button>
          </form>
        </div>
      </div>
    </header>
  );
}
