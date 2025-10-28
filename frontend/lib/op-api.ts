import type {
  BillDetailPayload,
  BillListPayload,
  CommitteeListPayload,
  DebateListPayload,
  HomePayload,
  PoliticianListPayload,
  SearchPayload,
  VoteDetailPayload,
  VoteListPayload,
} from "./op-types";

export type {
  BillDetailDataPayload,
  BillDetailPayload,
  BillReference,
  BillDebatePayload,
  CommitteeMeetingPayload,
  KnowledgeChunkScopePayload,
  DebateTabPayload,
  HansardMetadata,
  HansardSummary,
  HansardTopic,
  HistogramPayload,
  HomePayload,
  BillListFiltersPayload,
  BillListItemPayload,
  BillListPayload,
  PoliticianListItemPayload,
  PoliticianListPayload,
  DebateListItemPayload,
  DebateListPayload,
  CommitteeMeetingSummaryPayload,
  CommitteeListItemPayload,
  CommitteeListPayload,
  PaginationPayload,
  SearchFacetEntry,
  SearchPayload,
  SearchSortOption,
  SearchResultPayload,
  SessionSummary,
  SiteNewsItem,
  StatementListingPayload,
  StatementPayload,
  VoteSummary,
  VoteListPayload,
  VoteListFiltersPayload,
  VoteListItemPayload,
  VoteDetailPayload,
  VoteDetailDataPayload,
  PartyVotePayload,
  MemberBallotPayload,
  WordcloudEntry,
  SessionOption,
} from "./op-types";

// MARK: Internal helpers

type ApiRequestInit = RequestInit & {
  next?: {
    revalidate?: number;
    tags?: string[];
  };
};

type SearchFilterValue = string | string[];

export interface FetchSearchOptions {
  query: string;
  page?: number;
  sort?: string;
  filters?: Record<string, SearchFilterValue>;
  init?: ApiRequestInit;
}

export interface FetchBillDetailOptions {
  sessionId: string;
  billNumber: string;
  tab?: string | null;
  page?: number;
  singlePage?: boolean;
  init?: ApiRequestInit;
}

export interface FetchBillListOptions {
  sessionId?: string | null;
  limit?: number;
  init?: ApiRequestInit;
}

export interface FetchPoliticianListOptions {
  status?: "current" | "former";
  init?: ApiRequestInit;
}

export interface FetchDebateListOptions {
  limit?: number;
  init?: ApiRequestInit;
}

export interface FetchCommitteeListOptions {
  limit?: number;
  init?: ApiRequestInit;
}

export interface FetchVoteListOptions {
  sessionId?: string | null;
  limit?: number;
  init?: ApiRequestInit;
}

export interface FetchVoteDetailOptions {
  sessionId: string;
  number: number;
  init?: ApiRequestInit;
}

function buildBaseUrl(): string {
  const truecivicEnv = process.env.NEXT_PUBLIC_TRUECIVIC_API_BASE_URL;
  if (truecivicEnv) {
    return truecivicEnv.replace(/\/$/, "");
  }
  const legacyEnv = process.env.NEXT_PUBLIC_OP_API_BASE_URL;
  if (legacyEnv) {
    return legacyEnv.replace(/\/$/, "");
  }
  const fallback = process.env.NEXT_PUBLIC_API_BASE_URL;
  if (fallback) {
    return fallback.replace(/\/$/, "");
  }
  if (process.env.NODE_ENV !== "production") {
    return "http://localhost:8000";
  }
  return "";
}

function resolveUrl(path: string, searchParams?: URLSearchParams): string {
  const normalizedPath = path.startsWith("/") ? path : `/${path}`;
  const query = searchParams ? `?${searchParams.toString()}` : "";
  const base = buildBaseUrl();
  if (!base) {
    return `${normalizedPath}${query}`;
  }
  return `${base}${normalizedPath}${query}`;
}

async function readJson<T>(response: Response): Promise<T> {
  const payload = (await response.json()) as unknown;
  return payload as T;
}

// MARK: API client

export class TrueCivicApiClient {
  private readonly defaultInit: ApiRequestInit;

  private constructor(defaultInit?: ApiRequestInit) {
    this.defaultInit = {
      ...defaultInit,
    };
  }

  static fromEnv(init?: ApiRequestInit): TrueCivicApiClient {
    return new TrueCivicApiClient(init);
  }

  async fetchHome(init?: ApiRequestInit): Promise<HomePayload> {
    const requestInit = this.mergeInit(init, { next: { revalidate: 300 } });
    return this.fetchJson<HomePayload>({
      path: "/api/v1/home",
      description: "Home API",
      init: requestInit,
    });
  }

  async fetchSearch(options: FetchSearchOptions): Promise<SearchPayload> {
    const { query, page, sort, filters, init } = options;
    const searchParams = new URLSearchParams();
    searchParams.set("q", query);
    if (page && page > 1) {
      searchParams.set("page", String(page));
    }
    if (sort) {
      searchParams.set("sort", sort);
    }
    if (filters) {
      for (const [key, value] of Object.entries(filters)) {
        if (Array.isArray(value)) {
          value.forEach((entry) => searchParams.append(key, entry));
        } else if (value !== undefined) {
          searchParams.append(key, value);
        }
      }
    }
    const requestInit = this.mergeInit(init, { cache: "no-store" });
    return this.fetchJson<SearchPayload>({
      path: "/api/v1/search",
      description: "Search API",
      searchParams,
      init: requestInit,
    });
  }

