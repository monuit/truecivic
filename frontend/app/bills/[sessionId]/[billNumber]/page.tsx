import { notFound } from "next/navigation";

import { BillDetailPage } from "../../../../components/bills/bill-detail-page";
import { ApiError } from "../../../../components/common/api-error";
import { TrueCivicApiClient } from "../../../../lib/op-api";
import type { KnowledgeChunkScopePayload } from "../../../../lib/op-api";
import { readPositiveInt, readSingleParam } from "../../../../lib/url-params";
import { fetchKnowledgeChunks } from "../../../../lib/rag";
import type { KnowledgeChunk } from "../../../../lib/rag";

interface BillDetailPageProps {
  params: {
    sessionId: string;
    billNumber: string;
  };
  searchParams?: Record<string, string | string[] | undefined>;
}

export default async function BillDetailRoute({ params, searchParams }: BillDetailPageProps) {
  const { sessionId, billNumber } = params;
  const tab = readSingleParam(searchParams?.tab);
  const page = readPositiveInt(searchParams?.page);
  const client = TrueCivicApiClient.fromEnv();

  try {
    const payload = await client.fetchBillDetail({
      sessionId,
      billNumber,
      tab,
      page,
      init: { cache: "no-store" },
    });
    const knowledgeChunks = await loadKnowledgeChunks(payload.bill.rag_scope);
    const basePath = `/bills/${encodeURIComponent(sessionId)}/${encodeURIComponent(billNumber)}`;
    return <BillDetailPage basePath={basePath} payload={payload} knowledgeChunks={knowledgeChunks} />;
  } catch (error) {
    if (error instanceof Error && /status\s+404/.test(error.message)) {
      notFound();
    }
    return (
      <ApiError
        title={`Bill ${billNumber}`}
        message="We could not load the bill details right now. Please try again later."
        error={error}
      />
    );
  }
}

async function loadKnowledgeChunks(scope: KnowledgeChunkScopePayload | null | undefined): Promise<KnowledgeChunk[]> {
  if (!scope) {
    return [];
  }
  try {
    return await fetchKnowledgeChunks(scope);
  } catch (error) {
    console.error("Failed to load knowledge chunks for bill detail", error);
    return [];
  }
}
