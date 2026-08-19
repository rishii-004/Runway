from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING, Any

import structlog

from forge.policy.engine import PolicyEngine
from forge.policy.rules import PolicyDecision
from forge.tools.registry import ToolNotFoundError, ToolRegistry

if TYPE_CHECKING:
    from forge.sandbox.docker import DockerSandbox

logger = structlog.get_logger()


class PermissionError(Exception):
    def __init__(self, tool_name: str, decision: PolicyDecision) -> None:
        self.tool_name = tool_name
        self.decision = decision
        super().__init__(f"Tool {tool_name!r} denied by policy: {decision.value}")


class ApprovalError(Exception):
    def __init__(self, tool_name: str, arguments: dict | None = None) -> None:
        self.tool_name = tool_name
        self.arguments = arguments
        super().__init__(f"Tool {tool_name!r} requires human approval")


class ToolExecutionError(Exception):
    def __init__(self, tool_name: str, cause: Exception) -> None:
        self.tool_name = tool_name
        self.cause = cause
        super().__init__(f"Tool {tool_name!r} execution failed: {cause}")


class ToolGateway:
    def __init__(
        self,
        registry: ToolRegistry,
        policy_engine: PolicyEngine,
        tool_impls: dict[str, Callable[..., Any]] | None = None,
        sandbox: DockerSandbox | None = None,
    ):
        self.registry = registry
        self.policy_engine = policy_engine
        self._tool_impls: dict[str, Callable[..., Any]] = tool_impls or {}
        self._sandbox = sandbox

    def register_impl(self, name: str, fn: Callable[..., Any]) -> None:
        self._tool_impls[name] = fn

    async def execute(
        self,
        tool_name: str,
        arguments: dict | None = None,
        *,
        run_id: str,
        agent_id: str,
        already_approved: bool = False,
    ) -> Any:
        try:
            tool_spec = self.registry.get(tool_name)
        except ToolNotFoundError:
            logger.warning("tool_not_registered", tool=tool_name)
            raise

        decision = self.policy_engine.evaluate_tool(
            tool_spec, run_id=run_id, agent_id=agent_id, already_approved=already_approved
        )

        logger.info(
            "tool_gateway_decision",
            tool=tool_name,
            decision=decision.value,
            run_id=run_id,
        )

        if decision == PolicyDecision.DENY:
            raise PermissionError(tool_name, decision)

        if decision == PolicyDecision.REQUIRE_APPROVAL:
            raise ApprovalError(tool_name, arguments)

        if tool_spec.sandbox:
            if self._sandbox is None:
                logger.error("sandbox_required_but_unavailable", tool=tool_name)
                raise ToolExecutionError(
                    tool_name,
                    RuntimeError("Sandbox required but no sandbox configured"),
                )
            return await self._execute_sandboxed(tool_name, tool_spec, arguments)

        impl = self._tool_impls.get(tool_name)
        if impl is None:
            logger.warning("tool_no_impl", tool=tool_name)
            return {"status": "no_impl", "tool": tool_name}

        try:
            if callable(impl):
                import asyncio

                if asyncio.iscoroutinefunction(impl):
                    result = await impl(**(arguments or {}))
                else:
                    result = impl(**(arguments or {}))
            else:
                result = impl

            logger.info("tool_executed", tool=tool_name, run_id=run_id)
            return result

        except Exception as e:
            logger.error("tool_execution_error", tool=tool_name, error=str(e))
            raise ToolExecutionError(tool_name, e) from e

    async def _execute_sandboxed(
        self, tool_name: str, tool_spec: Any, arguments: dict | None
    ) -> dict[str, Any]:
        import json

        cmd_parts = [tool_name]
        if arguments:
            cmd_parts.extend(json.dumps(arguments).split())

        result = await self._sandbox.run(
            cmd_parts,
            timeout_seconds=tool_spec.timeout_seconds,
        )

        logger.info(
            "sandbox_tool_executed",
            tool=tool_name,
            exit_code=result.exit_code,
            timed_out=result.timed_out,
        )

        if result.exit_code != 0:
            raise ToolExecutionError(
                tool_name,
                RuntimeError(f"Sandbox exited {result.exit_code}: {result.stderr[:500]}"),
            )

        try:
            return json.loads(result.stdout)
        except (json.JSONDecodeError, ValueError):
            return {"stdout": result.stdout, "exit_code": result.exit_code}
