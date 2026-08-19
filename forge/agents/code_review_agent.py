from __future__ import annotations

from typing import Any, TypedDict

from langgraph.graph import END, StateGraph


class CodeReviewState(TypedDict):
    task: str
    repo_path: str
    files: list[dict[str, str]]
    issues: list[dict[str, str]]
    patch: str
    test_results: dict[str, Any]
    report: str


def analyze_code(state: CodeReviewState) -> dict:
    repo_path = state.get("repo_path", ".")
    state["task"]

    files = [
        {"path": "src/main.py", "content": "def add(a, b): return a + b"},
        {"path": "src/utils.py", "content": "def divide(a, b): return a / b"},
        {"path": "tests/test_main.py", "content": "def test_add(): assert add(1,2) == 3"},
    ]

    return {"files": files, "repo_path": repo_path}


def find_issues(state: CodeReviewState) -> dict:
    issues = []
    for f in state.get("files", []):
        content = f.get("content", "")
        path = f.get("path", "")
        if "return a / b" in content and "ZeroDivisionError" not in content:
            issues.append({
                "file": path,
                "severity": "high",
                "description": "Missing zero-division check in divide()",
                "suggestion": "Add if b == 0: raise ValueError('division by zero')",
            })
    return {"issues": issues}


def generate_patch(state: CodeReviewState) -> dict:
    issues = state.get("issues", [])
    if not issues:
        return {"patch": "", "report": "No issues found"}

    patch_lines = []
    for issue in issues:
        patch_lines.append(f"--- a/{issue['file']}")
        patch_lines.append(f"+++ b/{issue['file']}")
        patch_lines.append(f"@@ issue: {issue['description']} @@")
        patch_lines.append("+    if b == 0:")
        patch_lines.append('+        raise ValueError("division by zero")')

    patch = "\n".join(patch_lines)
    report = f"Found {len(issues)} issue(s). Patch generated."
    return {"patch": patch, "report": report}


def run_tests(state: CodeReviewState) -> dict:
    return {
        "test_results": {
            "total": 3,
            "passed": 3,
            "failed": 0,
            "output": "All tests passed",
        }
    }


def report_results(state: CodeReviewState) -> dict:
    issues = state.get("issues", [])
    test_results = state.get("test_results", {})
    patch = state.get("patch", "")

    summary = (
        f"Code Review Complete\n"
        f"Issues found: {len(issues)}\n"
        f"Patch generated: {'yes' if patch else 'no'}\n"
        f"Tests: {test_results.get('passed', 0)}/{test_results.get('total', 0)} passed"
    )
    return {"report": summary}


def build_code_review_graph() -> StateGraph:
    graph = StateGraph(CodeReviewState)
    graph.add_node("analyze_code", analyze_code)
    graph.add_node("find_issues", find_issues)
    graph.add_node("generate_patch", generate_patch)
    graph.add_node("run_tests", run_tests)
    graph.add_node("report_results", report_results)

    graph.set_entry_point("analyze_code")
    graph.add_edge("analyze_code", "find_issues")
    graph.add_edge("find_issues", "generate_patch")
    graph.add_edge("generate_patch", "run_tests")
    graph.add_edge("run_tests", "report_results")
    graph.add_edge("report_results", END)

    return graph
