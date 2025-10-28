import type { Metadata } from "next";
import { TrueCivicApiClient } from "../../lib/op-api";
import { SearchLanding } from "../../components/search/search-landing";
import { SearchPage } from "../../components/search/search-page";
import type { SearchFilterMap } from "../../components/search/search-url";

interface SearchRouteProps {
  searchParams?: Record<string, string | string[] | undefined>;
}

export const metadata: Metadata = {
  title: "Search | truecivic",
};

export default async function SearchRoute({ searchParams = {} }: SearchRouteProps) {
  const query = extractFirst(searchParams.q)?.trim() ?? "";
  const sort = extractFirst(searchParams.sort) ?? null;
  const pageNumber = parsePositiveInteger(extractFirst(searchParams.page)) ?? 1;
  const filters = extractFilters(searchParams);
  const client = TrueCivicApiClient.fromEnv();
  const requestFilters = mapFiltersForRequest(filters);

  if (!query) {
    try {
      const payload = await client.fetchSearch({
        query,
        sort: sort ?? undefined,
        page: pageNumber,
        filters: requestFilters,
      });

      return <SearchLanding filters={filters} sortOptions={payload.sort_options} />;
    } catch (error) {
      return renderSearchError(error);
    }
  }

  try {
    const payload = await client.fetchSearch({
      query,
      sort: sort ?? undefined,
      page: pageNumber,
      filters: requestFilters,
    });

    return <SearchPage payload={payload} query={query} sort={payload.sort ?? sort} filters={filters} />;
  } catch (error) {
    return renderSearchError(error);
  }
}

function renderSearchError(error: unknown) {
  return (
    <main className="site-main">
      <section className="home-section">
        <div className="layout-row">
          <div className="layout-primary">
            <h1>Search unavailable</h1>
            <p>We could not load search results right now. Please try again soon.</p>
            {process.env.NODE_ENV !== "production" ? (
              <pre className="error-block">{String(error)}</pre>
            ) : null}
          </div>
        </div>
      </section>
    </main>
  );
}

function extractFirst(value: string | string[] | undefined): string | null {
  if (Array.isArray(value)) {
    return value[0] ?? null;
  }
  if (typeof value === "string") {
    return value;
  }
  return null;
}

function parsePositiveInteger(raw: string | null): number | null {
  if (!raw) {
    return null;
  }
  const parsed = Number.parseInt(raw, 10);
  if (Number.isNaN(parsed) || parsed < 1) {
    return null;
  }
  return parsed;
}

function extractFilters(
  searchParams: Record<string, string | string[] | undefined>,
): SearchFilterMap {
  const result: SearchFilterMap = {};
  for (const [key, value] of Object.entries(searchParams)) {
    if (key === "q" || key === "sort" || key === "page") {
      continue;
    }
    if (Array.isArray(value)) {
      if (value.length > 0) {
        result[key] = value.filter((entry) => entry != null && entry !== "");
      }
    } else if (typeof value === "string" && value) {
      result[key] = [value];
    }
  }
  return result;
}

function mapFiltersForRequest(filters: SearchFilterMap): Record<string, string | string[]> {
  const result: Record<string, string | string[]> = {};
  for (const [key, values] of Object.entries(filters)) {
    if (values.length === 1) {
      result[key] = values[0];
    } else if (values.length > 1) {
      result[key] = values;
    }
  }
  return result;
}
