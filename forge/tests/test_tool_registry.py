from __future__ import annotations

from pathlib import Path

import pytest

from forge.tools.models import RiskLevel, ToolSpec
from forge.tools.registry import ToolNotFoundError, ToolRegistry

SAMPLE_YAML = Path(__file__).parent.parent / "tools" / "registry.yaml"


class TestToolSpec:
    def test_defaults(self):
        spec = ToolSpec(name="test_tool")
        assert spec.name == "test_tool"
        assert spec.risk == RiskLevel.LOW
        assert spec.requires_approval is False
        assert spec.timeout_seconds == 30
        assert spec.sandbox is False
        assert spec.rate_limit_rpm is None

    def test_custom_values(self):
        spec = ToolSpec(
            name="kubectl",
            risk=RiskLevel.HIGH,
            requires_approval=True,
            timeout_seconds=60,
            sandbox=True,
            rate_limit_rpm=10,
        )
        assert spec.risk == RiskLevel.HIGH
        assert spec.requires_approval is True
        assert spec.sandbox is True
        assert spec.rate_limit_rpm == 10

    def test_roundtrip(self):
        spec = ToolSpec(name="x", risk=RiskLevel.MEDIUM)
        data = spec.model_dump()
        restored = ToolSpec(**data)
        assert spec == restored


class TestToolRegistry:
    def test_register_and_get(self):
        registry = ToolRegistry()
        spec = ToolSpec(name="my_tool", risk=RiskLevel.LOW)
        registry.register(spec)
        assert registry.get("my_tool") == spec

    def test_get_unknown_raises(self):
        registry = ToolRegistry()
        with pytest.raises(ToolNotFoundError, match="nonexistent"):
            registry.get("nonexistent")

    def test_has(self):
        registry = ToolRegistry()
        registry.register(ToolSpec(name="a"))
        assert registry.has("a") is True
        assert registry.has("b") is False

    def test_list_tools(self):
        registry = ToolRegistry()
        registry.register(ToolSpec(name="a"))
        registry.register(ToolSpec(name="b"))
        tools = registry.list_tools()
        assert len(tools) == 2
        names = {t.name for t in tools}
        assert names == {"a", "b"}


class TestLoadFromYaml:
    def test_load_default_registry(self):
        registry = ToolRegistry()
        registry.load_from_yaml(SAMPLE_YAML)
        assert len(registry.list_tools()) > 0

    def test_load_known_tools(self):
        registry = ToolRegistry()
        registry.load_from_yaml(SAMPLE_YAML)

        read_file = registry.get("read_file")
        assert read_file.risk == RiskLevel.LOW
        assert read_file.requires_approval is False

        kubectl = registry.get("kubectl")
        assert kubectl.risk == RiskLevel.HIGH
        assert kubectl.requires_approval is True
        assert kubectl.timeout_seconds == 30

    def test_load_sandbox_tool(self):
        registry = ToolRegistry()
        registry.load_from_yaml(SAMPLE_YAML)
        run_tests = registry.get("run_tests")
        assert run_tests.sandbox is True
        assert run_tests.timeout_seconds == 120

    def test_load_missing_file(self, tmp_path):
        registry = ToolRegistry()
        registry.load_from_yaml(tmp_path / "nonexistent.yaml")
        assert len(registry.list_tools()) == 0

    def test_load_empty_yaml(self, tmp_path):
        yaml_file = tmp_path / "empty.yaml"
        yaml_file.write_text("")
        registry = ToolRegistry()
        registry.load_from_yaml(yaml_file)
        assert len(registry.list_tools()) == 0

    def test_load_invalid_yaml(self, tmp_path):
        yaml_file = tmp_path / "bad.yaml"
        yaml_file.write_text("not: [a, valid, tool, config]")
        registry = ToolRegistry()
        registry.load_from_yaml(yaml_file)
        assert len(registry.list_tools()) == 0
