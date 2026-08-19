from __future__ import annotations

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from forge.storage.models import Budget

logger = structlog.get_logger()


class BudgetExceededError(Exception):
    def __init__(self, budget_type: str, limit: int | float, used: int | float) -> None:
        self.budget_type = budget_type
        self.limit = limit
        self.used = used
        super().__init__(
            f"Budget exceeded: {budget_type} limit {limit} reached (used {used})"
        )


class BudgetManager:
    def __init__(self, session_factory=None):
        from forge.storage.session import async_session

        self._session_factory = session_factory or async_session

    async def load(self, session: AsyncSession, run_id) -> Budget | None:
        result = await session.execute(select(Budget).where(Budget.run_id == run_id))
        return result.scalar_one_or_none()

    async def check(self, session: AsyncSession, run_id) -> Budget | None:
        budget = await self.load(session, run_id)
        if budget is None:
            return None

        if budget.max_steps is not None and budget.used_steps >= budget.max_steps:
            raise BudgetExceededError("steps", budget.max_steps, budget.used_steps)

        if budget.max_tokens is not None and budget.used_tokens >= budget.max_tokens:
            raise BudgetExceededError("tokens", budget.max_tokens, budget.used_tokens)

        if budget.max_cost_usd is not None and budget.used_cost_usd >= budget.max_cost_usd:
            raise BudgetExceededError("cost_usd", budget.max_cost_usd, budget.used_cost_usd)

        if (
            budget.max_runtime_seconds is not None
            and budget.used_runtime_seconds >= budget.max_runtime_seconds
        ):
            raise BudgetExceededError(
                "runtime_seconds", budget.max_runtime_seconds, budget.used_runtime_seconds
            )

        return budget

    async def record_step(self, session: AsyncSession, run_id) -> None:
        budget = await self.load(session, run_id)
        if budget is not None:
            budget.used_steps += 1
            await session.flush()
            logger.debug("budget_step_recorded", run_id=str(run_id), used=budget.used_steps)

    async def record_usage(
        self,
        session: AsyncSession,
        run_id,
        *,
        tokens: int = 0,
        cost_usd: float = 0.0,
        runtime_seconds: float = 0.0,
    ) -> None:
        budget = await self.load(session, run_id)
        if budget is None:
            return

        budget.used_tokens += tokens
        budget.used_cost_usd += cost_usd
        budget.used_runtime_seconds += runtime_seconds
        await session.flush()
        logger.debug(
            "budget_usage_recorded",
            run_id=str(run_id),
            tokens=tokens,
            cost_usd=cost_usd,
            runtime_seconds=runtime_seconds,
        )
