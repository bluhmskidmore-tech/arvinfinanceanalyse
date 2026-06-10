from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from scripts.business_display_coverage_report import build_report


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "business_display_coverage_report.py"


def _run_report(*args: str) -> tuple[int, dict[str, object]]:
    completed = subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        cwd=ROOT,
        check=False,
        capture_output=True,
        stdin=subprocess.DEVNULL,
        text=True,
    )
    return completed.returncode, json.loads(completed.stdout)


def test_business_display_coverage_report_tracks_browser_smoke_business_routes() -> None:
    report = build_report(generated_at="2026-06-06T23:20:00+08:00")

    assert report["report_kind"] == "business_display_coverage_report"
    assert report["generated_at"] == "2026-06-06T23:20:00+08:00"
    assert report["summary"]["tracked_route_count"] == 26
    assert report["summary"]["route_gap_count"] == 0
    assert report["summary"]["browser_smoke_a11y_configured_route_count"] == 26
    assert report["summary"]["browser_smoke_a11y_gap_count"] == 0
    assert report["evidence_scope"] == {
        "runs_tests": False,
        "proves_business_correctness": False,
        "approves_metric_or_page": False,
        "captures_business_owner_approval": False,
        "maps_existing_test_evidence": True,
        "maps_browser_smoke_a11y_config": True,
        "executes_browser_smoke_a11y": False,
    }

    routes = {item["route"]: item for item in report["routes"]}
    assert set(routes) == {
        "/",
        "/bond-dashboard",
        "/balance-analysis",
        "/balance-movement-analysis",
        "/cross-asset",
        "/product-category-pnl",
        "/pnl",
        "/pnl-bridge",
        "/risk-tensor",
        "/ledger-pnl",
        "/positions",
        "/operations-analysis",
        "/liability-analytics",
        "/market-data",
        "/macro-toolkit",
        "/cashflow-projection",
        "/concentration-monitor",
        "/stock-analysis",
        "/average-balance",
        "/bond-analysis",
        "/pnl-attribution",
        "/team-performance",
        "/decision-items",
        "/kpi",
        "/news-events",
        "/platform-config",
    }
    assert {
        "/bond-analysis",
        "/stock-analysis",
        "/average-balance",
        "/cashflow-projection",
        "/concentration-monitor",
        "/team-performance",
    }.issubset(routes)
    assert routes["/"]["page_id"] == "PAGE-DASH-001"
    assert routes["/bond-dashboard"]["business_boundary"] == "candidate_bond_dashboard_not_risk_tensor_truth"
    assert routes["/balance-analysis"]["evidence"]["owner_boundary_test"]["path"] == (
        "tests/test_balance_analysis_business_owner_approval_status.py"
    )
    assert routes["/pnl-bridge"]["page_id"] == "PAGE-BRIDGE-001"
    assert routes["/risk-tensor"]["risk_tier"] == "critical"
    assert routes["/positions"]["business_boundary"] == "candidate_position_list_not_formal_metric_truth"
    assert routes["/decision-items"]["page_id"] == "GAP-DECISION-ITEMS-PAGE"
    assert routes["/kpi"]["page_id"] == "GAP-KPI-PERFORMANCE-PAGE"
    assert routes["/news-events"]["evidence"]["governance_or_boundary_test"]["exists"] is True
    assert routes["/platform-config"]["business_boundary"] == "diagnostic_config_surface"
    assert routes["/pnl-attribution"]["risk_tier"] == "critical"
    assert routes["/stock-analysis"]["business_boundary"] == "observational_no_trading"
    assert routes["/stock-analysis"]["coverage_status"] == "tracked"
    assert routes["/average-balance"]["business_boundary"] == "candidate_daily_adb_not_formal_balance_truth"
    assert routes["/average-balance"]["coverage_status"] == "tracked"
    assert "frontend_page_test" in routes["/product-category-pnl"]["evidence"]
    assert "backend_or_api_test" in routes["/bond-analysis"]["evidence"]
    assert routes["/bond-analysis"]["evidence"]["owner_boundary_test"]["exists"] is True
    assert routes["/stock-analysis"]["evidence"]["readiness_or_mcp_test"]["exists"] is True
    assert report["evidence_scope"]["maps_browser_smoke_a11y_config"] is True
    assert report["evidence_scope"]["executes_browser_smoke_a11y"] is False
    assert all(
        "npm.cmd run debt:audit"
        in item["required_when_frontend_display_logic_changes"]
        for item in report["routes"]
    )
    assert all(
        item["evidence"]["browser_smoke_a11y_config"]["exists"] is True
        for item in report["routes"]
    )
    assert routes["/cashflow-projection"]["evidence"]["browser_smoke_a11y_config"] == {
        "path": "frontend/tests/playwright/a11y-visual-smoke.spec.mjs",
        "exists": True,
        "configured": True,
        "ready_selector": '[data-testid="cashflow-projection-page"]',
        "runs_test": False,
    }
    assert routes["/concentration-monitor"]["evidence"]["browser_smoke_a11y_config"]["ready_selector"] == (
        '[data-testid="concentration-monitor-kpi-grid"]'
    )
    assert routes["/team-performance"]["evidence"]["browser_smoke_a11y_config"]["ready_selector"] == (
        '[data-testid="team-performance-page"]'
    )
    assert routes["/average-balance"]["evidence"]["browser_smoke_a11y_config"]["ready_selector"] == (
        '[data-testid="average-balance-page"]'
    )


