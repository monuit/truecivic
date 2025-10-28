import Link from "next/link";

import type { BillListFiltersPayload, BillListItemPayload, BillListPayload } from "../../lib/op-api";
import { EmptyState } from "../common/empty-state";

interface BillListPageProps {
  payload: BillListPayload;
}

export function BillListPage({ payload }: BillListPageProps) {
  const { filters, items } = payload;
  return (
    <main className="site-main">
      <section className="home-section">
        <div className="layout-row">
          <div className="layout-context">
            <h1>Bills before Parliament</h1>
            <p>Browse recent federal legislation and explore the full text on truecivic.ca.</p>
            <BillSessionFilter filters={filters} />
          </div>
          <div className="layout-primary">
            <BillList items={items} />
          </div>
        </div>
      </section>
    </main>
  );
}

function BillSessionFilter({ filters }: { filters: BillListFiltersPayload }) {
  if (!filters.sessions.length) {
    return null;
  }
  const options = [
    {
      id: "__all__",
      label: "All sessions",
      href: "/bills",
      isActive: !filters.selected_session,
    },
    ...filters.sessions.map((session) => ({
      id: session.id,
      label: session.label,
      href: `/bills?session=${session.id}`,
      isActive: session.id === filters.selected_session,
    })),
  ];
  return (
    <nav aria-label="Filter bills by session">
      <ul>
        {options.map((option) => (
          <li key={option.id}>
            <Link href={option.href} aria-current={option.isActive ? "page" : undefined}>
              {option.label}
            </Link>
          </li>
        ))}
      </ul>
    </nav>
  );
}

function BillList({ items }: { items: BillListItemPayload[] }) {
  if (!items.length) {
    return <EmptyState message="No bills are available right now." />;
  }
  return (
    <ul className="tile-grid">
      {items.map((bill) => (
        <li key={`${bill.session.id}-${bill.number}`}>
          <Link href={normalizePath(bill.url)}>
            <span className="tile-grid__heading">{bill.number}</span>
            <span className="tile-grid__body">
              {bill.short_title || bill.title}
              {bill.status ? ` · ${bill.status}` : ""}
            </span>
          </Link>
        </li>
      ))}
    </ul>
  );
}

function normalizePath(path: string) {
  if (!path) {
    return path;
  }
  const trimmed = path.trim();
  if (!trimmed) {
    return trimmed;
  }
  try {
    const url = new URL(trimmed, "http://localhost");
    const normalized = url.pathname.replace(/\/+$/, "");
    return normalized || "/";
  } catch (error) {
    console.warn("Failed to normalize bill link", path, error);
    return trimmed;
  }
}
