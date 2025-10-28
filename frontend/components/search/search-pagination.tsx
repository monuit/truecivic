import Link from "next/link";
import styles from "./search-pagination.module.css";
import type { PaginationPayload } from "../../lib/op-api";
import type { SearchFilterMap } from "./search-url";
import { buildSearchHref } from "./search-url";

// MARK: Component
interface SearchPaginationProps {
  pagination: PaginationPayload;
  query: string;
  sort: string | null | undefined;
  filters: SearchFilterMap;
  basePath?: string;
}

export function SearchPagination({
  pagination,
  query,
  sort,
  filters,
  basePath = "/search",
}: SearchPaginationProps) {
  if (pagination.page_count <= 1) {
    return null;
  }

  const prevPage = pagination.has_previous ? pagination.page - 1 : null;
  const nextPage = pagination.has_next ? pagination.page + 1 : null;

  const prevHref =
    prevPage && prevPage >= 1
      ? buildSearchHref(basePath, { query, sort: sort ?? null, page: prevPage, filters })
      : null;
  const nextHref =
    nextPage && nextPage <= pagination.page_count
      ? buildSearchHref(basePath, { query, sort: sort ?? null, page: nextPage, filters })
      : null;

  return (
    <nav className={styles.pagination} aria-label="Search pagination">
      <Link href={prevHref ?? "#"} className={styles.button} aria-disabled={!prevHref}>
        ← Previous
      </Link>
      <span className={styles.pageInfo}>
        Page {pagination.page} of {pagination.page_count}
      </span>
      <Link href={nextHref ?? "#"} className={styles.button} aria-disabled={!nextHref}>
        Next →
      </Link>
    </nav>
  );
}
