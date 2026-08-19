from __future__ import annotations

import json
import time
import uuid
from dataclasses import asdict, dataclass, field
from enum import StrEnum
from typing import Any

import structlog

logger = structlog.get_logger("forge.events")


class EventType(StrEnum):
    RUN_STARTED = "run.started"
    RUN_STEP = "run.step"
    RUN_TOOL_CALL = "run.tool_call"
    RUN_COMPLETED = "run.completed"
    RUN_FAILED = "run.failed"
    RUN_CANCELLED = "run.cancelled"
    SANDBOX_STARTED = "sandbox.started"
    SANDBOX_COMPLETED = "sandbox.completed"


@dataclass
class Event:
    event_type: EventType
    run_id: str
    agent_id: str
    timestamp: float = field(default_factory=time.time)
    event_id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    step: int | None = None
    tool_name: str | None = None
    data: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["event_type"] = self.event_type.value
        return d

    def to_json(self) -> str:
        return json.dumps(self.to_dict())


class EventBus:
    def __init__(self, kafka_producer: Any | None = None, sqs_client: Any | None = None):
        self._kafka = kafka_producer
        self._sqs = sqs_client
        self._history: list[Event] = []

    def publish(self, event: Event) -> None:
        self._history.append(event)
        logger.info(
            "event_published",
            event_type=event.event_type.value,
            run_id=event.run_id,
            event_id=event.event_id,
        )
        if self._kafka is not None:
            self._kafka.produce(
                topic="forge.events",
                key=event.run_id.encode(),
                value=event.to_json().encode(),
            )
        if self._sqs is not None:
            self._sqs.send_message(
                QueueUrl="arn:aws:sqs:events",
                MessageBody=event.to_json(),
            )

    def get_history(self, run_id: str | None = None) -> list[Event]:
        if run_id is None:
            return list(self._history)
        return [e for e in self._history if e.run_id == run_id]

    def emit_run_started(self, run_id: str, agent_id: str, **data: Any) -> Event:
        event = Event(
            event_type=EventType.RUN_STARTED,
            run_id=run_id,
            agent_id=agent_id,
            data=data,
        )
        self.publish(event)
        return event

    def emit_step(
        self, run_id: str, agent_id: str, step: int, **data: Any
    ) -> Event:
        event = Event(
            event_type=EventType.RUN_STEP,
            run_id=run_id,
            agent_id=agent_id,
            step=step,
            data=data,
        )
        self.publish(event)
        return event

    def emit_tool_call(
        self, run_id: str, agent_id: str, tool_name: str, step: int, **data: Any
    ) -> Event:
        event = Event(
            event_type=EventType.RUN_TOOL_CALL,
            run_id=run_id,
            agent_id=agent_id,
            tool_name=tool_name,
            step=step,
            data=data,
        )
        self.publish(event)
        return event

    def emit_run_completed(
        self, run_id: str, agent_id: str, **data: Any
    ) -> Event:
        event = Event(
            event_type=EventType.RUN_COMPLETED,
            run_id=run_id,
            agent_id=agent_id,
            data=data,
        )
        self.publish(event)
        return event

    def emit_run_failed(
        self, run_id: str, agent_id: str, error: str, **data: Any
    ) -> Event:
        event = Event(
            event_type=EventType.RUN_FAILED,
            run_id=run_id,
            agent_id=agent_id,
            data={"error": error, **data},
        )
        self.publish(event)
        return event
