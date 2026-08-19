from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel

from forge.shared import RiskLevel


class PolicyDecision(StrEnum):
    ALLOW = "ALLOW"
    DENY = "DENY"
    REQUIRE_APPROVAL = "REQUIRE_APPROVAL"


class PolicyContext(BaseModel):
    run_id: str
    agent_id: str
    tool_name: str
    risk: RiskLevel
    requires_approval: bool = False
    already_approved: bool = False


class PolicyRule(BaseModel):
    name: str
    description: str = ""
    blocked_tools: list[str] = []
    max_risk_without_approval: RiskLevel = RiskLevel.LOW
    require_approval_for_high_risk: bool = True
    enabled: bool = True

    def evaluate(self, ctx: PolicyContext) -> PolicyDecision | None:
        if not self.enabled:
            return None

        if ctx.tool_name in self.blocked_tools:
            return PolicyDecision.DENY

        if ctx.already_approved:
            return PolicyDecision.ALLOW

        if self.require_approval_for_high_risk and (
            ctx.requires_approval or ctx.risk == RiskLevel.HIGH
        ):
            return PolicyDecision.REQUIRE_APPROVAL

        if ctx.risk <= self.max_risk_without_approval:
            return PolicyDecision.ALLOW

        return None


DEFAULT_RULES = [
    PolicyRule(
        name="blocked_tools",
        description="Explicitly blocked tools are never allowed",
        blocked_tools=["rm_rf", "drop_table", "format_disk"],
    ),
    PolicyRule(
        name="approval_required",
        description="High-risk tools and tools requiring approval need human approval",
        require_approval_for_high_risk=True,
    ),
    PolicyRule(
        name="low_risk_auto_allow",
        description="Low and medium risk tools are auto-allowed",
        max_risk_without_approval=RiskLevel.MEDIUM,
    ),
]
