// ── Ingestion ──────────────────────────────────────────────────────────────────

export interface IngestionJob {
  job_id:     string;
  tenant_id:  string;
  user_id:    string;
  file_name:  string;
  file_type:  "csv" | "pdf" | "json";
  status:     "pending" | "running" | "done" | "failed";
  chunks:     number;
  error?:     string;
  created_at: string;
}

// ── Query ──────────────────────────────────────────────────────────────────────

export interface SourceAttribution {
  chunk_id: string;
  source:   string;
  content:  string;
  score:    number;
}

export interface QueryResponse {
  query:      string;
  answer:     string;
  intent:     string;
  sources:    SourceAttribution[];
  confidence: number;
  reasoning:  string;
  latency_ms: number;
  session_id?: string;
}

// ── Chat ───────────────────────────────────────────────────────────────────────

export interface ChatMessage {
  id:         string;
  role:       "user" | "assistant";
  content:    string;
  sources?:   SourceAttribution[];
  confidence?: number;
  intent?:    string;
  latency_ms?: number;
}

// ── Analytics ──────────────────────────────────────────────────────────────────

export interface ForecastResult {
  dates:      string[];
  values:     number[];
  lower_ci:   number[];
  upper_ci:   number[];
  model_used: string;
}

export interface AnalyticsResult {
  operation: string;
  forecast?: ForecastResult;
  stats?:    Record<string, any>;
}

// ── Auth ───────────────────────────────────────────────────────────────────────

export interface User {
  username:  string;
  tenant_id: string;
}
