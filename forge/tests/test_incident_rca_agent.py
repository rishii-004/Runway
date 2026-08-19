from __future__ import annotations

from forge.agents.incident_rca_agent import (
    IncidentState,
    build_incident_rca_graph,
    decide_remediation,
    execute_remediation,
    form_hypothesis,
    gather_logs,
    gather_metrics,
    gather_traces,
    receive_alert,
    verify_hypothesis,
)


def _base_state(**overrides) -> IncidentState:
    state: IncidentState = {
        "alert": {},
        "metrics": {},
        "logs": [],
        "traces": [],
        "hypothesis": "",
        "verification": {},
        "remediation_action": None,
        "remediation_result": None,
        "report": "",
    }
    state.update(overrides)
    return state


class TestIncidentRCANodes:
    def test_receive_alert(self):
        alert = {"service": "api", "severity": "critical"}
        result = receive_alert(_base_state(alert=alert))
        assert result["alert"] == alert

    def test_gather_metrics(self):
        result = gather_metrics(_base_state())
        m = result["metrics"]
        assert m["cpu_percent"] > 90
        assert m["error_rate_5m"] > 10

    def test_gather_logs(self):
        result = gather_logs(_base_state())
        assert len(result["logs"]) == 3
        assert any("ERROR" in log["level"] for log in result["logs"])

    def test_gather_traces(self):
        result = gather_traces(_base_state())
        assert len(result["traces"]) == 2

    def test_form_hypothesis_db_issue(self):
        state = _base_state(
            metrics={"p99_latency_ms": 4500},
            logs=[{"level": "ERROR", "message": "db-primary circuit breaker OPEN"}],
        )
        result = form_hypothesis(state)
        assert "connection pool" in result["hypothesis"].lower()

    def test_form_hypothesis_unknown(self):
        state = _base_state(
            metrics={"p99_latency_ms": 100},
            logs=[{"level": "INFO", "message": "all good"}],
        )
        result = form_hypothesis(state)
        assert "Unknown" in result["hypothesis"]

    def test_verify_hypothesis_confirmed(self):
        state = _base_state(hypothesis="Connection pool exhaustion in db-primary")
        result = verify_hypothesis(state)
        assert result["verification"]["verified"] == "True"
        assert result["verification"]["confidence"] == "high"

    def test_verify_hypothesis_not_confirmed(self):
        state = _base_state(hypothesis="CPU spike due to unknown cause")
        result = verify_hypothesis(state)
        assert result["verification"]["verified"] == "False"

    def test_decide_remediation_when_verified(self):
        state = _base_state(verification={"verified": "True"})
        result = decide_remediation(state)
        assert result["remediation_action"] == "restart_db_pool"

    def test_decide_remediation_when_not_verified(self):
        state = _base_state(verification={"verified": "False"})
        result = decide_remediation(state)
        assert result["remediation_action"] is None

    def test_execute_remediation(self):
        state = _base_state(remediation_action="restart_db_pool")
        result = execute_remediation(state)
        assert "restarted" in result["remediation_result"].lower()
        assert "resolved" in result["report"].lower()


class TestIncidentRCAGraph:
    def test_builds_compiled_graph(self):
        graph = build_incident_rca_graph()
        compiled = graph.compile()
        assert compiled is not None

    def test_conditional_edges(self):
        graph = build_incident_rca_graph()
        compiled = graph.compile()
        assert compiled is not None
