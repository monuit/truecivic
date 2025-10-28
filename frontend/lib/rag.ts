export type KnowledgeChunk = {
  id: number;
  title: string;
  content: string;
  source_type: string;
  source_identifier: string;
  jurisdiction: string;
  language: string;
  updated_at: string;
};

export type KnowledgeChunkScope = {
  source_type: string;
  source_identifier: string;
};

type KnowledgeChunkScopeLike = KnowledgeChunkScope | {
  source_type: string;
  source_identifier: string;
};

type FetchKnowledgeChunkOptions = {
  limit?: number;
  init?: RequestInit;
};

const DEFAULT_LIMIT = 3;

function resolveChunksEndpoint(): string {
  if (process.env.NEXT_PUBLIC_RAG_CHUNKS_ENDPOINT) {
    return process.env.NEXT_PUBLIC_RAG_CHUNKS_ENDPOINT;
  }
  if (process.env.NEXT_PUBLIC_API_BASE_URL) {
    return `${process.env.NEXT_PUBLIC_API_BASE_URL}/api/rag/chunks`;
  }
  return "/api/rag/chunks";
}

function normalizeBillIdentifier(identifier: string): string {
  const trimmed = identifier.trim();
  return trimmed.startsWith("bill:") ? trimmed : `bill:${trimmed}`;
}

export async function fetchKnowledgeChunks(
  scope: KnowledgeChunkScopeLike | null | undefined,
  options: FetchKnowledgeChunkOptions = {},
): Promise<KnowledgeChunk[]> {
  if (!scope?.source_type || !scope.source_identifier) {
    return [];
  }
  const { limit = DEFAULT_LIMIT, init } = options;
  const cappedLimit = Math.max(1, Math.min(limit, 25));
  const endpoint = resolveChunksEndpoint();
  const searchParams = new URLSearchParams({
    source_type: scope.source_type,
    source_identifier: scope.source_identifier,
    limit: String(cappedLimit),
  });

  const requestInit: RequestInit = { cache: "no-store", ...(init || {}) };
  const response = await fetch(`${endpoint}?${searchParams.toString()}`, requestInit);

  if (!response.ok) {
    throw new Error(`Failed to load knowledge chunks: ${response.status}`);
  }

  const payload = await response.json();
  if (!payload || !Array.isArray(payload.chunks)) {
    return [];
  }
  return payload.chunks as KnowledgeChunk[];
}

export async function fetchBillSummaries(
  identifier: string,
  limit: number = DEFAULT_LIMIT,
  init?: RequestInit,
): Promise<KnowledgeChunk[]> {
  const scope: KnowledgeChunkScope = {
    source_type: "bill",
    source_identifier: normalizeBillIdentifier(identifier),
  };
  return fetchKnowledgeChunks(scope, { limit, init });
}

export async function fetchKnowledgePreview(
  scope: KnowledgeChunkScopeLike | null | undefined,
  limit: number = 1,
  init?: RequestInit,
): Promise<KnowledgeChunk[]> {
  const previewLimit = Math.max(1, limit);
  return fetchKnowledgeChunks(scope, { limit: previewLimit, init });
}
