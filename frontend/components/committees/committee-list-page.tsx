import type { CommitteeListItemPayload, CommitteeListPayload } from "../../lib/op-api";
import type { KnowledgeChunk } from "../../lib/rag";
import { fetchKnowledgePreview } from "../../lib/rag";
import { EmptyState } from "../common/empty-state";
import { toTrueCivicUrl } from "../../lib/op-links";
import { KnowledgeInsightsSection } from "../common/knowledge-insights";

interface CommitteeListPageProps {
  payload: CommitteeListPayload;
}

interface CommitteeEntry {
  committee: CommitteeListItemPayload;
  chunks: KnowledgeChunk[];
}

async function loadCommitteeEntries(items: CommitteeListItemPayload[]): Promise<CommitteeEntry[]> {
  const tasks = items.map(async (committee) => ({
    committee,
    chunks: await fetchKnowledgePreview(committee.rag_scope, 1),
  }));
  return Promise.all(tasks);
}

export async function CommitteeListPage({ payload }: CommitteeListPageProps) {
  const entries = await loadCommitteeEntries(payload.items);
  return (
    <main className="site-main">
      <section className="home-section">
        <div className="layout-row">
          <div className="layout-context">
            <h1>Parliamentary committees</h1>
            <p>Watch committee activity and jump to the latest meeting notes on truecivic.ca.</p>
          </div>
          <div className="layout-primary">
            <CommitteeList entries={entries} />
          </div>
        </div>
      </section>
    </main>
  );
}

function CommitteeList({ entries }: { entries: CommitteeEntry[] }) {
  if (!entries.length) {
    return <EmptyState message="No committees are available right now." />;
  }
  return (
    <ul>
      {entries.map(({ committee, chunks }) => (
        <li key={committee.url}>
          <a href={toTrueCivicUrl(committee.url)} target="_blank" rel="noreferrer">
            {committee.name}
          </a>
          <div>
            {committee.latest_session ? `Session: ${committee.latest_session.name}` : "Session timing TBD"}
          </div>
          {committee.latest_meeting ? (
            <div>
              {committee.latest_meeting.url ? (
                <a
                  href={toTrueCivicUrl(committee.latest_meeting.url)}
                  target="_blank"
                  rel="noreferrer"
                >
                  Latest meeting #{committee.latest_meeting.number} on {committee.latest_meeting.date}
                </a>
              ) : (
                <>Latest meeting #{committee.latest_meeting.number} on {committee.latest_meeting.date}</>
              )}
            </div>
          ) : null}
          <KnowledgeInsightsSection
            title="Knowledge base insight"
            chunks={chunks}
            emptyMessage="No knowledge base summaries are available for this committee."
            showWhenEmpty={false}
          />
        </li>
      ))}
    </ul>
  );
}
