import json
import os
import subprocess
import threading
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_native_development_scripts_exist():
    expected = [
        ROOT / "scripts" / "dev-api.ps1",
        ROOT / "scripts" / "dev-worker.ps1",
        ROOT / "scripts" / "dev-env.ps1",
        ROOT / "scripts" / "dev-up.ps1",
        ROOT / "scripts" / "dev-down.ps1",
        ROOT / "scripts" / "dev-postgres-up.ps1",
        ROOT / "scripts" / "dev-postgres-down.ps1",
        ROOT / "scripts" / "dev-postgres-status.ps1",
        ROOT / "scripts" / "dev-python.ps1",
        ROOT / "scripts" / "dev-governance-maintenance.ps1",
        ROOT / "scripts" / "dev-hermes-webui.ps1",
        ROOT / "scripts" / "codex-verify-page.ps1",
        ROOT / "scripts" / "codex-page-smoke.ps1",
        ROOT / "scripts" / "codex-page-readiness.ps1",
        ROOT / "scripts" / "codex-dev-flow.ps1",
    ]

    missing = [str(path) for path in expected if not path.exists()]
    assert not missing, "Missing native development scripts:\n" + "\n".join(missing)


def run_powershell_script_result(
    script_name: str,
    *args: str,
    env_overrides: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    env = None
    if env_overrides:
        env = os.environ.copy()
        env.update(env_overrides)

    return subprocess.run(
        [
            "powershell",
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(ROOT / "scripts" / script_name),
            *args,
        ],
        cwd=ROOT,
        check=False,
        capture_output=True,
        env=env,
        stdin=subprocess.DEVNULL,
        text=True,
    )


def run_powershell_script(script_name: str, *args: str) -> str:
    completed = run_powershell_script_result(script_name, *args)
    completed.check_returncode()
    return completed.stdout


@contextmanager
def balance_movement_smoke_server(dates_payload: dict):
    class Handler(BaseHTTPRequestHandler):
        def _send(self, status: int, body: str, content_type: str = "application/json") -> None:
            encoded = body.encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(encoded)))
            self.end_headers()
            self.wfile.write(encoded)

        def do_GET(self) -> None:  # noqa: N802 - BaseHTTPRequestHandler API
            path = self.path.split("?", 1)[0]
            if path == "/health":
                self._send(200, json.dumps({"status": "ok"}))
                return
            if path == "/balance-movement-analysis":
                self._send(200, "<html><body>balance movement</body></html>", "text/html")
                return
            if path == "/ui/balance-movement-analysis/dates":
                self._send(200, json.dumps(dates_payload))
                return
            if path == "/ui/balance-movement-analysis":
                self._send(200, json.dumps({"result": {}, "result_meta": {}}))
                return
            self._send(404, json.dumps({"error": "not found"}))

        def log_message(self, *_args: object) -> None:
            return

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}"
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


@contextmanager
def ledger_pnl_smoke_server(dates_payload: dict):
    class Handler(BaseHTTPRequestHandler):
        def _send(self, status: int, body: str, content_type: str = "application/json") -> None:
            encoded = body.encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(encoded)))
            self.end_headers()
            self.wfile.write(encoded)

        def do_GET(self) -> None:  # noqa: N802 - BaseHTTPRequestHandler API
            path = self.path.split("?", 1)[0]
            if path == "/health":
                self._send(200, json.dumps({"status": "ok"}))
                return
            if path == "/ledger-pnl":
                self._send(200, "<html><body>ledger pnl</body></html>", "text/html")
                return
            if path == "/api/ledger-pnl/dates":
                self._send(200, json.dumps(dates_payload))
                return
            if path in {"/api/ledger-pnl/summary", "/api/ledger-pnl/data"}:
                self._send(200, json.dumps({"result": {}, "result_meta": {}}))
                return
            self._send(404, json.dumps({"error": "not found"}))

        def log_message(self, *_args: object) -> None:
            return

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}"
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


def test_codex_verify_page_defaults_to_dry_run():
    output = run_powershell_script("codex-verify-page.ps1", "-PageSlug", "product-category-pnl")

    assert "Codex verify page: product-category-pnl" in output
    assert "tests/test_project_mcp_servers.py" in output
    assert "ProductCategoryAdjustmentAuditPage.test.tsx" in output
    assert "--basetemp=" in output
    assert ".codex-tmp" in output
    assert "pytest-basetemp" in output
    assert "codex-verify-pytest-basetemp-cvp-product-category-pnl-" in output
    assert "Codex verify page dry run complete. Pass -Run to execute checks." in output
    assert "Codex verify page checks passed." not in output


def test_codex_verify_page_uses_explicit_pytest_basetemp_root_when_configured():
    explicit_root = str(ROOT / ".codex-tmp" / "pytest-explicit-dry-run-test")
    completed = run_powershell_script_result(
        "codex-verify-page.ps1",
        "-PageSlug",
        "product-category-pnl",
        env_overrides={"CODEX_PYTEST_BASETEMP_ROOT": explicit_root},
    )
    completed.check_returncode()

    output = completed.stdout
    assert "--basetemp=" in output
    assert explicit_root in output
    assert "pytest-explicit-dry-run-test-cvp-product-category-pnl-" in output


def test_codex_verify_page_can_plan_non_browser_product_category_checks():
    output = run_powershell_script(
        "codex-verify-page.ps1",
        "-PageSlug",
        "product-category-pnl",
        "-SkipMcpContracts",
        "-SkipBrowserSmoke",
    )

    assert "tests/test_project_mcp_servers.py" not in output
    assert "Product-category backend flow and mapping tests" in output
    assert "Product-category frontend tests" in output
    assert "Product-category browser a11y smoke" not in output
    assert "test:a11y-smoke" not in output
    assert "Frontend typecheck" in output
    assert "Frontend debt audit" in output
    assert "Frontend production build" in output
    assert "npm.cmd run build" in output


