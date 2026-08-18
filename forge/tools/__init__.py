from forge.shared import RiskLevel
from forge.tools.models import ToolSpec
from forge.tools.registry import ToolNotFoundError, ToolRegistry, load_default_registry

__all__ = [
    "ApprovalError",
    "PermissionError",
    "RiskLevel",
    "ToolExecutionError",
    "ToolGateway",
    "ToolNotFoundError",
    "ToolRegistry",
    "ToolSpec",
    "load_default_registry",
]


def __getattr__(name: str):
    if name in ("ToolGateway", "ApprovalError", "PermissionError", "ToolExecutionError"):
        from forge.tools import executor

        return getattr(executor, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
