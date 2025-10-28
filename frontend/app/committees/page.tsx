import { CommitteeListPage } from "../../components/committees/committee-list-page";
import { ApiError } from "../../components/common/api-error";
import { TrueCivicApiClient } from "../../lib/op-api";
import { readPositiveInt } from "../../lib/url-params";

type PageSearchParams = Record<string, string | string[] | undefined>;

interface CommitteesPageProps {
  searchParams?: PageSearchParams;
}

export default async function CommitteesPage({ searchParams }: CommitteesPageProps) {
  const limit = readPositiveInt(searchParams?.limit);
  const client = TrueCivicApiClient.fromEnv();

  try {
    const payload = await client.fetchCommitteeList({ limit });
    return <CommitteeListPage payload={payload} />;
  } catch (error) {
    return (
      <ApiError
        title="Committees"
        message="We could not load committee information right now. Please try again shortly."
        error={error}
      />
    );
  }
}