def test_codex_dev_flow_defaults_to_planning_the_system_development_loop():
    output = run_powershell_script("codex-dev-flow.ps1", "-PageSlug", "pnl-attribution")

    assert "MOSS development flow adapter: pnl-attribution" in output
    assert "Mode: plan" in output
    assert "1. Preflight readiness" in output
    assert "2. Page verification" in output
    assert "3. Page readiness gate" in output
    assert "4. Approval capture check" in output
    assert "scripts\\codex-page-readiness.ps1 -PageSlug pnl-attribution" in output
    assert "scripts\\codex-verify-page.ps1 -PageSlug pnl-attribution -Run" in output
    assert "scripts\\codex-page-readiness.ps1 -PageSlug pnl-attribution -Run" in output
    assert "scripts\\codex-page-readiness.ps1 -PageSlug pnl-attribution -RequireApprovalCaptured" in output
    assert "Development flow plan complete. Pass -Run with -Mode verify/readiness/approval/all to execute." in output


def test_codex_dev_flow_can_run_preflight_readiness_only():
    output = run_powershell_script("codex-dev-flow.ps1", "-PageSlug", "pnl-attribution", "-Mode", "preflight", "-Run")

    assert "MOSS development flow adapter: pnl-attribution" in output
    assert "Mode: preflight" in output
    assert "Running preflight readiness" in output
    assert "MOSS page readiness gate: pnl-attribution" in output
    assert "Development flow adapter finished." in output


def test_codex_verify_page_supports_dashboard_home_dry_run():
    output = run_powershell_script("codex-verify-page.ps1", "-PageSlug", "dashboard-home")

    assert "Codex verify page: dashboard-home" in output
    assert "tests/test_project_mcp_servers.py" in output
    assert "tests/test_home_snapshot_endpoint.py" in output
    assert "DashboardPage.test.tsx" in output
    assert "dashboardCockpitHomeModel.test.ts" in output
    assert "Codex verify page dry run complete. Pass -Run to execute checks." in output
    assert "Codex verify page checks passed." not in output


def test_codex_verify_page_supports_balance_analysis_dry_run():
    output = run_powershell_script("codex-verify-page.ps1", "-PageSlug", "balance-analysis")

    assert "Codex verify page: balance-analysis" in output
    assert "tests/test_project_mcp_servers.py" in output
    assert "tests/test_balance_analysis_api.py" in output
    assert "BalanceAnalysisPage.test.tsx" in output
    assert "@balance-analysis" in output
    assert "Codex verify page dry run complete. Pass -Run to execute checks." in output
    assert "Codex verify page checks passed." not in output


def test_codex_verify_page_supports_pnl_dry_run():
    output = run_powershell_script("codex-verify-page.ps1", "-PageSlug", "pnl")

    assert "Codex verify page: pnl" in output
    assert "tests/test_project_mcp_servers.py" in output
    assert "tests/test_pnl_api_contract.py" in output
    assert "PnlRoutesSmoke.test.tsx" in output
    assert "@pnl" in output
    assert "Codex verify page dry run complete. Pass -Run to execute checks." in output
    assert "Codex verify page checks passed." not in output


def test_codex_verify_page_supports_pnl_bridge_dry_run():
    output = run_powershell_script("codex-verify-page.ps1", "-PageSlug", "pnl-bridge")

    assert "Codex verify page: pnl-bridge" in output
    assert "tests/test_project_mcp_servers.py" in output
    assert "tests/test_pnl_bridge_core.py" in output
    assert "tests/test_pnl_bridge_curve_effects.py" in output
    assert "PnlBridgePage.test.tsx" in output
    assert "PnlRoutesSmoke.test.tsx" in output
    assert "@pnl-bridge" in output
    assert "Codex verify page dry run complete. Pass -Run to execute checks." in output
    assert "Codex verify page checks passed." not in output


def test_codex_verify_page_supports_risk_tensor_dry_run():
    output = run_powershell_script("codex-verify-page.ps1", "-PageSlug", "risk-tensor")

    assert "Codex verify page: risk-tensor" in output
    assert "tests/test_project_mcp_servers.py" in output
    assert "tests/test_risk_tensor_api.py" in output
    assert "tests/test_risk_tensor_service.py" in output
    assert "RiskTensorPage.test.tsx" in output
    assert "@risk-tensor" in output
    assert "Codex verify page dry run complete. Pass -Run to execute checks." in output
    assert "Codex verify page checks passed." not in output


def test_codex_verify_page_supports_bond_dashboard_dry_run():
    output = run_powershell_script("codex-verify-page.ps1", "-PageSlug", "bond-dashboard")

    assert "Codex verify page: bond-dashboard" in output
    assert "tests/test_project_mcp_servers.py" in output
    assert "tests/test_bond_dashboard_api_contract.py" in output
    assert "tests/test_bond_dashboard_headlines_contract.py" in output
    assert "BondDashboardPage.test.tsx" in output
    assert "@bond-dashboard" in output
    assert "Codex verify page dry run complete. Pass -Run to execute checks." in output
    assert "Codex verify page checks passed." not in output


def test_codex_verify_page_supports_bond_analysis_dry_run():
    output = run_powershell_script("codex-verify-page.ps1", "-PageSlug", "bond-analysis")

    assert "Codex verify page: bond-analysis" in output
    assert "tests/test_project_mcp_servers.py" in output
    assert "tests/test_bond_analytics_api.py" in output
    assert "tests/core_finance/test_action_attribution.py" in output
    assert "tests/test_action_attribution.py" not in output
    assert "BondAnalyticsViewContent.test.tsx" in output
    assert "BondAnalyticsView.test.tsx" in output
    assert "@bond-analysis" in output
    assert "Codex verify page dry run complete. Pass -Run to execute checks." in output
    assert "Codex verify page checks passed." not in output


def test_codex_verify_page_supports_balance_movement_analysis_dry_run():
    output = run_powershell_script("codex-verify-page.ps1", "-PageSlug", "balance-movement-analysis")

    assert "Codex verify page: balance-movement-analysis" in output
    assert "tests/test_project_mcp_servers.py" in output
    assert "tests/test_accounting_asset_movement_api.py" in output
    assert "tests/test_accounting_asset_movement_service.py" in output
    assert "BalanceMovementAnalysisPage.test.tsx" in output
    assert "@balance-movement-analysis" in output
    assert "Codex verify page dry run complete. Pass -Run to execute checks." in output
    assert "Codex verify page checks passed." not in output


