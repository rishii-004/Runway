import pytest
from langgraph.checkpoint.memory import MemorySaver

from forge.agents.demo_echo_agent import build_demo_graph
from forge.agents.langgraph_adapter import LangGraphAdapter


@pytest.fixture
def adapter():
    graph = build_demo_graph()
    checkpointer = MemorySaver()
    compiled = graph.compile(checkpointer=checkpointer)
    return LangGraphAdapter(compiled)


async def test_adapter_steps_through_graph(adapter):
    config = {"configurable": {"thread_id": "test-adapter-1"}}

    result = await adapter.astep({"task": "hello"}, config)
    assert result is not None
    assert result.node_name == "plan"
    assert "planned" in result.state.get("step1_result", "")

    result = await adapter.astep(None, config)
    assert result is not None
    assert result.node_name == "execute"

    result = await adapter.astep(None, config)
    assert result is not None
    assert result.node_name == "summarize"

    state = await adapter.aget_state(config)
    assert state is not None
    assert "done" in state["final_result"]


async def test_adapter_returns_none_when_done(adapter):
    config = {"configurable": {"thread_id": "test-adapter-2"}}
    await adapter.astep({"task": "hello"}, config)
    await adapter.astep(None, config)
    await adapter.astep(None, config)
    result = await adapter.astep(None, config)
    assert result is None
