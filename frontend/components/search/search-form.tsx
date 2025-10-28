import clsx from "clsx";
import styles from "./search-form.module.css";
import type { SearchFilterMap } from "./search-url";
import type { SearchSortOption } from "../../lib/op-types";

// MARK: Component
interface SearchFormProps {
  query: string;
  filters: SearchFilterMap;
  sort?: string | null | undefined;
  sortOptions?: SearchSortOption[];
  className?: string;
}

export function SearchForm({ query, filters, sort, sortOptions, className }: SearchFormProps) {
  const defaultSort = sortOptions && sortOptions.length > 0 ? sortOptions[0].value : "";
  const optionValues = new Set((sortOptions ?? []).map((option) => option.value));
  const resolvedSort = sort && optionValues.has(sort) ? sort : defaultSort;

  return (
    <form method="get" action="/search" className={clsx(styles.form, className)}>
      <label className="visually-hidden" htmlFor="site-search-query">
        Search Parliament
      </label>
      <input
        id="site-search-query"
        name="q"
        defaultValue={query}
        placeholder="Search Hansard, bills, votes, and more"
        className={styles.input}
        type="search"
        autoComplete="off"
      />
      {sortOptions && sortOptions.length > 0 ? (
        <label className="visually-hidden" htmlFor="site-search-sort">
          Sort results
        </label>
      ) : null}
      {sortOptions && sortOptions.length > 0 ? (
        <select id="site-search-sort" name="sort" defaultValue={resolvedSort} className={styles.select}>
          {sortOptions.map((option) => (
            <option key={option.value} value={option.value}>
              {option.label}
            </option>
          ))}
        </select>
      ) : null}
      <button type="submit" className={styles.button}>
        Search
      </button>
      {Object.entries(filters).map(([key, values]) =>
        values.map((value, index) => (
          <input key={`${key}-${index}`} type="hidden" name={key} value={value} />
        )),
      )}
    </form>
  );
}