def test_codex_verify_page_supports_ledger_pnl_dry_run():
    output = run_powershell_script("codex-verify-page.ps1", "-PageSlug", "ledger-pnl")

    assert "Codex verify page: ledger-pnl" in output
    assert "tests/test_project_mcp_servers.py" in output
    assert "tests/test_ledger_pnl_service.py" in output
    assert "tests/test_ledger_pnl_formal_financial_indicator_golden_sample.py" in output
    assert "LedgerPnlPage.test.tsx" in output
    assert "LedgerPnlRoutesSmoke.test.tsx" in output
    assert "@ledger-pnl" in output
    assert "Codex verify page dry run complete. Pass -Run to execute checks." in output
    assert "Codex verify page checks passed." not in output


def test_codex_verify_page_supports_positions_dry_run():
    output = run_powershell_script("codex-verify-page.ps1", "-PageSlug", "positions")

    assert "Codex verify page: positions" in output
    assert "tests/test_project_mcp_servers.py" in output
    assert "tests/test_positions_api_contract.py" in output
    assert "PositionsView.test.tsx" in output
    assert "RouteRegistry.test.tsx" in output
    assert "CustomerDetailModal.test.tsx" in output
    assert "@positions" in output
    assert "Codex verify page dry run complete. Pass -Run to execute checks." in output
    assert "Codex verify page checks passed." not in output


def test_codex_verify_page_supports_operations_analysis_dry_run():
    output = run_powershell_script("codex-verify-page.ps1", "-PageSlug", "operations-analysis")

    assert "Codex verify page: operations-analysis" in output
    assert "tests/test_project_mcp_servers.py" in output
    assert "tests/test_product_category_pnl_flow.py" in output
    assert "tests/test_balance_analysis_api.py" in output
    assert "OperationsAnalysisPage.test.tsx" in output
    assert "OperationsAnalysisPage.governed.test.tsx" in output
    assert "@operations-analysis" in output
    assert "Codex verify page dry run complete. Pass -Run to execute checks." in output
    assert "Codex verify page checks passed." not in output


def test_codex_verify_page_supports_liability_analytics_dry_run():
    output = run_powershell_script("codex-verify-page.ps1", "-PageSlug", "liability-analytics")

    assert "Codex verify page: liability-analytics" in output
    assert "tests/test_project_mcp_servers.py" in output
    assert "tests/test_liability_analytics_api.py" in output
    assert "tests/test_liability_analytics_envelope_contract.py" in output
    assert "tests/test_liability_analytics_unit_semantics.py" in output
    assert "LiabilityAnalyticsPage.test.tsx" in output
    assert "liabilityAdapter.test.ts" in output
    assert "liabilityAnalyticsPageModel.test.ts" in output
    assert "@liability-analytics" in output
    assert "Codex verify page dry run complete. Pass -Run to execute checks." in output
    assert "Codex verify page checks passed." not in output


def test_codex_verify_page_supports_market_data_dry_run():
    output = run_powershell_script("codex-verify-page.ps1", "-PageSlug", "market-data")

    assert "Codex verify page: market-data" in output
    assert "tests/test_project_mcp_servers.py" in output
    assert "tests/test_result_meta_on_all_ui_endpoints.py" in output
    assert "tests/test_market_data_ncd_proxy_api.py" in output
    assert "tests/test_market_data_livermore_api.py" in output
    assert "tests/test_macro_bond_linkage.py" in output
    assert "tests/test_fx_analytical_view_api.py" in output
    assert "MarketDataPage.test.tsx" in output
    assert "marketDataPageModel.test.ts" in output
    assert "@market-data" in output
    assert "Codex verify page dry run complete. Pass -Run to execute checks." in output
    assert "Codex verify page checks passed." not in output


def test_codex_verify_page_supports_macro_toolkit_dry_run():
    output = run_powershell_script("codex-verify-page.ps1", "-PageSlug", "macro-toolkit")

    assert "Codex verify page: macro-toolkit" in output
    assert "tests/test_project_mcp_servers.py" in output
    assert "tests/test_macro_toolkit_scripts.py" in output
    assert "tests/test_macro_toolkit_choice_stock_refresh_overview.py" in output
    assert "tests/test_macro_toolkit_shadow_portfolio_report.py" in output
    assert "tests/test_macro_query_contract_smoke.py" in output
    assert "tests/test_write_route_auth_contract.py" in output
    assert "MacroToolkitPage.test.tsx" in output
    assert "macroToolkitClient.test.ts" in output
    assert "@macro-toolkit" in output
    assert "Codex verify page dry run complete. Pass -Run to execute checks." in output
    assert "Codex verify page checks passed." not in output


def test_codex_verify_page_supports_stock_analysis_dry_run():
    output = run_powershell_script("codex-verify-page.ps1", "-PageSlug", "stock-analysis")

    assert "Codex verify page: stock-analysis" in output
    assert "tests/test_project_mcp_servers.py" in output
    assert "tests/test_market_data_livermore_api.py" in output
    assert "tests/test_market_data_livermore_candidate_history.py" in output
    assert "tests/test_market_data_livermore_stock_detail.py" in output
    assert "tests/test_market_data_livermore_sector_rank_series.py" in output
    assert "tests/test_market_data_livermore_risk_exit_source.py" in output
    assert "tests/test_livermore_signal_confluence.py" in output
    assert "StockAnalysisPage.test.tsx" in output
    assert "StockAnalysisPageModel.test.ts" in output
    assert "StockDetailDrawer.test.tsx" in output
    assert "@stock-analysis" in output
    assert "Codex verify page dry run complete. Pass -Run to execute checks." in output
    assert "Codex verify page checks passed." not in output


def test_codex_verify_page_supports_pnl_attribution_dry_run():
    output = run_powershell_script("codex-verify-page.ps1", "-PageSlug", "pnl-attribution")

    assert "Codex verify page: pnl-attribution" in output
    assert "tests/test_project_mcp_servers.py" in output
    assert "tests/test_pnl_attribution_api_contract.py" in output
    assert "tests/test_pnl_attribution_workbench_contract.py" in output
    assert "tests/test_pnl_attribution_service_explicit_numeric.py" in output
    assert "tests/test_campisi_attribution_service.py" in output
    assert "tests/test_campisi_formula_golden.py" in output
    assert "PnlAttributionPage.test.tsx" in output
    assert "pnlAttributionAdapter.test.ts" in output
    assert "PnlAttributionView.test.ts" in output
    assert "@pnl-attribution" in output
    assert "Codex verify page dry run complete. Pass -Run to execute checks." in output
    assert "Codex verify page checks passed." not in output


