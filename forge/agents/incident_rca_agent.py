from __future__ import annotations

from typing import Any, TypedDict

from langgraph.graph import END, StateGraph


class IncidentState(TypedDict):
    alert: dict[str, Any]
    metrics: dict[str, Any]
    logs: list[dict[str, str]]
    traces: list[dict[str, Any]]
    hypothesis: str
    verification: dict[str, str]
    remediation_action: str | None
    remediation_result: str | None
    report: str


def receive_alert(state: IncidentState) -> dict:
    alert = state.get("alert", {})
    return {
        "alert": alert,
    }


def gather_metrics(state: IncidentState) -> dict:
    return {
        "metrics": {
            "cpu_percent": 95.2,
            "memory_percent": 87.1,
            "error_rate_5m": 12.5,
            "p99_latency_ms": 4500,
            "queue_depth": 1520,
        }
    }


def gather_logs(state: IncidentState) -> dict:
    return {
        "logs": [
            {
                "timestamp": "2026-01-01T12:00:00Z",
                "level": "ERROR",
                "message": "Connection pool exhausted",
            },
            {
                "timestamp": "2026-01-01T12:00:01Z",
                "level": "ERROR",
                "message": "Retry queue full",
            },
            {
                "timestamp": "2026-01-01T12:00:02Z",
                "level": "WARN",
                "message": "Circuit breaker OPEN for db-primary",
            },
        ]
    }


def gather_traces(state: IncidentState) -> dict:
    return {
        "traces": [
            {"span": "db.query", "duration_ms": 3200, "status": "error"},
            {"span": "api.request", "duration_ms": 4100, "status": "error"},
        ]
    }


def form_hypothesis(state: IncidentState) -> dict:
    metrics = state.get("metrics", {})
    logs = state.get("logs", [])

    has_db_error = any("db" in log.get("message", "").lower() for log in logs)
    high_latency = metrics.get("p99_latency_ms", 0) > 3000

    if has_db_error and high_latency:
        hypothesis = (
            "Root cause: Database connection pool exhaustion under high load. "
            "The db-primary circuit breaker opened, causing cascading failures."
        )
    else:
        hypothesis = "Root cause: Unknown. Further investigation needed."

    return {"hypothesis": hypothesis}


def verify_hypothesis(state: IncidentState) -> dict:
    hypothesis = state.get("hypothesis", "")
    verified = "connection pool" in hypothesis.lower()

    return {
        "verification": {
            "verified": str(verified),
            "evidence": "Metrics show correlated CPU spike and latency increase",
            "confidence": "high" if verified else "low",
        }
    }


def decide_remediation(state: IncidentState) -> dict:
    verification = state.get("verification", {})
    if verification.get("verified") == "True":
        return {"remediation_action": "restart_db_pool"}
    return {"remediation_action": None}


def execute_remediation(state: IncidentState) -> dict:
    action = state.get("remediation_action")
    if action == "restart_db_pool":
        return {
            "remediation_result": "DB connection pool restarted successfully. "
            "Queue depth reduced from 1520 to 45.",
            "report": "Incident resolved. DB pool restart restored service.",
        }
    return {
        "remediation_result": None,
        "report": "No remediation needed or taken.",
    }


def should_remediate(state: IncidentState) -> str:
    if state.get("remediation_action"):
        return "execute_remediation"
    return "no_remediation"


def no_remediation(state: IncidentState) -> dict:
    return {
        "report": (
            f"Hypothesis: {state.get('hypothesis', 'N/A')}\n"
            f"Verification: {state.get('verification', {})}\n"
            "No automated remediation attempted."
        )
    }


def build_incident_rca_graph() -> StateGraph:
    graph = StateGraph(IncidentState)
    graph.add_node("receive_alert", receive_alert)
    graph.add_node("gather_metrics", gather_metrics)
    graph.add_node("gather_logs", gather_logs)
    graph.add_node("gather_traces", gather_traces)
    graph.add_node("form_hypothesis", form_hypothesis)
    graph.add_node("verify_hypothesis", verify_hypothesis)
    graph.add_node("decide_remediation", decide_remediation)
    graph.add_node("execute_remediation", execute_remediation)
    graph.add_node("no_remediation", no_remediation)

    graph.set_entry_point("receive_alert")
    graph.add_edge("receive_alert", "gather_metrics")
    graph.add_edge("gather_metrics", "gather_logs")
    graph.add_edge("gather_logs", "gather_traces")
    graph.add_edge("gather_traces", "form_hypothesis")
    graph.add_edge("form_hypothesis", "verify_hypothesis")
    graph.add_edge("verify_hypothesis", "decide_remediation")
    graph.add_conditional_edges(
        "decide_remediation",
        should_remediate,
        {
            "execute_remediation": "execute_remediation",
            "no_remediation": "no_remediation",
        },
    )
    graph.add_edge("execute_remediation", END)
    graph.add_edge("no_remediation", END)

    return graph
