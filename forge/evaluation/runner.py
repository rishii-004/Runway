from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime
from pathlib import Path

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from forge.evaluation.metrics import RunMetrics, aggregate_metrics
from forge.storage.models import Evaluation, EvaluationResult, Run
from forge.storage.session import async_session

logger = structlog.get_logger()


class EvaluationRunner:
    def __init__(self, session_factory=None):
        self._session_factory = session_factory or async_session

    async def run_evaluation(
        self,
        evaluation_id: uuid.UUID,
        agent_id: uuid.UUID,
        tasks: list[str],
    ) -> dict:
        session = self._session_factory()
        try:
            eval_result = await self._load_evaluation(session, evaluation_id)
            if eval_result is None:
                raise ValueError(f"Evaluation {evaluation_id} not found")

            eval_result.status = "RUNNING"
            await session.commit()

            run_metrics: list[RunMetrics] = []

            for task_text in tasks:
                run = Run(
                    id=uuid.uuid4(),
                    agent_id=agent_id,
                    task=task_text,
                    status="QUEUED",
                )
                session.add(run)
                await session.commit()
                await session.refresh(run)

                metrics = RunMetrics(task=task_text, success=False)
                run_metrics.append(metrics)

                result_row = EvaluationResult(
                    id=uuid.uuid4(),
                    evaluation_id=evaluation_id,
                    run_id=run.id,
                    task=task_text,
                    success=False,
                    metrics=metrics.to_dict(),
                )
                session.add(result_row)
                await session.commit()

                logger.info(
                    "eval_run_created",
                    evaluation_id=str(evaluation_id),
                    run_id=str(run.id),
                    task=task_text[:50],
                )

            aggregated = aggregate_metrics(run_metrics)
            eval_result.status = "COMPLETED"
            eval_result.metrics = aggregated.to_dict()
            eval_result.completed_at = datetime.now(tz=UTC)
            await session.commit()

            logger.info(
                "evaluation_completed",
                evaluation_id=str(evaluation_id),
                total_tasks=aggregated.total_tasks,
                success_rate=aggregated.success_rate,
            )

            return aggregated.to_dict()

        except Exception as e:
            logger.error("evaluation_failed", evaluation_id=str(evaluation_id), error=str(e))
            try:
                eval_result = await self._load_evaluation(session, evaluation_id)
                if eval_result:
                    eval_result.status = "FAILED"
                    await session.commit()
            except Exception:
                pass
            raise
        finally:
            await session.close()

    def load_tasks_from_file(self, path: str | Path) -> list[str]:
        tasks_path = Path(path)
        if not tasks_path.exists():
            raise FileNotFoundError(f"Tasks file not found: {tasks_path}")

        tasks = []
        with open(tasks_path) as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    data = json.loads(line)
                    if isinstance(data, dict) and "task" in data:
                        tasks.append(data["task"])
                    elif isinstance(data, str):
                        tasks.append(data)
                except json.JSONDecodeError:
                    tasks.append(line)
        return tasks

    async def _load_evaluation(
        self, session: AsyncSession, evaluation_id: uuid.UUID
    ) -> Evaluation | None:
        result = await session.execute(
            select(Evaluation).where(Evaluation.id == evaluation_id)
        )
        return result.scalar_one_or_none()
