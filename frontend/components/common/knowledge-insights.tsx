import type { KnowledgeChunk } from "../../lib/rag";

interface KnowledgeInsightsSectionProps {
  title: string;
  chunks: KnowledgeChunk[];
  emptyMessage: string;
  showWhenEmpty?: boolean;
  className?: string;
  entriesClassName?: string;
  entryClassName?: string;
  updatedClassName?: string;
  contentClassName?: string;
  titleTag?: "h2" | "h3";
}

export function KnowledgeInsightsSection({
  title,
  chunks,
  emptyMessage,
  showWhenEmpty = false,
  className,
  entriesClassName,
  entryClassName,
  updatedClassName,
  contentClassName,
  titleTag = "h3",
}: KnowledgeInsightsSectionProps) {
  if (!chunks.length && !showWhenEmpty) {
    return null;
  }

  const sectionClass = className ? `knowledge-section ${className}` : "knowledge-section";
  const entriesClass = entriesClassName ? entriesClassName : "knowledge-section__entries";
  const entryClass = entryClassName ? entryClassName : "knowledge-section__entry";
  const TitleTag = titleTag;

  return (
    <section className={sectionClass}>
      <TitleTag>{title}</TitleTag>
      {chunks.length ? (
        <div className={entriesClass}>
          {chunks.map((chunk) => (
            <article key={chunk.id} className={entryClass}>
              <header>
                <strong>{chunk.title}</strong>
                <span className={updatedClassName}>{formatUpdatedAt(chunk.updated_at)}</span>
              </header>
              <p className={contentClassName} style={{ whiteSpace: "pre-line" }}>
                {chunk.content}
              </p>
            </article>
          ))}
        </div>
      ) : (
        <p className="knowledge-section__empty">{emptyMessage}</p>
      )}
    </section>
  );
}

function formatUpdatedAt(value: string) {
  try {
    return new Intl.DateTimeFormat("en-CA", { dateStyle: "medium", timeStyle: "short" }).format(new Date(value));
  } catch (error) {
    console.warn("Failed to format knowledge chunk timestamp", value, error);
    return value;
  }
}
