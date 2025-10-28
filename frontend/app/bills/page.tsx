import { BillListPage } from "../../components/bills/bill-list-page";
import { ApiError } from "../../components/common/api-error";
import { TrueCivicApiClient } from "../../lib/op-api";
import { readPositiveInt, readSingleParam } from "../../lib/url-params";

type PageSearchParams = Record<string, string | string[] | undefined>;

interface BillsPageProps {
  searchParams?: PageSearchParams;
}

export default async function BillsPage({ searchParams }: BillsPageProps) {
  const sessionId = readSingleParam(searchParams?.session);
  const limit = readPositiveInt(searchParams?.limit);
  const client = TrueCivicApiClient.fromEnv();

  try {
    const payload = await client.fetchBillList({ sessionId, limit });
    return <BillListPage payload={payload} />;
  } catch (error) {
    return (
      <ApiError
        title="Bills"
        message="We could not load the bill listings. Please try again shortly."
        error={error}
      />
    );
  }
}
