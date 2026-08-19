from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from forge.api.deps import get_db
from forge.api.schemas.evaluation import (
    EvaluationCreate,
    EvaluationDetailResponse,
    EvaluationResponse,
)
from forge.evaluation.runner import EvaluationRunner
from forge.storage.models import Agent, Evaluation

router = APIRouter()


@router.post("/evaluations", response_model=EvaluationResponse, status_code=201)
async def create_evaluation(body: EvaluationCreate, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Agent).where(Agent.id == body.agent_id))
    agent = result.scalar_one_or_none()
    if agent is None:
        raise HTTPException(status_code=404, detail="Agent not found")

    evaluation = Evaluation(
        id=uuid.uuid4(),
        agent_id=body.agent_id,
        name=body.name,
        status="PENDING",
    )
    db.add(evaluation)
    await db.commit()
    await db.refresh(evaluation)

    runner = EvaluationRunner()
    try:
        await runner.run_evaluation(
            evaluation_id=evaluation.id,
            agent_id=body.agent_id,
            tasks=body.tasks,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Evaluation failed: {e}") from e

    await db.refresh(evaluation)
    return evaluation


@router.get("/evaluations/{evaluation_id}", response_model=EvaluationDetailResponse)
async def get_evaluation(
    evaluation_id: uuid.UUID, db: AsyncSession = Depends(get_db)
):
    result = await db.execute(
        select(Evaluation)
        .options(selectinload(Evaluation.results))
        .where(Evaluation.id == evaluation_id)
    )
    evaluation = result.scalar_one_or_none()
    if evaluation is None:
        raise HTTPException(status_code=404, detail="Evaluation not found")
    return evaluation


@router.get("/evaluations", response_model=list[EvaluationResponse])
async def list_evaluations(
    agent_id: uuid.UUID | None = None,
    db: AsyncSession = Depends(get_db),
):
    query = select(Evaluation)
    if agent_id is not None:
        query = query.where(Evaluation.agent_id == agent_id)
    query = query.order_by(Evaluation.created_at.desc())
    result = await db.execute(query)
    evaluations = result.scalars().all()
    return evaluations
