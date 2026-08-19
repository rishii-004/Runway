from __future__ import annotations

import json
from pathlib import Path

DASHBOARD_PATH = (
    Path(__file__).resolve().parent.parent.parent
    / "docker"
    / "grafana"
    / "dashboards"
    / "forge-overview.json"
)
DATASOURCE_PATH = (
    Path(__file__).resolve().parent.parent.parent
    / "docker"
    / "grafana"
    / "provisioning"
    / "datasources"
    / "prometheus.yaml"
)


class TestGrafanaProvisioning:
    def test_dashboard_json_is_valid(self):
        raw = DASHBOARD_PATH.read_text()
        dashboard = json.loads(raw)
        assert dashboard["title"] == "Forge Dashboard"
        assert dashboard["uid"] == "forge-overview"
        assert len(dashboard["panels"]) >= 5

    def test_dashboard_has_expected_panels(self):
        dashboard = json.loads(DASHBOARD_PATH.read_text())
        titles = [p["title"] for p in dashboard["panels"]]
        assert "Runs Total" in titles
        assert "Active Runs" in titles
        assert "Tool Calls / sec" in titles

    def test_datasource_yaml_exists(self):
        assert DATASOURCE_PATH.exists()

    def test_datasource_has_prometheus(self):
        import yaml

        data = yaml.safe_load(DATASOURCE_PATH.read_text())
        names = [ds["name"] for ds in data["datasources"]]
        assert "Prometheus" in names
