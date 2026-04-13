"use client";

import { useState, useRef, useEffect, useCallback } from "react";
import { useSearchParams } from "next/navigation";
import { Send, Bot, User, ChevronDown, ExternalLink, AlertTriangle } from "lucide-react";
import clsx from "clsx";
import toast from "react-hot-toast";
import { api } from "@/lib/api";
import { QueryBar } from "./QueryBar";
import type { ChatMessage, QueryResponse } from "@/types";

export function ChatInterface() {
  const searchParams = useSearchParams();
  const initialQ     = searchParams.get("q") ?? "";

  const [messages,   setMessages]   = useState<ChatMessage[]>([]);
  const [sessionId,  setSessionId]  = useState<string | null>(null);
  const [loading,    setLoading]    = useState(false);
  const bottomRef = useRef<HTMLDivElement>(null);

  const scrollToBottom = () =>
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });

  useEffect(() => { scrollToBottom(); }, [messages]);

  const sendQuery = useCallback(
    async (query: string) => {
      if (!query.trim() || loading) return;

      const userMsg: ChatMessage = { role: "user", content: query, id: Date.now().toString() };
      setMessages((m) => [...m, userMsg]);
      setLoading(true);

      try {
        const resp: QueryResponse = await api.query({
          query,
          session_id: sessionId ?? undefined,
        });

        if (!sessionId && resp.session_id) setSessionId(resp.session_id);

        const assistantMsg: ChatMessage = {
          role:       "assistant",
          content:    resp.answer,
          id:         (Date.now() + 1).toString(),
          sources:    resp.sources,
          confidence: resp.confidence,
          intent:     resp.intent,
          latency_ms: resp.latency_ms,
        };
        setMessages((m) => [...m, assistantMsg]);
      } catch (err: any) {
        toast.error(err?.message ?? "Query failed. Check your API key.");
      } finally {
        setLoading(false);
      }
    },
    [loading, sessionId]
  );

  // Run initial query from URL param
  useEffect(() => {
    if (initialQ && messages.length === 0) sendQuery(initialQ);
  }, []); // eslint-disable-line

  return (
    <div className="flex flex-col h-full">
      {/* Message list */}
      <div className="flex-1 overflow-y-auto px-6 py-6 space-y-6">
        {messages.length === 0 && (
          <EmptyState onExample={sendQuery} />
        )}
        {messages.map((msg) =>
          msg.role === "user" ? (
            <UserBubble key={msg.id} message={msg} />
          ) : (
            <AssistantBubble key={msg.id} message={msg} />
          )
        )}
        {loading && <ThinkingBubble />}
        <div ref={bottomRef} />
      </div>

      {/* Input */}
      <div className="border-t border-surface-800 px-6 py-4 bg-surface-900">
        <QueryBar
          placeholder="Ask a clinical or operational question…"
          onSubmit={sendQuery}
          loading={loading}
          autoFocus
        />
        <p className="text-[10px] text-slate-600 mt-2 text-center">
          AI responses may contain errors. Always verify clinical information with qualified professionals.
        </p>
      </div>
    </div>
  );
}

// ── Sub-components ────────────────────────────────────────────────────────────

function UserBubble({ message }: { message: ChatMessage }) {
  return (
    <div className="flex justify-end gap-3 animate-slide-up">
      <div className="max-w-[70%] bg-brand-600 text-white rounded-2xl rounded-tr-sm px-4 py-3 text-sm leading-relaxed">
        {message.content}
      </div>
      <div className="w-8 h-8 rounded-full bg-surface-700 flex items-center justify-center shrink-0">
        <User size={14} className="text-slate-300" />
      </div>
    </div>
  );
}

