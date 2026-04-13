# 🏥 HealthAI Platform

A **production-grade healthcare intelligence platform** built with a microservices + event-driven architecture.  
Accepts CSV/PDF data, answers natural language questions via RAG, forecasts trends, and exposes explainable AI responses — all with full observability.

---

## 📐 Architecture

```
┌──────────────────────────────────────────────────────────────────┐
│                        CLIENT (Next.js)                          │
└────────────────────────────┬─────────────────────────────────────┘
                             │ HTTPS
                             ▼
┌──────────────────────────────────────────────────────────────────┐
│              API GATEWAY  :8000                                   │
│     JWT auth · Rate limiting · Request routing                    │
└───┬──────────┬──────────┬──────────┬──────────┬──────────────────┘
    │          │          │          │          │
    ▼          ▼          ▼          ▼          ▼
┌───────┐ ┌───────┐ ┌─────────┐ ┌───────┐ ┌─────────┐
│Ingest │ │Agent  │ │Analytics│ │Session│ │   RAG   │
│ :8001 │ │ :8005 │ │  :8003  │ │ :8007 │ │  :8002  │
└───┬───┘ └───┬───┘ └─────────┘ └───────┘ └─────────┘
    │         │
    │ Kafka   │ calls
    ▼         ▼
┌───────┐ ┌─────────────────────────────────────────┐
│Qdrant │ │  LLM Service :8006  │  Knowledge :8004  │
│Vector │ │  OpenAI / Anthropic  │  Rule Engine      │
│  DB   │ └─────────────────────────────────────────┘
└───────┘

Infrastructure: Kafka · Redis · PostgreSQL · Qdrant
Observability:  Prometheus · Grafana · Jaeger (OTLP)
```

### Query Data Flow

```
User Query
    │
    ▼ API Gateway (auth + rate limit)
    │
    ▼ Agent Orchestrator
    │   ├─ LLM Planner → Intent + Execution Plan
    │   ├─ [parallel] RAG Service  →  vector search + rerank
    │   ├─ [parallel] Knowledge Service → rule matching
    │   └─ [if needed] Analytics Service → stats / forecast
    │
    ▼ LLM Service (GPT-4o → Claude fallback)
    │   └─ Context-grounded answer generation
    │
    ▼ QueryResponse { answer, sources, confidence, reasoning }
```

---

## 🗂️ Project Structure

```
healthcare-platform/
├── api-gateway/                  # JWT auth, rate limiting, proxy
│   ├── main.py
│   └── middleware/
│       ├── auth.py               # JWT bearer token
│       └── rate_limit.py         # Redis sliding-window limiter
│
├── services/
│   ├── ingestion-service/        # CSV/PDF parse → chunk → Kafka
│   │   ├── main.py
│   │   ├── parsers/              # csv_parser.py, pdf_parser.py
│   │   ├── processors/           # chunker.py, validator.py
│   │   └── tests/
│   │
│   ├── rag-service/              # embed → Qdrant → rerank
│   │   ├── main.py
│   │   ├── embeddings/           # embedder.py (OpenAI + cache)
│   │   ├── retrieval/            # vector_store.py, reranker.py
│   │   └── tests/
│   │
│   ├── analytics-service/        # forecast (Prophet/ARIMA) + stats
│   │   ├── main.py
│   │   ├── models/               # forecaster.py, summarizer.py
│   │   └── tests/
│   │
│   ├── knowledge-service/        # YAML rule engine + ontology
│   │   ├── main.py
│   │   ├── rules/                # rule_engine.py + rules.yaml
│   │   └── tests/
│   │
│   ├── agent-orchestrator/       # LLM planner + parallel execution
│   │   ├── main.py
│   │   ├── planner/              # intent_planner.py
│   │   └── tests/
│   │
│   ├── llm-service/              # OpenAI/Anthropic + Redis cache
│   │   └── main.py
│   │
│   └── session-service/          # Redis-backed conversation memory
│       └── main.py
│
├── shared/                       # Cross-service code
│   ├── models/schemas.py         # ALL Pydantic models
│   ├── config/settings.py        # Per-service pydantic-settings
│   ├── messaging/kafka_client.py # Async Kafka publish/consume
│   └── utils/logger.py           # Structlog + OpenTelemetry
│
├── frontend/                     # Next.js 14 + Tailwind
│   └── src/
│       ├── app/                  # page.tsx, chat/, upload/, analytics/
│       ├── components/           # Sidebar, ChatInterface, FileUploadZone…
│       ├── hooks/                # useAuthStore, useJobStore
│       ├── lib/api.ts            # Typed API client
│       └── types/index.ts
│
├── infrastructure/
│   ├── k8s/
│   │   ├── deployments/          # api-gateway.yaml, microservices.yaml, ingress.yaml
│   │   └── configmaps/           # platform-config.yaml (namespace + secrets)
│   └── monitoring/
│       ├── prometheus.yml
│       └── grafana-datasources.yml
│
├── scripts/
│   ├── seed_demo.py              # Upload demo data + run sample queries
│   └── healthcheck.sh            # Ping all /health endpoints
│
├── docker-compose.yml            # Full local stack (15 containers)
├── pyproject.toml                # Ruff + Mypy + Pytest config
├── .env.example                  # Environment variable template
└── .github/workflows/ci.yml     # GitHub Actions CI/CD
```