def test_codex_verify_page_supports_concentration_monitor_dry_run():
    output = run_powershell_script("codex-verify-page.ps1", "-PageSlug", "concentration-monitor")

    assert "Codex verify page: concentration-monitor" in output
    assert "tests/test_project_mcp_servers.py" in output
    assert "tests/test_bond_analytics_api.py" in output
    assert "tests/test_bond_analytics_service.py" in output
    assert "ConcentrationMonitorPage.test.tsx" in output
    assert "BondAnalyticsClient.test.ts" in output
    assert "@concentration-monitor" in output
    assert "Codex verify page dry run complete. Pass -Run to execute checks." in output
    assert "Codex verify page checks passed." not in output


def test_codex_verify_page_supports_team_performance_dry_run():
    output = run_powershell_script("codex-verify-page.ps1", "-PageSlug", "team-performance")

    assert "Codex verify page: team-performance" in output
    assert "tests/test_project_mcp_servers.py" in output
    assert "tests/test_pnl_api_contract.py" in output
    assert "tests/test_product_category_pnl_flow.py" in output
    assert "TeamPerformancePage.test.tsx" in output
    assert "RouteRegistry.test.tsx" in output
    assert "LiveRouteRealPageSmoke.test.tsx" in output
    assert "@team-performance" in output
    assert "Codex verify page dry run complete. Pass -Run to execute checks." in output
    assert "Codex verify page checks passed." not in output


def test_codex_verify_page_supports_platform_config_dry_run():
    output = run_powershell_script("codex-verify-page.ps1", "-PageSlug", "platform-config")

    assert "Codex verify page: platform-config" in output
    assert "tests/test_health_endpoints.py" in output
    assert "tests/test_source_preview_flow.py" in output
    assert "tests/test_result_meta_on_all_ui_endpoints.py" in output
    assert "PlatformConfigPage.test.tsx" in output
    assert "RouteRegistry.test.tsx" in output
    assert "LiveRouteRealPageSmoke.test.tsx" in output
    assert "@platform-config" in output
    assert "Codex verify page dry run complete. Pass -Run to execute checks." in output
    assert "Codex verify page checks passed." not in output


def test_codex_verify_page_supports_news_events_dry_run():
    output = run_powershell_script("codex-verify-page.ps1", "-PageSlug", "news-events")

    assert "Codex verify page: news-events" in output
    assert "tests/test_choice_news_routes.py" in output
    assert "tests/test_result_meta_on_all_ui_endpoints.py" in output
    assert "NewsEventsPage.test.tsx" in output
    assert "RouteRegistry.test.tsx" in output
    assert "LiveRouteRealPageSmoke.test.tsx" in output
    assert "@news-events" in output
    assert "Codex verify page dry run complete. Pass -Run to execute checks." in output
    assert "Codex verify page checks passed." not in output


def test_codex_page_smoke_defaults_to_checklist_only():
    output = run_powershell_script("codex-page-smoke.ps1", "-PageSlug", "product-category-pnl")

    assert "Codex page smoke: product-category-pnl" in output
    assert "/product-category-pnl" in output
    assert "/ui/pnl/product-category" in output
    assert "Playwright MCP" in output
    assert "Live checks:" not in output


def test_codex_page_smoke_supports_dashboard_home_checklist_only():
    output = run_powershell_script("codex-page-smoke.ps1", "-PageSlug", "dashboard-home")

    assert "Codex page smoke: dashboard-home" in output
    assert "Route aliases:" in output
    assert "http://127.0.0.1:5888/dashboard" in output
    assert "/ui/home/snapshot" in output
    assert "/api/dashboard/core_metrics" in output
    assert "Playwright MCP" in output
    assert "formal metric truth" in output
    assert "Live checks:" not in output


def test_codex_page_smoke_supports_balance_analysis_checklist_only():
    output = run_powershell_script("codex-page-smoke.ps1", "-PageSlug", "balance-analysis")

    assert "Codex page smoke: balance-analysis" in output
    assert "http://127.0.0.1:5888/balance-analysis" in output
    assert "/ui/balance-analysis/overview" in output
    assert "/ui/balance-analysis/dates" in output
    assert "Playwright MCP" in output
    assert "formal balance truth" in output
    assert "Live checks:" not in output


def test_codex_page_smoke_supports_pnl_checklist_only():
    output = run_powershell_script("codex-page-smoke.ps1", "-PageSlug", "pnl")

    assert "Codex page smoke: pnl" in output
    assert "http://127.0.0.1:5888/pnl" in output
    assert "/api/pnl/overview" in output
    assert "/api/pnl/dates" in output
    assert "/api/pnl/v1-data" in output
    assert "Playwright MCP" in output
    assert "formal PnL truth" in output
    assert "Live checks:" not in output


def test_codex_page_smoke_supports_pnl_bridge_checklist_only():
    output = run_powershell_script("codex-page-smoke.ps1", "-PageSlug", "pnl-bridge")

    assert "Codex page smoke: pnl-bridge" in output
    assert "http://127.0.0.1:5888/pnl-bridge" in output
    assert "/api/pnl/bridge" in output
    assert "/api/pnl/dates" in output
    assert "Playwright MCP" in output
    assert "PnL Bridge" in output
    assert "bridge warnings" in output
    assert "Live checks:" not in output


def test_codex_page_smoke_supports_risk_tensor_checklist_only():
    output = run_powershell_script("codex-page-smoke.ps1", "-PageSlug", "risk-tensor")

    assert "Codex page smoke: risk-tensor" in output
    assert "http://127.0.0.1:5888/risk-tensor" in output
    assert "/api/risk/tensor" in output
    assert "/api/risk/tensor/dates" in output
    assert "Playwright MCP" in output
    assert "Risk Tensor" in output
    assert "regulatory_dv01" in output
    assert "Live checks:" not in output


