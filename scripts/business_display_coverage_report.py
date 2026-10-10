from __future__ import annotations

import argparse
from datetime import datetime
import json
from pathlib import Path
import re
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = ROOT / "docs" / "audits" / "business-display-coverage-report.json"
SMOKE_SPEC = "frontend/tests/playwright/a11y-visual-smoke.spec.mjs"

EVIDENCE_SCOPE = {
    "runs_tests": False,
    "proves_business_correctness": False,
    "approves_metric_or_page": False,
    "captures_business_owner_approval": False,
    "maps_existing_test_evidence": True,
    "maps_browser_smoke_a11y_config": True,
    "executes_browser_smoke_a11y": False,
}

REQUIRED_WHEN_FRONTEND_DISPLAY_LOGIC_CHANGES = [
    "targeted frontend page/model/adapter test",
    "npm.cmd run typecheck",
    "npm.cmd run debt:audit",
]

BUSINESS_DISPLAY_ROUTES: tuple[dict[str, Any], ...] = (
    {
        "route": "/product-category-pnl",
        "page_id": "PAGE-PROD-CAT-PNL-001",
        "risk_tier": "critical",
        "business_boundary": "owner_signable_not_owner_approved",
        "evidence": {
            "frontend_page_test": "frontend/src/test/ProductCategoryPnlPage.test.tsx",
            "frontend_model_or_adapter_test": "frontend/src/features/product-category-pnl/pages/productCategoryPnlPageModel.test.ts",
            "backend_or_api_test": "tests/test_product_category_pnl_flow.py",
            "readiness_or_mcp_test": "tests/test_codex_page_readiness_gate.py",
            "owner_boundary_test": "tests/test_product_category_pnl_business_owner_approval_status.py",
        },
    },
    {
        "route": "/ledger-pnl",
        "page_id": "PAGE-LEDGER-PNL-001",
        "risk_tier": "critical",
        "business_boundary": "candidate_summary_owner_pending",
        "evidence": {
            "frontend_page_test": "frontend/src/test/LedgerPnlPage.test.tsx",
            "frontend_model_or_adapter_test": "frontend/src/test/LedgerPnlPage.test.tsx",
            "backend_or_api_test": "tests/test_ledger_analytics_api.py",
            "readiness_or_mcp_test": "tests/test_codex_page_readiness_gate.py",
            "owner_boundary_test": "tests/test_ledger_pnl_business_owner_approval_status.py",
        },
    },
    {
        "route": "/pnl-attribution",
        "page_id": "PAGE-PNL-ATTR-WB-001",
        "risk_tier": "critical",
        "business_boundary": "primary_api_dto_formal_result_meta_only",
        "evidence": {
            "frontend_page_test": "frontend/src/test/PnlAttributionPage.test.tsx",
            "frontend_model_or_adapter_test": "frontend/src/features/pnl-attribution/adapters/pnlAttributionAdapter.test.ts",
            "backend_or_api_test": "tests/test_pnl_api_contract.py",
            "readiness_or_mcp_test": "tests/test_codex_page_readiness_gate.py",
            "owner_boundary_test": "tests/test_pnl_attribution_owner_evidence_packet.py",
        },
    },
    {
        "route": "/bond-analysis",
        "page_id": "PAGE-BOND-ANALYSIS-001",
        "risk_tier": "critical",
        "business_boundary": "fixed_income_candidate_no_dashboard_borrow",
        "evidence": {
            "frontend_page_test": "frontend/src/test/BondAnalyticsView.test.tsx",
            "frontend_model_or_adapter_test": "frontend/src/features/bond-analytics/adapters/bondAnalyticsAdapter.test.ts",
            "backend_or_api_test": "tests/test_bond_analytics_api.py",
            "readiness_or_mcp_test": "tests/test_codex_page_readiness_gate.py",
            "owner_boundary_test": "tests/test_bond_analysis_owner_evidence_packet.py",
        },
    },
    {
        "route": "/stock-analysis",
        "page_id": "GAP-STOCK-ANALYSIS-PAGE",
        "risk_tier": "critical",
        "business_boundary": "observational_no_trading",
        "evidence": {
            "frontend_page_test": "frontend/src/test/StockAnalysisPage.test.tsx",
            "frontend_model_or_adapter_test": "frontend/src/features/market-data/lib/livermoreStrategyModel.test.ts",
            "backend_or_api_test": "tests/test_market_data_livermore_api.py",
            "readiness_or_mcp_test": "tests/test_codex_page_readiness_gate.py",
            "owner_boundary_test": "tests/test_stock_analysis_owner_evidence_packet.py",
        },
    },
    {
        "route": "/average-balance",
        "page_id": "PAGE-ADB-001",
        "risk_tier": "critical",
        "business_boundary": "candidate_daily_adb_not_formal_balance_truth",
        "evidence": {
            "frontend_page_test": "frontend/src/test/AverageBalanceView.test.tsx",
            "frontend_model_or_adapter_test": "frontend/src/test/AverageBalanceView.test.tsx",
            "backend_or_api_test": "tests/test_adb_analysis_api.py",
            "readiness_or_mcp_test": "tests/test_codex_page_readiness_gate.py",
            "owner_boundary_test": "tests/test_average_balance_owner_evidence_packet.py",
        },
    },
    {
        "route": "/cashflow-projection",
        "page_id": "GAP-CASHFLOW-PROJECTION-PAGE",
        "risk_tier": "high",
        "business_boundary": "candidate_liquidity_projection",
        "evidence": {
            "frontend_page_test": "frontend/src/test/CashflowProjectionPage.test.tsx",
            "frontend_model_or_adapter_test": "frontend/src/features/cashflow-projection/pages/cashflowProjectionPageModel.test.ts",
            "backend_or_api_test": "tests/test_cashflow_projection.py",
            "readiness_or_mcp_test": "tests/test_project_mcp_servers.py",
            "owner_boundary_test": "tests/test_codex_page_readiness_gate.py",
        },
    },
    {
        "route": "/concentration-monitor",
        "page_id": "PAGE-CONC-001",
        "risk_tier": "high",
        "business_boundary": "candidate_concentration_monitor",
        "evidence": {
            "frontend_page_test": "frontend/src/test/ConcentrationMonitorPage.test.tsx",
            "frontend_model_or_adapter_test": "frontend/src/test/ConcentrationMonitorPage.test.tsx",
            "backend_or_api_test": "tests/test_bond_analytics_service.py",
            "readiness_or_mcp_test": "tests/test_project_mcp_servers.py",
            "owner_boundary_test": "tests/test_codex_page_readiness_gate.py",
        },
    },
    {
        "route": "/team-performance",
        "page_id": "GAP-TEAM-PERFORMANCE-PAGE",
        "risk_tier": "high",
        "business_boundary": "candidate_non_additive_mapping",
        "evidence": {
            "frontend_page_test": "frontend/src/test/TeamPerformancePage.test.tsx",
            "frontend_model_or_adapter_test": "frontend/src/features/team-performance/teamPerformancePageModel.test.ts",
            "backend_or_api_test": "tests/test_pnl_api_contract.py",
            "readiness_or_mcp_test": "tests/test_project_mcp_servers.py",
            "owner_boundary_test": "tests/test_codex_page_readiness_gate.py",
        },
    },
    {
        "route": "/",
        "page_id": "PAGE-DASH-001",
        "risk_tier": "high",
        "business_boundary": "mixed_source_home_snapshot_not_formal_page_closure",
        "evidence": {
            "frontend_page_test": "frontend/src/test/DashboardHomePage.test.tsx",
            "frontend_model_or_adapter_test": "frontend/src/test/DeferredTerminalHomeContent.test.tsx",
            "backend_or_api_test": "tests/test_dashboard_api_contract.py",
            "readiness_or_mcp_test": "tests/test_codex_page_readiness_gate.py",
            "governance_or_boundary_test": "tests/test_project_mcp_servers.py",
        },
    },
    {
        "route": "/bond-dashboard",
        "page_id": "PAGE-BOND-001",
        "risk_tier": "high",
        "business_boundary": "candidate_bond_dashboard_not_risk_tensor_truth",
        "evidence": {
            "frontend_page_test": "frontend/src/test/BondDashboardPage.test.tsx",
            "frontend_model_or_adapter_test": "frontend/src/test/BondKpiRow.unit.test.tsx",
            "backend_or_api_test": "tests/test_bond_dashboard_api_contract.py",
            "readiness_or_mcp_test": "tests/test_codex_page_readiness_gate.py",
            "governance_or_boundary_test": "tests/test_project_mcp_servers.py",
        },
    },
    {
        "route": "/balance-analysis",
        "page_id": "PAGE-BALANCE-001",
        "risk_tier": "critical",
        "business_boundary": "formal_balance_truth_owner_pending",
        "evidence": {
            "frontend_page_test": "frontend/src/test/BalanceAnalysisPage.test.tsx",
            "frontend_model_or_adapter_test": "frontend/src/test/BalanceAnalysisPage.test.tsx",
            "backend_or_api_test": "tests/test_balance_analysis_api.py",
            "readiness_or_mcp_test": "tests/test_codex_page_readiness_gate.py",
            "owner_boundary_test": "tests/test_balance_analysis_business_owner_approval_status.py",
        },
    },
    {
        "route": "/balance-movement-analysis",
        "page_id": "PAGE-BAL-MOVE-001",
        "risk_tier": "critical",
        "business_boundary": "movement_explanation_not_balance_truth",
        "evidence": {
            "frontend_page_test": "frontend/src/test/BalanceMovementAnalysisPage.test.tsx",
            "frontend_model_or_adapter_test": "frontend/src/test/BalanceMovementAnalysisPage.test.tsx",
            "backend_or_api_test": "tests/test_accounting_asset_movement_api.py",
            "readiness_or_mcp_test": "tests/test_codex_page_readiness_gate.py",
            "governance_or_boundary_test": "tests/test_project_mcp_servers.py",
        },
    },
    {
        "route": "/cross-asset",
        "page_id": "GAP-CROSS-ASSET-PAGE",
        "risk_tier": "high",
        "business_boundary": "mixed_source_analytical_surface",
        "evidence": {
            "frontend_page_test": "frontend/src/test/CrossAssetPage.test.tsx",
            "frontend_model_or_adapter_test": "frontend/src/test/CrossAssetDriversRoute.test.tsx",
            "backend_or_api_test": "tests/test_cross_asset_macro_environment_backfill.py",
            "readiness_or_mcp_test": "tests/test_codex_page_readiness_gate.py",
            "governance_or_boundary_test": "tests/test_project_mcp_servers.py",
        },
    },
    {
        "route": "/pnl",
        "page_id": "PAGE-PNL-001",
        "risk_tier": "critical",
        "business_boundary": "formal_pnl_overview_result_meta_required",
        "evidence": {
            "frontend_page_test": "frontend/src/test/PnlPage.test.tsx",
            "frontend_model_or_adapter_test": "frontend/src/test/PnlRoutesSmoke.test.tsx",
            "backend_or_api_test": "tests/test_pnl_api_contract.py",
            "readiness_or_mcp_test": "tests/test_codex_page_readiness_gate.py",
            "governance_or_boundary_test": "tests/test_project_mcp_servers.py",
        },
    },
    {
        "route": "/pnl-bridge",
        "page_id": "PAGE-BRIDGE-001",
        "risk_tier": "critical",
        "business_boundary": "formal_bridge_warning_and_source_boundary",
        "evidence": {
            "frontend_page_test": "frontend/src/test/PnlBridgePage.test.tsx",
            "frontend_model_or_adapter_test": "frontend/src/test/PnlRoutesSmoke.test.tsx",
            "backend_or_api_test": "tests/test_pnl_bridge_core.py",
            "readiness_or_mcp_test": "tests/test_codex_page_readiness_gate.py",
            "governance_or_boundary_test": "tests/test_project_mcp_servers.py",
        },
    },
    {
        "route": "/risk-tensor",
        "page_id": "PAGE-RISK-001",
        "risk_tier": "critical",
        "business_boundary": "formal_risk_tensor_result_meta_required",
        "evidence": {
            "frontend_page_test": "frontend/src/test/RiskTensorPage.test.tsx",
            "frontend_model_or_adapter_test": "frontend/src/test/RiskTensorPage.test.tsx",
            "backend_or_api_test": "tests/test_risk_tensor_api.py",
            "readiness_or_mcp_test": "tests/test_codex_page_readiness_gate.py",
            "governance_or_boundary_test": "tests/test_project_mcp_servers.py",
        },
    },
    {
        "route": "/positions",
        "page_id": "PAGE-POS-001",
        "risk_tier": "high",
        "business_boundary": "candidate_position_list_not_formal_metric_truth",
        "evidence": {
            "frontend_page_test": "frontend/src/test/PositionsView.test.tsx",
            "frontend_model_or_adapter_test": "frontend/src/test/PositionsView.test.tsx",
            "backend_or_api_test": "tests/test_positions_api_contract.py",
            "readiness_or_mcp_test": "tests/test_codex_page_readiness_gate.py",
            "governance_or_boundary_test": "tests/test_project_mcp_servers.py",
        },
    },
    {
        "route": "/operations-analysis",
        "page_id": "PAGE-OPS-001",
        "risk_tier": "high",
        "business_boundary": "mixed_source_operations_temporary_exception",
        "evidence": {
            "frontend_page_test": "frontend/src/test/OperationsAnalysisPage.test.tsx",
            "frontend_governed_test": "frontend/src/test/OperationsAnalysisPage.governed.test.tsx",
            "readiness_or_mcp_test": "tests/test_codex_page_readiness_gate.py",
            "governance_or_boundary_test": "tests/test_project_mcp_servers.py",
        },
    },
    {
        "route": "/liability-analytics",
        "page_id": "PAGE-LIAB-ANALYTICS-001",
        "risk_tier": "high",
        "business_boundary": "mixed_source_liability_analytics",
        "evidence": {
            "frontend_page_test": "frontend/src/test/LiabilityAnalyticsPage.test.tsx",
            "frontend_model_or_adapter_test": "frontend/src/test/LiabilityAnalyticsPage.test.tsx",
            "backend_or_api_test": "tests/test_liability_analytics_api.py",
            "readiness_or_mcp_test": "tests/test_codex_page_readiness_gate.py",
            "governance_or_boundary_test": "tests/test_project_mcp_servers.py",
        },
    },
    {
        "route": "/market-data",
        "page_id": "PAGE-MKT-001",
        "risk_tier": "high",
        "business_boundary": "mixed_source_market_data_formal_fragment_only",
        "evidence": {
            "frontend_page_test": "frontend/src/test/MarketDataPage.test.tsx",
            "frontend_model_or_adapter_test": "frontend/src/features/market-data/lib/livermoreStrategyModel.test.ts",
            "backend_or_api_test": "tests/test_market_data_ncd_proxy_api.py",
            "readiness_or_mcp_test": "tests/test_codex_page_readiness_gate.py",
            "governance_or_boundary_test": "tests/test_project_mcp_servers.py",
        },
    },
    {
        "route": "/macro-toolkit",
        "page_id": "PAGE-MACRO-TOOLKIT-001",
        "risk_tier": "high",
        "business_boundary": "tooling_surface_not_formal_metric_truth",
        "evidence": {
            "frontend_page_test": "frontend/src/test/MacroToolkitPage.test.tsx",
            "frontend_model_or_adapter_test": "frontend/src/test/MacroToolkitPage.test.tsx",
            "backend_or_api_test": "tests/test_macro_toolkit_scripts.py",
            "readiness_or_mcp_test": "tests/test_codex_page_readiness_gate.py",
            "governance_or_boundary_test": "tests/test_project_mcp_servers.py",
        },
    },
    {
        "route": "/decision-items",
        "page_id": "GAP-DECISION-ITEMS-PAGE",
        "risk_tier": "high",
        "business_boundary": "candidate_read_write_governance_queue",
        "evidence": {
            "frontend_page_test": "frontend/src/test/DecisionItemsPage.test.tsx",
            "frontend_model_or_adapter_test": "frontend/src/test/DecisionItemsRoute.test.tsx",
            "backend_or_api_test": "tests/test_decision_items_governance_record.py",
            "readiness_or_mcp_test": "tests/test_codex_page_readiness_gate.py",
            "governance_or_boundary_test": "tests/test_project_mcp_servers.py",
        },
    },
    {
        "route": "/kpi",
        "page_id": "GAP-KPI-PERFORMANCE-PAGE",
        "risk_tier": "high",
        "business_boundary": "candidate_read_write_scoring_workbench",
        "evidence": {
            "frontend_page_test": "frontend/src/test/KpiPerformancePage.test.tsx",
            "frontend_model_or_adapter_test": "frontend/src/test/KpiTracePanel.test.tsx",
            "backend_or_api_test": "tests/test_kpi_api.py",
            "readiness_or_mcp_test": "tests/test_codex_page_readiness_gate.py",
            "governance_or_boundary_test": "tests/test_kpi_performance_governance_record.py",
        },
    },
    {
        "route": "/news-events",
        "page_id": "GAP-NEWS-EVENTS-PAGE",
        "risk_tier": "high",
        "business_boundary": "analytical_event_context",
        "evidence": {
            "frontend_page_test": "frontend/src/test/NewsEventsPage.test.tsx",
            "frontend_model_or_adapter_test": "frontend/src/test/NewsEventsPage.test.tsx",
            "backend_or_api_test": "tests/test_choice_news_routes.py",
            "readiness_or_mcp_test": "tests/test_codex_page_readiness_gate.py",
            "governance_or_boundary_test": "tests/test_news_events_governance_record.py",
        },
    },
    {
        "route": "/platform-config",
        "page_id": "GAP-PLATFORM-CONFIG-PAGE",
        "risk_tier": "high",
        "business_boundary": "diagnostic_config_surface",
        "evidence": {
            "frontend_page_test": "frontend/src/test/PlatformConfigPage.test.tsx",
            "frontend_model_or_adapter_test": "frontend/src/test/PlatformConfigPage.test.tsx",
            "backend_or_api_test": "tests/test_platform_config_governance_record.py",
            "readiness_or_mcp_test": "tests/test_codex_page_readiness_gate.py",
            "governance_or_boundary_test": "tests/test_project_mcp_servers.py",
        },
    },
)

