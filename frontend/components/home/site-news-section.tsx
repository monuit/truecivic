import Link from "next/link";
import type { SiteNewsItem } from "../../lib/op-api";

// MARK: Component
interface SiteNewsSectionProps {
  items: SiteNewsItem[];
}

export function SiteNewsSection({ items }: SiteNewsSectionProps) {
  if (!items.length) {
    return null;
  }
  return (
    <section className="home-section">
      <div className="layout-row">
        <div className="layout-context">
          <h2>What is new around here</h2>
        </div>
        <div className="layout-primary">
          <p className="home-section__intro">
            Subscribe to our <Link href="/feeds/site-news">site news feed</Link>, or follow
            {" "}
            <a href="https://twitter.com/openparlca">@openparlca</a> on Twitter.
          </p>
          <ol className="site-news">
            {items.map((item) => (
              <li key={item.id}>
                <article>
                  <header>
                    <h3>{item.title}</h3>
                    <time dateTime={item.date}>{formatDate(item.date)}</time>
                  </header>
                  <div className="site-news__body" dangerouslySetInnerHTML={{ __html: item.html }} />
                </article>
              </li>
            ))}
          </ol>
        </div>
      </div>
    </section>
  );
}

function formatDate(value: string) {
  return new Intl.DateTimeFormat("en-CA", {
    month: "long",
    day: "numeric",
  }).format(new Date(value));
}
