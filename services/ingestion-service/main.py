"""
Ingestion Service (v2)
----------------------
Accepts CSV/PDF uploads, validates, chunks, publishes to Kafka.
Now uses Redis-backed JobStore + rich /health probes.
"""

from __future__ import annotations
import asyncio, base64, sys
sys.path.insert(0, "/app/shared")

from fastapi import FastAPI, HTTPException, BackgroundTasks, Query
from prometheus_fastapi_instrumentator import Instrumentator

from config.settings import IngestionSettings
from models.schemas import DataChunk, IngestionJob, IngestionRequest, JobStatus, HealthResponse
from messaging.kafka_client import KafkaPublisher, TOPIC_CHUNKS_READY
from parsers.csv_parser import parse_csv
from parsers.pdf_parser import parse_pdf
from processors.chunker import chunk_text
from processors.validator import validate_file
from job_store import JobStore
from utils.logger import configure_logging, get_logger
from utils.health import HealthChecker, DependencyCheck, redis_probe, kafka_probe

settings = IngestionSettings()
configure_logging("ingestion-service", settings.LOG_LEVEL)
log = get_logger(__name__)

app = FastAPI(title="Ingestion Service", version="2.0.0")
Instrumentator().instrument(app).expose(app)

_store:     JobStore | None       = None
_publisher: KafkaPublisher | None = None
_checker    = HealthChecker("ingestion-service", version="2.0.0")


@app.on_event("startup")
async def startup() -> None:
    global _store, _publisher
    _store     = JobStore(settings.REDIS_URL)
    _publisher = KafkaPublisher(settings.KAFKA_BOOTSTRAP)
    await _publisher.start()
    _checker.add(DependencyCheck("redis", redis_probe(settings.REDIS_URL)))
    _checker.add(DependencyCheck("kafka", kafka_probe(settings.KAFKA_BOOTSTRAP)))
    log.info("ingestion_service_started", version="2.0.0")


@app.on_event("shutdown")
async def shutdown() -> None:
    if _publisher: await _publisher.stop()
    if _store:     await _store.close()


@app.post("/ingest", response_model=IngestionJob, status_code=202)
async def ingest(req: IngestionRequest, bg: BackgroundTasks):
    err = validate_file(req.file_name, req.file_type, req.content_b64, settings.MAX_FILE_SIZE_MB)
    if err:
        raise HTTPException(status_code=422, detail=err)
    job = IngestionJob(tenant_id=req.tenant_id, user_id=req.user_id,
                       file_name=req.file_name, file_type=req.file_type)
    assert _store
    await _store.save(job)
    bg.add_task(_process_file, job, req)
    log.info("job_created", job_id=str(job.job_id), file=req.file_name)
    return job


@app.get("/ingest", response_model=list[IngestionJob])
async def list_jobs(tenant_id: str = Query(...)):
    assert _store
    return await _store.list(tenant_id)


@app.get("/ingest/{job_id}", response_model=IngestionJob)
async def job_status(job_id: str):
    assert _store
    job = await _store.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return job


@app.get("/health", response_model=HealthResponse)
async def health():
    return await _checker.run()


async def _process_file(job: IngestionJob, req: IngestionRequest) -> None:
    assert _store and _publisher
    await _store.update_status(str(job.job_id), JobStatus.RUNNING)
    try:
        raw = base64.b64decode(req.content_b64)
        texts = parse_csv(raw) if req.file_type.value == "csv" else parse_pdf(raw)
        chunks: list[DataChunk] = []
        for page_idx, text in enumerate(texts):
            for piece in chunk_text(text, settings.CHUNK_SIZE, settings.CHUNK_OVERLAP):
                chunks.append(DataChunk(
                    job_id=job.job_id, tenant_id=req.tenant_id,
                    source=req.file_name, content=piece, page=page_idx,
                    metadata={**req.metadata, "tags": req.tags},
                ))
        # Publish in parallel batches of 50
        BATCH = 50
        for i in range(0, len(chunks), BATCH):
            await asyncio.gather(*[
                _publisher.publish(TOPIC_CHUNKS_READY, c.model_dump(mode="json"), key=str(c.chunk_id))
                for c in chunks[i:i+BATCH]
            ])
        await _store.update_status(str(job.job_id), JobStatus.DONE, chunks=len(chunks))
        log.info("job_done", job_id=str(job.job_id), chunks=len(chunks))
    except Exception as exc:
        await _store.update_status(str(job.job_id), JobStatus.FAILED, error=str(exc))
        log.error("job_failed", job_id=str(job.job_id), error=str(exc))