def test_codex_page_smoke_supports_bond_dashboard_checklist_only():
    output = run_powershell_script("codex-page-smoke.ps1", "-PageSlug", "bond-dashboard")

    assert "Codex page smoke: bond-dashboard" in output
    assert "http://127.0.0.1:5888/bond-dashboard" in output
    assert "/api/bond-dashboard/headline-kpis" in output
    assert "/api/bond-dashboard/dates" in output
    assert "/api/bond-dashboard/risk-indicators" in output
    assert "Playwright MCP" in output
    assert "candidate bond-dashboard headline question" in output
    assert "MTR-BOND" in output
    assert "Live checks:" not in output


def test_codex_page_smoke_supports_balance_movement_analysis_checklist_only():
    output = run_powershell_script("codex-page-smoke.ps1", "-PageSlug", "balance-movement-analysis")

    assert "Codex page smoke: balance-movement-analysis" in output
    assert "http://127.0.0.1:5888/balance-movement-analysis" in output
    assert "/ui/balance-movement-analysis" in output
    assert "/ui/balance-movement-analysis/dates" in output
    assert "Playwright MCP" in output
    assert "balance movement explanation question" in output
    assert "MTR-BMV" in output
    assert "Live checks:" not in output


def test_codex_page_smoke_balance_movement_check_live_fails_when_report_dates_missing():
    payload = {
        "result": {
            "currency_basis": "CNX",
            "freshness_status": "fresh",
            "latest_read_model_report_date": "2026-05-31",
            "latest_upstream_control_report_date": "2026-05-31",
        },
        "result_meta": {
            "tables_used": [
                "fact_accounting_asset_movement_monthly",
                "product_category_pnl_canonical_fact",
            ]
        },
    }
    with balance_movement_smoke_server(payload) as base_url:
        completed = run_powershell_script_result(
            "codex-page-smoke.ps1",
            "-PageSlug",
            "balance-movement-analysis",
            "-CheckLive",
            "-FrontendBaseUrl",
            base_url,
            "-ApiBaseUrl",
            base_url,
        )

    assert completed.returncode != 0
    assert (
        "Balance Movement freshness gate failed: missing read-model, upstream, or selectable report date."
        in completed.stderr
    )


def test_codex_page_smoke_balance_movement_check_live_passes_with_fresh_dates_payload():
    payload = {
        "result": {
            "report_dates": ["2026-05-31"],
            "currency_basis": "CNX",
            "freshness_status": "fresh",
            "latest_read_model_report_date": "2026-05-31",
            "latest_upstream_control_report_date": "2026-05-31",
        },
        "result_meta": {
            "tables_used": [
                "fact_accounting_asset_movement_monthly",
                "product_category_pnl_canonical_fact",
            ]
        },
    }
    with balance_movement_smoke_server(payload) as base_url:
        output = run_powershell_script(
            "codex-page-smoke.ps1",
            "-PageSlug",
            "balance-movement-analysis",
            "-CheckLive",
            "-FrontendBaseUrl",
            base_url,
            "-ApiBaseUrl",
            base_url,
        )

    assert "Balance Movement freshness gate passed: read_model=2026-05-31; upstream=2026-05-31; status=fresh" in output


def test_codex_page_smoke_supports_ledger_pnl_checklist_only():
    output = run_powershell_script("codex-page-smoke.ps1", "-PageSlug", "ledger-pnl")

    assert "Codex page smoke: ledger-pnl" in output
    assert "http://127.0.0.1:5888/ledger-pnl" in output
    assert "/api/ledger-pnl/summary" in output
    assert "/api/ledger-pnl/dates" in output
    assert "/api/ledger-pnl/formal-financial-indicators" in output
    assert "Playwright MCP" in output
    assert "ledger-account PnL candidate display question" in output
    assert "MTR-LPN" in output
    assert "Live checks:" not in output


def test_codex_page_smoke_ledger_pnl_check_live_uses_dates_payload():
    payload = {
        "result": {
            "dates": ["2026-05-31"],
        },
        "result_meta": {
            "tables_used": ["qdb_general_ledger_workbook"],
        },
    }
    with ledger_pnl_smoke_server(payload) as base_url:
        output = run_powershell_script(
            "codex-page-smoke.ps1",
            "-PageSlug",
            "ledger-pnl",
            "-CheckLive",
            "-FrontendBaseUrl",
            base_url,
            "-ApiBaseUrl",
            base_url,
        )

    assert "Page API detail skipped: no report_dates returned by /dates" not in output
    assert "Page API reachable: /api/ledger-pnl/data" in output
    assert "Page API reachable: /api/ledger-pnl/summary" in output


def test_codex_page_smoke_supports_positions_checklist_only():
    output = run_powershell_script("codex-page-smoke.ps1", "-PageSlug", "positions")

    assert "Codex page smoke: positions" in output
    assert "http://127.0.0.1:5888/positions" in output
    assert "/api/positions/bonds" in output
    assert "/api/positions/interbank" in output
    assert "/api/positions/stats/rating" in output
    assert "Playwright MCP" in output
    assert "positions list candidate display question" in output
    assert "MTR-POS" in output
    assert "Live checks:" not in output


def test_codex_page_smoke_supports_operations_analysis_checklist_only():
    output = run_powershell_script("codex-page-smoke.ps1", "-PageSlug", "operations-analysis")

    assert "Codex page smoke: operations-analysis" in output
    assert "http://127.0.0.1:5888/operations-analysis" in output
    assert "/ui/pnl/product-category" in output
    assert "/ui/balance-analysis/overview" in output
    assert "/ui/market-data/fx/formal-status" in output
    assert "Playwright MCP" in output
    assert "operations mixed-source entry question" in output
    assert "MTR-OPS" in output
    assert "Live checks:" not in output


def test_codex_page_smoke_supports_liability_analytics_checklist_only():
    output = run_powershell_script("codex-page-smoke.ps1", "-PageSlug", "liability-analytics")

    assert "Codex page smoke: liability-analytics" in output
    assert "http://127.0.0.1:5888/liability-analytics" in output
    assert "/api/risk/buckets" in output
    assert "/api/analysis/yield_metrics" in output
    assert "/api/analysis/liabilities/counterparty" in output
    assert "Playwright MCP" in output
    assert "liability compatibility analytics question" in output
    assert "MTR-LIAB" in output
    assert "Live checks:" not in output


