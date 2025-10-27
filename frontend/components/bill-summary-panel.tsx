import type { KnowledgeChunk } from "../lib/rag";

type BillSummaryPanelProps = {
  billNumber: string;
  chunks: KnowledgeChunk[];
};

export function BillSummaryPanel({ billNumber, chunks }: BillSummaryPanelProps) {
  if (!chunks.length) {
    return (
      <section className="rounded-lg border border-stone-800 bg-stone-900 p-4 text-stone-200">
        <header className="mb-2 flex items-center justify-between">
          <h2 className="text-lg font-semibold">Bill {billNumber} Summary</h2>
          <span className="text-xs uppercase tracking-wide text-stone-500">No context</span>
        </header>
        <p className="text-sm text-stone-400">
          We could not find supporting knowledge base entries for this bill yet.
        </p>
      </section>
    );
  }

  return (
    <section className="rounded-lg border border-stone-800 bg-stone-900 p-4 text-stone-200">
      <header className="mb-4 flex items-center justify-between">
        <h2 className="text-lg font-semibold">Bill {billNumber} Summary</h2>
        <span className="text-xs uppercase tracking-wide text-stone-500">
          {chunks.length} chunk{chunks.length > 1 ? "s" : ""}
        </span>
      </header>
      <div className="space-y-4">
        {chunks.map((chunk) => (
          <article key={chunk.id} className="rounded-md border border-stone-800 bg-stone-950 p-3">
            <h3 className="text-sm font-medium text-stone-100">{chunk.title}</h3>
            <p className="mt-2 whitespace-pre-line text-sm leading-relaxed text-stone-300">
              {chunk.content}
            </p>
            <dl className="mt-3 grid gap-2 text-xs text-stone-500 sm:grid-cols-2">
              <div className="flex items-center gap-1">
                <dt className="font-semibold">Jurisdiction:</dt>
                <dd>{chunk.jurisdiction}</dd>
              </div>
              <div className="flex items-center gap-1">
                <dt className="font-semibold">Updated:</dt>
                <dd>{new Date(chunk.updated_at).toLocaleString()}</dd>
              </div>
            </dl>
          </article>
        ))}
      </div>
    </section>
  );
}
