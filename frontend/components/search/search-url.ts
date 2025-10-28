// MARK: Types
export type SearchFilterMap = Record<string, string[]>;

interface BuildHrefOptions {
	query: string;
	page?: number;
	sort?: string | null;
	filters?: SearchFilterMap;
}

// MARK: Helpers
export function buildSearchHref(basePath: string, options: BuildHrefOptions): string {
	const params = new URLSearchParams();
	const trimmedQuery = options.query.trim();
	if (trimmedQuery.length > 0) {
		params.set("q", trimmedQuery);
	}
	if (options.sort) {
		params.set("sort", options.sort);
	}
	if (options.page && options.page > 1) {
		params.set("page", String(options.page));
	}
	if (options.filters) {
		for (const [key, values] of Object.entries(options.filters)) {
			for (const value of values) {
				params.append(key, value);
			}
		}
	}
	const queryString = params.toString();
	if (!queryString) {
		return basePath;
	}
	return `${basePath}?${queryString}`;
}

export function addFilterValue(
	filters: SearchFilterMap,
	key: string,
	value: string,
): SearchFilterMap {
	const next = cloneFilters(filters);
	const existing = next[key] ?? [];
	if (!existing.includes(value)) {
		next[key] = [...existing, value];
	} else {
		next[key] = existing;
	}
	return next;
}

export function removeFilterValue(
	filters: SearchFilterMap,
	key: string,
	value: string,
): SearchFilterMap {
	const next = cloneFilters(filters);
	if (!next[key]) {
		return next;
	}
	next[key] = next[key].filter((entry) => entry !== value);
	if (next[key].length === 0) {
		delete next[key];
	}
	return next;
}

export function cloneFilters(filters: SearchFilterMap): SearchFilterMap {
	return Object.fromEntries(
		Object.entries(filters).map(([filterKey, values]) => [filterKey, [...values]]),
	);
}
