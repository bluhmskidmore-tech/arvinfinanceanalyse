from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest
import tomllib

REPO_ROOT = Path(__file__).resolve().parents[1]
MCP_SCRIPT = REPO_ROOT / "scripts" / "mcp" / "moss_project_mcp.py"
CODEX_CONFIG = REPO_ROOT / ".codex" / "config.toml"


class McpProcess:
    def __init__(self, mode: str, env: dict[str, str] | None = None) -> None:
        process_env = os.environ.copy()
        process_env.update(env or {})
        self.process = subprocess.Popen(
            [sys.executable, str(MCP_SCRIPT), mode],
            cwd=REPO_ROOT,
            env=process_env,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        self._next_id = 1

    def close(self) -> None:
        self.process.terminate()
        try:
            self.process.wait(timeout=2)
        except subprocess.TimeoutExpired:
            self.process.kill()

    def request(self, method: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        request_id = self._next_id
        self._next_id += 1
        self._send({"jsonrpc": "2.0", "id": request_id, "method": method, "params": params or {}})
        response = self._read()
        assert response["id"] == request_id
        assert "error" not in response, response.get("error")
        return dict(response["result"])

    def request_error(self, method: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        request_id = self._next_id
        self._next_id += 1
        self._send({"jsonrpc": "2.0", "id": request_id, "method": method, "params": params or {}})
        response = self._read()
        assert response["id"] == request_id
        assert "error" in response, response
        return dict(response["error"])

    def notify(self, method: str, params: dict[str, Any] | None = None) -> None:
        self._send({"jsonrpc": "2.0", "method": method, "params": params or {}})

    def _send(self, payload: dict[str, Any]) -> None:
        assert self.process.stdin is not None
        body = json.dumps(payload).encode("utf-8")
        self.process.stdin.write(f"Content-Length: {len(body)}\r\n\r\n".encode("ascii") + body)
        self.process.stdin.flush()

    def _read(self) -> dict[str, Any]:
        assert self.process.stdout is not None
        headers = []
        while True:
            line = self.process.stdout.readline()
            assert line, self._stderr()
            if line in (b"\r\n", b"\n"):
                break
            headers.append(line.decode("ascii").strip())
        length = None
        for header in headers:
            if header.lower().startswith("content-length:"):
                length = int(header.split(":", 1)[1].strip())
        assert length is not None
        return json.loads(self.process.stdout.read(length).decode("utf-8"))

    def _stderr(self) -> str:
        if self.process.stderr is None:
            return ""
        return self.process.stderr.read().decode("utf-8", errors="replace")


def _request_initialize(command: str, args: list[str], cwd: Path) -> dict[str, Any]:
    process = subprocess.Popen(
        [command, *args],
        cwd=cwd,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    try:
        body = json.dumps({"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}}).encode("utf-8")
        assert process.stdin is not None
        process.stdin.write(f"Content-Length: {len(body)}\r\n\r\n".encode("ascii") + body)
        process.stdin.flush()

        assert process.stdout is not None
        headers = []
        while True:
            line = process.stdout.readline()
            assert line, process.stderr.read().decode("utf-8", errors="replace") if process.stderr else ""
            if line in (b"\r\n", b"\n"):
                break
            headers.append(line.decode("ascii").strip())
        length = None
        for header in headers:
            if header.lower().startswith("content-length:"):
                length = int(header.split(":", 1)[1].strip())
        assert length is not None
        return dict(json.loads(process.stdout.read(length).decode("utf-8")))
    finally:
        process.terminate()
        try:
            process.wait(timeout=2)
        except subprocess.TimeoutExpired:
            process.kill()


def _resolve_config_cwd(raw_cwd: str) -> Path:
    return (REPO_ROOT / raw_cwd).resolve()


def test_project_mcp_config_declares_read_only_surfaces() -> None:
    payload = json.loads((REPO_ROOT / ".mcp.json").read_text(encoding="utf-8"))
    servers = payload["mcpServers"]

    assert set(servers) >= {
        "gitnexus",
        "moss-metric-contracts",
        "moss-lineage-evidence",
        "moss-data-catalog",
        "moss-data-quality",
        "playwright",
    }
    assert servers["gitnexus"]["command"] == "node"
    assert servers["gitnexus"]["args"] == ["scripts/mcp/gitnexus_mcp_launcher.mjs"]
    if os.name != "nt":
        return
    assert servers["moss-metric-contracts"]["command"] == "cmd.exe"
    assert servers["moss-metric-contracts"]["args"] == [
        "/d",
        "/s",
        "/c",
        "scripts\\mcp\\moss_contracts.cmd",
    ]
    assert servers["moss-lineage-evidence"]["command"] == "cmd.exe"
    assert servers["moss-lineage-evidence"]["args"] == [
        "/d",
        "/s",
        "/c",
        "scripts\\mcp\\moss_lineage.cmd",
    ]
    assert servers["moss-data-catalog"]["command"] == "cmd.exe"
    assert servers["moss-data-catalog"]["args"] == [
        "/d",
        "/s",
        "/c",
        "scripts\\mcp\\moss_catalog.cmd",
    ]
    assert servers["moss-data-quality"]["command"] == "cmd.exe"
    assert servers["moss-data-quality"]["args"] == [
        "/d",
        "/s",
        "/c",
        "scripts\\mcp\\moss_data_quality.cmd",
    ]
    assert servers["playwright"]["args"][-1] == "@playwright/mcp@latest"


def test_project_mcp_config_pins_mcp_cwd_for_compatible_clients() -> None:
    if os.name != "nt":
        return

    payload = json.loads((REPO_ROOT / ".mcp.json").read_text(encoding="utf-8"))
    servers = payload["mcpServers"]

    for name in (
        "gitnexus",
        "moss-metric-contracts",
        "moss-lineage-evidence",
        "moss-data-catalog",
        "moss-data-quality",
        "playwright",
    ):
        assert _resolve_config_cwd(servers[name]["cwd"]) == REPO_ROOT


def test_project_codex_config_declares_read_only_surfaces() -> None:
    payload = tomllib.loads(CODEX_CONFIG.read_text(encoding="utf-8"))
    servers = payload["mcp_servers"]

    assert set(servers) >= {
        "gitnexus",
        "moss-metric-contracts",
        "moss-lineage-evidence",
        "moss-data-catalog",
        "moss-data-quality",
        "playwright",
    }
    assert servers["gitnexus"]["command"] == "node"
    assert servers["gitnexus"]["args"] == ["scripts/mcp/gitnexus_mcp_launcher.mjs"]
    if os.name != "nt":
        return
    assert servers["moss-metric-contracts"]["command"] == "cmd.exe"
    assert servers["moss-metric-contracts"]["args"] == [
        "/d",
        "/s",
        "/c",
        "scripts\\mcp\\moss_contracts.cmd",
    ]
    assert servers["moss-lineage-evidence"]["command"] == "cmd.exe"
    assert servers["moss-lineage-evidence"]["args"] == [
        "/d",
        "/s",
        "/c",
        "scripts\\mcp\\moss_lineage.cmd",
    ]
    assert servers["moss-data-catalog"]["command"] == "cmd.exe"
    assert servers["moss-data-catalog"]["args"] == [
        "/d",
        "/s",
        "/c",
        "scripts\\mcp\\moss_catalog.cmd",
    ]
    assert servers["moss-data-quality"]["command"] == "cmd.exe"
    assert servers["moss-data-quality"]["args"] == [
        "/d",
        "/s",
        "/c",
        "scripts\\mcp\\moss_data_quality.cmd",
    ]
    assert servers["playwright"]["command"] == "npx"
    assert servers["playwright"]["args"][-1] == "@playwright/mcp@latest"


def test_project_codex_config_pins_mcp_cwd_for_app_launches() -> None:
    if os.name != "nt":
        return

    payload = tomllib.loads(CODEX_CONFIG.read_text(encoding="utf-8"))
    servers = payload["mcp_servers"]

    for name in (
        "gitnexus",
        "moss-metric-contracts",
        "moss-lineage-evidence",
        "moss-data-catalog",
        "moss-data-quality",
        "playwright",
    ):
        assert _resolve_config_cwd(servers[name]["cwd"]) == REPO_ROOT


def test_moss_codex_mcp_entries_handshake_from_declared_cwd() -> None:
    if os.name != "nt":
        return

    payload = tomllib.loads(CODEX_CONFIG.read_text(encoding="utf-8"))
    servers = payload["mcp_servers"]

    for name, expected_server_info_name in (
        ("moss-metric-contracts", "moss-metric-contracts"),
        ("moss-lineage-evidence", "moss-lineage-evidence"),
        ("moss-data-catalog", "moss-data-catalog"),
        ("moss-data-quality", "moss-data-quality"),
    ):
        response = _request_initialize(
            servers[name]["command"],
            list(servers[name]["args"]),
            _resolve_config_cwd(servers[name]["cwd"]),
        )
        assert response["result"]["serverInfo"]["name"] == expected_server_info_name


def test_moss_launcher_handshake_is_cwd_independent() -> None:
    response = _request_initialize(
        sys.executable,
        [str(REPO_ROOT / "scripts" / "mcp" / "moss_mcp_launcher.py"), "metric-contracts"],
        REPO_ROOT / "tests",
    )
    assert response["result"]["serverInfo"]["name"] == "moss-metric-contracts"


def test_metric_contracts_mcp_exposes_contract_docs() -> None:
    server = McpProcess("metric-contracts")
    try:
        init = server.request("initialize")
        server.notify("notifications/initialized")
        assert init["serverInfo"]["name"] == "moss-metric-contracts"

        resources = server.request("resources/list")["resources"]
        assert any(item["uri"] == "moss://metric-contracts/summary" for item in resources)

        summary = server.request("resources/read", {"uri": "moss://metric-contracts/summary"})
        summary_payload = json.loads(summary["contents"][0]["text"])
        assert any(doc["key"] == "page_contracts" and doc["exists"] for doc in summary_payload["documents"])

        search = server.request(
            "tools/call",
            {"name": "search_contract_docs", "arguments": {"query": "product-category", "max_results": 5}},
        )
        search_payload = json.loads(search["content"][0]["text"])
        assert search_payload["matches"]
    finally:
        server.close()


@pytest.mark.parametrize(
    (
        "page_slug",
        "frontend_route",
        "primary_api",
        "truth_marker",
        "backend_touchpoint",
        "frontend_touchpoint",
        "test_touchpoint",
        "golden_sample",
        "guardrail_marker",
        "alias",
    ),
    [
        (
            "product-category-pnl",
            "/product-category-pnl",
            "/ui/pnl/product-category",
            "product_category_pnl_formal_read_model",
            "backend/app/services/product_category_source_service.py",
            "frontend/src/features/product-category-pnl/pages/ProductCategoryPnlPage.tsx",
            "tests/test_product_category_pnl_flow.py",
            "tests/golden_samples/GS-PROD-CAT-PNL-A",
            "zqtz holdings-side logic",
            "/product-category-pnl",
        ),
        (
            "dashboard-home",
            "/",
            "/ui/home/snapshot",
            "home_snapshot_envelope",
            "backend/app/services/executive_service.py",
            "frontend/src/features/workbench/pages/DashboardPage.tsx",
            "tests/test_home_snapshot_endpoint.py",
            "tests/golden_samples/GS-EXEC-OVERVIEW-A",
            "formal metric truth",
            "/dashboard",
        ),
        (
            "risk-tensor",
            "/risk-tensor",
            "/api/risk/tensor",
            "RiskTensorPayload",
            "backend/app/services/risk_tensor_service.py",
            "frontend/src/features/risk-tensor/RiskTensorPage.tsx",
            "tests/test_risk_tensor_api.py",
            "tests/golden_samples/GS-RISK-A",
            "warning quality",
            "/risk-tensor",
        ),
        (
            "bond-dashboard",
            "/bond-dashboard",
            "/api/bond-dashboard/headline-kpis",
            "bond_dashboard.headline_kpis",
            "backend/app/services/bond_dashboard_service.py",
            "frontend/src/features/bond-dashboard/pages/BondDashboardPage.tsx",
            "tests/test_bond_dashboard_api_contract.py",
            "tests/golden_samples/GS-BOND-HEADLINE-A",
            "pending_confirmation=true",
            "PAGE-BOND-001",
        ),
        (
            "positions",
            "/positions",
            "/api/positions/bonds",
            "positions.bonds.list",
            "backend/app/services/positions_service.py",
            "frontend/src/features/positions/components/PositionsView.tsx",
            "tests/test_positions_api_contract.py",
            "NO_DEDICATED_GOLDEN_SAMPLE",
            "GAP-POS-LIST",
            "PAGE-POS-001",
        ),
        (
            "market-data",
            "/market-data",
            "/ui/preview/macro-foundation",
            "GAP-MKT-DATA",
            "backend/app/services/macro_vendor_service.py",
            "frontend/src/features/market-data/pages/MarketDataPage.tsx",
            "frontend/src/test/MarketDataPage.test.tsx",
            "NO_DEDICATED_GOLDEN_SAMPLE",
            "mixed-source",
            "PAGE-MKT-001",
        ),
        (
            "macro-toolkit",
            "/macro-toolkit",
            "/ui/macro/toolkit/analysis",
            "macro_toolkit.analysis",
            "backend/app/api/routes/macro_toolkit.py",
            "frontend/src/features/macro-toolkit/pages/MacroToolkitPage.tsx",
            "frontend/src/test/MacroToolkitPage.test.tsx",
            "NO_DEDICATED_GOLDEN_SAMPLE",
            "tooling/analysis",
            "PAGE-MACRO-TOOLKIT-001",
        ),
        (
            "macro-observation",
            "/macro-observation",
            "/ui/macro/toolkit/analysis",
            "read-only macro observation",
            "backend/app/api/routes/macro_toolkit.py",
            "frontend/src/features/macro-toolkit/pages/MacroToolkitPage.tsx",
            "frontend/src/test/MacroToolkitPage.test.tsx",
            "NO_DEDICATED_GOLDEN_SAMPLE",
            "read-only",
            "PAGE-MACRO-OBS-001",
        ),
        (
            "agent",
            "/agent",
            "POST /api/agent/runs",
            "AgentEnvelope",
            "backend/app/api/routes/agent.py",
            "frontend/src/features/agent/AgentWorkbenchPage.tsx",
            "tests/test_agent_api_contract.py",
            "NO_DEDICATED_GOLDEN_SAMPLE",
            "read-only",
            "PAGE-AGENT-001",
        ),
        (
            "cube-query",
            "/cube-query",
            "POST /api/cube/query",
            "CubeQueryResult",
            "backend/app/api/routes/cube_query.py",
            "frontend/src/features/cube-query/pages/CubeQueryPage.tsx",
            "tests/test_cube_query_api.py",
            "NO_DEDICATED_GOLDEN_SAMPLE",
            "candidate query surface",
            "PAGE-CUBE-QUERY-001",
        ),
        (
            "portfolio-home",
            "/portfolio",
            "frontend aggregation: module-home/portfolio",
            "PAGE-PORTFOLIO-HOME-001",
            "backend/app/api/routes/balance_analysis.py",
            "frontend/src/features/workbench/module-home/ModuleWorkbenchHomePage.tsx",
            "frontend/src/test/ModuleWorkbenchHomeModel.test.ts",
            "NO_DEDICATED_GOLDEN_SAMPLE",
            "module home",
            "PAGE-PORTFOLIO-HOME-001",
        ),
        (
            "market-home",
            "/market-overview",
            "frontend aggregation: module-home/market",
            "PAGE-MARKET-HOME-001",
            "backend/app/api/routes/macro_vendor.py",
            "frontend/src/features/workbench/module-home/ModuleWorkbenchHomePage.tsx",
            "frontend/src/test/ModuleWorkbenchHomeModel.test.ts",
            "NO_DEDICATED_GOLDEN_SAMPLE",
            "module home",
            "PAGE-MARKET-HOME-001",
        ),
        (
            "risk-home",
            "/risk-overview",
            "frontend aggregation: module-home/risk",
            "PAGE-RISK-HOME-001",
            "backend/app/api/routes/risk_tensor.py",
            "frontend/src/features/workbench/module-home/ModuleWorkbenchHomePage.tsx",
            "frontend/src/test/ModuleWorkbenchHomeModel.test.ts",
            "NO_DEDICATED_GOLDEN_SAMPLE",
            "module home",
            "PAGE-RISK-HOME-001",
        ),
        (
            "performance-home",
            "/performance",
            "frontend aggregation: module-home/performance",
            "PAGE-PERFORMANCE-HOME-001",
            "backend/app/api/routes/kpi.py",
            "frontend/src/features/workbench/module-home/ModuleWorkbenchHomePage.tsx",
            "frontend/src/test/ModuleWorkbenchHomeModel.test.ts",
            "NO_DEDICATED_GOLDEN_SAMPLE",
            "module home",
            "PAGE-PERFORMANCE-HOME-001",
        ),
        (
            "reports-home",
            "/reports",
            "frontend aggregation: module-home/governance",
            "PAGE-REPORTS-HOME-001",
            "backend/app/api/routes/health.py",
            "frontend/src/features/workbench/module-home/ModuleWorkbenchHomePage.tsx",
            "frontend/src/test/ModuleWorkbenchHomeModel.test.ts",
            "NO_DEDICATED_GOLDEN_SAMPLE",
            "module home",
            "PAGE-REPORTS-HOME-001",
        ),
        (
            "pnl-bridge",
            "/pnl-bridge",
            "/api/pnl/bridge",
            "PnlBridgePayload",
            "backend/app/services/pnl_bridge_service.py",
            "frontend/src/features/pnl/PnlBridgePage.tsx",
            "tests/test_pnl_bridge_core.py",
            "tests/golden_samples/GS-BRIDGE-A",
            "bridge warnings",
            "/pnl-bridge",
        ),
        (
            "balance-analysis",
            "/balance-analysis",
            "/ui/balance-analysis/overview",
            "balance_analysis_overview_envelope",
            "backend/app/services/balance_analysis_service.py",
            "frontend/src/features/balance-analysis/pages/BalanceAnalysisPage.tsx",
            "tests/test_balance_analysis_api.py",
            "tests/golden_samples/GS-BAL-OVERVIEW-A",
            "formal balance truth",
            "/balance-analysis",
        ),
        (
            "pnl",
            "/pnl",
            "/api/pnl/overview",
            "pnl_overview_envelope",
            "backend/app/services/pnl_service.py",
            "frontend/src/features/pnl/PnlPage.tsx",
            "tests/test_pnl_api_contract.py",
            "tests/golden_samples/GS-PNL-OVERVIEW-A",
            "formal PnL truth",
            "/pnl",
        ),
        (
            "ledger-pnl",
            "/ledger-pnl",
            "/api/ledger-pnl/summary",
            "ledger_pnl.summary",
            "backend/app/services/ledger_pnl_service.py",
            "frontend/src/features/ledger-pnl/pages/LedgerPnlPage.tsx",
            "tests/test_ledger_pnl_service.py",
            "NO_DEDICATED_GOLDEN_SAMPLE",
            "candidate display metrics",
            "PAGE-LEDGER-PNL-001",
        ),
        (
            "executive-overview",
            "/dashboard",
            "/ui/home/overview",
            "executive.overview",
            "backend/app/services/executive_service.py",
            "frontend/src/features/executive-dashboard/components/OverviewSection.tsx",
            "tests/test_executive_dashboard_endpoints.py",
            "tests/golden_samples/GS-EXEC-OVERVIEW-A",
            "analytical overlay",
            "PAGE-EXEC-OVERVIEW-001",
        ),
        (
            "executive-summary",
            "/dashboard",
            "/ui/home/summary",
            "executive.summary",
            "backend/app/services/executive_service.py",
            "frontend/src/features/executive-dashboard/components/SummarySection.tsx",
            "tests/test_executive_service_contract.py",
            "tests/golden_samples/GS-EXEC-SUMMARY-A",
            "narrative-only",
            "PAGE-EXEC-SUMMARY-001",
        ),
        (
            "executive-pnl-attribution",
            "/dashboard",
            "/ui/pnl/attribution",
            "executive.pnl-attribution",
            "backend/app/services/executive_service.py",
            "frontend/src/features/executive-dashboard/components/PnlAttributionSection.tsx",
            "tests/test_executive_dashboard_endpoints.py",
            "tests/golden_samples/GS-EXEC-PNL-ATTR-A",
            "analytical overlay",
            "PAGE-EXEC-PNL-ATTR-001",
        ),
        (
            "pnl-attribution",
            "/pnl-attribution",
            "/api/pnl-attribution/volume-rate",
            "VolumeRateAttributionPayload",
            "backend/app/services/pnl_attribution_service.py",
            "frontend/src/features/pnl-attribution/pages/PnlAttributionPage.tsx",
            "tests/test_pnl_attribution_workbench_contract.py",
            "NO_DEDICATED_GOLDEN_SAMPLE",
            "formal PnL overview",
            "/pnl-attribution",
        ),
        (
            "operations-analysis",
            "/operations-analysis",
            "/ui/pnl/product-category",
            "GAP-OPS-MACRO-FX",
            "backend/app/services/product_category_pnl_service.py",
            "frontend/src/features/workbench/pages/OperationsAnalysisPage.tsx",
            "frontend/src/test/OperationsAnalysisPage.test.tsx",
            "tests/golden_samples/GS-PROD-CAT-PNL-A",
            "temporary-exception",
            "PAGE-OPS-001",
        ),
        (
            "balance-movement-analysis",
            "/balance-movement-analysis",
            "/ui/balance-movement-analysis",
            "AccountingAssetMovementPayload",
            "backend/app/services/accounting_asset_movement_service.py",
            "frontend/src/features/balance-movement-analysis/pages/BalanceMovementAnalysisPage.tsx",
            "tests/test_accounting_asset_movement_api.py",
            "NO_DEDICATED_GOLDEN_SAMPLE",
            "formal balance truth",
            "PAGE-BAL-MOVE-001",
        ),
        (
            "liability-analytics",
            "/liability-analytics",
            "/api/risk/buckets",
            "liability_analytics.risk_buckets",
            "backend/app/services/liability_analytics_service.py",
            "frontend/src/features/liability-analytics/pages/LiabilityAnalyticsPage.tsx",
            "tests/test_liability_analytics_api.py",
            "NO_DEDICATED_GOLDEN_SAMPLE",
            "mixed-source",
            "/liability-analytics",
        ),
    ],
)
def test_metric_contracts_mcp_exposes_seeded_page_trace_bundles(
    page_slug: str,
    frontend_route: str,
    primary_api: str,
    truth_marker: str,
    backend_touchpoint: str,
    frontend_touchpoint: str,
    test_touchpoint: str,
    golden_sample: str,
    guardrail_marker: str,
    alias: str,
) -> None:
    server = McpProcess("metric-contracts")
    try:
        server.request("initialize")
        server.notify("notifications/initialized")

        tools = server.request("tools/list")["tools"]
        assert any(tool["name"] == "get_page_trace_bundle" for tool in tools)

        result = server.request(
            "tools/call",
            {"name": "get_page_trace_bundle", "arguments": {"page_slug": page_slug}},
        )
        payload = json.loads(result["content"][0]["text"])

        assert payload["page_slug"] == page_slug
        assert payload["frontend_route"] == frontend_route
        assert payload["primary_api"] == primary_api
        assert any(truth_marker in item for item in payload["truth_chain"])
        assert backend_touchpoint in payload["backend_touchpoints"]
        assert frontend_touchpoint in payload["frontend_touchpoints"]
        assert test_touchpoint in payload["test_touchpoints"]
        if golden_sample == "NO_DEDICATED_GOLDEN_SAMPLE":
            assert payload["golden_samples"] == []
            assert any("No dedicated golden sample" in item for item in payload["verification_focus"])
        else:
            assert golden_sample in payload["golden_samples"]
            assert all(str(sample).startswith("tests/golden_samples/") for sample in payload["golden_samples"])
        assert payload["contract_docs"]
        assert payload["supporting_apis"]
        assert payload["verification_focus"]
        assert payload["guardrails"]
        assert any(guardrail_marker in guardrail for guardrail in payload["guardrails"])

        alias_result = server.request(
            "tools/call",
            {"name": "get_page_trace_bundle", "arguments": {"page_slug": alias}},
        )
        alias_payload = json.loads(alias_result["content"][0]["text"])
        assert alias_payload["page_slug"] == page_slug
    finally:
        server.close()


def test_liability_analytics_trace_bundle_preserves_mixed_source_boundaries() -> None:
    server = McpProcess("metric-contracts")
    try:
        server.request("initialize")
        server.notify("notifications/initialized")

        for alias in (
            "liability-analytics",
            "/liability-analytics",
            "PAGE-LIAB-ANALYTICS-001",
            "/api/risk/buckets",
        ):
            result = server.request(
                "tools/call",
                {"name": "get_page_trace_bundle", "arguments": {"page_slug": alias}},
            )
            payload = json.loads(result["content"][0]["text"])
            assert payload["page_slug"] == "liability-analytics"

        assert payload["page_id"] == "PAGE-LIAB-ANALYTICS-001"
        assert payload["primary_api"] == "/api/risk/buckets"
        assert "/api/analysis/yield_metrics" in payload["supporting_apis"]
        assert "/api/analysis/liabilities/counterparty" in payload["supporting_apis"]
        assert "/api/liabilities/monthly" in payload["supporting_apis"]
        assert "/ui/liability/business-context" in payload["supporting_apis"]
        assert payload["golden_samples"] == []
        assert any("MTR-LIAB-001" in item for item in payload["truth_chain"])
        assert any("MTR-LIAB-007" in item for item in payload["truth_chain"])
        assert any("liability_analytics.risk_buckets" in item for item in payload["truth_chain"])
        assert any("liability_analytics_compat" in item for item in payload["truth_chain"])
        assert any("mixed-source" in item for item in payload["guardrails"])
        assert any("compatibility" in item for item in payload["guardrails"])
        assert any("formal balance" in item for item in payload["guardrails"])
    finally:
        server.close()


def test_formal_pnl_trace_bundle_preserves_formal_total_boundaries() -> None:
    server = McpProcess("metric-contracts")
    try:
        server.request("initialize")
        server.notify("notifications/initialized")

        for alias in ("pnl", "/pnl", "PAGE-PNL-001", "/api/pnl/overview"):
            result = server.request(
                "tools/call",
                {"name": "get_page_trace_bundle", "arguments": {"page_slug": alias}},
            )
            payload = json.loads(result["content"][0]["text"])
            assert payload["page_slug"] == "pnl"

        assert payload["page_id"] == "PAGE-PNL-001"
        assert payload["primary_api"] == "/api/pnl/overview"
        assert "/api/pnl/dates" in payload["supporting_apis"]
        assert "/api/pnl/data" in payload["supporting_apis"]
        assert "tests/golden_samples/GS-PNL-OVERVIEW-A" in payload["golden_samples"]
        assert "tests/golden_samples/GS-PNL-DATA-A" in payload["golden_samples"]
        assert any("MTR-PNL-001" in item for item in payload["truth_chain"])
        assert any("MTR-PNL-104" in item for item in payload["truth_chain"])
        assert any("pnl_overview_envelope" in item for item in payload["truth_chain"])
        assert any("PnlDataPayload" in item for item in payload["truth_chain"])
        assert any("formal PnL truth" in item for item in payload["guardrails"])
        assert any("standardized total" in item for item in payload["guardrails"])
        assert any("executive analytical overlay" in item for item in payload["guardrails"])
    finally:
        server.close()


def test_ledger_pnl_trace_bundle_preserves_candidate_source_contract_boundaries() -> None:
    server = McpProcess("metric-contracts")
    try:
        server.request("initialize")
        server.notify("notifications/initialized")

        for alias in (
            "ledger-pnl",
            "/ledger-pnl",
            "PAGE-LEDGER-PNL-001",
            "/api/ledger-pnl/summary",
            "/api/ledger-pnl/formal-financial-indicators",
        ):
            result = server.request(
                "tools/call",
                {"name": "get_page_trace_bundle", "arguments": {"page_slug": alias}},
            )
            payload = json.loads(result["content"][0]["text"])
            assert payload["page_slug"] == "ledger-pnl"

        assert payload["page_id"] == "PAGE-LEDGER-PNL-001"
        assert payload["primary_api"] == "/api/ledger-pnl/summary"
        assert "/api/ledger-pnl/dates" in payload["supporting_apis"]
        assert "/api/ledger-pnl/data" in payload["supporting_apis"]
        assert "/api/ledger-pnl/formal-financial-indicators" in payload["supporting_apis"]
        assert payload["golden_samples"] == []
        assert any("MTR-LPN-001" in item for item in payload["truth_chain"])
        assert any("MTR-LPN-003" in item for item in payload["truth_chain"])
        assert any("ledger_pnl.formal_financial_indicator_source_contract" in item for item in payload["truth_chain"])
        assert any("GS-LEDGER-PNL-FIN-IND-202603-B" in item for item in payload["truth_chain"])
        assert any("pending_confirmation=true" in item for item in payload["guardrails"])
        assert any("formal PnL" in item for item in payload["guardrails"])
        assert any("formal financial indicator truth" in item for item in payload["guardrails"])
        assert any("zero" in item for item in payload["guardrails"])
    finally:
        server.close()


def test_executive_overview_trace_bundle_preserves_analytical_overlay_boundaries() -> None:
    server = McpProcess("metric-contracts")
    try:
        server.request("initialize")
        server.notify("notifications/initialized")

        for alias in (
            "executive-overview",
            "/ui/home/overview",
            "PAGE-EXEC-OVERVIEW-001",
        ):
            result = server.request(
                "tools/call",
                {"name": "get_page_trace_bundle", "arguments": {"page_slug": alias}},
            )
            payload = json.loads(result["content"][0]["text"])
            assert payload["page_slug"] == "executive-overview"

        assert payload["page_id"] == "PAGE-EXEC-OVERVIEW-001"
        assert payload["primary_api"] == "/ui/home/overview"
        assert "tests/golden_samples/GS-EXEC-OVERVIEW-A" in payload["golden_samples"]
        assert any("MTR-EXEC-001" in item for item in payload["truth_chain"])
        assert any("MTR-EXEC-004" in item for item in payload["truth_chain"])
        assert any("executive.overview" in item for item in payload["truth_chain"])
        assert any("caliber_label" in item for item in payload["truth_chain"])
        assert any("analytical overlay" in item for item in payload["guardrails"])
        assert any("formal source-of-truth" in item for item in payload["guardrails"])
        assert any("silent downgrade" in item for item in payload["guardrails"])
    finally:
        server.close()


def test_executive_summary_trace_bundle_preserves_narrative_contract_boundaries() -> None:
    server = McpProcess("metric-contracts")
    try:
        server.request("initialize")
        server.notify("notifications/initialized")

        for alias in (
            "executive-summary",
            "/ui/home/summary",
            "PAGE-EXEC-SUMMARY-001",
        ):
            result = server.request(
                "tools/call",
                {"name": "get_page_trace_bundle", "arguments": {"page_slug": alias}},
            )
            payload = json.loads(result["content"][0]["text"])
            assert payload["page_slug"] == "executive-summary"

        assert payload["page_id"] == "PAGE-EXEC-SUMMARY-001"
        assert payload["primary_api"] == "/ui/home/summary"
        assert "/ui/home/overview" in payload["supporting_apis"]
        assert "tests/golden_samples/GS-EXEC-SUMMARY-A" in payload["golden_samples"]
        assert any("GS-EXEC-SUMMARY-A" in item for item in payload["truth_chain"])
        assert any("SummaryPayload" in item for item in payload["truth_chain"])
        assert any("executive.summary" in item for item in payload["truth_chain"])
        assert any("narrative-only" in item for item in payload["truth_chain"])
        assert any("title" in item and "points.length" in item for item in payload["truth_chain"])
        assert any("metric dictionary" in item for item in payload["guardrails"])
        assert any("narrative" in item and "formal" in item for item in payload["guardrails"])
        assert any("upstream metric" in item for item in payload["guardrails"])
        assert any("report_date" in item for item in payload["verification_focus"])
    finally:
        server.close()


def test_executive_pnl_attribution_trace_bundle_preserves_overlay_boundaries() -> None:
    server = McpProcess("metric-contracts")
    try:
        server.request("initialize")
        server.notify("notifications/initialized")

        for alias in (
            "executive-pnl-attribution",
            "/ui/pnl/attribution",
            "PAGE-EXEC-PNL-ATTR-001",
        ):
            result = server.request(
                "tools/call",
                {"name": "get_page_trace_bundle", "arguments": {"page_slug": alias}},
            )
            payload = json.loads(result["content"][0]["text"])
            assert payload["page_slug"] == "executive-pnl-attribution"

        assert payload["page_id"] == "PAGE-EXEC-PNL-ATTR-001"
        assert payload["primary_api"] == "/ui/pnl/attribution"
        assert "tests/golden_samples/GS-EXEC-PNL-ATTR-A" in payload["golden_samples"]
        assert any("MTR-EXEC-101" in item for item in payload["truth_chain"])
        assert any("MTR-EXEC-106" in item for item in payload["truth_chain"])
        assert any("executive.pnl-attribution" in item for item in payload["truth_chain"])
        assert any("analytical overlay" in item for item in payload["guardrails"])
        assert any("formal bridge" in item for item in payload["guardrails"])
        assert any("formal PnL truth" in item for item in payload["guardrails"])
    finally:
        server.close()


def test_pnl_attribution_workbench_trace_bundle_preserves_workbench_boundaries() -> None:
    server = McpProcess("metric-contracts")
    try:
        server.request("initialize")
        server.notify("notifications/initialized")

        for alias in (
            "pnl-attribution",
            "/pnl-attribution",
            "PAGE-PNL-ATTR-WB-001",
            "/api/pnl-attribution/volume-rate",
        ):
            result = server.request(
                "tools/call",
                {"name": "get_page_trace_bundle", "arguments": {"page_slug": alias}},
            )
            payload = json.loads(result["content"][0]["text"])
            assert payload["page_slug"] == "pnl-attribution"

        assert payload["page_id"] == "PAGE-PNL-ATTR-WB-001"
        assert payload["primary_api"] == "/api/pnl-attribution/volume-rate"
        assert "/api/pnl-attribution/tpl-market" in payload["supporting_apis"]
        assert "/api/pnl-attribution/composition" in payload["supporting_apis"]
        assert "/api/pnl-attribution/advanced/summary" in payload["supporting_apis"]
        assert "/api/pnl-attribution/campisi/four-effects" in payload["supporting_apis"]
        assert payload["golden_samples"] == []
        assert any("MTR-PAT-001" in item for item in payload["truth_chain"])
        assert any("MTR-PAT-304" in item for item in payload["truth_chain"])
        assert any("VolumeRateAttributionPayload" in item for item in payload["truth_chain"])
        assert any("Campisi" in item for item in payload["truth_chain"])
        assert any("formal PnL overview" in item for item in payload["guardrails"])
        assert any("executive analytical overlay" in item for item in payload["guardrails"])
        assert any("front" in item for item in payload["guardrails"])
    finally:
        server.close()


def test_operations_analysis_trace_bundle_preserves_mixed_source_boundaries() -> None:
    server = McpProcess("metric-contracts")
    try:
        server.request("initialize")
        server.notify("notifications/initialized")

        for alias in (
            "operations-analysis",
            "/operations-analysis",
            "PAGE-OPS-001",
            "/ui/pnl/product-category",
        ):
            result = server.request(
                "tools/call",
                {"name": "get_page_trace_bundle", "arguments": {"page_slug": alias}},
            )
            payload = json.loads(result["content"][0]["text"])
            assert payload["page_slug"] == "operations-analysis"

        assert payload["page_id"] == "PAGE-OPS-001"
        assert payload["primary_api"] == "/ui/pnl/product-category"
        assert "/ui/pnl/product-category/dates" in payload["supporting_apis"]
        assert "/ui/balance-analysis/overview" in payload["supporting_apis"]
        assert "/ui/preview/source-foundation" in payload["supporting_apis"]
        assert "/ui/macro/choice-series/latest" in payload["supporting_apis"]
        assert "/ui/market-data/fx/formal-status" in payload["supporting_apis"]
        assert "/ui/news/choice-events/latest" in payload["supporting_apis"]
        assert "tests/golden_samples/GS-PROD-CAT-PNL-A" in payload["golden_samples"]
        assert "tests/golden_samples/GS-BAL-OVERVIEW-A" in payload["golden_samples"]
        assert any("MTR-PCP-001" in item for item in payload["truth_chain"])
        assert any("MTR-PCP-003" in item for item in payload["truth_chain"])
        assert any("GAP-OPS-MACRO-FX" in item for item in payload["truth_chain"])
        assert any("supplemental topic-entry" in item for item in payload["guardrails"])
        assert any("temporary-exception" in item for item in payload["guardrails"])
        assert any("Do not create or promote MTR-OPS-* metrics" in item for item in payload["guardrails"])
    finally:
        server.close()


def test_balance_movement_trace_bundle_preserves_movement_explanation_boundaries() -> None:
    server = McpProcess("metric-contracts")
    try:
        server.request("initialize")
        server.notify("notifications/initialized")

        for alias in (
            "balance-movement-analysis",
            "/balance-movement-analysis",
            "PAGE-BAL-MOVE-001",
            "/ui/balance-movement-analysis",
        ):
            result = server.request(
                "tools/call",
                {"name": "get_page_trace_bundle", "arguments": {"page_slug": alias}},
            )
            payload = json.loads(result["content"][0]["text"])
            assert payload["page_slug"] == "balance-movement-analysis"

        assert payload["page_id"] == "PAGE-BAL-MOVE-001"
        assert payload["primary_api"] == "/ui/balance-movement-analysis"
        assert "/ui/balance-movement-analysis/dates" in payload["supporting_apis"]
        assert "/ui/balance-movement-analysis/refresh" in payload["supporting_apis"]
        assert payload["golden_samples"] == []
        assert any("MTR-BMV-001" in item for item in payload["truth_chain"])
        assert any("MTR-BMV-004" in item for item in payload["truth_chain"])
        assert any("AccountingAssetMovementPayload" in item for item in payload["truth_chain"])
        assert any("rv_accounting_asset_movement_v2" in item for item in payload["truth_chain"])
        assert any("formal balance truth" in item for item in payload["guardrails"])
        assert any("selected report dates" in item for item in payload["guardrails"])
        assert any("demo rows" in item for item in payload["guardrails"])
    finally:
        server.close()


def test_balance_analysis_trace_bundle_preserves_formal_workbook_boundaries() -> None:
    server = McpProcess("metric-contracts")
    try:
        server.request("initialize")
        server.notify("notifications/initialized")

        for alias in (
            "balance-analysis",
            "/balance-analysis",
            "PAGE-BALANCE-001",
            "/ui/balance-analysis/overview",
        ):
            result = server.request(
                "tools/call",
                {"name": "get_page_trace_bundle", "arguments": {"page_slug": alias}},
            )
            payload = json.loads(result["content"][0]["text"])
            assert payload["page_slug"] == "balance-analysis"

        assert payload["page_id"] == "PAGE-BALANCE-001"
        assert payload["primary_api"] == "/ui/balance-analysis/overview"
        assert "/ui/balance-analysis/dates" in payload["supporting_apis"]
        assert "/ui/balance-analysis" in payload["supporting_apis"]
        assert "/ui/balance-analysis/workbook" in payload["supporting_apis"]
        assert "/ui/balance-analysis/summary" in payload["supporting_apis"]
        assert "tests/golden_samples/GS-BAL-OVERVIEW-A" in payload["golden_samples"]
        assert "tests/golden_samples/GS-BAL-WORKBOOK-A" in payload["golden_samples"]
        assert any("MTR-BAL-001" in item for item in payload["truth_chain"])
        assert any("MTR-BAL-203" in item for item in payload["truth_chain"])
        assert any("balance_analysis_overview_envelope" in item for item in payload["truth_chain"])
        assert any("BalanceAnalysisWorkbookPayload" in item for item in payload["truth_chain"])
        assert any("advanced_attribution" in item for item in payload["guardrails"])
        assert any("formal balance truth" in item for item in payload["guardrails"])
        assert any("frontend" in item for item in payload["guardrails"])
    finally:
        server.close()


def test_pnl_bridge_trace_bundle_preserves_warning_and_source_boundaries() -> None:
    server = McpProcess("metric-contracts")
    try:
        server.request("initialize")
        server.notify("notifications/initialized")

        for alias in ("pnl-bridge", "/pnl-bridge", "PAGE-BRIDGE-001", "/api/pnl/bridge"):
            result = server.request(
                "tools/call",
                {"name": "get_page_trace_bundle", "arguments": {"page_slug": alias}},
            )
            payload = json.loads(result["content"][0]["text"])
            assert payload["page_slug"] == "pnl-bridge"

        assert payload["page_id"] == "PAGE-BRIDGE-001"
        assert payload["primary_api"] == "/api/pnl/bridge"
        assert "/api/pnl/dates" in payload["supporting_apis"]
        assert "/api/pnl/refresh" in payload["supporting_apis"]
        assert "tests/golden_samples/GS-BRIDGE-A" in payload["golden_samples"]
        assert "tests/golden_samples/GS-BRIDGE-WARN-B" in payload["golden_samples"]
        assert any("MTR-BRG-001" in item for item in payload["truth_chain"])
        assert any("MTR-BRG-105" in item for item in payload["truth_chain"])
        assert any("PnlBridgePayload" in item for item in payload["truth_chain"])
        assert any("pnl_bridge_envelope" in item for item in payload["truth_chain"])
        assert any("bridge warnings" in item for item in payload["guardrails"])
        assert any("future-only" in item for item in payload["guardrails"])
        assert any("frontend" in item for item in payload["guardrails"])
    finally:
        server.close()


def test_dashboard_home_trace_bundle_preserves_mixed_source_boundaries() -> None:
    server = McpProcess("metric-contracts")
    try:
        server.request("initialize")
        server.notify("notifications/initialized")

        for alias in ("dashboard-home", "/", "/dashboard"):
            result = server.request(
                "tools/call",
                {"name": "get_page_trace_bundle", "arguments": {"page_slug": alias}},
            )
            payload = json.loads(result["content"][0]["text"])
            assert payload["page_slug"] == "dashboard-home"

        supporting_apis = set(payload["supporting_apis"])
        assert "/ui/home/snapshot" == payload["primary_api"]
        assert "/ui/risk/overview" not in supporting_apis
        assert "/ui/home/alerts" not in supporting_apis
        assert "/ui/home/contribution" not in supporting_apis
        assert any("analytical/mixed-source" in item for item in payload["guardrails"])
        assert any("not a full-page formal sample" in item for item in payload["guardrails"])
    finally:
        server.close()


def test_risk_tensor_trace_bundle_preserves_formal_warning_boundaries() -> None:
    server = McpProcess("metric-contracts")
    try:
        server.request("initialize")
        server.notify("notifications/initialized")

        for alias in ("risk-tensor", "/risk-tensor", "PAGE-RISK-001"):
            result = server.request(
                "tools/call",
                {"name": "get_page_trace_bundle", "arguments": {"page_slug": alias}},
            )
            payload = json.loads(result["content"][0]["text"])
            assert payload["page_slug"] == "risk-tensor"

        assert payload["page_id"] == "PAGE-RISK-001"
        assert payload["primary_api"] == "/api/risk/tensor"
        assert "/api/risk/tensor/dates" in payload["supporting_apis"]
        assert "/ui/risk/overview" not in payload["supporting_apis"]
        assert "tests/golden_samples/GS-RISK-A" in payload["golden_samples"]
        assert "tests/golden_samples/GS-RISK-WARN-B" in payload["golden_samples"]
        assert any("MTR-RSK-001" in item for item in payload["truth_chain"])
        assert any("fact_formal_risk_tensor_daily" in item for item in payload["truth_chain"])
        assert any("warning quality" in item for item in payload["guardrails"])
        assert any("duration denominator" in item for item in payload["guardrails"])
    finally:
        server.close()


def test_bond_dashboard_trace_bundle_preserves_candidate_metric_boundaries() -> None:
    server = McpProcess("metric-contracts")
    try:
        server.request("initialize")
        server.notify("notifications/initialized")

        for alias in (
            "bond-dashboard",
            "/bond-dashboard",
            "PAGE-BOND-001",
            "/api/bond-dashboard/headline-kpis",
            "/api/bond-dashboard/risk-indicators",
        ):
            result = server.request(
                "tools/call",
                {"name": "get_page_trace_bundle", "arguments": {"page_slug": alias}},
            )
            payload = json.loads(result["content"][0]["text"])
            assert payload["page_slug"] == "bond-dashboard"

        assert payload["page_id"] == "PAGE-BOND-001"
        assert payload["primary_api"] == "/api/bond-dashboard/headline-kpis"
        assert "/api/bond-dashboard/dates" in payload["supporting_apis"]
        assert "/api/bond-dashboard/risk-indicators" in payload["supporting_apis"]
        assert "tests/golden_samples/GS-BOND-HEADLINE-A" in payload["golden_samples"]
        assert any("MTR-BOND-001" in item for item in payload["truth_chain"])
        assert any("MTR-BOND-004" in item for item in payload["truth_chain"])
        assert any("GAP-BOND-DASH-HL" in item for item in payload["truth_chain"])
        assert any("GAP-BOND-DASH-RISK" in item for item in payload["truth_chain"])
        assert any("BondDashboardHeadlinePayload" in item for item in payload["truth_chain"])
        assert any("source_surface=\"bond_analytics\"" in item for item in payload["truth_chain"])
        assert any("pending_confirmation=true" in item for item in payload["guardrails"])
        assert any("GS-RISK-A" in item for item in payload["guardrails"])
        assert any("MTR-BAL" in item for item in payload["guardrails"])
        assert any("frontend" in item for item in payload["guardrails"])
    finally:
        server.close()


def test_positions_trace_bundle_preserves_list_candidate_and_dual_date_boundaries() -> None:
    server = McpProcess("metric-contracts")
    try:
        server.request("initialize")
        server.notify("notifications/initialized")

        for alias in (
            "positions",
            "/positions",
            "PAGE-POS-001",
            "/api/positions/bonds",
            "/api/positions/interbank",
        ):
            result = server.request(
                "tools/call",
                {"name": "get_page_trace_bundle", "arguments": {"page_slug": alias}},
            )
            payload = json.loads(result["content"][0]["text"])
            assert payload["page_slug"] == "positions"

        assert payload["page_id"] == "PAGE-POS-001"
        assert payload["primary_api"] == "/api/positions/bonds"
        assert "/api/positions/bonds/sub_types" in payload["supporting_apis"]
        assert "/api/positions/interbank/product_types" in payload["supporting_apis"]
        assert "/api/positions/counterparty/bonds" in payload["supporting_apis"]
        assert "/api/positions/stats/rating" in payload["supporting_apis"]
        assert "/api/positions/customer/details" in payload["supporting_apis"]
        assert "GET /ui/balance-analysis/dates" in payload["truth_chain"]
        assert payload["golden_samples"] == []
        assert any("MTR-POS-001" in item for item in payload["truth_chain"])
        assert any("MTR-POS-002" in item for item in payload["truth_chain"])
        assert any("GAP-POS-LIST" in item for item in payload["truth_chain"])
        assert any("BondPositionsPageResponse" in item for item in payload["truth_chain"])
        assert any("InterbankPositionsPageResponse" in item for item in payload["truth_chain"])
        assert any("pending_confirmation=true" in item for item in payload["guardrails"])
        assert any("bound_sample_id=none" in item for item in payload["guardrails"])
        assert any("balance-analysis dates" in item for item in payload["guardrails"])
        assert any("formal PnL" in item for item in payload["guardrails"])
        assert any("frontend" in item for item in payload["guardrails"])
    finally:
        server.close()


def test_market_data_trace_bundle_preserves_mixed_source_candidate_boundaries() -> None:
    server = McpProcess("metric-contracts")
    try:
        server.request("initialize")
        server.notify("notifications/initialized")

        for alias in (
            "market-data",
            "/market-data",
            "PAGE-MKT-001",
            "/ui/preview/macro-foundation",
            "/ui/market-data/rates",
        ):
            result = server.request(
                "tools/call",
                {"name": "get_page_trace_bundle", "arguments": {"page_slug": alias}},
            )
            payload = json.loads(result["content"][0]["text"])
            assert payload["page_slug"] == "market-data"

        assert payload["page_id"] == "PAGE-MKT-001"
        assert payload["primary_api"] == "/ui/preview/macro-foundation"
        assert "/ui/market-data/rates" in payload["supporting_apis"]
        assert "/ui/market-data/fx/formal-status" in payload["supporting_apis"]
        assert "/ui/market-data/fx/analytical" in payload["supporting_apis"]
        assert "/ui/market-data/ncd-funding-proxy" in payload["supporting_apis"]
        assert "/ui/market-data/livermore" in payload["supporting_apis"]
        assert payload["golden_samples"] == []
        assert any("MTR-MKT-001" in item for item in payload["truth_chain"])
        assert any("GAP-MKT-DATA" in item for item in payload["truth_chain"])
        assert any("formal rates fragment" in item for item in payload["truth_chain"])
        assert any("ncd-funding-proxy" in item for item in payload["truth_chain"])
        assert any("Livermore" in item for item in payload["truth_chain"])
        assert any("source-pending" in item for item in payload["truth_chain"])
        assert any("No dedicated golden sample" in item for item in payload["verification_focus"])
        assert any("full-page formal truth" in item for item in payload["guardrails"])
        assert any("static demo" in item for item in payload["guardrails"])
        assert any("NCD" in item and "proxy" in item for item in payload["guardrails"])
        assert any("Livermore" in item and "risk_exit" in item for item in payload["guardrails"])
        assert any("MTR-" in item and "promote" in item for item in payload["guardrails"])
    finally:
        server.close()


def test_macro_toolkit_trace_bundle_preserves_tooling_non_metric_boundaries() -> None:
    server = McpProcess("metric-contracts")
    try:
        server.request("initialize")
        server.notify("notifications/initialized")

        for alias in (
            "macro-toolkit",
            "/macro-toolkit",
            "PAGE-MACRO-TOOLKIT-001",
            "/ui/macro/toolkit/analysis",
            "/ui/macro/toolkit/scripts",
        ):
            result = server.request(
                "tools/call",
                {"name": "get_page_trace_bundle", "arguments": {"page_slug": alias}},
            )
            payload = json.loads(result["content"][0]["text"])
            assert payload["page_slug"] == "macro-toolkit"

        assert payload["page_id"] == "PAGE-MACRO-TOOLKIT-001"
        assert payload["primary_api"] == "/ui/macro/toolkit/analysis"
        assert "/ui/macro/toolkit/analysis/strategy-summaries" in payload["supporting_apis"]
        assert "/ui/macro/toolkit/scripts" in payload["supporting_apis"]
        assert "POST /ui/macro/toolkit/scripts/{name}/run" in payload["supporting_apis"]
        assert "POST /ui/macro/toolkit/cffex-member-rank/refresh" in payload["supporting_apis"]
        assert "POST /ui/macro/toolkit/choice-stock/refresh" in payload["supporting_apis"]
        assert "GET /ui/macro/toolkit/choice-stock/refresh-status" in payload["supporting_apis"]
        assert payload["golden_samples"] == []
        assert any("PAGE-MACRO-TOOLKIT-001" in item for item in payload["truth_chain"])
        assert any("macro_toolkit.analysis" in item for item in payload["truth_chain"])
        assert any("macro_toolkit.scripts" in item for item in payload["truth_chain"])
        assert any("MTR-MACRO" in item and "no" in item.lower() for item in payload["truth_chain"])
        assert any("source/version/run_id" in item for item in payload["truth_chain"])
        assert any("MacroToolkitContractBoundary" in item for item in payload["truth_chain"])
        assert any("operation/script outputs" in item for item in payload["truth_chain"])
        assert any("No dedicated golden sample" in item for item in payload["verification_focus"])
        assert any("formal metric truth" in item for item in payload["guardrails"])
        assert any("investment" in item and "trade signal" in item for item in payload["guardrails"])
        assert any("static demo" in item for item in payload["guardrails"])
        assert any("fallback" in item and "stale" in item and "source gaps" in item for item in payload["guardrails"])
        assert any("frontend" in item and "recompute" in item for item in payload["guardrails"])
    finally:
        server.close()


def test_macro_observation_trace_bundle_preserves_readonly_non_metric_boundaries() -> None:
    server = McpProcess("metric-contracts")
    try:
        server.request("initialize")
        server.notify("notifications/initialized")

        for alias in (
            "macro-observation",
            "/macro-observation",
            "PAGE-MACRO-OBS-001",
        ):
            result = server.request(
                "tools/call",
                {"name": "get_page_trace_bundle", "arguments": {"page_slug": alias}},
            )
            payload = json.loads(result["content"][0]["text"])
            assert payload["page_slug"] == "macro-observation"

        assert payload["page_id"] == "PAGE-MACRO-OBS-001"
        assert payload["primary_api"] == "/ui/macro/toolkit/analysis"
        assert payload["supporting_apis"] == ["/ui/macro/toolkit/analysis/strategy-summaries"]
        assert payload["golden_samples"] == []
        assert any("PAGE-MACRO-OBS-001" in item for item in payload["truth_chain"])
        assert any("read-only macro observation" in item for item in payload["truth_chain"])
        assert any("macro-observation-readonly-boundary" in item for item in payload["truth_chain"])
        assert any("MTR-MACRO" in item and "no" in item.lower() for item in payload["truth_chain"])
        assert any("No dedicated golden sample" in item for item in payload["verification_focus"])
        assert any("script" in item and "refresh" in item for item in payload["guardrails"])
        assert any("MTR" in item and "promote" in item for item in payload["guardrails"])
        assert any("read-only boundary" in item for item in payload["guardrails"])
        assert all("scripts" not in api for api in payload["supporting_apis"])
        assert all("refresh" not in api for api in payload["supporting_apis"])
    finally:
        server.close()


def test_agent_trace_bundle_preserves_readonly_formal_use_boundaries() -> None:
    server = McpProcess("metric-contracts")
    try:
        server.request("initialize")
        server.notify("notifications/initialized")

        for alias in (
            "agent",
            "/agent",
            "PAGE-AGENT-001",
            "POST /api/agent/runs",
            "POST /api/agent/query",
        ):
            result = server.request(
                "tools/call",
                {"name": "get_page_trace_bundle", "arguments": {"page_slug": alias}},
            )
            payload = json.loads(result["content"][0]["text"])
            assert payload["page_slug"] == "agent"

        assert payload["page_id"] == "PAGE-AGENT-001"
        assert payload["primary_api"] == "POST /api/agent/runs"
        assert "GET /api/agent/runs/{run_id}" in payload["supporting_apis"]
        assert "POST /api/agent/query" in payload["supporting_apis"]
        assert payload["golden_samples"] == []
        assert any("AgentEnvelope" in item for item in payload["truth_chain"])
        assert any("formal_use_allowed" in item for item in payload["truth_chain"])
        assert any("read-only" in item for item in payload["truth_chain"])
        assert any("No dedicated golden sample" in item for item in payload["verification_focus"])
        assert any("formal financial result" in item for item in payload["guardrails"])
        assert any("mutating" in item for item in payload["guardrails"])
        assert any("source lineage" in item for item in payload["guardrails"])
    finally:
        server.close()


def test_cube_query_trace_bundle_preserves_query_tool_non_metric_boundaries() -> None:
    server = McpProcess("metric-contracts")
    try:
        server.request("initialize")
        server.notify("notifications/initialized")

        for alias in (
            "cube-query",
            "/cube-query",
            "PAGE-CUBE-QUERY-001",
            "POST /api/cube/query",
            "GET /api/cube/dimensions/{fact_table}",
        ):
            result = server.request(
                "tools/call",
                {"name": "get_page_trace_bundle", "arguments": {"page_slug": alias}},
            )
            payload = json.loads(result["content"][0]["text"])
            assert payload["page_slug"] == "cube-query"

        assert payload["page_id"] == "PAGE-CUBE-QUERY-001"
        assert payload["primary_api"] == "POST /api/cube/query"
        assert "GET /api/cube/dimensions/{fact_table}" in payload["supporting_apis"]
        assert payload["golden_samples"] == []
        assert any("CubeQueryResult" in item for item in payload["truth_chain"])
        assert any("candidate query surface" in item for item in payload["truth_chain"])
        assert any("no standalone MTR" in item for item in payload["truth_chain"])
        assert any("No dedicated golden sample" in item for item in payload["verification_focus"])
        assert any("new page-level KPI" in item for item in payload["guardrails"])
        assert any("fail closed" in item for item in payload["guardrails"])
        assert any("frontend" in item and "reinterpret" in item for item in payload["guardrails"])
    finally:
        server.close()


def test_module_home_trace_bundles_preserve_downstream_truth_boundaries() -> None:
    server = McpProcess("metric-contracts")
    try:
        server.request("initialize")
        server.notify("notifications/initialized")

        cases = [
            (
                "portfolio-home",
                "PAGE-PORTFOLIO-HOME-001",
                "/portfolio",
                "frontend aggregation: module-home/portfolio",
                ["/balance-analysis", "/bond-dashboard", "/positions", "/pnl-attribution"],
                "standalone formal metric page",
            ),
            (
                "market-home",
                "PAGE-MARKET-HOME-001",
                "/market-overview",
                "frontend aggregation: module-home/market",
                ["/market-data", "/macro-toolkit", "/stock-analysis", "/news-events"],
                "formal market data claims",
            ),
            (
                "risk-home",
                "PAGE-RISK-HOME-001",
                "/risk-overview",
                "frontend aggregation: module-home/risk",
                ["/risk-tensor", "/concentration-monitor", "/cashflow-projection"],
                "PAGE-RISK-001 formal risk truth",
            ),
            (
                "performance-home",
                "PAGE-PERFORMANCE-HOME-001",
                "/performance",
                "frontend aggregation: module-home/performance",
                ["/kpi", "/team-performance", "/pnl-by-business", "/product-category-pnl"],
                "KPI scoring",
            ),
            (
                "reports-home",
                "PAGE-REPORTS-HOME-001",
                "/reports",
                "frontend aggregation: module-home/governance",
                ["/platform-config", "/cube-query"],
                "data-quality approval",
            ),
        ]

        for page_slug, page_id, route, primary_api, downstream_pages, guardrail_marker in cases:
            for alias in (page_slug, route, page_id):
                result = server.request(
                    "tools/call",
                    {"name": "get_page_trace_bundle", "arguments": {"page_slug": alias}},
                )
                payload = json.loads(result["content"][0]["text"])
                assert payload["page_slug"] == page_slug

            assert payload["page_id"] == page_id
            assert payload["frontend_route"] == route
            assert payload["primary_api"] == primary_api
            assert payload["golden_samples"] == []
            assert any(page_id in item for item in payload["truth_chain"])
            assert any("module home" in item for item in payload["truth_chain"])
            assert any("no standalone MTR" in item for item in payload["truth_chain"])
            assert any("No dedicated golden sample" in item for item in payload["verification_focus"])
            assert any("downstream" in item for item in payload["guardrails"])
            assert any(guardrail_marker in item for item in payload["guardrails"])
            for downstream_page in downstream_pages:
                assert downstream_page in payload["supporting_apis"]
    finally:
        server.close()


def test_business_pnl_trace_bundle_preserves_page_level_analysis_boundaries() -> None:
    server = McpProcess("metric-contracts")
    try:
        server.request("initialize")
        server.notify("notifications/initialized")

        for alias in (
            "pnl-by-business",
            "/pnl-by-business",
            "PAGE-PNL-BY-BUSINESS-001",
            "/api/pnl/by-business-ytd",
            "/api/pnl/by-business-analysis",
        ):
            result = server.request(
                "tools/call",
                {"name": "get_page_trace_bundle", "arguments": {"page_slug": alias}},
            )
            payload = json.loads(result["content"][0]["text"])
            assert payload["page_slug"] == "pnl-by-business"

        assert payload["page_id"] == "PAGE-PNL-BY-BUSINESS-001"
        assert payload["frontend_route"] == "/pnl-by-business"
        assert payload["primary_api"] == "/api/pnl/by-business-ytd"
        assert payload["golden_samples"] == []
        assert "/api/pnl/by-business-monthly" in payload["supporting_apis"]
        assert "/api/pnl/by-business" in payload["supporting_apis"]
        assert "/api/pnl/by-business-analysis" in payload["supporting_apis"]
        assert "/api/adb/comparison" in payload["supporting_apis"]
        assert any("YTD/monthly" in item for item in payload["truth_chain"])
        assert any("formal reconciliation evidence only" in item for item in payload["truth_chain"])
        assert any("no newly approved MTR" in item for item in payload["truth_chain"])
        assert any(
            "Manual adjustment" in item and "official metric" in item for item in payload["guardrails"]
        )
        assert any("Product-category truth" in item for item in payload["guardrails"])
        assert any("Ledger-account PnL truth" in item for item in payload["guardrails"])
        assert not any("MTR-" in item for item in payload["supporting_apis"])
        assert not any("GS-" in item for item in payload["supporting_apis"])
    finally:
        server.close()


def test_metric_contracts_page_trace_bundle_accepts_aliases_and_rejects_unknown_pages() -> None:
    server = McpProcess("metric-contracts")
    try:
        server.request("initialize")
        server.notify("notifications/initialized")

        for alias in ("/product-category-pnl", "PAGE-PROD-CAT-PNL-001"):
            alias_result = server.request(
                "tools/call",
                {"name": "get_page_trace_bundle", "arguments": {"page_slug": alias}},
            )
            alias_payload = json.loads(alias_result["content"][0]["text"])
            assert alias_payload["page_slug"] == "product-category-pnl"

        missing_slug = server.request_error(
            "tools/call",
            {"name": "get_page_trace_bundle", "arguments": {"page_slug": ""}},
        )
        assert missing_slug["code"] == -32602
        assert "page_slug is required" in missing_slug["message"]

        unknown_slug = server.request_error(
            "tools/call",
            {"name": "get_page_trace_bundle", "arguments": {"page_slug": "unknown-page"}},
        )
        assert unknown_slug["code"] == -32602
        assert "Unknown page_slug: unknown-page" in unknown_slug["message"]
        assert "dashboard-home" in unknown_slug["message"]
        assert "product-category-pnl" in unknown_slug["message"]
        assert "risk-tensor" in unknown_slug["message"]
    finally:
        server.close()


def test_lineage_evidence_mcp_reads_governance_stream_status(tmp_path: Path) -> None:
    governance = tmp_path / "governance"
    governance.mkdir()
    (governance / "cache_manifest.jsonl").write_text(
        json.dumps({"report_date": "2026-03-31", "source_version": "sv_test"}) + "\n",
        encoding="utf-8",
    )

    server = McpProcess("lineage-evidence", env={"MOSS_GOVERNANCE_PATH": str(governance)})
    try:
        server.request("initialize")
        server.notify("notifications/initialized")

        summary = server.request("resources/read", {"uri": "moss://lineage/summary"})
        payload = json.loads(summary["contents"][0]["text"])
        assert payload["streams"]["cache_manifest"]["exists"] is True

        found = server.request(
            "tools/call",
            {"name": "find_lineage_records", "arguments": {"query": "2026-03-31", "max_results": 5}},
        )
        found_payload = json.loads(found["content"][0]["text"])
        assert found_payload["records"][0]["stream"] == "cache_manifest"
    finally:
        server.close()


def test_lineage_evidence_mcp_maps_page_risk_contract_to_risk_tensor_records(tmp_path: Path) -> None:
    governance = tmp_path / "governance"
    governance.mkdir()
    (governance / "agent_audit.jsonl").write_text(
        json.dumps(
            {
                "result_kind": "risk.tensor",
                "page_slug": "risk-tensor",
                "source_surface": "risk_tensor",
                "tables_used": ["fact_formal_risk_tensor_daily"],
                "report_date": "2026-04-30",
            }
        )
        + "\n",
        encoding="utf-8",
    )

    server = McpProcess("lineage-evidence", env={"MOSS_GOVERNANCE_PATH": str(governance)})
    try:
        server.request("initialize")
        server.notify("notifications/initialized")

        found = server.request(
            "tools/call",
            {"name": "find_lineage_records", "arguments": {"query": "PAGE-RISK-001", "max_results": 5}},
        )
        found_payload = json.loads(found["content"][0]["text"])

        assert found_payload["query"] == "PAGE-RISK-001"
        assert "risk.tensor" in found_payload["expanded_queries"]
        assert "fact_formal_risk_tensor_daily" in found_payload["expanded_queries"]
        assert found_payload["records"][0]["matched_query"] == "fact_formal_risk_tensor_daily"
        assert found_payload["records"][0]["stream"] == "agent_audit"
        assert found_payload["records"][0]["record"]["result_kind"] == "risk.tensor"
    finally:
        server.close()


def test_lineage_evidence_mcp_maps_agent_page_contract_to_agent_audit_records(tmp_path: Path) -> None:
    governance = tmp_path / "governance"
    governance.mkdir()
    (governance / "agent_audit.jsonl").write_text(
        json.dumps(
            {
                "user_id": "agent_user",
                "query_text": "explain pnl",
                "tables_used": ["fact_formal_pnl_fi"],
                "result_meta": {
                    "result_kind": "agent.pnl_summary",
                    "formal_use_allowed": True,
                    "tables_used": ["fact_formal_pnl_fi"],
                },
                "created_at": "2026-04-12T14:31:38.517141Z",
            }
        )
        + "\n",
        encoding="utf-8",
    )

    server = McpProcess("lineage-evidence", env={"MOSS_GOVERNANCE_PATH": str(governance)})
    try:
        server.request("initialize")
        server.notify("notifications/initialized")

        found = server.request(
            "tools/call",
            {"name": "find_lineage_records", "arguments": {"query": "PAGE-AGENT-001", "max_results": 5}},
        )
        found_payload = json.loads(found["content"][0]["text"])

        assert found_payload["query"] == "PAGE-AGENT-001"
        assert "agent." in found_payload["expanded_queries"]
        assert found_payload["records"][0]["matched_query"] == "agent."
        assert found_payload["records"][0]["stream"] == "agent_audit"
        assert found_payload["records"][0]["record"]["result_meta"]["result_kind"] == "agent.pnl_summary"
        assert found_payload["records"][0]["record"]["result_meta"]["tables_used"] == ["fact_formal_pnl_fi"]
    finally:
        server.close()


def test_lineage_evidence_mcp_maps_cube_query_page_to_allowed_source_tables(tmp_path: Path) -> None:
    governance = tmp_path / "governance"
    governance.mkdir()
    (governance / "source_manifest_latest.jsonl").write_text(
        json.dumps(
            {
                "source_version": "sv_cube_pnl_fixture",
                "rule_version": "rv_cube_query_fixture",
                "tables_used": ["fact_formal_pnl_fi"],
                "created_at": "2026-04-12T14:31:38.517141Z",
            }
        )
        + "\n",
        encoding="utf-8",
    )

    server = McpProcess("lineage-evidence", env={"MOSS_GOVERNANCE_PATH": str(governance)})
    try:
        server.request("initialize")
        server.notify("notifications/initialized")

        found = server.request(
            "tools/call",
            {"name": "find_lineage_records", "arguments": {"query": "PAGE-CUBE-QUERY-001", "max_results": 5}},
        )
        found_payload = json.loads(found["content"][0]["text"])

        assert found_payload["query"] == "PAGE-CUBE-QUERY-001"
        assert "/api/cube/query" in found_payload["expanded_queries"]
        assert "cube_query." in found_payload["expanded_queries"]
        assert "fact_formal_pnl_fi" in found_payload["expanded_queries"]
        assert "result_meta" not in found_payload["expanded_queries"]
        assert found_payload["records"][0]["matched_query"] == "fact_formal_pnl_fi"
        assert found_payload["records"][0]["stream"] == "source_manifest_latest"
        assert found_payload["records"][0]["record"]["tables_used"] == ["fact_formal_pnl_fi"]
    finally:
        server.close()


@pytest.mark.parametrize(
    ("page_id", "record", "required_anchors"),
    [
        (
            "PAGE-PORTFOLIO-HOME-001",
            {
                "result_kind": "bond_dashboard.headline_kpis",
                "primary_api": "/api/bond-dashboard/headline-kpis",
                "page_role": "module-home/portfolio",
                "tables_used": ["fact_formal_bond_analytics_daily"],
                "boundary": "module home no standalone MTR binding",
            },
            [
                "module-home/portfolio",
                "/api/bond-dashboard/headline-kpis",
                "bond_dashboard.headline_kpis",
                "fact_formal_bond_analytics_daily",
            ],
        ),
        (
            "PAGE-MARKET-HOME-001",
            {
                "result_kind": "market_data.rates",
                "primary_api": "/ui/market-data/rates",
                "page_role": "module-home/market",
                "tables_used": ["market_data_series_category"],
                "boundary": "module home observational market entry",
            },
            [
                "module-home/market",
                "/ui/market-data/rates",
                "market_data.rates",
                "market_data_series_category",
            ],
        ),
        (
            "PAGE-RISK-HOME-001",
            {
                "result_kind": "risk.tensor",
                "primary_api": "/api/risk/tensor",
                "page_role": "module-home/risk",
                "tables_used": ["fact_formal_risk_tensor_daily"],
                "boundary": "module home does not replace PAGE-RISK-001 formal risk truth",
            },
            [
                "module-home/risk",
                "/api/risk/tensor",
                "risk.tensor",
                "fact_formal_risk_tensor_daily",
            ],
        ),
        (
            "PAGE-PERFORMANCE-HOME-001",
            {
                "result_kind": "pnl.by_business_ytd",
                "primary_api": "/api/pnl/by-business-ytd",
                "page_role": "module-home/performance",
                "tables_used": ["fact_formal_pnl_fi", "fact_nonstd_pnl_bridge"],
                "boundary": "module home does not rebuild KPI or team formulas",
            },
            [
                "module-home/performance",
                "/api/pnl/by-business-ytd",
                "pnl.by_business_ytd",
                "fact_formal_pnl_fi",
            ],
        ),
        (
            "PAGE-REPORTS-HOME-001",
            {
                "result_kind": "preview.source-foundation",
                "primary_api": "/ui/preview/source-foundation",
                "page_role": "module-home/governance",
                "tables_used": ["source_foundation"],
                "boundary": "module home diagnostics are not data-quality approval",
            },
            [
                "module-home/governance",
                "/ui/preview/source-foundation",
                "preview.source-foundation",
                "/api/cube/dimensions/bond_analytics",
            ],
        ),
    ],
)
def test_lineage_evidence_mcp_maps_module_home_pages_to_downstream_read_records(
    tmp_path: Path,
    page_id: str,
    record: dict[str, Any],
    required_anchors: list[str],
) -> None:
    governance = tmp_path / "governance"
    governance.mkdir()
    (governance / "cache_manifest.jsonl").write_text(
        json.dumps(record) + "\n",
        encoding="utf-8",
    )

    server = McpProcess("lineage-evidence", env={"MOSS_GOVERNANCE_PATH": str(governance)})
    try:
        server.request("initialize")
        server.notify("notifications/initialized")

        found = server.request(
            "tools/call",
            {"name": "find_lineage_records", "arguments": {"query": page_id, "max_results": 5}},
        )
        found_payload = json.loads(found["content"][0]["text"])

        assert found_payload["query"] == page_id
        for anchor in required_anchors:
            assert anchor in found_payload["expanded_queries"]
        assert not any(anchor.startswith("MTR-") for anchor in found_payload["expanded_queries"])
        assert not any(anchor.startswith("GS-") for anchor in found_payload["expanded_queries"])
        assert found_payload["records"]
        assert found_payload["records"][0]["matched_query"] in required_anchors
        assert found_payload["records"][0]["stream"] == "cache_manifest"
        assert found_payload["records"][0]["record"]["result_kind"] == record["result_kind"]
    finally:
        server.close()


def test_lineage_evidence_mcp_maps_business_pnl_page_to_page_level_read_records(tmp_path: Path) -> None:
    governance = tmp_path / "governance"
    governance.mkdir()
    record = {
        "result_kind": "pnl.by_business_ytd",
        "primary_api": "/api/pnl/by-business-ytd",
        "page_slug": "pnl-by-business",
        "tables_used": [
            "fact_formal_pnl_fi",
            "fact_nonstd_pnl_bridge",
            "fact_formal_zqtz_balance_daily",
        ],
        "boundary": "page-level analytical display no newly approved MTR binding",
    }
    (governance / "cache_manifest.jsonl").write_text(
        json.dumps(record) + "\n",
        encoding="utf-8",
    )

    server = McpProcess("lineage-evidence", env={"MOSS_GOVERNANCE_PATH": str(governance)})
    try:
        server.request("initialize")
        server.notify("notifications/initialized")

        found = server.request(
            "tools/call",
            {
                "name": "find_lineage_records",
                "arguments": {"query": "PAGE-PNL-BY-BUSINESS-001", "max_results": 5},
            },
        )
        found_payload = json.loads(found["content"][0]["text"])

        required_anchors = [
            "pnl-by-business",
            "/api/pnl/by-business-ytd",
            "/api/pnl/by-business-monthly",
            "/api/pnl/by-business",
            "/api/pnl/by-business-analysis",
            "/api/adb/comparison",
            "pnl.by_business_ytd",
            "pnl.by_business_monthly",
            "pnl.by_business",
            "pnl.by_business_analysis",
            "fact_formal_pnl_fi",
            "fact_nonstd_pnl_bridge",
            "fact_formal_zqtz_balance_daily",
            "fact_pnl_by_business_precompute",
            "pnl_by_business_adjustments",
        ]
        excluded_anchors = [
            "product_category_pnl_formal_read_model",
            "qdb_general_ledger_workbook",
            "GS-PROD-CAT-PNL-A",
            "PAGE-PROD-CAT-PNL-001",
            "PAGE-LEDGER-PNL-001",
            "MTR-PCP-001",
            "MTR-LPN-001",
        ]

        assert found_payload["query"] == "PAGE-PNL-BY-BUSINESS-001"
        for anchor in required_anchors:
            assert anchor in found_payload["expanded_queries"]
        for anchor in excluded_anchors:
            assert anchor not in found_payload["expanded_queries"]
        assert not any(anchor.startswith("MTR-") for anchor in found_payload["expanded_queries"])
        assert not any(anchor.startswith("GS-") for anchor in found_payload["expanded_queries"])
        assert found_payload["records"][0]["matched_query"] == "/api/pnl/by-business-ytd"
        assert found_payload["records"][0]["stream"] == "cache_manifest"
        assert found_payload["records"][0]["record"]["result_kind"] == "pnl.by_business_ytd"
    finally:
        server.close()


def test_lineage_evidence_mcp_maps_dashboard_home_page_to_mixed_snapshot_records(
    tmp_path: Path,
) -> None:
    governance = tmp_path / "governance"
    governance.mkdir()
    records = [
        {
            "cache_key": "dashboard:home:snapshot",
            "result_kind": "home.snapshot",
            "source_surface": "executive_analytical",
            "basis": "analytical",
            "primary_api": "/ui/home/snapshot",
            "payload_schema": "HomeSnapshotPayload",
            "service": "home_snapshot_envelope",
            "domains_effective_date": {
                "balance": "2026-05-31",
                "pnl": "2026-05-31",
                "liability": "2026-05-31",
                "bond": "2026-05-31",
            },
            "domains_missing": [],
            "child_result_kinds": [
                "executive.overview",
                "executive.summary",
                "executive.pnl-attribution",
                "product_category_ytd",
                "product_category_monthly",
            ],
            "supplemental_result_kinds": [
                "dashboard.core_metrics",
                "dashboard.daily_changes",
                "bond_dashboard.headline_kpis",
                "bond_analytics.portfolio_headlines",
                "market_data.rates",
                "calendar.supply_auctions",
            ],
            "tables_used": [
                "fact_formal_zqtz_balance_daily",
                "fact_formal_tyw_balance_daily",
                "fact_formal_pnl_fi",
                "fact_nonstd_pnl_bridge",
                "zqtz_bond_daily_snapshot",
                "tyw_interbank_daily_snapshot",
                "fact_formal_bond_analytics_daily",
                "product_category_pnl_formal_read_model",
                "product_category_pnl_canonical_fact",
                "fx_daily_mid",
            ],
        },
        {
            "cache_key": "dashboard:core-metrics",
            "result_kind": "dashboard.core_metrics",
            "source_surface": "dashboard_supplemental",
            "basis": "analytical",
            "role": "same_date_supplemental",
            "tables_used": ["fact_formal_zqtz_balance_daily", "fact_formal_tyw_balance_daily"],
        },
        {
            "cache_key": "dashboard:bond-headline",
            "result_kind": "bond_dashboard.headline_kpis",
            "source_surface": "bond_analytics",
            "basis": "analytical",
            "role": "same_date_supplemental",
            "tables_used": ["fact_formal_bond_analytics_daily"],
        },
        {
            "cache_key": "executive:overview",
            "result_kind": "executive.overview",
            "page_id": "PAGE-EXEC-OVERVIEW-001",
            "golden_sample": "GS-EXEC-OVERVIEW-A",
        },
        {
            "cache_key": "bond_dashboard:headline",
            "result_kind": "bond_dashboard.headline_kpis",
            "page_id": "PAGE-BOND-001",
            "golden_sample": "GS-BOND-HEADLINE-A",
        },
    ]
    (governance / "cache_manifest.jsonl").write_text(
        "".join(json.dumps(record) + "\n" for record in records),
        encoding="utf-8",
    )

    server = McpProcess("lineage-evidence", env={"MOSS_GOVERNANCE_PATH": str(governance)})
    try:
        server.request("initialize")
        server.notify("notifications/initialized")

        found = server.request(
            "tools/call",
            {"name": "find_lineage_records", "arguments": {"query": "PAGE-DASH-001", "max_results": 10}},
        )
        found_payload = json.loads(found["content"][0]["text"])

        assert found_payload["query"] == "PAGE-DASH-001"
        assert "/ui/home/snapshot" in found_payload["expanded_queries"]
        assert "home.snapshot" in found_payload["expanded_queries"]
        assert "dashboard-home" in found_payload["expanded_queries"]
        assert "HomeSnapshotPayload" in found_payload["expanded_queries"]
        assert "home_snapshot_envelope" in found_payload["expanded_queries"]
        assert "executive_analytical" in found_payload["expanded_queries"]
        assert "domains_effective_date" in found_payload["expanded_queries"]
        assert "domains_missing" in found_payload["expanded_queries"]
        assert "product_category_ytd" in found_payload["expanded_queries"]
        assert "product_category_monthly" in found_payload["expanded_queries"]
        assert "dashboard.core_metrics" in found_payload["expanded_queries"]
        assert "dashboard.daily_changes" in found_payload["expanded_queries"]
        assert "bond_dashboard.headline_kpis" in found_payload["expanded_queries"]
        assert "bond_analytics.portfolio_headlines" in found_payload["expanded_queries"]
        assert "market_data.rates" in found_payload["expanded_queries"]
        assert "calendar.supply_auctions" in found_payload["expanded_queries"]
        assert "fact_formal_zqtz_balance_daily" in found_payload["expanded_queries"]
        assert "fact_formal_tyw_balance_daily" in found_payload["expanded_queries"]
        assert "fact_formal_pnl_fi" in found_payload["expanded_queries"]
        assert "fact_nonstd_pnl_bridge" in found_payload["expanded_queries"]
        assert "fact_formal_bond_analytics_daily" in found_payload["expanded_queries"]
        assert "product_category_pnl_formal_read_model" in found_payload["expanded_queries"]
        assert "fx_daily_mid" in found_payload["expanded_queries"]
        assert "PAGE-EXEC-OVERVIEW-001" not in found_payload["expanded_queries"]
        assert "GS-EXEC-OVERVIEW-A" not in found_payload["expanded_queries"]
        assert "PAGE-EXEC-PNL-ATTR-001" not in found_payload["expanded_queries"]
        assert "GS-EXEC-PNL-ATTR-A" not in found_payload["expanded_queries"]
        assert "PAGE-BOND-001" not in found_payload["expanded_queries"]
        assert "GS-BOND-HEADLINE-A" not in found_payload["expanded_queries"]
        assert "PAGE-PROD-CAT-PNL-001" not in found_payload["expanded_queries"]
        assert "GS-PROD-CAT-PNL-A" not in found_payload["expanded_queries"]
        assert "PAGE-MKT-001" not in found_payload["expanded_queries"]
        assert found_payload["records"][0]["matched_query"] == "/ui/home/snapshot"
        assert found_payload["records"][0]["stream"] == "cache_manifest"
        assert found_payload["records"][0]["record"]["result_kind"] == "home.snapshot"
        assert found_payload["records"][0]["record"]["basis"] == "analytical"
        assert found_payload["records"][1]["matched_query"] == "dashboard.core_metrics"
        assert found_payload["records"][1]["record"]["role"] == "same_date_supplemental"
    finally:
        server.close()


def test_lineage_evidence_mcp_maps_executive_summary_page_to_narrative_records(
    tmp_path: Path,
) -> None:
    governance = tmp_path / "governance"
    governance.mkdir()
    records = [
        {
            "cache_key": "executive:summary",
            "result_kind": "executive.summary",
            "source_surface": "executive_summary",
            "basis": "analytical",
            "primary_api": "/ui/home/summary",
            "payload_schema": "SummaryPayload",
            "golden_sample": "GS-EXEC-SUMMARY-A",
            "contract_scope": "narrative-only",
            "lineage_dependency": "executive.overview",
        },
        {
            "cache_key": "executive:summary:point-income",
            "result_kind": "executive.summary",
            "source_surface": "executive_summary",
            "basis": "analytical",
            "payload_schema": "SummaryPoint",
            "point_id": "income",
            "lineage_dependency": "executive.overview",
        },
        {
            "cache_key": "executive:overview",
            "result_kind": "executive.overview",
            "page_id": "PAGE-EXEC-OVERVIEW-001",
            "golden_sample": "GS-EXEC-OVERVIEW-A",
            "metric_ids": ["MTR-EXEC-001", "MTR-EXEC-002"],
        },
        {
            "cache_key": "executive:pnl-attribution",
            "result_kind": "executive.pnl-attribution",
            "page_id": "PAGE-EXEC-PNL-ATTR-001",
            "golden_sample": "GS-EXEC-PNL-ATTR-A",
            "metric_ids": ["MTR-EXEC-101"],
        },
    ]
    (governance / "cache_manifest.jsonl").write_text(
        "".join(json.dumps(record) + "\n" for record in records),
        encoding="utf-8",
    )

    server = McpProcess("lineage-evidence", env={"MOSS_GOVERNANCE_PATH": str(governance)})
    try:
        server.request("initialize")
        server.notify("notifications/initialized")

        found = server.request(
            "tools/call",
            {
                "name": "find_lineage_records",
                "arguments": {"query": "PAGE-EXEC-SUMMARY-001", "max_results": 10},
            },
        )
        found_payload = json.loads(found["content"][0]["text"])

        assert found_payload["query"] == "PAGE-EXEC-SUMMARY-001"
        assert "/ui/home/summary" in found_payload["expanded_queries"]
        assert "executive.summary" in found_payload["expanded_queries"]
        assert "executive-summary" in found_payload["expanded_queries"]
        assert "executive_summary" in found_payload["expanded_queries"]
        assert "SummaryPayload" in found_payload["expanded_queries"]
        assert "SummaryPoint" in found_payload["expanded_queries"]
        assert "GS-EXEC-SUMMARY-A" in found_payload["expanded_queries"]
        assert "narrative-only" in found_payload["expanded_queries"]
        assert "executive.overview" in found_payload["expanded_queries"]
        assert "PAGE-EXEC-OVERVIEW-001" not in found_payload["expanded_queries"]
        assert "GS-EXEC-OVERVIEW-A" not in found_payload["expanded_queries"]
        assert "MTR-EXEC-001" not in found_payload["expanded_queries"]
        assert "MTR-EXEC-101" not in found_payload["expanded_queries"]
        assert "PAGE-EXEC-PNL-ATTR-001" not in found_payload["expanded_queries"]
        assert "GS-EXEC-PNL-ATTR-A" not in found_payload["expanded_queries"]
        assert found_payload["records"][0]["matched_query"] == "/ui/home/summary"
        assert found_payload["records"][0]["stream"] == "cache_manifest"
        assert found_payload["records"][0]["record"]["result_kind"] == "executive.summary"
        assert found_payload["records"][0]["record"]["contract_scope"] == "narrative-only"
        assert found_payload["records"][1]["matched_query"] == "executive.summary"
        assert found_payload["records"][1]["record"]["payload_schema"] == "SummaryPoint"
    finally:
        server.close()


def test_lineage_evidence_mcp_maps_macro_toolkit_page_to_tooling_records(
    tmp_path: Path,
) -> None:
    governance = tmp_path / "governance"
    governance.mkdir()
    records = [
        {
            "cache_key": "macro-toolkit:analysis",
            "result_kind": "macro_toolkit.analysis",
            "source_surface": "macro_toolkit",
            "basis": "analytical",
            "primary_api": "/ui/macro/toolkit/analysis",
            "formal_use_allowed": False,
            "contract_scope": "candidate tooling surface",
            "coverage_hit_rate": 0.82,
            "source_version": "sv_macro_toolkit_analysis",
            "rule_version": "rv_macro_toolkit_analysis",
        },
        {
            "cache_key": "macro-toolkit:strategy-summaries",
            "result_kind": "macro_toolkit.analysis.strategy_summaries",
            "source_surface": "macro_toolkit",
            "basis": "analytical",
            "primary_api": "/ui/macro/toolkit/analysis/strategy-summaries",
            "formal_use_allowed": False,
            "strategy_count": 3,
        },
        {
            "cache_key": "macro-toolkit:scripts",
            "result_kind": "macro_toolkit.scripts",
            "source_surface": "macro_toolkit",
            "basis": "tooling",
            "primary_api": "/ui/macro/toolkit/scripts",
            "formal_use_allowed": False,
            "script_count": 4,
        },
        {
            "cache_key": "macro-toolkit:refresh",
            "result_kind": "macro_toolkit.choice_stock_refresh",
            "source_surface": "macro_toolkit",
            "basis": "operational",
            "primary_api": "/ui/macro/toolkit/choice-stock/refresh",
            "formal_use_allowed": False,
            "run_id": "macro-refresh-1",
        },
        {
            "metric_id": "MTR-MACRO-001",
            "result_kind": "formal.macro.metric",
            "basis": "formal",
            "formal_use_allowed": True,
        },
    ]
    (governance / "cache_manifest.jsonl").write_text(
        "".join(json.dumps(record) + "\n" for record in records),
        encoding="utf-8",
    )

    server = McpProcess("lineage-evidence", env={"MOSS_GOVERNANCE_PATH": str(governance)})
    try:
        server.request("initialize")
        server.notify("notifications/initialized")

        found = server.request(
            "tools/call",
            {
                "name": "find_lineage_records",
                "arguments": {"query": "PAGE-MACRO-TOOLKIT-001", "max_results": 10},
            },
        )
        found_payload = json.loads(found["content"][0]["text"])

        assert found_payload["query"] == "PAGE-MACRO-TOOLKIT-001"
        assert "/ui/macro/toolkit/analysis" in found_payload["expanded_queries"]
        assert "/ui/macro/toolkit/analysis/strategy-summaries" in found_payload["expanded_queries"]
        assert "/ui/macro/toolkit/scripts" in found_payload["expanded_queries"]
        assert "/ui/macro/toolkit/scripts/" in found_payload["expanded_queries"]
        assert "/ui/macro/toolkit/choice-stock/refresh-status" in found_payload["expanded_queries"]
        assert "/ui/macro/toolkit/choice-stock/refresh" in found_payload["expanded_queries"]
        assert "/ui/macro/toolkit/cffex-member-rank/refresh" in found_payload["expanded_queries"]
        assert "macro-toolkit" in found_payload["expanded_queries"]
        assert "macro_toolkit.analysis" in found_payload["expanded_queries"]
        assert "macro_toolkit.analysis.strategy_summaries" in found_payload["expanded_queries"]
        assert "macro_toolkit.scripts" in found_payload["expanded_queries"]
        assert "macro_toolkit.choice_stock_refresh" in found_payload["expanded_queries"]
        assert "macro_toolkit.cffex_member_rank_refresh" in found_payload["expanded_queries"]
        assert "MacroToolkitAnalysisPayload" in found_payload["expanded_queries"]
        assert "MacroToolkitPayload" in found_payload["expanded_queries"]
        assert "MacroToolkitRunResponse" in found_payload["expanded_queries"]
        assert "candidate tooling surface" in found_payload["expanded_queries"]
        assert "source/version/run_id" in found_payload["expanded_queries"]
        assert "MTR-MACRO-001" not in found_payload["expanded_queries"]
        assert "MTR-" not in found_payload["expanded_queries"]
        assert "GS-MACRO-TOOLKIT-A" not in found_payload["expanded_queries"]
        matched_records = {record["record"]["result_kind"]: record for record in found_payload["records"]}
        assert matched_records["macro_toolkit.analysis"]["matched_query"] == "/ui/macro/toolkit/analysis"
        assert matched_records["macro_toolkit.analysis"]["record"]["formal_use_allowed"] is False
        assert matched_records["macro_toolkit.analysis"]["record"]["contract_scope"] == "candidate tooling surface"
        assert (
            matched_records["macro_toolkit.analysis.strategy_summaries"]["record"]["primary_api"]
            == "/ui/macro/toolkit/analysis/strategy-summaries"
        )
        assert matched_records["macro_toolkit.scripts"]["record"]["primary_api"] == "/ui/macro/toolkit/scripts"
    finally:
        server.close()


def test_lineage_evidence_mcp_maps_macro_observation_page_to_readonly_records(
    tmp_path: Path,
) -> None:
    governance = tmp_path / "governance"
    governance.mkdir()
    records = [
        {
            "cache_key": "macro-observation:analysis",
            "result_kind": "macro_toolkit.analysis",
            "source_surface": "macro_observation",
            "basis": "analytical",
            "primary_api": "/ui/macro/toolkit/analysis",
            "formal_use_allowed": False,
            "contract_scope": "read-only macro observation",
            "boundary": "macro-observation-readonly-boundary",
        },
        {
            "cache_key": "macro-observation:strategy-summaries",
            "result_kind": "macro_toolkit.analysis.strategy_summaries",
            "source_surface": "macro_observation",
            "basis": "analytical",
            "primary_api": "/ui/macro/toolkit/analysis/strategy-summaries",
            "formal_use_allowed": False,
            "contract_scope": "read-only macro observation",
        },
        {
            "cache_key": "macro-toolkit:scripts",
            "result_kind": "macro_toolkit.scripts",
            "source_surface": "macro_toolkit",
            "basis": "tooling",
            "primary_api": "/ui/macro/toolkit/scripts",
        },
        {
            "cache_key": "macro-toolkit:refresh",
            "result_kind": "macro_toolkit.choice_stock_refresh",
            "source_surface": "macro_toolkit",
            "basis": "operational",
            "primary_api": "/ui/macro/toolkit/choice-stock/refresh",
        },
    ]
    (governance / "cache_manifest.jsonl").write_text(
        "".join(json.dumps(record) + "\n" for record in records),
        encoding="utf-8",
    )

    server = McpProcess("lineage-evidence", env={"MOSS_GOVERNANCE_PATH": str(governance)})
    try:
        server.request("initialize")
        server.notify("notifications/initialized")

        found = server.request(
            "tools/call",
            {
                "name": "find_lineage_records",
                "arguments": {"query": "PAGE-MACRO-OBS-001", "max_results": 10},
            },
        )
        found_payload = json.loads(found["content"][0]["text"])

        assert found_payload["query"] == "PAGE-MACRO-OBS-001"
        assert "/ui/macro/toolkit/analysis" in found_payload["expanded_queries"]
        assert "/ui/macro/toolkit/analysis/strategy-summaries" in found_payload["expanded_queries"]
        assert "macro-observation" in found_payload["expanded_queries"]
        assert "macro_observation" in found_payload["expanded_queries"]
        assert "macro_toolkit.analysis" in found_payload["expanded_queries"]
        assert "macro_toolkit.analysis.strategy_summaries" in found_payload["expanded_queries"]
        assert "MacroToolkitAnalysisPayload" in found_payload["expanded_queries"]
        assert "macro-observation-readonly-boundary" in found_payload["expanded_queries"]
        assert "read-only macro observation" in found_payload["expanded_queries"]
        assert "/ui/macro/toolkit/scripts" not in found_payload["expanded_queries"]
        assert "/ui/macro/toolkit/scripts/" not in found_payload["expanded_queries"]
        assert "/ui/macro/toolkit/choice-stock/refresh" not in found_payload["expanded_queries"]
        assert "/ui/macro/toolkit/choice-stock/refresh-status" not in found_payload["expanded_queries"]
        assert "macro_toolkit.scripts" not in found_payload["expanded_queries"]
        assert "macro_toolkit.choice_stock_refresh" not in found_payload["expanded_queries"]
        assert "MTR-MACRO-001" not in found_payload["expanded_queries"]
        assert "MTR-" not in found_payload["expanded_queries"]
        matched_records = {record["record"]["result_kind"]: record for record in found_payload["records"]}
        assert matched_records["macro_toolkit.analysis"]["matched_query"] == "/ui/macro/toolkit/analysis"
        assert matched_records["macro_toolkit.analysis"]["record"]["contract_scope"] == "read-only macro observation"
        assert (
            matched_records["macro_toolkit.analysis.strategy_summaries"]["record"]["primary_api"]
            == "/ui/macro/toolkit/analysis/strategy-summaries"
        )
        assert matched_records["macro_toolkit.analysis.strategy_summaries"]["record"]["formal_use_allowed"] is False
    finally:
        server.close()


def test_lineage_evidence_mcp_maps_executive_overview_page_to_overlay_records(
    tmp_path: Path,
) -> None:
    governance = tmp_path / "governance"
    governance.mkdir()
    records = [
        {
            "cache_key": "executive:overview",
            "result_kind": "executive.overview",
            "source_surface": "executive_overview",
            "basis": "analytical",
            "golden_sample": "GS-EXEC-OVERVIEW-A",
            "metric_ids": [
                "MTR-EXEC-001",
                "MTR-EXEC-002",
                "MTR-EXEC-003",
                "MTR-EXEC-004",
                "MTR-EXEC-004A",
                "MTR-EXEC-004B",
                "MTR-EXEC-004C",
            ],
            "tables_used": [
                "fact_formal_zqtz_balance_daily",
                "fact_formal_tyw_balance_daily",
                "fact_formal_pnl_fi",
                "fact_nonstd_pnl_bridge",
                "zqtz_bond_daily_snapshot",
                "tyw_interbank_daily_snapshot",
                "fact_formal_bond_analytics_daily",
            ],
        },
        {
            "cache_key": "executive:overview:aum",
            "result_kind": "executive.overview",
            "metric_id": "MTR-EXEC-001",
            "source_surface": "formal_balance",
            "basis": "analytical",
            "tables_used": ["fact_formal_zqtz_balance_daily", "fact_formal_tyw_balance_daily"],
        },
        {
            "cache_key": "executive:overview:nim",
            "result_kind": "executive.overview",
            "metric_id": "MTR-EXEC-003",
            "source_surface": "liability_analytics.yield_metrics",
            "basis": "analytical",
            "tables_used": ["zqtz_bond_daily_snapshot", "tyw_interbank_daily_snapshot"],
        },
        {
            "cache_key": "balance:overview",
            "result_kind": "balance-analysis.overview",
            "page_id": "PAGE-BALANCE-001",
            "golden_sample": "GS-BAL-OVERVIEW-A",
        },
        {
            "cache_key": "pnl:overview",
            "result_kind": "pnl.overview",
            "page_id": "PAGE-PNL-001",
            "golden_sample": "GS-PNL-OVERVIEW-A",
        },
        {
            "cache_key": "risk:tensor",
            "result_kind": "risk.tensor",
            "page_id": "PAGE-RISK-001",
            "golden_sample": "GS-RISK-A",
        },
    ]
    (governance / "cache_manifest.jsonl").write_text(
        "".join(json.dumps(record) + "\n" for record in records),
        encoding="utf-8",
    )

    server = McpProcess("lineage-evidence", env={"MOSS_GOVERNANCE_PATH": str(governance)})
    try:
        server.request("initialize")
        server.notify("notifications/initialized")

        found = server.request(
            "tools/call",
            {
                "name": "find_lineage_records",
                "arguments": {"query": "PAGE-EXEC-OVERVIEW-001", "max_results": 10},
            },
        )
        found_payload = json.loads(found["content"][0]["text"])

        assert found_payload["query"] == "PAGE-EXEC-OVERVIEW-001"
        assert "/ui/home/overview" in found_payload["expanded_queries"]
        assert "executive.overview" in found_payload["expanded_queries"]
        assert "executive_overview" in found_payload["expanded_queries"]
        assert "OverviewPayload" in found_payload["expanded_queries"]
        assert "ExecutiveMetric" in found_payload["expanded_queries"]
        assert "ExecutiveMetric.caliber_label" in found_payload["expanded_queries"]
        assert "GS-EXEC-OVERVIEW-A" in found_payload["expanded_queries"]
        assert "MTR-EXEC-001" in found_payload["expanded_queries"]
        assert "MTR-EXEC-004C" in found_payload["expanded_queries"]
        assert "formal_balance" in found_payload["expanded_queries"]
        assert "fact_formal_zqtz_balance_daily" in found_payload["expanded_queries"]
        assert "fact_formal_tyw_balance_daily" in found_payload["expanded_queries"]
        assert "fact_formal_pnl_fi" in found_payload["expanded_queries"]
        assert "fact_nonstd_pnl_bridge" in found_payload["expanded_queries"]
        assert "liability_analytics.yield_metrics" in found_payload["expanded_queries"]
        assert "zqtz_bond_daily_snapshot" in found_payload["expanded_queries"]
        assert "tyw_interbank_daily_snapshot" in found_payload["expanded_queries"]
        assert "fact_formal_bond_analytics_daily" in found_payload["expanded_queries"]
        assert "PAGE-BALANCE-001" not in found_payload["expanded_queries"]
        assert "balance-analysis.overview" not in found_payload["expanded_queries"]
        assert "GS-BAL-OVERVIEW-A" not in found_payload["expanded_queries"]
        assert "PAGE-PNL-001" not in found_payload["expanded_queries"]
        assert "pnl.overview" not in found_payload["expanded_queries"]
        assert "GS-PNL-OVERVIEW-A" not in found_payload["expanded_queries"]
        assert "PAGE-RISK-001" not in found_payload["expanded_queries"]
        assert "risk.tensor" not in found_payload["expanded_queries"]
        assert "GS-RISK-A" not in found_payload["expanded_queries"]
        assert "executive.pnl-attribution" not in found_payload["expanded_queries"]
        assert "GS-EXEC-PNL-ATTR-A" not in found_payload["expanded_queries"]
        assert found_payload["records"][0]["matched_query"] == "executive.overview"
        assert found_payload["records"][0]["stream"] == "cache_manifest"
        assert found_payload["records"][0]["record"]["basis"] == "analytical"
        assert found_payload["records"][0]["record"]["golden_sample"] == "GS-EXEC-OVERVIEW-A"
        assert found_payload["records"][1]["matched_query"] == "executive.overview"
        assert found_payload["records"][1]["record"]["metric_id"] == "MTR-EXEC-001"
        assert found_payload["records"][1]["record"]["source_surface"] == "formal_balance"
        assert found_payload["records"][2]["matched_query"] == "executive.overview"
        assert found_payload["records"][2]["record"]["metric_id"] == "MTR-EXEC-003"
        assert found_payload["records"][2]["record"]["source_surface"] == "liability_analytics.yield_metrics"
    finally:
        server.close()


def test_lineage_evidence_mcp_maps_formal_pnl_page_to_formal_fact_records(tmp_path: Path) -> None:
    governance = tmp_path / "governance"
    governance.mkdir()
    (governance / "source_manifest_latest.jsonl").write_text(
        json.dumps(
            {
                "source_version": "fi-shared-v1__nonstd-shared-v1",
                "rule_version": "rv_pnl_phase2_materialize_v1",
                "cache_version": "cv_pnl_formal__rv_pnl_phase2_materialize_v1",
                "tables_used": ["fact_formal_pnl_fi", "fact_nonstd_pnl_bridge"],
                "golden_samples": ["GS-PNL-OVERVIEW-A", "GS-PNL-DATA-A"],
                "result_kind": "pnl.overview",
                "created_at": "2026-04-12T14:31:38.517141Z",
            }
        )
        + "\n",
        encoding="utf-8",
    )

    server = McpProcess("lineage-evidence", env={"MOSS_GOVERNANCE_PATH": str(governance)})
    try:
        server.request("initialize")
        server.notify("notifications/initialized")

        found = server.request(
            "tools/call",
            {"name": "find_lineage_records", "arguments": {"query": "PAGE-PNL-001", "max_results": 5}},
        )
        found_payload = json.loads(found["content"][0]["text"])

        assert found_payload["query"] == "PAGE-PNL-001"
        assert "/api/pnl/overview" in found_payload["expanded_queries"]
        assert "/api/pnl/data" in found_payload["expanded_queries"]
        assert "pnl.overview" in found_payload["expanded_queries"]
        assert "pnl.data" in found_payload["expanded_queries"]
        assert "fact_formal_pnl_fi" in found_payload["expanded_queries"]
        assert "fact_nonstd_pnl_bridge" in found_payload["expanded_queries"]
        assert "GS-PNL-OVERVIEW-A" in found_payload["expanded_queries"]
        assert "GS-PNL-DATA-A" in found_payload["expanded_queries"]
        assert "MTR-PNL-001" in found_payload["expanded_queries"]
        assert "MTR-PNL-104" in found_payload["expanded_queries"]
        assert "product_category_pnl_formal_read_model" not in found_payload["expanded_queries"]
        assert "qdb_general_ledger_workbook" not in found_payload["expanded_queries"]
        assert found_payload["records"][0]["matched_query"] == "pnl.overview"
        assert found_payload["records"][0]["stream"] == "source_manifest_latest"
        assert found_payload["records"][0]["record"]["tables_used"] == [
            "fact_formal_pnl_fi",
            "fact_nonstd_pnl_bridge",
        ]
    finally:
        server.close()


def test_lineage_evidence_mcp_maps_pnl_bridge_page_to_bridge_records(tmp_path: Path) -> None:
    governance = tmp_path / "governance"
    governance.mkdir()
    (governance / "cache_manifest.jsonl").write_text(
        json.dumps(
            {
                "cache_key": "pnl:bridge:formal",
                "result_kind": "pnl.bridge",
                "source_surface": "pnl_bridge",
                "fact_tables": ["fact_formal_pnl_fi", "fact_nonstd_pnl_bridge"],
                "golden_samples": ["GS-BRIDGE-A", "GS-BRIDGE-WARN-B"],
                "created_at": "2026-04-12T14:31:38.517141Z",
            }
        )
        + "\n",
        encoding="utf-8",
    )

    server = McpProcess("lineage-evidence", env={"MOSS_GOVERNANCE_PATH": str(governance)})
    try:
        server.request("initialize")
        server.notify("notifications/initialized")

        found = server.request(
            "tools/call",
            {"name": "find_lineage_records", "arguments": {"query": "PAGE-BRIDGE-001", "max_results": 5}},
        )
        found_payload = json.loads(found["content"][0]["text"])

        assert found_payload["query"] == "PAGE-BRIDGE-001"
        assert "/api/pnl/bridge" in found_payload["expanded_queries"]
        assert "pnl.bridge" in found_payload["expanded_queries"]
        assert "pnl_bridge" in found_payload["expanded_queries"]
        assert "fact_formal_pnl_fi" in found_payload["expanded_queries"]
        assert "fact_nonstd_pnl_bridge" in found_payload["expanded_queries"]
        assert "GS-BRIDGE-A" in found_payload["expanded_queries"]
        assert "GS-BRIDGE-WARN-B" in found_payload["expanded_queries"]
        assert "MTR-BRG-001" in found_payload["expanded_queries"]
        assert "MTR-BRG-105" in found_payload["expanded_queries"]
        assert "product_category_pnl_formal_read_model" not in found_payload["expanded_queries"]
        assert "qdb_general_ledger_workbook" not in found_payload["expanded_queries"]
        assert found_payload["records"][0]["matched_query"] == "pnl.bridge"
        assert found_payload["records"][0]["stream"] == "cache_manifest"
        assert found_payload["records"][0]["record"]["result_kind"] == "pnl.bridge"
        assert found_payload["records"][0]["record"]["source_surface"] == "pnl_bridge"
    finally:
        server.close()


def test_lineage_evidence_mcp_maps_balance_analysis_page_to_formal_balance_records(tmp_path: Path) -> None:
    governance = tmp_path / "governance"
    governance.mkdir()
    (governance / "source_manifest_latest.jsonl").write_text(
        json.dumps(
            {
                "source_version": "sv_balance_fixture",
                "rule_version": "rv_balance_materialize_fixture",
                "result_kind": "balance-analysis.overview",
                "tables_used": ["fact_formal_zqtz_balance_daily", "fact_formal_tyw_balance_daily"],
                "golden_samples": ["GS-BAL-OVERVIEW-A", "GS-BAL-WORKBOOK-A"],
                "created_at": "2026-04-12T14:31:38.517141Z",
            }
        )
        + "\n",
        encoding="utf-8",
    )

    server = McpProcess("lineage-evidence", env={"MOSS_GOVERNANCE_PATH": str(governance)})
    try:
        server.request("initialize")
        server.notify("notifications/initialized")

        found = server.request(
            "tools/call",
            {"name": "find_lineage_records", "arguments": {"query": "PAGE-BALANCE-001", "max_results": 5}},
        )
        found_payload = json.loads(found["content"][0]["text"])

        assert found_payload["query"] == "PAGE-BALANCE-001"
        assert "/ui/balance-analysis/overview" in found_payload["expanded_queries"]
        assert "/ui/balance-analysis/workbook" in found_payload["expanded_queries"]
        assert "balance-analysis.overview" in found_payload["expanded_queries"]
        assert "balance-analysis.workbook" in found_payload["expanded_queries"]
        assert "balance_analysis" in found_payload["expanded_queries"]
        assert "fact_formal_zqtz_balance_daily" in found_payload["expanded_queries"]
        assert "fact_formal_tyw_balance_daily" in found_payload["expanded_queries"]
        assert "GS-BAL-OVERVIEW-A" in found_payload["expanded_queries"]
        assert "GS-BAL-WORKBOOK-A" in found_payload["expanded_queries"]
        assert "MTR-BAL-001" in found_payload["expanded_queries"]
        assert "MTR-BAL-203" in found_payload["expanded_queries"]
        assert "fact_formal_pnl_fi" not in found_payload["expanded_queries"]
        assert "product_category_pnl_formal_read_model" not in found_payload["expanded_queries"]
        assert "qdb_general_ledger_workbook" not in found_payload["expanded_queries"]
        assert found_payload["records"][0]["matched_query"] == "balance-analysis.overview"
        assert found_payload["records"][0]["stream"] == "source_manifest_latest"
        assert found_payload["records"][0]["record"]["tables_used"] == [
            "fact_formal_zqtz_balance_daily",
            "fact_formal_tyw_balance_daily",
        ]
    finally:
        server.close()


def test_lineage_evidence_mcp_maps_pnl_attribution_workbench_to_formal_attribution_records(
    tmp_path: Path,
) -> None:
    governance = tmp_path / "governance"
    governance.mkdir()
    (governance / "source_manifest_latest.jsonl").write_text(
        json.dumps(
            {
                "source_version": "sv_pnl_attribution_fixture",
                "rule_version": "rv_pnl_attribution_workbench_v1",
                "cache_version": "cv_pnl_attribution_workbench_v1",
                "result_kind": "pnl_attribution.volume_rate",
                "tables_used": [
                    "fact_formal_pnl_fi",
                    "fact_nonstd_pnl_bridge",
                    "fact_formal_zqtz_balance_daily",
                ],
                "created_at": "2026-04-12T14:31:38.517141Z",
            }
        )
        + "\n",
        encoding="utf-8",
    )

    server = McpProcess("lineage-evidence", env={"MOSS_GOVERNANCE_PATH": str(governance)})
    try:
        server.request("initialize")
        server.notify("notifications/initialized")

        found = server.request(
            "tools/call",
            {"name": "find_lineage_records", "arguments": {"query": "PAGE-PNL-ATTR-WB-001", "max_results": 5}},
        )
        found_payload = json.loads(found["content"][0]["text"])

        assert found_payload["query"] == "PAGE-PNL-ATTR-WB-001"
        assert "/api/pnl-attribution/volume-rate" in found_payload["expanded_queries"]
        assert "/api/pnl-attribution/tpl-market" in found_payload["expanded_queries"]
        assert "/api/pnl-attribution/composition" in found_payload["expanded_queries"]
        assert "/api/pnl-attribution/advanced/summary" in found_payload["expanded_queries"]
        assert "/api/pnl-attribution/campisi/four-effects" in found_payload["expanded_queries"]
        assert "pnl_attribution.volume_rate" in found_payload["expanded_queries"]
        assert "pnl_attribution.advanced_summary" in found_payload["expanded_queries"]
        assert "VolumeRateAttributionPayload" in found_payload["expanded_queries"]
        assert "AdvancedAttributionSummary" in found_payload["expanded_queries"]
        assert "fact_formal_pnl_fi" in found_payload["expanded_queries"]
        assert "fact_nonstd_pnl_bridge" in found_payload["expanded_queries"]
        assert "fact_formal_zqtz_balance_daily" in found_payload["expanded_queries"]
        assert "fact_formal_bond_analytics_daily" in found_payload["expanded_queries"]
        assert "yield_curve_daily" in found_payload["expanded_queries"]
        assert "MTR-PAT-001" in found_payload["expanded_queries"]
        assert "MTR-PAT-304" in found_payload["expanded_queries"]
        assert "executive.pnl-attribution" not in found_payload["expanded_queries"]
        assert "GS-EXEC-PNL-ATTR-A" not in found_payload["expanded_queries"]
        assert "MTR-EXEC-101" not in found_payload["expanded_queries"]
        assert "qdb_general_ledger_workbook" not in found_payload["expanded_queries"]
        assert found_payload["records"][0]["matched_query"] == "pnl_attribution.volume_rate"
        assert found_payload["records"][0]["stream"] == "source_manifest_latest"
        assert found_payload["records"][0]["record"]["tables_used"] == [
            "fact_formal_pnl_fi",
            "fact_nonstd_pnl_bridge",
            "fact_formal_zqtz_balance_daily",
        ]
    finally:
        server.close()


def test_lineage_evidence_mcp_maps_balance_movement_page_to_movement_records(tmp_path: Path) -> None:
    governance = tmp_path / "governance"
    governance.mkdir()
    (governance / "cache_manifest.jsonl").write_text(
        json.dumps(
            {
                "cache_key": "accounting_asset_movement.monthly",
                "cache_version": "cv_accounting_asset_movement_v1",
                "result_kind_family": "balance-analysis.movement",
                "module_name": "accounting_asset_movement",
                "rule_version": "rv_accounting_asset_movement_v2",
                "fact_tables": ["fact_accounting_asset_movement_monthly"],
                "input_sources": ["fact_formal_zqtz_balance_daily"],
                "created_at": "2026-04-12T14:31:38.517141Z",
            }
        )
        + "\n",
        encoding="utf-8",
    )

    server = McpProcess("lineage-evidence", env={"MOSS_GOVERNANCE_PATH": str(governance)})
    try:
        server.request("initialize")
        server.notify("notifications/initialized")

        found = server.request(
            "tools/call",
            {"name": "find_lineage_records", "arguments": {"query": "PAGE-BAL-MOVE-001", "max_results": 5}},
        )
        found_payload = json.loads(found["content"][0]["text"])

        assert found_payload["query"] == "PAGE-BAL-MOVE-001"
        assert "/ui/balance-movement-analysis" in found_payload["expanded_queries"]
        assert "/ui/balance-movement-analysis/dates" in found_payload["expanded_queries"]
        assert "balance-analysis.movement.detail" in found_payload["expanded_queries"]
        assert "balance-analysis.movement.dates" in found_payload["expanded_queries"]
        assert "accounting_asset_movement" in found_payload["expanded_queries"]
        assert "fact_accounting_asset_movement_monthly" in found_payload["expanded_queries"]
        assert "fact_formal_zqtz_balance_daily" in found_payload["expanded_queries"]
        assert "rv_accounting_asset_movement_v2" in found_payload["expanded_queries"]
        assert "AccountingAssetMovementPayload" in found_payload["expanded_queries"]
        assert "MTR-BMV-001" in found_payload["expanded_queries"]
        assert "MTR-BMV-004" in found_payload["expanded_queries"]
        assert "MTR-BAL-001" not in found_payload["expanded_queries"]
        assert "GS-BAL-OVERVIEW-A" not in found_payload["expanded_queries"]
        assert "fact_formal_pnl_fi" not in found_payload["expanded_queries"]
        assert "qdb_general_ledger_workbook" not in found_payload["expanded_queries"]
        assert found_payload["records"][0]["matched_query"] == "balance-analysis.movement"
        assert found_payload["records"][0]["stream"] == "cache_manifest"
        assert found_payload["records"][0]["record"]["fact_tables"] == ["fact_accounting_asset_movement_monthly"]
        assert found_payload["records"][0]["record"]["input_sources"] == ["fact_formal_zqtz_balance_daily"]
    finally:
        server.close()


def test_lineage_evidence_mcp_maps_liability_analytics_page_to_mixed_source_records(
    tmp_path: Path,
) -> None:
    governance = tmp_path / "governance"
    governance.mkdir()
    (governance / "cache_manifest.jsonl").write_text(
        json.dumps(
            {
                "cache_key": "liability_analytics:compat:daily",
                "result_kind": "liability_analytics.risk_buckets",
                "source_surface": "formal_liability",
                "basis": "analytical",
                "source_tables": [
                    "fact_formal_zqtz_balance_daily",
                    "fact_formal_tyw_balance_daily",
                    "zqtz_bond_daily_snapshot",
                    "tyw_interbank_daily_snapshot",
                ],
                "rule_version": "rv_liability_analytics_compat_v1",
                "cache_version": "cv_liability_analytics_v1",
                "created_at": "2026-04-12T14:31:38.517141Z",
            }
        )
        + "\n",
        encoding="utf-8",
    )

    server = McpProcess("lineage-evidence", env={"MOSS_GOVERNANCE_PATH": str(governance)})
    try:
        server.request("initialize")
        server.notify("notifications/initialized")

        found = server.request(
            "tools/call",
            {"name": "find_lineage_records", "arguments": {"query": "PAGE-LIAB-ANALYTICS-001", "max_results": 5}},
        )
        found_payload = json.loads(found["content"][0]["text"])

        assert found_payload["query"] == "PAGE-LIAB-ANALYTICS-001"
        assert "/api/risk/buckets" in found_payload["expanded_queries"]
        assert "/api/analysis/yield_metrics" in found_payload["expanded_queries"]
        assert "/api/analysis/yield-by-period" in found_payload["expanded_queries"]
        assert "/api/analysis/liabilities/counterparty" in found_payload["expanded_queries"]
        assert "/api/liabilities/monthly" in found_payload["expanded_queries"]
        assert "/api/analysis/liabilities/cockpit-warnings" in found_payload["expanded_queries"]
        assert "/api/analysis/liabilities/contribution-split" in found_payload["expanded_queries"]
        assert "liability_analytics.risk_buckets" in found_payload["expanded_queries"]
        assert "liability_analytics.yield_metrics" in found_payload["expanded_queries"]
        assert "liability_analytics.yield_by_period" in found_payload["expanded_queries"]
        assert "liability_analytics.counterparty" in found_payload["expanded_queries"]
        assert "liability_analytics.monthly" in found_payload["expanded_queries"]
        assert "formal_liability" in found_payload["expanded_queries"]
        assert "fact_formal_zqtz_balance_daily" in found_payload["expanded_queries"]
        assert "fact_formal_tyw_balance_daily" in found_payload["expanded_queries"]
        assert "zqtz_bond_daily_snapshot" in found_payload["expanded_queries"]
        assert "tyw_interbank_daily_snapshot" in found_payload["expanded_queries"]
        assert "MTR-LIAB-001" in found_payload["expanded_queries"]
        assert "MTR-LIAB-007" in found_payload["expanded_queries"]
        assert "fact_nonstd_pnl_bridge" not in found_payload["expanded_queries"]
        assert "qdb_general_ledger_workbook" not in found_payload["expanded_queries"]
        assert "GS-BAL-OVERVIEW-A" not in found_payload["expanded_queries"]
        assert "GS-EXEC-OVERVIEW-A" not in found_payload["expanded_queries"]
        assert found_payload["records"][0]["matched_query"] == "liability_analytics.risk_buckets"
        assert found_payload["records"][0]["stream"] == "cache_manifest"
        assert found_payload["records"][0]["record"]["source_surface"] == "formal_liability"
        assert found_payload["records"][0]["record"]["basis"] == "analytical"
    finally:
        server.close()


def test_lineage_evidence_mcp_maps_bond_dashboard_page_to_candidate_bond_analytics_records(
    tmp_path: Path,
) -> None:
    governance = tmp_path / "governance"
    governance.mkdir()
    (governance / "cache_manifest.jsonl").write_text(
        json.dumps(
            {
                "cache_key": "bond_dashboard:headline",
                "result_kind": "bond_dashboard.headline_kpis",
                "source_surface": "bond_analytics",
                "basis": "analytical",
                "tables_used": ["fact_formal_bond_analytics_daily"],
                "golden_sample": "GS-BOND-HEADLINE-A",
                "rule_version": "rv_bond_analytics_formal_materialize_v1",
                "cache_version": "cv_bond_analytics_formal__rv_bond_analytics_formal_materialize_v1",
                "created_at": "2026-04-12T14:31:38.517141Z",
            }
        )
        + "\n",
        encoding="utf-8",
    )

    server = McpProcess("lineage-evidence", env={"MOSS_GOVERNANCE_PATH": str(governance)})
    try:
        server.request("initialize")
        server.notify("notifications/initialized")

        found = server.request(
            "tools/call",
            {"name": "find_lineage_records", "arguments": {"query": "PAGE-BOND-001", "max_results": 5}},
        )
        found_payload = json.loads(found["content"][0]["text"])

        assert found_payload["query"] == "PAGE-BOND-001"
        assert "/api/bond-dashboard/headline-kpis" in found_payload["expanded_queries"]
        assert "/api/bond-dashboard/risk-indicators" in found_payload["expanded_queries"]
        assert "/api/bond-dashboard/business-type-metrics" in found_payload["expanded_queries"]
        assert "bond_dashboard.headline_kpis" in found_payload["expanded_queries"]
        assert "bond_dashboard.risk_indicators" in found_payload["expanded_queries"]
        assert "bond_dashboard.business_type_metrics" in found_payload["expanded_queries"]
        assert "bond_analytics" in found_payload["expanded_queries"]
        assert "fact_formal_bond_analytics_daily" in found_payload["expanded_queries"]
        assert "GS-BOND-HEADLINE-A" in found_payload["expanded_queries"]
        assert "MTR-BOND-001" in found_payload["expanded_queries"]
        assert "MTR-BOND-004" in found_payload["expanded_queries"]
        assert "MTR-BAL-001" not in found_payload["expanded_queries"]
        assert "GS-BAL-OVERVIEW-A" not in found_payload["expanded_queries"]
        assert "PAGE-RISK-001" not in found_payload["expanded_queries"]
        assert "GS-RISK-A" not in found_payload["expanded_queries"]
        assert "qdb_general_ledger_workbook" not in found_payload["expanded_queries"]
        assert found_payload["records"][0]["matched_query"] == "bond_dashboard.headline_kpis"
        assert found_payload["records"][0]["stream"] == "cache_manifest"
        assert found_payload["records"][0]["record"]["basis"] == "analytical"
        assert found_payload["records"][0]["record"]["source_surface"] == "bond_analytics"
        assert found_payload["records"][0]["record"]["tables_used"] == ["fact_formal_bond_analytics_daily"]
    finally:
        server.close()


def test_lineage_evidence_mcp_maps_positions_page_to_candidate_snapshot_records(
    tmp_path: Path,
) -> None:
    governance = tmp_path / "governance"
    governance.mkdir()
    (governance / "cache_manifest.jsonl").write_text(
        json.dumps(
            {
                "cache_key": "positions:bonds:list",
                "result_kind": "positions.bonds.list",
                "source_surface": "positions_snapshot",
                "basis": "analytical",
                "formal_use_allowed": False,
                "quality_flag": "warning",
                "date_basis": "positions_snapshot_report_date",
                "tables_used": ["zqtz_bond_daily_snapshot"],
                "rule_version": "rv_positions_snapshot_read_v1",
                "created_at": "2026-04-12T14:31:38.517141Z",
            }
        )
        + "\n"
        + json.dumps(
            {
                "cache_key": "positions:interbank:list",
                "result_kind": "positions.interbank.list",
                "source_surface": "positions_snapshot",
                "basis": "analytical",
                "formal_use_allowed": False,
                "quality_flag": "warning",
                "date_basis": "positions_snapshot_report_date",
                "tables_used": ["tyw_interbank_daily_snapshot"],
                "rule_version": "rv_positions_snapshot_read_v1",
                "created_at": "2026-04-12T14:31:38.517141Z",
            }
        )
        + "\n",
        encoding="utf-8",
    )

    server = McpProcess("lineage-evidence", env={"MOSS_GOVERNANCE_PATH": str(governance)})
    try:
        server.request("initialize")
        server.notify("notifications/initialized")

        found = server.request(
            "tools/call",
            {"name": "find_lineage_records", "arguments": {"query": "PAGE-POS-001", "max_results": 5}},
        )
        found_payload = json.loads(found["content"][0]["text"])

        assert found_payload["query"] == "PAGE-POS-001"
        assert "/api/positions/bonds" in found_payload["expanded_queries"]
        assert "/api/positions/interbank" in found_payload["expanded_queries"]
        assert "/api/positions/bonds/sub_types" in found_payload["expanded_queries"]
        assert "/api/positions/interbank/product_types" in found_payload["expanded_queries"]
        assert "/api/positions/counterparty/bonds" in found_payload["expanded_queries"]
        assert "/api/positions/counterparty/interbank/split" in found_payload["expanded_queries"]
        assert "/api/positions/stats/rating" in found_payload["expanded_queries"]
        assert "/api/positions/stats/industry" in found_payload["expanded_queries"]
        assert "/api/positions/customer/details" in found_payload["expanded_queries"]
        assert "/api/positions/customer/trend" in found_payload["expanded_queries"]
        assert "positions.bonds.list" in found_payload["expanded_queries"]
        assert "positions.interbank.list" in found_payload["expanded_queries"]
        assert "positions.counterparty.bonds" in found_payload["expanded_queries"]
        assert "positions.counterparty.interbank.split" in found_payload["expanded_queries"]
        assert "positions.stats.rating" in found_payload["expanded_queries"]
        assert "positions.stats.industry" in found_payload["expanded_queries"]
        assert "positions.customer.details" in found_payload["expanded_queries"]
        assert "positions.customer.trend" in found_payload["expanded_queries"]
        assert "positions_snapshot" in found_payload["expanded_queries"]
        assert "zqtz_bond_daily_snapshot" in found_payload["expanded_queries"]
        assert "tyw_interbank_daily_snapshot" in found_payload["expanded_queries"]
        assert "MTR-POS-001" in found_payload["expanded_queries"]
        assert "MTR-POS-002" in found_payload["expanded_queries"]
        assert "fact_formal_pnl_fi" not in found_payload["expanded_queries"]
        assert "product_category_pnl_formal_read_model" not in found_payload["expanded_queries"]
        assert "bond_dashboard.headline_kpis" not in found_payload["expanded_queries"]
        assert "fact_formal_bond_analytics_daily" not in found_payload["expanded_queries"]
        assert "GS-BAL-OVERVIEW-A" not in found_payload["expanded_queries"]
        assert "MTR-BAL-001" not in found_payload["expanded_queries"]
        assert found_payload["records"][0]["matched_query"] == "positions.bonds.list"
        assert found_payload["records"][0]["stream"] == "cache_manifest"
        assert found_payload["records"][0]["record"]["basis"] == "analytical"
        assert found_payload["records"][0]["record"]["formal_use_allowed"] is False
        assert found_payload["records"][0]["record"]["quality_flag"] == "warning"
        assert found_payload["records"][0]["record"]["tables_used"] == ["zqtz_bond_daily_snapshot"]
        assert found_payload["records"][1]["matched_query"] == "positions.interbank.list"
        assert found_payload["records"][1]["record"]["tables_used"] == ["tyw_interbank_daily_snapshot"]
    finally:
        server.close()


def test_lineage_evidence_mcp_maps_market_data_page_to_mixed_source_records(
    tmp_path: Path,
) -> None:
    governance = tmp_path / "governance"
    governance.mkdir()
    records = [
        {
            "cache_key": "market_data:preview:macro_foundation",
            "result_kind": "preview.macro-foundation",
            "source_surface": "macro_preview",
            "basis": "analytical",
            "tables_used": ["fact_choice_macro_daily", "market_data_series_category"],
            "rule_version": "rv_phase1_macro_vendor_v1",
        },
        {
            "cache_key": "market_data:rates:formal_fragment",
            "result_kind": "market_data.rates",
            "source_surface": "market_data",
            "basis": "formal",
            "formal_use_allowed": True,
            "tables_used": ["fact_choice_macro_daily", "market_data_series_category"],
            "rule_version": "rv_market_data_rates_formal_v1",
        },
        {
            "cache_key": "market_data:fx:formal_status",
            "result_kind": "fx.formal.status",
            "source_surface": "formal_fx_status",
            "basis": "formal",
            "tables_used": ["fx_daily_mid"],
            "rule_version": "rv_fx_formal_mid_v1",
        },
        {
            "cache_key": "market_data:fx:analytical",
            "result_kind": "fx.analytical.groups",
            "source_surface": "fx_analytical",
            "basis": "analytical",
            "tables_used": ["fact_choice_macro_daily", "fx_daily_mid"],
            "rule_version": "rv_fx_analytical_v1",
        },
        {
            "cache_key": "market_data:ncd:proxy",
            "result_kind": "market_data.ncd_proxy",
            "source_surface": "ncd_funding_proxy",
            "basis": "analytical",
            "is_actual_ncd_matrix": False,
            "tables_used": ["fact_choice_macro_daily"],
            "rule_version": "rv_ncd_proxy_v1",
        },
        {
            "cache_key": "market_data:livermore:strategy",
            "result_kind": "market_data.livermore",
            "source_surface": "livermore_analytical",
            "basis": "analytical",
            "tables_used": [
                "fact_choice_macro_daily",
                "livermore_position_snapshot",
                "choice_stock_daily_observation",
                "fact_livermore_gate_supplement_daily",
            ],
            "rule_version": "rv_livermore_strategy_v1",
        },
        {
            "cache_key": "market_data:macro_bond_linkage",
            "result_kind": "macro_bond_linkage.analysis",
            "source_surface": "macro_bond_linkage",
            "basis": "analytical",
            "tables_used": ["fact_choice_macro_daily", "yield_curve_daily"],
            "rule_version": "rv_macro_bond_linkage_v1",
        },
    ]
    (governance / "cache_manifest.jsonl").write_text(
        "".join(json.dumps(record) + "\n" for record in records),
        encoding="utf-8",
    )

    server = McpProcess("lineage-evidence", env={"MOSS_GOVERNANCE_PATH": str(governance)})
    try:
        server.request("initialize")
        server.notify("notifications/initialized")

        found = server.request(
            "tools/call",
            {"name": "find_lineage_records", "arguments": {"query": "PAGE-MKT-001", "max_results": 10}},
        )
        found_payload = json.loads(found["content"][0]["text"])

        assert found_payload["query"] == "PAGE-MKT-001"
        assert "/ui/preview/macro-foundation" in found_payload["expanded_queries"]
        assert "/ui/market-data/rates" in found_payload["expanded_queries"]
        assert "/ui/market-data/fx/formal-status" in found_payload["expanded_queries"]
        assert "/ui/market-data/fx/analytical" in found_payload["expanded_queries"]
        assert "/ui/market-data/ncd-funding-proxy" in found_payload["expanded_queries"]
        assert "/api/macro-bond-linkage" in found_payload["expanded_queries"]
        assert "/ui/market-data/livermore" in found_payload["expanded_queries"]
        assert "preview.macro-foundation" in found_payload["expanded_queries"]
        assert "market_data.rates" in found_payload["expanded_queries"]
        assert "market_data.catalog" in found_payload["expanded_queries"]
        assert "macro.choice.latest" in found_payload["expanded_queries"]
        assert "fx.formal.status" in found_payload["expanded_queries"]
        assert "fx.analytical.groups" in found_payload["expanded_queries"]
        assert "market_data.ncd_proxy" in found_payload["expanded_queries"]
        assert "market_data.livermore" in found_payload["expanded_queries"]
        assert "macro_bond_linkage.analysis" in found_payload["expanded_queries"]
        assert "fact_choice_macro_daily" in found_payload["expanded_queries"]
        assert "market_data_series_category" in found_payload["expanded_queries"]
        assert "fx_daily_mid" in found_payload["expanded_queries"]
        assert "livermore_position_snapshot" in found_payload["expanded_queries"]
        assert "choice_stock_daily_observation" in found_payload["expanded_queries"]
        assert "fact_livermore_gate_supplement_daily" in found_payload["expanded_queries"]
        assert "MTR-MKT-001" in found_payload["expanded_queries"]
        assert "GAP-MKT-DATA" in found_payload["expanded_queries"]
        assert "fact_formal_pnl_fi" not in found_payload["expanded_queries"]
        assert "product_category_pnl_formal_read_model" not in found_payload["expanded_queries"]
        assert "fact_formal_zqtz_balance_daily" not in found_payload["expanded_queries"]
        assert "positions.bonds.list" not in found_payload["expanded_queries"]
        assert "bond_dashboard.headline_kpis" not in found_payload["expanded_queries"]
        assert "GS-BOND-HEADLINE-A" not in found_payload["expanded_queries"]
        assert found_payload["records"][0]["matched_query"] == "preview.macro-foundation"
        assert found_payload["records"][0]["record"]["basis"] == "analytical"
        assert found_payload["records"][1]["matched_query"] == "market_data.rates"
        assert found_payload["records"][1]["record"]["basis"] == "formal"
        assert found_payload["records"][2]["matched_query"] == "fx.formal.status"
        assert found_payload["records"][3]["matched_query"] == "fx.analytical.groups"
        assert found_payload["records"][4]["matched_query"] == "market_data.ncd_proxy"
        assert found_payload["records"][4]["record"]["is_actual_ncd_matrix"] is False
        assert found_payload["records"][5]["matched_query"] == "market_data.livermore"
        assert "livermore_position_snapshot" in found_payload["records"][5]["record"]["tables_used"]
    finally:
        server.close()


def test_lineage_evidence_mcp_maps_operations_page_to_mixed_source_records(
    tmp_path: Path,
) -> None:
    governance = tmp_path / "governance"
    governance.mkdir()
    records = [
        {
            "cache_key": "operations:product-category-headline",
            "result_kind": "product_category_pnl.detail",
            "source_surface": "product_category_pnl",
            "basis": "formal",
            "tables_used": [
                "product_category_pnl_formal_read_model",
                "product_category_pnl_canonical_fact",
            ],
            "golden_sample": "GS-PROD-CAT-PNL-A",
            "metric_ids": ["MTR-PCP-001", "MTR-PCP-002", "MTR-PCP-003"],
        },
        {
            "cache_key": "operations:balance-overview-supplemental",
            "result_kind": "balance-analysis.overview",
            "source_surface": "formal_balance",
            "basis": "formal",
            "role": "supplemental_topic_entry",
            "tables_used": ["fact_formal_zqtz_balance_daily", "fact_formal_tyw_balance_daily"],
            "golden_sample": "GS-BAL-OVERVIEW-A",
        },
        {
            "cache_key": "operations:source-preview",
            "result_kind": "preview.source-foundation",
            "source_surface": "source_preview",
            "basis": "preview",
            "tables_used": ["source_preview_manifest"],
        },
        {
            "cache_key": "operations:macro-preview",
            "result_kind": "preview.macro-foundation",
            "source_surface": "macro_preview",
            "basis": "analytical",
            "tables_used": ["fact_choice_macro_daily"],
        },
        {
            "cache_key": "operations:fx-status",
            "result_kind": "fx.formal.status",
            "source_surface": "formal_fx_status",
            "basis": "formal",
            "tables_used": ["fx_daily_mid"],
        },
        {
            "cache_key": "operations:choice-news",
            "result_kind": "news.choice.latest",
            "source_surface": "choice_news",
            "basis": "analytical",
            "tables_used": ["choice_news_event"],
        },
    ]
    (governance / "cache_manifest.jsonl").write_text(
        "".join(json.dumps(record) + "\n" for record in records),
        encoding="utf-8",
    )

    server = McpProcess("lineage-evidence", env={"MOSS_GOVERNANCE_PATH": str(governance)})
    try:
        server.request("initialize")
        server.notify("notifications/initialized")

        found = server.request(
            "tools/call",
            {"name": "find_lineage_records", "arguments": {"query": "PAGE-OPS-001", "max_results": 10}},
        )
        found_payload = json.loads(found["content"][0]["text"])

        assert found_payload["query"] == "PAGE-OPS-001"
        assert "/ui/pnl/product-category" in found_payload["expanded_queries"]
        assert "/ui/pnl/product-category/dates" in found_payload["expanded_queries"]
        assert "/ui/balance-analysis/overview" in found_payload["expanded_queries"]
        assert "/ui/preview/source-foundation" in found_payload["expanded_queries"]
        assert "/ui/preview/macro-foundation" in found_payload["expanded_queries"]
        assert "/ui/macro/choice-series/latest" in found_payload["expanded_queries"]
        assert "/ui/market-data/fx/formal-status" in found_payload["expanded_queries"]
        assert "/ui/news/choice-events/latest" in found_payload["expanded_queries"]
        assert "product_category_pnl.detail" in found_payload["expanded_queries"]
        assert "product_category_pnl_formal_read_model" in found_payload["expanded_queries"]
        assert "product_category_pnl_canonical_fact" in found_payload["expanded_queries"]
        assert "GS-PROD-CAT-PNL-A" in found_payload["expanded_queries"]
        assert "MTR-PCP-001" in found_payload["expanded_queries"]
        assert "MTR-PCP-003" in found_payload["expanded_queries"]
        assert "balance-analysis.overview" in found_payload["expanded_queries"]
        assert "formal_balance" in found_payload["expanded_queries"]
        assert "fact_formal_zqtz_balance_daily" in found_payload["expanded_queries"]
        assert "fact_formal_tyw_balance_daily" in found_payload["expanded_queries"]
        assert "GS-BAL-OVERVIEW-A" in found_payload["expanded_queries"]
        assert "MTR-BAL-001" in found_payload["expanded_queries"]
        assert "MTR-BAL-102" in found_payload["expanded_queries"]
        assert "preview.source-foundation" in found_payload["expanded_queries"]
        assert "preview.macro-foundation" in found_payload["expanded_queries"]
        assert "macro.choice.latest" in found_payload["expanded_queries"]
        assert "fx.formal.status" in found_payload["expanded_queries"]
        assert "news.choice.latest" in found_payload["expanded_queries"]
        assert "choice_news_event" in found_payload["expanded_queries"]
        assert "GAP-OPS-MACRO-FX" in found_payload["expanded_queries"]
        assert "MTR-OPS-001" not in found_payload["expanded_queries"]
        assert "fact_formal_pnl_fi" not in found_payload["expanded_queries"]
        assert "balance-analysis.workbook" not in found_payload["expanded_queries"]
        assert "GS-BAL-WORKBOOK-A" not in found_payload["expanded_queries"]
        assert "bond_dashboard.headline_kpis" not in found_payload["expanded_queries"]
        assert "positions.bonds.list" not in found_payload["expanded_queries"]
        assert found_payload["records"][0]["matched_query"] == "product_category_pnl.detail"
        assert found_payload["records"][0]["record"]["basis"] == "formal"
        assert found_payload["records"][1]["matched_query"] == "balance-analysis.overview"
        assert found_payload["records"][1]["record"]["role"] == "supplemental_topic_entry"
        assert found_payload["records"][2]["matched_query"] == "preview.source-foundation"
        assert found_payload["records"][3]["matched_query"] == "preview.macro-foundation"
        assert found_payload["records"][4]["matched_query"] == "fx.formal.status"
        assert found_payload["records"][5]["matched_query"] == "news.choice.latest"
    finally:
        server.close()


def test_lineage_evidence_mcp_maps_ledger_pnl_page_to_ledger_source_contracts(tmp_path: Path) -> None:
    governance = tmp_path / "governance"
    governance.mkdir()
    (governance / "source_manifest_latest.jsonl").write_text(
        json.dumps(
            {
                "source_version": "sv_ledger_pnl_fixture",
                "rule_version": "rv_ledger_pnl_fixture",
                "tables_used": ["qdb_general_ledger_workbook"],
                "created_at": "2026-04-12T14:31:38.517141Z",
            }
        )
        + "\n",
        encoding="utf-8",
    )

    server = McpProcess("lineage-evidence", env={"MOSS_GOVERNANCE_PATH": str(governance)})
    try:
        server.request("initialize")
        server.notify("notifications/initialized")

        found = server.request(
            "tools/call",
            {"name": "find_lineage_records", "arguments": {"query": "PAGE-LEDGER-PNL-001", "max_results": 5}},
        )
        found_payload = json.loads(found["content"][0]["text"])

        assert found_payload["query"] == "PAGE-LEDGER-PNL-001"
        assert "/api/ledger-pnl/summary" in found_payload["expanded_queries"]
        assert "ledger_pnl." in found_payload["expanded_queries"]
        assert "qdb_general_ledger_workbook" in found_payload["expanded_queries"]
        assert "formal_financial_indicator_source_contract" in found_payload["expanded_queries"]
        assert "GS-LEDGER-PNL-FIN-IND-202603-B" in found_payload["expanded_queries"]
        assert "fact_formal_pnl_fi" not in found_payload["expanded_queries"]
        assert "fact_nonstd_pnl_bridge" not in found_payload["expanded_queries"]
        assert found_payload["records"][0]["matched_query"] == "qdb_general_ledger_workbook"
        assert found_payload["records"][0]["stream"] == "source_manifest_latest"
        assert found_payload["records"][0]["record"]["tables_used"] == ["qdb_general_ledger_workbook"]
    finally:
        server.close()


def test_lineage_evidence_mcp_maps_product_category_page_aliases_to_formal_model_records(
    tmp_path: Path,
) -> None:
    governance = tmp_path / "governance"
    governance.mkdir()
    (governance / "cache_manifest.jsonl").write_text(
        json.dumps(
            {
                "cache_version": "cv_product_category_fixture",
                "table_name": "product_category_pnl_formal_read_model",
                "source_tables": ["product_category_pnl_canonical_fact"],
                "golden_sample": "GS-PROD-CAT-PNL-A",
                "created_at": "2026-04-12T14:31:38.517141Z",
            }
        )
        + "\n",
        encoding="utf-8",
    )

    server = McpProcess("lineage-evidence", env={"MOSS_GOVERNANCE_PATH": str(governance)})
    try:
        server.request("initialize")
        server.notify("notifications/initialized")

        for page_id in ("PAGE-PROD-CAT-PNL-001", "PAGE-PROD-CAT-001"):
            found = server.request(
                "tools/call",
                {"name": "find_lineage_records", "arguments": {"query": page_id, "max_results": 5}},
            )
            found_payload = json.loads(found["content"][0]["text"])

            assert found_payload["query"] == page_id
            assert "product-category-pnl" in found_payload["expanded_queries"]
            assert "/ui/pnl/product-category" in found_payload["expanded_queries"]
            assert "product_category_pnl.detail" in found_payload["expanded_queries"]
            assert "product_category_pnl_formal_read_model" in found_payload["expanded_queries"]
            assert "product_category_pnl_canonical_fact" in found_payload["expanded_queries"]
            assert "GS-PROD-CAT-PNL-A" in found_payload["expanded_queries"]
            assert "MTR-PCP-001" in found_payload["expanded_queries"]
            assert "fact_formal_pnl_fi" not in found_payload["expanded_queries"]
            assert "qdb_general_ledger_workbook" not in found_payload["expanded_queries"]
            assert found_payload["records"][0]["matched_query"] == "product_category_pnl_formal_read_model"
            assert found_payload["records"][0]["stream"] == "cache_manifest"
            assert found_payload["records"][0]["record"]["table_name"] == "product_category_pnl_formal_read_model"
            assert found_payload["records"][0]["record"]["source_tables"] == ["product_category_pnl_canonical_fact"]
    finally:
        server.close()


def test_data_catalog_mcp_is_safe_when_duckdb_is_missing(tmp_path: Path) -> None:
    missing_duckdb = tmp_path / "missing.duckdb"
    server = McpProcess("data-catalog", env={"MOSS_DUCKDB_PATH": str(missing_duckdb)})
    try:
        server.request("initialize")
        server.notify("notifications/initialized")

        summary = server.request("resources/read", {"uri": "moss://data-catalog/summary"})
        payload = json.loads(summary["contents"][0]["text"])
        assert payload["duckdb_exists"] is False
        assert payload["tables"] == []
        assert payload["schema_registry"]["exists"] is True
    finally:
        server.close()
