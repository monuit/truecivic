"use client";

import { useMemo } from "react";
import { useChat } from "@ai-sdk/react";
import ChatInput from "./chat/chat-input";
import ChatTranscript from "./chat/chat-transcript";

const MODEL = process.env.NEXT_PUBLIC_CHAT_MODEL ?? "gpt-4o";

export default function ChatScreen() {
  const { messages, input, handleInputChange, handleSubmit, isLoading } = useChat({
    api: "/api/chat",
    body: { model: MODEL },
  });

  const disabled = useMemo(() => isLoading, [isLoading]);

  return (
    <div className="mx-auto flex min-h-screen max-w-4xl flex-col gap-4 bg-stone-950 p-6 text-white">
      <header className="flex flex-col gap-2">
        <h1 className="text-3xl font-semibold">TrueCivic</h1>
        <p className="text-sm text-stone-400">
          Intelligent parliamentary insights across jurisdictions.
        </p>
      </header>
      <ChatTranscript messages={messages} />
      <ChatInput
        input={input}
        disabled={disabled}
        onInputChangeAction={handleInputChange}
        onSubmitAction={handleSubmit}
      />
    </div>
  );
}
