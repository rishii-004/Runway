import uuid

from forge.messaging.messages import RunRequestedMessage, RunResumeMessage


def test_run_requested_message_roundtrip():
    msg = RunRequestedMessage(
        run_id=uuid.uuid4(),
        agent_id=uuid.uuid4(),
        task="test task",
        thread_id="thread-1",
    )
    data = msg.model_dump()
    validated = RunRequestedMessage.model_validate(data)
    assert validated.task == "test task"
    assert validated.thread_id == "thread-1"


def test_run_resume_message_roundtrip():
    msg = RunResumeMessage(
        run_id=uuid.uuid4(),
        agent_id=uuid.uuid4(),
        thread_id="thread-1",
    )
    data = msg.model_dump()
    validated = RunResumeMessage.model_validate(data)
    assert validated.thread_id == "thread-1"
    assert validated.created_at is not None
