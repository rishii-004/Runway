from __future__ import annotations

import structlog
from sqlalchemy import select

from forge.runtime.executor import RunExecutor
from forge.storage.models import Run
from forge.storage.session import async_session

logger = structlog.get_logger()


async def recover_interrupted_runs(executor: RunExecutor) -> int:
    session = async_session()
    try:
        result = await session.execute(
            select(Run).where(Run.status.in_(["RUNNING", "WAITING_FOR_APPROVAL"]))
        )
        runs = result.scalars().all()
        recovered = 0
        for run in runs:
            logger.info("recovering_run", run_id=str(run.id), status=run.status)
            try:
                await executor.execute_run(run.id)
                recovered += 1
            except Exception as e:
                logger.error("recovery_failed", run_id=str(run.id), error=str(e))
        return recovered
    finally:
        await session.close()
