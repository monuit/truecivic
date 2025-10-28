import type { DebateListItemPayload, DebateListPayload } from "../../lib/op-api";
import type { KnowledgeChunk } from "../../lib/rag";
import { fetchKnowledgePreview } from "../../lib/rag";
import { EmptyState } from "../common/empty-state";
import { toTrueCivicUrl } from "../../lib/op-links";
import { KnowledgeInsightsSection } from "../common/knowledge-insights";

interface DebateListPageProps {
  payload: DebateListPayload;
}

interface DebateEntry {
  debate: DebateListItemPayload;
  chunks: KnowledgeChunk[];
}

async function loadDebateEntries(items: DebateListItemPayload[]): Promise<DebateEntry[]> {
  const tasks = items.map(async (debate) => ({
    debate,
    chunks: await fetchKnowledgePreview(debate.rag_scope, 1),
  }));
  return Promise.all(tasks);
}

export async function DebateListPage({ payload }: DebateListPageProps) {
  const entries = await loadDebateEntries(payload.items);
  return (
    <main className="site-main">
      <section className="home-section">
        <div className="layout-row">
          <div className="layout-context">
            <h1>Recent debates</h1>
            <p>Catch up on the latest Hansard debates and highlights from the House of Commons.</p>
          </div>
          <div className="layout-primary">
            <DebateList entries={entries} />
          </div>
        </div>
      </section>
    </main>
  );
}

function DebateList({ entries }: { entries: DebateEntry[] }) {
  if (!entries.length) {
    return <EmptyState message="No debates found." />;
  }
  return (
    <ul>
      {entries.map(({ debate, chunks }) => (
        <li key={debate.url}>
          <a href={toTrueCivicUrl(debate.url)} target="_blank" rel="noreferrer">
            {debate.headline}
          </a>
          <div>
            {formatDate(debate.date)} · Session {debate.session.name}
            {debate.most_frequent_word ? ` · Top word: ${debate.most_frequent_word}` : ""}
          </div>
          <KnowledgeInsightsSection
            title="Knowledge base insight"
            chunks={chunks}
            emptyMessage="No knowledge summaries are available for this debate."
            showWhenEmpty={false}
          />
        </li>
      ))}
    </ul>
  );
}

function formatDate(date: string | null): string {
  if (!date) {
    return "Date TBD";
  }
  const parsed = new Date(date);
  if (Number.isNaN(parsed.getTime())) {
    return date;
  }
  return parsed.toLocaleDateString("en-CA", { year: "numeric", month: "long", day: "numeric" });
}
