/**
 * useStreamingQuery – React hook for streaming LLM responses via SSE.
 *
 * Usage:
 *   const { stream, tokens, isStreaming, error } = useStreamingQuery();
 *   await stream("What is the 30-day readmission rate?");
 */

"use client";

import { useCallback, useRef, useState } from "react";

interface StreamOptions {
  query:      string;
  sessionId?: string;
  onToken?:   (token: string) => void;
  onDone?:    (fullText: string, latencyMs: number) => void;
  onError?:   (err: string) => void;
}

interface StreamState {
  isStreaming: boolean;
  tokens:     string;
  error:      string | null;
  latencyMs:  number | null;
}

const BASE = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

export function useStreamingQuery() {
  const [state, setState] = useState<StreamState>({
    isStreaming: false,
    tokens:      "",
    error:       null,
    latencyMs:   null,
  });

  const abortRef = useRef<AbortController | null>(null);

  const stream = useCallback(async (opts: StreamOptions) => {
    const { query, sessionId, onToken, onDone, onError } = opts;

    // Cancel any in-progress stream
    abortRef.current?.abort();
    const controller = new AbortController();
    abortRef.current = controller;

    setState({ isStreaming: true, tokens: "", error: null, latencyMs: null });

    const token = typeof window !== "undefined"
      ? localStorage.getItem("hai_token") ?? ""
      : "";

    try {
      const resp = await fetch(`${BASE}/api/v1/query/stream`, {
        method: "POST",
        headers: {
          "Content-Type":  "application/json",
          "Authorization": `Bearer ${token}`,
        },
        body: JSON.stringify({
          query,
          session_id: sessionId,
          tenant_id:  "tenant-demo",
          user_id:    "demo_user",
        }),
        signal: controller.signal,
      });

      if (!resp.ok) {
        throw new Error(`HTTP ${resp.status}: ${resp.statusText}`);
      }

      const reader  = resp.body!.getReader();
      const decoder = new TextDecoder();
      let buffer    = "";
      let fullText  = "";

      // eslint-disable-next-line no-constant-condition
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split("\n");
        buffer = lines.pop() ?? "";

        for (const line of lines) {
          if (!line.startsWith("data: ")) continue;
          const raw = line.slice(6).trim();
          if (!raw) continue;

          try {
            const parsed = JSON.parse(raw);

            if (parsed.error) {
              setState((s) => ({ ...s, error: parsed.error, isStreaming: false }));
              onError?.(parsed.error);
              return;
            }

            if (parsed.done) {
              const latencyMs = parsed.latency_ms ?? null;
              setState((s) => ({ ...s, isStreaming: false, latencyMs }));
              onDone?.(fullText, latencyMs ?? 0);
              return;
            }

            if (parsed.token) {
              fullText += parsed.token;
              setState((s) => ({ ...s, tokens: fullText }));
              onToken?.(parsed.token);
            }
          } catch {
            // Ignore malformed SSE lines
          }
        }
      }

      setState((s) => ({ ...s, isStreaming: false }));
    } catch (err: any) {
      if (err?.name === "AbortError") {
        setState((s) => ({ ...s, isStreaming: false }));
        return;
      }
      const msg = err?.message ?? "Stream failed";
      setState((s) => ({ ...s, error: msg, isStreaming: false }));
      onError?.(msg);
    }
  }, []);

  const cancel = useCallback(() => {
    abortRef.current?.abort();
    setState((s) => ({ ...s, isStreaming: false }));
  }, []);

  return { ...state, stream, cancel };
}