  async fetchBillDetail(options: FetchBillDetailOptions): Promise<BillDetailPayload> {
    const { sessionId, billNumber, tab, page, singlePage, init } = options;
    const searchParams = new URLSearchParams();
    if (tab) {
      searchParams.set("tab", tab);
    }
    if (page && page > 1) {
      searchParams.set("page", String(page));
    }
    if (singlePage) {
      searchParams.set("singlepage", "1");
    }
    const requestInit = this.mergeInit(init);
    return this.fetchJson<BillDetailPayload>({
      path: `/api/v1/bills/${sessionId}/${billNumber}`,
      description: "Bill detail API",
      searchParams,
      init: requestInit,
    });
  }

  async fetchBillList(options: FetchBillListOptions = {}): Promise<BillListPayload> {
    const { sessionId, limit, init } = options;
    const searchParams = new URLSearchParams();
    if (sessionId) {
      searchParams.set("session", sessionId);
    }
    if (limit && limit > 0) {
      searchParams.set("limit", String(limit));
    }
    const requestInit = this.mergeInit(init, { cache: "no-store" });
    return this.fetchJson<BillListPayload>({
      path: "/api/v1/bills",
      description: "Bill list API",
      searchParams,
      init: requestInit,
    });
  }

  async fetchPoliticianList(
    options: FetchPoliticianListOptions = {},
  ): Promise<PoliticianListPayload> {
    const { status = "current", init } = options;
    const normalized = status === "former" ? "former" : "current";
    const searchParams = new URLSearchParams();
    searchParams.set("status", normalized);
    const requestInit = this.mergeInit(init, { cache: "no-store" });
    return this.fetchJson<PoliticianListPayload>({
      path: "/api/v1/politicians",
      description: "Politician list API",
      searchParams,
      init: requestInit,
    });
  }

  async fetchDebateList(options: FetchDebateListOptions = {}): Promise<DebateListPayload> {
    const { limit, init } = options;
    const searchParams = new URLSearchParams();
    if (limit && limit > 0) {
      searchParams.set("limit", String(limit));
    }
    const requestInit = this.mergeInit(init, { cache: "no-store" });
    return this.fetchJson<DebateListPayload>({
      path: "/api/v1/debates",
      description: "Debate list API",
      searchParams,
      init: requestInit,
    });
  }

  async fetchCommitteeList(options: FetchCommitteeListOptions = {}): Promise<CommitteeListPayload> {
    const { limit, init } = options;
    const searchParams = new URLSearchParams();
    if (limit && limit > 0) {
      searchParams.set("limit", String(limit));
    }
    const requestInit = this.mergeInit(init, { cache: "no-store" });
    return this.fetchJson<CommitteeListPayload>({
      path: "/api/v1/committees",
      description: "Committee list API",
      searchParams,
      init: requestInit,
    });
  }

  async fetchVoteList(options: FetchVoteListOptions = {}): Promise<VoteListPayload> {
    const { sessionId, limit, init } = options;
    const searchParams = new URLSearchParams();
    if (sessionId) {
      searchParams.set("session", sessionId);
    }
    if (limit && limit > 0) {
      searchParams.set("limit", String(limit));
    }
    const requestInit = this.mergeInit(init, { cache: "no-store" });
    return this.fetchJson<VoteListPayload>({
      path: "/api/v1/votes",
      description: "Vote list API",
      searchParams,
      init: requestInit,
    });
  }

  async fetchVoteDetail(options: FetchVoteDetailOptions): Promise<VoteDetailPayload> {
    const { sessionId, number, init } = options;
    const requestInit = this.mergeInit(init, { cache: "no-store" });
    return this.fetchJson<VoteDetailPayload>({
      path: `/api/v1/votes/${sessionId}/${number}`,
      description: "Vote detail API",
      init: requestInit,
    });
  }

  private mergeInit(primary?: ApiRequestInit, secondary?: ApiRequestInit): ApiRequestInit {
    const headers = this.mergeHeaders(primary?.headers, secondary?.headers);
    return {
      ...this.defaultInit,
      ...secondary,
      ...primary,
      headers,
    };
  }

  private mergeHeaders(
    base?: HeadersInit | undefined,
    overrides?: HeadersInit | undefined,
  ): HeadersInit | undefined {
    if (!base && !overrides) {
      return undefined;
    }
    const merged = new Headers(base || {});
    if (overrides) {
      const overrideEntries = this.headersToEntries(overrides);
      for (const [key, value] of overrideEntries) {
        merged.set(key, value);
      }
    }
    return merged;
  }

  private withJsonHeaders(headers?: HeadersInit): HeadersInit {
    const merged = new Headers(headers || {});
    if (!merged.has("Accept")) {
      merged.set("Accept", "application/json");
    }
    return merged;
  }

  private headersToEntries(headers: HeadersInit): Array<[string, string]> {
    if (headers instanceof Headers) {
      return Array.from(headers.entries());
    }
    if (Array.isArray(headers)) {
      return headers.map(([key, value]) => [key, value] as [string, string]);
    }
    return Object.entries(headers).map(([key, value]) => [key, String(value)]);
  }

  private async fetchJson<T>(options: {
    path: string;
    description: string;
    searchParams?: URLSearchParams;
    init?: ApiRequestInit;
  }): Promise<T> {
    const requestInit = options.init ?? this.defaultInit;
    const response = await fetch(resolveUrl(options.path, options.searchParams), {
      ...requestInit,
      headers: this.withJsonHeaders(requestInit.headers),
    });
    if (!response.ok) {
      throw new Error(`${options.description} request failed with status ${response.status}`);
    }
    return readJson<T>(response);
  }
}
