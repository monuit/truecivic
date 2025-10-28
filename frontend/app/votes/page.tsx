import { VoteListPage } from "../../components/votes/vote-list-page";
import { ApiError } from "../../components/common/api-error";
import { TrueCivicApiClient } from "../../lib/op-api";
import { readPositiveInt, readSingleParam } from "../../lib/url-params";

type PageSearchParams = Record<string, string | string[] | undefined>;

interface VotesPageProps {
  searchParams?: PageSearchParams;
}

export default async function VotesPage({ searchParams }: VotesPageProps) {
  const sessionId = readSingleParam(searchParams?.session);
  const limit = readPositiveInt(searchParams?.limit);
  const client = TrueCivicApiClient.fromEnv();

  try {
    const payload = await client.fetchVoteList({ sessionId, limit });
    return <VoteListPage payload={payload} />;
  } catch (error) {
    return (
      <ApiError
        title="Votes"
        message="We could not load the vote listings. Please try again shortly."
        error={error}
      />
    );
  }
}
