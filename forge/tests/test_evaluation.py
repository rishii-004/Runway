from __future__ import annotations

import json
from tempfile import NamedTemporaryFile

import pytest

from forge.evaluation.metrics import RunMetrics, aggregate_metrics
from forge.evaluation.runner import EvaluationRunner


class TestRunMetrics:
    def test_to_dict(self):
        m = RunMetrics(task="test", success=True, steps=5, tokens=100)
        d = m.to_dict()
        assert d["task"] == "test"
        assert d["success"] is True
        assert d["steps"] == 5
        assert d["tokens"] == 100

    def test_defaults(self):
        m = RunMetrics(task="test", success=False)
        assert m.steps == 0
        assert m.tokens == 0
        assert m.cost_usd == 0.0


class TestAggregatedMetrics:
    def test_empty(self):
        agg = aggregate_metrics([])
        assert agg.total_tasks == 0
        assert agg.success_rate == 0.0

    def test_single_run(self):
        m = RunMetrics(task="t1", success=True, steps=3, tokens=50, cost_usd=0.01)
        agg = aggregate_metrics([m])
        assert agg.total_tasks == 1
        assert agg.successful == 1
        assert agg.success_rate == 1.0
        assert agg.avg_steps == 3.0
        assert agg.avg_tokens == 50.0

    def test_mixed_results(self):
        runs = [
            RunMetrics(task="t1", success=True, steps=2, tokens=100),
            RunMetrics(task="t2", success=False, steps=5, tokens=200, errors=1),
            RunMetrics(task="t3", success=True, steps=3, tokens=150),
        ]
        agg = aggregate_metrics(runs)
        assert agg.total_tasks == 3
        assert agg.successful == 2
        assert agg.failed == 1
        assert agg.success_rate == pytest.approx(2 / 3)
        assert agg.avg_steps == pytest.approx(10 / 3)
        assert agg.total_errors == 1
        assert agg.error_rate == pytest.approx(1 / 3)

    def test_to_dict(self):
        agg = aggregate_metrics([RunMetrics(task="t", success=True)])
        d = agg.to_dict()
        assert "success_rate" in d
        assert "avg_steps" in d
        assert "total_tasks" in d


class TestEvaluationRunner:
    def test_load_tasks_jsonl(self):
        with NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False) as f:
            f.write(json.dumps({"task": "task 1"}) + "\n")
            f.write(json.dumps({"task": "task 2"}) + "\n")
            f.write("plain string task\n")
            f.write("\n")
            f.write(json.dumps({"other": "field"}) + "\n")
            path = f.name

        runner = EvaluationRunner()
        tasks = runner.load_tasks_from_file(path)
        assert len(tasks) == 3
        assert tasks[0] == "task 1"
        assert tasks[1] == "task 2"
        assert tasks[2] == "plain string task"

    def test_load_tasks_missing_file(self):
        runner = EvaluationRunner()
        with pytest.raises(FileNotFoundError):
            runner.load_tasks_from_file("/nonexistent/path.jsonl")