HIGH_RISK_ROUTES = BUSINESS_DISPLAY_ROUTES


def _default_generated_at() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def _evidence_status(repo_root: Path, relative_path: str) -> dict[str, Any]:
    path = repo_root / relative_path
    return {
        "path": relative_path,
        "exists": path.is_file(),
    }


def _smoke_pages(repo_root: Path) -> dict[str, str]:
    spec_path = repo_root / SMOKE_SPEC
    if not spec_path.is_file():
        return {}

    spec_text = spec_path.read_text(encoding="utf-8")
    smoke_pages_match = re.search(
        r"const smokePages = \[(?P<body>.*?)\];\s*const flagshipKeyboardPages",
        spec_text,
        re.DOTALL,
    )
    if not smoke_pages_match:
        return {}

    routes: dict[str, str] = {}
    for block in re.finditer(r"\{(?P<body>.*?)\}", smoke_pages_match.group("body"), re.DOTALL):
        body = block.group("body")
        path_match = re.search(r'path:\s*"(?P<path>[^"]+)"', body)
        selector_match = re.search(r"readySelector:\s*'(?P<selector>[^']+)'", body)
        if path_match and selector_match:
            routes[path_match.group("path")] = selector_match.group("selector")
    return routes


def _browser_smoke_status(
    repo_root: Path,
    route: str,
    smoke_pages: dict[str, str],
) -> dict[str, Any]:
    spec_path = repo_root / SMOKE_SPEC
    configured = route in smoke_pages
    return {
        "path": SMOKE_SPEC,
        "exists": spec_path.is_file() and configured,
        "configured": configured,
        "ready_selector": smoke_pages.get(route),
        "runs_test": False,
    }


