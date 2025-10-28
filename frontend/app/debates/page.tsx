import { DebateListPage } from "../../components/debates/debate-list-page";
import { ApiError } from "../../components/common/api-error";
import { TrueCivicApiClient } from "../../lib/op-api";
import { readPositiveInt } from "../../lib/url-params";

type PageSearchParams = Record<string, string | string[] | undefined>;

interface DebatesPageProps {
  searchParams?: PageSearchParams;
}

export default async function DebatesPage({ searchParams }: DebatesPageProps) {
  const limit = readPositiveInt(searchParams?.limit);
  const client = TrueCivicApiClient.fromEnv();

  try {
    const payload = await client.fetchDebateList({ limit });
    return <DebateListPage payload={payload} />;
  } catch (error) {
    return (
      <ApiError
        title="Debates"
        message="We could not load the latest debates right now. Please try again shortly."
        error={error}
      />
    );
  }
}
