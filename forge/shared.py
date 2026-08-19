from __future__ import annotations

from enum import IntEnum


class RiskLevel(IntEnum):
    LOW = 0
    MEDIUM = 1
    HIGH = 2

    @classmethod
    def from_str(cls, value: str) -> RiskLevel:
        mapping = {"low": cls.LOW, "medium": cls.MEDIUM, "high": cls.HIGH}
        if value.lower() in mapping:
            return mapping[value.lower()]
        raise ValueError(f"Invalid risk level: {value!r}")

    def __str__(self) -> str:
        return self.name.lower()
