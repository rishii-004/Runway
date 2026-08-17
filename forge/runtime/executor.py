from __future__ import annotations

import uuid
from datetime import UTC, datetime

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from forge.agents.langgraph_adapter import LangGraphAdapter
from forge.checkpoints.postgres import PostgresCheckpointSaver
from forge.runtime.lifecycle import (
    COMPLETED,
    FAILED,
    RUNNING,
    WAITING_FOR_APPROVAL,
    transition,
)
from forge.storage.models import Run, RunStep
from forge.storage.session import async_session

logger = structlog.get_logger()


class RunExecutor:
    def __init__(
        self,
        adapter: LangGraphAdapter,
        checkpointer: PostgresCheckpointSaver,
        session_factory=None,
    ):
        self.adapter = adapter
        self.checkpointer = checkpointer
        self._session_factory = session_factory or async_session

    async def execute_run(self, run_id: uuid.UUID) -> str:
        session = self._session_factory()
        try:
            run = await self._load_run(session, run_id)
            if run is None:
                raise ValueError(f"Run {run_id} not found")

            run.status = transition(run.status, RUNNING)
            if run.started_at is None:
                run.started_at = datetime.now(tz=UTC)
            await session.commit()

            thread_id = str(run_id)
            config = {"configurable": {"thread_id": thread_id}}

            step_number = run.iteration
            while True:
                step_number += 1
                input_state = None
                if run.iteration == 0:
                    input_state = {"task": run.task}

                result = await self.adapter.astep(input_state, config)

                if result is None:
                    state = await self.adapter.aget_state(config)
                    run.status = COMPLETED
                    run.result = state
                    run.completed_at = datetime.now(tz=UTC)
                    run.iteration = step_number
                    await session.commit()
                    logger.info("run_completed", run_id=str(run_id), steps=step_number)
                    return COMPLETED

                if result.node_name == "__interrupt__":
                    run.status = WAITING_FOR_APPROVAL
                    run.current_node = "__interrupt__"
                    run.iteration = step_number
                    await session.commit()
                    logger.info("run_waiting_approval", run_id=str(run_id))
                    return WAITING_FOR_APPROVAL

                step = RunStep(
                    id=uuid.uuid4(),
                    run_id=run_id,
                    step_number=step_number,
                    node_name=result.node_name,
                    status="COMPLETED",
                    output_data=result.output,
                    started_at=datetime.now(tz=UTC),
                    completed_at=datetime.now(tz=UTC),
                )
                session.add(step)

                run.current_node = result.node_name
                run.iteration = step_number
                await session.commit()

                logger.info(
                    "step_completed",
                    run_id=str(run_id),
                    step=step_number,
                    node=result.node_name,
                )

        except Exception as e:
            logger.error("run_failed", run_id=str(run_id), error=str(e))
            try:
                run = await self._load_run(session, run_id)
                if run:
                    run.status = FAILED
                    run.error = str(e)
                    run.completed_at = datetime.now(tz=UTC)
                    await session.commit()
            except Exception:
                pass
            return FAILED
        finally:
            await session.close()

    async def _load_run(self, session: AsyncSession, run_id: uuid.UUID) -> Run | None:
        result = await session.execute(select(Run).where(Run.id == run_id))
        return result.scalar_one_or_none()
