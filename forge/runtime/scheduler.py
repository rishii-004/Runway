from __future__ import annotations

import uuid

import structlog

from forge.messaging.messages import RunRequestedMessage
from forge.messaging.rabbitmq import QUEUE_RUN_REQUESTED, RabbitMQManager

logger = structlog.get_logger()


class RunScheduler:
    def __init__(self, rabbitmq: RabbitMQManager):
        self.rabbitmq = rabbitmq

    async def submit_run(
        self,
        run_id: uuid.UUID,
        agent_id: uuid.UUID,
        task: str,
        thread_id: str,
    ) -> None:
        message = RunRequestedMessage(
            run_id=run_id,
            agent_id=agent_id,
            task=task,
            thread_id=thread_id,
        )
        await self.rabbitmq.publish(QUEUE_RUN_REQUESTED, message.model_dump(mode="json"))
        logger.info("run_submitted", run_id=str(run_id), agent_id=str(agent_id))
