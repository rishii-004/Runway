import uuid
from datetime import datetime, timezone

from forge.api.schemas.agent import AgentCreate, AgentResponse, RunCreate, RunResponse


def test_agent_create_roundtrip():
    data = {"name": "test-agent", "description": "A test agent", "config": {"model": "gpt-4"}}
    agent = AgentCreate(**data)
    dumped = agent.model_dump()
    assert dumped["name"] == "test-agent"
    assert dumped["config"]["model"] == "gpt-4"


def test_agent_response_from_attributes():
    now = datetime.now(tz=timezone.utc)
    agent = AgentResponse(
        id=uuid.uuid4(),
        name="test-agent",
        description=None,
        config=None,
        created_at=now,
        updated_at=now,
    )
    dumped = agent.model_dump()
    assert "id" in dumped
    assert dumped["name"] == "test-agent"


def test_run_create_roundtrip():
    agent_id = uuid.uuid4()
    data = {
        "agent_id": agent_id,
        "task": "Investigate latency",
        "max_steps": 50,
        "max_tokens": 100_000,
        "max_cost_usd": 2.0,
        "max_runtime_seconds": 300,
    }
    run = RunCreate(**data)
    dumped = run.model_dump()
    assert dumped["agent_id"] == agent_id
    assert dumped["max_steps"] == 50


def test_run_response_roundtrip():
    now = datetime.now(tz=timezone.utc)
    run = RunResponse(
        id=uuid.uuid4(),
        agent_id=uuid.uuid4(),
        task="test task",
        status="QUEUED",
        iteration=0,
        created_at=now,
        updated_at=now,
    )
    validated = RunResponse.model_validate(run.model_dump())
    assert validated.status == "QUEUED"