def test_codex_page_smoke_supports_market_data_checklist_only():
    output = run_powershell_script("codex-page-smoke.ps1", "-PageSlug", "market-data")

    assert "Codex page smoke: market-data" in output
    assert "http://127.0.0.1:5888/market-data" in output
    assert "/ui/preview/macro-foundation" in output
    assert "/ui/market-data/rates" in output
    assert "/ui/market-data/fx/formal-status" in output
    assert "/ui/market-data/ncd-funding-proxy" in output
    assert "/ui/market-data/livermore" in output
    assert "Playwright MCP" in output
    assert "market-data mixed-source question" in output
    assert "MTR-MKT-001" in output
    assert "Live checks:" not in output


def test_codex_page_smoke_supports_macro_toolkit_checklist_only():
    output = run_powershell_script("codex-page-smoke.ps1", "-PageSlug", "macro-toolkit")

    assert "Codex page smoke: macro-toolkit" in output
    assert "http://127.0.0.1:5888/macro-toolkit" in output
    assert "/ui/macro/toolkit/analysis" in output
    assert "/ui/macro/toolkit/analysis/strategy-summaries" in output
    assert "/ui/macro/toolkit/scripts" in output
    assert "/ui/macro/toolkit/choice-stock/refresh-status" in output
    assert "Playwright MCP" in output
    assert "macro-toolkit tooling observation question" in output
    assert "formal metric truth" in output
    assert "investment recommendations" in output
    assert "operation/script outputs" in output
    assert "Live checks:" not in output


def test_codex_page_smoke_supports_stock_analysis_checklist_only():
    output = run_powershell_script("codex-page-smoke.ps1", "-PageSlug", "stock-analysis")

    assert "Codex page smoke: stock-analysis" in output
    assert "http://127.0.0.1:5888/stock-analysis" in output
    assert "/ui/market-data/livermore" in output
    assert "/ui/market-data/livermore/signal-confluence" in output
    assert "/ui/market-data/livermore/stock-detail" in output
    assert "/ui/market-data/livermore/candidate-history" in output
    assert "/ui/market-data/livermore/strategy-score" in output
    assert "/ui/market-data/livermore/sector-rank-series" in output
    assert "Playwright MCP" in output
    assert "stock-analysis observational review question" in output
    assert "PAGE-STOCK" in output
    assert "trading instructions" in output
    assert "formal metric truth" in output
    assert "Live checks:" not in output


def test_codex_page_smoke_supports_pnl_attribution_checklist_only():
    output = run_powershell_script("codex-page-smoke.ps1", "-PageSlug", "pnl-attribution")

    assert "Codex page smoke: pnl-attribution" in output
    assert "http://127.0.0.1:5888/pnl-attribution" in output
    assert "/api/pnl-attribution/volume-rate" in output
    assert "/api/pnl-attribution/tpl-market" in output
    assert "/api/pnl-attribution/composition" in output
    assert "/api/pnl-attribution/advanced/summary" in output
    assert "/api/pnl-attribution/campisi/four-effects" in output
    assert "Playwright MCP" in output
    assert "PnL Attribution Workbench candidate closure question" in output
    assert "MTR-PAT" in output
    assert "formal PnL overview" in output
    assert "executive analytical overlay" in output
    assert "Live checks:" not in output


def test_codex_page_smoke_supports_concentration_monitor_checklist_only():
    output = run_powershell_script("codex-page-smoke.ps1", "-PageSlug", "concentration-monitor")

    assert "Codex page smoke: concentration-monitor" in output
    assert "http://127.0.0.1:5888/concentration-monitor" in output
    assert "/api/bond-analytics/credit-spread-migration" in output
    assert "/api/bond-analytics/dates" in output
    assert "Playwright MCP" in output
    assert "concentration-monitor candidate risk question" in output
    assert "MTR-CON" in output
    assert "formal risk truth" in output
    assert "certified concentration-limit approval" in output
    assert "Live checks:" not in output


def test_codex_page_smoke_supports_team_performance_checklist_only():
    output = run_powershell_script("codex-page-smoke.ps1", "-PageSlug", "team-performance")

    assert "Codex page smoke: team-performance" in output
    assert "http://127.0.0.1:5888/team-performance" in output
    assert "/api/pnl/by-business-ytd" in output
    assert "/ui/pnl/product-category" in output
    assert "Playwright MCP" in output
    assert "candidate team-performance mapping question" in output
    assert "MTR-TEAM-001" in output
    assert "formal KPI truth" in output
    assert "owner-approved performance allocation" in output
    assert "Live checks:" not in output


def test_codex_page_smoke_supports_platform_config_checklist_only():
    output = run_powershell_script("codex-page-smoke.ps1", "-PageSlug", "platform-config")

    assert "Codex page smoke: platform-config" in output
    assert "http://127.0.0.1:5888/platform-config" in output
    assert "/ui/preview/source-foundation" in output
    assert "/health/ready" in output
    assert "/health/live" in output
    assert "Playwright MCP" in output
    assert "diagnostic platform/source question" in output
    assert "MTR-PLT-001" in output
    assert "MTR-PLT-003" in output
    assert "data-quality approval" in output
    assert "Live checks:" not in output


def test_codex_page_smoke_supports_news_events_checklist_only():
    output = run_powershell_script("codex-page-smoke.ps1", "-PageSlug", "news-events")

    assert "Codex page smoke: news-events" in output
    assert "http://127.0.0.1:5888/news-events" in output
    assert "/ui/news/choice-events/latest" in output
    assert "Playwright MCP" in output
    assert "analytical news/event context question" in output
    assert "PAGE-CONTRACT-PENDING:/news-events" in output
    assert "GAP-NEWS-EVENTS-PAGE" in output
    assert "formal metric truth" in output
    assert "trading instruction" in output
    assert "source data-quality approval" in output
    assert "Live checks:" not in output


def test_codex_page_readiness_defaults_to_dry_run():
    output = run_powershell_script("codex-page-readiness.ps1", "-PageSlug", "product-category-pnl")

    assert "MOSS page readiness gate: product-category-pnl" in output
    assert "Static evidence gates:" in output
    assert "trace_bundle_present: pass" in output
    assert "evidence_readiness_explicit: pass" in output
    assert "golden_sample_boundary: pass" in output
    assert "Residual gaps surfaced:" in output
    assert "codex-page-smoke.ps1 -PageSlug product-category-pnl" in output
    assert "codex-verify-page.ps1 -PageSlug product-category-pnl -Run" in output
    assert "Dry run complete. Pass -Run to execute page checks." in output
    assert "Page readiness gate passed." not in output


