import Link from "next/link";
import type {
  HansardMetadata,
  HansardSummary,
  WordcloudEntry,
} from "../../lib/op-api";

const KEYWORD_LIMIT = 6;

interface TranscriptHighlightSectionProps {
  latestHansard: HansardMetadata | null;
  summary: HansardSummary | null;
  wordcloud: WordcloudEntry[];
}

export function TranscriptHighlightSection({
  latestHansard,
  summary,
  wordcloud,
}: TranscriptHighlightSectionProps) {
  if (!summary && !latestHansard && wordcloud.length === 0) {
    return null;
  }

  const headline = formatHeadlineDate(latestHansard?.date);
  const topKeywords = wordcloud.slice(0, KEYWORD_LIMIT);

  return (
    <section className="home-section transcript-highlight" aria-labelledby="transcript-highlight-heading">
      <div className="layout-row transcript-highlight__row">
        <div className="layout-context">
          <h2 id="transcript-highlight-heading">Latest House TL;DR</h2>
        </div>
        <div className="layout-primary transcript-highlight__body">
          {summary ? (
            <article className="transcript-highlight__summary" aria-live="polite">
              <header>
                <p className="transcript-highlight__summary-label">Summary generated</p>
                <p className="transcript-highlight__summary-meta">
                  {headline}
                  {summary.token_count ? ` · ${summary.token_count} tokens` : ""}
                </p>
              </header>
              {summary.title ? <h3>{summary.title}</h3> : null}
              <div
                className="transcript-highlight__summary-content"
                dangerouslySetInnerHTML={{ __html: summary.html }}
              />
            </article>
          ) : (
            <p className="home-section__intro">We are still preparing a TL;DR for the latest House sitting.</p>
          )}
        </div>
        {(latestHansard || topKeywords.length > 0) ? (
          <aside className="transcript-highlight__meta">
            {latestHansard ? (
              <div className="transcript-highlight__meta-block">
                <h3>Latest transcript</h3>
                <p className="transcript-highlight__meta-date">{headline}</p>
                <p className="transcript-highlight__meta-word">
                  {latestHansard.most_frequent_word ? (
                    <>
                      Word of the day: <strong>{latestHansard.most_frequent_word}</strong>
                    </>
                  ) : (
                    "Topical highlights below."
                  )}
                </p>
                {latestHansard.url ? (
                  <Link className="transcript-highlight__link" href={latestHansard.url}>
                    Read the full transcript
                  </Link>
                ) : null}
              </div>
            ) : null}
            {topKeywords.length > 0 ? (
              <div className="transcript-highlight__keywords">
                <h3>Top keywords</h3>
                <ul>
                  {topKeywords.map((entry) => (
                    <li key={entry.text} aria-label={`${entry.text} keyword`}>
                      {entry.text}
                    </li>
                  ))}
                </ul>
              </div>
            ) : null}
          </aside>
        ) : null}
      </div>
    </section>
  );
}

function formatHeadlineDate(value: string | null | undefined) {
  if (!value) {
    return "Latest sitting";
  }
  const formatter = new Intl.DateTimeFormat("en-CA", {
    year: "numeric",
    month: "long",
    day: "numeric",
  });
  return formatter.format(new Date(value));
}
