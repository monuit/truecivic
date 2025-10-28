import clsx from "clsx";
import styles from "./search-page.module.css";
import { SearchForm } from "./search-form";
import type { SearchFilterMap } from "./search-url";
import { resolveSortOptions } from "./search-constants";
import type { SearchSortOption } from "../../lib/op-types";

// MARK: Component
interface SearchLandingProps {
  filters: SearchFilterMap;
  sortOptions?: SearchSortOption[] | null;
}

export function SearchLanding({ filters, sortOptions }: SearchLandingProps) {
  const resolvedSortOptions = resolveSortOptions(sortOptions);
  const defaultSort = resolvedSortOptions[0]?.value;

  return (
    <main className="site-main">
      <section className={styles.section}>
        <div className={clsx("layout-row", styles.layout)}>
          <div className={clsx("layout-primary", styles.primary)}>
            <header className={styles.header}>
              <h1 className={styles.title}>Search Parliament</h1>
              <p className={styles.summary}>
                Explore debates, bills, votes, and committee appearances across Canada&apos;s Parliament.
              </p>
            </header>
            <SearchForm
              query=""
              filters={filters}
              sort={defaultSort}
              sortOptions={resolvedSortOptions}
            />
          </div>
        </div>
      </section>
    </main>
  );
}