def test_codex_page_readiness_supports_dashboard_home_dry_run():
    output = run_powershell_script("codex-page-readiness.ps1", "-PageSlug", "dashboard-home")

    assert "MOSS page readiness gate: dashboard-home" in output
    assert "mixed_source_or_observational" in output
    assert "formal_promotion_boundary: pass" in output
    assert "supporting_or_fragment_only" in output
    assert "codex-page-smoke.ps1 -PageSlug dashboard-home" in output
    assert "codex-verify-page.ps1 -PageSlug dashboard-home -Run" in output


def test_codex_page_readiness_supports_balance_analysis_dry_run():
    output = run_powershell_script("codex-page-readiness.ps1", "-PageSlug", "balance-analysis")

    assert "MOSS page readiness gate: balance-analysis" in output
    assert "formal_or_governed" in output
    assert "golden_sample_boundary: pass" in output
    assert "codex-page-smoke.ps1 -PageSlug balance-analysis" in output
    assert "codex-verify-page.ps1 -PageSlug balance-analysis -Run" in output
    assert "Dry run complete. Pass -Run to execute page checks." in output


def test_codex_page_readiness_supports_pnl_dry_run():
    output = run_powershell_script("codex-page-readiness.ps1", "-PageSlug", "pnl")

    assert "MOSS page readiness gate: pnl" in output
    assert "formal_or_governed" in output
    assert "golden_sample_boundary: pass" in output
    assert "codex-page-smoke.ps1 -PageSlug pnl" in output
    assert "codex-verify-page.ps1 -PageSlug pnl -Run" in output
    assert "full data-catalog/date review required" in output
    assert "direct page-keyed governance records" in output
    assert "Dry run complete. Pass -Run to execute page checks." in output


def test_codex_page_readiness_supports_pnl_bridge_dry_run():
    output = run_powershell_script("codex-page-readiness.ps1", "-PageSlug", "pnl-bridge")

    assert "MOSS page readiness gate: pnl-bridge" in output
    assert "formal_or_governed" in output
    assert "golden_sample_boundary: pass" in output
    assert "codex-page-smoke.ps1 -PageSlug pnl-bridge" in output
    assert "codex-verify-page.ps1 -PageSlug pnl-bridge -Run" in output
    assert "full data-catalog/date review required" in output
    assert "direct page-keyed governance records" in output
    assert "Dry run complete. Pass -Run to execute page checks." in output


def test_codex_page_readiness_supports_risk_tensor_dry_run():
    output = run_powershell_script("codex-page-readiness.ps1", "-PageSlug", "risk-tensor")

    assert "MOSS page readiness gate: risk-tensor" in output
    assert "formal_or_governed" in output
    assert "golden_sample_boundary: pass" in output
    assert "catalog_date_evidence_sampled: pass" in output
    assert "direct_governance_record_ready: pass" in output
    assert "codex-page-smoke.ps1 -PageSlug risk-tensor" in output
    assert "codex-verify-page.ps1 -PageSlug risk-tensor -Run" in output
    assert "full data-catalog/date review required" not in output
    assert "direct page-keyed governance records" not in output
    assert "Business owner approval is still required" in output
    assert "Dry run complete. Pass -Run to execute page checks." in output


def test_codex_page_readiness_supports_bond_dashboard_dry_run():
    output = run_powershell_script("codex-page-readiness.ps1", "-PageSlug", "bond-dashboard")

    assert "MOSS page readiness gate: bond-dashboard" in output
    assert "candidate_or_pending" in output
    assert "golden_sample_boundary: pass" in output
    assert "page_dto_only" in output
    assert "catalog_date_evidence_sampled: pass" in output
    assert "direct_governance_record_ready: pass" in output
    assert "codex-page-smoke.ps1 -PageSlug bond-dashboard" in output
    assert "codex-verify-page.ps1 -PageSlug bond-dashboard -Run" in output
    assert "full data-catalog/date review required" not in output
    assert "direct page-keyed governance records" not in output
    assert "Candidate metric dictionary-level approval remains pending." in output
    assert "Business owner approval is still required" in output
    assert "Dry run complete. Pass -Run to execute page checks." in output


def test_codex_page_readiness_supports_balance_movement_analysis_dry_run():
    output = run_powershell_script("codex-page-readiness.ps1", "-PageSlug", "balance-movement-analysis")

    assert "MOSS page readiness gate: balance-movement-analysis" in output
    assert "candidate_or_pending" in output
    assert "golden_sample_boundary: pass" in output
    assert "missing" in output
    assert "catalog_date_evidence_sampled: pass" in output
    assert "direct_governance_record_ready: pass" in output
    assert "codex-page-smoke.ps1 -PageSlug balance-movement-analysis" in output
    assert "codex-verify-page.ps1 -PageSlug balance-movement-analysis -Run" in output
    assert "full data-catalog/date review required" not in output
    assert "direct page-keyed governance records" not in output
    assert "dedicated golden sample is missing" in output
    assert "Business owner approval is still required" in output
    assert "Dry run complete. Pass -Run to execute page checks." in output


def test_codex_page_readiness_supports_ledger_pnl_dry_run():
    output = run_powershell_script("codex-page-readiness.ps1", "-PageSlug", "ledger-pnl")

    assert "MOSS page readiness gate: ledger-pnl" in output
    assert "candidate_or_pending" in output
    assert "golden_sample_boundary: pass" in output
    assert "missing" in output
    assert "codex-page-smoke.ps1 -PageSlug ledger-pnl" in output
    assert "codex-verify-page.ps1 -PageSlug ledger-pnl -Run" in output
    assert "full data-catalog/date review required" in output
    assert "direct page-keyed governance records" in output
    assert "Candidate metric dictionary-level approval remains pending." in output
    assert "Dry run complete. Pass -Run to execute page checks." in output


