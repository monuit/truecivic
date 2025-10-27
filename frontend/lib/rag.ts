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
  return identifier.startsWith("bill:") ? identifier : `bill:${identifier}`;
}

export async function fetchBillSummaries(
  identifier: string,
  limit: number = DEFAULT_LIMIT,
  init?: RequestInit,
): Promise<KnowledgeChunk[]> {
  const endpoint = resolveChunksEndpoint();
  const searchParams = new URLSearchParams({
    source_type: "bill",
    source_identifier: normalizeBillIdentifier(identifier),
    limit: String(Math.max(1, Math.min(limit, 25))),
  });

  const response = await fetch(`${endpoint}?${searchParams.toString()}`, {
    cache: "no-store",
    ...init,
  });

  if (!response.ok) {
    throw new Error(`Failed to load bill summaries: ${response.status}`);
  }

  const payload = await response.json();
  if (!payload || !Array.isArray(payload.chunks)) {
    return [];
  }
  return payload.chunks as KnowledgeChunk[];
}
