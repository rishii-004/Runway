from __future__ import annotations

from forge.policy.engine import PolicyEngine
from forge.policy.rules import PolicyContext, PolicyDecision, PolicyRule
from forge.tools.models import RiskLevel, ToolSpec


class TestPolicyDecision:
    def test_enum_values(self):
        assert PolicyDecision.ALLOW == "ALLOW"
        assert PolicyDecision.DENY == "DENY"
        assert PolicyDecision.REQUIRE_APPROVAL == "REQUIRE_APPROVAL"


class TestPolicyRule:
    def test_blocked_tool(self):
        rule = PolicyRule(name="block", blocked_tools=["rm_rf"])
        ctx = PolicyContext(
            run_id="r1", agent_id="a1", tool_name="rm_rf", risk=RiskLevel.HIGH
        )
        assert rule.evaluate(ctx) == PolicyDecision.DENY

    def test_not_blocked_tool_passes_block_check(self):
        rule = PolicyRule(
            name="block",
            blocked_tools=["rm_rf"],
            max_risk_without_approval=RiskLevel.LOW,
            require_approval_for_high_risk=False,
        )
        ctx = PolicyContext(
            run_id="r1", agent_id="a1", tool_name="safe_tool", risk=RiskLevel.LOW
        )
        assert rule.evaluate(ctx) == PolicyDecision.ALLOW

    def test_not_blocked_high_risk_not_caught_by_block_rule(self):
        rule = PolicyRule(
            name="block_only",
            blocked_tools=["rm_rf"],
            require_approval_for_high_risk=False,
        )
        ctx = PolicyContext(
            run_id="r1", agent_id="a1", tool_name="safe_tool", risk=RiskLevel.HIGH
        )
        assert rule.evaluate(ctx) is None

    def test_high_risk_requires_approval(self):
        rule = PolicyRule(name="approval", require_approval_for_high_risk=True)
        ctx = PolicyContext(
            run_id="r1", agent_id="a1", tool_name="kubectl", risk=RiskLevel.HIGH
        )
        assert rule.evaluate(ctx) == PolicyDecision.REQUIRE_APPROVAL

    def test_already_approved(self):
        rule = PolicyRule(name="approval", require_approval_for_high_risk=True)
        ctx = PolicyContext(
            run_id="r1",
            agent_id="a1",
            tool_name="kubectl",
            risk=RiskLevel.HIGH,
            already_approved=True,
        )
        assert rule.evaluate(ctx) == PolicyDecision.ALLOW

    def test_low_risk_auto_allow(self):
        rule = PolicyRule(
            name="auto_allow", max_risk_without_approval=RiskLevel.MEDIUM
        )
        ctx = PolicyContext(
            run_id="r1", agent_id="a1", tool_name="read_file", risk=RiskLevel.LOW
        )
        assert rule.evaluate(ctx) == PolicyDecision.ALLOW

    def test_medium_risk_auto_allow(self):
        rule = PolicyRule(
            name="auto_allow", max_risk_without_approval=RiskLevel.MEDIUM
        )
        ctx = PolicyContext(
            run_id="r1",
            agent_id="a1",
            tool_name="apply_patch",
            risk=RiskLevel.MEDIUM,
        )
        assert rule.evaluate(ctx) == PolicyDecision.ALLOW

    def test_disabled_rule_returns_none(self):
        rule = PolicyRule(name="disabled", enabled=False, blocked_tools=["x"])
        ctx = PolicyContext(
            run_id="r1", agent_id="a1", tool_name="x", risk=RiskLevel.HIGH
        )
        assert rule.evaluate(ctx) is None

    def test_explicit_approval_flag(self):
        rule = PolicyRule(name="approval", require_approval_for_high_risk=True)
        ctx = PolicyContext(
            run_id="r1",
            agent_id="a1",
            tool_name="run_tests",
            risk=RiskLevel.MEDIUM,
            requires_approval=True,
        )
        assert rule.evaluate(ctx) == PolicyDecision.REQUIRE_APPROVAL


class TestPolicyEngine:
    def test_low_risk_allowed(self):
        engine = PolicyEngine()
        spec = ToolSpec(name="read_file", risk=RiskLevel.LOW)
        decision = engine.evaluate_tool(spec, run_id="r1", agent_id="a1")
        assert decision == PolicyDecision.ALLOW

    def test_medium_risk_allowed(self):
        engine = PolicyEngine()
        spec = ToolSpec(name="apply_patch", risk=RiskLevel.MEDIUM)
        decision = engine.evaluate_tool(spec, run_id="r1", agent_id="a1")
        assert decision == PolicyDecision.ALLOW

    def test_high_risk_requires_approval(self):
        engine = PolicyEngine()
        spec = ToolSpec(name="kubectl", risk=RiskLevel.HIGH)
        decision = engine.evaluate_tool(spec, run_id="r1", agent_id="a1")
        assert decision == PolicyDecision.REQUIRE_APPROVAL

    def test_high_risk_with_approval_flag(self):
        engine = PolicyEngine()
        spec = ToolSpec(
            name="run_tests", risk=RiskLevel.MEDIUM, requires_approval=True
        )
        decision = engine.evaluate_tool(spec, run_id="r1", agent_id="a1")
        assert decision == PolicyDecision.REQUIRE_APPROVAL

    def test_blocked_tool_denied(self):
        engine = PolicyEngine()
        spec = ToolSpec(name="rm_rf", risk=RiskLevel.LOW)
        decision = engine.evaluate_tool(spec, run_id="r1", agent_id="a1")
        assert decision == PolicyDecision.DENY

    def test_already_approved_allows(self):
        engine = PolicyEngine()
        spec = ToolSpec(name="kubectl", risk=RiskLevel.HIGH)
        decision = engine.evaluate_tool(
            spec, run_id="r1", agent_id="a1", already_approved=True
        )
        assert decision == PolicyDecision.ALLOW

    def test_custom_rules(self):

        class AlwaysBlockRule(PolicyRule):
            def evaluate(self, ctx: PolicyContext) -> PolicyDecision | None:
                if not self.enabled:
                    return None
                return PolicyDecision.DENY

        engine = PolicyEngine(rules=[AlwaysBlockRule(name="block_all")])
        spec = ToolSpec(name="anything", risk=RiskLevel.LOW)
        decision = engine.evaluate_tool(spec, run_id="r1", agent_id="a1")
        assert decision == PolicyDecision.DENY

    def test_empty_rules_allows_everything(self):
        engine = PolicyEngine(rules=[])
        spec = ToolSpec(name="kubectl", risk=RiskLevel.HIGH)
        decision = engine.evaluate_tool(spec, run_id="r1", agent_id="a1")
        assert decision == PolicyDecision.ALLOW
