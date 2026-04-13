"""
shared/utils/metrics.py
-----------------------
Custom Prometheus metrics used across all services.
Import at service startup; the prometheus_fastapi_instrumentator
handles the /metrics endpoint automatically.

Usage:
    from utils.metrics import INGESTION_JOBS, LLM_TOKEN_COUNTER, QUERY_LATENCY

    INGESTION_JOBS.labels(status="done", tenant_id="t1").inc()
    LLM_TOKEN_COUNTER.labels(model="gpt-4o", direction="in").inc(450)
    with QUERY_LATENCY.labels(service="rag").time():
        results = await retriever.search(query)
"""

from __future__ import annotations

from prometheus_client import Counter, Gauge, Histogram, Summary

# ─── Ingestion metrics ────────────────────────────────────────────────────────

INGESTION_JOBS = Counter(
    "ingestion_jobs_total",
    "Total ingestion jobs processed",
    labelnames=["status", "tenant_id", "file_type"],
)

INGESTION_CHUNKS = Counter(
    "ingestion_chunks_total",
    "Total document chunks created",
    labelnames=["tenant_id", "file_type"],
)

INGESTION_FILE_SIZE = Histogram(
    "ingestion_file_size_bytes",
    "Uploaded file size distribution",
    buckets=[
        1_024, 10_240, 102_400, 512_000,
        1_048_576, 5_242_880, 10_485_760, 52_428_800,
    ],
    labelnames=["file_type"],
)

# ─── RAG / retrieval metrics ──────────────────────────────────────────────────

RETRIEVAL_LATENCY = Histogram(
    "retrieval_latency_seconds",
    "Time taken for RAG retrieval (vector search + rerank)",
    buckets=[0.05, 0.1, 0.25, 0.5, 1.0, 2.0, 5.0],
    labelnames=["retriever_type"],   # "dense" | "hybrid"
)

RETRIEVAL_CHUNKS_RETURNED = Histogram(
    "retrieval_chunks_returned",
    "Number of chunks returned per retrieval request",
    buckets=[1, 2, 3, 5, 8, 10, 15, 20, 30],
    labelnames=["tenant_id"],
)

EMBEDDING_LATENCY = Histogram(
    "embedding_latency_seconds",
    "Time taken to generate embeddings",
    buckets=[0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0],
    labelnames=["model"],
)

EMBEDDING_CACHE_HITS = Counter(
    "embedding_cache_hits_total",
    "Number of embedding cache hits",
    labelnames=["model"],
)

# ─── LLM metrics ─────────────────────────────────────────────────────────────

LLM_TOKEN_COUNTER = Counter(
    "llm_tokens_total",
    "Total LLM tokens processed",
    labelnames=["model", "direction"],   # direction: "in" | "out"
)

LLM_GENERATION_LATENCY = Histogram(
    "llm_generation_latency_seconds",
    "End-to-end LLM response generation time",
    buckets=[0.5, 1.0, 2.0, 5.0, 10.0, 20.0, 30.0, 60.0],
    labelnames=["model"],
)

LLM_CACHE_HITS = Counter(
    "llm_cache_hits_total",
    "Number of LLM response cache hits",
    labelnames=["model"],
)

LLM_FALLBACK_COUNTER = Counter(
    "llm_fallbacks_total",
    "Number of times the fallback LLM was used",
    labelnames=["primary", "fallback"],
)

# ─── Agent / query metrics ────────────────────────────────────────────────────

QUERY_LATENCY = Histogram(
    "query_latency_seconds",
    "End-to-end query latency (agent orchestration)",
    buckets=[0.1, 0.5, 1.0, 2.0, 5.0, 10.0, 30.0],
    labelnames=["intent"],
)

QUERY_CONFIDENCE = Histogram(
    "query_confidence",
    "Confidence score distribution for query responses",
    buckets=[0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0],
    labelnames=["intent"],
)

PLAN_STEPS = Histogram(
    "agent_plan_steps",
    "Number of steps in LLM-generated execution plans",
    buckets=[1, 2, 3, 4, 5, 6, 8, 10],
    labelnames=["intent"],
)

# ─── Session metrics ──────────────────────────────────────────────────────────

ACTIVE_SESSIONS = Gauge(
    "active_sessions",
    "Number of currently active user sessions",
    labelnames=["tenant_id"],
)

SESSION_MESSAGES = Histogram(
    "session_messages_total",
    "Distribution of messages per session",
    buckets=[1, 2, 5, 10, 20, 50, 100],
    labelnames=["tenant_id"],
)

# ─── Knowledge metrics ────────────────────────────────────────────────────────

KNOWLEDGE_RULES_MATCHED = Histogram(
    "knowledge_rules_matched",
    "Number of rules matched per lookup",
    buckets=[0, 1, 2, 3, 5, 8, 10],
    labelnames=["domain"],
)

# ─── Rate-limit metrics ───────────────────────────────────────────────────────

RATE_LIMIT_HITS = Counter(
    "rate_limit_hits_total",
    "Number of requests blocked by rate limiting",
    labelnames=["client_type"],
)
