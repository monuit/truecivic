import Link from "next/link";
import type { VoteSummary } from "../../lib/op-api";

// MARK: Component
interface VoteGridSectionProps {
  votes: VoteSummary[];
}

export function VoteGridSection({ votes }: VoteGridSectionProps) {
  if (!votes.length) {
    return null;
  }
  return (
    <section className="home-section">
      <div className="layout-row">
        <div className="layout-context">
          <h2>Recent votes</h2>
        </div>
        <div className="layout-primary">
          <ul className="tile-grid">
            {votes.map((vote) => (
              <li key={vote.number}>
                <Link href={vote.url}>
                  <span className="tile-grid__heading">#{vote.number}</span>
                  <span className={`vote-tag vote-tag--${vote.result_code.toLowerCase()}`}>
                    {vote.result}
                  </span>
                  <span className="tile-grid__body">
                    {vote.bill_number ? `Bill ${vote.bill_number}: ` : ""}
                    {vote.description}
                  </span>
                </Link>
              </li>
            ))}
          </ul>
        </div>
      </div>
    </section>
  );
}
