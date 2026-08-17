import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from forge.api.deps import get_db
from forge.api.main import app


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture(autouse=True)
def mock_db():
    mock_session = AsyncMock()
    mock_result = MagicMock()

    async def execute(stmt):
        return mock_result

    mock_session.execute = execute

    async def refresh(obj):
        if hasattr(obj, "created_at") and obj.created_at is None:
            obj.created_at = datetime.now(tz=timezone.utc)
        if hasattr(obj, "updated_at") and obj.updated_at is None:
            obj.updated_at = datetime.now(tz=timezone.utc)

    mock_session.refresh = refresh
    mock_result.scalar_one_or_none.return_value = None
    mock_result.scalars.return_value.all.return_value = []

    async def _get_db():
        yield mock_session

    app.dependency_overrides[get_db] = _get_db
    yield
    app.dependency_overrides.clear()


def test_health(client):
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


def test_create_agent(client):
    resp = client.post(
        "/agents",
        json={"name": "test-agent", "description": "A test agent"},
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["name"] == "test-agent"
    assert "id" in data
    assert "created_at" in data


def test_get_agent_not_found(client):
    resp = client.get(f"/agents/{uuid.uuid4()}")
    assert resp.status_code == 404


def test_create_run_not_found(client):
    resp = client.post(
        "/runs",
        json={"agent_id": str(uuid.uuid4()), "task": "test task"},
    )
    assert resp.status_code == 404


def test_get_run_not_found(client):
    resp = client.get(f"/runs/{uuid.uuid4()}")
    assert resp.status_code == 404


def test_cancel_run_not_found(client):
    resp = client.post(f"/runs/{uuid.uuid4()}/cancel")
    assert resp.status_code == 404
