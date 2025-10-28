import styles from "./search-result-list.module.css";
import { SearchResultItem } from "./search-result-item";
import type { SearchResultPayload } from "../../lib/op-api";

// MARK: Component
interface SearchResultListProps {
  results: SearchResultPayload[];
}

export function SearchResultList({ results }: SearchResultListProps) {
  if (results.length === 0) {
    return <p className={styles.empty}>No matches for your query. Try adjusting your filters.</p>;
  }

  return (
    <ol className={styles.list} aria-label="Search results">
      {results.map((result) => (
        <li key={`${result.type}-${result.url}`}>
          <SearchResultItem result={result} />
        </li>
      ))}
    </ol>
  );
}
