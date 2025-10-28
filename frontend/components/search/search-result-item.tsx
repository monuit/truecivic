import styles from "./search-result-item.module.css";
import type { SearchResultPayload } from "../../lib/op-api";

// MARK: Helpers
function formatResultDate(input: string | null): string | null {
  if (!input) {
    return null;
  }
  const parsed = new Date(input);
  if (Number.isNaN(parsed.getTime())) {
    return input;
  }
  return new Intl.DateTimeFormat("en-CA", { dateStyle: "long" }).format(parsed);
}

// MARK: Component
interface SearchResultItemProps {
  result: SearchResultPayload;
}

export function SearchResultItem({ result }: SearchResultItemProps) {
  const formattedDate = formatResultDate(result.date);
  const metaEntries = Object.entries(result.meta ?? {});

  return (
    <article className={styles.item}>
      <header>
        <p className={styles.badge}>{result.type}</p>
        <h2 className={styles.heading}>
          <a href={result.url}>{result.title}</a>
        </h2>
        {formattedDate ? <p className={styles.meta}>{formattedDate}</p> : null}
      </header>
      {result.summary ? <p className={styles.summary}>{result.summary}</p> : null}
      {metaEntries.length > 0 ? (
        <ul className={styles.metaList}>
          {metaEntries.map(([key, value]) => (
            <li key={key}>
              <strong>{key}:</strong> {String(value)}
            </li>
          ))}
        </ul>
      ) : null}
    </article>
  );
}
