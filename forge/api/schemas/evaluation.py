from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel


class EventResponse(BaseModel):
    id: uuid.UUID
    run_id: uuid.UUID
    event_type: str
    data: dict | None = None
    node_name: str | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class CheckpointResponse(BaseModel):
    id: uuid.UUID
    run_id: uuid.UUID
    thread_id: str
    checkpoint_id: str
    parent_checkpoint_id: str | None = None
    checkpoint_data: dict
    checkpoint_metadata: dict | None = None
    pending_writes: dict | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class TraceResponse(BaseModel):
    run_id: uuid.UUID
    checkpoints: list[CheckpointResponse]
    events: list[EventResponse]


class ReplayResponse(BaseModel):
    run_id: uuid.UUID
    status: str
    message: str


class EvaluationCreate(BaseModel):
    agent_id: uuid.UUID
    name: str
    tasks: list[str]


class EvaluationResponse(BaseModel):
    id: uuid.UUID
    agent_id: uuid.UUID
    name: str
    status: str
    metrics: dict | None = None
    created_at: datetime
    completed_at: datetime | None = None

    model_config = {"from_attributes": True}


class EvaluationResultResponse(BaseModel):
    id: uuid.UUID
    evaluation_id: uuid.UUID
    run_id: uuid.UUID
    task: str
    success: bool
    metrics: dict | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class EvaluationDetailResponse(EvaluationResponse):
    results: list[EvaluationResultResponse] = []
