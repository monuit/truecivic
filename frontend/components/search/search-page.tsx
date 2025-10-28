import clsx from "clsx";
import styles from "./search-page.module.css";
import { SearchForm } from "./search-form";
import { SearchResultList } from "./search-result-list";
import { SearchPagination } from "./search-pagination";
import { SearchFacets } from "./search-facets";
import { SearchHistogram } from "./search-histogram";
import type { SearchPayload } from "../../lib/op-api";
import type { SearchFilterMap } from "./search-url";
import { resolveSortOptions } from "./search-constants";

// MARK: Component
interface SearchPageProps {
  payload: SearchPayload;
  query: string;
  sort: string | null | undefined;
  filters: SearchFilterMap;
  basePath?: string;
}

export function SearchPage({
  payload,
  query,
  sort,
  filters,
  basePath = "/search",
}: SearchPageProps) {
  const totalItems = payload.pagination.total_items;
  const hasResults = payload.results.length > 0;
  const sortOptions = resolveSortOptions(payload.sort_options);
  const activeSort = payload.sort ?? sort ?? (sortOptions[0]?.value ?? null);

  return (
    <main className="site-main">
      <section className={styles.section}>
        <div className={clsx("layout-row", styles.layout)}>
          <div className={clsx("layout-primary", styles.primary)}>
            <header className={styles.header}>
              <h1 className={styles.title}>Search Parliament</h1>
              <p className={styles.summary}>
                {hasResults
                  ? `${totalItems.toLocaleString()} results for “${query}”.`
                  : `No matches for “${query}” yet.`}
              </p>
            </header>
            <SearchForm
              query={query}
              filters={filters}
              sort={activeSort}
              sortOptions={sortOptions}
            />
            <SearchHistogram histogram={payload.histogram} />
            <SearchResultList results={payload.results} />
            <SearchPagination
              pagination={payload.pagination}
              query={query}
              sort={activeSort}
              filters={filters}
              basePath={basePath}
            />
          </div>
          <aside className={clsx("layout-secondary", styles.secondary)}>
            <SearchFacets
              facets={payload.facets}
              query={query}
              sort={activeSort}
              filters={filters}
              basePath={basePath}
            />
          </aside>
        </div>
      </section>
    </main>
  );
}
