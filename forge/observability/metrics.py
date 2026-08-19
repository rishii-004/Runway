from __future__ import annotations

from prometheus_client import (
    CollectorRegistry,
    Counter,
    Gauge,
    Histogram,
    generate_latest,
)

REGISTRY = CollectorRegistry()

runs_total = Counter(
    "forge_runs_total",
    "Total number of runs",
    ["agent_id", "status"],
    registry=REGISTRY,
)

run_duration_seconds = Histogram(
    "forge_run_duration_seconds",
    "Run duration in seconds",
    ["agent_id"],
    buckets=(1, 5, 10, 30, 60, 120, 300, 600),
    registry=REGISTRY,
)

tool_calls_total = Counter(
    "forge_tool_calls_total",
    "Total tool invocations",
    ["tool_name", "status"],
    registry=REGISTRY,
)

tool_call_duration_seconds = Histogram(
    "forge_tool_call_duration_seconds",
    "Tool call duration in seconds",
    ["tool_name"],
    buckets=(0.1, 0.5, 1, 2, 5, 10, 30),
    registry=REGISTRY,
)

active_runs = Gauge(
    "forge_active_runs",
    "Number of currently active runs",
    registry=REGISTRY,
)

budget_usage = Gauge(
    "forge_budget_usage",
    "Budget used per run",
    ["run_id", "budget_type"],
    registry=REGISTRY,
)

sandbox_runs_total = Counter(
    "forge_sandbox_runs_total",
    "Total sandbox executions",
    ["exit_type"],
    registry=REGISTRY,
)


def get_metrics() -> bytes:
    return generate_latest(REGISTRY)


def get_metrics_content_type() -> str:
    return "text/plain; version=0.0.4; charset=utf-8"
