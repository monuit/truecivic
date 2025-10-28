import Link from "next/link";

import type { VoteListPayload, VoteListItemPayload, VoteListFiltersPayload } from "../../lib/op-api";
import type { KnowledgeChunk } from "../../lib/rag";
import { fetchKnowledgePreview } from "../../lib/rag";
import { EmptyState } from "../common/empty-state";
import { KnowledgeInsightsSection } from "../common/knowledge-insights";

interface VoteListPageProps {
  payload: VoteListPayload;
}

interface VoteEntry {
  vote: VoteListItemPayload;
  chunks: KnowledgeChunk[];
}

async function loadVoteEntries(items: VoteListItemPayload[]): Promise<VoteEntry[]> {
  const tasks = items.map(async (vote) => ({
    vote,
    chunks: await fetchKnowledgePreview(vote.rag_scope, 1),
  }));
  return Promise.all(tasks);
}

export async function VoteListPage({ payload }: VoteListPageProps) {
  const entries = await loadVoteEntries(payload.items);
  const { filters } = payload;
  return (
    <main className="site-main">
      <section className="home-section">
        <div className="layout-row">
          <div className="layout-context">
            <h1>Votes</h1>
            <p>Recorded divisions in the House of Commons, grouped by parliamentary session.</p>
            <VoteSessionFilter filters={filters} />
          </div>
          <div className="layout-primary">
            <VoteList entries={entries} />
          </div>
        </div>
      </section>
    </main>
  );
}

function VoteSessionFilter({ filters }: { filters: VoteListFiltersPayload }) {
  if (!filters.sessions.length) {
    return null;
  }
  const options = [
    { id: "__all__", label: "All sessions", href: "/votes", isActive: !filters.selected_session },
    ...filters.sessions.map((session) => ({
      id: session.id,
      label: session.label,
      href: `/votes?session=${session.id}`,
      isActive: session.id === filters.selected_session,
    })),
  ];
  return (
    <nav aria-label="Filter votes by session">
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

function VoteList({ entries }: { entries: VoteEntry[] }) {
  if (!entries.length) {
    return <EmptyState message="No votes have been recorded yet." />;
  }
  return (
    <ul className="tile-list">
      {entries.map(({ vote, chunks }) => (
        <li key={`${vote.session.id}-${vote.number}-${vote.date}`}>
          <Link href={normalizePath(vote.url)}>
            <strong>
              Vote {vote.number} · {vote.session.name}
            </strong>
            <span>{vote.description}</span>
            <span className="tile-list__meta">
              {formatDate(vote.date)} · {vote.result} · {vote.yea_total} – {vote.nay_total} ({vote.paired_total} paired)
            </span>
          </Link>
          <KnowledgeInsightsSection
            title="Knowledge base insight"
            chunks={chunks}
            emptyMessage="No knowledge summaries are available for this vote."
            showWhenEmpty={false}
          />
        </li>
      ))}
    </ul>
  );
}

function formatDate(date: string) {
  try {
    return new Intl.DateTimeFormat("en-CA", { dateStyle: "medium" }).format(new Date(date));
  } catch (error) {
    console.warn("Failed to format vote date", date, error);
    return date;
  }
}

function normalizePath(path: string) {
  if (!path) {
    return path;
  }
  try {
    const url = new URL(path, "http://localhost");
    const normalized = url.pathname.replace(/\/+$/, "");
    return normalized || "/";
  } catch (error) {
    console.warn("Failed to normalize vote link", path, error);
    return path;
  }
}
