"""
RAG Service – FREE version
--------------------------
Uses sentence-transformers locally instead of OpenAI embeddings.
No API key required. Model downloads automatically (~90MB).
"""

from __future__ import annotations
import asyncio
import sys
import time

sys.path.insert(0, "/app/shared")

from fastapi import FastAPI, HTTPException
from prometheus_fastapi_instrumentator import Instrumentator

from config.settings import RAGSettings
from models.schemas import (
    DataChunk, RetrievalRequest, RetrievalResponse, RetrievedChunk,
    EmbeddingRequest, EmbeddingResponse, HealthResponse,
)
from messaging.kafka_client import KafkaConsumer, TOPIC_CHUNKS_READY
from embeddings.local_embedder import get_embedder, LocalEmbedder
from retrieval.vector_store import VectorStore
from retrieval.reranker import Reranker
from utils.logger import configure_logging, get_logger

settings = RAGSettings()
configure_logging("rag-service-free", settings.LOG_LEVEL)
log = get_logger(__name__)

app = FastAPI(title="RAG Service (Free – Local Embeddings)", version="2.0.0")
Instrumentator().instrument(app).expose(app)

embedder:     LocalEmbedder | None = None
vector_store: VectorStore    | None = None
reranker:     Reranker       | None = None
consumer:     KafkaConsumer  | None = None
_bg_task:     asyncio.Task   | None = None


@app.on_event("startup")
async def startup() -> None:
    global embedder, vector_store, reranker, consumer, _bg_task

    # Local embedder – no API key needed
    embedder = get_embedder()
    log.info("using_local_embeddings", model=embedder._model_name, dim=embedder.dim)

    # Use whatever dim the local model has (not hardcoded to 1536)
    vector_store = VectorStore(
        settings.VECTOR_DB_URL,
        settings.COLLECTION_NAME,
        embedder.dim,   # ← dynamic dim from local model
    )
    reranker = Reranker(settings.RERANK_MODEL)
    await vector_store.ensure_collection()

    consumer = KafkaConsumer(
        settings.KAFKA_BOOTSTRAP,
        group_id="rag-service-free",
        topics=[TOPIC_CHUNKS_READY],
    )

    @consumer.on(TOPIC_CHUNKS_READY)
    async def handle_chunk(payload: dict) -> None:
        chunk     = DataChunk(**payload)
        embedding = await embedder.embed_one(chunk.content)
        await vector_store.upsert(chunk, embedding)
        log.debug("chunk_indexed", chunk_id=str(chunk.chunk_id))

    await consumer.start()
    _bg_task = asyncio.create_task(consumer.consume())
    log.info("rag_free_service_started")


@app.on_event("shutdown")
async def shutdown() -> None:
    if _bg_task:
        _bg_task.cancel()
    if consumer:
        await consumer.stop()


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
        candidates = candidates[: req.top_k]

    latency = (time.perf_counter() - t0) * 1000
    return RetrievalResponse(query=req.query, chunks=candidates, latency_ms=latency)


@app.post("/embed", response_model=EmbeddingResponse)
async def embed(req: EmbeddingRequest):
    assert embedder
    vecs   = await embedder.embed_batch(req.texts)
    tokens = sum(len(t.split()) for t in req.texts)
    return EmbeddingResponse(
        embeddings=vecs,
        model=embedder._model_name,
        tokens=tokens,
    )


@app.get("/health", response_model=HealthResponse)
async def health():
    dim = embedder.dim if embedder else 0
    return HealthResponse(
        service="rag-service-free",
        details={"embedding_model": embedder._model_name if embedder else "not loaded",
                 "embedding_dim": dim, "cost": "free"},
    )