def test_business_display_coverage_report_surfaces_missing_targets_without_approval(
    tmp_path: Path,
) -> None:
    repo_root = tmp_path / "repo"
    (repo_root / "frontend" / "src" / "test").mkdir(parents=True)
    (repo_root / "tests").mkdir(parents=True)

    report = build_report(repo_root=repo_root, generated_at="2026-06-06T23:20:00+08:00")

    assert report["summary"]["tracked_route_count"] == 26
    assert report["summary"]["route_gap_count"] == report["summary"]["tracked_route_count"]
    assert report["summary"]["browser_smoke_a11y_configured_route_count"] == 0
    assert report["summary"]["browser_smoke_a11y_gap_count"] == report["summary"]["tracked_route_count"]
    assert report["summary"]["coverage_status"] == "gaps"
    assert report["evidence_scope"]["approves_metric_or_page"] is False
    assert report["routes"][0]["coverage_status"] == "gap"
    assert report["routes"][0]["missing_evidence"]
    assert "browser_smoke_a11y_config" in report["routes"][0]["missing_evidence"]


def test_business_display_coverage_report_cli_writes_json(tmp_path: Path) -> None:
    output_path = tmp_path / "coverage.json"

    returncode, payload = _run_report(
        "--generated-at",
        "2026-06-06T23:20:00+08:00",
        "--output",
        str(output_path),
    )

    assert returncode == 0
    assert payload["report_path"] == str(output_path)
    assert payload["coverage_status"] in {"tracked", "gaps"}
    assert payload["tracked_route_count"] == 26
    assert payload["browser_smoke_a11y_gap_count"] == 0
    assert payload["evidence_scope"]["maps_existing_test_evidence"] is True

    written = json.loads(output_path.read_text(encoding="utf-8"))
    assert written["report_kind"] == "business_display_coverage_report"
    assert written["generated_at"] == "2026-06-06T23:20:00+08:00"


def test_checked_in_business_display_coverage_report_matches_generator() -> None:
    report_path = ROOT / "docs" / "audits" / "business-display-coverage-report.json"
    checked_in = json.loads(report_path.read_text(encoding="utf-8"))
    generated = build_report(generated_at=checked_in["generated_at"])

    checked_in_comparable = dict(checked_in)
    generated_comparable = dict(generated)
    checked_in_comparable["repo_root"] = "<repo-root>"
    generated_comparable["repo_root"] = "<repo-root>"

    assert checked_in_comparable == generated_comparable
