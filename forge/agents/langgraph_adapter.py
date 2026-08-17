from __future__ import annotations

from dataclasses import dataclass
from typing import Any, TypedDict

import structlog
from langgraph.graph import END, StateGraph
from langgraph.graph.state import CompiledStateGraph

logger = structlog.get_logger()


@dataclass
class StepResult:
    node_name: str
    output: dict[str, Any]
    state: dict[str, Any]


class LangGraphAdapter:
    def __init__(self, graph: CompiledStateGraph):
        self.graph = graph

    async def astep(
        self,
        input_state: dict[str, Any] | None,
        config: dict[str, Any],
    ) -> StepResult | None:
        async for event in self.graph.astream(
            input_state, config=config, stream_mode="updates"
        ):
            for node_name, output in event.items():
                if node_name == "__interrupt__":
                    return StepResult(
                        node_name="__interrupt__",
                        output={},
                        state={},
                    )
                state = await self.graph.aget_state(config)
                result = StepResult(
                    node_name=node_name,
                    output=output if isinstance(output, dict) else {"result": output},
                    state=state.values if state else {},
                )
                logger.info("step_completed", node=node_name, state_keys=list(result.state.keys()))
                return result
        return None

    async def aget_state(self, config: dict[str, Any]) -> dict[str, Any] | None:
        state = await self.graph.aget_state(config)
        return state.values if state else None

    async def aget_next_nodes(self, config: dict[str, Any]) -> tuple[str, ...]:
        state = await self.graph.aget_state(config)
        return state.next if state else ()

    async def aupdate_state(
        self,
        config: dict[str, Any],
        values: dict[str, Any],
    ) -> None:
        await self.graph.aupdate_state(config, values)

    @property
    def stream_channels(self) -> list[str]:
        return self.graph.stream_channels_list
