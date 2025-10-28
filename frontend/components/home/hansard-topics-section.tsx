import Link from "next/link";
import type { HansardMetadata, HansardTopic } from "../../lib/op-api";

const CANONICAL_HOST = "https://truecivic.ca";

// MARK: Component
interface HansardTopicsSectionProps {
  latestHansard: HansardMetadata | null;
  topics: HansardTopic[];
}

export function HansardTopicsSection({ latestHansard, topics }: HansardTopicsSectionProps) {
  return (
    <section className="home-section">
      <div className="layout-row">
        <div className="layout-context">
          <h2>What they are talking about</h2>
        </div>
        <div className="layout-primary">
          {latestHansard ? renderHansardIntro(latestHansard) : renderEmptyState()}
          {topics.length > 0 ? renderTopics(latestHansard, topics) : null}
        </div>
      </div>
    </section>
  );
}

function renderHansardIntro(hansard: HansardMetadata) {
  return (
    <p className="home-section__intro">
      The latest House transcript is from <strong>{formatHansardDate(hansard.date)}</strong>
      {hansard.most_frequent_word ? (
        <>
          , when the <span className="tip">word of the day</span> was <strong>{hansard.most_frequent_word}</strong>.
        </>
      ) : (
        "."
      )}
    </p>
  );
}

function renderTopics(latestHansard: HansardMetadata | null, topics: HansardTopic[]) {
  return (
    <ul className="topic-grid">
      {topics.map((topic) => (
        <li key={topic.slug || topic.heading || topic.debate_stage}>
          <h3>{topic.heading || "House debate"}</h3>
          <dl className="topic-metadata">
            <div>
              <dt>Minutes</dt>
              <dd>{topic.minutes}</dd>
            </div>
            <div>
              <dt>Wordcount</dt>
              <dd>{topic.wordcount}</dd>
            </div>
          </dl>
          {topic.bill_number ? (
            <p className="topic-bill">
              Bill <Link href={buildBillUrl(latestHansard, topic.bill_number)}>{topic.bill_number}</Link>
            </p>
          ) : null}
          {topic.subheadings.length > 0 ? (
            <ul className="topic-subheadings">
              {topic.subheadings.map((entry) => (
                <li key={entry.slug}>
                  <Link href={buildSubheadingUrl(latestHansard, topic, entry.slug)}>{entry.label}</Link>
                </li>
              ))}
            </ul>
          ) : null}
        </li>
      ))}
    </ul>
  );
}

function renderEmptyState() {
  return <p className="home-section__intro">We do not have any Hansard transcripts available yet.</p>;
}

function formatHansardDate(value: string | null) {
  if (!value) {
    return "the most recent sitting";
  }
  return new Intl.DateTimeFormat("en-CA", { month: "long", day: "numeric" }).format(new Date(value));
}

function buildBillUrl(hansard: HansardMetadata | null, billNumber: string) {
  if (hansard?.url) {
    const url = new URL(hansard.url, CANONICAL_HOST);
    const parts = url.pathname.split("/").filter(Boolean);
    if (parts.length >= 3) {
      const sessionId = parts[1];
      return `/bills/${sessionId}/${billNumber}`;
    }
  }
  return `/bills/${billNumber}`;
}

function buildSubheadingUrl(hansard: HansardMetadata | null, topic: HansardTopic, slug: string) {
  const base = hansard?.url ? hansard.url : "/debates/";
  const joinSegments = createPathJoiner(base);
  const topicSegment = topic.slug || "";
  const cleanSlug = slug.replace(/^#/, "");
  return joinSegments(topicSegment, cleanSlug);
}

function createPathJoiner(base: string) {
  const normalizedBase = ensureTrailingSlash(base);
  return (...segments: string[]) => {
    const sanitized = segments
      .filter(Boolean)
      .map((segment) => segment.replace(/^\/+|\/+$/g, ""))
      .filter(Boolean);
    const path = [normalizedBase.replace(/\/+$/g, ""), ...sanitized].join("/");
    if (path.startsWith("http")) {
      const url = new URL(path, CANONICAL_HOST);
      return ensureTrailingSlash(url.pathname);
    }
    return ensureTrailingSlash(path.startsWith("/") ? path : `/${path}`);
  };
}

function ensureTrailingSlash(input: string) {
  return input.endsWith("/") ? input : `${input}/`;
}