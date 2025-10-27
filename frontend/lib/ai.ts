import { createOpenAI } from "@ai-sdk/openai";

const apiKey = process.env.OPENAI_API_KEY;

if (!apiKey) {
  // eslint-disable-next-line no-console -- surfaced during development
  console.warn("OPENAI_API_KEY is not set. Chat streaming will fail.");
}

export const openai = createOpenAI({ apiKey });
