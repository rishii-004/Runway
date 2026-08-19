from __future__ import annotations

from pathlib import Path

import structlog
import yaml

from forge.tools.models import ToolSpec

logger = structlog.get_logger()

_DEFAULT_REGISTRY_PATH = Path(__file__).parent / "registry.yaml"


class ToolNotFoundError(Exception):
    def __init__(self, name: str) -> None:
        super().__init__(f"Tool {name!r} not found in registry")
        self.name = name


class ToolRegistry:
    def __init__(self) -> None:
        self._tools: dict[str, ToolSpec] = {}

    def load_from_yaml(self, path: Path | str) -> None:
        path = Path(path)
        if not path.exists():
            logger.warning("registry_file_not_found", path=str(path))
            return

        with open(path) as f:
            data = yaml.safe_load(f)

        if not data or "tools" not in data:
            logger.warning("registry_empty_or_invalid", path=str(path))
            return

        for tool_data in data["tools"]:
            spec = ToolSpec(**tool_data)
            self._tools[spec.name] = spec
            logger.debug("tool_registered", name=spec.name, risk=spec.risk.value)

        logger.info("registry_loaded", path=str(path), count=len(self._tools))

    def register(self, spec: ToolSpec) -> None:
        self._tools[spec.name] = spec

    def get(self, name: str) -> ToolSpec:
        if name not in self._tools:
            raise ToolNotFoundError(name)
        return self._tools[name]

    def list_tools(self) -> list[ToolSpec]:
        return list(self._tools.values())

    def has(self, name: str) -> bool:
        return name in self._tools


def load_default_registry() -> ToolRegistry:
    registry = ToolRegistry()
    registry.load_from_yaml(_DEFAULT_REGISTRY_PATH)
    return registry
