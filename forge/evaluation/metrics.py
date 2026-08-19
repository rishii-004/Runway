from __future__ import annotations

from dataclasses import dataclass


@dataclass
class RunMetrics:
    task: str
    success: bool
    steps: int = 0
    tokens: int = 0
    cost_usd: float = 0.0
    duration_seconds: float = 0.0
    tool_calls: int = 0
    errors: int = 0

    def to_dict(self) -> dict:
        return {
            "task": self.task,
            "success": self.success,
            "steps": self.steps,
            "tokens": self.tokens,
            "cost_usd": self.cost_usd,
            "duration_seconds": self.duration_seconds,
            "tool_calls": self.tool_calls,
            "errors": self.errors,
        }


@dataclass
class AggregatedMetrics:
    total_tasks: int = 0
    successful: int = 0
    failed: int = 0
    success_rate: float = 0.0
    total_steps: int = 0
    avg_steps: float = 0.0
    total_tokens: int = 0
    avg_tokens: float = 0.0
    total_cost_usd: float = 0.0
    avg_cost_usd: float = 0.0
    total_duration_seconds: float = 0.0
    avg_duration_seconds: float = 0.0
    total_tool_calls: int = 0
    avg_tool_calls: float = 0.0
    total_errors: int = 0
    error_rate: float = 0.0

    def to_dict(self) -> dict:
        return {
            "total_tasks": self.total_tasks,
            "successful": self.successful,
            "failed": self.failed,
            "success_rate": self.success_rate,
            "total_steps": self.total_steps,
            "avg_steps": self.avg_steps,
            "total_tokens": self.total_tokens,
            "avg_tokens": self.avg_tokens,
            "total_cost_usd": self.total_cost_usd,
            "avg_cost_usd": self.avg_cost_usd,
            "total_duration_seconds": self.total_duration_seconds,
            "avg_duration_seconds": self.avg_duration_seconds,
            "total_tool_calls": self.total_tool_calls,
            "avg_tool_calls": self.avg_tool_calls,
            "total_errors": self.total_errors,
            "error_rate": self.error_rate,
        }


def aggregate_metrics(run_metrics: list[RunMetrics]) -> AggregatedMetrics:
    if not run_metrics:
        return AggregatedMetrics()

    total = len(run_metrics)
    successful = sum(1 for m in run_metrics if m.success)

    return AggregatedMetrics(
        total_tasks=total,
        successful=successful,
        failed=total - successful,
        success_rate=successful / total if total > 0 else 0.0,
        total_steps=sum(m.steps for m in run_metrics),
        avg_steps=sum(m.steps for m in run_metrics) / total,
        total_tokens=sum(m.tokens for m in run_metrics),
        avg_tokens=sum(m.tokens for m in run_metrics) / total,
        total_cost_usd=sum(m.cost_usd for m in run_metrics),
        avg_cost_usd=sum(m.cost_usd for m in run_metrics) / total,
        total_duration_seconds=sum(m.duration_seconds for m in run_metrics),
        avg_duration_seconds=sum(m.duration_seconds for m in run_metrics) / total,
        total_tool_calls=sum(m.tool_calls for m in run_metrics),
        avg_tool_calls=sum(m.tool_calls for m in run_metrics) / total,
        total_errors=sum(m.errors for m in run_metrics),
        error_rate=sum(m.errors for m in run_metrics) / total if total > 0 else 0.0,
    )
