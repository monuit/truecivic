import Link from "next/link";

import type { PoliticianListItemPayload, PoliticianListPayload } from "../../lib/op-api";
import type { KnowledgeChunk } from "../../lib/rag";
import { fetchKnowledgePreview } from "../../lib/rag";
import { EmptyState } from "../common/empty-state";
import { toTrueCivicUrl } from "../../lib/op-links";
import { KnowledgeInsightsSection } from "../common/knowledge-insights";

interface PoliticianListPageProps {
  payload: PoliticianListPayload;
  status: "current" | "former";
}

interface PoliticianEntry {
  member: PoliticianListItemPayload;
  chunks: KnowledgeChunk[];
}

async function loadPoliticianEntries(items: PoliticianListItemPayload[]): Promise<PoliticianEntry[]> {
  const tasks = items.map(async (member) => ({
    member,
    chunks: await fetchKnowledgePreview(member.rag_scope, 1),
  }));
  return Promise.all(tasks);
}

export async function PoliticianListPage({ payload, status }: PoliticianListPageProps) {
  const entries = await loadPoliticianEntries(payload.items);
  return (
    <main className="site-main">
      <section className="home-section">
        <div className="layout-row">
          <div className="layout-context">
            <h1>Members of Parliament</h1>
            <p>Review the roster of MPs and jump directly to their profiles on truecivic.ca.</p>
            <PoliticianStatusFilter status={status} />
          </div>
          <div className="layout-primary">
            <PoliticianList entries={entries} />
          </div>
        </div>
      </section>
    </main>
  );
}

function PoliticianStatusFilter({ status }: { status: "current" | "former" }) {
  const options: Array<{ label: string; value: "current" | "former" }> = [
    { label: "Current MPs", value: "current" },
    { label: "Former MPs", value: "former" },
  ];
  return (
    <nav aria-label="Filter politicians by status">
      <ul>
        {options.map((option) => (
          <li key={option.value}>
            <Link
              href={option.value === "current" ? "/politicians" : `/politicians?status=${option.value}`}
              aria-current={status === option.value ? "page" : undefined}
            >
              {option.label}
            </Link>
          </li>
        ))}
      </ul>
    </nav>
  );
}

function PoliticianList({ entries }: { entries: PoliticianEntry[] }) {
  if (!entries.length) {
    return <EmptyState message="No politicians matched this filter." />;
  }
  return (
    <ul>
      {entries.map(({ member, chunks }) => (
        <li key={member.url}>
          <a href={toTrueCivicUrl(member.url)} target="_blank" rel="noreferrer">
            {member.name}
          </a>
          <div>
            {formatParty(member)}
            {member.riding ? ` — ${member.riding}` : ""}
            {member.province ? ` (${member.province})` : ""}
          </div>
          <KnowledgeInsightsSection
            title="Knowledge base insight"
            chunks={chunks}
            emptyMessage="No knowledge summaries are available for this member."
            showWhenEmpty={false}
          />
        </li>
      ))}
    </ul>
  );
}

function formatParty(member: PoliticianListItemPayload): string {
  if (member.party_short) {
    return member.party_short;
  }
  if (member.party) {
    return member.party;
  }
  return "Independent";
}
