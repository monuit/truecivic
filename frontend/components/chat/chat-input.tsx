"use client";

import { FormEvent } from "react";

type Props = {
  input: string;
  disabled: boolean;
  onInputChangeAction: (event: React.ChangeEvent<HTMLTextAreaElement>) => void;
  onSubmitAction: (event: FormEvent<HTMLFormElement>) => void;
};

export default function ChatInput({ input, disabled, onInputChangeAction, onSubmitAction }: Props) {
  return (
    <form onSubmit={onSubmitAction} className="flex flex-col gap-3">
      <textarea
        value={input}
        onChange={onInputChangeAction}
        className="min-h-28 resize-y rounded-md bg-stone-900 p-3 text-base text-stone-50 outline-none"
        placeholder="Ask about bills, debates, committees, or MPs..."
        disabled={disabled}
        required
      />
      <button
        type="submit"
        disabled={disabled}
        className="self-end rounded-md bg-emerald-500 px-4 py-2 text-sm font-medium text-emerald-950 disabled:opacity-40"
      >
        Send
      </button>
    </form>
  );
}
