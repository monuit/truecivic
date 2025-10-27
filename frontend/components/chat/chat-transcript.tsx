"use client";

import type { Message } from "ai";

const BOT_ROLE = "assistant";

export default function ChatTranscript({ messages }: { messages: Message[] }) {
  if (messages.length === 0) {
    return (
      <div className="flex flex-1 items-center justify-center rounded-md border border-stone-800 bg-stone-900 text-sm text-stone-400">
        Ask about bills, debates, committees, or representatives.
      </div>
    );
  }

  return (
    <div className="flex flex-1 flex-col gap-4 overflow-y-auto rounded-md border border-stone-800 bg-stone-900 p-4 text-sm">
      {messages.map((message) => (
        <article key={message.id} className="flex flex-col gap-1">
          <span className="text-xs uppercase tracking-wide text-stone-500">
            {message.role === BOT_ROLE ? "TrueCivic" : "You"}
          </span>
          <p className="whitespace-pre-wrap leading-6 text-stone-100">{message.content}</p>
        </article>
      ))}
    </div>
  );
}
