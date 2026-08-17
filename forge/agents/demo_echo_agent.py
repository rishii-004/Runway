from typing import TypedDict

from langgraph.graph import END, StateGraph


class EchoState(TypedDict):
    task: str
    step1_result: str
    step2_result: str
    final_result: str


def plan(state: EchoState) -> dict:
    return {"step1_result": f"planned: {state['task']}"}


def execute(state: EchoState) -> dict:
    return {"step2_result": f"executed: {state['step1_result']}"}


def summarize(state: EchoState) -> dict:
    return {"final_result": f"done: {state['step2_result']}"}


def build_demo_graph() -> StateGraph:
    graph = StateGraph(EchoState)
    graph.add_node("plan", plan)
    graph.add_node("execute", execute)
    graph.add_node("summarize", summarize)
    graph.set_entry_point("plan")
    graph.add_edge("plan", "execute")
    graph.add_edge("execute", "summarize")
    graph.add_edge("summarize", END)
    return graph
