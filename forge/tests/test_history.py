from __future__ import annotations

import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException

from forge.api.routes.runs import get_run_events, get_run_trace, replay_run
from forge.storage.models import CheckpointRow, ExecutionEvent, Run


def _make_run(run_id: uuid.UUID | None = None) -> Run:
    return Run(
        id=run_id or uuid.uuid4(),
        agent_id=uuid.uuid4(),
        task="test task",
        status="COMPLETED",
        iteration=3,
        created_at=datetime.now(tz=UTC),
        updated_at=datetime.now(tz=UTC),
    )


def _make_event(
    event_type: str = "run.started",
    run_id: uuid.UUID | None = None,
) -> ExecutionEvent:
    return ExecutionEvent(
        id=uuid.uuid4(),
        run_id=run_id or uuid.uuid4(),
        event_type=event_type,
        data={"step": 1},
        node_name="test_node",
        created_at=datetime.now(tz=UTC),
    )


def _make_checkpoint(run_id: uuid.UUID | None = None) -> CheckpointRow:
    rid = run_id or uuid.uuid4()
    return CheckpointRow(
        id=uuid.uuid4(),
        run_id=rid,
        thread_id=str(rid),
        checkpoint_id="cp-1",
        checkpoint_data={"checkpoint": {}, "metadata": {}},
        created_at=datetime.now(tz=UTC),
    )


class TestGetRunEvents:
    async def test_returns_events(self):
        run = _make_run()
        events = [
            _make_event("run.started", run.id),
            _make_event("run.step", run.id),
            _make_event("run.completed", run.id),
        ]

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = events

        with patch("forge.api.routes.runs.select") as mock_select:
            chain = mock_select.return_value
            chain.where.return_value.order_by.return_value = chain
            mock_db = AsyncMock()
            mock_db.execute.return_value = mock_result

            response = await get_run_events(run.id, mock_db)
            assert len(response) == 3

    async def test_empty_events(self):
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []

        mock_db = AsyncMock()
        mock_db.execute.return_value = mock_result

        response = await get_run_events(uuid.uuid4(), mock_db)
        assert response == []


class TestGetRunTrace:
    async def test_returns_trace(self):
        run = _make_run()
        checkpoints = [_make_checkpoint(run.id)]
        events = [_make_event("run.started", run.id)]

        run_result = MagicMock()
        run_result.scalar_one_or_none.return_value = run

        ckpt_result = MagicMock()
        ckpt_result.scalars.return_value.all.return_value = checkpoints

        event_result = MagicMock()
        event_result.scalars.return_value.all.return_value = events

        call_count = 0

        async def mock_execute(query):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return run_result
            elif call_count == 2:
                return ckpt_result
            return event_result

        mock_db = AsyncMock()
        mock_db.execute = mock_execute

        response = await get_run_trace(run.id, mock_db)
        assert response.run_id == run.id
        assert len(response.checkpoints) == 1
        assert len(response.events) == 1

    async def test_run_not_found(self):
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None

        mock_db = AsyncMock()
        mock_db.execute.return_value = mock_result

        with pytest.raises(HTTPException) as exc_info:
            await get_run_trace(uuid.uuid4(), mock_db)
        assert exc_info.value.status_code == 404


class TestReplayRun:
    async def test_replay_completed_run(self):
        run = _make_run()
        run.status = "COMPLETED"

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = run

        mock_db = AsyncMock()
        mock_db.execute.return_value = mock_result

        response = await replay_run(run.id, mock_db)
        assert response.status == "QUEUED"
        assert run.status == "QUEUED"
        assert run.iteration == 0

    async def test_replay_rejects_running_run(self):
        run = _make_run()
        run.status = "RUNNING"

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = run

        mock_db = AsyncMock()
        mock_db.execute.return_value = mock_result

        with pytest.raises(HTTPException) as exc_info:
            await replay_run(run.id, mock_db)
        assert exc_info.value.status_code == 400

    async def test_replay_run_not_found(self):
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None

        mock_db = AsyncMock()
        mock_db.execute.return_value = mock_result

        with pytest.raises(HTTPException) as exc_info:
            await replay_run(uuid.uuid4(), mock_db)
        assert exc_info.value.status_code == 404
