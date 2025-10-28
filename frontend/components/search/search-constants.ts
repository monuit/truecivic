import type { SearchSortOption } from "../../lib/op-types";

export const DEFAULT_SEARCH_SORT_OPTIONS: SearchSortOption[] = [
  { value: "score desc", label: "Best match" },
  { value: "date desc", label: "Newest first" },
  { value: "date asc", label: "Oldest first" },
];

export function resolveSortOptions(options?: SearchSortOption[] | null): SearchSortOption[] {
  if (options && options.length > 0) {
    return options;
  }
  return DEFAULT_SEARCH_SORT_OPTIONS;
}

const LEGACY_FACET_LABELS: Record<string, string> = {
  party: "Party",
  province: "Province",
  politician: "Person",
  politician_id: "MP",
  who_hocid: "Witness",
  committee_slug: "Committee",
  date: "Date",
  type: "Type",
  doc_url: "Document",
};

export function getFacetLabel(key: string): string {
  return LEGACY_FACET_LABELS[key] ?? formatFallbackLabel(key);
}

function formatFallbackLabel(rawKey: string): string {
  return rawKey
    .split(/[_\-]/)
    .map((segment) => segment.charAt(0).toUpperCase() + segment.slice(1))
    .join(" ");
}
