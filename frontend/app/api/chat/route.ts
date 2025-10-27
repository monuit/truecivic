import { streamText } from "ai";
import { z } from "zod";

import { openai } from "../../../lib/ai";

type RuntimeEnv = Record<string, string | undefined>;

const runtimeEnv: RuntimeEnv =
  (globalThis as { process?: { env?: RuntimeEnv } }).process?.env ?? {};

const DEFAULT_JURISDICTION =
  runtimeEnv.NEXT_PUBLIC_DEFAULT_JURISDICTION ?? "canada-federal";
const DEFAULT_LANGUAGE = runtimeEnv.NEXT_PUBLIC_DEFAULT_LANGUAGE ?? "en";

const MessageSchema = z.object({
  id: z.string(),
  role: z.enum(["user", "assistant", "system"]),
  content: z.string(),
});

const RequestSchema = z.object({
  model: z.string().optional(),
  messages: z.array(MessageSchema),
});

type Message = z.infer<typeof MessageSchema>;

type RagChunk = {
  id: number;
  title: string;
  content: string;
  jurisdiction: string;
  language: string;
};

type RagContextResponse = {
  chunks: RagChunk[];
  nia: Array<Record<string, unknown>>;
};

async function fetchContext(messages: Message[]): Promise<RagContextResponse> {
  const endpoint =
    runtimeEnv.RAG_CONTEXT_ENDPOINT ??
    (runtimeEnv.NEXT_PUBLIC_API_BASE_URL
      ? `${runtimeEnv.NEXT_PUBLIC_API_BASE_URL}/api/rag/context`
      : "/api/rag/context");
  try {
    const response = await fetch(endpoint, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        messages,
        jurisdiction: DEFAULT_JURISDICTION,
        language: DEFAULT_LANGUAGE,
      }),
    });

    if (!response.ok) {
      return { chunks: [], nia: [] };
    }

    const data = await response.json();
    return {
      chunks: Array.isArray(data.chunks) ? data.chunks : [],
      nia: Array.isArray(data.nia) ? data.nia : [],
    };
  } catch (error) {
    console.error("Context fetch failed", error);
    return { chunks: [], nia: [] };
  }
}

function buildPrompt(chunks: RagChunk[], nia: Array<Record<string, unknown>>): string {
  const sections: string[] = [];

  if (chunks.length) {
    const chunkText = chunks
      .map((chunk) => {
        return `Title: ${chunk.title}\nJurisdiction: ${chunk.jurisdiction}\nLanguage: ${chunk.language}\n${chunk.content}`;
      })
      .join("\n\n");
    sections.push(`Retrieved Knowledge:\n${chunkText}`);
  }

  if (nia.length) {
    const niaText = nia
      .map((entry) => JSON.stringify(entry, null, 2))
      .join("\n\n");
    sections.push(`NIA Insights:\n${niaText}`);
  }

  if (!sections.length) {
    return "Answer the final user question using your existing knowledge.";
  }

  return `Use the supplied context to answer the final user question.\n\n${sections.join("\n\n")}`;
}

export async function POST(request: Request) {
  const json = await request.json();
  const { model, messages } = RequestSchema.parse(json);
  const { chunks, nia } = await fetchContext(messages);
  const prompt = buildPrompt(chunks, nia);

  const result = await streamText({
    model: openai(model ?? runtimeEnv.VERCEL_AI_MODEL ?? "gpt-4o"),
    messages: [
      ...messages,
      {
        id: "context",
        role: "system",
        content: prompt,
      },
    ],
  });

  return result.toTextStreamResponse();
}
