import uuid
from unittest.mock import AsyncMock, MagicMock, patch

from forge.runtime.recovery import recover_interrupted_runs


async def test_recover_interrupted_runs():
    mock_executor = AsyncMock()
    mock_session = AsyncMock()

    run1 = MagicMock()
    run1.id = uuid.uuid4()
    run1.status = "RUNNING"

    run2 = MagicMock()
    run2.id = uuid.uuid4()
    run2.status = "WAITING_FOR_APPROVAL"

    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = [run1, run2]
    mock_session.execute.return_value = mock_result

    with patch("forge.runtime.recovery.async_session", return_value=mock_session):
        recovered = await recover_interrupted_runs(mock_executor)

    assert recovered == 2
    assert mock_executor.execute_run.call_count == 2
    mock_session.close.assert_called_once()
