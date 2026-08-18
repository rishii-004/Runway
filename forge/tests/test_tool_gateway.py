from __future__ import annotations

import pytest

from forge.policy.engine import PolicyEngine
from forge.policy.rules import PolicyDecision, PolicyRule
from forge.tools.executor import (
    ApprovalError,
    PermissionError,
    ToolExecutionError,
    ToolGateway,
)
from forge.tools.models import RiskLevel, ToolSpec
from forge.tools.registry import ToolRegistry


def _make_gateway(
    tools: list[ToolSpec] | None = None,
    impls: dict | None = None,
    rules: list[PolicyRule] | None = None,
    use_default_rules: bool = False,
) -> ToolGateway:
    registry = ToolRegistry()
    for t in tools or []:
        registry.register(t)
    engine = PolicyEngine() if use_default_rules else PolicyEngine(rules=rules or [])
    return ToolGateway(registry, engine, tool_impls=impls or {})


class TestToolGatewayAllow:
    async def test_low_risk_tool_executes(self):
        gateway = _make_gateway(
            tools=[ToolSpec(name="read_file", risk=RiskLevel.LOW)],
            impls={"read_file": lambda: "file contents"},
        )
        result = await gateway.execute(
            "read_file", run_id="r1", agent_id="a1"
        )
        assert result == "file contents"

    async def test_async_tool_executes(self):
        async def async_impl():
            return "async result"

        gateway = _make_gateway(
            tools=[ToolSpec(name="async_tool", risk=RiskLevel.LOW)],
            impls={"async_tool": async_impl},
        )
        result = await gateway.execute(
            "async_tool", run_id="r1", agent_id="a1"
        )
        assert result == "async result"

    async def test_tool_with_arguments(self):
        def grep(pattern: str, path: str = "."):
            return f"found {pattern} in {path}"

        gateway = _make_gateway(
            tools=[ToolSpec(name="grep", risk=RiskLevel.LOW)],
            impls={"grep": grep},
        )
        result = await gateway.execute(
            "grep",
            {"pattern": "TODO", "path": "src/"},
            run_id="r1",
            agent_id="a1",
        )
        assert result == "found TODO in src/"

    async def test_unregistered_tool_raises(self):
        gateway = _make_gateway()
        with pytest.raises(Exception, match="not found"):
            await gateway.execute("nonexistent", run_id="r1", agent_id="a1")


class TestToolGatewayDeny:
    async def test_blocked_tool_raises(self):
        gateway = _make_gateway(
            tools=[ToolSpec(name="rm_rf", risk=RiskLevel.LOW)],
            use_default_rules=True,
        )
        with pytest.raises(PermissionError) as exc_info:
            await gateway.execute("rm_rf", run_id="r1", agent_id="a1")
        assert exc_info.value.tool_name == "rm_rf"
        assert exc_info.value.decision == PolicyDecision.DENY

    async def test_denied_tool_impl_not_called(self):
        def mock_fn():
            return "should not run"

        gateway = _make_gateway(
            tools=[ToolSpec(name="rm_rf", risk=RiskLevel.LOW)],
            impls={"rm_rf": mock_fn},
            use_default_rules=True,
        )
        with pytest.raises(PermissionError):
            await gateway.execute("rm_rf", run_id="r1", agent_id="a1")


class TestToolGatewayApproval:
    async def test_high_risk_raises_approval_required(self):
        gateway = _make_gateway(
            tools=[ToolSpec(name="kubectl", risk=RiskLevel.HIGH)],
            use_default_rules=True,
        )
        with pytest.raises(ApprovalError) as exc_info:
            await gateway.execute("kubectl", run_id="r1", agent_id="a1")
        assert exc_info.value.tool_name == "kubectl"

    async def test_approval_flagged_tool_raises(self):
        gateway = _make_gateway(
            tools=[ToolSpec(name="deploy", risk=RiskLevel.MEDIUM, requires_approval=True)],
            use_default_rules=True,
        )
        with pytest.raises(ApprovalError):
            await gateway.execute("deploy", run_id="r1", agent_id="a1")

    async def test_already_approved_bypasses(self):
        gateway = _make_gateway(
            tools=[ToolSpec(name="kubectl", risk=RiskLevel.HIGH)],
            impls={"kubectl": lambda: "deployed"},
            use_default_rules=True,
        )
        result = await gateway.execute(
            "kubectl", run_id="r1", agent_id="a1", already_approved=True
        )
        assert result == "deployed"

    async def test_approval_required_tool_impl_not_called(self):
        def mock_fn():
            return "should not run"

        gateway = _make_gateway(
            tools=[ToolSpec(name="kubectl", risk=RiskLevel.HIGH)],
            impls={"kubectl": mock_fn},
            use_default_rules=True,
        )
        with pytest.raises(ApprovalError):
            await gateway.execute("kubectl", run_id="r1", agent_id="a1")


class TestToolGatewayError:
    async def test_tool_impl_exception_wrapped(self):
        def failing_tool():
            raise RuntimeError("boom")

        gateway = _make_gateway(
            tools=[ToolSpec(name="failing", risk=RiskLevel.LOW)],
            impls={"failing": failing_tool},
        )
        with pytest.raises(ToolExecutionError) as exc_info:
            await gateway.execute("failing", run_id="r1", agent_id="a1")
        assert exc_info.value.tool_name == "failing"
        assert isinstance(exc_info.value.cause, RuntimeError)

    async def test_no_impl_returns_no_impl_status(self):
        gateway = _make_gateway(
            tools=[ToolSpec(name="stub", risk=RiskLevel.LOW)],
        )
        result = await gateway.execute("stub", run_id="r1", agent_id="a1")
        assert result == {"status": "no_impl", "tool": "stub"}

    async def test_register_impl(self):
        gateway = _make_gateway(
            tools=[ToolSpec(name="dynamic", risk=RiskLevel.LOW)],
        )
        gateway.register_impl("dynamic", lambda: "registered later")
        result = await gateway.execute("dynamic", run_id="r1", agent_id="a1")
        assert result == "registered later"
