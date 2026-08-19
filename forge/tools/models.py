from __future__ import annotations

from pydantic import BaseModel, field_validator

from forge.shared import RiskLevel


class ToolSpec(BaseModel):
    name: str
    description: str = ""
    risk: RiskLevel = RiskLevel.LOW
    requires_approval: bool = False
    timeout_seconds: int = 30
    sandbox: bool = False
    rate_limit_rpm: int | None = None

    @field_validator("risk", mode="before")
    @classmethod
    def coerce_risk(cls, v: str | int | RiskLevel) -> RiskLevel:
        if isinstance(v, RiskLevel):
            return v
        if isinstance(v, int):
            return RiskLevel(v)
        if isinstance(v, str):
            return RiskLevel.from_str(v)
        raise ValueError(f"Cannot convert {v!r} to RiskLevel")

    def __repr__(self) -> str:
        return f"ToolSpec(name={self.name!r}, risk={self.risk})"
