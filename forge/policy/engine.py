from __future__ import annotations

from typing import TYPE_CHECKING

import structlog

from forge.policy.rules import (
    DEFAULT_RULES,
    PolicyContext,
    PolicyDecision,
    PolicyRule,
)

if TYPE_CHECKING:
    from forge.tools.models import ToolSpec

logger = structlog.get_logger()


class PolicyEngine:
    def __init__(self, rules: list[PolicyRule] | None = None):
        if rules is None:
            self.rules = list(DEFAULT_RULES)
        else:
            self.rules = rules

    def evaluate(self, tool_spec: ToolSpec, context: PolicyContext) -> PolicyDecision:
        for rule in self.rules:
            decision = rule.evaluate(context)
            if decision is not None:
                logger.info(
                    "policy_decision",
                    tool=tool_spec.name,
                    decision=decision.value,
                    rule=rule.name,
                    risk=str(context.risk),
                )
                return decision

        logger.info(
            "policy_default_allow",
            tool=tool_spec.name,
            risk=str(context.risk),
        )
        return PolicyDecision.ALLOW

    def evaluate_tool(
        self,
        tool_spec: ToolSpec,
        run_id: str,
        agent_id: str,
        already_approved: bool = False,
    ) -> PolicyDecision:
        context = PolicyContext(
            run_id=run_id,
            agent_id=agent_id,
            tool_name=tool_spec.name,
            risk=tool_spec.risk,
            requires_approval=tool_spec.requires_approval,
            already_approved=already_approved,
        )
        return self.evaluate(tool_spec, context)
