import pytest
from unittest.mock import AsyncMock, MagicMock
from langgraph.checkpoint.base import empty_checkpoint

from forge.checkpoints.postgres import PostgresCheckpointSaver, _make_config


@pytest.fixture
def saver():
    return PostgresCheckpointSaver(session_factory=MagicMock())


def _config(thread_id: str, checkpoint_id: str | None = None):
    return _make_config({"thread_id": thread_id}, checkpoint_id)


async def test_aput_and_aget_tuple(saver):
    config = _config("test-thread")
    checkpoint = empty_checkpoint()
    metadata = {"source": "input", "step": -1, "parents": {}}
    new_versions = {}

    mock_session = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None
    mock_session.execute.return_value = mock_result
    saver._session_factory.return_value = mock_session

    returned_config = await saver.aput(config, checkpoint, metadata, new_versions)
    assert returned_config is not None
    mock_session.add.assert_called_once()
    mock_session.commit.assert_called_once()


async def test_aget_tuple_returns_none(saver):
    config = _config("test-thread", "cp-1")

    mock_session = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None
    mock_session.execute.return_value = mock_result
    saver._session_factory.return_value = mock_session

    result = await saver.aget_tuple(config)
    assert result is None


async def test_aget_tuple_returns_checkpoint(saver):
    config = _config("test-thread", "cp-1")

    checkpoint = empty_checkpoint()
    row = MagicMock()
    row.thread_id = "test-thread"
    row.checkpoint_id = "cp-1"
    row.parent_checkpoint_id = None
    row.checkpoint_data = {
        "checkpoint": checkpoint,
        "metadata": {"source": "loop", "step": 0, "parents": {}},
    }
    row.pending_writes = None

    mock_session = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = row
    mock_session.execute.return_value = mock_result
    saver._session_factory.return_value = mock_session

    result = await saver.aget_tuple(config)
    assert result is not None
    assert result.checkpoint == checkpoint
