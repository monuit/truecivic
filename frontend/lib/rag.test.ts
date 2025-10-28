import { describe, it, expect, vi, afterEach, beforeEach } from "vitest";
import { fetchKnowledgeChunks, fetchKnowledgePreview } from "./rag";

const originalFetch = globalThis.fetch;
let fetchMock: ReturnType<typeof vi.fn>;

beforeEach(() => {
  fetchMock = vi.fn();
  globalThis.fetch = fetchMock as unknown as typeof fetch;
});

afterEach(() => {
  if (originalFetch) {
    globalThis.fetch = originalFetch;
  } else {
    // In older Node versions fetch may be undefined
    // eslint-disable-next-line @typescript-eslint/no-dynamic-delete
    delete (globalThis as { fetch?: typeof fetch }).fetch;
  }
  vi.restoreAllMocks();
});

describe("fetchKnowledgeChunks", () => {
  it("returns empty array without calling fetch when scope is null", async () => {
    const chunks = await fetchKnowledgeChunks(null);

    expect(chunks).toEqual([]);
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("returns empty array without calling fetch when scope is missing identifiers", async () => {
    // @ts-expect-error intentionally passing malformed scope for regression coverage
    const chunks = await fetchKnowledgeChunks({ source_type: "bill" });

    expect(chunks).toEqual([]);
    expect(fetchMock).not.toHaveBeenCalled();
  });
});

describe("fetchKnowledgePreview", () => {
  it("requests the preview endpoint with provided limit and returns chunks", async () => {
    const responsePayload = {
      chunks: [
        {
          id: 1,
          title: "Example chunk",
          content: "Preview content",
          source_type: "vote",
          source_identifier: "vote:test",
          jurisdiction: "canada-federal",
          language: "en",
          updated_at: new Date().toISOString(),
        },
      ],
    };
    fetchMock.mockResolvedValue({
      ok: true,
      json: async () => responsePayload,
    } as unknown as Response);

    const chunks = await fetchKnowledgePreview({ source_type: "vote", source_identifier: "vote:test" }, 2);

    expect(fetchMock).toHaveBeenCalledTimes(1);
    const requestUrl = fetchMock.mock.calls[0]?.[0] as string;
    expect(requestUrl).toContain("limit=2");
    expect(requestUrl).toContain("source_type=vote");
    expect(requestUrl).toContain("source_identifier=vote%3Atest");
    expect(chunks).toHaveLength(1);
    expect(chunks[0]?.title).toBe("Example chunk");
  });
});
