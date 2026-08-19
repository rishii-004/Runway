from __future__ import annotations

from unittest.mock import MagicMock

from forge.observability.events import Event, EventBus, EventType


class TestEvent:
    def test_to_dict(self):
        event = Event(
            event_type=EventType.RUN_STARTED,
            run_id="r1",
            agent_id="a1",
            data={"key": "val"},
        )
        d = event.to_dict()
        assert d["event_type"] == "run.started"
        assert d["run_id"] == "r1"
        assert d["agent_id"] == "a1"
        assert d["data"] == {"key": "val"}
        assert "event_id" in d
        assert "timestamp" in d

    def test_to_json(self):
        event = Event(
            event_type=EventType.RUN_COMPLETED,
            run_id="r1",
            agent_id="a1",
        )
        j = event.to_json()
        assert '"run_id": "r1"' in j


class TestEventBus:
    def test_publish_records_history(self):
        bus = EventBus()
        event = Event(event_type=EventType.RUN_STARTED, run_id="r1", agent_id="a1")
        bus.publish(event)
        assert len(bus.get_history()) == 1

    def test_get_history_filter_by_run_id(self):
        bus = EventBus()
        bus.publish(Event(event_type=EventType.RUN_STARTED, run_id="r1", agent_id="a1"))
        bus.publish(Event(event_type=EventType.RUN_STARTED, run_id="r2", agent_id="a2"))
        bus.publish(Event(event_type=EventType.RUN_COMPLETED, run_id="r1", agent_id="a1"))

        r1_events = bus.get_history(run_id="r1")
        assert len(r1_events) == 2

    def test_emit_run_started(self):
        bus = EventBus()
        event = bus.emit_run_started("r1", "a1", model="gpt-4")
        assert event.event_type == EventType.RUN_STARTED
        assert event.data == {"model": "gpt-4"}

    def test_emit_step(self):
        bus = EventBus()
        event = bus.emit_step("r1", "a1", step=3)
        assert event.step == 3

    def test_emit_tool_call(self):
        bus = EventBus()
        event = bus.emit_tool_call("r1", "a1", "run_tests", step=2)
        assert event.tool_name == "run_tests"
        assert event.step == 2

    def test_emit_run_completed(self):
        bus = EventBus()
        event = bus.emit_run_completed("r1", "a1", tokens=500)
        assert event.event_type == EventType.RUN_COMPLETED
        assert event.data["tokens"] == 500

    def test_emit_run_failed(self):
        bus = EventBus()
        event = bus.emit_run_failed("r1", "a1", "timeout exceeded")
        assert event.event_type == EventType.RUN_FAILED
        assert event.data["error"] == "timeout exceeded"

    def test_kafka_producer_called(self):
        producer = MagicMock()
        bus = EventBus(kafka_producer=producer)
        event = Event(event_type=EventType.RUN_STARTED, run_id="r1", agent_id="a1")
        bus.publish(event)
        producer.produce.assert_called_once()
        call_kwargs = producer.produce.call_args[1]
        assert call_kwargs["topic"] == "forge.events"
        assert call_kwargs["key"] == b"r1"

    def test_sqs_client_called(self):
        sqs = MagicMock()
        bus = EventBus(sqs_client=sqs)
        event = Event(event_type=EventType.RUN_STARTED, run_id="r1", agent_id="a1")
        bus.publish(event)
        sqs.send_message.assert_called_once()

    def test_history_empty_by_default(self):
        bus = EventBus()
        assert bus.get_history() == []
