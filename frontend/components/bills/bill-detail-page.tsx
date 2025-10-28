import clsx from "clsx";
import Link from "next/link";
import type { ReactNode } from "react";

import type {
  BillDetailDataPayload,
  BillDetailPayload,
  BillReference,
  BillDebatePayload,
  CommitteeMeetingPayload,
  StatementListingPayload,
  VoteSummary,
} from "../../lib/op-api";
import type { KnowledgeChunk } from "../../lib/rag";
import { KnowledgeInsightsSection } from "../common/knowledge-insights";

interface BillDetailPageProps {
  basePath: string;
  payload: BillDetailPayload;
  knowledgeChunks: KnowledgeChunk[];
}

export function BillDetailPage({ basePath, payload, knowledgeChunks }: BillDetailPageProps) {
  const { bill, debate, votes, committee_meetings: meetings, similar_bills: similar, same_number_bills: sameNumber } =
    payload;

  return (
    <main className="site-main">
      <article className="bill-detail">
        <section className="bill-detail__intro">
          <div className="layout-row">
            <header className="bill-detail__header layout-primary">
              <span className="bill-detail__session">{bill.session.name}</span>
              <h1 className="bill-detail__title">
                <span className="bill-detail__number">{bill.number}</span>
                {bill.title}
              </h1>
              <div className="bill-detail__status-row">
                {bill.status ? <StatusBadge isLaw={bill.is_law}>{bill.status}</StatusBadge> : null}
                {bill.status_date ? <span className="bill-detail__status-date">Updated {formatDate(bill.status_date)}</span> : null}
                {bill.is_private_members_bill ? <span className="bill-detail__tag">Private member&apos;s bill</span> : null}
                {bill.chamber ? <span className="bill-detail__tag">{bill.chamber}</span> : null}
              </div>
            </header>
            <aside className="bill-detail__meta layout-secondary">
              <BillMetadata bill={bill} />
            </aside>
          </div>
        </section>

        <section className="bill-detail__body">
          <div className="layout-row">
            <div className="layout-primary">
              <BillSummary bill={bill} />
              <BillKnowledgeSection chunks={knowledgeChunks} />
              <BillDebateSection basePath={basePath} debate={debate} />
              <BillVotesSection votes={votes} />
              <BillCommitteeSection meetings={meetings} />
            </div>
            <aside className="layout-secondary bill-detail__related">
              <BillRelatedSection similar={similar} sameNumber={sameNumber} />
            </aside>
          </div>
        </section>
      </article>
    </main>
  );
}

// MARK: Intro metadata

interface StatusBadgeProps {
  isLaw: boolean;
  children: string;
}

function StatusBadge({ isLaw, children }: StatusBadgeProps) {
  return <span className={clsx("bill-detail__status", isLaw && "bill-detail__status--law")}>{children}</span>;
}

function BillMetadata({ bill }: { bill: BillDetailDataPayload }) {
  const items: Array<{ label: string; value: ReactNode }> = [];
  if (bill.sponsor_name) {
    items.push({
      label: "Sponsor",
      value: bill.sponsor_url ? (
        <Link href={normalizePath(bill.sponsor_url)}>{bill.sponsor_name}</Link>
      ) : (
        bill.sponsor_name
      ),
    });
  }
  if (bill.sponsor_party) {
    items.push({ label: "Party", value: bill.sponsor_party });
  }
  if (bill.sponsor_riding) {
    items.push({ label: "Riding", value: bill.sponsor_riding });
  }
  if (bill.has_library_summary && bill.library_summary_url) {
    items.push({
      label: "Library of Parliament",
      value: (
        <a href={bill.library_summary_url} target="_blank" rel="noreferrer">
          Read summary (opens in new tab)
        </a>
      ),
    });
  }
  items.push({ label: "Session", value: bill.session.name });

  return (
    <div className="bill-detail__meta-list">
      <h2>Bill details</h2>
      <dl>
        {items.map((item) => (
          <div key={item.label} className="bill-detail__meta-item">
            <dt>{item.label}</dt>
            <dd>{item.value}</dd>
          </div>
        ))}
      </dl>
    </div>
  );
}

// MARK: Summary

function BillSummary({ bill }: { bill: BillDetailDataPayload }) {
  return (
    <section className="bill-detail__section bill-detail__summary">
      <h2>Summary</h2>
      {bill.summary_html ? (
        <div className="bill-detail__summary-html" dangerouslySetInnerHTML={{ __html: bill.summary_html }} />
      ) : (
        <p>This bill does not yet have an official summary.</p>
      )}
    </section>
  );
}

// MARK: Knowledge insights

