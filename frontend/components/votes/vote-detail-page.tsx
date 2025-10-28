import Link from "next/link";

import type {
  MemberBallotPayload,
  VoteDetailPayload,
  VoteDetailDataPayload,
} from "../../lib/op-api";
import type { KnowledgeChunk } from "../../lib/rag";
import { KnowledgeInsightsSection } from "../common/knowledge-insights";

interface VoteDetailPageProps {
  payload: VoteDetailPayload;
  knowledgeChunks: KnowledgeChunk[];
}

export function VoteDetailPage({ payload, knowledgeChunks }: VoteDetailPageProps) {
  const { vote, party_breakdown: partyBreakdown, ballots } = payload;
  const groupedBallots = groupBallots(ballots);
  const hasBallots = ballots.length > 0;

  return (
    <main className="site-main">
      <article className="vote-detail">
        <header className="vote-detail__header">
          <div>
            <span className="vote-detail__session">{vote.session.name}</span>
            <h1>
              Vote {vote.number}
              <span className="vote-detail__result">{vote.result}</span>
            </h1>
            <p className="vote-detail__meta">
              {formatDate(vote.date)} · Yes {vote.yea_total ?? 0} · No {vote.nay_total ?? 0}
              {vote.paired_total ? ` · Paired ${vote.paired_total}` : ""}
            </p>
          </div>
          <div className="vote-detail__totals">
            <Stat label="Yes" value={vote.yea_total} accent="yes" />
            <Stat label="No" value={vote.nay_total} accent="no" />
            <Stat label="Paired" value={vote.paired_total} />
          </div>
        </header>

        <section className="vote-detail__summary">
          <h2>Description</h2>
          <p>{vote.description || "No description available for this vote."}</p>
          <VoteLinks vote={vote} />
        </section>

        <KnowledgeInsightsSection
          title="Knowledge base insights"
          chunks={knowledgeChunks}
          emptyMessage="No knowledge base summaries are available for this vote yet."
          showWhenEmpty
          className="vote-detail__section"
        />

        <section className="vote-detail__parties">
          <h2>Party breakdown</h2>
          {partyBreakdown.length ? (
            <ul>
              {partyBreakdown.map((entry) => (
                <li key={entry.party_name}>
                  <span className="vote-detail__party-name">{entry.party_short || entry.party_name}</span>
                  <span className={`vote-detail__party-vote vote-detail__party-vote--${voteClass(entry.vote_code)}`}>
                    {entry.vote}
                  </span>
                  {entry.disagreement ? (
                    <span className="vote-detail__party-disagreement">
                      {Math.round(entry.disagreement * 100)}% dissent
                    </span>
                  ) : null}
                </li>
              ))}
            </ul>
          ) : (
            <p className="vote-detail__empty">No party-level data is available.</p>
          )}
        </section>

        <section className="vote-detail__ballots">
          <h2>Ballots</h2>
          {hasBallots ? (
            groupedBallots.map(([code, members]) => (
              <div key={code} className="vote-detail__ballot-group">
                <h3>{ballotLabel(code)}</h3>
                <ul>
                  {members.map((member) => (
                    <li key={`${member.politician_name}-${member.party}-${member.riding}`}>
                      <div className="vote-detail__ballot-name">
                        {member.politician_url ? (
                          <Link href={normalizePath(member.politician_url)}>{member.politician_name}</Link>
                        ) : (
                          member.politician_name
                        )}
                        {member.party ? <span>{member.party}</span> : null}
                        {member.riding ? <span>{member.riding}</span> : null}
                      </div>
                      {member.dissent ? <span className="vote-detail__badge">Dissent</span> : null}
                    </li>
                  ))}
                </ul>
              </div>
            ))
          ) : (
            <p className="vote-detail__empty">Ballot information is not available for this vote.</p>
          )}
        </section>
      </article>
    </main>
  );
}

function voteClass(code: string) {
  if (code === "Y") return "yes";
  if (code === "N") return "no";
  if (code === "P") return "paired";
  return "abstain";
}

function groupBallots(ballots: MemberBallotPayload[]): Array<[string, MemberBallotPayload[]]> {
  const grouped = new Map<string, MemberBallotPayload[]>();
  for (const ballot of ballots) {
    const key = ballot.vote_code || "?";
    const list = grouped.get(key) ?? [];
    list.push(ballot);
    grouped.set(key, list);
  }
  const priority = ["Y", "N", "P", "A"];
  return Array.from(grouped.entries()).sort((a, b) => {
    const indexA = priority.indexOf(a[0]);
    const indexB = priority.indexOf(b[0]);
    const resolvedA = indexA === -1 ? priority.length : indexA;
    const resolvedB = indexB === -1 ? priority.length : indexB;
    return resolvedA - resolvedB;
  });
}

function ballotLabel(code: string): string {
  switch (code) {
    case "Y":
      return "Yes";
    case "N":
      return "No";
    case "P":
      return "Paired";
    case "A":
      return "Did not vote";
    default:
      return "Other";
  }
}

function VoteLinks({ vote }: { vote: VoteDetailDataPayload }) {
  const links: Array<{ label: string; href: string }> = [];
  if (vote.bill) {
    links.push({ label: `Related bill: ${vote.bill.number}`, href: normalizePath(vote.bill.url) });
  }
  if (vote.context_statement_url) {
    links.push({ label: "View Hansard context", href: normalizePath(vote.context_statement_url) });
  }
  if (!links.length) {
    return null;
  }
  return (
    <ul className="vote-detail__links">
      {links.map((link) => (
        <li key={link.href}>
          <Link href={link.href}>{link.label}</Link>
        </li>
      ))}
    </ul>
  );
}

interface StatProps {
  label: string;
  value: number | null | undefined;
  accent?: "yes" | "no" | "neutral";
}

function Stat({ label, value, accent }: StatProps) {
  return (
    <div className={`vote-detail__stat vote-detail__stat--${accent || "neutral"}`}>
      <span className="vote-detail__stat-label">{label}</span>
      <span className="vote-detail__stat-value">{value ?? 0}</span>
    </div>
  );
}

function formatDate(date: string) {
  try {
    return new Intl.DateTimeFormat("en-CA", { dateStyle: "long" }).format(new Date(date));
  } catch (error) {
    console.warn("Failed to format vote date", date, error);
    return date;
  }
}

function normalizePath(path: string | null | undefined): string {
  if (!path) {
    return "/";
  }
  try {
    const url = new URL(path, "http://localhost");
    const normalized = url.pathname.replace(/\/+$/, "");
    return normalized || "/";
  } catch (error) {
    console.warn("Failed to normalize path", path, error);
    return path;
  }
}