def test_codex_page_readiness_supports_positions_dry_run():
    output = run_powershell_script("codex-page-readiness.ps1", "-PageSlug", "positions")

    assert "MOSS page readiness gate: positions" in output
    assert "candidate_or_pending" in output
    assert "golden_sample_boundary: pass" in output
    assert "missing" in output
    assert "codex-page-smoke.ps1 -PageSlug positions" in output
    assert "codex-verify-page.ps1 -PageSlug positions -Run" in output
    assert "full data-catalog/date review required" in output
    assert "direct page-keyed governance records" in output
    assert "Candidate metric dictionary-level approval remains pending." in output
    assert "dedicated golden sample is missing" in output
    assert "Dry run complete. Pass -Run to execute page checks." in output


def test_codex_page_readiness_supports_operations_analysis_dry_run():
    output = run_powershell_script("codex-page-readiness.ps1", "-PageSlug", "operations-analysis")

    assert "MOSS page readiness gate: operations-analysis" in output
    assert "mixed_source_or_observational" in output
    assert "golden_sample_boundary: pass" in output
    assert "supporting_or_fragment_only" in output
    assert "codex-page-smoke.ps1 -PageSlug operations-analysis" in output
    assert "codex-verify-page.ps1 -PageSlug operations-analysis -Run" in output
    assert "full data-catalog/date review required" in output
    assert "direct page-keyed governance records" in output
    assert "Mixed-source page cannot be collapsed into full-page formal truth." in output
    assert "GAP-OPS-MACRO-FX" in output
    assert "Dry run complete. Pass -Run to execute page checks." in output


def test_codex_page_readiness_supports_liability_analytics_dry_run():
    output = run_powershell_script("codex-page-readiness.ps1", "-PageSlug", "liability-analytics")

    assert "MOSS page readiness gate: liability-analytics" in output
    assert "mixed_source_or_observational" in output
    assert "golden_sample_boundary: pass" in output
    assert "missing" in output
    assert "codex-page-smoke.ps1 -PageSlug liability-analytics" in output
    assert "codex-verify-page.ps1 -PageSlug liability-analytics -Run" in output
    assert "full data-catalog/date review required" in output
    assert "direct page-keyed governance records" in output
    assert "Mixed-source page cannot be collapsed into full-page formal truth." in output
    assert "dedicated golden sample is missing" in output
    assert "Dry run complete. Pass -Run to execute page checks." in output


def test_codex_page_readiness_supports_market_data_dry_run():
    output = run_powershell_script("codex-page-readiness.ps1", "-PageSlug", "market-data")

    assert "MOSS page readiness gate: market-data" in output
    assert "mixed_source_or_observational" in output
    assert "golden_sample_boundary: pass" in output
    assert "missing" in output
    assert "codex-page-smoke.ps1 -PageSlug market-data" in output
    assert "codex-verify-page.ps1 -PageSlug market-data -Run" in output
    assert "full data-catalog/date review required" in output
    assert "direct page-keyed governance records" in output
    assert "Mixed-source page cannot be collapsed into full-page formal truth." in output
    assert "dedicated golden sample is missing" in output
    assert "Dry run complete. Pass -Run to execute page checks." in output


def test_codex_page_readiness_supports_macro_toolkit_dry_run():
    output = run_powershell_script("codex-page-readiness.ps1", "-PageSlug", "macro-toolkit")

    assert "MOSS page readiness gate: macro-toolkit" in output
    assert "mixed_source_or_observational" in output
    assert "golden_sample_boundary: pass" in output
    assert "missing" in output
    assert "codex-page-smoke.ps1 -PageSlug macro-toolkit" in output
    assert "codex-verify-page.ps1 -PageSlug macro-toolkit -Run" in output
    assert "full data-catalog/date review required" in output
    assert "direct page-keyed governance records" in output
    assert "Mixed-source page cannot be collapsed into full-page formal truth." in output
    assert "dedicated golden sample is missing" in output
    assert "Dry run complete. Pass -Run to execute page checks." in output


def test_codex_page_readiness_supports_stock_analysis_dry_run():
    output = run_powershell_script("codex-page-readiness.ps1", "-PageSlug", "stock-analysis")

    assert "MOSS page readiness gate: stock-analysis" in output
    assert "gap_or_observational" in output
    assert "golden_sample_boundary: pass" in output
    assert "missing" in output
    assert "codex-page-smoke.ps1 -PageSlug stock-analysis" in output
    assert "codex-verify-page.ps1 -PageSlug stock-analysis -Run" in output
    assert "full data-catalog/date review required" in output
    assert "direct page-keyed governance records" in output
    assert "GAP/observational route lacks standalone formal page contract closure" in output
    assert "PAGE-STOCK contracts" in output
    assert "Dedicated sample GS-STOCK-ANALYSIS-OBS-A is page DTO evidence only" in output
    assert "Trading instructions" in output
    assert "Dry run complete. Pass -Run to execute page checks." in output


def test_codex_page_readiness_supports_pnl_attribution_dry_run():
    output = run_powershell_script("codex-page-readiness.ps1", "-PageSlug", "pnl-attribution")

    assert "MOSS page readiness gate: pnl-attribution" in output
    assert "candidate_or_pending" in output
    assert "golden_sample_boundary: pass" in output
    assert "missing" in output
    assert "codex-page-smoke.ps1 -PageSlug pnl-attribution" in output
    assert "codex-verify-page.ps1 -PageSlug pnl-attribution -Run" in output
    assert "catalog_date_evidence_sampled: pass (5/5 table date samples)" in output
    assert "direct_governance_record_ready: pass (1 ready direct record(s))" in output
    assert "Candidate metric dictionary-level approval remains pending." in output
    assert "Existing golden sample is supporting or page DTO evidence only" in output
    assert "Dry run complete. Pass -Run to execute page checks." in output


def test_codex_page_readiness_all_mode_defaults_to_batch_dry_run():
    output = run_powershell_script("codex-page-readiness.ps1", "-All")

    assert "MOSS page readiness gate: all seeded pages" in output
    assert "Summary: page_count=39" in output
    assert "blocked_count=0" in output
    assert "run_supported_count=27" in output
    assert "Page readiness rows:" in output
    assert "Blocking pages:" not in output
    assert "executive-pnl-attribution: static-pass" in output
    assert "product-category-pnl" in output
    assert "balance-analysis" in output
    assert "macro-toolkit" in output
    assert "reports-home" in output
    assert "Batch dry run complete. Pass -Run to execute page checks for supported pages." in output
    assert "Page readiness gate passed." not in output