function AssistantBubble({ message }: { message: ChatMessage }) {
  const [showSources, setShowSources] = useState(false);
  const hasSources = (message.sources?.length ?? 0) > 0;

  return (
    <div className="flex gap-3 animate-slide-up">
      <div className="w-8 h-8 rounded-full bg-brand-600/20 border border-brand-500/30 flex items-center justify-center shrink-0">
        <Bot size={14} className="text-brand-400" />
      </div>
      <div className="flex-1 max-w-[80%] space-y-2">
        {/* Meta badges */}
        <div className="flex items-center gap-2 flex-wrap">
          {message.intent && (
            <span className="badge badge-blue">{message.intent}</span>
          )}
          {message.confidence != null && (
            <ConfidenceBadge value={message.confidence} />
          )}
          {message.latency_ms != null && (
            <span className="badge bg-surface-800 text-slate-500">
              {Math.round(message.latency_ms)}ms
            </span>
          )}
        </div>

        {/* Answer */}
        <div className="card px-4 py-3 text-sm text-slate-200 leading-relaxed whitespace-pre-wrap">
          {message.content}
        </div>

        {/* Sources */}
        {hasSources && (
          <div>
            <button
              onClick={() => setShowSources((v) => !v)}
              className="flex items-center gap-1.5 text-xs text-slate-500 hover:text-slate-300 transition-colors"
            >
              <ChevronDown
                size={12}
                className={clsx("transition-transform", showSources && "rotate-180")}
              />
              {message.sources!.length} source{message.sources!.length > 1 ? "s" : ""}
            </button>
            {showSources && (
              <div className="mt-2 space-y-2">
                {message.sources!.map((src, i) => (
                  <SourceCard key={src.chunk_id} index={i + 1} source={src} />
                ))}
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

function SourceCard({ index, source }: { index: number; source: any }) {
  return (
    <div className="card px-3 py-2.5 text-xs space-y-1">
      <div className="flex items-center gap-2">
        <span className="badge badge-blue">[{index}]</span>
        <span className="text-slate-400 truncate flex-1">{source.source}</span>
        <span className="text-slate-600">{(source.score * 100).toFixed(0)}%</span>
      </div>
      <p className="text-slate-500 line-clamp-2">{source.content}</p>
    </div>
  );
}

function ConfidenceBadge({ value }: { value: number }) {
  const pct = Math.round(value * 100);
  const cls =
    pct >= 75 ? "badge-green" : pct >= 50 ? "badge-yellow" : "badge-red";
  return (
    <span className={clsx("badge", cls)}>
      {pct >= 50 ? null : <AlertTriangle size={10} />}
      {pct}% confidence
    </span>
  );
}

function ThinkingBubble() {
  return (
    <div className="flex gap-3 animate-fade-in">
      <div className="w-8 h-8 rounded-full bg-brand-600/20 border border-brand-500/30 flex items-center justify-center shrink-0">
        <Bot size={14} className="text-brand-400" />
      </div>
      <div className="card px-4 py-3 flex items-center gap-2">
        {[0, 1, 2].map((i) => (
          <span
            key={i}
            className="w-1.5 h-1.5 rounded-full bg-brand-400 animate-pulse-dot"
            style={{ animationDelay: `${i * 0.2}s` }}
          />
        ))}
        <span className="text-xs text-slate-500 ml-1">Thinking…</span>
      </div>
    </div>
  );
}

const EXAMPLES = [
  "What is the 30-day readmission rate for cardiac patients?",
  "Summarise the hypertension medication compliance trends",
  "Are there any drug interactions I should be aware of?",
  "Forecast ICU bed occupancy for the next 30 days",
];

function EmptyState({ onExample }: { onExample: (q: string) => void }) {
  return (
    <div className="flex flex-col items-center justify-center h-full py-20 text-center space-y-6 animate-fade-in">
      <div className="w-14 h-14 rounded-2xl bg-brand-600/15 border border-brand-500/20 flex items-center justify-center">
        <Bot size={24} className="text-brand-400" />
      </div>
      <div>
        <h2 className="text-lg font-semibold text-slate-200">Healthcare AI Assistant</h2>
        <p className="text-slate-500 text-sm mt-1 max-w-sm">
          Ask questions about your clinical data, run analytics, or explore clinical knowledge.
        </p>
      </div>
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 max-w-xl w-full">
        {EXAMPLES.map((q) => (
          <button
            key={q}
            onClick={() => onExample(q)}
            className="card p-3 text-left text-sm text-slate-400 hover:text-slate-200 hover:border-brand-500/40 transition-all duration-150"
          >
            {q}
          </button>
        ))}
      </div>
    </div>
  );
}
