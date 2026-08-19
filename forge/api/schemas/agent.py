from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel


class AgentCreate(BaseModel):
    name: str
    description: str | None = None
    config: dict | None = None


class AgentResponse(BaseModel):
    id: uuid.UUID
    name: str
    description: str | None = None
    config: dict | None = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class RunCreate(BaseModel):
    agent_id: uuid.UUID
    task: str
    max_steps: int | None = None
    max_tokens: int | None = None
    max_cost_usd: float | None = None
    max_runtime_seconds: int | None = None


class RunResponse(BaseModel):
    id: uuid.UUID
    agent_id: uuid.UUID
    task: str
    status: str
    current_node: str | None = None
    iteration: int = 0
    result: dict | None = None
    error: str | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ApprovalResponse(BaseModel):
    id: uuid.UUID
    run_id: uuid.UUID
    tool_name: str
    arguments: dict | None = None
    decision: str | None = None
    decided_at: datetime | None = None
    decided_by: str | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class ApprovalDecision(BaseModel):
    decided_by: str = "human"
