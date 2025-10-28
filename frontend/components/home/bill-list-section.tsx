import Link from "next/link";
import type { BillReference } from "../../lib/op-api";

// MARK: Component
interface BillListSectionProps {
  bills: BillReference[];
}

export function BillListSection({ bills }: BillListSectionProps) {
  if (!bills.length) {
    return null;
  }
  return (
    <section className="home-section">
      <div className="layout-row">
        <div className="layout-context">
          <h2>Recently debated bills</h2>
        </div>
        <div className="layout-primary">
          <ul className="tile-grid">
            {bills.map((bill) => (
              <li key={`${bill.session.id}-${bill.number}`}>
                <Link href={bill.url}>
                  <span className="tile-grid__heading">{bill.number}</span>
                  <span className="tile-grid__body">{bill.short_title || bill.title}</span>
                </Link>
              </li>
            ))}
          </ul>
        </div>
      </div>
    </section>
  );
}
