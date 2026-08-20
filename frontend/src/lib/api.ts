/**
 * Centralised API client.
 * Reads the JWT token from localStorage and injects it as a Bearer header.
 * In a real app, swap localStorage for a secure cookie / auth provider.
 */

import axios from "axios";
import type { IngestionJob, QueryResponse } from "@/types";

const BASE = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

const http = axios.create({ baseURL: BASE, timeout: 60_000 });

// Inject auth token
http.interceptors.request.use((config) => {
  const token = typeof window !== "undefined" ? localStorage.getItem("hai_token") : null;
  if (token) config.headers.Authorization = `Bearer ${token}`;
  return config;
});

// Extract error message
http.interceptors.response.use(
  (r) => r,
  (err) => {
    const msg =
      err?.response?.data?.detail ??
      err?.response?.data?.message ??
      err?.message ??
      "An unexpected error occurred";
    return Promise.reject(new Error(msg));
  }
);

// ── Auth ──────────────────────────────────────────────────────────────────────

async function login(username: string, password: string, tenant_id: string): Promise<string> {
  const { data } = await http.post("/auth/token", { username, password, tenant_id });
  localStorage.setItem("hai_token", data.access_token);
  return data.access_token;
}

function logout() {
  localStorage.removeItem("hai_token");
}

// ── Ingestion ─────────────────────────────────────────────────────────────────

async function ingest(payload: {
  file_name:   string;
  file_type:   string;
  content_b64: string;
  tags?:       string[];
  metadata?:   Record<string, any>;
}): Promise<IngestionJob> {
  const { data } = await http.post("/api/v1/ingest", payload);
  return data;
}

async function jobStatus(jobId: string): Promise<IngestionJob> {
  const { data } = await http.get(`/api/v1/ingest/${jobId}`);
  return data;
}

// ── Query ─────────────────────────────────────────────────────────────────────

async function query(payload: {
  query:      string;
  session_id?: string;
  context?:   Record<string, any>;
}): Promise<QueryResponse> {
  const { data } = await http.post("/api/v1/query", payload);
  return data;
}

// ── Analytics ─────────────────────────────────────────────────────────────────

async function analytics(payload: {
  operation:  string;
  dataset_id: string;
  params?:    Record<string, any>;
}): Promise<any> {
  const { data } = await http.post("/api/v1/analytics", payload);
  return data;
}

// ── Sessions ──────────────────────────────────────────────────────────────────

async function getSession(sessionId: string): Promise<any> {
  const { data } = await http.get(`/api/v1/sessions/${sessionId}`);
  return data;
}

async function deleteSession(sessionId: string): Promise<void> {
  await http.delete(`/api/v1/sessions/${sessionId}`);
}

// ── Health ────────────────────────────────────────────────────────────────────

async function health(): Promise<any> {
  const { data } = await http.get("/health");
  return data;
}

export const api = {
  login,
  logout,
  ingest,
  jobStatus,
  query,
  analytics,
  getSession,
  deleteSession,
  health,
};
