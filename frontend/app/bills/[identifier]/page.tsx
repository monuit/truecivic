import Link from "next/link";

import { BillSummaryPanel } from "../../../components/bill-summary-panel";
import { fetchBillSummaries } from "../../../lib/rag";

async function loadSummaries(identifier: string) {
  try {
    return await fetchBillSummaries(identifier);
  } catch (error) {
    console.error("Failed to load bill summaries", error);
    return [];
  }
}

type BillPageProps = {
  params: {
    identifier: string;
  };
};

export default async function BillPage({ params }: BillPageProps) {
  const { identifier } = params;
  const chunks = await loadSummaries(identifier);
  const billLabel = identifier.toUpperCase();

  return (
    <main className="mx-auto flex min-h-screen max-w-4xl flex-col gap-6 bg-stone-950 p-6 text-white">
      <header className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-semibold">{billLabel}</h1>
          <p className="text-sm text-stone-400">
            Retrieval augmented insights captured from recent parliamentary records.
          </p>
        </div>
        <Link href="/" className="text-sm text-emerald-400 hover:underline">
          Back to chat
        </Link>
      </header>
      <BillSummaryPanel billNumber={billLabel} chunks={chunks} />
    </main>
  );
}
