from __future__ import annotations

import json
from collections.abc import AsyncIterator, Callable
from typing import Any

import aio_pika
import structlog

from forge.config import settings

logger = structlog.get_logger()

QUEUE_RUN_REQUESTED = "run.requested"
QUEUE_RUN_RESUME = "run.resume"


class RabbitMQManager:
    def __init__(self, url: str | None = None):
        self._url = url or settings.RABBITMQ_URL
        self._connection: aio_pika.abc.AbstractRobustConnection | None = None
        self._channel: aio_pika.abc.AbstractChannel | None = None

    async def connect(self) -> None:
        self._connection = await aio_pika.connect_robust(self._url)
        self._channel = await self._connection.channel()
        await self._channel.declare_queue(QUEUE_RUN_REQUESTED, durable=True)
        await self._channel.declare_queue(QUEUE_RUN_RESUME, durable=True)
        logger.info("rabbitmq_connected", url=self._url)

    async def close(self) -> None:
        if self._connection and not self._connection.is_closed:
            await self._connection.close()
            logger.info("rabbitmq_closed")

    async def publish(self, queue_name: str, message: dict[str, Any]) -> None:
        if not self._channel:
            raise RuntimeError("Not connected to RabbitMQ")
        body = json.dumps(message, default=str).encode()
        await self._channel.default_exchange.publish(
            aio_pika.Message(body=body, content_type="application/json"),
            routing_key=queue_name,
        )
        logger.info("message_published", queue=queue_name, body_keys=list(message.keys()))

    async def consume(
        self,
        queue_name: str,
        handler: Callable[[dict[str, Any]], None],
    ) -> None:
        if not self._channel:
            raise RuntimeError("Not connected to RabbitMQ")
        queue = await self._channel.get_queue(queue_name)
        async with queue.iterator() as queue_iter:
            async for message in queue_iter:
                async with message.process():
                    body = json.loads(message.body.decode())
                    logger.info("message_received", queue=queue_name, body_keys=list(body.keys()))
                    await handler(body)
                    logger.info("message_processed", queue=queue_name)

    async def consume_iter(self, queue_name: str) -> AsyncIterator[dict[str, Any]]:
        if not self._channel:
            raise RuntimeError("Not connected to RabbitMQ")
        queue = await self._channel.get_queue(queue_name)
        async with queue.iterator() as queue_iter:
            async for message in queue_iter:
                async with message.process():
                    body = json.loads(message.body.decode())
                    yield body
