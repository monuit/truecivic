import Link from "next/link";
import type { HansardMetadata } from "../../lib/op-api";

// MARK: Component
interface HomeHeroProps {
  latestHansard: HansardMetadata | null;
}

export function HomeHero({ latestHansard }: HomeHeroProps) {
  return (
    <section className="home-section home-hero" aria-labelledby="home-hero-heading">
      <div className="home-hero__surface">
        <div className="home-hero__intro">
          <p className="home-hero__kicker">Daily civic intelligence</p>
          <h1 className="home-hero__title" id="home-hero-heading">
            Stay ahead of Parliament.
          </h1>
          <p className="home-hero__lede">
            TrueCivic brings together transcripts, votes, and legislation so you can understand what MPs are
            debating without sifting through hours of proceedings.
          </p>
          <div className="home-hero__actions">
            <Link className="home-hero__action" href="/debates">
              Browse debates
            </Link>
            <Link className="home-hero__action home-hero__action--secondary" href="/votes">
              Recent votes
            </Link>
            <Link className="home-hero__action home-hero__action--secondary" href="/bills">
              Track legislation
            </Link>
          </div>
        </div>
        {latestHansard ? (
          <aside className="home-hero__meta" aria-live="polite">
            <p className="home-hero__meta-label">Latest House transcript</p>
            <p className="home-hero__meta-date">{formatHansardDate(latestHansard)}</p>
            {latestHansard.most_frequent_word ? (
              <p className="home-hero__meta-word">
                Word of the day <strong>{latestHansard.most_frequent_word}</strong>
              </p>
            ) : null}
            {latestHansard.url ? (
              <Link className="home-hero__meta-link" href={latestHansard.url}>
                Open transcript
              </Link>
            ) : null}
          </aside>
        ) : null}
      </div>
    </section>
  );
}

function formatHansardDate(hansard: HansardMetadata): string {
  if (!hansard.date) {
    return "Most recent sitting";
  }
  const formatter = new Intl.DateTimeFormat("en-CA", {
    month: "long",
    day: "numeric",
  });
  return formatter.format(new Date(hansard.date));
}
