from __future__ import annotations

import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from forge.api.deps import get_db
from forge.api.schemas.agent import (
    AgentCreate,
    AgentResponse,
    ApprovalDecision,
    ApprovalResponse,
    RunCreate,
    RunResponse,
)
from forge.api.schemas.evaluation import (
    CheckpointResponse,
    EventResponse,
    ReplayResponse,
    TraceResponse,
)
from forge.storage.models import Agent, Approval, Budget, CheckpointRow, ExecutionEvent, Run

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


@router.post("/runs/{run_id}/approve", response_model=ApprovalResponse)
async def approve_run(
    run_id: uuid.UUID, body: ApprovalDecision, db: AsyncSession = Depends(get_db)
):
    result = await db.execute(select(Run).where(Run.id == run_id))
    run = result.scalar_one_or_none()
    if run is None:
        raise HTTPException(status_code=404, detail="Run not found")

    if run.status != "WAITING_FOR_APPROVAL":
        raise HTTPException(
            status_code=400,
            detail=f"Run is not awaiting approval (current: {run.status})",
        )

    existing = await db.execute(
        select(Approval).where(Approval.run_id == run_id)
    )
    approval = existing.scalar_one_or_none()
    if approval is None:
        raise HTTPException(status_code=404, detail="No pending approval for this run")

    approval.decision = "APPROVED"
    approval.decided_at = datetime.now(tz=UTC)
    approval.decided_by = body.decided_by

    run.status = "RUNNING"
    await db.commit()
    await db.refresh(approval)
    return approval


@router.post("/runs/{run_id}/deny", response_model=ApprovalResponse)
async def deny_run(
    run_id: uuid.UUID, body: ApprovalDecision, db: AsyncSession = Depends(get_db)
):
    result = await db.execute(select(Run).where(Run.id == run_id))
    run = result.scalar_one_or_none()
    if run is None:
        raise HTTPException(status_code=404, detail="Run not found")

    if run.status != "WAITING_FOR_APPROVAL":
        raise HTTPException(
            status_code=400,
            detail=f"Run is not awaiting approval (current: {run.status})",
        )

    existing = await db.execute(
        select(Approval).where(Approval.run_id == run_id)
    )
    approval = existing.scalar_one_or_none()
    if approval is None:
        raise HTTPException(status_code=404, detail="No pending approval for this run")

    approval.decision = "DENIED"
    approval.decided_at = datetime.now(tz=UTC)
    approval.decided_by = body.decided_by

    run.status = "FAILED"
    run.error = "Tool execution denied by human operator"
    run.completed_at = datetime.now(tz=UTC)
    await db.commit()
    await db.refresh(approval)
    return approval


@router.get("/runs/{run_id}/events", response_model=list[EventResponse])
async def get_run_events(run_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(ExecutionEvent)
        .where(ExecutionEvent.run_id == run_id)
        .order_by(ExecutionEvent.created_at)
    )
    events = result.scalars().all()
    return events


@router.get("/runs/{run_id}/trace", response_model=TraceResponse)
async def get_run_trace(run_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    run_result = await db.execute(select(Run).where(Run.id == run_id))
    run = run_result.scalar_one_or_none()
    if run is None:
        raise HTTPException(status_code=404, detail="Run not found")

    ckpt_result = await db.execute(
        select(CheckpointRow)
        .where(CheckpointRow.run_id == run_id)
        .order_by(CheckpointRow.created_at)
    )
    checkpoints = ckpt_result.scalars().all()

    event_result = await db.execute(
        select(ExecutionEvent)
        .where(ExecutionEvent.run_id == run_id)
        .order_by(ExecutionEvent.created_at)
    )
    events = event_result.scalars().all()

    return TraceResponse(
        run_id=run_id,
        checkpoints=[CheckpointResponse.model_validate(c) for c in checkpoints],
        events=[EventResponse.model_validate(e) for e in events],
    )


@router.post("/runs/{run_id}/replay", response_model=ReplayResponse)
async def replay_run(run_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Run).where(Run.id == run_id)
    )
    run = result.scalar_one_or_none()
    if run is None:
        raise HTTPException(status_code=404, detail="Run not found")

    if run.status not in ("COMPLETED", "FAILED", "CANCELLED", "TIMEOUT", "BUDGET_EXCEEDED"):
        raise HTTPException(
            status_code=400,
            detail=f"Can only replay completed/failed runs (current: {run.status})",
        )

    run.status = "QUEUED"
    run.error = None
    run.result = None
    run.current_node = None
    run.iteration = 0
    run.started_at = None
    run.completed_at = None
    await db.commit()
    await db.refresh(run)

    return ReplayResponse(
        run_id=run_id,
        status="QUEUED",
        message="Run queued for replay from latest checkpoint",
    )
