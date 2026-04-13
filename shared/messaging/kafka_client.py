"""
Shared Kafka client – thin wrapper around aiokafka for async publish / consume.
"""

from __future__ import annotations
import json
import logging
from typing import Any, Callable, Coroutine, Dict, List, Optional

from aiokafka import AIOKafkaConsumer, AIOKafkaProducer
from aiokafka.errors import KafkaConnectionError

logger = logging.getLogger(__name__)

# ─── Topic constants ──────────────────────────────────────────────────────────
TOPIC_INGESTION_JOBS    = "ingestion.jobs"
TOPIC_CHUNKS_READY      = "chunks.ready"
TOPIC_EMBED_REQUESTS    = "embed.requests"
TOPIC_QUERY_REQUESTS    = "query.requests"
TOPIC_ANALYTICS_JOBS    = "analytics.jobs"
TOPIC_NOTIFICATIONS     = "notifications"


class KafkaPublisher:
    """Async Kafka producer with automatic serialisation."""

    def __init__(self, bootstrap_servers: str) -> None:
        self._servers  = bootstrap_servers
        self._producer: Optional[AIOKafkaProducer] = None

    async def start(self) -> None:
        self._producer = AIOKafkaProducer(
            bootstrap_servers=self._servers,
            value_serializer=lambda v: json.dumps(v).encode(),
            key_serializer=lambda k: k.encode() if k else None,
            acks="all",
            enable_idempotence=True,
        )
        await self._producer.start()
        logger.info("Kafka producer connected to %s", self._servers)

    async def stop(self) -> None:
        if self._producer:
            await self._producer.stop()

    async def publish(
        self,
        topic:   str,
        payload: Dict[str, Any],
        key:     Optional[str] = None,
    ) -> None:
        if not self._producer:
            raise RuntimeError("Publisher not started – call start() first.")
        try:
            await self._producer.send_and_wait(topic, value=payload, key=key)
            logger.debug("Published to %s key=%s", topic, key)
        except KafkaConnectionError as exc:
            logger.error("Kafka publish failed: %s", exc)
            raise


class KafkaConsumer:
    """Async Kafka consumer with handler registration."""

    Handler = Callable[[Dict[str, Any]], Coroutine]

    def __init__(
        self,
        bootstrap_servers: str,
        group_id:          str,
        topics:            List[str],
    ) -> None:
        self._servers  = bootstrap_servers
        self._group_id = group_id
        self._topics   = topics
        self._consumer: Optional[AIOKafkaConsumer] = None
        self._handlers: Dict[str, List[KafkaConsumer.Handler]] = {}

    def on(self, topic: str) -> Callable:
        """Decorator: @consumer.on('topic.name') async def handler(msg): ..."""
        def decorator(fn: KafkaConsumer.Handler) -> KafkaConsumer.Handler:
            self._handlers.setdefault(topic, []).append(fn)
            return fn
        return decorator

    async def start(self) -> None:
        self._consumer = AIOKafkaConsumer(
            *self._topics,
            bootstrap_servers=self._servers,
            group_id=self._group_id,
            value_deserializer=lambda v: json.loads(v.decode()),
            auto_offset_reset="earliest",
            enable_auto_commit=True,
        )
        await self._consumer.start()
        logger.info("Kafka consumer [%s] subscribed to %s", self._group_id, self._topics)

    async def stop(self) -> None:
        if self._consumer:
            await self._consumer.stop()

    async def consume(self) -> None:
        """Blocking loop – run as a background task."""
        if not self._consumer:
            raise RuntimeError("Consumer not started – call start() first.")
        async for msg in self._consumer:
            topic = msg.topic
            handlers = self._handlers.get(topic, [])
            for handler in handlers:
                try:
                    await handler(msg.value)
                except Exception as exc:
                    logger.exception("Handler error on topic %s: %s", topic, exc)