---

## ⚡ Quick Start (Docker Compose)

### Prerequisites
- Docker Desktop ≥ 4.25 (with 8 GB RAM allocated)
- `docker compose` v2
- OpenAI API key (required for embeddings + LLM)

### 1. Clone & configure

```bash
git clone https://github.com/your-org/healthcare-platform.git
cd healthcare-platform

cp .env.example .env
# Edit .env — at minimum set:
#   OPENAI_API_KEY=sk-...
#   SECRET_KEY=<random 32+ char string>
```

### 2. Start the platform

```bash
docker compose up --build -d
```

Startup takes ~2 minutes the first time (image builds + Kafka init).

### 3. Verify everything is running

```bash
./scripts/healthcheck.sh
# or:
docker compose ps
```

### 4. Seed demo data

```bash
pip install httpx
python scripts/seed_demo.py
```

### 5. Open the UI

| Service        | URL                          |
|----------------|------------------------------|
| Frontend       | http://localhost:3000        |
| API Docs       | http://localhost:8000/docs   |
| Grafana        | http://localhost:3001 (admin/admin) |
| Prometheus     | http://localhost:9090        |
| Jaeger UI      | http://localhost:16686       |
| Qdrant UI      | http://localhost:6333/dashboard |

---

## 🔌 API Reference

All requests go through the **API Gateway** on `:8000`.  
Authenticate first, then use the JWT token in `Authorization: Bearer <token>`.

### Authentication

```bash
curl -X POST http://localhost:8000/auth/token \
  -H "Content-Type: application/json" \
  -d '{"username":"demo_user","password":"demo","tenant_id":"tenant-demo"}'
```

### Upload a file

```bash
# Encode file
B64=$(base64 -w0 patients.csv)

curl -X POST http://localhost:8000/api/v1/ingest \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d "{
    \"file_name\": \"patients.csv\",
    \"file_type\": \"csv\",
    \"content_b64\": \"$B64\",
    \"tenant_id\": \"tenant-demo\",
    \"user_id\": \"demo_user\",
    \"tags\": [\"patients\"]
  }"
```

### Query the platform

```bash
curl -X POST http://localhost:8000/api/v1/query \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "What are the most common diagnoses?",
    "tenant_id": "tenant-demo",
    "user_id": "demo_user"
  }'
```

**Response:**
```json
{
  "query": "What are the most common diagnoses?",
  "answer": "Based on the patient dataset, the most common diagnoses are...",
  "intent": "retrieval",
  "sources": [
    { "chunk_id": "...", "source": "patients.csv", "score": 0.94, "content": "..." }
  ],
  "confidence": 0.91,
  "reasoning": "Used RAG retrieval over patients.csv to find diagnosis frequencies.",
  "latency_ms": 820
}
```

### Run a forecast

