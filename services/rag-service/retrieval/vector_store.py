"""
Qdrant vector store – handles upsert and hybrid search.
Supports per-tenant isolation via payload filters.
"""

from __future__ import annotations
from typing import Any, Dict, List

from qdrant_client import AsyncQdrantClient
from qdrant_client.models import (
    Distance, FieldCondition, Filter, MatchValue,
    PointStruct, SearchRequest, VectorParams,
)

from models.schemas import DataChunk, RetrievedChunk


class VectorStore:
    def __init__(self, url: str, collection: str, dim: int) -> None:
        self._client     = AsyncQdrantClient(url=url)
        self._collection = collection
        self._dim        = dim

    async def ensure_collection(self) -> None:
        existing = {c.name for c in await self._client.get_collections()}  # type: ignore
        if self._collection not in existing:
            await self._client.create_collection(
                collection_name=self._collection,
                vectors_config=VectorParams(size=self._dim, distance=Distance.COSINE),
            )

    async def upsert(self, chunk: DataChunk, embedding: List[float]) -> None:
        point = PointStruct(
            id=str(chunk.chunk_id),
            vector=embedding,
            payload={
                "content":   chunk.content,
                "source":    chunk.source,
                "tenant_id": chunk.tenant_id,
                "job_id":    str(chunk.job_id),
                **chunk.metadata,
            },
        )
        await self._client.upsert(collection_name=self._collection, points=[point])

    async def search(
        self,
        query_vec:  List[float],
        tenant_id:  str,
        top_k:      int = 30,
        filters:    Dict[str, Any] | None = None,
    ) -> List[RetrievedChunk]:
        must_conditions = [
            FieldCondition(key="tenant_id", match=MatchValue(value=tenant_id))
        ]
        if filters:
            for k, v in filters.items():
                must_conditions.append(FieldCondition(key=k, match=MatchValue(value=v)))

        results = await self._client.search(
            collection_name=self._collection,
            query_vector=query_vec,
            query_filter=Filter(must=must_conditions),
            limit=top_k,
            with_payload=True,
        )
        return [
            RetrievedChunk(
                chunk_id=str(r.id),
                content=r.payload.get("content", ""),
                source=r.payload.get("source", ""),
                score=r.score,
                metadata={k: v for k, v in r.payload.items() if k not in {"content", "source", "tenant_id"}},
            )
            for r in results
        ]
