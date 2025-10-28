import { notFound } from "next/navigation";

import { VoteDetailPage as VoteDetailView } from "../../../../components/votes/vote-detail-page";
import { ApiError } from "../../../../components/common/api-error";
import { TrueCivicApiClient } from "../../../../lib/op-api";
import { fetchKnowledgePreview } from "../../../../lib/rag";

interface VoteDetailRouteProps {
  params: {
    sessionId: string;
    number: string;
  };
}

export default async function VoteDetailRoute({ params }: VoteDetailRouteProps) {
  const sessionId = params.sessionId;
  const numberValue = Number.parseInt(params.number, 10);

  if (!sessionId || Number.isNaN(numberValue)) {
    notFound();
  }

  const client = TrueCivicApiClient.fromEnv();

  try {
    const payload = await client.fetchVoteDetail({
      sessionId,
      number: numberValue,
      init: { cache: "no-store" },
    });
    const knowledgeChunks = await fetchKnowledgePreview(payload.vote.rag_scope, 3);
    return <VoteDetailView payload={payload} knowledgeChunks={knowledgeChunks} />;
  } catch (error) {
    if (error instanceof Error && /status\s+404/.test(error.message)) {
      notFound();
    }
    return (
      <ApiError
        title="Vote detail"
        message="We could not load this vote. Please try again shortly."
        error={error}
      />
    );
  }
}
