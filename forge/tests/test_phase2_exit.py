from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from forge.policy.engine import PolicyEngine
from forge.policy.rules import PolicyDecision
from forge.tools.executor import ApprovalError, ToolGateway
from forge.tools.models import RiskLevel, ToolSpec
from forge.tools.registry import ToolRegistry


def _build_gateway_with_approval_tool() -> tuple[ToolGateway, MagicMock]:
    registry = ToolRegistry()
    registry.register(
        ToolSpec(
            name="execute_migration",
            risk=RiskLevel.HIGH,
            requires_approval=True,
            timeout_seconds=60,
        )
    )

    policy_engine = PolicyEngine()
    mock_fn = MagicMock(return_value="migration executed")
    gateway = ToolGateway(
        registry, policy_engine, tool_impls={"execute_migration": mock_fn}
    )
    return gateway, mock_fn


class TestPhaseExitHITL:
    async def test_unapproved_high_risk_tool_never_executes(self):
        gateway, mock_fn = _build_gateway_with_approval_tool()

        with pytest.raises(ApprovalError):
            await gateway.execute(
                "execute_migration",
                {"target": "production"},
                run_id="run-1",
                agent_id="agent-1",
            )

        mock_fn.assert_not_called()

    async def test_approved_high_risk_tool_executes_once(self):
        gateway, mock_fn = _build_gateway_with_approval_tool()

        result = await gateway.execute(
            "execute_migration",
            {"target": "production"},
            run_id="run-1",
            agent_id="agent-1",
            already_approved=True,
        )

        assert result == "migration executed"
        mock_fn.assert_called_once()
        mock_fn.assert_called_with(target="production")

    async def test_approval_error_contains_tool_and_args(self):
        gateway, _ = _build_gateway_with_approval_tool()

        with pytest.raises(ApprovalError) as exc_info:
            await gateway.execute(
                "execute_migration",
                {"target": "staging"},
                run_id="run-2",
                agent_id="agent-1",
            )

        assert exc_info.value.tool_name == "execute_migration"
        assert exc_info.value.arguments == {"target": "staging"}

    async def test_policy_decision_is_require_approval(self):
        registry = ToolRegistry()
        registry.register(
            ToolSpec(name="kubectl", risk=RiskLevel.HIGH, requires_approval=True)
        )
        engine = PolicyEngine()
        tool_spec = registry.get("kubectl")
        decision = engine.evaluate_tool(tool_spec, run_id="r1", agent_id="a1")
        assert decision == PolicyDecision.REQUIRE_APPROVAL

    async def test_low_risk_tool_bypasses_approval(self):
        registry = ToolRegistry()
        registry.register(
            ToolSpec(name="read_file", risk=RiskLevel.LOW, requires_approval=False)
        )
        engine = PolicyEngine()
        tool_spec = registry.get("read_file")
        decision = engine.evaluate_tool(tool_spec, run_id="r1", agent_id="a1")
        assert decision == PolicyDecision.ALLOW

    async def test_medium_risk_tool_with_approval_flag_requires(self):
        registry = ToolRegistry()
        registry.register(
            ToolSpec(name="apply_patch", risk=RiskLevel.MEDIUM, requires_approval=True)
        )
        engine = PolicyEngine()
        tool_spec = registry.get("apply_patch")
        decision = engine.evaluate_tool(tool_spec, run_id="r1", agent_id="a1")
        assert decision == PolicyDecision.REQUIRE_APPROVAL
