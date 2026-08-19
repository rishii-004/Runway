from __future__ import annotations

from opentelemetry.sdk.trace import TracerProvider

from forge.observability.tracing import get_tracer, setup_tracing, span


class TestTracing:
    def test_setup_tracing_returns_provider(self):
        provider = setup_tracing(console_export=True)
        assert isinstance(provider, TracerProvider)

    def test_get_tracer(self):
        tracer = get_tracer("test.tracer")
        assert tracer is not None

    def test_span_context_manager(self):
        with span("test.span", attributes={"key": "value"}) as s:
            assert s is not None
            assert s.is_recording()

    def test_span_records_exception(self):
        raised = False
        try:
            with span("error.span"):
                raise ValueError("boom")
        except ValueError:
            raised = True
        assert raised

    def test_span_success_status(self):
        with span("ok.span") as s:
            pass
        assert s is not None
