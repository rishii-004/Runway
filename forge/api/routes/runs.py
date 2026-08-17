from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from forge.api.deps import get_db
from forge.api.schemas.agent import AgentCreate, AgentResponse, RunCreate, RunResponse
from forge.storage.models import Agent, Budget, Run

router = APIRouter()


@router.post("/agents", response_model=AgentResponse, status_code=201)
async def create_agent(body: AgentCreate, db: AsyncSession = Depends(get_db)):
    agent = Agent(
        id=uuid.uuid4(),
        name=body.name,
        description=body.description,
        config=body.config,
    )
    db.add(agent)
    await db.commit()
    await db.refresh(agent)
    return agent


@router.get("/agents/{agent_id}", response_model=AgentResponse)
async def get_agent(agent_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Agent).where(Agent.id == agent_id))
    agent = result.scalar_one_or_none()
    if agent is None:
        raise HTTPException(status_code=404, detail="Agent not found")
    return agent


@router.post("/runs", response_model=RunResponse, status_code=201)
async def create_run(body: RunCreate, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Agent).where(Agent.id == body.agent_id))
    agent = result.scalar_one_or_none()
    if agent is None:
        raise HTTPException(status_code=404, detail="Agent not found")

    run = Run(
        id=uuid.uuid4(),
        agent_id=body.agent_id,
        task=body.task,
        status="QUEUED",
    )
    db.add(run)

    has_budget = any(
        v is not None
        for v in [body.max_steps, body.max_tokens, body.max_cost_usd, body.max_runtime_seconds]
    )
    if has_budget:
        budget = Budget(
            id=uuid.uuid4(),
            run_id=run.id,
            max_steps=body.max_steps,
            max_tokens=body.max_tokens,
            max_cost_usd=body.max_cost_usd,
            max_runtime_seconds=body.max_runtime_seconds,
        )
        db.add(budget)

    await db.commit()
    await db.refresh(run)
    return run


@router.get("/runs/{run_id}", response_model=RunResponse)
async def get_run(run_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Run).where(Run.id == run_id))
    run = result.scalar_one_or_none()
    if run is None:
        raise HTTPException(status_code=404, detail="Run not found")
    return run


@router.post("/runs/{run_id}/cancel", response_model=RunResponse)
async def cancel_run(run_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Run).where(Run.id == run_id))
    run = result.scalar_one_or_none()
    if run is None:
        raise HTTPException(status_code=404, detail="Run not found")

    if run.status in ("COMPLETED", "FAILED", "CANCELLED", "TIMEOUT", "BUDGET_EXCEEDED"):
        raise HTTPException(status_code=400, detail=f"Cannot cancel run in {run.status} state")

    run.status = "CANCELLED"
    await db.commit()
    await db.refresh(run)
    return run