export function BillKnowledgeSection({ chunks }: { chunks: KnowledgeChunk[] }) {
  return (
    <KnowledgeInsightsSection
      title="Knowledge base insights"
      chunks={chunks}
      emptyMessage="No knowledge base context is available for this bill yet."
      showWhenEmpty
      className="bill-detail__section"
      entriesClassName="bill-detail__insights"
      entryClassName="bill-detail__insight"
      updatedClassName="bill-detail__insight-updated"
      contentClassName="bill-detail__insight-text"
      titleTag="h2"
    />
  );
}

// MARK: Debate

interface BillDebateSectionProps {
  basePath: string;
  debate: BillDebatePayload;
}

function BillDebateSection({ basePath, debate }: BillDebateSectionProps) {
  const tabs = debate.tabs.filter((tab) => tab.has_content);
  if (!tabs.length) {
    return null;
  }
  const activeTab = debate.active_tab ?? debate.default_tab ?? tabs[0]?.key;
  const statementListing = debate.statements;

  return (
    <section className="bill-detail__section">
      <div className="bill-detail__section-header">
        <div>
          <h2>Debate history</h2>
          <p className="bill-detail__section-lede">
            Explore statements and committee meetings associated with this bill. Use the tabs below to switch between
            debate stages.
          </p>
        </div>
        <BillStageSummary stageWordCounts={debate.stage_word_counts} />
      </div>

      <BillDebateTabs basePath={basePath} tabs={tabs} activeTab={activeTab} />

      {activeTab === "meetings" ? (
        <p className="bill-detail__empty">Committee meetings are listed in the sidebar.</p>
      ) : statementListing && statementListing.items.length ? (
        <BillStatementList listing={statementListing} basePath={basePath} activeTab={activeTab} />
      ) : (
        <p className="bill-detail__empty">No debate text is available for this stage yet.</p>
      )}
    </section>
  );
}

interface BillStageSummaryProps {
  stageWordCounts: Record<string, number>;
}

function BillStageSummary({ stageWordCounts }: BillStageSummaryProps) {
  const entries = Object.entries(stageWordCounts);
  if (!entries.length) {
    return null;
  }
  const labels: Record<string, string> = {
    "1": "1st reading",
    "2": "2nd reading",
    "3": "3rd reading",
    report: "Report stage",
    senate: "Senate amendments",
    other: "Other debates",
  };
  return (
    <ul className="bill-detail__stage-summary" aria-label="Bill debate word counts">
      {entries.map(([key, count]) => (
        <li key={key}>
          <span>{labels[key] ?? key}</span>
          <span>{count.toLocaleString()} words</span>
        </li>
      ))}
    </ul>
  );
}

interface BillDebateTabsProps {
  basePath: string;
  tabs: BillDebatePayload["tabs"];
  activeTab: string | null;
}

function BillDebateTabs({ basePath, tabs, activeTab }: BillDebateTabsProps) {
  return (
    <nav className="bill-detail__tabs" aria-label="Bill debate tabs">
      <ul>
        {tabs.map((tab) => {
          const href = buildHref(basePath, tab.key, undefined);
          const isActive = tab.key === activeTab;
          return (
            <li key={tab.key}>
              <Link href={href} aria-current={isActive ? "page" : undefined}>
                {tab.label}
              </Link>
            </li>
          );
        })}
      </ul>
    </nav>
  );
}

interface BillStatementListProps {
  listing: StatementListingPayload;
  basePath: string;
  activeTab: string | null;
}

function BillStatementList({ listing, basePath, activeTab }: BillStatementListProps) {
  return (
    <div className="bill-detail__statements">
      <ol>
        {listing.items.map((item) => (
          <li key={item.slug}>
            <article>
              <header>
                <h3>{item.heading || item.topic || "House debate"}</h3>
                <p className="bill-detail__statement-meta">
                  {item.politician_name ? (
                    <>
                      <span>{item.politician_name}</span>
                      {item.party ? <span>{item.party}</span> : null}
                      {item.riding ? <span>{item.riding}</span> : null}
                    </>
                  ) : (
                    <span>Statement</span>
                  )}
                  {item.time ? <span>{formatDateTime(item.time)}</span> : null}
                </p>
              </header>
              <div className="bill-detail__statement-html" dangerouslySetInnerHTML={{ __html: item.html }} />
              <footer>
                <Link href={item.url}>View in context</Link>
              </footer>
            </article>
          </li>
        ))}
      </ol>
      {listing.pagination ? (
        <Pagination
          basePath={basePath}
          activeTab={activeTab}
          pagination={listing.pagination}
        />
      ) : null}
    </div>
  );
}

// MARK: Votes

function BillVotesSection({ votes }: { votes: VoteSummary[] }) {
  return (
    <section className="bill-detail__section">
      <h2>Votes</h2>
      {votes.length ? (
        <ul className="bill-detail__list">
          {votes.map((vote) => (
            <li key={`${vote.date}-${vote.number}`}>
              <Link href={normalizePath(vote.url)}>
                <span className="bill-detail__list-label">Vote {vote.number}</span>
                <span className="bill-detail__list-body">
                  {vote.description} · {formatDate(vote.date)} · {vote.result}
                </span>
              </Link>
            </li>
          ))}
        </ul>
      ) : (
        <p className="bill-detail__empty">No recorded votes for this bill yet.</p>
      )}
    </section>
  );
}

