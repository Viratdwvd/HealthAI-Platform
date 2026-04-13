"""
Centralised configuration – FREE/LOCAL version.
All AI runs locally via Ollama + sentence-transformers.
No paid API keys required.
"""

from __future__ import annotations
from typing import Optional
from pydantic_settings import BaseSettings, SettingsConfigDict


class BaseServiceSettings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    LOG_LEVEL:           str = "INFO"
    ENVIRONMENT:         str = "development"
    KAFKA_BOOTSTRAP:     str = "kafka:9092"
    REDIS_URL:           str = "redis://redis:6379/0"
    OTLP_ENDPOINT:       str = "http://jaeger:4317"
    SECRET_KEY:          str = "dev-secret-change-in-production"


class APIGatewaySettings(BaseServiceSettings):
    PORT:                int  = 8000
    ALLOWED_ORIGINS:     str  = "*"
    JWT_ALGORITHM:       str  = "HS256"
    ACCESS_TOKEN_EXPIRE: int  = 3600
    RATE_LIMIT_PER_MIN:  int  = 60


class IngestionSettings(BaseServiceSettings):
    PORT:                int = 8001
    MAX_FILE_SIZE_MB:    int = 50
    CHUNK_SIZE:          int = 512
    CHUNK_OVERLAP:       int = 64


class RAGSettings(BaseServiceSettings):
    PORT:                int = 8002
    # No OpenAI key needed — uses local sentence-transformers
    OPENAI_API_KEY:      str = "not-needed"
    EMBEDDING_MODEL:     str = "BAAI/bge-small-en-v1.5"
    EMBEDDING_DIM:       int = 384          # local model dimension
    VECTOR_DB_URL:       str = "http://qdrant:6333"
    COLLECTION_NAME:     str = "healthcare_chunks"
    TOP_K:               int = 10
    RERANK_MODEL:        str = "cross-encoder/ms-marco-MiniLM-L-6-v2"


class AnalyticsSettings(BaseServiceSettings):
    PORT:                int = 8003
    POSTGRES_DSN:        str = "postgresql+asyncpg://postgres:postgres@postgres:5432/healthcare"
    FORECAST_HORIZON:    int = 30


class KnowledgeSettings(BaseServiceSettings):
    PORT:                int = 8004
    RULES_FILE:          str = "/app/rules/rules.yaml"
    UMLS_API_KEY:        Optional[str] = None


class AgentSettings(BaseServiceSettings):
    PORT:                  int = 8005
    LLM_SERVICE_URL:       str = "http://llm-service:8006"
    RAG_SERVICE_URL:       str = "http://rag-service:8002"
    ANALYTICS_SERVICE_URL: str = "http://analytics-service:8003"
    KNOWLEDGE_SERVICE_URL: str = "http://knowledge-service:8004"
    SESSION_SERVICE_URL:   str = "http://session-service:8007"
    MAX_PLAN_STEPS:        int = 8
    AGENT_TIMEOUT_S:       int = 60     # longer timeout for local models


class LLMSettings(BaseServiceSettings):
    PORT:                int = 8006
    # These are kept for interface compatibility but ignored
    # when OLLAMA_URL is set (which it is by default)
    OPENAI_API_KEY:      str = "not-needed"
    ANTHROPIC_API_KEY:   str = "not-needed"
    DEFAULT_MODEL:       str = "llama3.2"    # local Ollama model
    FALLBACK_MODEL:      str = "mistral"     # local Ollama fallback
    CACHE_TTL_S:         int = 300
    # Ollama configuration
    OLLAMA_URL:          str = "http://ollama:11434"


class SessionSettings(BaseServiceSettings):
    PORT:                int = 8007
    SESSION_TTL_S:       int = 86400
