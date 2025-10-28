// MARK: Session & reference contracts
export interface SessionSummary {
  id: string;
  name: string;
  parliament: number | null;
  session: number | null;
}

export interface SessionOption {
  id: string;
  label: string;
}

export interface BillReference {
  number: string;
  session: SessionSummary;
  title: string;
  short_title: string | null;
  url: string;
  is_law: boolean;
}

export interface VoteSummary {
  number: number;
  date: string;
  description: string;
  result: string;
  result_code: string;
  url: string;
  bill_number: string | null;
  rag_scope: KnowledgeChunkScopePayload | null;
}

export interface VoteListItemPayload {
  number: number;
  date: string;
  description: string;
  result: string;
  result_code: string;
  url: string;
  session: SessionSummary;
  bill_number: string | null;
  bill_url: string | null;
  yea_total: number;
  nay_total: number;
  paired_total: number;
  rag_scope: KnowledgeChunkScopePayload | null;
}

export interface VoteListFiltersPayload {
  sessions: SessionOption[];
  selected_session: string | null;
}

export interface VoteListPayload {
  filters: VoteListFiltersPayload;
  items: VoteListItemPayload[];
}

export interface PartyVotePayload {
  party_name: string;
  party_short: string | null;
  vote: string;
  vote_code: string;
  disagreement: number | null;
}

export interface MemberBallotPayload {
  politician_name: string | null;
  politician_url: string | null;
  party: string | null;
  riding: string | null;
  vote: string;
  vote_code: string;
  dissent: boolean;
}

export interface VoteDetailDataPayload {
  number: number;
  date: string;
  description: string;
  result: string;
  result_code: string;
  url: string;
  session: SessionSummary;
  yea_total: number;
  nay_total: number;
  paired_total: number;
  bill: BillReference | null;
  context_statement_url: string | null;
  rag_scope: KnowledgeChunkScopePayload | null;
}

export interface VoteDetailPayload {
  vote: VoteDetailDataPayload;
  party_breakdown: PartyVotePayload[];
  ballots: MemberBallotPayload[];
}

export interface SiteNewsItem {
  id: number;
  title: string;
  date: string;
  text: string;
  html: string;
}

export interface WordcloudEntry {
  text: string;
  score: number;
}

// MARK: Listing payloads
export interface BillListItemPayload {
  number: string;
  session: SessionSummary;
  title: string;
  short_title: string | null;
  status: string | null;
  status_date: string | null;
  url: string;
  sponsor_name: string | null;
  sponsor_party: string | null;
}

export interface BillListFiltersPayload {
  sessions: SessionOption[];
  selected_session: string | null;
}

export interface BillListPayload {
  filters: BillListFiltersPayload;
  items: BillListItemPayload[];
}

export interface PoliticianListItemPayload {
  name: string;
  url: string;
  party: string | null;
  party_short: string | null;
  riding: string | null;
  province: string | null;
  start_date: string | null;
  rag_scope: KnowledgeChunkScopePayload | null;
}

export interface PoliticianListPayload {
  items: PoliticianListItemPayload[];
}

export interface DebateListItemPayload {
  date: string | null;
  number: string | null;
  session: SessionSummary;
  url: string;
  headline: string;
  most_frequent_word: string | null;
  rag_scope: KnowledgeChunkScopePayload | null;
}

export interface DebateListPayload {
  items: DebateListItemPayload[];
}

export interface CommitteeMeetingSummaryPayload {
  date: string;
  number: number;
  url: string | null;
}

export interface CommitteeListItemPayload {
  name: string;
  short_name: string;
  url: string;
  latest_session: SessionSummary | null;
  latest_meeting: CommitteeMeetingSummaryPayload | null;
  rag_scope: KnowledgeChunkScopePayload | null;
}

export interface CommitteeListPayload {
  items: CommitteeListItemPayload[];
}

// MARK: Hansard payloads
export interface HansardTopic {
  slug?: string;
  heading?: string | null;
  minutes: number;
  wordcount: number;
  additional_segments: string[];
  subheadings: Array<{ label: string; slug: string }>;
  bill_number?: string | null;
  debate_stage?: string | null;
  statement_slugs: string[];
}

export interface HansardSummary {
  title: string;
  text: string;
  html: string;
  generated_at: string;
  token_count: number;
}

export interface HansardMetadata {
  id: number;
  date: string | null;
  number: string | null;
  url: string;
  most_frequent_word: string | null;
}

export interface StatementPayload {
  slug: string;
  time: string | null;
  heading: string | null;
  topic: string | null;
  summary: string;
  html: string;
  url: string;
  politician_name: string | null;
  politician_url: string | null;
  party: string | null;
  riding: string | null;
}

// MARK: Pagination
export interface PaginationPayload {
  page: number;
  page_count: number;
  page_size: number;
  total_items: number;
  has_next: boolean;
  has_previous: boolean;
}

// MARK: Home payload
export interface HomePayload {
  latest_hansard: HansardMetadata | null;
  hansard_topics: HansardTopic[];
  hansard_summary: HansardSummary | null;
  wordcloud: WordcloudEntry[];
  recently_debated_bills: BillReference[];
  recent_votes: VoteSummary[];
  site_news: SiteNewsItem[];
}

// MARK: Search payload
export interface SearchFacetEntry {
  value: string;
  count: number;
}

export interface SearchResultPayload {
  type: string;
  title: string;
  url: string;
  summary: string;
  date: string | null;
  meta: Record<string, unknown>;
}

export interface HistogramPayload {
  years: number[];
  values: number[];
  discontinuity: number | null;
}

export interface SearchSortOption {
  value: string;
  label: string;
}

export interface SearchPayload {
  query: string;
  normalized_query: string;
  applied_filters: Record<string, string>;
  sort: string | null;
  sort_options: SearchSortOption[];
  pagination: PaginationPayload;
  results: SearchResultPayload[];
  facets: Record<string, SearchFacetEntry[]>;
  histogram: HistogramPayload;
}

// MARK: Bill detail payloads
export interface DebateTabPayload {
  key: string;
  label: string;
  has_content: boolean;
}

export interface StatementListingPayload {
  tab: string;
  items: StatementPayload[];
  pagination: PaginationPayload | null;
}

export interface BillDebatePayload {
  tabs: DebateTabPayload[];
  default_tab: string | null;
  active_tab: string | null;
  stage_word_counts: Record<string, number>;
  statements: StatementListingPayload | null;
  has_mentions: boolean;
  has_meetings: boolean;
}

export interface CommitteeMeetingPayload {
  date: string;
  number: number;
  url: string;
  committee: string;
}

export interface KnowledgeChunkScopePayload {
  source_type: string;
  source_identifier: string;
}

export interface BillDetailDataPayload {
  number: string;
  session: SessionSummary;
  title: string;
  short_title: string | null;
  status: string | null;
  status_code: string | null;
  status_date: string | null;
  is_law: boolean;
  is_private_members_bill: boolean;
  chamber: string | null;
  sponsor_name: string | null;
  sponsor_url: string | null;
  sponsor_party: string | null;
  sponsor_riding: string | null;
  summary_html: string | null;
  has_library_summary: boolean;
  library_summary_url: string | null;
  rag_scope: KnowledgeChunkScopePayload | null;
}

export interface BillDetailPayload {
  bill: BillDetailDataPayload;
  similar_bills: BillReference[];
  same_number_bills: BillReference[];
  votes: VoteSummary[];
  debate: BillDebatePayload;
  committee_meetings: CommitteeMeetingPayload[];
}
