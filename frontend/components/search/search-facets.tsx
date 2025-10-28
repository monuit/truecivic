import Link from "next/link";
import styles from "./search-facets.module.css";
import type { SearchFacetEntry } from "../../lib/op-api";
import type { SearchFilterMap } from "./search-url";
import { addFilterValue, buildSearchHref, removeFilterValue } from "./search-url";
import { getFacetLabel } from "./search-constants";

function hasFacetContent(facets: Record<string, SearchFacetEntry[]>): boolean {
  return Object.values(facets).some((entries) => entries.length > 0);
}

// MARK: Component
interface SearchFacetsProps {
  facets: Record<string, SearchFacetEntry[]>;
  query: string;
  sort: string | null | undefined;
  filters: SearchFilterMap;
  basePath?: string;
}

export function SearchFacets({
  facets,
  query,
  sort,
  filters,
  basePath = "/search",
}: SearchFacetsProps) {
  const hasFacets = hasFacetContent(facets);
  const hasActiveFilters = Object.keys(filters).length > 0;

  if (!hasFacets && !hasActiveFilters) {
    return null;
  }

  return (
    <div className={styles.container}>
      {hasActiveFilters ? (
        <section className={styles.activeFilters} aria-label="Active filters">
          <h2>Active filters</h2>
          <ul className={styles.filterList}>
            {Object.entries(filters).map(([key, values]) =>
              values.map((value) => {
                const nextFilters = removeFilterValue(filters, key, value);
                const href = buildSearchHref(basePath, {
                  query,
                  sort: sort ?? null,
                  page: 1,
                  filters: nextFilters,
                });
                return (
                  <li key={`${key}-${value}`}>
                    <Link href={href} className={styles.chip} prefetch={false}>
                      {getFacetLabel(key)}: {value} ×
                    </Link>
                  </li>
                );
              }),
            )}
          </ul>
          <Link
            href={buildSearchHref(basePath, { query, sort: sort ?? null, page: 1 })}
            prefetch={false}
          >
            Clear all
          </Link>
        </section>
      ) : null}

      {hasFacets ? (
        <section aria-label="Available filters">
          <h2>Filter results</h2>
          {Object.entries(facets).map(([facetKey, entries]) => {
            if (entries.length === 0) {
              return null;
            }
            return (
              <div key={facetKey} className={styles.group}>
                <h3>{getFacetLabel(facetKey)}</h3>
                <ul className={styles.groupList}>
                  {entries.map((entry) => {
                    const isActive = filters[facetKey]?.includes(entry.value) ?? false;
                    if (isActive) {
                      return (
                        <li key={`${facetKey}-${entry.value}`}>
                          <span>
                            {entry.value}
                            <span className={styles.count}> ({entry.count})</span>
                          </span>
                        </li>
                      );
                    }
                    const nextFilters = addFilterValue(filters, facetKey, entry.value);
                    const href = buildSearchHref(basePath, {
                      query,
                      sort: sort ?? null,
                      page: 1,
                      filters: nextFilters,
                    });
                    return (
                      <li key={`${facetKey}-${entry.value}`}>
                        <Link href={href} prefetch={false}>
                          {entry.value}
                          <span className={styles.count}> ({entry.count})</span>
                        </Link>
                      </li>
                    );
                  })}
                </ul>
              </div>
            );
          })}
        </section>
      ) : null}
    </div>
  );
}