```bash
curl -X POST http://localhost:8000/api/v1/analytics \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "tenant_id": "tenant-demo",
    "dataset_id": "admissions",
    "operation": "forecast",
    "params": {
      "horizon": 30,
      "data": [
        {"ds": "2024-01-01", "y": 42},
        {"ds": "2024-01-02", "y": 38}
      ]
    }
  }'
```

---

## 🧪 Running Tests

```bash
# Install test deps
pip install pytest pytest-asyncio pytest-cov pandas statsmodels pyyaml fastapi httpx pydantic pydantic-settings

# Run all tests
PYTHONPATH=shared pytest

# Run a specific service
PYTHONPATH=shared:services/ingestion-service \
  pytest services/ingestion-service/tests/ -v

# With coverage
PYTHONPATH=shared pytest --cov=services --cov-report=html
```

---

## 🚀 Kubernetes Deployment

```bash
# 1. Create namespace + secrets
kubectl apply -f infrastructure/k8s/configmaps/platform-config.yaml

# Edit the secret values first!
kubectl create secret generic platform-secrets \
  --from-literal=secret-key="$(openssl rand -hex 32)" \
  --from-literal=openai-api-key="sk-..." \
  --from-literal=anthropic-api-key="sk-ant-..." \
  -n healthcare

# 2. Deploy all microservices
kubectl apply -f infrastructure/k8s/deployments/

# 3. Watch rollout
kubectl rollout status deployment/api-gateway -n healthcare

# 4. Check pods
kubectl get pods -n healthcare
```

---

## ⚙️ Configuration Reference

| Variable                | Default                           | Description                      |
|-------------------------|-----------------------------------|----------------------------------|
| `SECRET_KEY`            | *(required)*                      | JWT signing secret               |
| `OPENAI_API_KEY`        | *(required)*                      | OpenAI API key                   |
| `ANTHROPIC_API_KEY`     | *(optional)*                      | Fallback LLM                     |
| `KAFKA_BOOTSTRAP`       | `kafka:9092`                      | Kafka broker address             |
| `REDIS_URL`             | `redis://redis:6379/0`            | Redis connection string          |
| `VECTOR_DB_URL`         | `http://qdrant:6333`              | Qdrant vector DB                 |
| `POSTGRES_DSN`          | `postgresql+asyncpg://...`        | Analytics DB                     |
| `EMBEDDING_MODEL`       | `text-embedding-3-small`          | OpenAI embedding model           |
| `DEFAULT_MODEL`         | `gpt-4o`                          | Primary LLM                      |
| `FALLBACK_MODEL`        | `claude-3-5-sonnet-20241022`      | Fallback LLM                     |
| `LOG_LEVEL`             | `INFO`                            | Logging level                    |
| `OTLP_ENDPOINT`         | `http://jaeger:4317`              | Tracing collector                |

---

## 🔒 Security Notes

- All inter-service communication is on a private Docker/K8s network
- JWT tokens expire after 1 hour (configurable via `ACCESS_TOKEN_EXPIRE`)
- Rate limiting: 60 req/min per IP (Redis sliding window)
- File validation: magic-byte check + size limit (50 MB)
- Tenant isolation: all vector DB queries are filtered by `tenant_id`
- **Never commit your `.env` file — it is in `.gitignore`**

---

## 📊 Observability

| Tool        | URL                    | Purpose                    |
|-------------|------------------------|----------------------------|
| Grafana     | :3001                  | Dashboards (metrics)       |
| Prometheus  | :9090                  | Metrics scraping           |
| Jaeger      | :16686                 | Distributed tracing        |

Every FastAPI service exposes `/metrics` (Prometheus format) and sends OTLP spans to Jaeger automatically via `configure_tracing()` in `shared/utils/logger.py`.

---

## 🤝 Contributing

1. Fork the repo
2. Create a feature branch: `git checkout -b feat/my-feature`
3. Write tests for your changes
4. Run `ruff check . && pytest` before pushing
5. Open a pull request — CI will run automatically

---

## 📄 License

MIT License — see `LICENSE` for details.
