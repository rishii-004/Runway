from __future__ import annotations

import uuid
from datetime import datetime, timezone

from pydantic import BaseModel, Field


class RunRequestedMessage(BaseModel):
    run_id: uuid.UUID
    agent_id: uuid.UUID
    task: str
    thread_id: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(tz=timezone.utc))


class RunResumeMessage(BaseModel):
    run_id: uuid.UUID
    agent_id: uuid.UUID
    thread_id: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(tz=timezone.utc))
