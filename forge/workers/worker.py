from __future__ import annotations

import asyncio
import signal

import structlog

from forge.agents.demo_echo_agent import build_demo_graph
from forge.agents.langgraph_adapter import LangGraphAdapter
from forge.checkpoints.postgres import PostgresCheckpointSaver
from forge.messaging.messages import RunRequestedMessage, RunResumeMessage
from forge.messaging.rabbitmq import QUEUE_RUN_REQUESTED, QUEUE_RUN_RESUME, RabbitMQManager
from forge.runtime.executor import RunExecutor
from forge.runtime.recovery import recover_interrupted_runs

logger = structlog.get_logger()


class Worker:
    def __init__(self, rabbitmq: RabbitMQManager, executor: RunExecutor):
        self.rabbitmq = rabbitmq
        self.executor = executor
        self._running = True

    async def start(self) -> None:
        logger.info("worker_starting")
        loop = asyncio.get_event_loop()
        for sig in (signal.SIGTERM, signal.SIGINT):
            loop.add_signal_handler(sig, self._handle_signal)

        await self.rabbitmq.connect()

        recovered = await recover_interrupted_runs(self.executor)
        if recovered > 0:
            logger.info("recovered_runs", count=recovered)

        while self._running:
            try:
                async for message in self.rabbitmq.consume_iter(QUEUE_RUN_REQUESTED):
                    if not self._running:
                        break
                    await self._handle_run_requested(message)

                if self._running:
                    async for message in self.rabbitmq.consume_iter(QUEUE_RUN_RESUME):
                        if not self._running:
                            break
                        await self._handle_run_resume(message)
            except Exception as e:
                logger.error("worker_error", error=str(e))
                if self._running:
                    await asyncio.sleep(1)

        await self.rabbitmq.close()
        logger.info("worker_stopped")

    async def _handle_run_requested(self, message: dict) -> None:
        msg = RunRequestedMessage(**message)
        logger.info("handling_run_requested", run_id=str(msg.run_id))
        status = await self.executor.execute_run(msg.run_id)
        logger.info("run_finished", run_id=str(msg.run_id), status=status)

    async def _handle_run_resume(self, message: dict) -> None:
        msg = RunResumeMessage(**message)
        logger.info("handling_run_resume", run_id=str(msg.run_id))
        status = await self.executor.execute_run(msg.run_id)
        logger.info("run_finished", run_id=str(msg.run_id), status=status)

    def _handle_signal(self) -> None:
        logger.info("worker_shutdown_signal")
        self._running = False


def create_worker() -> Worker:
    rabbitmq = RabbitMQManager()
    checkpointer = PostgresCheckpointSaver()
    graph = build_demo_graph()
    compiled = graph.compile(checkpointer=checkpointer)
    adapter = LangGraphAdapter(compiled)
    executor = RunExecutor(adapter=adapter, checkpointer=checkpointer)
    return Worker(rabbitmq=rabbitmq, executor=executor)


async def run_worker() -> None:
    worker = create_worker()
    await worker.start()


if __name__ == "__main__":
    from forge.observability.logging import setup_logging

    setup_logging()
    asyncio.run(run_worker())
