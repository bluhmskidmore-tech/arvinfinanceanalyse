from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from scripts.mcp.moss_project_mcp import MetricContractsProvider

pytestmark = pytest.mark.mcp_full

REPO_ROOT = Path(__file__).resolve().parents[1]
CURRENT_HOME_PAGE = (
    "frontend/src/features/workbench/dashboard-home/DashboardHomePage.tsx"
)
CURRENT_HOME_TEST = "frontend/src/test/DashboardHomePage.test.tsx"


def test_dashboard_home_trace_bundle_follows_current_routes_and_snapshot_boundaries() -> (
    None
):
    provider = MetricContractsProvider()
    bundles = []
    for alias in ("/", "/dashboard"):
        result = provider.call_tool("get_page_trace_bundle", {"page_slug": alias})
        bundles.append(json.loads(result["content"][0]["text"]))

    assert {bundle["page_slug"] for bundle in bundles} == {"dashboard-home"}
    assert {bundle["page_id"] for bundle in bundles} == {"PAGE-DASH-001"}

    bundle = bundles[0]
    assert bundle["frontend_route"] == "/"
    assert bundle["primary_api"] == "/ui/home/snapshot"
    assert CURRENT_HOME_PAGE in bundle["frontend_touchpoints"]
    assert CURRENT_HOME_TEST in bundle["test_touchpoints"]

    expected_supplemental = {
        "/api/ledger-pnl/candidate-financial-indicators",
        "/api/bond-dashboard/home-summary",
        "/api/bond-analytics/portfolio-headlines",
    }
    assert expected_supplemental <= set(bundle["supporting_apis"])
    assert not {
        "/ui/home/overview",
        "/ui/home/summary",
        "/api/dashboard/core_metrics",
        "/api/dashboard/daily-changes",
        "/api/bond-dashboard/headline-kpis",
    } & set(bundle["supporting_apis"])

    assert (
        "frontend/src/features/workbench/dashboard-home/DashboardHomePage.tsx"
        in bundle["truth_chain"]
    )
    assert any("snapshot report_date" in item for item in bundle["verification_focus"])
    assert any("candidate/non-formal" in item for item in bundle["verification_focus"])

    route_source = (REPO_ROOT / "frontend/src/router/routes.tsx").read_text(
        encoding="utf-8"
    )
    assert re.search(
        r'import\("\.\./features/workbench/dashboard-home/DashboardHomePage"\)',
        route_source,
    )
    assert re.search(
        r'if\s*\(section\.path\s*===\s*"/"\).*?index:\s*true,\s*element:\s*systemReadRouteElement\(<DashboardHomePage\s*/>,\s*false\)',
        route_source,
        re.DOTALL,
    )
    assert re.search(
        r'path:\s*"dashboard",\s*element:\s*systemReadRouteElement\(<DashboardHomePage\s*/>,\s*false\)',
        route_source,
    )

    for field in ("backend_touchpoints", "frontend_touchpoints", "test_touchpoints"):
        for relative_path in bundle[field]:
            assert (REPO_ROOT / relative_path).is_file(), (
                f"missing {field} path: {relative_path}"
            )
