"use client";

import { useState, KeyboardEvent } from "react";
import { Send, Loader2 } from "lucide-react";
import clsx from "clsx";

interface Props {
  placeholder?: string;
  onSubmit:     (query: string) => void;
  loading?:     boolean;
  autoFocus?:   boolean;
}

export function QueryBar({ placeholder, onSubmit, loading, autoFocus }: Props) {
  const [value, setValue] = useState("");

  const submit = () => {
    const q = value.trim();
    if (!q || loading) return;
    onSubmit(q);
    setValue("");
  };

  const onKey = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      submit();
    }
  };

  return (
    <div className="relative flex items-end gap-2">
      <textarea
        rows={1}
        value={value}
        onChange={(e) => setValue(e.target.value)}
        onKeyDown={onKey}
        placeholder={placeholder ?? "Ask a question…"}
        autoFocus={autoFocus}
        disabled={loading}
        className={clsx(
          "input flex-1 resize-none min-h-[44px] max-h-40 py-3 pr-12 leading-relaxed",
          "scrollbar-none"
        )}
        style={{ overflowY: "auto" }}
      />
      <button
        onClick={submit}
        disabled={!value.trim() || loading}
        className={clsx(
          "absolute right-2 bottom-2 w-8 h-8 rounded-lg flex items-center justify-center transition-all",
          value.trim() && !loading
            ? "bg-brand-600 hover:bg-brand-500 text-white"
            : "bg-surface-700 text-slate-600 cursor-not-allowed"
        )}
      >
        {loading ? (
          <Loader2 size={14} className="animate-spin" />
        ) : (
          <Send size={14} />
        )}
      </button>
    </div>
  );
}
