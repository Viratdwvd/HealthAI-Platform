"""
RAG Service – FREE LOCAL VERSION
----------------------------------
Embeddings via sentence-transformers (local, free).
Vector storage via Qdrant (local Docker, free).
"""

from __future__ import annotations
import asyncio, sys, time
sys.path.insert(0, "/app/shared")

from fastapi import FastAPI, HTTPException
from prometheus_fastapi_instrumentator import Instrumentator

from config.settings import RAGSettings
from models.schemas import (
    DataChunk, RetrievalRequest, RetrievalResponse, RetrievedChunk,
    EmbeddingRequest, EmbeddingResponse, HealthResponse,
)
from messaging.kafka_client import KafkaConsumer, TOPIC_CHUNKS_READY
from embeddings.embedder import Embedder, EMBEDDING_DIM
from retrieval.vector_store import VectorStore
from retrieval.reranker import Reranker
from utils.logger import configure_logging, get_logger

settings = RAGSettings()
configure_logging("rag-service", settings.LOG_LEVEL)
log = get_logger(__name__)

app = FastAPI(title="RAG Service (Local/Free)", version="2.0.0")
Instrumentator().instrument(app).expose(app)

embedder:     Embedder | None      = None
vector_store: VectorStore | None   = None
reranker:     Reranker | None      = None
consumer:     KafkaConsumer | None = None
_bg_task:     asyncio.Task | None  = None


@app.on_event("startup")
async def startup() -> None:
    global embedder, vector_store, reranker, consumer, _bg_task

    # Use local sentence-transformers (no API key needed)
    embedder     = Embedder()

    # Override dimension from settings to match local model (384 vs 1536)
    vector_store = VectorStore(
        settings.VECTOR_DB_URL,
        settings.COLLECTION_NAME,
        EMBEDDING_DIM,   # 384 for local model
    )
    reranker     = Reranker(settings.RERANK_MODEL)
    await vector_store.ensure_collection()

    consumer = KafkaConsumer(
        settings.KAFKA_BOOTSTRAP,
        group_id="rag-service",
        topics=[TOPIC_CHUNKS_READY],
    )

    @consumer.on(TOPIC_CHUNKS_READY)
    async def handle_chunk(payload: dict) -> None:
        chunk = DataChunk(**payload)
        embedding = await embedder.embed_one(chunk.content)
        await vector_store.upsert(chunk, embedding)
        log.debug("chunk_indexed", chunk_id=str(chunk.chunk_id))

    await consumer.start()
    _bg_task = asyncio.create_task(consumer.consume())
    log.info("rag_service_started", mode="local/free", dim=EMBEDDING_DIM)


@app.on_event("shutdown")
async def shutdown() -> None:
    if _bg_task:   _bg_task.cancel()
    if consumer:   await consumer.stop()


@app.post("/retrieve", response_model=RetrievalResponse)
async def retrieve(req: RetrievalRequest):
    t0 = time.perf_counter()
    assert embedder and vector_store and reranker

    query_vec  = await embedder.embed_one(req.query)
    candidates = await vector_store.search(
        query_vec, req.tenant_id, top_k=req.top_k * 3, filters=req.filters
    )
    if req.use_rerank and candidates:
        candidates = await reranker.rerank(req.query, candidates, top_k=req.top_k)
    else:
        candidates = candidates[:req.top_k]

    return RetrievalResponse(
        query=req.query,
        chunks=candidates,
        latency_ms=(time.perf_counter() - t0) * 1000,
    )


@app.post("/embed", response_model=EmbeddingResponse)
async def embed(req: EmbeddingRequest):
    assert embedder
    vecs = await embedder.embed_batch(req.texts)
    return EmbeddingResponse(
        embeddings=vecs,
        model="BAAI/bge-small-en-v1.5",
        tokens=sum(len(t.split()) for t in req.texts),
    )


@app.get("/health", response_model=HealthResponse)
async def health():
    return HealthResponse(
        service="rag-service",
        details={"mode": "local/free", "embedding_model": "BAAI/bge-small-en-v1.5", "dim": EMBEDDING_DIM}
    )
