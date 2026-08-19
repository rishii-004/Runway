from __future__ import annotations

import pytest

from forge.policy.engine import PolicyEngine
from forge.sandbox.docker import SandboxResult
from forge.tools.executor import ToolExecutionError, ToolGateway
from forge.tools.models import RiskLevel, ToolSpec
from forge.tools.registry import ToolRegistry


class FakeSandbox:
    def __init__(self, result: SandboxResult | None = None):
        self._result = result or SandboxResult(stdout="ok", stderr="", exit_code=0)
        self.last_call = None

    async def run(self, command, **kwargs):
        self.last_call = {"command": command, **kwargs}
        return self._result


def _make_sandboxed_gateway(sandbox_result: SandboxResult | None = None):
    registry = ToolRegistry()
    registry.register(
        ToolSpec(name="run_tests", risk=RiskLevel.MEDIUM, sandbox=True, timeout_seconds=60)
    )
    registry.register(
        ToolSpec(name="read_file", risk=RiskLevel.LOW, sandbox=False)
    )
    engine = PolicyEngine()
    sandbox = FakeSandbox(sandbox_result)
    gateway = ToolGateway(
        registry,
        engine,
        sandbox=sandbox,
        tool_impls={"read_file": lambda: "file contents"},
    )
    return gateway, sandbox


class TestSandboxedExecution:
    async def test_sandboxed_tool_runs_in_container(self):
        result = SandboxResult(stdout='{"passed": 5}', stderr="", exit_code=0)
        gateway, sandbox = _make_sandboxed_gateway(result)

        output = await gateway.execute(
            "run_tests", {"path": "/workspace"}, run_id="r1", agent_id="a1"
        )

        assert output == {"passed": 5}
        assert sandbox.last_call is not None
        assert "run_tests" in sandbox.last_call["command"]

    async def test_sandboxed_tool_timeout_from_spec(self):
        result = SandboxResult(stdout="done", stderr="", exit_code=0)
        gateway, sandbox = _make_sandboxed_gateway(result)

        await gateway.execute("run_tests", run_id="r1", agent_id="a1")

        assert sandbox.last_call["timeout_seconds"] == 60

    async def test_sandboxed_tool_nonzero_exit_raises(self):
        result = SandboxResult(stdout="", stderr="test failed", exit_code=1)
        gateway, _ = _make_sandboxed_gateway(result)

        with pytest.raises(ToolExecutionError) as exc_info:
            await gateway.execute("run_tests", run_id="r1", agent_id="a1")

        assert exc_info.value.tool_name == "run_tests"

    async def test_non_sandboxed_tool_runs_in_process(self):
        gateway, _ = _make_sandboxed_gateway()

        result = await gateway.execute("read_file", run_id="r1", agent_id="a1")
        assert result == "file contents"

    async def test_sandboxed_tool_stdout_not_json(self):
        result = SandboxResult(stdout="plain text output", stderr="", exit_code=0)
        gateway, _ = _make_sandboxed_gateway(result)

        output = await gateway.execute("run_tests", run_id="r1", agent_id="a1")

        assert output == {"stdout": "plain text output", "exit_code": 0}

    async def test_sandboxed_tool_no_sandbox_raises(self):
        registry = ToolRegistry()
        registry.register(
            ToolSpec(name="run_tests", risk=RiskLevel.MEDIUM, sandbox=True)
        )
        engine = PolicyEngine()
        gateway = ToolGateway(registry, engine, sandbox=None)

        with pytest.raises(Exception, match="run_tests"):
            await gateway.execute("run_tests", run_id="r1", agent_id="a1")
