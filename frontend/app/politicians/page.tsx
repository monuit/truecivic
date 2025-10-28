import { PoliticianListPage } from "../../components/politicians/politician-list-page";
import { ApiError } from "../../components/common/api-error";
import { TrueCivicApiClient } from "../../lib/op-api";
import { readSingleParam } from "../../lib/url-params";

type PageSearchParams = Record<string, string | string[] | undefined>;

interface PoliticiansPageProps {
  searchParams?: PageSearchParams;
}

export default async function PoliticiansPage({ searchParams }: PoliticiansPageProps) {
  const rawStatus = readSingleParam(searchParams?.status);
  const status = rawStatus === "former" ? "former" : "current";
  const client = TrueCivicApiClient.fromEnv();

  try {
    const payload = await client.fetchPoliticianList({ status });
    return <PoliticianListPage payload={payload} status={status} />;
  } catch (error) {
    return (
      <ApiError
        title="Politicians"
        message="We could not load the roster of MPs right now. Please try again shortly."
        error={error}
      />
    );
  }
}
