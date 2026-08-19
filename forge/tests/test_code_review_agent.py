from __future__ import annotations

from forge.agents.code_review_agent import (
    CodeReviewState,
    analyze_code,
    build_code_review_graph,
    find_issues,
    generate_patch,
    report_results,
    run_tests,
)


class TestCodeReviewNodes:
    def test_analyze_code(self):
        state: CodeReviewState = {
            "task": "review code",
            "repo_path": "/tmp/repo",
            "files": [],
            "issues": [],
            "patch": "",
            "test_results": {},
            "report": "",
        }
        result = analyze_code(state)
        assert len(result["files"]) > 0
        assert result["repo_path"] == "/tmp/repo"

    def test_find_issues_detects_division(self):
        state: CodeReviewState = {
            "task": "review code",
            "repo_path": ".",
            "files": [
                {"path": "src/calc.py", "content": "def divide(a, b): return a / b"},
            ],
            "issues": [],
            "patch": "",
            "test_results": {},
            "report": "",
        }
        result = find_issues(state)
        assert len(result["issues"]) == 1
        assert result["issues"][0]["severity"] == "high"

    def test_find_issues_no_problems(self):
        state: CodeReviewState = {
            "task": "review code",
            "repo_path": ".",
            "files": [
                {"path": "src/safe.py", "content": "def add(a, b): return a + b"},
            ],
            "issues": [],
            "patch": "",
            "test_results": {},
            "report": "",
        }
        result = find_issues(state)
        assert len(result["issues"]) == 0

    def test_generate_patch_with_issues(self):
        state: CodeReviewState = {
            "task": "review code",
            "repo_path": ".",
            "files": [],
            "issues": [
                {"file": "src/calc.py", "severity": "high", "description": "div by zero"},
            ],
            "patch": "",
            "test_results": {},
            "report": "",
        }
        result = generate_patch(state)
        assert len(result["patch"]) > 0
        assert "Found 1 issue" in result["report"]

    def test_generate_patch_no_issues(self):
        state: CodeReviewState = {
            "task": "review code",
            "repo_path": ".",
            "files": [],
            "issues": [],
            "patch": "",
            "test_results": {},
            "report": "",
        }
        result = generate_patch(state)
        assert result["patch"] == ""
        assert "No issues found" in result["report"]

    def test_run_tests(self):
        state: CodeReviewState = {
            "task": "review code",
            "repo_path": ".",
            "files": [],
            "issues": [],
            "patch": "",
            "test_results": {},
            "report": "",
        }
        result = run_tests(state)
        assert result["test_results"]["passed"] == 3
        assert result["test_results"]["failed"] == 0

    def test_report_results(self):
        state: CodeReviewState = {
            "task": "review code",
            "repo_path": ".",
            "files": [],
            "issues": [{"file": "x.py", "severity": "high", "description": "bug"}],
            "patch": "--- a/x.py\n+++ b/x.py",
            "test_results": {"total": 3, "passed": 3, "failed": 0},
            "report": "",
        }
        result = report_results(state)
        assert "Issues found: 1" in result["report"]
        assert "3/3 passed" in result["report"]


class TestCodeReviewGraph:
    def test_builds_compiled_graph(self):
        graph = build_code_review_graph()
        compiled = graph.compile()
        assert compiled is not None