// MARK: Committees

function BillCommitteeSection({ meetings }: { meetings: CommitteeMeetingPayload[] }) {
  if (!meetings.length) {
    return null;
  }
  return (
    <section className="bill-detail__section">
      <h2>Committee meetings</h2>
      <ul className="bill-detail__list">
        {meetings.map((meeting) => (
          <li key={`${meeting.committee}-${meeting.date}-${meeting.number}`}>
            <Link href={normalizePath(meeting.url)}>
              <span className="bill-detail__list-label">
                {meeting.committee} meeting #{meeting.number}
              </span>
              <span className="bill-detail__list-body">{formatDate(meeting.date)}</span>
            </Link>
          </li>
        ))}
      </ul>
    </section>
  );
}

// MARK: Related bills

interface BillRelatedSectionProps {
  similar: BillReference[];
  sameNumber: BillReference[];
}

function BillRelatedSection({ similar, sameNumber }: BillRelatedSectionProps) {
  if (!similar.length && !sameNumber.length) {
    return (
      <div>
        <h2>Related bills</h2>
        <p className="bill-detail__empty">No related legislation available.</p>
      </div>
    );
  }
  return (
    <div className="bill-detail__related-list">
      <h2>Related bills</h2>
      {similar.length ? (
        <section>
          <h3>Similar bills</h3>
          <ul>
            {similar.map((entry) => (
              <li key={`${entry.session.id}-${entry.number}`}>
                <Link href={normalizePath(entry.url)}>
                  <span>{entry.number}</span>
                  <span>{entry.short_title || entry.title}</span>
                </Link>
              </li>
            ))}
          </ul>
        </section>
      ) : null}
      {sameNumber.length ? (
        <section>
          <h3>Other sessions</h3>
          <ul>
            {sameNumber.map((entry) => (
              <li key={`${entry.session.id}-${entry.number}-${entry.url}`}>
                <Link href={normalizePath(entry.url)}>
                  <span>{entry.session.name}</span>
                  <span>{entry.short_title || entry.title}</span>
                </Link>
              </li>
            ))}
          </ul>
        </section>
      ) : null}
    </div>
  );
}

// MARK: Pagination

interface PaginationProps {
  basePath: string;
  activeTab: string | null;
  pagination: StatementListingPayload["pagination"];
}

function Pagination({ basePath, activeTab, pagination }: PaginationProps) {
  if (!pagination) {
    return null;
  }
  const { page, page_count: pageCount, has_previous: hasPrevious, has_next: hasNext } = pagination;
  return (
    <nav className="bill-detail__pagination" aria-label="Bill debate pagination">
      <ul>
        <li>
          {hasPrevious ? (
            <Link href={buildHref(basePath, activeTab, page - 1)}>Previous</Link>
          ) : (
            <span aria-disabled="true">Previous</span>
          )}
        </li>
        <li>
          <span>
            Page {page} of {pageCount}
          </span>
        </li>
        <li>
          {hasNext ? (
            <Link href={buildHref(basePath, activeTab, page + 1)}>Next</Link>
          ) : (
            <span aria-disabled="true">Next</span>
          )}
        </li>
      </ul>
    </nav>
  );
}

// MARK: Helpers

function buildHref(basePath: string, tab: string | null | undefined, page: number | undefined) {
  const params = new URLSearchParams();
  if (tab) {
    params.set("tab", tab);
  }
  if (page && page > 1) {
    params.set("page", String(page));
  }
  const query = params.toString();
  return query ? `${basePath}?${query}` : basePath;
}

function normalizePath(path: string) {
  if (!path) {
    return path;
  }
  try {
    const url = new URL(path, "http://localhost");
    const pathname = url.pathname.replace(/\/+$/, "");
    const search = url.search;
    const normalized = `${pathname || "/"}${search}`;
    return normalized;
  } catch (error) {
    console.warn("Failed to normalize path", path, error);
    return path;
  }
}

function formatDate(date: string) {
  try {
    return new Intl.DateTimeFormat("en-CA", { dateStyle: "long" }).format(new Date(date));
  } catch (error) {
    console.warn("Failed to format date", date, error);
    return date;
  }
}

function formatDateTime(dateTime: string) {
  try {
    const date = new Date(dateTime);
    return new Intl.DateTimeFormat("en-CA", {
      dateStyle: "medium",
      timeStyle: "short",
    }).format(date);
  } catch (error) {
    console.warn("Failed to format datetime", dateTime, error);
    return dateTime;
  }
}
