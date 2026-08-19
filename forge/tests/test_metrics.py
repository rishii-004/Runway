from __future__ import annotations

from forge.observability.metrics import (
    active_runs,
    budget_usage,
    get_metrics,
    get_metrics_content_type,
    run_duration_seconds,
    runs_total,
    sandbox_runs_total,
    tool_call_duration_seconds,
    tool_calls_total,
)


class TestPrometheusMetrics:
    def test_get_metrics_returns_bytes(self):
        result = get_metrics()
        assert isinstance(result, bytes)

    def test_get_metrics_content_type(self):
        ct = get_metrics_content_type()
        assert "text/plain" in ct

    def test_runs_total_increment(self):
        runs_total.labels(agent_id="a1", status="completed").inc()
        metric = get_metrics()
        assert b"forge_runs_total" in metric

    def test_run_duration_seconds_observe(self):
        run_duration_seconds.labels(agent_id="a1").observe(5.0)
        metric = get_metrics()
        assert b"forge_run_duration_seconds" in metric

    def test_tool_calls_total_increment(self):
        tool_calls_total.labels(tool_name="run_tests", status="success").inc()
        metric = get_metrics()
        assert b"forge_tool_calls_total" in metric

    def test_tool_call_duration_observe(self):
        tool_call_duration_seconds.labels(tool_name="sh").observe(0.5)
        metric = get_metrics()
        assert b"forge_tool_call_duration_seconds" in metric

    def test_active_runs_gauge(self):
        active_runs.set(3)
        metric = get_metrics()
        assert b"forge_active_runs" in metric

    def test_budget_usage_gauge(self):
        budget_usage.labels(run_id="r1", budget_type="tokens").set(500)
        metric = get_metrics()
        assert b"forge_budget_usage" in metric

    def test_sandbox_runs_total(self):
        sandbox_runs_total.labels(exit_type="success").inc()
        metric = get_metrics()
        assert b"forge_sandbox_runs_total" in metric
