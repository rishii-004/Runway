from __future__ import annotations

import uuid

import pytest
from sqlalchemy import Column, Float, Integer
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from forge.budgets.manager import BudgetExceededError, BudgetManager


class Base(DeclarativeBase):
    pass


class Budget(Base):
    __tablename__ = "budgets"

    id = Column(PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    run_id = Column(PG_UUID(as_uuid=True), unique=True, nullable=False)
    max_steps = Column(Integer, nullable=True)
    max_tokens = Column(Integer, nullable=True)
    max_cost_usd = Column(Float, nullable=True)
    max_runtime_seconds = Column(Integer, nullable=True)
    used_steps = Column(Integer, nullable=False, default=0)
    used_tokens = Column(Integer, nullable=False, default=0)
    used_cost_usd = Column(Float, nullable=False, default=0.0)
    used_runtime_seconds = Column(Float, nullable=False, default=0.0)


@pytest.fixture
async def engine():
    eng = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with eng.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield eng
    await eng.dispose()


@pytest.fixture
async def session(engine):
    factory = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with factory() as sess:
        yield sess


def _make_budget(
    run_id: uuid.UUID,
    *,
    max_steps: int | None = None,
    max_tokens: int | None = None,
    max_cost_usd: float | None = None,
    max_runtime_seconds: int | None = None,
    used_steps: int = 0,
    used_tokens: int = 0,
    used_cost_usd: float = 0.0,
    used_runtime_seconds: float = 0.0,
) -> Budget:
    return Budget(
        id=uuid.uuid4(),
        run_id=run_id,
        max_steps=max_steps,
        max_tokens=max_tokens,
        max_cost_usd=max_cost_usd,
        max_runtime_seconds=max_runtime_seconds,
        used_steps=used_steps,
        used_tokens=used_tokens,
        used_cost_usd=used_cost_usd,
        used_runtime_seconds=used_runtime_seconds,
    )


class _TestBudgetManager(BudgetManager):
    """BudgetManager that uses the test model instead of the production one."""

    def __init__(self, session: AsyncSession):
        self._session = session
        self._model = Budget

    async def load(self, session, run_id):
        from sqlalchemy import select

        result = await session.execute(select(Budget).where(Budget.run_id == run_id))
        return result.scalar_one_or_none()


class TestBudgetCheck:
    async def test_no_budget_returns_none(self, session: AsyncSession):
        manager = _TestBudgetManager(session)
        result = await manager.check(session, uuid.uuid4())
        assert result is None

    async def test_within_budget(self, session: AsyncSession):
        run_id = uuid.uuid4()
        budget = _make_budget(run_id, max_steps=10, used_steps=5)
        session.add(budget)
        await session.commit()

        manager = _TestBudgetManager(session)
        result = await manager.check(session, run_id)
        assert result is not None
        assert result.used_steps == 5

    async def test_steps_exceeded(self, session: AsyncSession):
        run_id = uuid.uuid4()
        budget = _make_budget(run_id, max_steps=3, used_steps=3)
        session.add(budget)
        await session.commit()

        manager = _TestBudgetManager(session)
        with pytest.raises(BudgetExceededError) as exc_info:
            await manager.check(session, run_id)
        assert exc_info.value.budget_type == "steps"
        assert exc_info.value.limit == 3
        assert exc_info.value.used == 3

    async def test_tokens_exceeded(self, session: AsyncSession):
        run_id = uuid.uuid4()
        budget = _make_budget(run_id, max_tokens=1000, used_tokens=1000)
        session.add(budget)
        await session.commit()

        manager = _TestBudgetManager(session)
        with pytest.raises(BudgetExceededError) as exc_info:
            await manager.check(session, run_id)
        assert exc_info.value.budget_type == "tokens"

    async def test_cost_exceeded(self, session: AsyncSession):
        run_id = uuid.uuid4()
        budget = _make_budget(run_id, max_cost_usd=1.0, used_cost_usd=1.0)
        session.add(budget)
        await session.commit()

        manager = _TestBudgetManager(session)
        with pytest.raises(BudgetExceededError) as exc_info:
            await manager.check(session, run_id)
        assert exc_info.value.budget_type == "cost_usd"

    async def test_runtime_exceeded(self, session: AsyncSession):
        run_id = uuid.uuid4()
        budget = _make_budget(run_id, max_runtime_seconds=60, used_runtime_seconds=60.0)
        session.add(budget)
        await session.commit()

        manager = _TestBudgetManager(session)
        with pytest.raises(BudgetExceededError) as exc_info:
            await manager.check(session, run_id)
        assert exc_info.value.budget_type == "runtime_seconds"


class TestBudgetRecord:
    async def test_record_step(self, session: AsyncSession):
        run_id = uuid.uuid4()
        budget = _make_budget(run_id, max_steps=10, used_steps=0)
        session.add(budget)
        await session.commit()

        manager = _TestBudgetManager(session)
        await manager.record_step(session, run_id)

        refreshed = await manager.load(session, run_id)
        assert refreshed is not None
        assert refreshed.used_steps == 1

    async def test_record_usage(self, session: AsyncSession):
        run_id = uuid.uuid4()
        budget = _make_budget(run_id, max_tokens=10000)
        session.add(budget)
        await session.commit()

        manager = _TestBudgetManager(session)
        await manager.record_usage(session, run_id, tokens=500, cost_usd=0.05, runtime_seconds=2.5)

        refreshed = await manager.load(session, run_id)
        assert refreshed is not None
        assert refreshed.used_tokens == 500
        assert refreshed.used_cost_usd == pytest.approx(0.05)
        assert refreshed.used_runtime_seconds == pytest.approx(2.5)

    async def test_record_usage_no_budget_is_noop(self, session: AsyncSession):
        manager = _TestBudgetManager(session)
        await manager.record_usage(session, uuid.uuid4(), tokens=100)

    async def test_record_step_no_budget_is_noop(self, session: AsyncSession):
        manager = _TestBudgetManager(session)
        await manager.record_step(session, uuid.uuid4())

    async def test_steps_exceeded_after_recording(self, session: AsyncSession):
        run_id = uuid.uuid4()
        budget = _make_budget(run_id, max_steps=2, used_steps=1)
        session.add(budget)
        await session.commit()

        manager = _TestBudgetManager(session)
        await manager.record_step(session, run_id)

        with pytest.raises(BudgetExceededError):
            await manager.check(session, run_id)
