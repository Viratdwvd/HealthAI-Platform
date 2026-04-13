"""
Shared Pydantic schemas for all microservices.
Single source of truth for data contracts.
"""

from __future__ import annotations
from enum import Enum
from typing import Any, Dict, List, Optional
from datetime import datetime
from uuid import UUID, uuid4
from pydantic import BaseModel, Field, validator


# ─── Enums ───────────────────────────────────────────────────────────────────

class FileType(str, Enum):
    CSV = "csv"
    PDF = "pdf"
    JSON = "json"

class JobStatus(str, Enum):
    PENDING   = "pending"
    RUNNING   = "running"
    DONE      = "done"
    FAILED    = "failed"

class QueryIntent(str, Enum):
    RETRIEVAL   = "retrieval"
    ANALYTICS   = "analytics"
    FORECAST    = "forecast"
    SUMMARY     = "summary"
    KNOWLEDGE   = "knowledge"
    MIXED       = "mixed"

class MessageRole(str, Enum):
    USER      = "user"
    ASSISTANT = "assistant"
    SYSTEM    = "system"


# ─── Base ─────────────────────────────────────────────────────────────────────

class TimestampedModel(BaseModel):
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: Optional[datetime] = None

    class Config:
        json_encoders = {datetime: lambda v: v.isoformat()}


# ─── Ingestion ────────────────────────────────────────────────────────────────

class IngestionRequest(BaseModel):
    file_name:   str
    file_type:   FileType
    content_b64: str                          # base-64 encoded bytes
    tenant_id:   str
    user_id:     str
    tags:        List[str] = Field(default_factory=list)
    metadata:    Dict[str, Any] = Field(default_factory=dict)

class IngestionJob(TimestampedModel):
    job_id:     UUID = Field(default_factory=uuid4)
    tenant_id:  str
    user_id:    str
    file_name:  str
    file_type:  FileType
    status:     JobStatus = JobStatus.PENDING
    chunks:     int = 0
    error:      Optional[str] = None

class DataChunk(BaseModel):
    chunk_id:   UUID = Field(default_factory=uuid4)
    job_id:     UUID
    tenant_id:  str
    source:     str
    content:    str
    page:       Optional[int] = None
    row_start:  Optional[int] = None
    row_end:    Optional[int] = None
    metadata:   Dict[str, Any] = Field(default_factory=dict)


# ─── RAG ──────────────────────────────────────────────────────────────────────

class EmbeddingRequest(BaseModel):
    texts:     List[str]
    tenant_id: str
    model:     str = "text-embedding-3-small"

class EmbeddingResponse(BaseModel):
    embeddings: List[List[float]]
    model:      str
    tokens:     int

class RetrievalRequest(BaseModel):
    query:       str
    tenant_id:   str
    top_k:       int = 10
    filters:     Dict[str, Any] = Field(default_factory=dict)
    use_rerank:  bool = True

class RetrievedChunk(BaseModel):
    chunk_id:   str
    content:    str
    source:     str
    score:      float
    metadata:   Dict[str, Any] = Field(default_factory=dict)

class RetrievalResponse(BaseModel):
    query:      str
    chunks:     List[RetrievedChunk]
    latency_ms: float


# ─── Analytics ───────────────────────────────────────────────────────────────

class AnalyticsRequest(BaseModel):
    tenant_id:  str
    dataset_id: str
    operation:  str                           # "forecast" | "summarize" | "stats"
    params:     Dict[str, Any] = Field(default_factory=dict)

class ForecastResult(BaseModel):
    dates:      List[str]
    values:     List[float]
    lower_ci:   List[float]
    upper_ci:   List[float]
    model_used: str

class AnalyticsResponse(BaseModel):
    operation:  str
    result:     Dict[str, Any]
    latency_ms: float


# ─── Agent / Query ────────────────────────────────────────────────────────────

class QueryRequest(BaseModel):
    query:      str
    tenant_id:  str
    user_id:    str
    session_id: Optional[str] = None
    context:    Dict[str, Any] = Field(default_factory=dict)

class PlanStep(BaseModel):
    step_id:   int
    service:   str                            # "rag" | "analytics" | "knowledge" | "llm"
    action:    str
    params:    Dict[str, Any] = Field(default_factory=dict)
    depends_on: List[int] = Field(default_factory=list)

class ExecutionPlan(BaseModel):
    plan_id:   UUID = Field(default_factory=uuid4)
    intent:    QueryIntent
    steps:     List[PlanStep]
    reasoning: str

class SourceAttribution(BaseModel):
    chunk_id: str
    source:   str
    content:  str
    score:    float

class QueryResponse(BaseModel):
    query:        str
    answer:       str
    intent:       QueryIntent
    sources:      List[SourceAttribution] = Field(default_factory=list)
    confidence:   float
    reasoning:    str
    latency_ms:   float
    session_id:   Optional[str] = None


# ─── Knowledge ───────────────────────────────────────────────────────────────

class KnowledgeRequest(BaseModel):
    query:     str
    tenant_id: str
    domains:   List[str] = Field(default_factory=list)

class KnowledgeResult(BaseModel):
    rules:     List[Dict[str, Any]]
    facts:     List[str]
    sources:   List[str]


# ─── Session ─────────────────────────────────────────────────────────────────

class ChatMessage(BaseModel):
    role:      MessageRole
    content:   str
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    metadata:  Dict[str, Any] = Field(default_factory=dict)

class Session(TimestampedModel):
    session_id: str = Field(default_factory=lambda: str(uuid4()))
    tenant_id:  str
    user_id:    str
    messages:   List[ChatMessage] = Field(default_factory=list)
    context:    Dict[str, Any] = Field(default_factory=dict)

    def add_message(self, role: MessageRole, content: str) -> None:
        self.messages.append(ChatMessage(role=role, content=content))
        self.updated_at = datetime.utcnow()

    def get_history_text(self, last_n: int = 10) -> str:
        recent = self.messages[-last_n:]
        return "\n".join(f"{m.role.upper()}: {m.content}" for m in recent)


# ─── LLM ─────────────────────────────────────────────────────────────────────

class LLMRequest(BaseModel):
    system_prompt: str
    user_prompt:   str
    history:       List[ChatMessage] = Field(default_factory=list)
    temperature:   float = 0.2
    max_tokens:    int = 2048
    model:         str = "gpt-4o"

class LLMResponse(BaseModel):
    content:    str
    model:      str
    tokens_in:  int
    tokens_out: int
    latency_ms: float


# ─── Health ───────────────────────────────────────────────────────────────────

class HealthResponse(BaseModel):
    service:    str
    status:     str = "ok"
    version:    str = "1.0.0"
    timestamp:  datetime = Field(default_factory=datetime.utcnow)
    details:    Dict[str, Any] = Field(default_factory=dict)