def _route_report(
    repo_root: Path,
    spec: dict[str, Any],
    smoke_pages: dict[str, str],
) -> dict[str, Any]:
    evidence = {
        name: _evidence_status(repo_root, path)
        for name, path in spec["evidence"].items()
    }
    evidence["browser_smoke_a11y_config"] = _browser_smoke_status(
        repo_root,
        spec["route"],
        smoke_pages,
    )
    missing = [
        name
        for name, item in evidence.items()
        if not bool(item["exists"])
    ]
    return {
        "route": spec["route"],
        "page_id": spec["page_id"],
        "risk_tier": spec["risk_tier"],
        "business_boundary": spec["business_boundary"],
        "coverage_status": "tracked" if not missing else "gap",
        "missing_evidence": missing,
        "evidence": evidence,
        "required_when_frontend_display_logic_changes": list(
            REQUIRED_WHEN_FRONTEND_DISPLAY_LOGIC_CHANGES
        ),
    }


def build_report(
    *,
    repo_root: Path = ROOT,
    generated_at: str | None = None,
) -> dict[str, Any]:
    root = Path(repo_root)
    smoke_pages = _smoke_pages(root)
    routes = [_route_report(root, spec, smoke_pages) for spec in BUSINESS_DISPLAY_ROUTES]
    route_gap_count = sum(1 for item in routes if item["coverage_status"] != "tracked")
    browser_smoke_configured_count = sum(
        1
        for item in routes
        if bool(item["evidence"]["browser_smoke_a11y_config"]["configured"])
    )
    browser_smoke_gap_count = len(routes) - browser_smoke_configured_count
    return {
        "report_kind": "business_display_coverage_report",
        "generated_at": generated_at or _default_generated_at(),
        "repo_root": str(root),
        "summary": {
            "tracked_route_count": len(routes),
            "route_gap_count": route_gap_count,
            "browser_smoke_a11y_configured_route_count": browser_smoke_configured_count,
            "browser_smoke_a11y_gap_count": browser_smoke_gap_count,
            "coverage_status": "tracked" if route_gap_count == 0 else "gaps",
        },
        "evidence_scope": dict(EVIDENCE_SCOPE),
        "routes": routes,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Build a static coverage map for browser-smoke business display paths.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT,
        help="JSON report path to write.",
    )
    parser.add_argument(
        "--generated-at",
        default=None,
        help="Stable timestamp for reproducible tests.",
    )
    args = parser.parse_args(argv)

    report = build_report(generated_at=args.generated_at)
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    payload = {
        "report_kind": report["report_kind"],
        "report_path": str(output_path),
        "coverage_status": report["summary"]["coverage_status"],
        "tracked_route_count": report["summary"]["tracked_route_count"],
        "route_gap_count": report["summary"]["route_gap_count"],
        "browser_smoke_a11y_configured_route_count": report["summary"][
            "browser_smoke_a11y_configured_route_count"
        ],
        "browser_smoke_a11y_gap_count": report["summary"][
            "browser_smoke_a11y_gap_count"
        ],
        "evidence_scope": report["evidence_scope"],
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
