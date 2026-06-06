from __future__ import annotations

import argparse
import json
import os
import re
import sys
from collections.abc import Callable, Iterable
from pathlib import Path
from typing import Any

PROTOCOL_VERSION = "2024-11-05"
REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DUCKDB_PATH = REPO_ROOT / "data" / "moss.duckdb"
DEFAULT_GOVERNANCE_DIR = REPO_ROOT / "data" / "governance"
DEFAULT_EVIDENCE_READINESS_PAGES = [
    "PAGE-LEDGER-PNL-001",
    "PAGE-BOND-001",
    "PAGE-POS-001",
    "PAGE-MKT-001",
    "GAP-STOCK-ANALYSIS-PAGE",
    "PAGE-OPS-001",
]
DEFAULT_CATALOG_DATE_EXCLUDED_PAGE_IDS = {"GAP-AVERAGE-BALANCE-PAGE"}
EVIDENCE_READINESS_STATUS_BY_PAGE_ID = {
    "GAP-CROSS-ASSET-PAGE": "mixed_source_or_observational",
    "GAP-DECISION-ITEMS-PAGE": "candidate_or_pending",
    "GAP-KPI-PERFORMANCE-PAGE": "candidate_or_pending",
    "GAP-AVERAGE-BALANCE-PAGE": "candidate_or_pending",
    "PAGE-BOND-ANALYSIS-001": "candidate_or_pending",
    "GAP-STOCK-ANALYSIS-PAGE": "gap_or_observational",
    "PAGE-AGENT-001": "mixed_source_or_observational",
    "PAGE-BAL-MOVE-001": "candidate_or_pending",
    "PAGE-BALANCE-001": "formal_or_governed",
    "PAGE-BOND-001": "candidate_or_pending",
    "PAGE-BRIDGE-001": "formal_or_governed",
    "PAGE-CUBE-QUERY-001": "candidate_or_pending",
    "PAGE-DASH-001": "mixed_source_or_observational",
    "PAGE-EXEC-OVERVIEW-001": "mixed_source_or_observational",
    "PAGE-EXEC-PNL-ATTR-001": "mixed_source_or_observational",
    "PAGE-EXEC-SUMMARY-001": "mixed_source_or_observational",
    "PAGE-LEDGER-PNL-001": "candidate_or_pending",
    "PAGE-LIAB-ANALYTICS-001": "mixed_source_or_observational",
    "PAGE-MACRO-OBS-001": "mixed_source_or_observational",
    "PAGE-MACRO-TOOLKIT-001": "mixed_source_or_observational",
    "PAGE-MKT-001": "mixed_source_or_observational",
    "PAGE-OPS-001": "mixed_source_or_observational",
    "PAGE-PNL-001": "formal_or_governed",
    "PAGE-PNL-ATTR-WB-001": "candidate_or_pending",
    "PAGE-PNL-BY-BUSINESS-001": "candidate_or_pending",
    "PAGE-POS-001": "candidate_or_pending",
    "PAGE-PROD-CAT-001": "formal_or_governed",
    "PAGE-PORTFOLIO-HOME-001": "mixed_source_or_observational",
    "PAGE-MARKET-HOME-001": "mixed_source_or_observational",
    "PAGE-RISK-001": "formal_or_governed",
    "PAGE-RISK-HOME-001": "mixed_source_or_observational",
    "PAGE-PERFORMANCE-HOME-001": "mixed_source_or_observational",
    "PAGE-REPORTS-HOME-001": "mixed_source_or_observational",
}
CANDIDATE_METRIC_WATCHLIST = [
    {
        "metric_id": f"MTR-CFP-{index:03d}",
        "page": "/cashflow-projection",
        "status": "candidate page-contract-pending",
        "formal_use_allowed": False,
        "residual_gap": "Needs approved page contract, bound sample, direct lineage records, and date/catalog review.",
    }
    for index in range(1, 5)
] + [
    {
        "metric_id": f"MTR-CON-{index:03d}",
        "page": "/concentration-monitor",
        "status": "candidate page-contract-pending",
        "formal_use_allowed": False,
        "residual_gap": "Needs approved page contract, bound sample, lineage records, and date/catalog review.",
    }
    for index in range(1, 5)
]
PAGE_CATALOG_DATE_TABLES = {
    "PAGE-PROD-CAT-001": [
        "product_category_pnl_formal_read_model",
        "product_category_pnl_canonical_fact",
    ],
    "PAGE-BALANCE-001": [
        "fact_formal_zqtz_balance_daily",
        "fact_formal_tyw_balance_daily",
    ],
    "PAGE-PNL-001": [
        "fact_formal_pnl_fi",
        "fact_nonstd_pnl_bridge",
    ],
    "PAGE-LEDGER-PNL-001": [
        "qdb_general_ledger_workbook",
        "ledger_import_batch",
        "ledger_raw_row",
    ],
    "PAGE-BRIDGE-001": [
        "fact_formal_pnl_fi",
        "fact_nonstd_pnl_bridge",
    ],
    "PAGE-RISK-001": [
        "fact_formal_risk_tensor_daily",
    ],
    "PAGE-DASH-001": [
        "fact_formal_zqtz_balance_daily",
        "fact_formal_tyw_balance_daily",
        "fact_formal_pnl_fi",
        "fact_nonstd_pnl_bridge",
        "zqtz_bond_daily_snapshot",
        "tyw_interbank_daily_snapshot",
        "fact_formal_bond_analytics_daily",
        "fx_daily_mid",
    ],
    "PAGE-EXEC-OVERVIEW-001": [
        "fact_formal_zqtz_balance_daily",
        "fact_formal_tyw_balance_daily",
        "fact_formal_pnl_fi",
        "fact_nonstd_pnl_bridge",
        "zqtz_bond_daily_snapshot",
        "tyw_interbank_daily_snapshot",
        "fact_formal_bond_analytics_daily",
    ],
    "PAGE-BAL-MOVE-001": [
        "fact_accounting_asset_movement_monthly",
        "fact_formal_zqtz_balance_daily",
    ],
    "PAGE-PNL-BY-BUSINESS-001": [
        "fact_formal_pnl_fi",
        "fact_nonstd_pnl_bridge",
        "fact_formal_zqtz_balance_daily",
        "fact_pnl_by_business_precompute",
    ],
    "PAGE-PNL-ATTR-WB-001": [
        "fact_formal_pnl_fi",
        "fact_nonstd_pnl_bridge",
        "fact_formal_zqtz_balance_daily",
        "fact_formal_bond_analytics_daily",
        "yield_curve_daily",
    ],
    "PAGE-CUBE-QUERY-001": [
        "fact_formal_bond_analytics_daily",
        "fact_formal_pnl_fi",
        "fact_formal_zqtz_balance_daily",
        "product_category_pnl_formal_read_model",
    ],
    "PAGE-PORTFOLIO-HOME-001": [
        "fact_formal_zqtz_balance_daily",
        "fact_formal_tyw_balance_daily",
        "fact_formal_bond_analytics_daily",
        "zqtz_bond_daily_snapshot",
        "tyw_interbank_daily_snapshot",
        "fact_formal_pnl_fi",
        "fact_nonstd_pnl_bridge",
        "fact_formal_risk_tensor_daily",
    ],
    "PAGE-LIAB-ANALYTICS-001": [
        "fact_formal_zqtz_balance_daily",
        "fact_formal_tyw_balance_daily",
        "zqtz_bond_daily_snapshot",
        "tyw_interbank_daily_snapshot",
    ],
    "PAGE-BOND-001": [
        "fact_formal_bond_analytics_daily",
    ],
    "PAGE-BOND-ANALYSIS-001": [
        "fact_formal_bond_analytics_daily",
    ],
    "PAGE-POS-001": [
        "zqtz_bond_daily_snapshot",
        "tyw_interbank_daily_snapshot",
    ],
    "PAGE-MKT-001": [
        "fact_choice_macro_daily",
        "fx_daily_mid",
        "market_data_series_category",
        "livermore_position_snapshot",
        "choice_stock_daily_observation",
        "fact_livermore_gate_supplement_daily",
    ],
    "GAP-STOCK-ANALYSIS-PAGE": [
        "livermore_position_snapshot",
        "livermore_candidate_history",
        "choice_stock_daily_observation",
        "fact_livermore_gate_supplement_daily",
    ],
    "GAP-AVERAGE-BALANCE-PAGE": [
        "fact_formal_zqtz_balance_daily",
        "fact_formal_tyw_balance_daily",
        "zqtz_bond_daily_snapshot",
        "tyw_interbank_daily_snapshot",
    ],
    "GAP-CROSS-ASSET-PAGE": [
        "fact_choice_macro_daily",
        "fx_daily_mid",
        "market_data_series_category",
        "livermore_position_snapshot",
        "choice_stock_daily_observation",
        "fact_livermore_gate_supplement_daily",
        "choice_news_event",
    ],
    "PAGE-OPS-001": [
        "product_category_pnl_formal_read_model",
        "product_category_pnl_canonical_fact",
        "fact_formal_zqtz_balance_daily",
        "fact_formal_tyw_balance_daily",
        "fact_choice_macro_daily",
        "fx_daily_mid",
        "choice_news_event",
    ],
    "PAGE-MARKET-HOME-001": [
        "fact_choice_macro_daily",
        "market_data_series_category",
        "fx_daily_mid",
    ],
    "PAGE-RISK-HOME-001": [
        "fact_formal_risk_tensor_daily",
        "fact_formal_zqtz_balance_daily",
        "fact_formal_tyw_balance_daily",
    ],
    "PAGE-PERFORMANCE-HOME-001": [
        "product_category_pnl_formal_read_model",
        "product_category_pnl_canonical_fact",
        "fact_formal_pnl_fi",
        "fact_nonstd_pnl_bridge",
    ],
    "PAGE-REPORTS-HOME-001": [
        "fact_formal_bond_analytics_daily",
        "source_foundation",
    ],
}
PAGE_CATALOG_DATE_DEFERRED_REASONS = {
    "GAP-DECISION-ITEMS-PAGE": (
        "Read/write governance action queue; direct DuckDB table/date review belongs to PAGE-BALANCE-001 "
        "while decision-status writes are reviewed through governance records."
    ),
    "GAP-KPI-PERFORMANCE-PAGE": (
        "Read/write KPI scoring workbench; direct page closure depends on governance SQL source, score-rule, "
        "permission, and audit-trail evidence rather than DuckDB table/date sampling."
    ),
    "GAP-AVERAGE-BALANCE-PAGE": (
        "ADB analytical route; direct page closure depends on PAGE contract approval, ADB denominator semantics, "
        "bound golden sample, lineage records, and owner review before any formal-use claim."
    ),
    "PAGE-EXEC-SUMMARY-001": "Narrative-only summary endpoint; table/date review belongs to upstream overview and snapshot evidence.",
    "PAGE-EXEC-PNL-ATTR-001": "Executive attribution overlay has no direct table contract; sample upstream attribution and formal-source pages instead.",
    "PAGE-MACRO-TOOLKIT-001": "Tooling/workflow surface; no direct business metric table contract is approved for page-level sampling.",
    "PAGE-MACRO-OBS-001": "Read-only macro observation surface; no direct business metric table contract is approved for page-level sampling.",
    "PAGE-AGENT-001": "Agent answer workbench; governance audit records are query/run evidence, not direct catalog/date table anchors.",
}
DATE_COLUMN_PRIORITY = (
    "report_date",
    "as_of_date",
    "trade_date",
    "natural_date",
    "business_date",
    "date",
)


class McpError(Exception):
    def __init__(self, code: int, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


def main() -> int:
    parser = argparse.ArgumentParser(description="Read-only project MCP servers for MOSS.")
    parser.add_argument(
        "mode",
        choices=("metric-contracts", "lineage-evidence", "data-catalog", "data-quality"),
        help="Project MCP surface to expose.",
    )
    args = parser.parse_args()

    server = ProjectMcpServer(build_provider(args.mode))
    server.serve()
    return 0


class ProjectMcpServer:
    def __init__(self, provider: "McpProvider") -> None:
        self._provider = provider
        self._next_request_id = 0

    def serve(self) -> None:
        while True:
            message = self._read_message()
            if message is None:
                return
            if "id" not in message:
                self._handle_notification(message)
                continue
            response = self._handle_request(message)
            self._write_message(response)

    def _handle_notification(self, message: dict[str, Any]) -> None:
        if message.get("method") == "notifications/initialized":
            return

    def _handle_request(self, message: dict[str, Any]) -> dict[str, Any]:
        request_id = message.get("id")
        method = str(message.get("method") or "")
        params = message.get("params") if isinstance(message.get("params"), dict) else {}
        try:
            result = self._dispatch(method, params)
            return {"jsonrpc": "2.0", "id": request_id, "result": result}
        except McpError as exc:
            return {
                "jsonrpc": "2.0",
                "id": request_id,
                "error": {"code": exc.code, "message": exc.message},
            }
        except Exception as exc:  # pragma: no cover - final protocol safety net
            return {
                "jsonrpc": "2.0",
                "id": request_id,
                "error": {"code": -32603, "message": str(exc)},
            }

    def _dispatch(self, method: str, params: dict[str, Any]) -> dict[str, Any]:
        if method == "initialize":
            return {
                "protocolVersion": PROTOCOL_VERSION,
                "capabilities": {"resources": {}, "tools": {}},
                "serverInfo": {"name": self._provider.name, "version": "0.1.0"},
            }
        if method == "resources/list":
            return {"resources": self._provider.resources()}
        if method == "resources/read":
            uri = str(params.get("uri") or "")
            return {"contents": [self._provider.read_resource(uri)]}
        if method == "tools/list":
            return {"tools": self._provider.tools()}
        if method == "tools/call":
            name = str(params.get("name") or "")
            arguments = params.get("arguments") if isinstance(params.get("arguments"), dict) else {}
            return self._provider.call_tool(name, arguments)
        raise McpError(-32601, f"Unsupported method: {method}")

    def _read_message(self) -> dict[str, Any] | None:
        header_lines: list[bytes] = []
        while True:
            line = sys.stdin.buffer.readline()
            if not line:
                return None
            if line in (b"\r\n", b"\n"):
                break
            header_lines.append(line.rstrip(b"\r\n"))

        content_length = None
        for raw_line in header_lines:
            line = raw_line.decode("ascii", errors="ignore")
            if line.lower().startswith("content-length:"):
                content_length = int(line.split(":", 1)[1].strip())
                break
        if content_length is None:
            raise McpError(-32600, "Missing Content-Length header.")

        body = sys.stdin.buffer.read(content_length)
        if not body:
            return None
        return json.loads(body.decode("utf-8"))

    def _write_message(self, payload: dict[str, Any]) -> None:
        body = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        sys.stdout.buffer.write(f"Content-Length: {len(body)}\r\n\r\n".encode("ascii"))
        sys.stdout.buffer.write(body)
        sys.stdout.buffer.flush()


class McpProvider:
    name: str

    def resources(self) -> list[dict[str, Any]]:
        raise NotImplementedError

    def read_resource(self, uri: str) -> dict[str, Any]:
        raise NotImplementedError

    def tools(self) -> list[dict[str, Any]]:
        return []

    def call_tool(self, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        raise McpError(-32602, f"Unknown tool: {name}")


class MetricContractsProvider(McpProvider):
    name = "moss-metric-contracts"

    def __init__(self) -> None:
        self._docs = {
            "page_contracts": REPO_ROOT / "docs" / "page_contracts.md",
            "calc_rules": REPO_ROOT / "docs" / "calc_rules.md",
            "metric_dictionary": REPO_ROOT / "docs" / "metric_dictionary.md",
            "product_category_truth": REPO_ROOT
            / "docs"
            / "pnl"
            / "product-category-page-truth-contract.md",
            "golden_sample_catalog": REPO_ROOT / "docs" / "golden_sample_catalog.md",
        }
        self._page_trace_bundles = product_page_trace_bundles()

    def resources(self) -> list[dict[str, Any]]:
        resources = [
            text_resource(
                "moss://metric-contracts/summary",
                "MOSS metric/page contract summary",
                "High-level index of contract documents and golden samples.",
            )
        ]
        for key, path in self._docs.items():
            resources.append(
                text_resource(
                    f"moss://metric-contracts/doc/{key}",
                    key.replace("_", " "),
                    str(path.relative_to(REPO_ROOT)),
                )
            )
        return resources

    def read_resource(self, uri: str) -> dict[str, Any]:
        if uri == "moss://metric-contracts/summary":
            payload = {
                "repo": str(REPO_ROOT),
                "documents": [
                    {
                        "key": key,
                        "path": str(path.relative_to(REPO_ROOT)),
                        "exists": path.is_file(),
                    }
                    for key, path in self._docs.items()
                ],
                "golden_samples": list_golden_samples(limit=80),
            }
            return resource_content(uri, json.dumps(payload, ensure_ascii=False, indent=2), "application/json")

        prefix = "moss://metric-contracts/doc/"
        if uri.startswith(prefix):
            key = uri.removeprefix(prefix)
            path = self._docs.get(key)
            if path is None:
                raise McpError(-32602, f"Unknown contract document: {key}")
            return resource_content(uri, read_text(path), "text/markdown")
        raise McpError(-32602, f"Unknown resource: {uri}")

    def tools(self) -> list[dict[str, Any]]:
        return [
            {
                "name": "search_contract_docs",
                "description": "Search page contracts, metric dictionary, calc rules, and golden-sample docs.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "query": {"type": "string"},
                        "max_results": {"type": "integer", "minimum": 1, "maximum": 50},
                    },
                    "required": ["query"],
                },
            },
            {
                "name": "get_page_trace_bundle",
                "description": "Return the read-only contract, lineage, code, and test touchpoints for one seeded MOSS page.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "page_slug": {
                            "type": "string",
                            "description": "Seeded page slug or route alias, for example product-category-pnl or dashboard-home.",
                        }
                    },
                    "required": ["page_slug"],
                },
            },
            {
                "name": "get_page_evidence_readiness",
                "description": (
                    "Return a read-only audit matrix for seeded page evidence readiness without promoting candidate "
                    "or mixed-source surfaces to formal metric approval."
                ),
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "page_slugs": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Optional seeded page slugs, page IDs, or route aliases to summarize.",
                        }
                    },
                },
            },
        ]

    def call_tool(self, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        if name == "search_contract_docs":
            query = str(arguments.get("query") or "").strip()
            if not query:
                raise McpError(-32602, "query is required.")
            max_results = int(arguments.get("max_results") or 20)
            matches = search_files(self._docs.values(), query=query, max_results=max_results)
            return tool_text(json.dumps({"query": query, "matches": matches}, ensure_ascii=False, indent=2))
        if name == "get_page_trace_bundle":
            page_slug = str(arguments.get("page_slug") or "").strip()
            payload = page_trace_bundle(self._page_trace_bundles, page_slug)
            return tool_text(json.dumps(payload, ensure_ascii=False, indent=2))
        if name == "get_page_evidence_readiness":
            raw_page_slugs = arguments.get("page_slugs")
            if raw_page_slugs is None:
                page_slugs = DEFAULT_EVIDENCE_READINESS_PAGES
            elif isinstance(raw_page_slugs, list):
                page_slugs = [str(item).strip() for item in raw_page_slugs if str(item).strip()]
            else:
                raise McpError(-32602, "page_slugs must be an array of strings.")
            payload = page_evidence_readiness(self._page_trace_bundles, page_slugs)
            return tool_text(json.dumps(payload, ensure_ascii=False, indent=2))
        return super().call_tool(name, arguments)


class LineageEvidenceProvider(McpProvider):
    name = "moss-lineage-evidence"
    _QUERY_EXPANSIONS = {
        "page-agent-001": [
            "agent.",
            "AgentEnvelope",
            "agent_audit",
            "/api/agent/runs",
            "/api/agent/query",
        ],
        "page-balance-001": [
            "/ui/balance-analysis/overview",
            "/ui/balance-analysis/workbook",
            "balance-analysis.overview",
            "balance-analysis.workbook",
            "balance_analysis",
            "fact_formal_zqtz_balance_daily",
            "fact_formal_tyw_balance_daily",
            "GS-BAL-OVERVIEW-A",
            "GS-BAL-WORKBOOK-A",
            "MTR-BAL-001",
            "MTR-BAL-002",
            "MTR-BAL-003",
            "MTR-BAL-004",
            "MTR-BAL-005",
            "MTR-BAL-006",
            "MTR-BAL-101",
            "MTR-BAL-102",
            "MTR-BAL-103",
            "MTR-BAL-104",
            "MTR-BAL-105",
            "MTR-BAL-201",
            "MTR-BAL-202",
            "MTR-BAL-203",
        ],
        "page-bal-move-001": [
            "/ui/balance-movement-analysis",
            "/ui/balance-movement-analysis/dates",
            "/ui/balance-movement-analysis/refresh",
            "balance-analysis.movement",
            "balance-analysis.movement.detail",
            "balance-analysis.movement.dates",
            "accounting_asset_movement",
            "fact_accounting_asset_movement_monthly",
            "fact_formal_zqtz_balance_daily",
            "rv_accounting_asset_movement_v2",
            "cv_accounting_asset_movement_v1",
            "AccountingAssetMovementPayload",
            "AccountingAssetMovementSummaryPayload",
            "MTR-BMV-001",
            "MTR-BMV-002",
            "MTR-BMV-003",
            "MTR-BMV-004",
        ],
        "gap-decision-items-page": [
            "/decision-items",
            "decision-items",
            "decision_items",
            "GAP-DECISION-ITEMS-PAGE",
            "/ui/balance-analysis/decision-items",
            "/ui/balance-analysis/decision-items/status",
            "/ui/balance-analysis/current-user",
            "/ui/balance-analysis/dates",
            "balance-analysis.decision-items",
            "balance_analysis_decision_status",
            "BalanceAnalysisDecisionItemsPayload",
            "BalanceAnalysisDecisionItemStatusRow",
            "BalanceAnalysisDecisionStatusUpdateRequest",
            "balance_analysis.decision_status",
            "fact_formal_zqtz_balance_daily",
            "fact_formal_tyw_balance_daily",
            "PAGE-BALANCE-001",
            "temporary-exception read/write governance action queue",
        ],
        "gap-kpi-performance-page": [
            "/kpi",
            "kpi-performance",
            "kpi_performance",
            "GAP-KPI-PERFORMANCE-PAGE",
            "/api/kpi/owners",
            "/api/kpi/values/summary",
            "/api/kpi/metrics",
            "/api/kpi/values",
            "/api/kpi/values/batch",
            "/api/kpi/fetch_and_recalc",
            "/api/kpi/report",
            "kpi.owners",
            "kpi.values.summary",
            "KpiPeriodSummaryPayload",
            "KpiMetricWithValue",
            "KpiFetchAndRecalcResponse",
            "MTR-KPI-001",
            "PAGE-CONTRACT-PENDING:/kpi",
            "kpi.metric",
            "kpi.value",
            "temporary-exception read/write KPI scoring boundary",
        ],
        "gap-average-balance-page": [
            "/average-balance",
            "average-balance",
            "average_balance",
            "GAP-AVERAGE-BALANCE-PAGE",
            "/api/analysis/adb",
            "/api/analysis/adb/comparison",
            "/api/analysis/adb/monthly",
            "/api/analysis/adb/coverage",
            "/ui/balance-analysis/dates",
            "adb_analysis",
            "adb_analysis.monthly",
            "adb_analysis.comparison",
            "ADBAnalysisResponse",
            "ADBMonthlyResponse",
            "MTR-ADB-001",
            "MTR-ADB-002",
            "MTR-ADB-003",
            "PAGE-CONTRACT-PENDING:/average-balance",
            "temporary-exception ADB analytical balance boundary",
        ],
        "page-bond-001": [
            "/api/bond-dashboard/headline-kpis",
            "/api/bond-dashboard/dates",
            "/api/bond-dashboard/asset-structure",
            "/api/bond-dashboard/yield-distribution",
            "/api/bond-dashboard/portfolio-comparison",
            "/api/bond-dashboard/spread-analysis",
            "/api/bond-dashboard/maturity-structure",
            "/api/bond-dashboard/industry-distribution",
            "/api/bond-dashboard/risk-indicators",
            "/api/bond-dashboard/business-type-metrics",
            "bond_dashboard.dates",
            "bond_dashboard.headline_kpis",
            "bond_dashboard.asset_structure",
            "bond_dashboard.yield_distribution",
            "bond_dashboard.portfolio_comparison",
            "bond_dashboard.spread_analysis",
            "bond_dashboard.maturity_structure",
            "bond_dashboard.industry_distribution",
            "bond_dashboard.risk_indicators",
            "bond_dashboard.business_type_metrics",
            "bond_analytics",
            "fact_formal_bond_analytics_daily",
            "GS-BOND-HEADLINE-A",
            "MTR-BOND-001",
            "MTR-BOND-002",
            "MTR-BOND-003",
            "MTR-BOND-004",
        ],
        "page-bond-analysis-001": [
            "/bond-analysis",
            "PAGE-BOND-ANALYSIS-001",
            "/api/bond-analytics/dates",
            "/api/bond-analytics/action-attribution",
            "/api/bond-analytics/return-decomposition",
            "/api/bond-analytics/benchmark-excess",
            "/api/bond-analytics/krd-curve-risk",
            "/api/bond-analytics/dv01-risk",
            "/api/bond-analytics/dv01-reconciliation",
            "/api/bond-analytics/dv01-movement",
            "/api/bond-analytics/dv01-action-plan",
            "/api/bond-analytics/dv01-limit-config-status",
            "/api/bond-analytics/accounting-class-audit",
            "/api/bond-analytics/credit-spread-migration",
            "/api/bond-analytics/portfolio-headlines",
            "/api/bond-analytics/top-holdings",
            "/api/bond-analytics/position-changes",
            "/api/bond-analytics/yield-curve-term-structure",
            "/api/credit-spread-analysis/detail",
            "bond_analytics.action_attribution",
            "bond_analytics.return_decomposition",
            "bond_analytics.krd_curve_risk",
            "bond_analytics.dv01_risk",
            "bond_analytics.credit_spread_migration",
            "bond_analytics.portfolio_headlines",
            "fact_formal_bond_analytics_daily",
            "yield_curve_daily",
            "GS-BOND-ANALYSIS-ACTION-ATTR-A",
            "MTR-BOND-ACT-001",
            "MTR-BOND-ACT-002",
            "MTR-BOND-ACT-003",
            "MTR-BOND-ACT-004",
            "MTR-BOND-ACT-005",
            "MTR-BOND-ACT-006",
        ],
        "page-bridge-001": [
            "/api/pnl/bridge",
            "pnl.bridge",
            "pnl_bridge",
            "fact_formal_pnl_fi",
            "fact_nonstd_pnl_bridge",
            "GS-BRIDGE-A",
            "GS-BRIDGE-WARN-B",
            "MTR-BRG-001",
            "MTR-BRG-002",
            "MTR-BRG-003",
            "MTR-BRG-004",
            "MTR-BRG-005",
            "MTR-BRG-006",
            "MTR-BRG-007",
            "MTR-BRG-008",
            "MTR-BRG-009",
            "MTR-BRG-010",
            "MTR-BRG-011",
            "MTR-BRG-012",
            "MTR-BRG-013",
            "MTR-BRG-014",
            "MTR-BRG-101",
            "MTR-BRG-102",
            "MTR-BRG-103",
            "MTR-BRG-104",
            "MTR-BRG-105",
        ],
        "page-cube-query-001": [
            "/api/cube/query",
            "cube_query.",
            "fact_formal_bond_analytics_daily",
            "fact_formal_pnl_fi",
            "fact_formal_zqtz_balance_daily",
            "product_category_pnl_formal_read_model",
        ],
        "page-dash-001": [
            "/ui/home/snapshot",
            "home.snapshot",
            "dashboard-home",
            "HomeSnapshotPayload",
            "home_snapshot_envelope",
            "executive_analytical",
            "domains_effective_date",
            "domains_missing",
            "product_category_ytd",
            "product_category_monthly",
            "dashboard.core_metrics",
            "dashboard.daily_changes",
            "bond_dashboard.headline_kpis",
            "bond_analytics.portfolio_headlines",
            "market_data.rates",
            "calendar.supply_auctions",
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
        "page-exec-overview-001": [
            "/ui/home/overview",
            "executive.overview",
            "executive_overview",
            "OverviewPayload",
            "ExecutiveMetric",
            "ExecutiveMetric.caliber_label",
            "GS-EXEC-OVERVIEW-A",
            "MTR-EXEC-001",
            "MTR-EXEC-002",
            "MTR-EXEC-003",
            "MTR-EXEC-004",
            "MTR-EXEC-004A",
            "MTR-EXEC-004B",
            "MTR-EXEC-004C",
            "formal_balance",
            "fact_formal_zqtz_balance_daily",
            "fact_formal_tyw_balance_daily",
            "fact_formal_pnl_fi",
            "fact_nonstd_pnl_bridge",
            "liability_analytics.yield_metrics",
            "zqtz_bond_daily_snapshot",
            "tyw_interbank_daily_snapshot",
            "bond_analytics",
            "fact_formal_bond_analytics_daily",
        ],
        "page-exec-summary-001": [
            "/ui/home/summary",
            "executive.summary",
            "executive-summary",
            "executive_summary",
            "SummaryPayload",
            "SummaryPoint",
            "GS-EXEC-SUMMARY-A",
            "narrative-only",
            "executive.overview",
        ],
        "page-exec-pnl-attr-001": [
            "/ui/pnl/attribution",
            "executive.pnl-attribution",
            "executive-pnl-attribution",
            "executive_pnl_attribution",
            "PnlAttributionPayload",
            "PnlAttributionSection",
            "GS-EXEC-PNL-ATTR-A",
            "MTR-EXEC-101",
            "MTR-EXEC-102",
            "MTR-EXEC-103",
            "MTR-EXEC-104",
            "MTR-EXEC-105",
            "MTR-EXEC-106",
            "formal_pnl",
            "pnl_bridge",
            "fact_formal_pnl_fi",
            "fact_nonstd_pnl_bridge",
            "product_category_pnl_formal_read_model",
        ],
        "page-macro-toolkit-001": [
            "/ui/macro/toolkit/analysis",
            "/ui/macro/toolkit/analysis/strategy-summaries",
            "/ui/macro/toolkit/scripts",
            "/ui/macro/toolkit/scripts/",
            "/ui/macro/toolkit/choice-stock/refresh-status",
            "/ui/macro/toolkit/choice-stock/refresh",
            "/ui/macro/toolkit/cffex-member-rank/refresh",
            "/ui/macro/toolkit/source-backfill/refresh",
            "/ui/macro/toolkit/commodity-futures/refresh",
            "macro-toolkit",
            "macro_toolkit",
            "macro_toolkit.analysis",
            "macro_toolkit.analysis.strategy_summaries",
            "macro_toolkit.scripts",
            "macro_toolkit.choice_stock_refresh",
            "macro_toolkit.cffex_member_rank_refresh",
            "MacroToolkitAnalysisPayload",
            "MacroToolkitPayload",
            "MacroToolkitRunResponse",
            "MacroToolkitChoiceStockRefreshResponse",
            "candidate tooling surface",
            "source/version/run_id",
        ],
        "page-macro-obs-001": [
            "/ui/macro/toolkit/analysis",
            "/ui/macro/toolkit/analysis/strategy-summaries",
            "macro-observation",
            "macro_observation",
            "macro_toolkit.analysis",
            "macro_toolkit.analysis.strategy_summaries",
            "MacroToolkitAnalysisPayload",
            "macro-observation-readonly-boundary",
            "read-only macro observation",
        ],
        "page-market-home-001": [
            "module-home/market",
            "/ui/macro/choice-series/latest",
            "/ui/market-data/rates",
            "/ui/market-data/catalog",
            "/ui/macro/toolkit/analysis",
            "/ui/macro/toolkit/analysis/strategy-summaries",
            "macro.choice.latest",
            "market_data.rates",
            "market_data.catalog",
            "macro_toolkit.analysis",
            "macro_toolkit.analysis.strategy_summaries",
            "fact_choice_macro_daily",
            "market_data_series_category",
            "fx_daily_mid",
            "module home observational market entry",
        ],
        "page-ledger-pnl-001": [
            "/api/ledger-pnl/summary",
            "/api/ledger-pnl/data",
            "/api/ledger-pnl/formal-financial-indicators",
            "ledger_pnl.",
            "qdb_general_ledger_workbook",
            "formal_financial_indicator_source_contract",
            "GS-LEDGER-PNL-FIN-IND-202603-B",
        ],
        "page-pnl-by-business-001": [
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
            "pnl-by-business",
            "/pnl-by-business",
            "page-level analytical display no newly approved MTR binding",
        ],
        "page-liab-analytics-001": [
            "/api/risk/buckets",
            "/api/analysis/yield_metrics",
            "/api/analysis/yield-by-period",
            "/api/analysis/liabilities/counterparty",
            "/api/liabilities/monthly",
            "/ui/liability/business-context",
            "/api/analysis/liabilities/cockpit-warnings",
            "/api/analysis/liabilities/contribution-split",
            "liability_analytics.risk_buckets",
            "liability_analytics.yield_metrics",
            "liability_analytics.yield_by_period",
            "liability_analytics.counterparty",
            "liability_analytics.monthly",
            "liability_analytics.cockpit_warnings",
            "liability_analytics.contribution_split",
            "formal_liability",
            "fact_formal_zqtz_balance_daily",
            "fact_formal_tyw_balance_daily",
            "zqtz_bond_daily_snapshot",
            "tyw_interbank_daily_snapshot",
            "rv_liability_analytics_compat_v1",
            "cv_liability_analytics_v1",
            "LiabilityRiskBucketsPayload",
            "LiabilityYieldMetricsPayload",
            "LiabilityCounterpartyPayload",
            "LiabilitiesMonthlyPayload",
            "MTR-LIAB-001",
            "MTR-LIAB-002",
            "MTR-LIAB-003",
            "MTR-LIAB-004",
            "MTR-LIAB-005",
            "MTR-LIAB-006",
            "MTR-LIAB-007",
        ],
        "page-mkt-001": [
            "/ui/preview/macro-foundation",
            "/ui/market-data/rates",
            "/ui/market-data/fx/formal-status",
            "/ui/market-data/fx/analytical",
            "/ui/market-data/ncd-funding-proxy",
            "/api/macro-bond-linkage",
            "/ui/macro/choice-series/latest",
            "/ui/market-data/livermore",
            "/ui/market-data/livermore/stock-detail",
            "/ui/market-data/livermore/candidate-history",
            "/ui/market-data/livermore/sector-rank-series",
            "preview.macro-foundation",
            "market_data.rates",
            "market_data.catalog",
            "macro.choice.latest",
            "fx.formal.status",
            "fx.analytical.groups",
            "market_data.ncd_proxy",
            "market_data.livermore",
            "market_data.livermore.stock_detail",
            "market_data.livermore.candidate_history",
            "market_data.livermore.sector_rank_series",
            "macro_bond_linkage.analysis",
            "macro_bond_linkage.environment_context",
            "fact_choice_macro_daily",
            "market_data_series_category",
            "fx_daily_mid",
            "livermore_position_snapshot",
            "choice_stock_daily_observation",
            "fact_livermore_gate_supplement_daily",
            "rv_phase1_macro_vendor_v1",
            "rv_market_data_rates_formal_v1",
            "rv_fx_formal_mid_v1",
            "rv_fx_analytical_v1",
            "rv_ncd_proxy_v1",
            "rv_livermore_strategy_v1",
            "rv_macro_bond_linkage_v1",
            "MTR-MKT-001",
            "GAP-MKT-DATA",
        ],
        "gap-cross-asset-page": [
            "/cross-asset",
            "cross-asset",
            "cross_asset",
            "GAP-CROSS-ASSET-PAGE",
            "/ui/macro/choice-series/latest",
            "/api/macro-bond-linkage/analysis",
            "/ui/market-data/ncd-funding-proxy",
            "/ui/market-data/livermore",
            "/ui/market-data/livermore/signal-confluence",
            "/ui/news/choice-events/latest",
            "macro.choice.latest",
            "macro_bond_linkage.analysis",
            "macro_bond_linkage.environment_context",
            "market_data.ncd_proxy",
            "market_data.livermore",
            "market_data.livermore.signal_confluence",
            "news.choice.latest",
            "fact_choice_macro_daily",
            "fx_daily_mid",
            "market_data_series_category",
            "livermore_position_snapshot",
            "choice_stock_daily_observation",
            "fact_livermore_gate_supplement_daily",
            "choice_news_event",
            "rv_macro_bond_linkage_v1",
            "rv_ncd_proxy_v1",
            "rv_livermore_signal_confluence_v1",
            "rv_choice_news_v1",
            "temporary-exception analytical cross-asset boundary",
        ],
        "gap-stock-analysis-page": [
            "stock-analysis",
            "/stock-analysis",
            "GAP-STOCK-ANALYSIS-PAGE",
            "/ui/market-data/livermore",
            "/ui/market-data/livermore/stock-detail",
            "/ui/market-data/livermore/candidate-history",
            "/ui/market-data/livermore/strategy-score",
            "/ui/market-data/livermore/strategy-optimization",
            "/ui/market-data/livermore/cycle-proxy-backtest",
            "/ui/market-data/livermore/candidate-history-portfolio-backtest",
            "/ui/market-data/livermore/sector-rank-series",
            "/ui/market-data/livermore/signal-confluence",
            "market_data.livermore",
            "market_data.livermore.stock_detail",
            "market_data.livermore.candidate_history",
            "market_data.livermore.strategy_score",
            "market_data.livermore.strategy_optimization",
            "market_data.livermore.cycle_proxy_backtest",
            "market_data.livermore.candidate_history_portfolio_backtest",
            "market_data.livermore.sector_rank_series",
            "market_data.livermore.signal_confluence",
            "livermore_position_snapshot",
            "livermore_candidate_history",
            "choice_stock_daily_observation",
            "fact_livermore_gate_supplement_daily",
            "rv_livermore_strategy_v1",
            "rv_livermore_strategy_score_v1",
            "rv_livermore_strategy_optimization_v1",
            "rv_livermore_cycle_proxy_backtest_v1",
            "rv_livermore_candidate_history_portfolio_backtest_v1",
            "rv_livermore_sector_rank_series_v1",
            "rv_livermore_signal_confluence_v1",
            "temporary-exception observational stock analysis boundary",
        ],
        "stock-analysis": [
            "GAP-STOCK-ANALYSIS-PAGE",
            "stock-analysis",
            "/stock-analysis",
            "/ui/market-data/livermore",
            "/ui/market-data/livermore/stock-detail",
            "/ui/market-data/livermore/candidate-history",
            "/ui/market-data/livermore/strategy-score",
            "/ui/market-data/livermore/strategy-optimization",
            "/ui/market-data/livermore/cycle-proxy-backtest",
            "/ui/market-data/livermore/candidate-history-portfolio-backtest",
            "/ui/market-data/livermore/sector-rank-series",
            "/ui/market-data/livermore/signal-confluence",
            "market_data.livermore",
            "market_data.livermore.stock_detail",
            "market_data.livermore.candidate_history",
            "market_data.livermore.strategy_score",
            "market_data.livermore.strategy_optimization",
            "market_data.livermore.cycle_proxy_backtest",
            "market_data.livermore.candidate_history_portfolio_backtest",
            "market_data.livermore.sector_rank_series",
            "market_data.livermore.signal_confluence",
            "livermore_position_snapshot",
            "livermore_candidate_history",
            "choice_stock_daily_observation",
            "fact_livermore_gate_supplement_daily",
            "rv_livermore_strategy_v1",
            "rv_livermore_strategy_score_v1",
            "rv_livermore_strategy_optimization_v1",
            "rv_livermore_cycle_proxy_backtest_v1",
            "rv_livermore_candidate_history_portfolio_backtest_v1",
            "rv_livermore_sector_rank_series_v1",
            "rv_livermore_signal_confluence_v1",
            "temporary-exception observational stock analysis boundary",
        ],
        "/stock-analysis": [
            "GAP-STOCK-ANALYSIS-PAGE",
            "stock-analysis",
            "/stock-analysis",
            "/ui/market-data/livermore",
            "/ui/market-data/livermore/stock-detail",
            "/ui/market-data/livermore/candidate-history",
            "/ui/market-data/livermore/strategy-score",
            "/ui/market-data/livermore/strategy-optimization",
            "/ui/market-data/livermore/cycle-proxy-backtest",
            "/ui/market-data/livermore/candidate-history-portfolio-backtest",
            "/ui/market-data/livermore/sector-rank-series",
            "/ui/market-data/livermore/signal-confluence",
            "market_data.livermore",
            "market_data.livermore.stock_detail",
            "market_data.livermore.candidate_history",
            "market_data.livermore.strategy_score",
            "market_data.livermore.strategy_optimization",
            "market_data.livermore.cycle_proxy_backtest",
            "market_data.livermore.candidate_history_portfolio_backtest",
            "market_data.livermore.sector_rank_series",
            "market_data.livermore.signal_confluence",
            "livermore_position_snapshot",
            "livermore_candidate_history",
            "choice_stock_daily_observation",
            "fact_livermore_gate_supplement_daily",
            "rv_livermore_strategy_v1",
            "rv_livermore_strategy_score_v1",
            "rv_livermore_strategy_optimization_v1",
            "rv_livermore_cycle_proxy_backtest_v1",
            "rv_livermore_candidate_history_portfolio_backtest_v1",
            "rv_livermore_sector_rank_series_v1",
            "rv_livermore_signal_confluence_v1",
            "temporary-exception observational stock analysis boundary",
        ],
        "page-ops-001": [
            "/ui/pnl/product-category",
            "/ui/pnl/product-category/dates",
            "/ui/balance-analysis/overview",
            "/ui/balance-analysis/dates",
            "/ui/preview/source-foundation",
            "/ui/preview/macro-foundation",
            "/ui/macro/choice-series/latest",
            "/ui/market-data/fx/formal-status",
            "/ui/news/choice-events/latest",
            "product_category_pnl.detail",
            "product_category_pnl.dates",
            "product_category_pnl_formal_read_model",
            "product_category_pnl_canonical_fact",
            "GS-PROD-CAT-PNL-A",
            "MTR-PCP-001",
            "MTR-PCP-002",
            "MTR-PCP-003",
            "balance-analysis.overview",
            "balance-analysis.dates",
            "formal_balance",
            "fact_formal_zqtz_balance_daily",
            "fact_formal_tyw_balance_daily",
            "GS-BAL-OVERVIEW-A",
            "MTR-BAL-001",
            "MTR-BAL-002",
            "MTR-BAL-003",
            "MTR-BAL-101",
            "MTR-BAL-102",
            "preview.source-foundation",
            "preview.macro-foundation",
            "macro.choice.latest",
            "fx.formal.status",
            "fact_choice_macro_daily",
            "fx_daily_mid",
            "news.choice.latest",
            "choice_news_event",
            "GAP-OPS-MACRO-FX",
        ],
        "page-performance-home-001": [
            "module-home/performance",
            "/api/kpi/owners",
            "/api/kpi/values/summary",
            "/api/pnl/by-business-ytd",
            "/ui/pnl/product-category",
            "kpi.owners",
            "kpi.values.summary",
            "pnl.by_business_ytd",
            "product_category_pnl.detail",
            "product_category_pnl_formal_read_model",
            "product_category_pnl_canonical_fact",
            "fact_formal_pnl_fi",
            "fact_nonstd_pnl_bridge",
            "module home does not rebuild KPI or team formulas",
        ],
        "page-pos-001": [
            "/api/positions/bonds",
            "/api/positions/bonds/sub_types",
            "/api/positions/interbank",
            "/api/positions/interbank/product_types",
            "/api/positions/counterparty/bonds",
            "/api/positions/counterparty/interbank/split",
            "/api/positions/stats/rating",
            "/api/positions/stats/industry",
            "/api/positions/customer/details",
            "/api/positions/customer/trend",
            "positions.bonds.list",
            "positions.bonds.sub_types",
            "positions.interbank.list",
            "positions.interbank.product_types",
            "positions.counterparty.bonds",
            "positions.counterparty.interbank.split",
            "positions.stats.rating",
            "positions.stats.industry",
            "positions.customer.details",
            "positions.customer.trend",
            "positions_snapshot",
            "zqtz_bond_daily_snapshot",
            "tyw_interbank_daily_snapshot",
            "rv_positions_snapshot_read_v1",
            "MTR-POS-001",
            "MTR-POS-002",
        ],
        "page-portfolio-home-001": [
            "module-home/portfolio",
            "/ui/balance-analysis/overview",
            "/ui/balance-analysis/dates",
            "/api/bond-dashboard/headline-kpis",
            "/api/bond-dashboard/risk-indicators",
            "/api/bond-dashboard/asset-structure",
            "/api/bond-dashboard/yield-distribution",
            "/api/bond-dashboard/portfolio-comparison",
            "/api/bond-dashboard/spread-analysis",
            "/api/bond-dashboard/maturity-structure",
            "/api/bond-dashboard/industry-distribution",
            "/api/bond-dashboard/business-type-metrics",
            "/api/positions/bonds",
            "/api/pnl-attribution/summary",
            "/api/pnl-attribution/analysis-summary",
            "/api/risk/tensor/dates",
            "balance-analysis.overview",
            "balance-analysis.dates",
            "bond_dashboard.headline_kpis",
            "bond_dashboard.risk_indicators",
            "bond_dashboard.asset_structure",
            "bond_dashboard.yield_distribution",
            "bond_dashboard.portfolio_comparison",
            "bond_dashboard.spread_analysis",
            "bond_dashboard.maturity_structure",
            "bond_dashboard.industry_distribution",
            "bond_dashboard.business_type_metrics",
            "positions.bonds.list",
            "pnl_attribution.summary",
            "risk.tensor.dates",
            "GS-PORTFOLIO-HOME-A",
            "fact_formal_zqtz_balance_daily",
            "fact_formal_tyw_balance_daily",
            "fact_formal_bond_analytics_daily",
            "zqtz_bond_daily_snapshot",
            "tyw_interbank_daily_snapshot",
            "fact_formal_pnl_fi",
            "fact_nonstd_pnl_bridge",
            "fact_formal_risk_tensor_daily",
            "module home no standalone MTR binding",
        ],
        "page-pnl-001": [
            "/api/pnl/overview",
            "/api/pnl/data",
            "pnl.overview",
            "pnl.data",
            "fact_formal_pnl_fi",
            "fact_nonstd_pnl_bridge",
            "GS-PNL-OVERVIEW-A",
            "GS-PNL-DATA-A",
            "MTR-PNL-001",
            "MTR-PNL-002",
            "MTR-PNL-003",
            "MTR-PNL-004",
            "MTR-PNL-005",
            "MTR-PNL-101",
            "MTR-PNL-102",
            "MTR-PNL-103",
            "MTR-PNL-104",
        ],
        "page-pnl-attr-wb-001": [
            "/api/pnl-attribution/volume-rate",
            "/api/pnl-attribution/tpl-market",
            "/api/pnl-attribution/composition",
            "/api/pnl-attribution/summary",
            "/api/pnl-attribution/advanced/carry-rolldown",
            "/api/pnl-attribution/advanced/spread",
            "/api/pnl-attribution/advanced/krd",
            "/api/pnl-attribution/advanced/summary",
            "/api/pnl-attribution/campisi/four-effects",
            "/api/pnl-attribution/campisi/enhanced",
            "/api/pnl-attribution/campisi/maturity-buckets",
            "/api/pnl-attribution/campisi/decision-grade",
            "pnl_attribution.volume_rate",
            "pnl_attribution.tpl_market",
            "pnl_attribution.composition",
            "pnl_attribution.summary",
            "pnl_attribution.carry_rolldown",
            "pnl_attribution.spread",
            "pnl_attribution.krd",
            "pnl_attribution.advanced_summary",
            "pnl_attribution.campisi",
            "campisi.four_effects",
            "campisi.enhanced",
            "campisi.maturity_buckets",
            "campisi.decision_grade",
            "VolumeRateAttributionPayload",
            "TPLMarketCorrelationPayload",
            "PnlCompositionPayload",
            "AdvancedAttributionSummary",
            "fact_formal_pnl_fi",
            "fact_nonstd_pnl_bridge",
            "fact_formal_zqtz_balance_daily",
            "fact_formal_bond_analytics_daily",
            "yield_curve_daily",
            "MTR-PAT-001",
            "MTR-PAT-002",
            "MTR-PAT-003",
            "MTR-PAT-004",
            "MTR-PAT-005",
            "MTR-PAT-006",
            "MTR-PAT-101",
            "MTR-PAT-102",
            "MTR-PAT-103",
            "MTR-PAT-201",
            "MTR-PAT-202",
            "MTR-PAT-203",
            "MTR-PAT-204",
            "MTR-PAT-205",
            "MTR-PAT-301",
            "MTR-PAT-302",
            "MTR-PAT-303",
            "MTR-PAT-304",
        ],
        "page-prod-cat-001": [
            "product-category-pnl",
            "/ui/pnl/product-category",
            "product_category_pnl.detail",
            "product_category_pnl_formal_read_model",
            "product_category_pnl_canonical_fact",
            "GS-PROD-CAT-PNL-A",
            "MTR-PCP-001",
            "MTR-PCP-002",
            "MTR-PCP-003",
        ],
        "page-prod-cat-pnl-001": [
            "product-category-pnl",
            "/ui/pnl/product-category",
            "product_category_pnl.detail",
            "product_category_pnl_formal_read_model",
            "product_category_pnl_canonical_fact",
            "GS-PROD-CAT-PNL-A",
            "MTR-PCP-001",
            "MTR-PCP-002",
            "MTR-PCP-003",
        ],
        "page-reports-home-001": [
            "module-home/governance",
            "/health/live",
            "/health",
            "/ui/preview/source-foundation",
            "/api/cube/dimensions/bond_analytics",
            "health.live",
            "health.status",
            "preview.source-foundation",
            "cube_query.",
            "fact_formal_bond_analytics_daily",
            "source_foundation",
            "module home diagnostics are not data-quality approval",
        ],
        "page-risk-001": [
            "fact_formal_risk_tensor_daily",
            "agent.risk_tensor",
            "risk_tensor",
            "risk.tensor",
            "risk-tensor",
        ],
        "page-risk-home-001": [
            "module-home/risk",
            "/api/risk/tensor/dates",
            "/api/risk/tensor",
            "/api/cashflow-projection",
            "risk.tensor.dates",
            "risk.tensor",
            "cashflow_projection.overview",
            "fact_formal_risk_tensor_daily",
            "fact_formal_zqtz_balance_daily",
            "fact_formal_tyw_balance_daily",
            "module home does not replace PAGE-RISK-001 formal risk truth",
        ],
    }

    def __init__(self) -> None:
        self._governance_dir = resolve_path_env("MOSS_GOVERNANCE_PATH", DEFAULT_GOVERNANCE_DIR)
        self._page_trace_bundles = product_page_trace_bundles()
        self._streams = {
            "agent_audit": self._governance_dir / "agent_audit.jsonl",
            "cache_build_run": self._governance_dir / "cache_build_run.jsonl",
            "cache_manifest": self._governance_dir / "cache_manifest.jsonl",
            "snapshot_manifest": self._governance_dir / "snapshot_manifest.jsonl",
            "source_manifest": self._governance_dir / "source_manifest.jsonl",
            "source_manifest_latest": self._governance_dir / "source_manifest_latest.jsonl",
            "vendor_version_registry": self._governance_dir / "vendor_version_registry.jsonl",
        }

    def resources(self) -> list[dict[str, Any]]:
        resources = [
            text_resource(
                "moss://lineage/summary",
                "MOSS lineage/evidence summary",
                "Governance stream status and latest records.",
            ),
            text_resource(
                "moss://lineage/streams",
                "MOSS governance streams",
                "Known governance JSONL streams.",
            ),
        ]
        for name in self._streams:
            resources.append(
                text_resource(
                    f"moss://lineage/stream/{name}",
                    name,
                    f"Latest records from {name}.",
                    mime_type="application/json",
                )
            )
        return resources

    def read_resource(self, uri: str) -> dict[str, Any]:
        if uri == "moss://lineage/summary":
            payload = {
                "governance_dir": str(self._governance_dir),
                "streams": {
                    name: stream_status(path)
                    for name, path in self._streams.items()
                },
            }
            return resource_content(uri, json.dumps(payload, ensure_ascii=False, indent=2), "application/json")
        if uri == "moss://lineage/streams":
            payload = {
                name: str(path.relative_to(REPO_ROOT)) if is_relative_to(path, REPO_ROOT) else str(path)
                for name, path in self._streams.items()
            }
            return resource_content(uri, json.dumps(payload, ensure_ascii=False, indent=2), "application/json")

        prefix = "moss://lineage/stream/"
        if uri.startswith(prefix):
            stream = uri.removeprefix(prefix)
            path = self._stream_path(stream)
            payload = {
                "stream": stream,
                "path": str(path),
                "latest_records": read_jsonl_tail(path, limit=5),
            }
            return resource_content(uri, json.dumps(payload, ensure_ascii=False, indent=2), "application/json")
        raise McpError(-32602, f"Unknown resource: {uri}")

    def tools(self) -> list[dict[str, Any]]:
        return [
            {
                "name": "read_governance_stream",
                "description": "Read the latest records from a whitelisted governance JSONL stream.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "stream": {"type": "string", "enum": sorted(self._streams)},
                        "limit": {"type": "integer", "minimum": 1, "maximum": 50},
                    },
                    "required": ["stream"],
                },
            },
            {
                "name": "find_lineage_records",
                "description": "Find lineage/evidence records by report_date, source_version, rule_version, or result kind.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "query": {"type": "string"},
                        "streams": {
                            "type": "array",
                            "items": {"type": "string", "enum": sorted(self._streams)},
                        },
                        "max_results": {"type": "integer", "minimum": 1, "maximum": 100},
                    },
                    "required": ["query"],
                },
            },
            {
                "name": "get_page_lineage_evidence",
                "description": (
                    "Summarize page-keyed governance lineage evidence while separating direct page/API records from "
                    "expanded source-table or metric-anchor records."
                ),
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "page_slugs": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Optional seeded page slugs, page IDs, or route aliases to summarize.",
                        },
                        "all_seeded_pages": {
                            "type": "boolean",
                            "description": "When true, summarize every unique seeded page trace bundle.",
                        },
                        "streams": {
                            "type": "array",
                            "items": {"type": "string", "enum": sorted(self._streams)},
                        },
                        "max_results": {"type": "integer", "minimum": 1, "maximum": 100},
                    },
                },
            },
            {
                "name": "get_page_governance_record_requirements",
                "description": (
                    "Describe the required fields and accepted direct page/API anchors for page-level governance "
                    "records without creating records or granting approval."
                ),
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "page_slugs": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Optional seeded page slugs, page IDs, or route aliases to describe.",
                        },
                        "all_seeded_pages": {
                            "type": "boolean",
                            "description": "When true, describe every unique seeded page trace bundle.",
                        },
                    },
                },
            },
            {
                "name": "validate_page_governance_records",
                "description": (
                    "Validate existing direct page/API governance records against the page requirements without "
                    "writing records or granting approval."
                ),
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "page_slugs": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Optional seeded page slugs, page IDs, or route aliases to validate.",
                        },
                        "all_seeded_pages": {
                            "type": "boolean",
                            "description": "When true, validate every unique seeded page trace bundle.",
                        },
                        "streams": {
                            "type": "array",
                            "items": {"type": "string", "enum": sorted(self._streams)},
                        },
                        "max_results": {"type": "integer", "minimum": 1, "maximum": 100},
                    },
                },
            },
            {
                "name": "get_page_governance_audit_review_checklist",
                "description": (
                    "Return a read-only audit-review checklist for page/API governance records after field "
                    "validation, without proving execution or granting approval."
                ),
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "page_slugs": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Optional seeded page slugs, page IDs, or route aliases to review.",
                        },
                        "all_seeded_pages": {
                            "type": "boolean",
                            "description": "When true, review every unique seeded page trace bundle.",
                        },
                        "streams": {
                            "type": "array",
                            "items": {"type": "string", "enum": sorted(self._streams)},
                        },
                        "max_results": {"type": "integer", "minimum": 1, "maximum": 100},
                    },
                },
            },
            {
                "name": "get_page_governance_audit_review_queue",
                "description": (
                    "Return a read-only queue of pages whose direct records are field-complete and still need "
                    "manual audit review, without proving execution or granting approval."
                ),
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "page_slugs": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Optional seeded page slugs, page IDs, or route aliases to queue.",
                        },
                        "all_seeded_pages": {
                            "type": "boolean",
                            "description": "When true, queue every unique seeded page trace bundle.",
                        },
                        "streams": {
                            "type": "array",
                            "items": {"type": "string", "enum": sorted(self._streams)},
                        },
                        "max_results": {"type": "integer", "minimum": 1, "maximum": 100},
                    },
                },
            },
            {
                "name": "get_page_governance_audit_evidence_packet",
                "description": (
                    "Aggregate read-only MCP-backed evidence for one field-complete page audit review without "
                    "running UI smoke checks, writing records, or granting approval."
                ),
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "page_slug": {
                            "type": "string",
                            "description": "Seeded page slug, page ID, or route alias to package.",
                        },
                        "streams": {
                            "type": "array",
                            "items": {"type": "string", "enum": sorted(self._streams)},
                        },
                        "duckdb_path": {
                            "type": "string",
                            "description": "Optional DuckDB path for catalog/date sampling.",
                        },
                        "max_results": {"type": "integer", "minimum": 1, "maximum": 100},
                    },
                    "required": ["page_slug"],
                },
            },
            {
                "name": "get_page_governance_audit_evidence_packet_queue",
                "description": (
                    "Aggregate read-only MCP-backed evidence packets for field-complete pages that still need "
                    "manual audit review, without running UI smoke checks, writing records, or granting approval."
                ),
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "page_slugs": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Optional seeded page slugs, page IDs, or route aliases to package.",
                        },
                        "all_seeded_pages": {
                            "type": "boolean",
                            "description": "When true, package every ready unique seeded page trace bundle.",
                        },
                        "streams": {
                            "type": "array",
                            "items": {"type": "string", "enum": sorted(self._streams)},
                        },
                        "duckdb_path": {
                            "type": "string",
                            "description": "Optional DuckDB path for catalog/date sampling.",
                        },
                        "max_results": {"type": "integer", "minimum": 1, "maximum": 100},
                    },
                },
            },
            {
                "name": "preflight_page_governance_record",
                "description": (
                    "Validate one candidate page/API governance record before writing it, without checking "
                    "existence, writing records, proving execution, or granting approval."
                ),
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "page_slug": {
                            "type": "string",
                            "description": "Seeded page slug, page ID, or route alias for the candidate record.",
                        },
                        "record": {
                            "type": "object",
                            "description": "Candidate governance record to validate against the page checklist.",
                        },
                    },
                    "required": ["page_slug", "record"],
                },
            },
            {
                "name": "get_page_governance_record_blueprint",
                "description": (
                    "Build a read-only candidate page/API governance record template with manual-fill gaps and "
                    "preflight status, without writing records or granting approval."
                ),
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "page_slug": {
                            "type": "string",
                            "description": "Seeded page slug, page ID, or route alias for the candidate template.",
                        },
                    },
                    "required": ["page_slug"],
                },
            },
            {
                "name": "get_page_governance_record_blueprint_queue",
                "description": (
                    "Return a prioritized read-only queue of page/API governance record gaps with candidate "
                    "record templates attached, without writing records or granting approval."
                ),
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "page_slugs": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Optional seeded page slugs, page IDs, or route aliases to queue.",
                        },
                        "all_seeded_pages": {
                            "type": "boolean",
                            "description": "When true, queue every unique seeded page trace bundle.",
                        },
                        "streams": {
                            "type": "array",
                            "items": {"type": "string", "enum": sorted(self._streams)},
                        },
                        "max_results": {"type": "integer", "minimum": 1, "maximum": 100},
                    },
                },
            },
            {
                "name": "get_page_governance_gap_queue",
                "description": (
                    "Return a prioritized read-only queue of page/API governance record gaps for seeded pages."
                ),
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "page_slugs": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Optional seeded page slugs, page IDs, or route aliases to queue.",
                        },
                        "all_seeded_pages": {
                            "type": "boolean",
                            "description": "When true, queue every unique seeded page trace bundle.",
                        },
                        "streams": {
                            "type": "array",
                            "items": {"type": "string", "enum": sorted(self._streams)},
                        },
                        "max_results": {"type": "integer", "minimum": 1, "maximum": 100},
                    },
                },
            },
        ]

    def call_tool(self, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        if name == "read_governance_stream":
            stream = str(arguments.get("stream") or "")
            limit = int(arguments.get("limit") or 10)
            path = self._stream_path(stream)
            payload = {"stream": stream, "records": read_jsonl_tail(path, limit=limit)}
            return tool_text(json.dumps(payload, ensure_ascii=False, indent=2))
        if name == "find_lineage_records":
            query = str(arguments.get("query") or "").strip()
            if not query:
                raise McpError(-32602, "query is required.")
            query_terms = lineage_query_terms(query, self._QUERY_EXPANSIONS)
            requested_streams = arguments.get("streams")
            if isinstance(requested_streams, list) and requested_streams:
                stream_names = [str(stream) for stream in requested_streams]
            else:
                stream_names = list(self._streams)
            max_results = int(arguments.get("max_results") or 40)
            records = []
            seen_records: set[tuple[str, int]] = set()
            for stream in stream_names:
                path = self._stream_path(stream)
                for query_term in query_terms:
                    stream_records = find_jsonl_records(
                        path,
                        stream=stream,
                        query=query_term,
                        max_results=max_results,
                    )
                    for record in stream_records:
                        record_key = (str(record.get("stream") or stream), int(record.get("line") or 0))
                        if record_key in seen_records:
                            continue
                        seen_records.add(record_key)
                        records.append({"matched_query": query_term, **record})
                        if len(records) >= max_results:
                            break
                    if len(records) >= max_results:
                        break
                if len(records) >= max_results:
                    break
            payload = {
                "query": query,
                "expanded_queries": query_terms,
                "records": records[:max_results],
            }
            return tool_text(json.dumps(payload, ensure_ascii=False, indent=2))
        if name == "get_page_lineage_evidence":
            page_slugs = lineage_page_slugs_from_arguments(arguments)
            requested_streams = arguments.get("streams")
            if isinstance(requested_streams, list) and requested_streams:
                stream_names = [str(stream) for stream in requested_streams]
            else:
                stream_names = list(self._streams)
            max_results = int(arguments.get("max_results") or 20)
            payload = page_lineage_evidence(
                self._page_trace_bundles,
                self._streams,
                page_slugs,
                stream_names,
                max_results=max_results,
            )
            return tool_text(json.dumps(payload, ensure_ascii=False, indent=2))
        if name == "get_page_governance_record_requirements":
            page_slugs = lineage_page_slugs_from_arguments(arguments)
            payload = page_governance_record_requirements(self._page_trace_bundles, page_slugs)
            return tool_text(json.dumps(payload, ensure_ascii=False, indent=2))
        if name == "validate_page_governance_records":
            page_slugs = lineage_page_slugs_from_arguments(arguments)
            requested_streams = arguments.get("streams")
            if isinstance(requested_streams, list) and requested_streams:
                stream_names = [str(stream) for stream in requested_streams]
            else:
                stream_names = list(self._streams)
            max_results = int(arguments.get("max_results") or 20)
            payload = page_governance_record_validation(
                self._page_trace_bundles,
                self._streams,
                page_slugs,
                stream_names,
                max_results=max_results,
            )
            return tool_text(json.dumps(payload, ensure_ascii=False, indent=2))
        if name == "get_page_governance_audit_review_checklist":
            page_slugs = lineage_page_slugs_from_arguments(arguments)
            requested_streams = arguments.get("streams")
            if isinstance(requested_streams, list) and requested_streams:
                stream_names = [str(stream) for stream in requested_streams]
            else:
                stream_names = list(self._streams)
            max_results = int(arguments.get("max_results") or 20)
            payload = page_governance_audit_review_checklist(
                self._page_trace_bundles,
                self._streams,
                page_slugs,
                stream_names,
                max_results=max_results,
            )
            return tool_text(json.dumps(payload, ensure_ascii=False, indent=2))
        if name == "get_page_governance_audit_review_queue":
            page_slugs = lineage_page_slugs_from_arguments(arguments)
            requested_streams = arguments.get("streams")
            if isinstance(requested_streams, list) and requested_streams:
                stream_names = [str(stream) for stream in requested_streams]
            else:
                stream_names = list(self._streams)
            max_results = int(arguments.get("max_results") or 20)
            payload = page_governance_audit_review_queue(
                self._page_trace_bundles,
                self._streams,
                page_slugs,
                stream_names,
                max_results=max_results,
            )
            return tool_text(json.dumps(payload, ensure_ascii=False, indent=2))
        if name == "get_page_governance_audit_evidence_packet":
            page_slug = str(arguments.get("page_slug") or "").strip()
            requested_streams = arguments.get("streams")
            if isinstance(requested_streams, list) and requested_streams:
                stream_names = [str(stream) for stream in requested_streams]
            else:
                stream_names = list(self._streams)
            raw_duckdb_path = str(arguments.get("duckdb_path") or "").strip()
            duckdb_path = Path(raw_duckdb_path) if raw_duckdb_path else resolve_path_env("MOSS_DUCKDB_PATH", DEFAULT_DUCKDB_PATH)
            max_results = int(arguments.get("max_results") or 20)
            payload = page_governance_audit_evidence_packet(
                self._page_trace_bundles,
                self._streams,
                page_slug,
                stream_names,
                duckdb_path,
                max_results=max_results,
            )
            return tool_text(json.dumps(payload, ensure_ascii=False, indent=2))
        if name == "get_page_governance_audit_evidence_packet_queue":
            page_slugs = lineage_page_slugs_from_arguments(arguments)
            requested_streams = arguments.get("streams")
            if isinstance(requested_streams, list) and requested_streams:
                stream_names = [str(stream) for stream in requested_streams]
            else:
                stream_names = list(self._streams)
            raw_duckdb_path = str(arguments.get("duckdb_path") or "").strip()
            duckdb_path = Path(raw_duckdb_path) if raw_duckdb_path else resolve_path_env("MOSS_DUCKDB_PATH", DEFAULT_DUCKDB_PATH)
            max_results = int(arguments.get("max_results") or 20)
            payload = page_governance_audit_evidence_packet_queue(
                self._page_trace_bundles,
                self._streams,
                page_slugs,
                stream_names,
                duckdb_path,
                max_results=max_results,
            )
            return tool_text(json.dumps(payload, ensure_ascii=False, indent=2))
        if name == "preflight_page_governance_record":
            page_slug = str(arguments.get("page_slug") or "").strip()
            raw_record = arguments.get("record")
            if not isinstance(raw_record, dict):
                raise McpError(-32602, "record must be an object.")
            payload = page_governance_record_preflight(self._page_trace_bundles, page_slug, raw_record)
            return tool_text(json.dumps(payload, ensure_ascii=False, indent=2))
        if name == "get_page_governance_record_blueprint":
            page_slug = str(arguments.get("page_slug") or "").strip()
            payload = page_governance_record_blueprint(self._page_trace_bundles, page_slug)
            return tool_text(json.dumps(payload, ensure_ascii=False, indent=2))
        if name == "get_page_governance_record_blueprint_queue":
            page_slugs = lineage_page_slugs_from_arguments(arguments)
            requested_streams = arguments.get("streams")
            if isinstance(requested_streams, list) and requested_streams:
                stream_names = [str(stream) for stream in requested_streams]
            else:
                stream_names = list(self._streams)
            max_results = int(arguments.get("max_results") or 20)
            payload = page_governance_record_blueprint_queue(
                self._page_trace_bundles,
                self._streams,
                page_slugs,
                stream_names,
                max_results=max_results,
            )
            return tool_text(json.dumps(payload, ensure_ascii=False, indent=2))
        if name == "get_page_governance_gap_queue":
            page_slugs = lineage_page_slugs_from_arguments(arguments)
            requested_streams = arguments.get("streams")
            if isinstance(requested_streams, list) and requested_streams:
                stream_names = [str(stream) for stream in requested_streams]
            else:
                stream_names = list(self._streams)
            max_results = int(arguments.get("max_results") or 20)
            payload = page_governance_gap_queue(
                self._page_trace_bundles,
                self._streams,
                page_slugs,
                stream_names,
                max_results=max_results,
            )
            return tool_text(json.dumps(payload, ensure_ascii=False, indent=2))
        return super().call_tool(name, arguments)

    def _stream_path(self, stream: str) -> Path:
        path = self._streams.get(stream)
        if path is None:
            raise McpError(-32602, f"Unknown governance stream: {stream}")
        return path


class DataCatalogProvider(McpProvider):
    name = "moss-data-catalog"

    def __init__(self) -> None:
        self._duckdb_path = resolve_path_env("MOSS_DUCKDB_PATH", DEFAULT_DUCKDB_PATH)
        self._governance_dir = resolve_path_env("MOSS_GOVERNANCE_PATH", DEFAULT_GOVERNANCE_DIR)
        self._schema_dir = REPO_ROOT / "backend" / "app" / "schema_registry" / "duckdb"
        self._page_trace_bundles = product_page_trace_bundles()
        self._streams = {
            "agent_audit": self._governance_dir / "agent_audit.jsonl",
            "cache_build_run": self._governance_dir / "cache_build_run.jsonl",
            "cache_manifest": self._governance_dir / "cache_manifest.jsonl",
            "snapshot_manifest": self._governance_dir / "snapshot_manifest.jsonl",
            "source_manifest": self._governance_dir / "source_manifest.jsonl",
            "source_manifest_latest": self._governance_dir / "source_manifest_latest.jsonl",
            "vendor_version_registry": self._governance_dir / "vendor_version_registry.jsonl",
        }

    def resources(self) -> list[dict[str, Any]]:
        return [
            text_resource(
                "moss://data-catalog/summary",
                "MOSS read-only data catalog summary",
                "DuckDB path, schema registry, table inventory, and available report-date hints.",
                mime_type="application/json",
            ),
            text_resource(
                "moss://data-catalog/schema-registry",
                "MOSS DuckDB schema registry",
                "SQL files under backend/app/schema_registry/duckdb.",
                mime_type="application/json",
            ),
            text_resource(
                "moss://data-catalog/tables",
                "MOSS DuckDB tables",
                "Read-only table inventory from information_schema.",
                mime_type="application/json",
            ),
        ]

    def read_resource(self, uri: str) -> dict[str, Any]:
        if uri == "moss://data-catalog/summary":
            payload = {
                "duckdb_path": str(self._duckdb_path),
                "duckdb_exists": self._duckdb_path.is_file(),
                "schema_registry": schema_registry_summary(self._schema_dir),
                "tables": duckdb_tables(self._duckdb_path, limit=80),
            }
            return resource_content(uri, json.dumps(payload, ensure_ascii=False, indent=2), "application/json")
        if uri == "moss://data-catalog/schema-registry":
            payload = schema_registry_summary(self._schema_dir)
            return resource_content(uri, json.dumps(payload, ensure_ascii=False, indent=2), "application/json")
        if uri == "moss://data-catalog/tables":
            payload = {"tables": duckdb_tables(self._duckdb_path, limit=500)}
            return resource_content(uri, json.dumps(payload, ensure_ascii=False, indent=2), "application/json")
        raise McpError(-32602, f"Unknown resource: {uri}")

    def tools(self) -> list[dict[str, Any]]:
        return [
            {
                "name": "describe_table",
                "description": "Describe one DuckDB table using information_schema only.",
                "inputSchema": {
                    "type": "object",
                    "properties": {"table_name": {"type": "string"}},
                    "required": ["table_name"],
                },
            },
            {
                "name": "list_available_dates",
                "description": "List distinct dates for a known date column on one DuckDB table.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "table_name": {"type": "string"},
                        "date_column": {"type": "string", "default": "report_date"},
                        "limit": {"type": "integer", "minimum": 1, "maximum": 200},
                    },
                    "required": ["table_name"],
                },
            },
            {
                "name": "get_page_catalog_date_evidence",
                "description": (
                    "Sample configured DuckDB table and date-column evidence for seeded pages without proving "
                    "lineage, page execution, metric definition, or formal approval."
                ),
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "page_slugs": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Optional seeded page slugs, page IDs, or route aliases to sample.",
                        },
                        "limit": {
                            "type": "integer",
                            "minimum": 1,
                            "maximum": 200,
                            "description": "Maximum distinct date values to sample per table.",
                        },
                    },
                },
            },
            {
                "name": "get_page_catalog_date_coverage",
                "description": (
                    "Report which seeded pages have explicit catalog/date table configuration, without sampling "
                    "DuckDB tables or granting approval."
                ),
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "page_slugs": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Optional seeded page slugs, page IDs, or route aliases to check.",
                        }
                    },
                },
            },
            {
                "name": "get_page_catalog_date_lineage_review_queue",
                "description": (
                    "Return a read-only prioritized queue for catalog/date plus lineage review across seeded pages, "
                    "without sampling DuckDB tables, checking lineage records, proving page execution, or granting "
                    "approval."
                ),
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "page_slugs": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Optional seeded page slugs, page IDs, or route aliases to queue.",
                        }
                    },
                },
            },
        ]

    def call_tool(self, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        if name == "describe_table":
            table_name = str(arguments.get("table_name") or "").strip()
            payload = describe_duckdb_table(self._duckdb_path, table_name)
            return tool_text(json.dumps(payload, ensure_ascii=False, indent=2))
        if name == "list_available_dates":
            table_name = str(arguments.get("table_name") or "").strip()
            date_column = str(arguments.get("date_column") or "report_date").strip()
            limit = int(arguments.get("limit") or 50)
            payload = list_available_dates(self._duckdb_path, table_name, date_column, limit=limit)
            return tool_text(json.dumps(payload, ensure_ascii=False, indent=2))
        if name == "get_page_catalog_date_evidence":
            raw_page_slugs = arguments.get("page_slugs")
            if raw_page_slugs is None:
                page_slugs = DEFAULT_EVIDENCE_READINESS_PAGES
            elif isinstance(raw_page_slugs, list):
                page_slugs = [str(item).strip() for item in raw_page_slugs if str(item).strip()]
            else:
                raise McpError(-32602, "page_slugs must be an array of strings.")
            limit = int(arguments.get("limit") or 5)
            payload = page_catalog_date_evidence(
                self._page_trace_bundles,
                self._duckdb_path,
                page_slugs,
                limit=limit,
            )
            return tool_text(json.dumps(payload, ensure_ascii=False, indent=2))
        if name == "get_page_catalog_date_coverage":
            raw_page_slugs = arguments.get("page_slugs")
            if raw_page_slugs is None:
                page_slugs = []
            elif isinstance(raw_page_slugs, list):
                page_slugs = [str(item).strip() for item in raw_page_slugs if str(item).strip()]
            else:
                raise McpError(-32602, "page_slugs must be an array of strings.")
            payload = page_catalog_date_coverage(self._page_trace_bundles, page_slugs)
            return tool_text(json.dumps(payload, ensure_ascii=False, indent=2))
        if name == "get_page_catalog_date_lineage_review_queue":
            raw_page_slugs = arguments.get("page_slugs")
            if raw_page_slugs is None:
                page_slugs = []
            elif isinstance(raw_page_slugs, list):
                page_slugs = [str(item).strip() for item in raw_page_slugs if str(item).strip()]
            else:
                raise McpError(-32602, "page_slugs must be an array of strings.")
            payload = page_catalog_date_lineage_review_queue(
                self._page_trace_bundles,
                page_slugs,
                streams=self._streams,
                stream_names=list(self._streams),
            )
            return tool_text(json.dumps(payload, ensure_ascii=False, indent=2))
        return super().call_tool(name, arguments)


class DataQualityProvider(McpProvider):
    name = "moss-data-quality"

    def __init__(self) -> None:
        self._duckdb_path = resolve_path_env("MOSS_DUCKDB_PATH", DEFAULT_DUCKDB_PATH)

    def resources(self) -> list[dict[str, Any]]:
        return [
            text_resource(
                "moss://data-quality/summary",
                "MOSS DuckDB data-quality summary",
                "Read-only table/view quality targets and DuckDB availability.",
                mime_type="application/json",
            ),
            text_resource(
                "moss://data-quality/targets",
                "MOSS DuckDB quality targets",
                "Read-only list of table/view targets eligible for quality profiling.",
                mime_type="application/json",
            ),
        ]

    def read_resource(self, uri: str) -> dict[str, Any]:
        if uri == "moss://data-quality/summary":
            payload = {
                "duckdb_path": str(self._duckdb_path),
                "duckdb_exists": self._duckdb_path.is_file(),
                "targets": duckdb_quality_targets(self._duckdb_path, limit=80),
            }
            return resource_content(uri, json.dumps(payload, ensure_ascii=False, indent=2), "application/json")
        if uri == "moss://data-quality/targets":
            payload = {"targets": duckdb_quality_targets(self._duckdb_path, limit=500)}
            return resource_content(uri, json.dumps(payload, ensure_ascii=False, indent=2), "application/json")
        raise McpError(-32602, f"Unknown resource: {uri}")

    def tools(self) -> list[dict[str, Any]]:
        return [
            {
                "name": "list_quality_targets",
                "description": "List read-only DuckDB tables/views eligible for quality summaries.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "limit": {"type": "integer", "minimum": 1, "maximum": 200},
                    },
                },
            },
            {
                "name": "get_quality_summary",
                "description": "Compute a read-only quality summary for one known DuckDB table or view.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "table_name": {"type": "string"},
                        "column_limit": {"type": "integer", "minimum": 1, "maximum": 100},
                    },
                    "required": ["table_name"],
                },
            },
        ]

    def call_tool(self, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        if name == "list_quality_targets":
            limit = int(arguments.get("limit") or 50)
            payload = {"targets": duckdb_quality_targets(self._duckdb_path, limit=limit)}
            return tool_text(json.dumps(payload, ensure_ascii=False, indent=2))
        if name == "get_quality_summary":
            table_name = str(arguments.get("table_name") or "").strip()
            column_limit = int(arguments.get("column_limit") or 25)
            payload = duckdb_quality_summary(self._duckdb_path, table_name, column_limit=column_limit)
            return tool_text(json.dumps(payload, ensure_ascii=False, indent=2))
        return super().call_tool(name, arguments)


def build_provider(mode: str) -> McpProvider:
    providers: dict[str, Callable[[], McpProvider]] = {
        "metric-contracts": MetricContractsProvider,
        "lineage-evidence": LineageEvidenceProvider,
        "data-catalog": DataCatalogProvider,
        "data-quality": DataQualityProvider,
    }
    return providers[mode]()


def text_resource(uri: str, name: str, description: str, *, mime_type: str = "text/plain") -> dict[str, Any]:
    return {"uri": uri, "name": name, "description": description, "mimeType": mime_type}


def resource_content(uri: str, text: str, mime_type: str) -> dict[str, Any]:
    return {"uri": uri, "mimeType": mime_type, "text": text}


def tool_text(text: str, *, is_error: bool = False) -> dict[str, Any]:
    return {"content": [{"type": "text", "text": text}], "isError": is_error}


def read_text(path: Path) -> str:
    safe_path = assert_repo_path(path)
    if not safe_path.is_file():
        raise McpError(-32602, f"File does not exist: {safe_path}")
    return safe_path.read_text(encoding="utf-8", errors="replace")


def assert_repo_path(path: Path) -> Path:
    resolved = path.resolve()
    if not is_relative_to(resolved, REPO_ROOT):
        raise McpError(-32602, f"Path is outside repo: {resolved}")
    return resolved


def is_relative_to(path: Path, base: Path) -> bool:
    try:
        path.resolve().relative_to(base.resolve())
        return True
    except ValueError:
        return False


def resolve_path_env(env_name: str, fallback: Path) -> Path:
    raw = str(os.environ.get(env_name) or "").strip()
    if not raw:
        return fallback.resolve()
    candidate = Path(raw)
    if candidate.is_absolute():
        return candidate.resolve()
    return (REPO_ROOT / candidate).resolve()


def product_page_trace_bundles() -> dict[str, dict[str, Any]]:
    product_category_bundle = {
        "page_slug": "product-category-pnl",
        "page_id": "PAGE-PROD-CAT-001",
        "page_name": "Product-category PnL",
        "aliases": [
            "product-category-pnl",
            "/product-category-pnl",
            "product_category_pnl",
            "PAGE-PROD-CAT-001",
            "PAGE-PROD-CAT-PNL-001",
        ],
        "frontend_route": "/product-category-pnl",
        "primary_api": "/ui/pnl/product-category",
        "supporting_apis": [
            "/ui/pnl/product-category/dates",
            "/ui/pnl/product-category/refresh",
            "/ui/pnl/product-category/refresh-status",
            "/ui/pnl/product-category/manual-adjustments",
            "/ui/pnl/product-category/manual-adjustments/export",
        ],
        "contract_docs": [
            "docs/pnl/product-category-page-truth-contract.md",
            "docs/pnl/adr-product-category-truth-chain.md",
            "docs/pnl/product-category-golden-sample-a.md",
            "docs/pnl/product-category-closure-checklist.md",
            "docs/BALANCE_ANALYSIS_SPEC_FOR_CODEX.md",
        ],
        "truth_chain": [
            "paired ledger reconciliation workbook + daily average workbook",
            "backend/app/services/product_category_source_service.py",
            "backend/app/core_finance/product_category_pnl.py",
            "product_category_pnl_formal_read_model",
            "backend/app/services/product_category_pnl_service.py",
            "/ui/pnl/product-category",
            "frontend/src/features/product-category-pnl/pages/ProductCategoryPnlPage.tsx",
        ],
        "backend_touchpoints": [
            "backend/app/services/product_category_source_service.py",
            "backend/app/core_finance/config/product_category_mapping.py",
            "backend/app/core_finance/product_category_pnl.py",
            "backend/app/services/product_category_pnl_service.py",
            "backend/app/api/routes/product_category_pnl.py",
            "backend/app/schemas/product_category_pnl.py",
            "backend/app/repositories/product_category_pnl_repo.py",
            "backend/app/tasks/product_category_pnl.py",
            "backend/app/schema_registry/duckdb/08_product_category_pnl.sql",
        ],
        "frontend_touchpoints": [
            "frontend/src/api/pnlClient.ts",
            "frontend/src/api/contracts.ts",
            "frontend/src/features/product-category-pnl/pages/ProductCategoryPnlPage.tsx",
            "frontend/src/features/product-category-pnl/pages/productCategoryPnlPageModel.ts",
            "frontend/src/features/product-category-pnl/pages/ProductCategoryAdjustmentAuditPage.tsx",
        ],
        "test_touchpoints": [
            "tests/test_product_category_pnl_flow.py",
            "tests/test_product_category_mapping_contract.py",
            "frontend/src/test/ProductCategoryPnlPage.test.tsx",
            "frontend/src/test/ProductCategoryBranchSwitcher.test.tsx",
            "frontend/src/test/ProductCategoryAdjustmentAuditPage.test.tsx",
            "frontend/src/features/product-category-pnl/pages/productCategoryPnlPageModel.test.ts",
            "tests/golden_samples/GS-PROD-CAT-PNL-A/assertions.md",
        ],
        "golden_samples": ["tests/golden_samples/GS-PROD-CAT-PNL-A"],
        "verification_focus": [
            "Trace API response through adapter/model state into ProductCategoryPnlPage before changing display logic.",
            "Check units, precision, null-vs-zero semantics, report_date resolution, fallback/stale flags, and result_meta visibility.",
            "Keep baseline and scenario row identity stable; scenario_rate_pct must not redefine the category tree.",
            "Do not recompute governed totals in the frontend; display backend totals.",
        ],
        "guardrails": [
            "Do not infer product-category row meaning from zqtz holdings-side logic, holdings buckets, or research-style bond categories.",
            "Use the paired ledger reconciliation + daily average source chain as the row authority.",
            "Use backend/app/core_finance/config/product_category_mapping.py and backend/app/core_finance/product_category_pnl.py for governed row meaning.",
            "Do not add qtd or year_to_report_month_end to the main page selector without updating the page contract, closure checklist, and tests.",
            "Treat missing standalone as_of_date as an explicit contract gap, not an assumption.",
        ],
    }
    dashboard_home_bundle = {
        "page_slug": "dashboard-home",
        "page_id": "PAGE-DASH-001",
        "page_name": "Dashboard Home",
        "aliases": [
            "dashboard-home",
            "dashboard",
            "/dashboard",
            "/",
            "PAGE-DASH-001",
        ],
        "frontend_route": "/",
        "primary_api": "/ui/home/snapshot",
        "supporting_apis": [
            "/ui/home/overview",
            "/ui/home/summary",
            "/api/dashboard/core_metrics",
            "/api/dashboard/daily-changes",
            "/api/bond-dashboard/headline-kpis",
            "/api/bond-analytics/portfolio-headlines",
            "/ui/market-data/rates",
            "/ui/calendar/supply-auctions",
        ],
        "contract_docs": [
            "docs/page_contracts.md",
            "docs/dashboard_cockpit_contract.md",
            "docs/metric_dictionary.md",
            "docs/golden_sample_catalog.md",
        ],
        "truth_chain": [
            "docs/page_contracts.md PAGE-DASH-001",
            "docs/dashboard_cockpit_contract.md",
            "backend/app/services/executive_service.py home_snapshot_envelope",
            "backend/app/api/routes/executive.py GET /ui/home/snapshot",
            "frontend/src/api/executiveHomeSnapshotFetch.ts",
            "frontend/src/features/workbench/pages/useDashboardSnapshotBoundary.ts",
            "frontend/src/features/workbench/pages/DashboardPage.tsx",
        ],
        "backend_touchpoints": [
            "backend/app/api/routes/executive.py",
            "backend/app/services/executive_service.py",
            "backend/app/services/dashboard_service.py",
            "backend/app/services/bond_dashboard_service.py",
            "backend/app/schemas/executive_dashboard.py",
        ],
        "frontend_touchpoints": [
            "frontend/src/router/routes.tsx",
            "frontend/src/api/executiveClient.ts",
            "frontend/src/api/executiveHomeSnapshotFetch.ts",
            "frontend/src/api/contracts.ts",
            "frontend/src/features/workbench/pages/DashboardPage.tsx",
            "frontend/src/features/workbench/pages/useDashboardSnapshotBoundary.ts",
            "frontend/src/features/workbench/dashboard/dashboardHomeModel.ts",
            "frontend/src/features/workbench/dashboard/dashboardCockpitHomeModel.ts",
            "frontend/src/features/workbench/dashboard/sections/DashboardCockpitHeader.tsx",
            "frontend/src/features/workbench/dashboard/sections/DashboardJudgmentStrip.tsx",
        ],
        "test_touchpoints": [
            "tests/test_home_snapshot_endpoint.py",
            "tests/test_dashboard_api_contract.py",
            "tests/test_executive_dashboard_endpoints.py",
            "tests/test_executive_service_contract.py",
            "frontend/src/test/DashboardPage.test.tsx",
            "frontend/src/features/workbench/pages/useDashboardSnapshotBoundary.test.tsx",
            "frontend/src/features/workbench/dashboard/dashboardHomeModel.test.ts",
            "frontend/src/features/workbench/dashboard/dashboardCockpitHomeModel.test.ts",
            "frontend/src/features/workbench/dashboard/sections/DashboardCockpitHeader.test.tsx",
        ],
        "golden_samples": [
            "tests/golden_samples/GS-EXEC-OVERVIEW-A",
            "tests/golden_samples/GS-EXEC-PNL-ATTR-A",
            "tests/golden_samples/GS-EXEC-SUMMARY-A",
        ],
        "verification_focus": [
            "Treat /ui/home/snapshot as the primary report-date, verdict, governance-status, and lineage source.",
            "Trace snapshot result through getHomeSnapshot, useDashboardSnapshotBoundary, dashboardHomeModel, dashboardCockpitHomeModel, and DashboardPage before changing display logic.",
            "Keep supplemental surfaces gated by report_date equality with the snapshot report_date before first-screen trust.",
            "Check analytical basis, partial-mode domains, stale/fallback/vendor flags, mock fallback warnings, and reserved endpoint visibility.",
        ],
        "guardrails": [
            "Do not promote dashboard-home aggregate values to formal metric truth without updating metric_dictionary and page contracts.",
            "Do not request or render reserved /ui/risk/overview, /ui/home/alerts, or /ui/home/contribution as normal first-screen conclusions.",
            "Do not fill missing homepage snapshot fields with demo, reserved, or stale figures in real mode.",
            "Do not recompute formal business metrics in the frontend; consume backend-owned snapshot and supplemental payloads.",
            "Treat the aggregate homepage as analytical/mixed-source; its executive golden samples cover sub-surfaces, not a full-page formal sample.",
        ],
    }
    executive_overview_bundle = {
        "page_slug": "executive-overview",
        "page_id": "PAGE-EXEC-OVERVIEW-001",
        "page_name": "Executive Overview",
        "aliases": [
            "executive-overview",
            "executive_overview",
            "/ui/home/overview",
            "PAGE-EXEC-OVERVIEW-001",
        ],
        "frontend_route": "/dashboard",
        "primary_api": "/ui/home/overview",
        "supporting_apis": [
            "/ui/home/snapshot",
            "/ui/home/summary",
        ],
        "contract_docs": [
            "docs/page_contracts.md",
            "docs/metric_dictionary.md",
            "docs/golden_sample_catalog.md",
            "docs/dashboard_cockpit_contract.md",
        ],
        "truth_chain": [
            "docs/page_contracts.md PAGE-EXEC-OVERVIEW-001",
            "docs/metric_dictionary.md MTR-EXEC-001 through MTR-EXEC-004 and MTR-EXEC-004A/B/C",
            "backend/app/services/executive_service.py executive_overview",
            "backend/app/schemas/executive_dashboard.py OverviewPayload and ExecutiveMetric.caliber_label",
            "executive.overview result_meta",
            "/ui/home/overview",
            "frontend/src/features/executive-dashboard/components/OverviewSection.tsx",
        ],
        "backend_touchpoints": [
            "backend/app/api/routes/executive.py",
            "backend/app/services/executive_service.py",
            "backend/app/schemas/executive_dashboard.py",
        ],
        "frontend_touchpoints": [
            "frontend/src/api/executiveClient.ts",
            "frontend/src/api/contracts.ts",
            "frontend/src/features/executive-dashboard/components/OverviewSection.tsx",
            "frontend/src/features/executive-dashboard/selectors/executiveDashboardSelectors.ts",
            "frontend/src/features/executive-dashboard/adapters/executiveDashboardAdapter.ts",
        ],
        "test_touchpoints": [
            "tests/test_executive_dashboard_endpoints.py",
            "tests/test_executive_service_contract.py",
            "tests/test_executive_release_contract.py",
            "tests/test_executive_dashboard_numeric_migration.py",
            "tests/test_golden_samples_capture_ready.py",
            "frontend/src/test/OverviewSection.test.tsx",
            "frontend/src/features/executive-dashboard/components/OverviewSection.states.test.tsx",
            "frontend/src/features/executive-dashboard/selectors/executiveDashboardSelectors.test.ts",
            "frontend/src/features/executive-dashboard/adapters/executiveDashboardAdapter.test.ts",
            "tests/golden_samples/GS-EXEC-OVERVIEW-A/assertions.md",
        ],
        "golden_samples": ["tests/golden_samples/GS-EXEC-OVERVIEW-A"],
        "verification_focus": [
            "Trace /ui/home/overview result_meta through executive_overview, getOverview, the dashboard adapter/selectors, and OverviewSection before changing display logic.",
            "Check analytical basis, report_date selection, metric IDs, caliber_label display, domain effective-date labels, and no silent mock fallback.",
            "Verify GS-EXEC-OVERVIEW-A remains an executive analytical overlay sample and does not redefine formal balance, formal PnL, or risk-tensor truth.",
        ],
        "guardrails": [
            "Treat this as an analytical overlay for management summary, not a formal source-of-truth page.",
            "Do not replace formal balance, formal PnL, risk tensor, or PnL bridge evidence with executive overview cards.",
            "Do not hide metric caliber_label, result_meta, quality, fallback, vendor, or date-resolution boundaries.",
            "Do not allow silent downgrade to mock/demo values when /ui/home/overview cannot resolve governed inputs.",
            "Keep MTR-EXEC-004A/B/C as management-risk split components; do not collapse them into a new formal risk metric without updating contracts and tests.",
        ],
    }
    executive_summary_bundle = {
        "page_slug": "executive-summary",
        "page_id": "PAGE-EXEC-SUMMARY-001",
        "page_name": "Executive Summary",
        "aliases": [
            "executive-summary",
            "executive_summary",
            "/ui/home/summary",
            "PAGE-EXEC-SUMMARY-001",
        ],
        "frontend_route": "/dashboard",
        "primary_api": "/ui/home/summary",
        "supporting_apis": [
            "/ui/home/overview",
            "/ui/home/snapshot",
        ],
        "contract_docs": [
            "docs/page_contracts.md",
            "docs/metric_dictionary.md",
            "docs/golden_sample_catalog.md",
            "docs/dashboard_cockpit_contract.md",
        ],
        "truth_chain": [
            "docs/page_contracts.md PAGE-EXEC-SUMMARY-001",
            "docs/metric_dictionary.md GS-EXEC-SUMMARY-A is narrative-only and does not enter the business metric dictionary main table",
            "docs/golden_sample_catalog.md GS-EXEC-SUMMARY-A freezes title, points.length, and point labels for /ui/home/summary",
            "backend/app/services/executive_service.py executive_summary",
            "backend/app/schemas/executive_dashboard.py SummaryPayload title/report_date/narrative/points",
            "executive.summary result_meta",
            "/ui/home/summary",
            "frontend/src/api/executiveClient.ts getSummary",
            "frontend/src/features/executive-dashboard/components/SummarySection.tsx",
        ],
        "backend_touchpoints": [
            "backend/app/api/routes/executive.py",
            "backend/app/services/executive_service.py",
            "backend/app/schemas/executive_dashboard.py",
        ],
        "frontend_touchpoints": [
            "frontend/src/api/executiveClient.ts",
            "frontend/src/api/contracts.ts",
            "frontend/src/features/executive-dashboard/components/SummarySection.tsx",
        ],
        "test_touchpoints": [
            "tests/test_executive_service_contract.py",
            "tests/test_executive_dashboard_endpoints.py",
            "tests/test_executive_release_contract.py",
            "tests/test_golden_samples_capture_ready.py",
            "tests/golden_samples/GS-EXEC-SUMMARY-A/assertions.md",
        ],
        "golden_samples": ["tests/golden_samples/GS-EXEC-SUMMARY-A"],
        "verification_focus": [
            "Trace /ui/home/summary through executive_summary, SummaryPayload, getSummary, SummarySection, and GS-EXEC-SUMMARY-A before changing narrative display logic.",
            "Check report_date selection, narrative text, title, points length, point labels, result_meta.result_kind=executive.summary, source_version, and rule_version.",
            "Verify summary narrative does not hide upstream overview, formal balance, formal PnL, risk, or attribution no-data/fallback/stale states.",
        ],
        "guardrails": [
            "Treat PAGE-EXEC-SUMMARY-001 as a narrative-only contract, not a formal business metric surface.",
            "Do not add executive summary narrative fields to the metric dictionary main table or promote them to MTR-* rows.",
            "Do not use narrative text as formal source-of-truth evidence or as a substitute for formal balance, formal PnL, risk tensor, PnL bridge, or attribution truth.",
            "Do not use narrative text to cover upstream metric missing-data, stale, fallback, vendor, no-data, or error states.",
            "Keep GS-EXEC-SUMMARY-A scoped to title, points.length, point labels, and result_meta lineage for the summary endpoint.",
        ],
    }
    balance_analysis_bundle = {
        "page_slug": "balance-analysis",
        "page_id": "PAGE-BALANCE-001",
        "page_name": "Balance Analysis",
        "aliases": [
            "balance-analysis",
            "/balance-analysis",
            "balance_analysis",
            "PAGE-BALANCE-001",
            "/ui/balance-analysis/overview",
        ],
        "frontend_route": "/balance-analysis",
        "primary_api": "/ui/balance-analysis/overview",
        "supporting_apis": [
            "/ui/balance-analysis/dates",
            "/ui/balance-analysis",
            "/ui/balance-analysis/workbook",
            "/ui/balance-analysis/summary",
            "/ui/balance-analysis/summary-by-basis",
            "/ui/balance-analysis/decision-items",
            "/ui/balance-analysis/current-user",
            "/ui/balance-analysis/advanced-attribution",
            "/ui/balance-analysis/refresh",
            "/ui/balance-analysis/refresh-status",
        ],
        "contract_docs": [
            "docs/page_contracts.md",
            "docs/metric_dictionary.md",
            "docs/golden_sample_catalog.md",
            "docs/calc_rules.md",
            "docs/BALANCE_ANALYSIS_SPEC_FOR_CODEX.md",
            "docs/balance_analysis_field_trace.md",
        ],
        "truth_chain": [
            "docs/page_contracts.md PAGE-BALANCE-001",
            "docs/metric_dictionary.md MTR-BAL-001 through MTR-BAL-006, MTR-BAL-101 through MTR-BAL-105, and MTR-BAL-201 through MTR-BAL-203",
            "backend/app/schema_registry/duckdb/05_balance_analysis.sql fact_formal_zqtz_balance_daily + fact_formal_tyw_balance_daily",
            "backend/app/tasks/balance_analysis_materialize.py materialize_balance_analysis_facts",
            "backend/app/services/balance_analysis_service.py balance_analysis_overview_envelope",
            "BalanceAnalysisWorkbookPayload",
            "/ui/balance-analysis/overview",
            "frontend/src/features/balance-analysis/pages/BalanceAnalysisPage.tsx",
        ],
        "backend_touchpoints": [
            "backend/app/api/routes/balance_analysis.py",
            "backend/app/services/balance_analysis_service.py",
            "backend/app/services/balance_analysis_workbook_service.py",
            "backend/app/core_finance/balance_analysis.py",
            "backend/app/core_finance/balance_analysis_workbook.py",
            "backend/app/schemas/balance_analysis.py",
            "backend/app/repositories/balance_analysis_repo.py",
            "backend/app/repositories/balance_analysis_decision_repo.py",
            "backend/app/tasks/balance_analysis_materialize.py",
            "backend/app/schema_registry/duckdb/05_balance_analysis.sql",
        ],
        "frontend_touchpoints": [
            "frontend/src/api/client.ts",
            "frontend/src/api/contracts.ts",
            "frontend/src/features/balance-analysis/pages/BalanceAnalysisPage.tsx",
            "frontend/src/features/balance-analysis/pages/balanceAnalysisPageModel.ts",
            "frontend/src/features/balance-analysis/components/BalanceAnalysisWorkbenchLayout.tsx",
        ],
        "test_touchpoints": [
            "tests/test_balance_analysis_api.py",
            "tests/test_balance_analysis_contracts.py",
            "tests/test_balance_analysis_core.py",
            "tests/test_balance_analysis_materialize_flow.py",
            "tests/test_balance_analysis_service.py",
            "tests/test_balance_analysis_boundary_guards.py",
            "tests/test_balance_analysis_workbook_contract.py",
            "tests/test_balance_analysis_module_registration_flow.py",
            "frontend/src/test/BalanceAnalysisPage.test.tsx",
            "tests/test_golden_samples_capture_ready.py",
        ],
        "golden_samples": [
            "tests/golden_samples/GS-BAL-OVERVIEW-A",
            "tests/golden_samples/GS-BAL-WORKBOOK-A",
        ],
        "verification_focus": [
            "Trace /ui/balance-analysis/overview result_meta through getBalanceAnalysisOverview, buildBalanceAnalysisPageModel, BalanceAnalysisPage, and the formal meta panel before changing display logic.",
            "Check report_date, position_scope, currency_basis, source_version, rule_version, cache_version, trace_id, and fallback/stale visibility.",
            "Check units and null-vs-zero semantics for total market value, amortized cost, accrued interest, detail rows, summary rows, workbook sections, and basis breakdown.",
            "Keep workbook structural truth separate from advanced attribution; advanced_attribution is an analytical/scenario boundary, not formal balance truth.",
        ],
        "guardrails": [
            "Do not replace formal balance truth with snapshot, preview, ADB analytical preview, or advanced_attribution_bundle output.",
            "Do not write advanced_attribution_bundle as a currently governed workbook section.",
            "Do not recompute governed balance metrics, row counts, position_scope, currency_basis, invest_type_std, accounting_basis, or source_family in the frontend.",
            "Keep fallback_mode, stale/vendor status, result_meta, and no-data states visible on the frontend.",
            "Use fact_formal_zqtz_balance_daily and fact_formal_tyw_balance_daily as the formal balance read authority.",
        ],
    }
    average_balance_bundle = {
        "page_slug": "average-balance",
        "page_id": "GAP-AVERAGE-BALANCE-PAGE",
        "page_name": "Average Balance",
        "aliases": [
            "average-balance",
            "average_balance",
            "/average-balance",
            "GAP-AVERAGE-BALANCE-PAGE",
            "/api/analysis/adb",
            "/api/analysis/adb/comparison",
            "/api/analysis/adb/monthly",
            "/api/analysis/adb/coverage",
        ],
        "frontend_route": "/average-balance",
        "primary_api": "/api/analysis/adb",
        "supporting_apis": [
            "/api/analysis/adb/comparison",
            "/api/analysis/adb/monthly",
            "/api/analysis/adb/coverage",
            "/ui/balance-analysis/dates",
        ],
        "contract_docs": [
            "docs/live_route_maturity.md",
            "docs/metric_dictionary.md",
            "docs/page_contracts.md",
        ],
        "truth_chain": [
            "docs/live_route_maturity.md marks /average-balance as temporary-exception with page id GAP-AVERAGE-BALANCE-PAGE.",
            "docs/metric_dictionary.md registers MTR-ADB-001 through MTR-ADB-003 as candidate metrics only.",
            "docs/metric_dictionary.md keeps bound_page_id=PAGE-CONTRACT-PENDING:/average-balance and bound_sample_id=none for the ADB candidate metrics.",
            "GET /api/analysis/adb returns interval ADB analysis for the visible /average-balance route.",
            "GET /api/analysis/adb/monthly returns selected-year monthly ADB trend evidence.",
            "GET /api/analysis/adb/comparison and /api/analysis/adb/coverage support comparison and coverage diagnostics.",
            "PAGE-BALANCE-001 and /balance-analysis remain the formal balance truth; this route is analytical ADB candidate evidence only.",
        ],
        "backend_touchpoints": [
            "backend/app/api/routes/adb_analysis.py",
            "backend/app/services/adb_analysis_service.py",
            "backend/app/core_finance/adb_analytics.py",
            "backend/app/api/routes/balance_analysis.py",
            "backend/app/services/balance_analysis_service.py",
        ],
        "frontend_touchpoints": [
            "frontend/src/features/average-balance/components/AverageBalanceView.tsx",
            "frontend/src/api/contracts.ts",
            "frontend/src/api/client.ts",
            "frontend/src/router/routes.tsx",
        ],
        "test_touchpoints": [
            "tests/test_adb_analysis_api.py",
            "tests/test_result_meta_on_all_ui_endpoints.py",
            "frontend/src/test/AverageBalanceView.test.tsx",
        ],
        "golden_samples": [],
        "verification_focus": [
            "No dedicated golden sample is currently registered for GAP-AVERAGE-BALANCE-PAGE; verify through live-route maturity, ADB API tests, result_meta checks, and AverageBalanceView tests.",
            "Trace /api/analysis/adb, comparison, monthly, and coverage payloads through AverageBalanceView query state, boundary chips, charts, and result_meta display before changing page logic.",
            "Check observed, LOCF, and calendar-zero denominator semantics, selected date range, monthly/YTD basis, amount unit conversion, percent precision, null-vs-zero behavior, and fallback/no-data states.",
        ],
        "guardrails": [
            "GAP-AVERAGE-BALANCE-PAGE is candidate ADB analysis, not formal balance truth.",
            "Do not replace formal balance truth from PAGE-BALANCE-001 or /balance-analysis with ADB interval, comparison, monthly, or coverage output.",
            "Do not promote MTR-ADB-001 through MTR-ADB-003 to formal use until a dedicated PAGE contract, golden sample, lineage records, manual audit, and owner approval exist.",
            "Do not hide candidate, stale, fallback, no-data, denominator, date-range, or result_meta boundaries behind a successful /average-balance shell.",
            "Do not backfill missing ADB rows, monthly rows, comparison rows, or coverage diagnostics with static demo values in real mode.",
        ],
    }
    decision_items_bundle = {
        "page_slug": "decision-items",
        "page_id": "GAP-DECISION-ITEMS-PAGE",
        "page_name": "Decision Items",
        "aliases": [
            "decision-items",
            "decision_items",
            "/decision-items",
            "GAP-DECISION-ITEMS-PAGE",
            "/ui/balance-analysis/decision-items",
            "/ui/balance-analysis/decision-items/status",
        ],
        "frontend_route": "/decision-items",
        "primary_api": "/ui/balance-analysis/decision-items",
        "supporting_apis": [
            "/ui/balance-analysis/dates",
            "/ui/balance-analysis/current-user",
            "/ui/balance-analysis/decision-items/status",
        ],
        "contract_docs": [
            "docs/live_route_maturity.md",
            "docs/page_contracts.md",
            "docs/metric_dictionary.md",
        ],
        "truth_chain": [
            "docs/live_route_maturity.md marks /decision-items as temporary-exception with page id GAP-DECISION-ITEMS-PAGE.",
            "docs/page_contracts.md documents decision items as a PAGE-BALANCE-001 section, not as standalone formal page closure.",
            "GET /ui/balance-analysis/decision-items reads generated balance-analysis governance action items.",
            "POST /ui/balance-analysis/decision-items/status writes decision status records to balance_analysis_decision_status governance stream.",
            "GET /ui/balance-analysis/current-user exposes can_write_decision_status so the page can hide write actions when permission is absent or unknown.",
            "backend/app/repositories/balance_analysis_decision_repo.py stores latest status overlays in balance_analysis_decision_status.",
            "fact_formal_zqtz_balance_daily and fact_formal_tyw_balance_daily remain the upstream formal balance data anchors through PAGE-BALANCE-001.",
        ],
        "backend_touchpoints": [
            "backend/app/api/routes/balance_analysis.py",
            "backend/app/services/balance_analysis_service.py",
            "backend/app/repositories/balance_analysis_decision_repo.py",
            "backend/app/repositories/balance_analysis_repo.py",
            "backend/app/security/route_policy.py",
            "backend/app/schemas/balance_analysis.py",
        ],
        "frontend_touchpoints": [
            "frontend/src/api/balanceAnalysisClient.ts",
            "frontend/src/api/contracts.ts",
            "frontend/src/features/decision-items/pages/DecisionItemsPage.tsx",
            "frontend/src/features/decision-items/lib/decisionItemsPageModel.ts",
            "frontend/src/router/routes.tsx",
            "frontend/src/mocks/navigation.ts",
        ],
        "test_touchpoints": [
            "tests/test_balance_analysis_api.py",
            "tests/test_balance_analysis_service.py",
            "tests/test_write_route_auth_contract.py",
            "tests/test_live_route_page_contract_completeness.py",
            "frontend/src/test/DecisionItemsPage.test.tsx",
            "frontend/src/test/DecisionItemsRoute.test.tsx",
            "frontend/src/test/decisionItemsPageModel.test.ts",
        ],
        "golden_samples": [],
        "verification_focus": [
            "No dedicated golden sample is currently registered for GAP-DECISION-ITEMS-PAGE; verify through live-route maturity, balance-analysis API/service tests, decision-items frontend tests, write-route auth tests, and governance record evidence.",
            "Trace /decision-items through DecisionItemsPage queries, buildDecisionItemsPageViewModel, result_meta panels, permission banners, and action buttons before changing display logic.",
            "Check report_date, position_scope, currency_basis, result_meta, latest status overlay, missing/no-data/error states, and permissions before treating the page as ready.",
            "Verify write actions require balance_analysis.decision_status/write and that status writes do not imply page approval, owner signoff, or formal business metric closure.",
        ],
        "guardrails": [
            "GAP-DECISION-ITEMS-PAGE is a candidate read/write governance queue; do not claim standalone formal page truth or business-owner closure.",
            "Do not promote decision item counts, status changes, or action labels into MTR-* rows without a dedicated PAGE contract, metric dictionary rows, lineage, samples, and tests.",
            "Do not treat read/write status updates as approval of PAGE-BALANCE-001 metrics, balance-analysis outputs, or the /decision-items page itself.",
            "Keep permissions, read-only, permission-unknown, stale/fallback/no-data/error, report_date, position_scope, currency_basis, and result_meta states visible.",
            "Do not backfill missing decision rows or status overlays with static demo values in real mode.",
        ],
    }
    balance_movement_analysis_bundle = {
        "page_slug": "balance-movement-analysis",
        "page_id": "PAGE-BAL-MOVE-001",
        "page_name": "Balance Movement Analysis",
        "aliases": [
            "balance-movement-analysis",
            "balance_movement_analysis",
            "/balance-movement-analysis",
            "PAGE-BAL-MOVE-001",
            "/ui/balance-movement-analysis",
        ],
        "frontend_route": "/balance-movement-analysis",
        "primary_api": "/ui/balance-movement-analysis",
        "supporting_apis": [
            "/ui/balance-movement-analysis/dates",
            "/ui/balance-movement-analysis/refresh",
        ],
        "contract_docs": [
            "docs/page_contracts.md",
            "docs/metric_dictionary.md",
            "docs/live_route_maturity.md",
            "docs/plans/2026-05-14-balance-movement-analysis-diagnostics-mvp.md",
        ],
        "truth_chain": [
            "docs/page_contracts.md PAGE-BAL-MOVE-001",
            "docs/page_contracts.md MTR-BMV-001 through MTR-BMV-004",
            "backend/app/schema_registry/duckdb/18_accounting_asset_movement.sql fact_accounting_asset_movement_monthly",
            "backend/app/tasks/accounting_asset_movement.py rv_accounting_asset_movement_v2",
            "backend/app/services/accounting_asset_movement_service.py accounting_asset_movement_envelope",
            "AccountingAssetMovementPayload",
            "AccountingAssetMovementSummaryPayload",
            "/ui/balance-movement-analysis",
            "frontend/src/features/balance-movement-analysis/pages/BalanceMovementAnalysisPage.tsx",
        ],
        "backend_touchpoints": [
            "backend/app/api/routes/accounting_asset_movement.py",
            "backend/app/services/accounting_asset_movement_service.py",
            "backend/app/repositories/accounting_asset_movement_repo.py",
            "backend/app/tasks/accounting_asset_movement.py",
            "backend/app/core_finance/accounting_asset_movement.py",
            "backend/app/schemas/accounting_asset_movement.py",
            "backend/app/schema_registry/duckdb/18_accounting_asset_movement.sql",
        ],
        "frontend_touchpoints": [
            "frontend/src/api/balanceMovementClient.ts",
            "frontend/src/api/contracts.ts",
            "frontend/src/features/balance-movement-analysis/pages/BalanceMovementAnalysisPage.tsx",
            "frontend/src/features/balance-movement-analysis/pages/BalanceMovementAnalysisPage.css",
            "frontend/src/mocks/navigation.ts",
        ],
        "test_touchpoints": [
            "tests/test_accounting_asset_movement_api.py",
            "tests/test_accounting_asset_movement_service.py",
            "tests/test_accounting_asset_movement_core.py",
            "tests/test_accounting_asset_movement_materialize.py",
            "tests/test_result_meta_on_all_ui_endpoints.py",
            "tests/test_live_route_page_contract_completeness.py",
            "tests/test_write_route_auth_contract.py",
            "frontend/src/test/BalanceMovementAnalysisPage.test.tsx",
            "frontend/src/test/RouteRegistry.test.tsx",
        ],
        "golden_samples": [],
        "verification_focus": [
            "No dedicated golden sample is currently registered for PAGE-BAL-MOVE-001; verify through page contract, route/service/core/materialize tests, result_meta checks, and frontend page tests.",
            "Trace /ui/balance-movement-analysis summary fields through balanceMovementClient, BalanceMovementAnalysisPage, summary cards, reconciliation strip, and movement diagnostics before changing display logic.",
            "Check selected report dates, currency_basis, previous/current/change/reconciliation totals, refresh authorization, stale/fallback metadata, and no-data/error states.",
            "Keep balance movement explanation separate from PAGE-BALANCE-001 formal balance truth; this page explains movement for selected report dates and currency basis.",
        ],
        "guardrails": [
            "Do not use balance movement explanation to replace PAGE-BALANCE-001 formal balance truth.",
            "Do not hide selected report dates, currency_basis, result_meta, source/rule/cache versions, refresh status, stale/fallback states, or no-data/error states.",
            "Do not backfill missing movement rows with demo rows, mock rows, or previous page values in real mode.",
            "Do not recompute governed previous/current/change/reconciliation summary totals in the frontend.",
            "Keep unsupported valuation, FX translation, low-coverage, residual, and diagnostic caveats visible when present.",
        ],
    }
    pnl_bundle = {
        "page_slug": "pnl",
        "page_id": "PAGE-PNL-001",
        "page_name": "Formal PnL",
        "aliases": [
            "pnl",
            "/pnl",
            "formal-pnl",
            "formal_pnl",
            "PAGE-PNL-001",
            "/api/pnl/overview",
        ],
        "frontend_route": "/pnl",
        "primary_api": "/api/pnl/overview",
        "supporting_apis": [
            "/api/pnl/dates",
            "/api/pnl/data",
            "/api/data/refresh_pnl",
            "/api/data/import_status/pnl",
        ],
        "contract_docs": [
            "docs/page_contracts.md",
            "docs/metric_dictionary.md",
            "docs/golden_sample_catalog.md",
            "docs/calc_rules.md",
            "docs/data_contracts.md",
        ],
        "truth_chain": [
            "docs/page_contracts.md PAGE-PNL-001",
            "docs/metric_dictionary.md MTR-PNL-001 through MTR-PNL-005 and MTR-PNL-101 through MTR-PNL-104",
            "backend/app/schema_registry/duckdb/07_pnl_materialize.sql fact_formal_pnl_fi + fact_nonstd_pnl_bridge",
            "backend/app/core_finance/pnl.py build_formal_pnl_fi_fact_rows",
            "backend/app/tasks/pnl_materialize.py materialize_formal_pnl_facts",
            "backend/app/services/pnl_service.py pnl_overview_envelope",
            "PnlOverviewPayload",
            "PnlDataPayload",
            "/api/pnl/overview",
            "frontend/src/features/pnl/PnlPage.tsx",
        ],
        "backend_touchpoints": [
            "backend/app/api/routes/pnl.py",
            "backend/app/services/pnl_service.py",
            "backend/app/core_finance/pnl.py",
            "backend/app/schemas/pnl.py",
            "backend/app/repositories/pnl_repo.py",
            "backend/app/tasks/pnl_materialize.py",
            "backend/app/schema_registry/duckdb/07_pnl_materialize.sql",
        ],
        "frontend_touchpoints": [
            "frontend/src/api/pnlCoreClient.ts",
            "frontend/src/api/contracts.ts",
            "frontend/src/features/pnl/PnlPage.tsx",
        ],
        "test_touchpoints": [
            "tests/test_pnl_api_contract.py",
            "tests/test_pnl_formal_semantics_contract.py",
            "tests/test_pnl_core_finance_contract.py",
            "tests/test_pnl_materialize_flow.py",
            "frontend/src/test/PnlPage.test.tsx",
            "frontend/src/test/PnlRoutesSmoke.test.tsx",
            "tests/test_golden_samples_capture_ready.py",
        ],
        "golden_samples": [
            "tests/golden_samples/GS-PNL-OVERVIEW-A",
            "tests/golden_samples/GS-PNL-DATA-A",
        ],
        "verification_focus": [
            "Trace /api/pnl/overview result_meta through getFormalPnlOverview, PnlPage state, overview cards, formal row table, and the meta panel before changing display logic.",
            "Check report_date, basis, source_version, rule_version, cache_version, trace_id, fallback/stale visibility, and report-date-specific build lineage preference.",
            "Check units and null-vs-zero semantics for 514 interest income, 516 fair value change, 517 capital gain, manual adjustment, total_pnl, and row counts.",
            "Verify GS-PNL-OVERVIEW-A can be reconciled back to GS-PNL-DATA-A row aggregation.",
        ],
        "guardrails": [
            "Do not replace formal PnL truth with PnL Bridge reconciliation, executive analytical overlay, or product-category operating PnL.",
            "Do not treat standardized total as formal PnL total; fact_formal_pnl_fi.total_pnl is the formal recognized total.",
            "Do not redo 516 sign logic, formal recognition, invest_type_std, accounting_basis, or row-count calculations in the frontend.",
            "Keep non-formal basis selections visibly distinct from the formal main chain.",
            "Keep missing data, 404 no-data states, fallback lineage, and result_meta visible instead of filling with mock or stale figures.",
        ],
    }
    ledger_pnl_bundle = {
        "page_slug": "ledger-pnl",
        "page_id": "PAGE-LEDGER-PNL-001",
        "page_name": "Ledger PnL",
        "aliases": [
            "ledger-pnl",
            "ledger_pnl",
            "/ledger-pnl",
            "PAGE-LEDGER-PNL-001",
            "/api/ledger-pnl/summary",
            "/api/ledger-pnl/formal-financial-indicators",
        ],
        "frontend_route": "/ledger-pnl",
        "primary_api": "/api/ledger-pnl/summary",
        "supporting_apis": [
            "/api/ledger-pnl/dates",
            "/api/ledger-pnl/data",
            "/api/ledger-pnl/formal-financial-indicators",
        ],
        "contract_docs": [
            "docs/page_contracts.md",
            "docs/metric_dictionary.md",
            "docs/audits/2026-05-16-ledger-pnl-formal-financial-indicator-source-gap.md",
        ],
        "truth_chain": [
            "docs/page_contracts.md PAGE-LEDGER-PNL-001",
            "docs/metric_dictionary.md MTR-LPN-001 through MTR-LPN-003 as candidate metrics with pending_confirmation=true",
            "backend/app/services/ledger_pnl_service.py ledger_pnl.summary / ledger_pnl.data / ledger_pnl.dates",
            "backend/app/services/ledger_pnl_service.py ledger_pnl.formal_financial_indicator_source_contract",
            "backend/app/core_finance/formal_financial_indicators.py GS-LEDGER-PNL-FIN-IND-202603-B contract fixture builder",
            "tests/fixtures/formal_financial_indicators/ledger_pnl_202603_financial_indicator_golden.json GS-LEDGER-PNL-FIN-IND-202603-B",
            "LedgerPnlSummaryPayload",
            "LedgerPnlDataPayload",
            "LedgerPnlFormalFinancialIndicatorContractPayload",
            "/api/ledger-pnl/summary",
            "frontend/src/features/ledger-pnl/pages/LedgerPnlPage.tsx",
        ],
        "backend_touchpoints": [
            "backend/app/api/routes/ledger_pnl.py",
            "backend/app/services/ledger_pnl_service.py",
            "backend/app/core_finance/formal_financial_indicators.py",
            "backend/app/core_finance/config/classification_rules.py",
            "backend/app/services/product_category_source_service.py",
        ],
        "frontend_touchpoints": [
            "frontend/src/api/pnlCoreClient.ts",
            "frontend/src/api/contracts.ts",
            "frontend/src/features/ledger-pnl/pages/LedgerPnlPage.tsx",
            "frontend/src/features/ledger-pnl/pages/LedgerPnlPage.css",
            "frontend/src/mocks/ledgerPnlMocks.ts",
        ],
        "test_touchpoints": [
            "tests/test_ledger_pnl_service.py",
            "tests/test_ledger_pnl_formal_financial_indicator_golden_sample.py",
            "tests/test_golden_samples_capture_ready.py",
            "tests/test_governance_doc_contract.py",
            "tests/test_live_route_page_contract_completeness.py",
            "frontend/src/test/LedgerPnlPage.test.tsx",
            "frontend/src/test/LedgerPnlRoutesSmoke.test.tsx",
            "tests/golden_samples/GS-LEDGER-PNL-SUMMARY-A/assertions.md",
            "tests/fixtures/formal_financial_indicators/ledger_pnl_202603_financial_indicator_golden.json",
        ],
        "golden_samples": ["tests/golden_samples/GS-LEDGER-PNL-SUMMARY-A"],
        "verification_focus": [
            "GS-LEDGER-PNL-SUMMARY-A is a dedicated capture-ready page-level summary DTO sample for PAGE-LEDGER-PNL-001; it is captured-awaiting-approval and does not approve formal use.",
            "Trace /api/ledger-pnl/summary, /api/ledger-pnl/data, and /api/ledger-pnl/formal-financial-indicators through pnlCoreClient, LedgerPnlPage, summary cards, detail tables, source-contract panel, and result_meta display before changing display logic.",
            "Check report_date, report_month, currency filter, yuan-to-yi display conversion, signed amount display, source_version, rule_version, cache_version, trace_id, as_of_date, and date_basis.",
            "Keep GS-LEDGER-PNL-FIN-IND-202603-B as a formal financial indicator source-contract fixture only; it freezes source status and Excel sample values but does not approve system values for formal use.",
        ],
        "guardrails": [
            "Treat MTR-LPN-001 through MTR-LPN-003 as candidate display metrics with pending_confirmation=true.",
            "Do not use ledger summary cards to replace formal PnL, product-category PnL, PnL bridge, or formal financial indicator truth.",
            "Do not render formal_pending financial indicator values as zero; keep value null and show missing-source status until a governed production source is approved.",
            "Do not promote candidate_qdb_aligned values or reconciliation probes into formal financial indicator truth without updating contracts, samples, and tests.",
            "Do not hide result_meta, report_month/report_date binding, stale/fallback/vendor degradation, no-data states, or missing-source states.",
            "Do not recompute ledger summary totals in the frontend; consume /api/ledger-pnl/summary and keep currency filtering bound to the backend read chain.",
        ],
    }
    pnl_by_business_bundle = {
        "page_slug": "pnl-by-business",
        "page_id": "PAGE-PNL-BY-BUSINESS-001",
        "page_name": "Business Type PnL",
        "aliases": [
            "pnl-by-business",
            "pnl_by_business",
            "/pnl-by-business",
            "PAGE-PNL-BY-BUSINESS-001",
            "/api/pnl/by-business-ytd",
            "/api/pnl/by-business-analysis",
        ],
        "frontend_route": "/pnl-by-business",
        "primary_api": "/api/pnl/by-business-ytd",
        "supporting_apis": [
            "/api/pnl/by-business-monthly",
            "/api/pnl/by-business",
            "/api/pnl/by-business-analysis",
            "/api/pnl/by-business/manual-adjustments",
            "/api/adb/comparison",
        ],
        "contract_docs": [
            "docs/page_contracts.md",
            "docs/pnl/pnl-by-business-formal-untraced-diagnostic-2026-05-31.md",
            "docs/pnl/pnl-by-business-formal-untraced-detail-packet-2026-05-31.md",
        ],
        "truth_chain": [
            "docs/page_contracts.md PAGE-PNL-BY-BUSINESS-001",
            "YTD/monthly ZQTZ management-disclosure business classification is the primary analysis view.",
            "Formal primary is formal reconciliation evidence only and must not be mixed into YTD/monthly business conclusions.",
            "This page has no newly approved MTR metric binding in this pass.",
            "backend/app/services/pnl_service.py materialize_pnl_by_business_read_model",
            "fact_formal_pnl_fi + fact_nonstd_pnl_bridge + fact_formal_zqtz_balance_daily",
            "fact_pnl_by_business_precompute",
            "pnl_by_business_adjustments as audit/reconciliation control evidence",
            "/api/pnl/by-business-ytd",
            "frontend/src/features/pnl/PnlByBusinessPage.tsx",
        ],
        "backend_touchpoints": [
            "backend/app/api/routes/pnl.py",
            "backend/app/services/pnl_service.py",
            "backend/app/repositories/pnl_repo.py",
            "backend/app/schemas/pnl.py",
        ],
        "frontend_touchpoints": [
            "frontend/src/api/pnlClient.ts",
            "frontend/src/api/contracts.ts",
            "frontend/src/features/pnl/PnlByBusinessPage.tsx",
            "frontend/src/features/pnl/pnlByBusinessPageModel.ts",
        ],
        "test_touchpoints": [
            "tests/test_pnl_api_contract.py",
            "tests/test_live_route_page_contract_completeness.py",
            "frontend/src/features/pnl/pnlByBusinessPageModel.test.ts",
            "frontend/src/test/PnlRoutesSmoke.test.tsx",
        ],
        "golden_samples": [],
        "verification_focus": [
            "No dedicated golden sample is currently registered for PAGE-PNL-BY-BUSINESS-001; verify through page contract, PnL API contract tests, frontend model tests, and lineage evidence.",
            "Trace the active monthly/YTD/formal endpoint result_meta through pnlClient, pnlByBusinessPageModel, PnlByBusinessPage, status strip, main table, and evidence panel before changing display logic.",
            "Check YTD year/as_of_date, monthly report bucket, formal report_date, fallback/stale/warning visibility, and null-vs-zero semantics.",
            "Check units: amount fields are displayed as ten-thousand yuan unless explicitly labelled hundred-million yuan; ADB/current balance are hundred-million yuan; yields are percent.",
        ],
        "guardrails": [
            "Manual adjustment audit/actions are audit and reconciliation controls; they must not create a new official metric definition.",
            "Product-category truth remains governed by PAGE-PROD-CAT-PNL-001 and must not be replaced by Business Type PnL rows.",
            "Ledger-account PnL truth remains governed by PAGE-LEDGER-PNL-001 and must not be inferred from this page.",
            "Formal PnL overview truth remains PAGE-PNL-001, and PnL Bridge truth remains PAGE-BRIDGE-001.",
            "Do not recalculate official PnL, balance, FTP cost, or formal yield formulas in the frontend.",
            "Do not hide untraced formal rows, zero-balance evidence, quality warnings, stale/fallback state, or missing ADB/FTP evidence.",
        ],
    }
    executive_pnl_attribution_bundle = {
        "page_slug": "executive-pnl-attribution",
        "page_id": "PAGE-EXEC-PNL-ATTR-001",
        "page_name": "Executive PnL Attribution",
        "aliases": [
            "executive-pnl-attribution",
            "executive-pnl-attr",
            "executive_pnl_attribution",
            "PAGE-EXEC-PNL-ATTR-001",
            "/ui/pnl/attribution",
        ],
        "frontend_route": "/dashboard",
        "primary_api": "/ui/pnl/attribution",
        "supporting_apis": [
            "/ui/home/snapshot",
            "/ui/home/overview",
        ],
        "contract_docs": [
            "docs/page_contracts.md",
            "docs/metric_dictionary.md",
            "docs/golden_sample_catalog.md",
            "docs/dashboard_cockpit_contract.md",
        ],
        "truth_chain": [
            "docs/page_contracts.md PAGE-EXEC-PNL-ATTR-001",
            "docs/metric_dictionary.md MTR-EXEC-101 through MTR-EXEC-106",
            "backend/app/services/executive_service.py executive_pnl_attribution",
            "executive.pnl-attribution result_meta",
            "PnlAttributionPayload",
            "/ui/pnl/attribution",
            "frontend/src/features/executive-dashboard/components/PnlAttributionSection.tsx",
        ],
        "backend_touchpoints": [
            "backend/app/api/routes/executive.py",
            "backend/app/services/executive_service.py",
            "backend/app/schemas/executive_dashboard.py",
        ],
        "frontend_touchpoints": [
            "frontend/src/api/pnlAttributionClient.ts",
            "frontend/src/api/contracts.ts",
            "frontend/src/features/executive-dashboard/components/PnlAttributionSection.tsx",
            "frontend/src/features/executive-dashboard/selectors/executiveDashboardSelectors.ts",
        ],
        "test_touchpoints": [
            "tests/test_executive_dashboard_endpoints.py",
            "tests/test_executive_service_contract.py",
            "tests/test_executive_release_contract.py",
            "tests/test_golden_samples_capture_ready.py",
            "frontend/src/test/PnlAttributionSection.test.tsx",
            "frontend/src/features/executive-dashboard/components/PnlAttributionSection.states.test.tsx",
            "tests/golden_samples/GS-EXEC-PNL-ATTR-A/assertions.md",
        ],
        "golden_samples": ["tests/golden_samples/GS-EXEC-PNL-ATTR-A"],
        "verification_focus": [
            "Trace /ui/pnl/attribution result_meta through executive_pnl_attribution, getPnlAttribution, PnlAttributionSection, and dashboard snapshot consumers before changing display logic.",
            "Check report_date, analytical basis, segment identity, signed amount display, fallback/stale states, and result_meta.result_kind.",
            "Verify GS-EXEC-PNL-ATTR-A remains an overlay sample and does not redefine formal PnL or bridge totals.",
        ],
        "guardrails": [
            "Treat this as an analytical overlay for management explanation, not formal PnL truth.",
            "Do not use executive analytical overlay values to replace formal bridge evidence or formal PnL totals.",
            "Do not merge this surface with the /pnl-attribution workbench; they have different routes, tests, and metric dictionaries.",
            "Keep analytical overlay wording and result_meta visible even when upstream data is missing.",
            "Do not recompute carry, roll-down, credit, trading, or other segments in the frontend.",
        ],
    }
    pnl_attribution_workbench_bundle = {
        "page_slug": "pnl-attribution",
        "page_id": "PAGE-PNL-ATTR-WB-001",
        "page_name": "PnL Attribution Workbench",
        "aliases": [
            "pnl-attribution",
            "pnl_attribution",
            "/pnl-attribution",
            "PAGE-PNL-ATTR-WB-001",
            "/api/pnl-attribution/volume-rate",
        ],
        "frontend_route": "/pnl-attribution",
        "primary_api": "/api/pnl-attribution/volume-rate",
        "supporting_apis": [
            "/api/pnl-attribution/tpl-market",
            "/api/pnl-attribution/composition",
            "/api/pnl-attribution/summary",
            "/api/pnl-attribution/advanced/carry-rolldown",
            "/api/pnl-attribution/advanced/spread",
            "/api/pnl-attribution/advanced/krd",
            "/api/pnl-attribution/advanced/summary",
            "/api/pnl-attribution/advanced/campisi",
            "/api/pnl-attribution/campisi/four-effects",
            "/api/pnl-attribution/campisi/enhanced",
            "/api/pnl-attribution/campisi/maturity-buckets",
            "/api/pnl-attribution/campisi/decision-grade",
        ],
        "contract_docs": [
            "docs/page_contracts.md",
            "docs/metric_dictionary.md",
            "docs/live_route_maturity.md",
            "docs/plans/2026-05-15-campisi-attribution-audit.md",
        ],
        "truth_chain": [
            "docs/page_contracts.md PAGE-PNL-ATTR-WB-001",
            "docs/metric_dictionary.md MTR-PAT-001 through MTR-PAT-006, MTR-PAT-101 through MTR-PAT-103, MTR-PAT-201 through MTR-PAT-205, and MTR-PAT-301 through MTR-PAT-304",
            "backend/app/core_finance/pnl_attribution/workbench.py build_volume_rate_attribution / build_tpl_market_correlation / build_pnl_composition",
            "backend/app/services/pnl_attribution_service.py volume_rate_attribution_envelope and advanced attribution envelopes",
            "backend/app/api/routes/pnl_attribution.py /api/pnl-attribution/*",
            "backend/app/api/routes/campisi_attribution.py Campisi endpoints",
            "VolumeRateAttributionPayload",
            "TPLMarketCorrelationPayload",
            "PnlCompositionPayload",
            "AdvancedAttributionSummary",
            "frontend/src/api/pnlAttributionClient.ts",
            "frontend/src/features/pnl-attribution/pages/PnlAttributionPage.tsx",
        ],
        "backend_touchpoints": [
            "backend/app/api/routes/pnl_attribution.py",
            "backend/app/api/routes/campisi_attribution.py",
            "backend/app/services/pnl_attribution_service.py",
            "backend/app/services/campisi_attribution_service.py",
            "backend/app/core_finance/pnl_attribution/workbench.py",
            "backend/app/core_finance/campisi.py",
            "backend/app/schemas/pnl_attribution.py",
        ],
        "frontend_touchpoints": [
            "frontend/src/api/pnlAttributionClient.ts",
            "frontend/src/api/contracts.ts",
            "frontend/src/features/pnl-attribution/pages/PnlAttributionPage.tsx",
            "frontend/src/features/pnl-attribution/components/PnlAttributionView.tsx",
            "frontend/src/features/pnl-attribution/components/AdvancedAttributionChart.tsx",
            "frontend/src/features/pnl-attribution/components/TPLMarketChart.tsx",
            "frontend/src/features/pnl-attribution/components/CampisiAttributionPanel.tsx",
        ],
        "test_touchpoints": [
            "tests/test_pnl_attribution_api_contract.py",
            "tests/test_pnl_attribution_workbench_contract.py",
            "tests/test_pnl_attribution_service_explicit_numeric.py",
            "tests/test_pnl_attribution_numeric_migration.py",
            "tests/test_advanced_attribution_contract.py",
            "tests/test_result_meta_source_surface.py",
            "backend/tests/services/test_pnl_attribution_campisi.py",
            "frontend/src/test/PnlAttributionPage.test.tsx",
            "frontend/src/features/pnl-attribution/components/PnlAttributionView.test.ts",
            "frontend/src/test/PnlCompositionChart.test.tsx",
            "frontend/src/test/TPLMarketChart.test.tsx",
            "frontend/src/test/AdvancedAttributionChart.test.tsx",
            "frontend/src/test/CampisiAttributionPanel.test.tsx",
            "tests/test_golden_samples_capture_ready.py",
            "tests/golden_samples/GS-PNL-ATTR-WB-A/assertions.md",
        ],
        "golden_samples": ["tests/golden_samples/GS-PNL-ATTR-WB-A"],
        "verification_focus": [
            "Verify GS-PNL-ATTR-WB-A remains scoped to the /api/pnl-attribution/volume-rate workbench DTO and does not replace formal PnL overview, executive analytical overlay, advanced attribution, or Campisi surfaces.",
            "Trace active-tab payloads through pnlAttributionClient, PnlAttributionView state, current_view_meta, charts, tables, and advanced/Campisi panels before changing display logic.",
            "Check amount, percent, bp, current/previous period, generated_at, quality_flag, fallback_mode, and null-vs-zero semantics for each workbench tab.",
            "Keep product-category, formal attribution, advanced attribution, and Campisi panels visibly scoped to their own basis and provenance.",
        ],
        "guardrails": [
            "Do not use this workbench to replace the formal PnL overview or the executive analytical overlay.",
            "Do not merge /pnl-attribution with /ui/pnl/attribution; they have different consumers, basis labels, and tests.",
            "Do not recompute volume-rate, TPL-market, composition, advanced, KRD, or Campisi outputs in the frontend.",
            "Do not hide generated_at, quality_flag, fallback_mode, no-data, stale, or provenance boundaries on the active tab.",
            "Treat KRD yield_change unit wording as a known follow-up gap unless the field contract is updated with explicit bp naming.",
        ],
    }
    operations_analysis_bundle = {
        "page_slug": "operations-analysis",
        "page_id": "PAGE-OPS-001",
        "page_name": "Operations Analysis",
        "aliases": [
            "operations-analysis",
            "/operations-analysis",
            "operations_analysis",
            "PAGE-OPS-001",
            "/ui/pnl/product-category",
        ],
        "frontend_route": "/operations-analysis",
        "primary_api": "/ui/pnl/product-category",
        "supporting_apis": [
            "/ui/pnl/product-category/dates",
            "/ui/balance-analysis/dates",
            "/ui/balance-analysis/overview",
            "/ui/preview/source-foundation",
            "/ui/preview/macro-foundation",
            "/ui/macro/choice-series/latest",
            "/ui/market-data/fx/formal-status",
            "/ui/news/choice-events/latest",
        ],
        "contract_docs": [
            "docs/page_contracts.md",
            "docs/metric_dictionary.md",
            "docs/golden_sample_catalog.md",
            "docs/golden_sample_plan.md",
            "docs/live_route_maturity.md",
            "docs/GPT55_FRONTEND_DESIGN_CONTEXT.md",
        ],
        "truth_chain": [
            "docs/page_contracts.md PAGE-OPS-001",
            "docs/metric_dictionary.md PAGE-OPS-001 reuses MTR-PCP-001 through MTR-PCP-003 from product-category headline truth",
            "docs/metric_dictionary.md balance overview is supplemental topic-entry evidence with MTR-BAL-001, MTR-BAL-002, MTR-BAL-003, MTR-BAL-101, and MTR-BAL-102",
            "docs/metric_dictionary.md GAP-OPS-MACRO-FX keeps source preview, macro, FX, news, and operational strips outside formal metric promotion",
            "backend/app/services/product_category_pnl_service.py ProductCategoryPnlPayload headline totals",
            "backend/app/services/balance_analysis_service.py BalanceAnalysisOverviewPayload supplemental topic-entry evidence",
            "backend/app/services/macro_vendor_service.py preview and Choice macro analytical evidence",
            "backend/app/services/choice_news_service.py Choice news analytical evidence",
            "frontend/src/features/workbench/pages/OperationsAnalysisPage.tsx",
        ],
        "backend_touchpoints": [
            "backend/app/api/routes/product_category_pnl.py",
            "backend/app/services/product_category_pnl_service.py",
            "backend/app/api/routes/balance_analysis.py",
            "backend/app/services/balance_analysis_service.py",
            "backend/app/api/routes/source_preview.py",
            "backend/app/api/routes/macro_vendor.py",
            "backend/app/api/routes/choice_news.py",
            "backend/app/schemas/product_category_pnl.py",
            "backend/app/schemas/balance_analysis.py",
        ],
        "frontend_touchpoints": [
            "frontend/src/api/productCategoryClient.ts",
            "frontend/src/api/balanceAnalysisClient.ts",
            "frontend/src/api/marketDataClient.ts",
            "frontend/src/api/contracts.ts",
            "frontend/src/features/workbench/pages/OperationsAnalysisPage.tsx",
            "frontend/src/features/workbench/pages/OperationsAnalysisPage.css",
            "frontend/src/mocks/navigation.ts",
        ],
        "test_touchpoints": [
            "frontend/src/test/OperationsAnalysisPage.test.tsx",
            "frontend/src/test/OperationsAnalysisPage.governed.test.tsx",
            "frontend/src/test/navigation.test.ts",
            "frontend/src/test/RouteRegistry.test.tsx",
            "frontend/src/test/WorkbenchShell.test.tsx",
            "tests/test_governance_doc_contract.py",
            "tests/test_live_route_page_contract_completeness.py",
            "tests/test_product_category_pnl_flow.py",
            "tests/test_balance_analysis_api.py",
            "tests/test_golden_samples_capture_ready.py",
        ],
        "golden_samples": [
            "tests/golden_samples/GS-PROD-CAT-PNL-A",
            "tests/golden_samples/GS-BAL-OVERVIEW-A",
        ],
        "verification_focus": [
            "Trace /ui/pnl/product-category headline totals through OperationsAnalysisPage primary KPI cards before changing PAGE-OPS-001 display logic.",
            "Verify balance overview remains supplemental topic-entry evidence and routes users to /balance-analysis for formal workbook/detail truth.",
            "Check source preview, macro, FX, and news sections keep analytical/preview/vendor/result_meta context and do not promote new MTR-OPS-* metrics.",
            "Keep temporary-exception labels and static/mixed-source section boundaries visible until PAGE-OPS-001 exits the live-route maturity exception.",
        ],
        "guardrails": [
            "PAGE-OPS-001 is a temporary-exception mixed-source page; do not claim full page-level formal closure from its aggregate first screen.",
            "Do not create or promote MTR-OPS-* metrics; the current formal operating KPI cards reuse MTR-PCP-001, MTR-PCP-002, and MTR-PCP-003.",
            "Balance overview is supplemental topic-entry evidence, not a replacement for PAGE-BALANCE-001 workbook/detail truth.",
            "Do not treat source preview, macro, FX, Choice news, static watch items, or calendar examples as formal business metric truth.",
            "Do not hide GAP-OPS-MACRO-FX, mock-mode, static-example, result_meta, fallback, stale, or vendor-status boundaries.",
        ],
    }
    liability_analytics_bundle = {
        "page_slug": "liability-analytics",
        "page_id": "PAGE-LIAB-ANALYTICS-001",
        "page_name": "Liability Analytics",
        "aliases": [
            "liability-analytics",
            "/liability-analytics",
            "liability_analytics",
            "PAGE-LIAB-ANALYTICS-001",
            "/api/risk/buckets",
        ],
        "frontend_route": "/liability-analytics",
        "primary_api": "/api/risk/buckets",
        "supporting_apis": [
            "/api/analysis/yield_metrics",
            "/api/analysis/yield-by-period",
            "/api/analysis/liabilities/counterparty",
            "/api/liabilities/monthly",
            "/ui/liability/business-context",
            "/api/analysis/liabilities/cockpit-warnings",
            "/api/analysis/liabilities/contribution-split",
            "/ui/balance-analysis/dates",
            "/ui/balance-analysis/overview",
            "/api/analysis/adb/monthly",
        ],
        "contract_docs": [
            "docs/page_contracts.md",
            "docs/metric_dictionary.md",
            "docs/live_route_maturity.md",
            "docs/DOCUMENT_AUTHORITY.md",
            "docs/V2_V3_PARITY_MATRIX.md",
        ],
        "truth_chain": [
            "docs/page_contracts.md PAGE-LIAB-ANALYTICS-001",
            "docs/metric_dictionary.md MTR-LIAB-001 through MTR-LIAB-007",
            "docs/live_route_maturity.md governed-mixed-source / compatibility boundary",
            "backend/app/core_finance/liability_analytics_compat.py compute_liability_risk_buckets / compute_liability_yield_metrics",
            "backend/app/services/liability_analytics_service.py liability_analytics.risk_buckets",
            "backend/app/api/routes/liability_analytics.py /api/risk/buckets and compatibility routes",
            "frontend/src/api/liabilityAdbClient.ts liability API client",
            "frontend/src/features/liability-analytics/pages/LiabilityAnalyticsPage.tsx",
        ],
        "backend_touchpoints": [
            "backend/app/api/routes/liability_analytics.py",
            "backend/app/services/liability_analytics_service.py",
            "backend/app/core_finance/liability_analytics_compat.py",
            "backend/app/schemas/liability_analytics.py",
            "backend/app/repositories/liability_analytics_repo.py",
        ],
        "frontend_touchpoints": [
            "frontend/src/api/liabilityAdbClient.ts",
            "frontend/src/api/contracts.ts",
            "frontend/src/features/liability-analytics/pages/LiabilityAnalyticsPage.tsx",
            "frontend/src/features/liability-analytics/pages/liabilityAnalyticsPageModel.ts",
            "frontend/src/features/liability-analytics/adapters/liabilityAdapter.ts",
        ],
        "test_touchpoints": [
            "tests/test_liability_analytics_api.py",
            "tests/test_liability_analytics_envelope_contract.py",
            "tests/test_liability_analytics_compat_contract.py",
            "tests/test_liability_analytics_unit_semantics.py",
            "tests/test_liability_analytics_numeric_migration.py",
            "tests/test_result_meta_on_all_ui_endpoints.py",
            "tests/test_result_meta_source_surface_followup.py",
            "tests/test_live_route_page_contract_completeness.py",
            "frontend/src/test/LiabilityAnalyticsPage.test.tsx",
            "frontend/src/features/liability-analytics/adapters/liabilityAdapter.test.ts",
            "frontend/src/features/liability-analytics/pages/liabilityAnalyticsPageModel.test.ts",
        ],
        "golden_samples": [],
        "verification_focus": [
            "No dedicated golden sample is currently registered for PAGE-LIAB-ANALYTICS-001; verify via page contract, metric dictionary, route/service tests, result_meta checks, and frontend page tests.",
            "Trace risk, yield, counterparty, monthly, business-context, cockpit-warning, and contribution payloads through liabilityAdbClient, adapters, page read model, and LiabilityAnalyticsPage before changing display logic.",
            "Check amount display conversion, percent/bp semantics, report_date binding, monthly average-balance semantics, fallback_mode, vendor_status, quality_flag, and missing-result-meta states.",
            "Keep actual compatibility API paths distinct from the page-contract /ui liability target paths until the routing contract is reconciled.",
        ],
        "guardrails": [
            "Treat the page as governed-mixed-source and compatibility analytical, not formal balance truth or formal PnL truth.",
            "Do not hide mixed-source, compatibility, synthetic, fallback, stale, or pending-definition boundaries from users.",
            "Do not promote reserved or compatibility endpoints to formal truth without updating page contracts, metric dictionary, lineage, and tests.",
            "Do not recompute liability cost, NIM, maturity pressure, counterparty concentration, monthly averages, or bucket definitions in the frontend.",
            "Use result_meta and no-data/error states to distinguish backend-owned values from compatibility or derived sections.",
        ],
    }
    pnl_bridge_bundle = {
        "page_slug": "pnl-bridge",
        "page_id": "PAGE-BRIDGE-001",
        "page_name": "PnL Bridge",
        "aliases": [
            "pnl-bridge",
            "/pnl-bridge",
            "pnl_bridge",
            "PAGE-BRIDGE-001",
            "/api/pnl/bridge",
        ],
        "frontend_route": "/pnl-bridge",
        "primary_api": "/api/pnl/bridge",
        "supporting_apis": [
            "/api/pnl/dates",
            "/api/pnl/refresh",
            "/api/pnl/refresh-status",
        ],
        "contract_docs": [
            "docs/page_contracts.md",
            "docs/metric_dictionary.md",
            "docs/golden_sample_catalog.md",
            "docs/calc_rules.md",
        ],
        "truth_chain": [
            "docs/page_contracts.md PAGE-BRIDGE-001",
            "docs/metric_dictionary.md MTR-BRG-001 through MTR-BRG-014 and MTR-BRG-101 through MTR-BRG-105",
            "backend/app/schema_registry/duckdb/07_pnl_materialize.sql fact_formal_pnl_fi + fact_nonstd_pnl_bridge",
            "backend/app/core_finance/pnl_bridge.py build_pnl_bridge_rows",
            "backend/app/services/pnl_bridge_service.py pnl_bridge_envelope",
            "PnlBridgePayload",
            "/api/pnl/bridge",
            "frontend/src/features/pnl/PnlBridgePage.tsx",
        ],
        "backend_touchpoints": [
            "backend/app/api/routes/pnl.py",
            "backend/app/services/pnl_bridge_service.py",
            "backend/app/core_finance/pnl_bridge.py",
            "backend/app/schemas/pnl_bridge.py",
            "backend/app/repositories/pnl_repo.py",
            "backend/app/repositories/balance_analysis_repo.py",
            "backend/app/repositories/yield_curve_repo.py",
            "backend/app/tasks/pnl_materialize.py",
            "backend/app/schema_registry/duckdb/07_pnl_materialize.sql",
        ],
        "frontend_touchpoints": [
            "frontend/src/api/pnlCoreClient.ts",
            "frontend/src/api/contracts.ts",
            "frontend/src/features/pnl/PnlBridgePage.tsx",
            "frontend/src/features/pnl/adapters/pnlBridgeAdapter.ts",
        ],
        "test_touchpoints": [
            "tests/test_pnl_api_contract.py",
            "tests/test_pnl_bridge_core.py",
            "tests/test_pnl_bridge_curve_effects.py",
            "tests/test_pnl_bridge_fx_translation.py",
            "tests/test_pnl_bridge_with_curve.py",
            "tests/test_pnl_bridge_numeric_migration.py",
            "tests/test_pnl_bridge_service_boundaries.py",
            "frontend/src/test/PnlBridgePage.test.tsx",
            "tests/test_golden_samples_capture_ready.py",
        ],
        "golden_samples": [
            "tests/golden_samples/GS-BRIDGE-A",
            "tests/golden_samples/GS-BRIDGE-WARN-B",
        ],
        "verification_focus": [
            "Trace /api/pnl/bridge result_meta through getPnlBridge, adaptPnlBridge, PnlBridgePage, and the formal meta panel before changing display logic.",
            "Check report_date, requested/resolved date behavior, source_version, rule_version, cache_version, trace_id, and curve/balance fallback visibility.",
            "Check units and null-vs-zero semantics for beginning/ending dirty market value, carry, roll-down, curve effects, FX, actual, explained, residual, and residual ratio.",
            "Keep bridge warnings and warning-profile golden samples visible; warning quality is valid governed output, not an error to hide.",
        ],
        "guardrails": [
            "Do not hide bridge warnings, balance lineage fallback warnings, curve fallback, vendor stale, or quality_flag=warning states.",
            "Do not use PnL Bridge to replace the formal PnL detail page or ledger-level PnL evidence.",
            "Do not synthesize future-only attribution sections as current governed bridge output.",
            "Do not recompute governed totals, residuals, or quality flags in the frontend; consume backend-owned PnlBridgePayload values.",
            "Preserve balance-analysis current/prior input lineage and yield-curve fallback/vendor-stale visibility when auditing this page.",
        ],
    }
    risk_tensor_bundle = {
        "page_slug": "risk-tensor",
        "page_id": "PAGE-RISK-001",
        "page_name": "Risk Tensor",
        "aliases": [
            "risk-tensor",
            "/risk-tensor",
            "risk_tensor",
            "PAGE-RISK-001",
            "/api/risk/tensor",
        ],
        "frontend_route": "/risk-tensor",
        "primary_api": "/api/risk/tensor",
        "supporting_apis": [
            "/api/risk/tensor/dates",
        ],
        "contract_docs": [
            "docs/page_contracts.md",
            "docs/metric_dictionary.md",
            "docs/golden_sample_catalog.md",
            "docs/calc_rules.md",
        ],
        "truth_chain": [
            "docs/page_contracts.md PAGE-RISK-001",
            "docs/metric_dictionary.md MTR-RSK-001 / MTR-RSK-001R / MTR-RSK-021-023",
            "backend/app/schema_registry/duckdb/04_risk_tensor.sql fact_formal_risk_tensor_daily",
            "backend/app/tasks/risk_tensor_materialize.py materialize_risk_tensor_facts",
            "backend/app/services/risk_tensor_service.py risk_tensor_envelope",
            "RiskTensorPayload",
            "/api/risk/tensor",
            "frontend/src/features/risk-tensor/RiskTensorPage.tsx",
        ],
        "backend_touchpoints": [
            "backend/app/api/routes/risk_tensor.py",
            "backend/app/services/risk_tensor_service.py",
            "backend/app/repositories/risk_tensor_repo.py",
            "backend/app/schemas/risk_tensor.py",
            "backend/app/core_finance/risk_tensor.py",
            "backend/app/core_finance/risk_tensor_regulatory_scope.py",
            "backend/app/tasks/risk_tensor_materialize.py",
            "backend/app/schema_registry/duckdb/04_risk_tensor.sql",
        ],
        "frontend_touchpoints": [
            "frontend/src/api/executiveClient.ts",
            "frontend/src/api/contracts.ts",
            "frontend/src/features/risk-tensor/RiskTensorPage.tsx",
            "frontend/src/features/risk-tensor/RiskTensorPage.css",
        ],
        "test_touchpoints": [
            "tests/test_risk_tensor_api.py",
            "tests/test_risk_tensor_service.py",
            "tests/test_risk_tensor_repo.py",
            "tests/test_risk_tensor_core.py",
            "tests/test_risk_tensor_materialize.py",
            "tests/test_risk_tensor_numeric_migration.py",
            "tests/test_risk_tensor_liquidity.py",
            "frontend/src/test/RiskTensorPage.test.tsx",
            "tests/test_golden_samples_capture_ready.py",
        ],
        "golden_samples": [
            "tests/golden_samples/GS-RISK-A",
            "tests/golden_samples/GS-RISK-WARN-B",
        ],
        "verification_focus": [
            "Trace /api/risk/tensor result_meta through getRiskTensor, RiskTensorPage, and the quality/detail surfaces before changing display logic.",
            "Check report_date, source_version, upstream_source_version, liability_source_version, rule_version, cache_version, and trace_id visibility.",
            "Check units and null-vs-zero semantics for DV01, regulatory_dv01, KRD, CS01, convexity, HHI, liquidity gaps, and duration-scope fields.",
            "Keep warning quality visible; latest data can be formal while still requiring user-visible warning context.",
        ],
        "guardrails": [
            "Do not recompute KRD, DV01, CS01, convexity, liquidity gaps, or issuer concentration in the frontend.",
            "Do not use /ui/risk/overview as formal PAGE-RISK-001 evidence; it is a separate overview surface.",
            "Do not backfill regulatory_dv01 from portfolio_dv01 or hide missing regulatory scope.",
            "Keep warning quality and warnings visible, including tenor remaps, unsupported tenor exclusions, and stale/fallback report-date blocks.",
            "Do not synthesize maturity dates for no-maturity rows; preserve duration denominator exclusions and disclose excluded market value/count.",
            "DV01 totals remain row-DV01 sourced even when duration denominator excludes rows.",
        ],
    }
    bond_dashboard_bundle = {
        "page_slug": "bond-dashboard",
        "page_id": "PAGE-BOND-001",
        "page_name": "Bond Dashboard",
        "aliases": [
            "bond-dashboard",
            "bond_dashboard",
            "/bond-dashboard",
            "PAGE-BOND-001",
            "/api/bond-dashboard/headline-kpis",
            "/api/bond-dashboard/risk-indicators",
        ],
        "frontend_route": "/bond-dashboard",
        "primary_api": "/api/bond-dashboard/headline-kpis",
        "supporting_apis": [
            "/api/bond-dashboard/dates",
            "/api/bond-dashboard/asset-structure",
            "/api/bond-dashboard/yield-distribution",
            "/api/bond-dashboard/portfolio-comparison",
            "/api/bond-dashboard/spread-analysis",
            "/api/bond-dashboard/maturity-structure",
            "/api/bond-dashboard/industry-distribution",
            "/api/bond-dashboard/risk-indicators",
            "/api/bond-dashboard/business-type-metrics",
        ],
        "contract_docs": [
            "docs/page_contracts.md",
            "docs/metric_dictionary.md",
            "docs/golden_sample_catalog.md",
            "docs/data_contracts.md",
        ],
        "truth_chain": [
            "docs/page_contracts.md PAGE-BOND-001",
            "docs/metric_dictionary.md MTR-BOND-001 through MTR-BOND-004 as candidate metrics with pending_confirmation=true",
            "docs/metric_dictionary.md GAP-BOND-DASH-HL and GAP-BOND-DASH-RISK",
            "docs/golden_sample_catalog.md GS-BOND-HEADLINE-A freezes page-level DTO truth only",
            "backend/app/services/bond_dashboard_service.py bond_dashboard.headline_kpis with source_surface=\"bond_analytics\"",
            "backend/app/services/bond_dashboard_service.py bond_dashboard.risk_indicators",
            "backend/app/schemas/bond_dashboard.py BondDashboardHeadlinePayload",
            "backend/app/schemas/bond_dashboard.py BondDashboardRiskIndicatorsPayload",
            "backend/app/repositories/bond_analytics_repo.py fact_formal_bond_analytics_daily read model",
            "/api/bond-dashboard/headline-kpis",
            "frontend/src/features/bond-dashboard/pages/BondDashboardPage.tsx",
        ],
        "backend_touchpoints": [
            "backend/app/api/routes/bond_dashboard.py",
            "backend/app/services/bond_dashboard_service.py",
            "backend/app/schemas/bond_dashboard.py",
            "backend/app/repositories/bond_analytics_repo.py",
            "backend/app/schema_registry/duckdb/05_bond_analytics.sql",
        ],
        "frontend_touchpoints": [
            "frontend/src/api/bondAnalyticsClient.ts",
            "frontend/src/api/contracts.ts",
            "frontend/src/features/bond-dashboard/pages/BondDashboardPage.tsx",
            "frontend/src/features/bond-dashboard/components/HeadlineKpis.tsx",
            "frontend/src/features/bond-dashboard/components/RiskIndicatorsPanel.tsx",
        ],
        "test_touchpoints": [
            "tests/test_bond_dashboard_api_contract.py",
            "tests/test_bond_dashboard_headlines_contract.py",
            "tests/test_bond_analytics_api.py",
            "tests/test_result_meta_source_surface_followup.py",
            "tests/test_golden_samples_capture_ready.py",
            "frontend/src/test/BondDashboardPage.test.tsx",
            "tests/golden_samples/GS-BOND-HEADLINE-A/assertions.md",
        ],
        "golden_samples": ["tests/golden_samples/GS-BOND-HEADLINE-A"],
        "verification_focus": [
            "Trace /api/bond-dashboard/headline-kpis result_meta through get_bond_dashboard_headline_kpis, getBondDashboardHeadlineKpis, HeadlineKpis, the candidate-boundary notice, and first-screen conclusion before changing display logic.",
            "Check report_date, previous report date, source_surface, basis/formal_use_allowed, source/rule/cache versions, data_source, yuan-to-yi display, pct/ratio semantics, DV01 display, and empty-state behavior.",
            "Verify GS-BOND-HEADLINE-A remains a page-level DTO sample for headline_kpis and does not approve dictionary-level MTR-BOND-* binding or risk-card equivalence.",
            "Trace /api/bond-dashboard/risk-indicators separately before comparing with PAGE-RISK-001; risk-card fields are not automatically GS-RISK-A / risk-tensor truth.",
        ],
        "guardrails": [
            "Treat MTR-BOND-001 through MTR-BOND-004 as candidate display metrics with pending_confirmation=true.",
            "Do not use GS-BOND-HEADLINE-A to approve dictionary-level MTR-BOND-* bindings; it freezes the page headline DTO and empty-state behavior only.",
            "Do not claim bond-dashboard headline totals are equivalent to MTR-BAL-* formal balance metrics without a separate approved contract.",
            "Do not claim bond-dashboard risk indicators are equivalent to GS-RISK-A or PAGE-RISK-001 risk tensor metrics without a separate approved contract.",
            "Do not recompute headline, risk, duration, yield, DV01, spread, asset-structure, maturity, or industry totals in the frontend.",
            "Keep result_meta, source_surface, data_source, stale/fallback/vendor degradation, empty states, and candidate-boundary messaging visible.",
        ],
    }
    bond_analysis_bundle = {
        "page_slug": "bond-analysis",
        "page_id": "PAGE-BOND-ANALYSIS-001",
        "page_name": "Bond Analysis",
        "aliases": [
            "bond-analysis",
            "bond_analysis",
            "/bond-analysis",
            "PAGE-BOND-ANALYSIS-001",
            "/api/bond-analytics/action-attribution",
            "/api/bond-analytics/dv01-risk",
            "GS-BOND-ANALYSIS-ACTION-ATTR-A",
        ],
        "frontend_route": "/bond-analysis",
        "primary_api": "/api/bond-analytics/action-attribution",
        "supporting_apis": [
            "/api/bond-analytics/dates",
            "/api/bond-analytics/return-decomposition",
            "/api/bond-analytics/benchmark-excess",
            "/api/bond-analytics/krd-curve-risk",
            "/api/bond-analytics/dv01-risk",
            "/api/bond-analytics/dv01-reconciliation",
            "/api/bond-analytics/dv01-movement",
            "/api/bond-analytics/dv01-action-plan",
            "/api/bond-analytics/dv01-limit-config-status",
            "/api/bond-analytics/accounting-class-audit",
            "/api/bond-analytics/credit-spread-migration",
            "/api/bond-analytics/portfolio-headlines",
            "/api/bond-analytics/top-holdings",
            "/api/bond-analytics/position-changes",
            "/api/bond-analytics/yield-curve-term-structure",
            "/api/credit-spread-analysis/detail",
        ],
        "contract_docs": [
            "docs/audits/2026-06-06-bond-analysis-gate-i-lane.md",
            "docs/audits/2026-06-05-bond-analysis-gate-i-boundary-gap.json",
            "docs/page_contracts.md",
            "docs/metric_dictionary.md",
            "docs/golden_sample_catalog.md",
            "docs/live_route_maturity.md",
        ],
        "truth_chain": [
            "docs/audits/2026-06-06-bond-analysis-gate-i-lane.md defines the direct Gate I lane and fixed-income certification blockers for /bond-analysis.",
            "PAGE-BOND-ANALYSIS-001 is a route-specific candidate page contract for /bond-analysis, not PAGE-BOND-001.",
            "PAGE-BOND-001, MTR-BOND-001 through MTR-BOND-004, and GS-BOND-HEADLINE-A are /bond-dashboard evidence only and must not certify /bond-analysis.",
            "GS-BOND-ANALYSIS-ACTION-ATTR-A freezes GET /api/bond-analytics/action-attribution page-level DTO evidence only.",
            "GET /api/bond-analytics/action-attribution drives the first-screen FI risk decision cockpit.",
            "GET /api/bond-analytics/dates supplies report-date choices for BondAnalyticsViewContent.",
            "GET /api/bond-analytics/dv01-risk, dv01-reconciliation, dv01-movement, and dv01-action-plan supply DV01 module evidence.",
            "GET /api/bond-analytics/krd-curve-risk supplies KRD/duration curve-risk evidence.",
            "GET /api/bond-analytics/return-decomposition and benchmark-excess supply return attribution evidence.",
            "GET /api/bond-analytics/credit-spread-migration and /api/credit-spread-analysis/detail supply credit-spread evidence.",
            "GET /api/bond-analytics/portfolio-headlines, top-holdings, and position-changes supply portfolio and holdings evidence.",
            "backend/app/api/routes/bond_analytics.py exposes the bond-analytics route family.",
            "backend/app/services/bond_analytics_service.py and backend/app/core_finance/action_attribution.py own the fixed-income analytics calculations.",
            "frontend/src/api/bondAnalyticsClient.ts maps BondAnalyticsViewContent to /api/bond-analytics/*.",
            "frontend/src/features/bond-analytics/components/BondAnalyticsViewContent.tsx renders the first-screen cockpit and result_meta trust state.",
        ],
        "backend_touchpoints": [
            "backend/app/api/routes/bond_analytics.py",
            "backend/app/api/routes/credit_spread_analysis.py",
            "backend/app/services/bond_analytics_service.py",
            "backend/app/services/credit_spread_analysis_service.py",
            "backend/app/core_finance/action_attribution.py",
            "backend/app/core_finance/bond_analytics/read_models.py",
            "backend/app/repositories/bond_analytics_repo.py",
            "backend/app/schema_registry/duckdb/05_bond_analytics.sql",
        ],
        "frontend_touchpoints": [
            "frontend/src/api/bondAnalyticsClient.ts",
            "frontend/src/api/contracts.ts",
            "frontend/src/features/bond-analytics/components/BondAnalyticsView.tsx",
            "frontend/src/features/bond-analytics/components/BondAnalyticsViewContent.tsx",
            "frontend/src/features/bond-analytics/components/BondAnalyticsDetailSection.tsx",
            "frontend/src/features/bond-analytics/components/DV01RiskView.tsx",
            "frontend/src/features/bond-analytics/components/KRDCurveRiskView.tsx",
            "frontend/src/features/bond-analytics/components/ReturnDecompositionView.tsx",
            "frontend/src/router/routes.tsx",
        ],
        "test_touchpoints": [
            "tests/test_bond_analytics_api.py",
            "tests/test_bond_analytics_service.py",
            "tests/test_bond_analytics_core.py",
            "tests/test_bond_analytics_curve_effects.py",
            "tests/test_bond_analytics_materialize_flow.py",
            "tests/test_action_attribution.py",
            "tests/test_bond_analysis_business_owner_approval_status.py",
            "tests/test_bond_analysis_owner_evidence_packet.py",
            "tests/test_credit_spread_analysis.py",
            "tests/test_golden_samples_capture_ready.py",
            "frontend/src/test/BondAnalyticsView.test.tsx",
            "frontend/src/test/BondAnalyticsViewContent.test.tsx",
            "frontend/tests/playwright/a11y-visual-smoke.spec.mjs",
        ],
        "golden_samples": ["tests/golden_samples/GS-BOND-ANALYSIS-ACTION-ATTR-A"],
        "verification_focus": [
            "GS-BOND-ANALYSIS-ACTION-ATTR-A is capture-ready page-level DTO evidence for action-attribution only; it is not approved formal fixed-income truth.",
            "Trace /api/bond-analytics/action-attribution through getBondAnalyticsActionAttribution, BondAnalyticsViewContent, the FI risk decision cockpit, and result_meta before changing first-screen logic.",
            "Trace DV01, KRD/duration, return decomposition, credit-spread, yield/YTM, holdings, accounting-class, bp movement, and market-value scale separately; browser cleanliness alone does not certify fixed-income metric correctness.",
            "Keep report_date, period_type, accounting_class, asset_class, stale/fallback/no-data, warnings, vendor degradation, and formal_use_allowed states visible.",
        ],
        "guardrails": [
            "PAGE-BOND-ANALYSIS-001 is a route-specific candidate evidence lane; do not certify /bond-analysis without approved golden sample, governance validation, manual audit review, and business-owner approval.",
            "Do not use PAGE-BOND-001, /bond-dashboard, GS-BOND-HEADLINE-A, or MTR-BOND-001 through MTR-BOND-004 to certify /bond-analysis.",
            "Do not promote DV01, duration, KRD, yield/YTM, credit-spread, action-attribution PnL, holdings, or accounting-class values to formal metric truth without approved metric dictionary rows, units, null/date rules, lineage, samples, and tests.",
            "Do not recompute bond-analytics metrics in the frontend; consume backend envelopes and keep result_meta visible.",
            "Keep stale, fallback, warning, no-data, missing limit config, placeholder, partial, and vendor degradation states visible instead of smoothing them into a successful page shell.",
        ],
    }
    positions_bundle = {
        "page_slug": "positions",
        "page_id": "PAGE-POS-001",
        "page_name": "Positions",
        "aliases": [
            "positions",
            "/positions",
            "PAGE-POS-001",
            "/api/positions/bonds",
            "/api/positions/interbank",
        ],
        "frontend_route": "/positions",
        "primary_api": "/api/positions/bonds",
        "supporting_apis": [
            "/api/positions/bonds/sub_types",
            "/api/positions/interbank/product_types",
            "/api/positions/interbank",
            "/api/positions/counterparty/bonds",
            "/api/positions/counterparty/interbank/split",
            "/api/positions/stats/rating",
            "/api/positions/stats/industry",
            "/api/positions/customer/details",
            "/api/positions/customer/trend",
        ],
        "contract_docs": [
            "docs/page_contracts.md",
            "docs/metric_dictionary.md",
            "docs/golden_sample_catalog.md",
        ],
        "truth_chain": [
            "docs/page_contracts.md PAGE-POS-001",
            "docs/metric_dictionary.md MTR-POS-001 and MTR-POS-002 as candidate metrics with pending_confirmation=true and bound_sample_id=none",
            "docs/metric_dictionary.md GAP-POS-LIST",
            "GET /ui/balance-analysis/dates",
            "balance-analysis dates supply the default report_dates selector for this page",
            "backend/app/services/positions_service.py positions.bonds.list / positions.interbank.list",
            "backend/app/services/positions_service.py positions.counterparty.bonds / positions.stats.rating / positions.customer.details",
            "backend/app/schemas/positions.py BondPositionsPageResponse",
            "backend/app/schemas/positions.py InterbankPositionsPageResponse",
            "backend/app/repositories/positions_repo.py snapshot read model",
            "/api/positions/bonds",
            "frontend/src/features/positions/components/PositionsView.tsx",
        ],
        "backend_touchpoints": [
            "backend/app/api/routes/positions.py",
            "backend/app/services/positions_service.py",
            "backend/app/schemas/positions.py",
            "backend/app/repositories/positions_repo.py",
        ],
        "frontend_touchpoints": [
            "frontend/src/api/positionsClient.ts",
            "frontend/src/api/contracts.ts",
            "frontend/src/features/positions/pages/PositionsPage.tsx",
            "frontend/src/features/positions/components/PositionsView.tsx",
            "frontend/src/features/positions/components/CustomerDetailModal.tsx",
            "frontend/src/features/positions/components/RatingDistributionCard.tsx",
            "frontend/src/features/positions/components/IndustryDistributionCard.tsx",
        ],
        "test_touchpoints": [
            "tests/test_positions_api_contract.py",
            "tests/test_live_route_page_contract_completeness.py",
            "tests/test_governance_doc_contract.py",
            "frontend/src/test/PositionsView.test.tsx",
            "frontend/src/test/RouteRegistry.test.tsx",
            "frontend/src/test/CustomerDetailModal.test.tsx",
        ],
        "golden_samples": [],
        "verification_focus": [
            "No dedicated golden sample is currently registered for PAGE-POS-001; verify list/count behavior through page contract, metric dictionary, positions API contract tests, and frontend page tests.",
            "Trace /api/positions/bonds and /api/positions/interbank through positions_service, positionsClient, PositionsView, table totals, candidate-boundary copy, and result_meta display before changing display logic.",
            "Check report_date selection from balance-analysis dates, explicit URL report_date behavior, list request gating, start_date/end_date interval semantics for counterparty/stat endpoints, and customer drilldown report_date behavior.",
            "Verify GAP-POS-LIST remains explicit: positions list/stat DTOs are page evidence but not approved formal business metric truth or dedicated sample truth.",
        ],
        "guardrails": [
            "Treat MTR-POS-001 and MTR-POS-002 as candidate display metrics with pending_confirmation=true and bound_sample_id=none.",
            "Keep GAP-POS-LIST visible in the page contract and do not promote positions list/count DTOs into formal metric truth without new contracts, samples, and tests.",
            "Do not use positions list totals to replace formal PnL, product-category PnL, bond-dashboard headline truth, or balance-analysis truth.",
            "Do not fire list requests without an explicit report_date; preserve balance-analysis dates as the default selector source and keep that dual-source boundary visible.",
            "Do not recompute cross-page scale, PnL, rating, industry, counterparty, or customer metrics in the frontend; consume positions_service envelopes and show result_meta/stale/fallback states.",
            "Keep filter context fields excluded from MTR-* promotion, including date ranges, business type, product type, customer search, direction, and counterparty filters.",
        ],
    }
    market_data_bundle = {
        "page_slug": "market-data",
        "page_id": "PAGE-MKT-001",
        "page_name": "Market Data",
        "aliases": [
            "market-data",
            "market_data",
            "/market-data",
            "PAGE-MKT-001",
            "/ui/preview/macro-foundation",
            "/ui/market-data/rates",
            "/ui/market-data/fx/formal-status",
            "/ui/market-data/ncd-funding-proxy",
            "/ui/market-data/livermore",
        ],
        "frontend_route": "/market-data",
        "primary_api": "/ui/preview/macro-foundation",
        "supporting_apis": [
            "/ui/market-data/rates",
            "/ui/macro/choice-series/latest",
            "/ui/market-data/fx/formal-status",
            "/ui/market-data/fx/analytical",
            "/ui/market-data/ncd-funding-proxy",
            "/api/macro-bond-linkage",
            "/ui/macro/choice-refresh/status/{run_id}",
            "/ui/market-data/livermore",
            "/ui/market-data/livermore/stock-detail",
            "/ui/market-data/livermore/candidate-history",
            "/ui/market-data/livermore/sector-rank-series",
        ],
        "contract_docs": [
            "docs/page_contracts.md",
            "docs/metric_dictionary.md",
            "docs/golden_sample_catalog.md",
            "docs/DOCUMENT_AUTHORITY.md",
            "docs/plans/market-workbench-cursor-prompts.md",
        ],
        "truth_chain": [
            "docs/page_contracts.md PAGE-MKT-001",
            "docs/metric_dictionary.md MTR-MKT-001 macro catalog count is candidate with pending_confirmation=true and bound_sample_id=none",
            "docs/metric_dictionary.md GAP-MKT-DATA: no full-page formal metric dictionary and no full-page capture-ready golden sample",
            "GET /ui/market-data/rates is a formal rates fragment only, not full-page formal truth",
            "backend/app/services/macro_vendor_service.py market_data_rates / macro_foundation / Choice macro analytical evidence",
            "backend/app/services/market_data_ncd_proxy_service.py ncd-funding-proxy returns Shibor funding proxy evidence, not an actual NCD matrix",
            "backend/app/services/market_data_livermore_service.py Livermore analytical surface with backend unsupported_outputs, rule_readiness, and data_gaps",
            "BondFuturesTable / BondTradeDetail / CreditBondTradesTable remain source-pending terminal surfaces",
            "frontend/src/api/marketDataClient.ts getMacroFoundation, getMarketDataRates, getFxAnalytical, getNcdFundingProxy, getMacroBondLinkageAnalysis, and getLivermoreStrategy",
            "frontend/src/features/market-data/hooks/useMarketDataPageData.ts mounted page queries",
            "frontend/src/features/market-data/pages/MarketDataPage.tsx",
        ],
        "backend_touchpoints": [
            "backend/app/api/routes/macro_vendor.py",
            "backend/app/api/routes/macro_bond_linkage.py",
            "backend/app/api/routes/market_data_ncd_proxy.py",
            "backend/app/api/routes/market_data_livermore.py",
            "backend/app/services/macro_vendor_service.py",
            "backend/app/services/macro_bond_linkage_service.py",
            "backend/app/services/market_data_ncd_proxy_service.py",
            "backend/app/services/market_data_livermore_service.py",
            "backend/app/services/livermore_signal_confluence_service.py",
            "backend/app/schemas/macro_vendor.py",
            "backend/app/schemas/macro_bond_linkage.py",
            "backend/app/schemas/ncd_proxy.py",
        ],
        "frontend_touchpoints": [
            "frontend/src/api/marketDataClient.ts",
            "frontend/src/api/contracts.ts",
            "frontend/src/features/market-data/hooks/useMarketDataPageData.ts",
            "frontend/src/features/market-data/pages/MarketDataPage.tsx",
            "frontend/src/features/market-data/pages/marketDataPageModel.ts",
            "frontend/src/features/market-data/pages/MarketDataHeroSection.tsx",
            "frontend/src/features/market-data/components/RateQuoteTable.tsx",
            "frontend/src/features/market-data/components/MoneyMarketTable.tsx",
            "frontend/src/features/market-data/components/NcdMatrix.tsx",
            "frontend/src/features/market-data/components/LivermoreStrategyPanel.tsx",
            "frontend/src/features/market-data/components/LiveResultMetaStrip.tsx",
        ],
        "test_touchpoints": [
            "tests/test_result_meta_on_all_ui_endpoints.py",
            "tests/test_market_data_ncd_proxy_api.py",
            "tests/test_market_data_livermore_api.py",
            "tests/test_market_data_livermore_risk_exit_source.py",
            "tests/test_macro_bond_linkage.py",
            "tests/test_fx_analytical_view_api.py",
            "frontend/src/test/MarketDataPage.test.tsx",
            "frontend/src/features/market-data/pages/marketDataPageModel.test.ts",
            "frontend/src/test/RouteRegistry.test.tsx",
        ],
        "golden_samples": [],
        "verification_focus": [
            "No dedicated golden sample is currently registered for PAGE-MKT-001; verify through page contract, metric dictionary, result_meta endpoint checks, market-data route tests, and frontend page/model tests.",
            "Trace macro catalog count through /ui/preview/macro-foundation, getMacroFoundation, useMarketDataPageData, marketDataPageModel, and MarketDataPage before changing MTR-MKT-001 display logic.",
            "Trace /ui/market-data/rates separately as a formal rates fragment and keep result_meta.basis / formal_use_allowed / emptyReason visible; do not use it as full-page formal proof.",
            "Check analytical, preview, proxy, stale, fallback, blocked, source-pending, and no-data states across FX, NCD proxy, macro-bond linkage, terminal tables, and Livermore panels.",
        ],
        "guardrails": [
            "PAGE-MKT-001 is mixed-source; do not claim full-page formal truth from macro preview, formal rates fragment, FX analytical, NCD proxy, or Livermore outputs.",
            "Do not promote new MTR-* rows, formal rates values, filter context fields, source-pending panels, or analytical/proxy outputs without approved metric dictionary, lineage, sample, and tests.",
            "Do not fill missing rate quote, money market, bond futures, bond trade detail, credit trade, FX, or macro rows with static demo backfill in real mode.",
            "Treat NCD output as Shibor funding proxy evidence unless a separate approved actual NCD term-by-rating matrix contract exists.",
            "Treat Livermore risk_exit as backend-owned and gated by unsupported_outputs, rule_readiness, data_gaps, ACTIVE A-share holdings, entry-cost, and K-line supplement readiness.",
            "Keep getFxFormalStatus scoped as a formal FX status endpoint; the current MarketDataPage implementation does not independently mount it as full-page formal truth.",
        ],
    }
    cross_asset_bundle = {
        "page_slug": "cross-asset",
        "page_id": "GAP-CROSS-ASSET-PAGE",
        "page_name": "Cross Asset Drivers",
        "aliases": [
            "cross-asset",
            "cross_asset",
            "/cross-asset",
            "GAP-CROSS-ASSET-PAGE",
            "/api/macro-bond-linkage/analysis",
            "/ui/market-data/ncd-funding-proxy",
        ],
        "frontend_route": "/cross-asset",
        "primary_api": "frontend aggregation: cross-asset drivers",
        "supporting_apis": [
            "/ui/macro/choice-series/latest",
            "/api/macro-bond-linkage/analysis",
            "/ui/market-data/ncd-funding-proxy",
            "/ui/market-data/livermore",
            "/ui/market-data/livermore/signal-confluence",
            "/ui/news/choice-events/latest",
        ],
        "contract_docs": [
            "docs/live_route_maturity.md",
            "docs/page_contracts.md",
            "docs/metric_dictionary.md",
        ],
        "truth_chain": [
            "docs/live_route_maturity.md marks /cross-asset as temporary-exception with page id GAP-CROSS-ASSET-PAGE.",
            "docs/page_contracts.md lists /cross-asset as a Market Workbench Home downstream page, not standalone formal PAGE contract closure.",
            "frontend/src/features/cross-asset/pages/CrossAssetDriversPage.tsx renders a mixed-source analytical drivers surface.",
            "GET /ui/macro/choice-series/latest supplies Choice macro latest evidence.",
            "GET /api/macro-bond-linkage/analysis supplies macro-bond analytical linkage evidence.",
            "GET /ui/market-data/ncd-funding-proxy supplies Shibor funding proxy evidence, not actual NCD matrix truth.",
            "GET /ui/market-data/livermore and /signal-confluence supply observational stock strategy readiness.",
            "GET /ui/news/choice-events/latest supplies analytical event context only.",
        ],
        "backend_touchpoints": [
            "backend/app/api/routes/macro_vendor.py",
            "backend/app/api/routes/macro_bond_linkage.py",
            "backend/app/api/routes/market_data_ncd_proxy.py",
            "backend/app/api/routes/market_data_livermore.py",
            "backend/app/api/routes/choice_news.py",
            "backend/app/services/macro_vendor_service.py",
            "backend/app/services/macro_bond_linkage_service.py",
            "backend/app/services/market_data_ncd_proxy_service.py",
            "backend/app/services/market_data_livermore_service.py",
            "backend/app/services/livermore_signal_confluence_service.py",
            "backend/app/services/choice_news_service.py",
        ],
        "frontend_touchpoints": [
            "frontend/src/api/marketDataClient.ts",
            "frontend/src/api/contracts.ts",
            "frontend/src/features/cross-asset/pages/CrossAssetDriversPage.tsx",
            "frontend/src/features/cross-asset/pages/CrossAssetPage.tsx",
            "frontend/src/features/cross-asset/lib/crossAssetDriversPageModel.ts",
            "frontend/src/features/cross-asset/lib/crossAssetKpiModel.ts",
            "frontend/src/router/routes.tsx",
        ],
        "test_touchpoints": [
            "frontend/src/test/CrossAssetDriversRoute.test.tsx",
            "frontend/src/test/CrossAssetPage.test.tsx",
            "frontend/src/test/crossAssetDriversPageModel.test.ts",
            "frontend/src/features/cross-asset/lib/crossAssetAnalytics.test.ts",
            "frontend/src/features/cross-asset/lib/crossAssetKpiModel.test.ts",
            "frontend/tests/playwright/a11y-visual-smoke.spec.mjs",
            "tests/test_live_route_page_contract_completeness.py",
        ],
        "golden_samples": [],
        "verification_focus": [
            "No dedicated golden sample is currently registered for GAP-CROSS-ASSET-PAGE; verify through live-route maturity, cross-asset frontend/model tests, Playwright smoke, and source lineage evidence.",
            "Trace /cross-asset through CrossAssetDriversPage queries, crossAssetDriversPageModel, source-status flags, evidence details, and decision rail before changing display logic.",
            "Check mixed dates, stale/fallback/no-data/source-blocked states across macro, macro-bond linkage, NCD proxy, Livermore, and news-event evidence.",
        ],
        "guardrails": [
            "GAP-CROSS-ASSET-PAGE is a mixed-source analytical surface; do not claim full-page formal market, bond, stock, or news truth.",
            "Do not create MTR-* rows, page-level formal use, trading instructions, or allocation decisions from cross-asset linkage evidence.",
            "Treat NCD output as Shibor funding proxy evidence unless a separate approved actual NCD matrix contract exists.",
            "Treat Livermore and signal-confluence output as observational readiness, not trading instruction or formal stock-analysis truth.",
            "Do not hide stale, fallback, source-blocked, no-data, mixed-date, or vendor degradation states behind a successful cross-asset shell.",
            "Do not backfill missing macro, NCD, Livermore, or event rows with static demo values in real mode.",
        ],
    }
    stock_analysis_bundle = {
        "page_slug": "stock-analysis",
        "page_id": "GAP-STOCK-ANALYSIS-PAGE",
        "page_name": "Stock Analysis",
        "aliases": [
            "stock-analysis",
            "stock_analysis",
            "/stock-analysis",
            "GAP-STOCK-ANALYSIS-PAGE",
        ],
        "frontend_route": "/stock-analysis",
        "primary_api": "/ui/market-data/livermore",
        "supporting_apis": [
            "/ui/market-data/livermore/signal-confluence",
            "/ui/market-data/livermore/stock-detail",
            "/ui/market-data/livermore/candidate-history",
            "/ui/market-data/livermore/strategy-score",
            "/ui/market-data/livermore/strategy-optimization",
            "/ui/market-data/livermore/cycle-proxy-backtest",
            "/ui/market-data/livermore/candidate-history-portfolio-backtest",
            "/ui/market-data/livermore/sector-rank-series",
        ],
        "contract_docs": [
            "docs/audits/2026-06-06-stock-analysis-gate-i-lane.md",
            "docs/pnl/stock-analysis-owner-evidence-packet.md",
            "docs/pnl/stock-analysis-business-owner-approval-template.md",
            "docs/live_route_maturity.md",
            "docs/page_contracts.md",
            "docs/metric_dictionary.md",
            "docs/golden_sample_catalog.md",
        ],
        "truth_chain": [
            "docs/audits/2026-06-06-stock-analysis-gate-i-lane.md defines the direct observational Gate I lane and no-trading-instruction boundary for /stock-analysis.",
            "docs/pnl/stock-analysis-owner-evidence-packet.md packages owner-review evidence without approving page closure.",
            "docs/pnl/stock-analysis-business-owner-approval-template.md captures pending owner fields and preserves formal_use_allowed=false.",
            "tests/golden_samples/GS-STOCK-ANALYSIS-OBS-A freezes the observation-only Livermore primary DTO for /stock-analysis.",
            "docs/live_route_maturity.md marks /stock-analysis as temporary-exception with page id GAP-STOCK-ANALYSIS-PAGE",
            "docs/page_contracts.md currently lists /stock-analysis as a Market Workbench Home downstream page, not as a standalone PAGE-STOCK contract",
            "search_contract_docs has no PAGE-STOCK-* or MTR-STOCK-* binding for this page in the current contract set",
            "GET /ui/market-data/livermore returns market_data.livermore analytical observation-only evidence",
            "GET /ui/market-data/livermore/signal-confluence returns read-only signal confluence diagnostics",
            "GET /ui/market-data/livermore/strategy-score and strategy-optimization use candidate-history diagnostics for ranking, not formal metric approval",
            "GET /ui/market-data/livermore/cycle-proxy-backtest and candidate-history-portfolio-backtest are reduced proxy backtests with full-strategy readiness gaps",
            "backend/app/services/market_data_livermore_service.py keeps risk_exit backend-owned and gated by unsupported_outputs, rule_readiness, and data_gaps",
            "backend/app/services/livermore_candidate_history_service.py builds candidate-history diagnostics from read-only persisted observations",
            "frontend/src/features/stock-analysis/pages/StockAnalysisPage.tsx renders the route as a read-only review surface with readiness and boundary states visible",
            "frontend/src/features/stock-analysis/lib/stockAnalysisPageModel.ts localizes observation-only and no-trading-instruction boundaries",
        ],
        "backend_touchpoints": [
            "backend/app/api/routes/market_data_livermore.py",
            "backend/app/services/market_data_livermore_service.py",
            "backend/app/services/livermore_signal_confluence_service.py",
            "backend/app/services/livermore_candidate_history_service.py",
            "backend/app/services/livermore_stock_detail_service.py",
            "backend/app/services/livermore_sector_rank_series_service.py",
            "backend/app/core_finance/livermore_strategy.py",
            "backend/app/core_finance/livermore_risk_exit.py",
        ],
        "frontend_touchpoints": [
            "frontend/src/api/marketDataClient.ts",
            "frontend/src/api/contracts.ts",
            "frontend/src/features/stock-analysis/pages/StockAnalysisPage.tsx",
            "frontend/src/features/stock-analysis/lib/stockAnalysisPageModel.ts",
            "frontend/src/features/stock-analysis/lib/buildStockAnalysisAgentPageContext.ts",
            "frontend/src/features/stock-analysis/components/StockDetailDrawer.tsx",
            "frontend/src/router/routes.tsx",
        ],
        "test_touchpoints": [
            "tests/test_market_data_livermore_api.py",
            "tests/test_market_data_livermore_risk_exit_source.py",
            "tests/test_market_data_livermore_candidate_history.py",
            "tests/test_livermore_stock_detail_service.py",
            "tests/test_golden_samples_capture_ready.py",
            "tests/test_stock_analysis_business_owner_approval_status.py",
            "tests/test_stock_analysis_owner_evidence_packet.py",
            "frontend/src/test/StockAnalysisPage.test.tsx",
            "frontend/src/test/StockAnalysisPageModel.test.ts",
            "frontend/src/features/stock-analysis/lib/buildConsensusSummary.test.ts",
            "frontend/src/test/RouteRegistry.test.tsx",
        ],
        "golden_samples": ["tests/golden_samples/GS-STOCK-ANALYSIS-OBS-A"],
        "verification_focus": [
            "Dedicated golden sample GS-STOCK-ANALYSIS-OBS-A is capture-ready pending approval and freezes observation-only Livermore DTO evidence; it does not approve trading instructions or formal stock-analysis truth.",
            "There is currently no PAGE-STOCK standalone contract or MTR-STOCK binding; do not treat this trace bundle as contract closure or formal metric approval.",
            "Trace /ui/market-data/livermore through marketDataClient, StockAnalysisPage query state, stockAnalysisPageModel, readiness panels, boundary summary, and stock detail drawer before changing display logic.",
            "Check as_of_date/requested_as_of_date, stale/fallback/no-data/error states, unsupported_outputs, rule_readiness, data_gaps, proxy-backtest sample maturity, and risk_exit blocked/ready conditions.",
        ],
        "guardrails": [
            "GAP-STOCK-ANALYSIS-PAGE is observational only; do not generate trading instructions, execution approval, allocation advice, or position-change commands from this page.",
            "Do not claim full-page formal metric truth from Livermore candidates, signal confluence, sector ranking, strategy scores, optimization diagnostics, or proxy backtests.",
            "Do not promote any stock-analysis field to MTR-* without a PAGE-STOCK contract, metric dictionary row, unit/precision/null/date rules, lineage records, golden samples, and tests.",
            "Keep Livermore readiness, fallback, stale, unsupported, missing-input, and no-data states visible instead of hiding them behind a successful page shell.",
            "Treat risk_exit as backend-owned and gated by ACTIVE A-share holdings, entry-cost, close-history, and gate-supplement readiness.",
            "Do not backfill missing stock, candidate-history, risk_exit, sector, signal-confluence, or proxy-backtest rows with static demo values in real mode.",
        ],
    }
    macro_toolkit_bundle = {
        "page_slug": "macro-toolkit",
        "page_id": "PAGE-MACRO-TOOLKIT-001",
        "page_name": "Macro Toolkit",
        "aliases": [
            "macro-toolkit",
            "macro_toolkit",
            "/macro-toolkit",
            "PAGE-MACRO-TOOLKIT-001",
            "/ui/macro/toolkit/analysis",
            "/ui/macro/toolkit/scripts",
            "/ui/macro/toolkit/analysis/strategy-summaries",
        ],
        "frontend_route": "/macro-toolkit",
        "primary_api": "/ui/macro/toolkit/analysis",
        "supporting_apis": [
            "/ui/macro/toolkit/analysis/strategy-summaries",
            "/ui/macro/toolkit/scripts",
            "/ui/macro/toolkit/adversarial-signal",
            "POST /ui/macro/toolkit/scripts/{name}/run",
            "POST /ui/macro/toolkit/cffex-member-rank/refresh",
            "POST /ui/macro/toolkit/choice-stock/refresh",
            "GET /ui/macro/toolkit/choice-stock/refresh-status",
            "POST /ui/macro/toolkit/source-backfill/refresh",
            "POST /ui/macro/toolkit/commodity-futures/refresh",
        ],
        "contract_docs": [
            "docs/page_contracts.md",
            "docs/metric_dictionary.md",
            "docs/live_route_maturity.md",
            "docs/golden_sample_catalog.md",
        ],
        "truth_chain": [
            "docs/page_contracts.md PAGE-MACRO-TOOLKIT-001 candidate tooling surface",
            "docs/metric_dictionary.md /macro-toolkit has no MTR-* and no MTR-MACRO-*; tooling/analysis status evidence is not formal metric truth",
            "docs/metric_dictionary.md coverage.hit_rate, script counts, strategy counts, real-chain counts, refresh row counts, and source/version/run_id are status/tracing evidence only",
            "GET /ui/macro/toolkit/analysis?detail=core returns macro_toolkit.analysis for analytical/tooling evidence",
            "GET /ui/macro/toolkit/analysis/strategy-summaries returns macro_toolkit.analysis.strategy_summaries for strategy supply evidence",
            "GET /ui/macro/toolkit/scripts returns macro_toolkit.scripts for script registry and operation/script outputs",
            "POST refresh and script-run endpoints return operation/script outputs only; run_id, started_at, and finished_at are operational trace fields",
            "backend/app/api/routes/macro_toolkit.py macro_toolkit.analysis / macro_toolkit.scripts / macro_toolkit.choice_stock_refresh / macro_toolkit.cffex_member_rank_refresh",
            "backend/app/services/macro_toolkit_service.py script registry, refresh status, and run payload helpers",
            "frontend/src/api/macroToolkitClient.ts getMacroToolkitAnalysis, getMacroToolkitStrategySummaries, getMacroToolkitScripts, runMacroToolkitScript, and refresh clients",
            "frontend/src/features/macro-toolkit/pages/MacroToolkitPage.tsx MacroToolkitContractBoundary keeps formal_use_allowed=false visible",
        ],
        "backend_touchpoints": [
            "backend/app/api/routes/macro_toolkit.py",
            "backend/app/services/macro_toolkit_service.py",
            "backend/app/core_finance/macro",
            "backend/app/core_finance/macro/toolkit/scripts",
        ],
        "frontend_touchpoints": [
            "frontend/src/api/macroToolkitClient.ts",
            "frontend/src/api/contracts.ts",
            "frontend/src/features/macro-toolkit/pages/MacroToolkitPage.tsx",
            "frontend/src/router/routes.tsx",
        ],
        "test_touchpoints": [
            "tests/test_macro_toolkit_scripts.py",
            "tests/test_macro_toolkit_choice_stock_refresh_overview.py",
            "tests/test_macro_toolkit_factor_snapshot_dates.py",
            "tests/test_macro_toolkit_a_share_risk.py",
            "tests/test_macro_query_contract_smoke.py",
            "tests/test_write_route_auth_contract.py",
            "tests/test_governance_doc_contract.py",
            "frontend/src/test/MacroToolkitPage.test.tsx",
            "frontend/src/test/RouteRegistry.test.tsx",
            "frontend/src/test/navigation.test.ts",
            "frontend/src/test/macroToolkitClient.test.ts",
        ],
        "golden_samples": [],
        "verification_focus": [
            "No dedicated golden sample is currently registered for PAGE-MACRO-TOOLKIT-001; verify through page contract, metric dictionary, route tests, macro toolkit API tests, auth tests, and frontend MacroToolkitPage tests.",
            "Trace analysis through /ui/macro/toolkit/analysis, macro_toolkit.analysis result_meta, getMacroToolkitAnalysis, MacroToolkitPage query state, and MacroToolkitContractBoundary before changing display logic.",
            "Trace script registry, script run, refresh, and refresh-status behavior separately as operational evidence; do not use operation/script outputs as formal metric truth.",
            "Check loading, empty, stale, fallback, source/version/run_id, deferred section, permission, and no-data states across analysis, strategy, script, and refresh sections.",
        ],
        "guardrails": [
            "PAGE-MACRO-TOOLKIT-001 is tooling/analysis only; do not claim formal metric truth from macro analysis, script registry, refresh status, strategy summaries, or operation/script outputs.",
            "Do not treat analysis cards, sample strategies, script outputs, vendor reads, refresh counts, source/version/run_id, or coverage.hit_rate as investment recommendations or an executable trade signal.",
            "Do not promote any macro toolkit field to MTR-* or MTR-MACRO-* without approved metric dictionary rows, units, precision/null rules, lineage, samples or candidate decision, and tests.",
            "Do not fill missing macro analysis, strategy, script, vendor, or refresh evidence with static demo backfill in real mode.",
            "Do not hide fallback, stale, source gaps, permission failures, no-data, or deferred-section states behind a successful page shell.",
            "Do not recompute macro indicators, strategy counts, refresh row counts, or script-derived measures in the frontend; consume backend envelopes and keep result_meta visible.",
        ],
    }
    macro_observation_bundle = {
        "page_slug": "macro-observation",
        "page_id": "PAGE-MACRO-OBS-001",
        "page_name": "Macro Observation",
        "aliases": [
            "macro-observation",
            "macro_observation",
            "/macro-observation",
            "PAGE-MACRO-OBS-001",
        ],
        "frontend_route": "/macro-observation",
        "primary_api": "/ui/macro/toolkit/analysis",
        "supporting_apis": [
            "/ui/macro/toolkit/analysis/strategy-summaries",
        ],
        "contract_docs": [
            "docs/page_contracts.md",
            "docs/metric_dictionary.md",
            "docs/live_route_maturity.md",
            "docs/golden_sample_catalog.md",
        ],
        "truth_chain": [
            "docs/page_contracts.md PAGE-MACRO-OBS-001 read-only macro observation surface",
            "docs/metric_dictionary.md /macro-observation has no MTR-* and no MTR-MACRO-*; read-only macro evidence is not formal metric truth",
            "docs/metric_dictionary.md core signals, crowding risk, strategy supply status, and source/version/run_id are analysis evidence only",
            "GET /ui/macro/toolkit/analysis?detail=core is reused for read-only macro observation evidence",
            "GET /ui/macro/toolkit/analysis/strategy-summaries supplies read-only strategy evidence",
            "frontend/src/features/macro-toolkit/pages/MacroToolkitPage.tsx mode='observation'",
            "frontend/src/features/macro-toolkit/pages/MacroToolkitPage.tsx macro-observation-readonly-boundary keeps read-only macro observation visible",
            "frontend/src/features/macro-toolkit/pages/MacroToolkitPage.tsx MacroToolkitContractBoundary keeps formal_use_allowed=false visible",
        ],
        "backend_touchpoints": [
            "backend/app/api/routes/macro_toolkit.py",
            "backend/app/services/macro_toolkit_service.py",
            "backend/app/core_finance/macro",
        ],
        "frontend_touchpoints": [
            "frontend/src/api/macroToolkitClient.ts",
            "frontend/src/api/contracts.ts",
            "frontend/src/features/macro-toolkit/pages/MacroToolkitPage.tsx",
            "frontend/src/router/routes.tsx",
        ],
        "test_touchpoints": [
            "tests/test_governance_doc_contract.py",
            "tests/test_live_route_page_contract_completeness.py",
            "frontend/src/test/MacroToolkitPage.test.tsx",
            "frontend/src/test/RouteRegistry.test.tsx",
            "frontend/src/test/navigation.test.ts",
            "frontend/src/test/macroToolkitClient.test.ts",
        ],
        "golden_samples": [],
        "verification_focus": [
            "No dedicated golden sample is currently registered for PAGE-MACRO-OBS-001; verify through page contract, metric dictionary, route tests, and frontend MacroToolkitPage observation-mode tests.",
            "Trace observation display through /ui/macro/toolkit/analysis, /ui/macro/toolkit/analysis/strategy-summaries, getMacroToolkitAnalysis, getMacroToolkitStrategySummaries, and MacroToolkitPage mode='observation'.",
            "Confirm macro-observation-readonly-boundary remains visible in normal and error states and that script registry, run, refresh, and refresh-status controls stay absent.",
            "Check loading, empty, stale, fallback, source/version/run_id, deferred-section, and no-data states without inheriting operational actions from /macro-toolkit.",
        ],
        "guardrails": [
            "PAGE-MACRO-OBS-001 is read-only; do not expose script registry, script run, refresh actions, refresh-status controls, or operational registries on /macro-observation.",
            "Do not promote read-only observation evidence to MTR-* or MTR-MACRO-* without approved metric dictionary rows, lineage, sample or candidate decision, and tests.",
            "Keep the read-only boundary and macro-observation-readonly-boundary visible in normal and error states.",
            "Do not use macro observation to replace market-data rates/macros, stock-analysis decisions, formal PnL, balance, risk, or executive truth.",
            "Do not hide fallback, stale, source gaps, no-data, or analysis failure states behind the shared MacroToolkitPage shell.",
        ],
    }

    agent_bundle = {
        "page_slug": "agent",
        "page_id": "PAGE-AGENT-001",
        "page_name": "Agent Workbench",
        "aliases": [
            "agent",
            "/agent",
            "PAGE-AGENT-001",
            "POST /api/agent/runs",
            "GET /api/agent/runs/{run_id}",
            "POST /api/agent/query",
        ],
        "frontend_route": "/agent",
        "primary_api": "POST /api/agent/runs",
        "supporting_apis": [
            "GET /api/agent/runs/{run_id}",
            "POST /api/agent/query",
        ],
        "contract_docs": [
            "docs/page_contracts.md",
            "docs/metric_dictionary.md",
            "docs/live_route_maturity.md",
        ],
        "truth_chain": [
            "docs/page_contracts.md PAGE-AGENT-001 active Agent Workbench",
            "docs/metric_dictionary.md PAGE-AGENT-001 has no standalone MTR-*; agent answers are analytical/read-only unless result_meta explicitly allows formal use",
            "backend/app/api/routes/agent.py enforces read-only agent request context before executing managed runs or compatibility query calls",
            "POST /api/agent/runs creates managed agent runs; GET /api/agent/runs/{run_id} polls status and ownership",
            "POST /api/agent/query is a local/synchronous compatibility path, not a page metric endpoint",
            "AgentEnvelope carries answer, cards, evidence, result_meta, next_drill, and suggested_actions",
            "AgentResultMeta.formal_use_allowed gates whether an answer may be presented as a formal financial result",
            "frontend/src/api/agentClient.ts queryAgent",
            "frontend/src/features/agent/AgentWorkbenchPage.tsx builds AgentQueryRequest and displays evidence/result metadata",
        ],
        "backend_touchpoints": [
            "backend/app/api/routes/agent.py",
            "backend/app/services/agent_run_service.py",
            "backend/app/services/agent_service.py",
            "backend/app/agent/schemas/agent_request.py",
            "backend/app/agent/schemas/agent_response.py",
            "backend/app/agent/schemas/agent_run.py",
            "backend/app/governance/agent_audit.py",
        ],
        "frontend_touchpoints": [
            "frontend/src/api/agentClient.ts",
            "frontend/src/api/contracts.ts",
            "frontend/src/features/agent/AgentWorkbenchPage.tsx",
            "frontend/src/features/agent/components/AgentEvidencePanel.tsx",
            "frontend/src/features/agent/components/AgentResultMetaPanel.tsx",
            "frontend/src/router/routes.tsx",
        ],
        "test_touchpoints": [
            "tests/test_agent_api_contract.py",
            "tests/test_agent_enabled_path_smoke.py",
            "tests/test_agent_runs_api.py",
            "tests/test_agent_intent_routing.py",
            "tests/test_agent_audit_log_contract.py",
            "frontend/src/test/AgentWorkbenchPage.test.tsx",
            "frontend/src/test/AgentPlaceholderPage.test.tsx",
            "frontend/src/test/AgentClient.test.ts",
            "frontend/src/test/RouteRegistry.test.tsx",
        ],
        "golden_samples": [],
        "verification_focus": [
            "No dedicated golden sample is currently registered for PAGE-AGENT-001; verify through page contract, agent API contract, run ownership/status tests, frontend AgentWorkbenchPage tests, and route registry tests.",
            "Trace answers through AgentQueryRequest, /api/agent/runs or /api/agent/query, AgentEnvelope, evidence/result_meta panels, and formal_use_allowed before changing display logic.",
            "Check disabled-provider, rejected request, failed run, forbidden run ownership, empty answer, stale/fallback, and vendor degradation states remain visible.",
        ],
        "guardrails": [
            "PAGE-AGENT-001 is read-only analytical workbench surface; do not treat an agent answer as a formal financial result unless result_meta.formal_use_allowed explicitly allows it.",
            "Do not allow mutating or write-route actions through agent page context, suggested actions, or run payloads without a separate approved write contract.",
            "Do not use agent answers to replace formal metrics, source lineage, page contracts, result_meta evidence, or governed downstream page truth.",
            "Keep disabled-provider, permission, stale, fallback, vendor degradation, and no-data states visible instead of smoothing them into a successful answer.",
        ],
    }
    cube_query_bundle = {
        "page_slug": "cube-query",
        "page_id": "PAGE-CUBE-QUERY-001",
        "page_name": "Cube Query",
        "aliases": [
            "cube-query",
            "cube_query",
            "/cube-query",
            "PAGE-CUBE-QUERY-001",
            "POST /api/cube/query",
            "GET /api/cube/dimensions/{fact_table}",
        ],
        "frontend_route": "/cube-query",
        "primary_api": "POST /api/cube/query",
        "supporting_apis": [
            "GET /api/cube/dimensions/{fact_table}",
        ],
        "contract_docs": [
            "docs/page_contracts.md",
            "docs/metric_dictionary.md",
            "docs/live_route_maturity.md",
        ],
        "truth_chain": [
            "docs/page_contracts.md PAGE-CUBE-QUERY-001 active candidate query surface",
            "docs/metric_dictionary.md PAGE-CUBE-QUERY-001 has no standalone MTR-* and no standalone MTR binding; formal semantics are scoped to the returned query result_meta",
            "POST /api/cube/query returns CubeQueryResult / CubeQueryResponse rows, columns, summary, drill path, and result_meta for the selected query",
            "GET /api/cube/dimensions/{fact_table} describes allowed dimensions for backend-approved fact tables",
            "backend/app/api/routes/cube_query.py delegates to AnalyticalBridgeService and CubeQueryService",
            "backend/app/services/cube_query_service.py keeps allowed table/dimension semantics backend-owned",
            "frontend/src/api/cubeClient.ts executeCubeQuery and getCubeDimensions",
            "frontend/src/features/cube-query/pages/CubeQueryPage.tsx builds CubeQueryRequest",
        ],
        "backend_touchpoints": [
            "backend/app/api/routes/cube_query.py",
            "backend/app/services/cube_query_service.py",
            "backend/app/services/analytical_bridge_service.py",
            "backend/app/repositories/cube_query_repo.py",
            "backend/app/schemas/cube_query.py",
        ],
        "frontend_touchpoints": [
            "frontend/src/api/cubeClient.ts",
            "frontend/src/api/contracts.ts",
            "frontend/src/features/cube-query/pages/CubeQueryPage.tsx",
            "frontend/src/router/routes.tsx",
        ],
        "test_touchpoints": [
            "tests/test_cube_query_api.py",
            "tests/test_cube_query_service.py",
            "tests/test_cube_query_schema_contract.py",
            "tests/test_live_route_page_contract_completeness.py",
            "frontend/src/test/CubeQueryPage.test.tsx",
            "frontend/src/test/RouteRegistry.test.tsx",
        ],
        "golden_samples": [],
        "verification_focus": [
            "No dedicated golden sample is currently registered for PAGE-CUBE-QUERY-001; verify through cube query API/service/schema tests, page contract, route registry, and CubeQueryPage tests.",
            "Trace a query through CubeQueryRequest, /api/cube/query, backend-approved fact table/dimensions/measures, CubeQueryResult, result_meta, and the rendered query table before changing query display logic.",
            "Check invalid table, invalid dimension, invalid measure, invalid filter, unavailable storage, empty result, stale/fallback, and quality states fail closed or stay visible.",
        ],
        "guardrails": [
            "PAGE-CUBE-QUERY-001 is a candidate query surface; do not create a new page-level KPI, metric definition, or formal business conclusion outside the returned query result_meta.",
            "Unsupported fact tables, dimensions, measures, filters, or storage states must fail closed with visible errors.",
            "Do not let the frontend reinterpret measure units, date semantics, formal basis, stale/fallback status, or query result_meta.",
            "Do not render demo rows for empty query results in real mode.",
        ],
    }

    def module_home_bundle(
        *,
        page_slug: str,
        page_id: str,
        page_name: str,
        frontend_route: str,
        kind: str,
        downstream_pages: list[str],
        supporting_apis: list[str],
        backend_touchpoints: list[str],
        truth_detail: str,
        guardrail_detail: str,
        golden_samples: list[str] | None = None,
        verification_focus: list[str] | None = None,
    ) -> dict[str, Any]:
        return {
            "page_slug": page_slug,
            "page_id": page_id,
            "page_name": page_name,
            "aliases": [
                page_slug,
                page_slug.replace("-", "_"),
                frontend_route,
                page_id,
            ],
            "frontend_route": frontend_route,
            "primary_api": f"frontend aggregation: module-home/{kind}",
            "supporting_apis": [*downstream_pages, *supporting_apis],
            "contract_docs": [
                "docs/page_contracts.md",
                "docs/metric_dictionary.md",
                "docs/live_route_maturity.md",
            ],
            "truth_chain": [
                f"docs/page_contracts.md {page_id} active module home",
                f"docs/metric_dictionary.md {frontend_route} is a module home route with no standalone MTR-* and no standalone MTR binding",
                f"frontend/src/features/workbench/module-home/moduleHomeConfig.ts kind={kind}",
                f"frontend/src/features/workbench/module-home/moduleHomeModel.ts buildModuleHomeView kind={kind}",
                "frontend/src/features/workbench/module-home/ModuleWorkbenchHomePage.tsx mounts module-home queries and source statuses",
                truth_detail,
            ],
            "backend_touchpoints": backend_touchpoints,
            "frontend_touchpoints": [
                "frontend/src/features/workbench/module-home/ModuleWorkbenchHomePage.tsx",
                "frontend/src/features/workbench/module-home/moduleHomeModel.ts",
                "frontend/src/features/workbench/module-home/moduleHomeConfig.ts",
                "frontend/src/router/routes.tsx",
            ],
            "test_touchpoints": [
                "frontend/src/test/ModuleWorkbenchHomeModel.test.ts",
                "frontend/src/test/ModuleWorkbenchHomePage.test.tsx",
                "frontend/src/test/RouteRegistry.test.tsx",
                "tests/test_live_route_page_contract_completeness.py",
                "tests/test_page_contract_metric_dictionary_completeness.py",
            ],
            "golden_samples": list(golden_samples or []),
            "verification_focus": verification_focus
            or [
                f"No dedicated golden sample is currently registered for {page_id}; verify through the page contract, module home model/page tests, route registry tests, and downstream page/API tests when changing displayed fields.",
                f"Trace {frontend_route} through moduleHomeConfig, ModuleWorkbenchHomePage queries, buildModuleHomeView, source statuses, and downstream page result_meta before changing module-home display logic.",
                "Check mixed dates, no-data, partial child-query failure, stale/fallback, source metadata, and downstream page ownership remain visible.",
            ],
            "guardrails": [
                f"{page_id} is a module home and navigation summary, not a standalone formal metric page.",
                "Keep formal-use claims scoped to downstream pages, endpoint result_meta, page contracts, and approved metric dictionary rows.",
                guardrail_detail,
                "Do not backfill missing child-query data with static demo values in real mode.",
                "Do not hide stale, fallback, source gaps, no-data, or child-query errors behind a successful module home shell.",
            ],
        }

    portfolio_home_bundle = module_home_bundle(
        page_slug="portfolio-home",
        page_id="PAGE-PORTFOLIO-HOME-001",
        page_name="Portfolio Workbench Home",
        frontend_route="/portfolio",
        kind="portfolio",
        downstream_pages=["/balance-analysis", "/bond-dashboard", "/positions", "/pnl-attribution"],
        supporting_apis=[
            "/ui/balance-analysis/overview",
            "/api/bond-dashboard/headline-kpis",
            "/api/positions/bonds",
            "/api/pnl-attribution/analysis-summary",
            "/api/risk/tensor/dates",
        ],
        backend_touchpoints=[
            "backend/app/api/routes/balance_analysis.py",
            "backend/app/api/routes/bond_dashboard.py",
            "backend/app/api/routes/positions.py",
            "backend/app/api/routes/pnl_attribution.py",
            "backend/app/api/routes/risk_tensor.py",
        ],
        truth_detail="Portfolio module home aggregates balance, bond dashboard, positions, attribution, and risk.tensor.dates evidence only to guide drilldown and risk-date closure review.",
        guardrail_detail="Do not use portfolio module-home cards as a standalone formal metric page or as replacements for balance, bond, positions, attribution, or PAGE-RISK-001 risk tensor truth.",
        golden_samples=["tests/golden_samples/GS-PORTFOLIO-HOME-A"],
        verification_focus=[
            "GS-PORTFOLIO-HOME-A is a supporting-only observational evidence pack for the portfolio module-home aggregation; it does not approve page-level formal use.",
            "Trace /portfolio through moduleHomeConfig, ModuleWorkbenchHomePage queries, buildModuleHomeView, source statuses, downstream result_meta, and risk.tensor.dates before changing module-home display logic.",
            "Check mixed dates, no-data, partial child-query failure, stale/fallback, source metadata, risk tensor date mismatch, and downstream page ownership remain visible.",
        ],
    )
    market_home_bundle = module_home_bundle(
        page_slug="market-home",
        page_id="PAGE-MARKET-HOME-001",
        page_name="Market Workbench Home",
        frontend_route="/market-overview",
        kind="market",
        downstream_pages=["/market-data", "/macro-toolkit", "/stock-analysis", "/news-events"],
        supporting_apis=[
            "/ui/macro/choice-series/latest",
            "/ui/market-data/rates",
            "/ui/market-data/catalog",
            "/ui/macro/toolkit/analysis",
            "/ui/macro/toolkit/analysis/strategy-summaries",
        ],
        backend_touchpoints=[
            "backend/app/api/routes/macro_vendor.py",
            "backend/app/api/routes/macro_toolkit.py",
            "backend/app/api/routes/market_data_livermore.py",
        ],
        truth_detail="Market module home aggregates market data, macro toolkit, stock observation, and news/event readiness only to guide market drilldown.",
        guardrail_detail="Do not promote observational, vendor-readiness, macro-toolkit, stock, news, or event summaries into formal market data claims.",
    )
    risk_home_bundle = module_home_bundle(
        page_slug="risk-home",
        page_id="PAGE-RISK-HOME-001",
        page_name="Risk Workbench Home",
        frontend_route="/risk-overview",
        kind="risk",
        downstream_pages=["/risk-tensor", "/concentration-monitor", "/cashflow-projection"],
        supporting_apis=[
            "/api/risk/tensor/dates",
            "/api/risk/tensor",
            "/api/cashflow-projection",
        ],
        backend_touchpoints=[
            "backend/app/api/routes/risk_tensor.py",
            "backend/app/api/routes/cashflow_projection.py",
        ],
        truth_detail="Risk module home summarizes risk tensor and cashflow readiness only to guide risk drilldown.",
        guardrail_detail="Do not replace PAGE-RISK-001 formal risk truth, regulatory DV01, liquidity pressure, or concentration limits with frontend module-home estimates.",
    )
    performance_home_bundle = module_home_bundle(
        page_slug="performance-home",
        page_id="PAGE-PERFORMANCE-HOME-001",
        page_name="Performance Workbench Home",
        frontend_route="/performance",
        kind="performance",
        downstream_pages=["/kpi", "/team-performance", "/pnl-by-business", "/product-category-pnl"],
        supporting_apis=[
            "/api/kpi/owners",
            "/api/kpi/values/summary",
            "/api/pnl/by-business-ytd",
            "/ui/pnl/product-category",
        ],
        backend_touchpoints=[
            "backend/app/api/routes/kpi.py",
            "backend/app/api/routes/pnl.py",
            "backend/app/api/routes/product_category_pnl.py",
        ],
        truth_detail="Performance module home aggregates KPI, team, business PnL, and product PnL entry-point evidence only to guide performance review drilldown.",
        guardrail_detail="Do not rebuild KPI scoring, team allocation, business PnL, or product PnL formulas on the module home.",
    )
    kpi_performance_bundle = {
        "page_slug": "kpi-performance",
        "page_id": "GAP-KPI-PERFORMANCE-PAGE",
        "page_name": "KPI Performance",
        "aliases": [
            "kpi-performance",
            "kpi_performance",
            "kpi",
            "/kpi",
            "GAP-KPI-PERFORMANCE-PAGE",
            "/api/kpi/values/summary",
        ],
        "frontend_route": "/kpi",
        "primary_api": "/api/kpi/values/summary",
        "supporting_apis": [
            "/api/kpi/owners",
            "/api/kpi/metrics",
            "/api/kpi/values",
            "/api/kpi/values/batch",
            "/api/kpi/fetch_and_recalc",
            "/api/kpi/report",
        ],
        "contract_docs": [
            "docs/live_route_maturity.md",
            "docs/metric_dictionary.md",
        ],
        "truth_chain": [
            "docs/live_route_maturity.md marks /kpi as temporary-exception with page id GAP-KPI-PERFORMANCE-PAGE.",
            "docs/metric_dictionary.md registers MTR-KPI-001 as candidate and PAGE-CONTRACT-PENDING:/kpi, not formal approval.",
            "GET /api/kpi/owners selects active KPI owners from the governance SQL authority gate.",
            "GET /api/kpi/values/summary returns period total_score and metric summaries for a selected owner/year/period.",
            "GET /api/kpi/metrics, GET /api/kpi/values, and GET /api/kpi/report support the workbench view and export.",
            "POST/PUT/DELETE /api/kpi/metrics mutate metric definitions under kpi.metric write/delete permission.",
            "POST/PUT /api/kpi/values, POST /api/kpi/values/batch, and POST /api/kpi/fetch_and_recalc mutate values or recalculated scores under kpi.value write permission.",
            "frontend/src/features/kpi-performance/pages/KpiPerformancePage.tsx renders the KPI workbench and action controls.",
        ],
        "backend_touchpoints": [
            "backend/app/api/routes/kpi.py",
            "backend/app/services/kpi_service.py",
            "backend/app/services/kpi_workbench_service.py",
            "backend/app/repositories/kpi_repo.py",
            "backend/app/schemas/kpi.py",
            "backend/app/models/kpi.py",
        ],
        "frontend_touchpoints": [
            "frontend/src/api/kpiClient.ts",
            "frontend/src/api/contracts.ts",
            "frontend/src/features/kpi-performance/pages/KpiPerformancePage.tsx",
            "frontend/src/features/kpi-performance/components/MetricTable.tsx",
            "frontend/src/features/kpi-performance/components/MetricEditModal.tsx",
            "frontend/src/features/kpi-performance/components/MetricManageModal.tsx",
            "frontend/src/features/kpi-performance/components/BatchPasteModal.tsx",
            "frontend/src/features/kpi-performance/components/TracePanel.tsx",
            "frontend/src/router/routes.tsx",
            "frontend/src/mocks/navigation.ts",
        ],
        "test_touchpoints": [
            "tests/test_kpi_api.py",
            "tests/test_kpi_repo.py",
            "tests/test_write_route_auth_contract.py",
            "tests/test_live_route_page_contract_completeness.py",
            "frontend/src/test/KpiPerformancePage.test.tsx",
            "frontend/src/test/KpiTracePanel.test.tsx",
            "frontend/src/test/RouteRegistry.test.tsx",
        ],
        "golden_samples": [],
        "verification_focus": [
            "No dedicated golden sample is currently registered for GAP-KPI-PERFORMANCE-PAGE; verify through live-route maturity, KPI API/repo tests, write-route auth tests, frontend route tests, and governance SQL/audit evidence.",
            "Trace /kpi through KpiPerformancePage, kpiClient, owner selection, period summary, metric table, trace panel, and action modals before changing display logic.",
            "Check owner_id, year, period_type, period_value, as_of_date, Decimal string fields, total_weight, total_score, null/empty states, and permissions before treating the page as ready.",
            "Verify write actions require kpi.metric or kpi.value permissions and that scoring recalculation does not imply metric dictionary approval, page approval, or business-owner signoff.",
        ],
        "guardrails": [
            "GAP-KPI-PERFORMANCE-PAGE is a candidate read/write scoring workbench; do not claim standalone formal KPI truth or business-owner closure.",
            "Do not promote KPI total_score, score_weight, progress_pct, completion_ratio, or scoring labels into approved MTR-* rows beyond the existing candidate MTR-KPI-001 without a dedicated PAGE contract, lineage, samples, and tests.",
            "Do not treat write operations, batch paste, fetch_and_recalc, CSV export, or scoring recomputation as approval of the KPI page or metric dictionary.",
            "Keep write/scoring permissions, source/trace panels, empty/error states, owner/year/period/as_of_date context, and Decimal string semantics visible.",
            "Do not backfill missing KPI owners, metrics, values, or score traces with static demo values in real mode.",
        ],
    }
    reports_home_bundle = module_home_bundle(
        page_slug="reports-home",
        page_id="PAGE-REPORTS-HOME-001",
        page_name="Reports And Data Home",
        frontend_route="/reports",
        kind="governance",
        downstream_pages=["/platform-config", "/cube-query"],
        supporting_apis=[
            "/health/live",
            "/health",
            "/ui/preview/source-foundation",
            "/api/cube/dimensions/bond_analytics",
        ],
        backend_touchpoints=[
            "backend/app/api/routes/health.py",
            "backend/app/api/routes/source_preview.py",
            "backend/app/api/routes/cube_query.py",
        ],
        truth_detail="Reports/data module home aggregates health, source preview, cube capability, and report-planning status only to guide data governance drilldown.",
        guardrail_detail="Do not convert diagnostics, source preview, cube capability, or planned reports into data-quality approval.",
    )

    bundles = [
        product_category_bundle,
        dashboard_home_bundle,
        executive_overview_bundle,
        executive_summary_bundle,
        balance_analysis_bundle,
        average_balance_bundle,
        decision_items_bundle,
        balance_movement_analysis_bundle,
        pnl_bundle,
        ledger_pnl_bundle,
        pnl_by_business_bundle,
        executive_pnl_attribution_bundle,
        pnl_attribution_workbench_bundle,
        operations_analysis_bundle,
        liability_analytics_bundle,
        pnl_bridge_bundle,
        risk_tensor_bundle,
        bond_dashboard_bundle,
        bond_analysis_bundle,
        positions_bundle,
        market_data_bundle,
        cross_asset_bundle,
        stock_analysis_bundle,
        macro_toolkit_bundle,
        macro_observation_bundle,
        agent_bundle,
        cube_query_bundle,
        portfolio_home_bundle,
        market_home_bundle,
        risk_home_bundle,
        performance_home_bundle,
        kpi_performance_bundle,
        reports_home_bundle,
    ]
    return {
        alias.casefold(): bundle
        for bundle in bundles
        for alias in bundle["aliases"]
    }


def page_trace_bundle(bundles: dict[str, dict[str, Any]], page_slug: str) -> dict[str, Any]:
    if not page_slug:
        raise McpError(-32602, "page_slug is required.")
    bundle = bundles.get(page_slug.casefold())
    if bundle is None:
        supported = sorted({bundle["page_slug"] for bundle in bundles.values()})
        raise McpError(-32602, f"Unknown page_slug: {page_slug}. Supported pages: {', '.join(supported)}")
    return bundle


def page_evidence_readiness(bundles: dict[str, dict[str, Any]], page_slugs: list[str]) -> dict[str, Any]:
    selected_slugs = page_slugs or DEFAULT_EVIDENCE_READINESS_PAGES
    pages = [page_evidence_readiness_row(page_trace_bundle(bundles, page_slug)) for page_slug in selected_slugs]
    formal_count = sum(1 for page in pages if page["formal_use_allowed"])
    review_required_count = sum(
        1 for page in pages if page["checks"]["catalog_date"]["status"] == "direct_review_required"
    )
    return {
        "scope": "page-trace-readiness",
        "disclaimer": (
            "This matrix summarizes seeded page trace-bundle anchors only; it does not prove live catalog, date, "
            "lineage, or formal metric approval. Use moss-lineage-evidence, moss-data-catalog, and "
            "moss-data-quality for direct proof before changing business metric semantics."
        ),
        "pages": pages,
        "candidate_metric_watchlist": CANDIDATE_METRIC_WATCHLIST,
        "summary": {
            "page_count": len(pages),
            "formal_use_allowed_count": formal_count,
            "candidate_or_gap_count": len(pages) - formal_count,
            "direct_catalog_date_review_required_count": review_required_count,
        },
    }


def page_catalog_date_evidence(
    bundles: dict[str, dict[str, Any]],
    duckdb_path: Path,
    page_slugs: list[str],
    *,
    limit: int,
) -> dict[str, Any]:
    if limit < 1 or limit > 200:
        raise McpError(-32602, "limit must be between 1 and 200.")
    selected_slugs = page_slugs or DEFAULT_EVIDENCE_READINESS_PAGES
    pages = [
        page_catalog_date_evidence_row(page_trace_bundle(bundles, page_slug), duckdb_path, limit=limit)
        for page_slug in selected_slugs
    ]
    table_rows = [row for page in pages for row in page["table_evidence"]]
    present_count = sum(1 for row in table_rows if row["status"] in {"present", "present_no_date_column"})
    sampled_count = sum(1 for row in table_rows if row["status"] == "present" and row["available_dates"])
    return {
        "scope": "page-catalog-date-evidence",
        "disclaimer": (
            "This tool samples configured DuckDB table and date-column evidence only; it does not prove page "
            "execution, governance lineage, metric definition, or formal approval."
        ),
        "duckdb_path": str(duckdb_path),
        "duckdb_exists": duckdb_path.is_file(),
        "pages": pages,
        "summary": {
            "page_count": len(pages),
            "table_anchor_count": len(table_rows),
            "present_table_count": present_count,
            "date_sampled_table_count": sampled_count,
        },
    }


def page_catalog_date_coverage(
    bundles: dict[str, dict[str, Any]],
    page_slugs: list[str],
) -> dict[str, Any]:
    selected_bundles = selected_catalog_date_page_bundles(bundles, page_slugs)
    pages = [page_catalog_date_coverage_row(bundle) for bundle in selected_bundles]
    page_order = {page["page_id"]: index for index, page in enumerate(pages)}
    missing_queue = [
        page for page in pages if page["coverage_status"] == "missing_explicit_table_config"
    ]
    deferred_queue = [
        page for page in pages if page["coverage_status"] == "deferred_no_direct_table_config"
    ]
    missing_queue.sort(key=lambda page: page_catalog_date_coverage_sort_key(page, page_order))
    deferred_queue.sort(key=lambda page: page_catalog_date_coverage_sort_key(page, page_order))
    return {
        "scope": "page-catalog-date-coverage",
        "disclaimer": (
            "This tool reports explicit catalog/date table configuration coverage only; it does not sample "
            "DuckDB tables, does not prove lineage or page/API execution, and does not approve metric/page formal use."
        ),
        "pages": pages,
        "missing_config_queue": missing_queue,
        "deferred_config_queue": deferred_queue,
        "summary": {
            "page_count": len(pages),
            "configured_page_count": sum(
                1 for page in pages if page["coverage_status"] == "configured_direct_tables"
            ),
            "deferred_no_direct_table_config_count": len(deferred_queue),
            "missing_explicit_config_count": len(missing_queue),
            "formal_missing_explicit_config_count": sum(
                1 for page in missing_queue if page["approval_status"] == "formal_or_governed"
            ),
        },
    }


def page_catalog_date_lineage_review_queue(
    bundles: dict[str, dict[str, Any]],
    page_slugs: list[str],
    *,
    streams: dict[str, Path] | None = None,
    stream_names: list[str] | None = None,
) -> dict[str, Any]:
    selected_bundles = selected_catalog_date_page_bundles(bundles, page_slugs)
    coverage_rows = [page_catalog_date_coverage_row(bundle) for bundle in selected_bundles]
    bundle_by_page_id = {str(bundle["page_id"]): bundle for bundle in selected_bundles}
    page_order = {str(row["page_id"]): index for index, row in enumerate(coverage_rows)}
    record_readiness_by_page_id = page_catalog_date_lineage_record_readiness_by_page_id(
        bundles,
        [str(bundle["page_slug"]) for bundle in selected_bundles],
        streams=streams,
        stream_names=stream_names,
    )
    queue_rows = [
        page_catalog_date_lineage_review_queue_item(
            row,
            bundle_by_page_id[str(row["page_id"])],
            record_readiness=record_readiness_by_page_id.get(str(row["page_id"])),
        )
        for row in coverage_rows
    ]
    review_queue = [
        row
        for row in queue_rows
        if row["review_lane"] != "deferred_no_direct_table_config_review"
    ]
    deferred_queue = [
        row
        for row in queue_rows
        if row["review_lane"] == "deferred_no_direct_table_config_review"
    ]
    review_queue.sort(key=lambda row: page_catalog_date_lineage_review_queue_sort_key(row, page_order))
    deferred_queue.sort(key=lambda row: page_catalog_date_lineage_review_queue_sort_key(row, page_order))
    record_remediation_work_items = page_catalog_date_lineage_record_remediation_work_items(queue_rows)
    record_remediation_evidence_work_items = page_catalog_date_lineage_record_remediation_evidence_work_items(
        queue_rows,
    )
    record_remediation_review_lane_work_items = (
        page_catalog_date_lineage_record_remediation_review_lane_work_items(queue_rows)
    )
    suggested_tool_call_work_items = page_catalog_date_lineage_suggested_tool_call_work_items(
        queue_rows,
    )
    record_remediation_scope_audit = page_catalog_date_lineage_record_remediation_scope_audit(
        {
            "record_remediation_work_items": record_remediation_work_items,
            "record_remediation_evidence_work_items": record_remediation_evidence_work_items,
            "record_remediation_review_lane_work_items": record_remediation_review_lane_work_items,
        },
    )
    suggested_tool_call_scope_audit = page_catalog_date_lineage_suggested_tool_call_scope_audit(
        suggested_tool_call_work_items,
    )
    evidence_collection_execution_plan = page_catalog_date_lineage_evidence_collection_execution_plan(
        suggested_tool_call_work_items,
        suggested_tool_call_scope_audit,
    )
    evidence_collection_execution_plan_scope_audit = (
        page_catalog_date_lineage_evidence_collection_execution_plan_scope_audit(
            evidence_collection_execution_plan,
        )
    )
    record_gap_execution_plan = page_catalog_date_lineage_record_gap_execution_plan(
        record_remediation_work_items,
        record_remediation_evidence_work_items,
        record_remediation_review_lane_work_items,
        record_remediation_scope_audit,
    )
    record_gap_execution_plan_scope_audit = (
        page_catalog_date_lineage_record_gap_execution_plan_scope_audit(record_gap_execution_plan)
    )
    manual_audit_review_execution_plan = page_catalog_date_lineage_manual_audit_review_execution_plan(
        record_remediation_work_items,
    )
    manual_audit_review_execution_plan_scope_audit = (
        page_catalog_date_lineage_manual_audit_review_execution_plan_scope_audit(
            manual_audit_review_execution_plan,
        )
    )
    business_owner_approval_execution_plan = page_catalog_date_lineage_business_owner_approval_execution_plan(
        record_remediation_work_items,
    )
    business_owner_approval_execution_plan_scope_audit = (
        page_catalog_date_lineage_business_owner_approval_execution_plan_scope_audit(
            business_owner_approval_execution_plan,
        )
    )
    ready_for_audit_review_count = sum(
        1
        for row in queue_rows
        if row["record_readiness"]["audit_review_status"] == "ready_for_audit_review"
    )
    blocked_by_record_gaps_count = sum(
        1
        for row in queue_rows
        if row["record_readiness"]["audit_review_status"] == "blocked_by_record_gaps"
    )
    closure_blocker_work_items = page_catalog_date_lineage_closure_blocker_work_items(
        queue_rows,
        suggested_tool_call_work_items,
        execution_plans={
            "record_gap_execution_plan": record_gap_execution_plan,
            "evidence_collection_execution_plan": evidence_collection_execution_plan,
            "manual_audit_review_execution_plan": manual_audit_review_execution_plan,
            "business_owner_approval_execution_plan": business_owner_approval_execution_plan,
        },
        source_work_item_group_counts={
            "record_remediation_work_items": len(record_remediation_work_items),
            "record_remediation_evidence_work_items": len(record_remediation_evidence_work_items),
            "record_remediation_review_lane_work_items": len(record_remediation_review_lane_work_items),
            "suggested_tool_call_work_items": len(suggested_tool_call_work_items),
        },
        record_remediation_work_item_count=record_remediation_scope_audit["work_item_count"],
        suggested_tool_call_work_item_count=suggested_tool_call_scope_audit["work_item_count"],
    )
    closure_blocker_work_item_breakdown = page_catalog_date_lineage_closure_blocker_work_item_breakdown(
        closure_blocker_work_items,
    )
    closure_blocker_routing_index = page_catalog_date_lineage_closure_blocker_routing_index(
        closure_blocker_work_items,
    )
    closure_blocker_scope_audit = page_catalog_date_lineage_closure_blocker_scope_audit(
        closure_blocker_work_items,
    )
    closure_readiness = page_catalog_date_lineage_closure_readiness(
        page_count=len(queue_rows),
        ready_for_audit_review_count=ready_for_audit_review_count,
        blocked_by_record_gaps_count=blocked_by_record_gaps_count,
        record_remediation_work_item_count=record_remediation_scope_audit["work_item_count"],
        suggested_tool_call_work_item_count=suggested_tool_call_scope_audit["work_item_count"],
        closure_blocker_work_item_count=len(closure_blocker_work_items),
        closure_blocker_work_item_breakdown=closure_blocker_work_item_breakdown,
        closure_blocker_routing_index=closure_blocker_routing_index,
        queue_boundary_work_item_count=0,
        execution_plans={
            "record_gap_execution_plan": record_gap_execution_plan,
            "evidence_collection_execution_plan": evidence_collection_execution_plan,
            "manual_audit_review_execution_plan": manual_audit_review_execution_plan,
            "business_owner_approval_execution_plan": business_owner_approval_execution_plan,
        },
    )
    queue_boundary_audit = page_catalog_date_lineage_queue_boundary_audit(
        {
            "record_gap_execution_plan_scope_audit": record_gap_execution_plan_scope_audit,
            "record_remediation_scope_audit": record_remediation_scope_audit,
            "suggested_tool_call_scope_audit": suggested_tool_call_scope_audit,
            "evidence_collection_execution_plan_scope_audit": evidence_collection_execution_plan_scope_audit,
            "manual_audit_review_execution_plan_scope_audit": manual_audit_review_execution_plan_scope_audit,
            "business_owner_approval_execution_plan_scope_audit": business_owner_approval_execution_plan_scope_audit,
            "closure_blocker_scope_audit": closure_blocker_scope_audit,
            "next_closure_action_scope_audit": closure_readiness[
                "next_closure_action_scope_audit"
            ],
            "closure_dispatch_packet_scope_audit": closure_readiness[
                "closure_dispatch_packet_scope_audit"
            ],
        },
    )
    closure_readiness["queue_boundary_work_item_count"] = queue_boundary_audit["work_item_count"]
    return {
        "scope": "page-catalog-date-lineage-review-queue",
        "disclaimer": (
            "This read-only queue routes catalog/date plus lineage evidence collection; it does not sample DuckDB "
            "tables, does not prove lineage or page/API execution, and does not approve metric/page formal use."
        ),
        "review_queue": review_queue,
        "deferred_review_queue": deferred_queue,
        "review_lane_breakdown": page_catalog_date_lineage_review_lane_breakdown(queue_rows),
        "record_remediation_breakdown": page_catalog_date_lineage_record_remediation_breakdown(queue_rows),
        "record_remediation_work_items": record_remediation_work_items,
        "record_remediation_evidence_work_items": record_remediation_evidence_work_items,
        "record_remediation_review_lane_work_items": record_remediation_review_lane_work_items,
        "record_gap_execution_plan": record_gap_execution_plan,
        "record_gap_execution_plan_scope_audit": record_gap_execution_plan_scope_audit,
        "record_remediation_scope_audit": record_remediation_scope_audit,
        "suggested_tool_call_work_items": suggested_tool_call_work_items,
        "suggested_tool_call_scope_audit": suggested_tool_call_scope_audit,
        "evidence_collection_execution_plan": evidence_collection_execution_plan,
        "evidence_collection_execution_plan_scope_audit": evidence_collection_execution_plan_scope_audit,
        "manual_audit_review_execution_plan": manual_audit_review_execution_plan,
        "manual_audit_review_execution_plan_scope_audit": manual_audit_review_execution_plan_scope_audit,
        "business_owner_approval_execution_plan": business_owner_approval_execution_plan,
        "business_owner_approval_execution_plan_scope_audit": business_owner_approval_execution_plan_scope_audit,
        "queue_boundary_audit": queue_boundary_audit,
        "closure_blocker_work_items": closure_blocker_work_items,
        "closure_blocker_routing_index": closure_blocker_routing_index,
        "closure_blocker_scope_audit": closure_blocker_scope_audit,
        "summary": {
            "page_count": len(queue_rows),
            "review_item_count": len(review_queue),
            "deferred_review_item_count": len(deferred_queue),
            "p1_review_item_count": sum(1 for row in review_queue if row["review_priority"] == "P1"),
            "gap_or_observational_review_item_count": sum(
                1
                for row in review_queue
                if row["review_lane"] == "gap_observational_separate_review"
            ),
            "ready_for_audit_review_count": ready_for_audit_review_count,
            "blocked_by_record_gaps_count": blocked_by_record_gaps_count,
            "closure_readiness": closure_readiness,
        },
    }


def page_catalog_date_lineage_closure_readiness(
    *,
    page_count: int,
    ready_for_audit_review_count: int,
    blocked_by_record_gaps_count: int,
    record_remediation_work_item_count: int,
    suggested_tool_call_work_item_count: int,
    closure_blocker_work_item_count: int,
    closure_blocker_work_item_breakdown: dict[str, dict[str, int]],
    closure_blocker_routing_index: dict[str, dict[str, Any]],
    queue_boundary_work_item_count: int,
    execution_plans: dict[str, dict[str, Any]] | None = None,
) -> dict[str, Any]:
    residual_requirements = []
    if blocked_by_record_gaps_count:
        residual_requirements.append("record_gap_remediation")
    if suggested_tool_call_work_item_count:
        residual_requirements.append("catalog_date_lineage_evidence_collection")
    if ready_for_audit_review_count:
        residual_requirements.append("manual_audit_review")
        residual_requirements.append("business_owner_approval")

    closure_execution_sequence = page_catalog_date_lineage_closure_execution_sequence(
        residual_requirements,
        closure_blocker_work_item_breakdown,
        closure_blocker_routing_index,
        execution_plans or {},
    )
    closure_dispatch_packet = page_catalog_date_lineage_closure_dispatch_packet(
        closure_execution_sequence,
        status=page_catalog_date_lineage_closure_status(
            blocked_by_record_gaps_count=blocked_by_record_gaps_count,
            suggested_tool_call_work_item_count=suggested_tool_call_work_item_count,
            ready_for_audit_review_count=ready_for_audit_review_count,
        ),
    )
    next_closure_action = page_catalog_date_lineage_next_closure_action(
        closure_execution_sequence,
        execution_plans or {},
    )
    return {
        "page_count": page_count,
        "ready_for_audit_review_count": ready_for_audit_review_count,
        "blocked_by_record_gaps_count": blocked_by_record_gaps_count,
        "record_remediation_work_item_count": record_remediation_work_item_count,
        "suggested_tool_call_work_item_count": suggested_tool_call_work_item_count,
        "closure_blocker_work_item_count": closure_blocker_work_item_count,
        "closure_blocker_work_item_breakdown": closure_blocker_work_item_breakdown,
        "queue_boundary_work_item_count": queue_boundary_work_item_count,
        "closure_approved_count": 0,
        "closure_ready_count": 0,
        "closure_blocked_count": page_count,
        "queue_grants_closure": False,
        "status": page_catalog_date_lineage_closure_status(
            blocked_by_record_gaps_count=blocked_by_record_gaps_count,
            suggested_tool_call_work_item_count=suggested_tool_call_work_item_count,
            ready_for_audit_review_count=ready_for_audit_review_count,
        ),
        "residual_closure_requirements": residual_requirements,
        "next_closure_action": next_closure_action,
        "next_closure_action_scope_audit": page_catalog_date_lineage_next_closure_action_scope_audit(
            next_closure_action,
            closure_execution_sequence=closure_execution_sequence,
        ),
        "closure_dispatch_packet": closure_dispatch_packet,
        "closure_dispatch_packet_scope_audit": (
            page_catalog_date_lineage_closure_dispatch_packet_scope_audit(
                closure_dispatch_packet,
                closure_execution_sequence=closure_execution_sequence,
            )
        ),
        "closure_execution_sequence": closure_execution_sequence,
    }


def page_catalog_date_lineage_closure_dispatch_packet(
    closure_execution_sequence: list[dict[str, Any]],
    *,
    status: str,
) -> dict[str, Any]:
    dispatch_steps = [
        page_catalog_date_lineage_closure_dispatch_step(step)
        for step in closure_execution_sequence
    ]
    return {
        "scope": "catalog_date_lineage_closure_dispatch_packet",
        "status": status,
        "dispatch_step_count": len(dispatch_steps),
        "next_dispatch_step": dispatch_steps[0] if dispatch_steps else None,
        "dispatch_steps": dispatch_steps,
        "writes_governance_records": False,
        "executes_tool_calls": False,
        "samples_duckdb_tables": False,
        "checks_lineage_records": False,
        "proves_page_execution": False,
        "runs_ui_or_api_smoke": False,
        "captures_business_owner_approval": False,
        "approves_metric_or_page": False,
        "queue_grants_closure": False,
    }


def page_catalog_date_lineage_closure_dispatch_step(
    closure_step: dict[str, Any],
) -> dict[str, Any]:
    return {
        "sequence": closure_step["sequence"],
        "blocker_type": closure_step["blocker_type"],
        "dispatch_action": closure_step["next_step"],
        "execution_plan": closure_step["execution_plan"],
        "execution_stage": closure_step["execution_stage"],
        "page_count": closure_step["page_count"],
        "work_item_count": closure_step["work_item_count"],
        "arguments": closure_step["arguments"],
        "execution_stage_detail": closure_step.get("execution_stage_detail"),
        "source_work_item_group_counts": closure_step.get("source_work_item_group_counts", {}),
        "must_complete_before": closure_step["must_complete_before"],
        "writes_governance_records": False,
        "executes_tool_calls": False,
        "samples_duckdb_tables": False,
        "checks_lineage_records": False,
        "proves_page_execution": False,
        "runs_ui_or_api_smoke": False,
        "captures_business_owner_approval": False,
        "approves_metric_or_page": False,
        "queue_grants_closure": False,
    }


def page_catalog_date_lineage_closure_dispatch_packet_scope_audit(
    dispatch_packet: dict[str, Any],
    *,
    closure_execution_sequence: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    scope_keys = [
        "writes_governance_records",
        "executes_tool_calls",
        "samples_duckdb_tables",
        "checks_lineage_records",
        "proves_page_execution",
        "runs_ui_or_api_smoke",
        "captures_business_owner_approval",
        "approves_metric_or_page",
        "queue_grants_closure",
    ]
    scope_flags = {key: False for key in scope_keys}
    scope_violations = []
    execution_target_violations = []
    packet_consistency_violations = []
    source_consistency_violations = []
    dispatch_steps = dispatch_packet.get("dispatch_steps", [])
    expected_dispatch_step_count = len(dispatch_steps)
    dispatch_step_count = dispatch_packet.get("dispatch_step_count")
    if dispatch_step_count != expected_dispatch_step_count:
        packet_consistency_violations.append(
            {
                "packet_key": "dispatch_step_count",
                "expected_key": "len(dispatch_steps)",
                "packet_value": dispatch_step_count,
                "expected_value": expected_dispatch_step_count,
            }
        )
    expected_next_dispatch_step = dispatch_steps[0] if dispatch_steps else None
    next_dispatch_step = dispatch_packet.get("next_dispatch_step")
    if next_dispatch_step != expected_next_dispatch_step:
        packet_consistency_violations.append(
            {
                "packet_key": "next_dispatch_step",
                "expected_key": "dispatch_steps[0]",
                "packet_value": next_dispatch_step,
                "expected_value": expected_next_dispatch_step,
            }
        )
    if closure_execution_sequence is not None and len(dispatch_steps) != len(
        closure_execution_sequence
    ):
        source_consistency_violations.append(
            {
                "work_item_group": "closure_dispatch_packet.dispatch_steps",
                "work_item_index": None,
                "packet_key": "len(dispatch_steps)",
                "expected_key": "len(closure_execution_sequence)",
                "packet_value": len(dispatch_steps),
                "expected_value": len(closure_execution_sequence),
            }
        )
        if len(dispatch_steps) < len(closure_execution_sequence):
            for missing_index in range(len(dispatch_steps), len(closure_execution_sequence)):
                source_consistency_violations.append(
                    {
                        "work_item_group": "closure_dispatch_packet.dispatch_steps",
                        "work_item_index": missing_index,
                        "packet_key": f"dispatch_steps[{missing_index}]",
                        "expected_key": f"closure_execution_sequence[{missing_index}]",
                        "packet_value": None,
                        "expected_value": closure_execution_sequence[missing_index],
                    }
                )
        else:
            for extra_index in range(len(closure_execution_sequence), len(dispatch_steps)):
                source_consistency_violations.append(
                    {
                        "work_item_group": "closure_dispatch_packet.dispatch_steps",
                        "work_item_index": extra_index,
                        "packet_key": f"dispatch_steps[{extra_index}]",
                        "expected_key": f"closure_execution_sequence[{extra_index}]",
                        "packet_value": dispatch_steps[extra_index],
                        "expected_value": None,
                    }
                )
    for index, step in enumerate(dispatch_steps):
        blocker_type = str(step.get("blocker_type") or "") if isinstance(step, dict) else ""
        expected_sequence = index + 1
        sequence = step.get("sequence") if isinstance(step, dict) else None
        if sequence != expected_sequence:
            packet_consistency_violations.append(
                {
                    "packet_key": f"dispatch_steps[{index}].sequence",
                    "expected_key": "1-based dispatch step index",
                    "packet_value": sequence,
                    "expected_value": expected_sequence,
                }
            )
        expected_source_step = (
            closure_execution_sequence[index]
            if closure_execution_sequence is not None
            and index < len(closure_execution_sequence)
            else None
        )
        if isinstance(expected_source_step, dict) and isinstance(step, dict):
            source_key_map = {
                "sequence": "sequence",
                "blocker_type": "blocker_type",
                "dispatch_action": "next_step",
                "execution_plan": "execution_plan",
                "execution_stage": "execution_stage",
                "execution_stage_detail": "execution_stage_detail",
                "page_count": "page_count",
                "work_item_count": "work_item_count",
                "arguments": "arguments",
                "source_work_item_group_counts": "source_work_item_group_counts",
                "must_complete_before": "must_complete_before",
            }
            for packet_key, source_key in source_key_map.items():
                packet_value = step.get(packet_key)
                expected_value = expected_source_step.get(source_key)
                if packet_value != expected_value:
                    source_consistency_violations.append(
                        {
                            "work_item_group": "closure_dispatch_packet.dispatch_steps",
                            "work_item_index": index,
                            "packet_key": f"dispatch_steps[{index}].{packet_key}",
                            "expected_key": (
                                f"closure_execution_sequence[{index}].{source_key}"
                            ),
                            "packet_value": packet_value,
                            "expected_value": expected_value,
                        }
                    )
        try:
            expected_plan, expected_stage, expected_action = (
                page_catalog_date_lineage_closure_execution_target(blocker_type)
            )
        except KeyError:
            expected_plan = None
            expected_stage = None
            expected_action = None
        for target_key, expected_value in (
            ("execution_plan", expected_plan),
            ("execution_stage", expected_stage),
            ("dispatch_action", expected_action),
        ):
            target_value = step.get(target_key) if isinstance(step, dict) else None
            if target_value != expected_value:
                execution_target_violations.append(
                    {
                        "work_item_group": "closure_dispatch_packet.dispatch_steps",
                        "work_item_index": index,
                        "blocker_type": blocker_type,
                        "target_key": target_key,
                        "target_value": target_value,
                        "expected_value": expected_value,
                    }
                )
        stage_detail = step.get("execution_stage_detail") if isinstance(step, dict) else None
        stage_detail_stage_type = (
            stage_detail.get("stage_type")
            if isinstance(stage_detail, dict)
            else None
        )
        if stage_detail_stage_type != expected_stage:
            execution_target_violations.append(
                {
                    "work_item_group": "closure_dispatch_packet.dispatch_steps",
                    "work_item_index": index,
                    "blocker_type": blocker_type,
                    "target_key": "execution_stage_detail.stage_type",
                    "target_value": stage_detail_stage_type,
                    "expected_value": expected_stage,
                }
            )
        source_work_item_group_counts = (
            step.get("source_work_item_group_counts", {})
            if isinstance(step, dict)
            else {}
        )
        expected_stage_work_item_group = (
            next(iter(source_work_item_group_counts))
            if isinstance(source_work_item_group_counts, dict)
            and source_work_item_group_counts
            else None
        )
        stage_detail_work_item_group = (
            stage_detail.get("work_item_group")
            if isinstance(stage_detail, dict)
            else None
        )
        if stage_detail_work_item_group != expected_stage_work_item_group:
            execution_target_violations.append(
                {
                    "work_item_group": "closure_dispatch_packet.dispatch_steps",
                    "work_item_index": index,
                    "blocker_type": blocker_type,
                    "target_key": "execution_stage_detail.work_item_group",
                    "target_value": stage_detail_work_item_group,
                    "expected_value": expected_stage_work_item_group,
                }
            )
        for key in scope_keys:
            value = step.get(key) if isinstance(step, dict) else None
            if value is True:
                scope_flags[key] = True
            if value is not False:
                scope_violations.append(
                    {
                        "work_item_group": "closure_dispatch_packet.dispatch_steps",
                        "work_item_index": index,
                        "scope_key": key,
                        "scope_value": value,
                    }
                )
    for key in scope_keys:
        value = dispatch_packet.get(key)
        if value is True:
            scope_flags[key] = True
        if value is not False:
            scope_violations.append(
                {
                    "work_item_group": "closure_dispatch_packet",
                    "work_item_index": None,
                    "scope_key": key,
                    "scope_value": value,
                }
            )

    return {
        "work_item_count": len(dispatch_steps),
        "checked_work_item_group": "closure_dispatch_packet.dispatch_steps",
        "writes_governance_records": scope_flags["writes_governance_records"],
        "executes_tool_calls": scope_flags["executes_tool_calls"],
        "samples_duckdb_tables": scope_flags["samples_duckdb_tables"],
        "checks_lineage_records": scope_flags["checks_lineage_records"],
        "proves_page_execution": scope_flags["proves_page_execution"],
        "runs_ui_or_api_smoke": scope_flags["runs_ui_or_api_smoke"],
        "captures_business_owner_approval": scope_flags["captures_business_owner_approval"],
        "approves_metric_or_page": scope_flags["approves_metric_or_page"],
        "queue_grants_closure": scope_flags["queue_grants_closure"],
        "scope_violations": scope_violations,
        "execution_target_violations": execution_target_violations,
        "packet_consistency_violations": packet_consistency_violations,
        "source_consistency_violations": source_consistency_violations,
    }


def page_catalog_date_lineage_closure_execution_sequence(
    residual_requirements: list[str],
    closure_blocker_work_item_breakdown: dict[str, dict[str, int]],
    closure_blocker_routing_index: dict[str, dict[str, Any]],
    execution_plans: dict[str, dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    dependency_tail = {
        "record_gap_remediation": ["manual_audit_review", "business_owner_approval"],
        "catalog_date_lineage_evidence_collection": ["manual_audit_review", "business_owner_approval"],
        "manual_audit_review": ["business_owner_approval"],
        "business_owner_approval": [],
    }
    sequence = []
    for index, blocker_type in enumerate(residual_requirements, start=1):
        breakdown = closure_blocker_work_item_breakdown.get(blocker_type, {})
        routing = closure_blocker_routing_index.get(blocker_type, {})
        execution_plan, execution_stage, next_step = page_catalog_date_lineage_closure_execution_target(
            blocker_type,
        )
        sequence.append(
            {
                "sequence": index,
                "blocker_type": blocker_type,
                "next_step": next_step,
                "execution_plan": execution_plan,
                "execution_stage": execution_stage,
                "execution_stage_detail": page_catalog_date_lineage_execution_stage_detail(
                    execution_plans or {},
                    execution_plan,
                    execution_stage,
                ),
                "page_count": int(breakdown.get("page_count") or 0),
                "work_item_count": int(breakdown.get("work_item_count") or 0),
                "source_work_item_group_counts": routing.get("source_work_item_group_counts", {}),
                "arguments": routing.get("arguments", {}),
                "must_complete_before": dependency_tail[blocker_type],
                "queue_grants_closure": False,
            }
        )
    return sequence


def page_catalog_date_lineage_next_closure_action(
    closure_execution_sequence: list[dict[str, Any]],
    execution_plans: dict[str, dict[str, Any]] | None = None,
) -> dict[str, Any] | None:
    if not closure_execution_sequence:
        return None
    first_step = closure_execution_sequence[0]
    blocker_type = str(first_step["blocker_type"])
    execution_plan, execution_stage, next_step = page_catalog_date_lineage_closure_execution_target(
        blocker_type,
    )
    return {
        "blocker_type": blocker_type,
        "next_step": next_step,
        "execution_plan": execution_plan,
        "execution_stage": execution_stage,
        "execution_stage_detail": first_step.get("execution_stage_detail")
        or page_catalog_date_lineage_execution_stage_detail(
            execution_plans or {},
            execution_plan,
            execution_stage,
        ),
        "page_count": first_step["page_count"],
        "work_item_count": first_step["work_item_count"],
        "arguments": first_step["arguments"],
        "must_complete_before": first_step["must_complete_before"],
        **page_catalog_date_lineage_closure_work_item_scope(),
    }


def page_catalog_date_lineage_next_closure_action_scope_audit(
    next_closure_action: dict[str, Any] | None,
    *,
    closure_execution_sequence: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    scope_keys = [
        "writes_governance_records",
        "executes_tool_calls",
        "samples_duckdb_tables",
        "checks_lineage_records",
        "proves_page_execution",
        "runs_ui_or_api_smoke",
        "captures_business_owner_approval",
        "approves_metric_or_page",
        "queue_grants_closure",
    ]
    scope_flags = {key: False for key in scope_keys}
    scope_violations = []
    execution_target_violations = []
    source_consistency_violations = []
    expected_first_step = (
        closure_execution_sequence[0]
        if closure_execution_sequence
        else None
    )
    if next_closure_action is None:
        if expected_first_step is not None:
            source_consistency_violations.append(
                {
                    "work_item_group": "closure_readiness.next_closure_action",
                    "work_item_index": None,
                    "action_key": "next_closure_action",
                    "expected_key": "closure_execution_sequence[0]",
                    "action_value": None,
                    "expected_value": expected_first_step,
                }
            )
        return {
            "work_item_count": 0,
            "checked_work_item_group": "closure_readiness.next_closure_action",
            "writes_governance_records": False,
            "executes_tool_calls": False,
            "samples_duckdb_tables": False,
            "checks_lineage_records": False,
            "proves_page_execution": False,
            "runs_ui_or_api_smoke": False,
            "captures_business_owner_approval": False,
            "approves_metric_or_page": False,
            "queue_grants_closure": False,
            "scope_violations": [],
            "execution_target_violations": [],
            "source_consistency_violations": source_consistency_violations,
        }

    blocker_type = str(next_closure_action.get("blocker_type") or "")
    try:
        expected_plan, expected_stage, expected_step = page_catalog_date_lineage_closure_execution_target(
            blocker_type,
        )
    except KeyError:
        expected_plan = None
        expected_stage = None
        expected_step = None
    for target_key, expected_value in (
        ("execution_plan", expected_plan),
        ("execution_stage", expected_stage),
        ("next_step", expected_step),
    ):
        target_value = next_closure_action.get(target_key)
        if target_value != expected_value:
            execution_target_violations.append(
                {
                    "work_item_group": "closure_readiness.next_closure_action",
                    "work_item_index": None,
                    "blocker_type": blocker_type,
                    "target_key": target_key,
                    "target_value": target_value,
                    "expected_value": expected_value,
                }
            )
    stage_detail = next_closure_action.get("execution_stage_detail")
    stage_detail_stage_type = (
        stage_detail.get("stage_type")
        if isinstance(stage_detail, dict)
        else None
    )
    if stage_detail_stage_type != expected_stage:
        execution_target_violations.append(
            {
                "work_item_group": "closure_readiness.next_closure_action",
                "work_item_index": None,
                "blocker_type": blocker_type,
                "target_key": "execution_stage_detail.stage_type",
                "target_value": stage_detail_stage_type,
                "expected_value": expected_stage,
            }
        )
    expected_source_work_item_group = (
        next(iter(expected_first_step.get("source_work_item_group_counts", {})))
        if isinstance(expected_first_step, dict)
        and expected_first_step.get("source_work_item_group_counts")
        else None
    )
    stage_detail_work_item_group = (
        stage_detail.get("work_item_group")
        if isinstance(stage_detail, dict)
        else None
    )
    if stage_detail_work_item_group != expected_source_work_item_group:
        execution_target_violations.append(
            {
                "work_item_group": "closure_readiness.next_closure_action",
                "work_item_index": None,
                "blocker_type": blocker_type,
                "target_key": "execution_stage_detail.work_item_group",
                "target_value": stage_detail_work_item_group,
                "expected_value": expected_source_work_item_group,
            }
        )
    if expected_first_step is None:
        source_consistency_violations.append(
            {
                "work_item_group": "closure_readiness.next_closure_action",
                "work_item_index": None,
                "action_key": "next_closure_action",
                "expected_key": "closure_execution_sequence[0]",
                "action_value": next_closure_action,
                "expected_value": None,
            }
        )
    else:
        source_key_map = {
            "blocker_type": "blocker_type",
            "next_step": "next_step",
            "execution_plan": "execution_plan",
            "execution_stage": "execution_stage",
            "execution_stage_detail": "execution_stage_detail",
            "page_count": "page_count",
            "work_item_count": "work_item_count",
            "arguments": "arguments",
            "must_complete_before": "must_complete_before",
        }
        for action_key, source_key in source_key_map.items():
            action_value = next_closure_action.get(action_key)
            expected_value = expected_first_step.get(source_key)
            if action_value != expected_value:
                source_consistency_violations.append(
                    {
                        "work_item_group": "closure_readiness.next_closure_action",
                        "work_item_index": None,
                        "action_key": f"next_closure_action.{action_key}",
                        "expected_key": f"closure_execution_sequence[0].{source_key}",
                        "action_value": action_value,
                        "expected_value": expected_value,
                    }
                )

    for key in scope_keys:
        value = next_closure_action.get(key)
        if value is True:
            scope_flags[key] = True
        if value is not False:
            scope_violations.append(
                {
                    "work_item_group": "closure_readiness.next_closure_action",
                    "work_item_index": None,
                    "scope_key": key,
                    "scope_value": value,
                }
            )
    for key in scope_keys:
        if key == "queue_grants_closure":
            continue
        stage_detail_value = (
            stage_detail.get(key)
            if isinstance(stage_detail, dict)
            else None
        )
        if stage_detail_value is True:
            scope_flags[key] = True
        if stage_detail_value is not False:
            scope_violations.append(
                {
                    "work_item_group": "closure_readiness.next_closure_action.execution_stage_detail",
                    "work_item_index": None,
                    "scope_key": key,
                    "scope_value": stage_detail_value,
                }
            )

    return {
        "work_item_count": 1,
        "checked_work_item_group": "closure_readiness.next_closure_action",
        "writes_governance_records": scope_flags["writes_governance_records"],
        "executes_tool_calls": scope_flags["executes_tool_calls"],
        "samples_duckdb_tables": scope_flags["samples_duckdb_tables"],
        "checks_lineage_records": scope_flags["checks_lineage_records"],
        "proves_page_execution": scope_flags["proves_page_execution"],
        "runs_ui_or_api_smoke": scope_flags["runs_ui_or_api_smoke"],
        "captures_business_owner_approval": scope_flags["captures_business_owner_approval"],
        "approves_metric_or_page": scope_flags["approves_metric_or_page"],
        "queue_grants_closure": scope_flags["queue_grants_closure"],
        "scope_violations": scope_violations,
        "execution_target_violations": execution_target_violations,
        "source_consistency_violations": source_consistency_violations,
    }


def page_catalog_date_lineage_closure_execution_target(
    blocker_type: str,
) -> tuple[str, str, str]:
    return {
        "record_gap_remediation": (
            "record_gap_execution_plan",
            "remediation_type_batches",
            "use_record_gap_execution_plan",
        ),
        "catalog_date_lineage_evidence_collection": (
            "evidence_collection_execution_plan",
            "catalog_date_evidence_batches",
            "use_evidence_collection_execution_plan",
        ),
        "manual_audit_review": (
            "manual_audit_review_execution_plan",
            "audit_review_queue_batches",
            "use_manual_audit_review_execution_plan",
        ),
        "business_owner_approval": (
            "business_owner_approval_execution_plan",
            "owner_approval_request_batches",
            "use_business_owner_approval_execution_plan",
        ),
    }[blocker_type]


def page_catalog_date_lineage_execution_stage_detail(
    execution_plans: dict[str, dict[str, Any]],
    execution_plan: str,
    execution_stage: str,
) -> dict[str, Any] | None:
    for stage in execution_plans.get(execution_plan, {}).get("execution_stages", []):
        if str(stage.get("stage_type")) == execution_stage:
            return dict(stage)
    return None


def page_catalog_date_lineage_closure_status(
    *,
    blocked_by_record_gaps_count: int,
    suggested_tool_call_work_item_count: int,
    ready_for_audit_review_count: int,
) -> str:
    if blocked_by_record_gaps_count and suggested_tool_call_work_item_count:
        return "record_remediation_and_catalog_date_lineage_review_required"
    if blocked_by_record_gaps_count:
        return "record_remediation_required"
    if suggested_tool_call_work_item_count:
        return "catalog_date_lineage_review_required"
    if ready_for_audit_review_count:
        return "manual_audit_review_required"
    return "closure_not_granted_by_queue"


def page_catalog_date_lineage_closure_blocker_work_items(
    queue_rows: list[dict[str, Any]],
    suggested_tool_call_work_items: list[dict[str, Any]],
    *,
    execution_plans: dict[str, dict[str, Any]] | None = None,
    source_work_item_group_counts: dict[str, int],
    record_remediation_work_item_count: int,
    suggested_tool_call_work_item_count: int,
) -> list[dict[str, Any]]:
    execution_plans = execution_plans or {}
    blocked_rows = [
        row
        for row in queue_rows
        if row["record_readiness"]["audit_review_status"] == "blocked_by_record_gaps"
    ]
    blocked_page_ids = [
        str(row["page_id"]) for row in blocked_rows
    ]
    blocked_page_slugs = [
        str(row["page_slug"]) for row in blocked_rows
    ]
    ready_rows = [
        row
        for row in queue_rows
        if row["record_readiness"]["audit_review_status"] == "ready_for_audit_review"
    ]
    ready_page_ids = [
        str(row["page_id"]) for row in ready_rows
    ]
    ready_page_slugs = [
        str(row["page_slug"]) for row in ready_rows
    ]
    suggested_page_ids: list[str] = []
    suggested_page_slugs: list[str] = []
    for work_item in suggested_tool_call_work_items:
        page_ids = work_item.get("page_ids", [])
        page_slugs = work_item.get("page_slugs", [])
        for index, page_id in enumerate(page_ids):
            page_catalog_date_lineage_append_unique(suggested_page_ids, str(page_id))
            if index < len(page_slugs):
                page_catalog_date_lineage_append_unique(
                    suggested_page_slugs,
                    str(page_slugs[index]),
                )

    work_items = []
    if blocked_page_ids:
        execution_plan, execution_stage, next_step = page_catalog_date_lineage_closure_execution_target(
            "record_gap_remediation",
        )
        work_items.append(
            {
                "blocker_type": "record_gap_remediation",
                "next_step": next_step,
                "execution_plan": execution_plan,
                "execution_stage": execution_stage,
                "execution_stage_detail": page_catalog_date_lineage_execution_stage_detail(
                    execution_plans,
                    execution_plan,
                    execution_stage,
                ),
                "source_work_item_groups": [
                    "record_remediation_work_items",
                    "record_remediation_evidence_work_items",
                    "record_remediation_review_lane_work_items",
                ],
                "source_work_item_group_counts": {
                    "record_remediation_work_items": source_work_item_group_counts[
                        "record_remediation_work_items"
                    ],
                    "record_remediation_evidence_work_items": source_work_item_group_counts[
                        "record_remediation_evidence_work_items"
                    ],
                    "record_remediation_review_lane_work_items": source_work_item_group_counts[
                        "record_remediation_review_lane_work_items"
                    ],
                },
                "page_count": len(blocked_page_ids),
                "work_item_count": record_remediation_work_item_count,
                "page_ids": blocked_page_ids,
                "page_slugs": blocked_page_slugs,
                "arguments": {"page_slugs": blocked_page_slugs},
                **page_catalog_date_lineage_closure_work_item_scope(),
            }
        )
    if suggested_page_ids:
        execution_plan, execution_stage, next_step = page_catalog_date_lineage_closure_execution_target(
            "catalog_date_lineage_evidence_collection",
        )
        work_items.append(
            {
                "blocker_type": "catalog_date_lineage_evidence_collection",
                "next_step": next_step,
                "execution_plan": execution_plan,
                "execution_stage": execution_stage,
                "execution_stage_detail": page_catalog_date_lineage_execution_stage_detail(
                    execution_plans,
                    execution_plan,
                    execution_stage,
                ),
                "source_work_item_groups": ["suggested_tool_call_work_items"],
                "source_work_item_group_counts": {
                    "suggested_tool_call_work_items": source_work_item_group_counts[
                        "suggested_tool_call_work_items"
                    ],
                },
                "page_count": len(suggested_page_ids),
                "work_item_count": suggested_tool_call_work_item_count,
                "page_ids": suggested_page_ids,
                "page_slugs": suggested_page_slugs,
                "arguments": {"page_slugs": suggested_page_slugs},
                **page_catalog_date_lineage_closure_work_item_scope(),
            }
        )
    if ready_page_ids:
        execution_plan, execution_stage, next_step = page_catalog_date_lineage_closure_execution_target(
            "manual_audit_review",
        )
        work_items.append(
            {
                "blocker_type": "manual_audit_review",
                "next_step": next_step,
                "execution_plan": execution_plan,
                "execution_stage": execution_stage,
                "execution_stage_detail": page_catalog_date_lineage_execution_stage_detail(
                    execution_plans,
                    execution_plan,
                    execution_stage,
                ),
                "source_work_item_groups": ["record_remediation_work_items"],
                "source_work_item_group_counts": {
                    "record_remediation_work_items": source_work_item_group_counts[
                        "record_remediation_work_items"
                    ],
                },
                "page_count": len(ready_page_ids),
                "work_item_count": len(ready_page_ids),
                "page_ids": ready_page_ids,
                "page_slugs": ready_page_slugs,
                "arguments": {"page_slugs": ready_page_slugs},
                **page_catalog_date_lineage_closure_work_item_scope(),
            }
        )
        execution_plan, execution_stage, next_step = page_catalog_date_lineage_closure_execution_target(
            "business_owner_approval",
        )
        work_items.append(
            {
                "blocker_type": "business_owner_approval",
                "next_step": next_step,
                "execution_plan": execution_plan,
                "execution_stage": execution_stage,
                "execution_stage_detail": page_catalog_date_lineage_execution_stage_detail(
                    execution_plans,
                    execution_plan,
                    execution_stage,
                ),
                "source_work_item_groups": ["record_remediation_work_items"],
                "source_work_item_group_counts": {
                    "record_remediation_work_items": source_work_item_group_counts[
                        "record_remediation_work_items"
                    ],
                },
                "page_count": len(ready_page_ids),
                "work_item_count": len(ready_page_ids),
                "page_ids": ready_page_ids,
                "page_slugs": ready_page_slugs,
                "arguments": {"page_slugs": ready_page_slugs},
                **page_catalog_date_lineage_closure_work_item_scope(),
            }
        )
    return work_items


def page_catalog_date_lineage_closure_blocker_work_item_breakdown(
    work_items: list[dict[str, Any]],
) -> dict[str, dict[str, int]]:
    return {
        str(item["blocker_type"]): {
            "page_count": int(item.get("page_count") or 0),
            "work_item_count": int(item.get("work_item_count") or 0),
        }
        for item in work_items
    }


def page_catalog_date_lineage_closure_blocker_routing_index(
    work_items: list[dict[str, Any]],
) -> dict[str, dict[str, Any]]:
    return {
        str(item["blocker_type"]): {
            "next_step": item["next_step"],
            "execution_plan": item["execution_plan"],
            "execution_stage": item["execution_stage"],
            "execution_stage_detail": item.get("execution_stage_detail"),
            "page_count": int(item.get("page_count") or 0),
            "work_item_count": int(item.get("work_item_count") or 0),
            "source_work_item_group_counts": item.get("source_work_item_group_counts", {}),
            "arguments": item.get("arguments", {}),
            "queue_grants_closure": item.get("queue_grants_closure") is True,
        }
        for item in work_items
    }


def page_catalog_date_lineage_closure_work_item_scope() -> dict[str, bool]:
    return {
        "writes_governance_records": False,
        "executes_tool_calls": False,
        "samples_duckdb_tables": False,
        "checks_lineage_records": False,
        "proves_page_execution": False,
        "runs_ui_or_api_smoke": False,
        "captures_business_owner_approval": False,
        "approves_metric_or_page": False,
        "queue_grants_closure": False,
    }


def page_catalog_date_lineage_closure_blocker_scope_audit(
    work_items: list[dict[str, Any]],
) -> dict[str, Any]:
    scope_keys = [
        "writes_governance_records",
        "executes_tool_calls",
        "samples_duckdb_tables",
        "checks_lineage_records",
        "proves_page_execution",
        "runs_ui_or_api_smoke",
        "captures_business_owner_approval",
        "approves_metric_or_page",
        "queue_grants_closure",
    ]
    scope_flags = {key: False for key in scope_keys}
    scope_violations = []
    execution_target_violations = []
    for index, item in enumerate(work_items):
        blocker_type = str(item.get("blocker_type") or "")
        try:
            expected_plan, expected_stage, expected_step = page_catalog_date_lineage_closure_execution_target(
                blocker_type,
            )
        except KeyError:
            expected_plan = None
            expected_stage = None
            expected_step = None
        for target_key, expected_value in (
            ("execution_plan", expected_plan),
            ("execution_stage", expected_stage),
            ("next_step", expected_step),
        ):
            target_value = item.get(target_key)
            if target_value != expected_value:
                execution_target_violations.append(
                    {
                        "work_item_group": "closure_blocker_work_items",
                        "work_item_index": index,
                        "blocker_type": blocker_type,
                        "target_key": target_key,
                        "target_value": target_value,
                        "expected_value": expected_value,
                    }
                )
        stage_detail = item.get("execution_stage_detail")
        stage_detail_stage_type = (
            stage_detail.get("stage_type")
            if isinstance(stage_detail, dict)
            else None
        )
        if stage_detail_stage_type != expected_stage:
            execution_target_violations.append(
                {
                    "work_item_group": "closure_blocker_work_items",
                    "work_item_index": index,
                    "blocker_type": blocker_type,
                    "target_key": "execution_stage_detail.stage_type",
                    "target_value": stage_detail_stage_type,
                    "expected_value": expected_stage,
                }
            )
        source_work_item_groups = [
            str(group)
            for group in item.get("source_work_item_groups", [])
        ]
        expected_stage_work_item_group = (
            source_work_item_groups[0]
            if source_work_item_groups
            else None
        )
        stage_detail_work_item_group = (
            stage_detail.get("work_item_group")
            if isinstance(stage_detail, dict)
            else None
        )
        if stage_detail_work_item_group != expected_stage_work_item_group:
            execution_target_violations.append(
                {
                    "work_item_group": "closure_blocker_work_items",
                    "work_item_index": index,
                    "blocker_type": blocker_type,
                    "target_key": "execution_stage_detail.work_item_group",
                    "target_value": stage_detail_work_item_group,
                    "expected_value": expected_stage_work_item_group,
                }
            )
        for key in scope_keys:
            value = item.get(key)
            if value is True:
                scope_flags[key] = True
            if value is not False:
                scope_violations.append(
                    {
                        "work_item_group": "closure_blocker_work_items",
                        "work_item_index": index,
                        "scope_key": key,
                        "scope_value": value,
                    }
                )
        for key in scope_keys:
            if key == "queue_grants_closure":
                continue
            stage_detail_value = (
                stage_detail.get(key)
                if isinstance(stage_detail, dict)
                else None
            )
            if stage_detail_value is True:
                scope_flags[key] = True
            if stage_detail_value is not False:
                scope_violations.append(
                    {
                        "work_item_group": "closure_blocker_work_items.execution_stage_detail",
                        "work_item_index": index,
                        "scope_key": key,
                        "scope_value": stage_detail_value,
                    }
                )

    return {
        "work_item_count": len(work_items),
        "checked_work_item_group": "closure_blocker_work_items",
        "writes_governance_records": scope_flags["writes_governance_records"],
        "executes_tool_calls": scope_flags["executes_tool_calls"],
        "samples_duckdb_tables": scope_flags["samples_duckdb_tables"],
        "checks_lineage_records": scope_flags["checks_lineage_records"],
        "proves_page_execution": scope_flags["proves_page_execution"],
        "runs_ui_or_api_smoke": scope_flags["runs_ui_or_api_smoke"],
        "captures_business_owner_approval": scope_flags["captures_business_owner_approval"],
        "approves_metric_or_page": scope_flags["approves_metric_or_page"],
        "queue_grants_closure": scope_flags["queue_grants_closure"],
        "scope_violations": scope_violations,
        "execution_target_violations": execution_target_violations,
    }


def page_catalog_date_lineage_record_readiness_by_page_id(
    bundles: dict[str, dict[str, Any]],
    page_slugs: list[str],
    *,
    streams: dict[str, Path] | None,
    stream_names: list[str] | None,
) -> dict[str, dict[str, Any]]:
    if streams is None or stream_names is None:
        return {}
    checklist = page_governance_audit_review_checklist(
        bundles,
        streams,
        page_slugs,
        stream_names,
        max_results=20,
    )
    return {
        str(page["page_id"]): page_catalog_date_lineage_record_readiness(page)
        for page in checklist["pages"]
    }


def page_catalog_date_lineage_record_remediation_breakdown(
    queue_rows: list[dict[str, Any]],
) -> dict[str, dict[str, Any]]:
    breakdown: dict[str, dict[str, Any]] = {}
    for row in queue_rows:
        remediation_type = str(row["record_remediation"]["remediation_type"])
        group = breakdown.setdefault(
            remediation_type,
            {
                "item_count": 0,
                "page_ids": [],
            },
        )
        group["item_count"] += 1
        group["page_ids"].append(str(row["page_id"]))
    return dict(sorted(breakdown.items()))


def page_catalog_date_lineage_record_remediation_work_items(
    queue_rows: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    remediation_order = {
        "create_direct_record": 0,
        "repair_primary_page_anchor": 1,
        "complete_direct_record_fields": 2,
        "none": 3,
    }
    work_items_by_type: dict[str, dict[str, Any]] = {}
    for row in queue_rows:
        remediation = row["record_remediation"]
        remediation_type = str(remediation["remediation_type"])
        work_item = work_items_by_type.setdefault(
            remediation_type,
            {
                "remediation_type": remediation_type,
                "next_step": remediation["next_step"],
                "evidence_to_collect": list(remediation.get("evidence_to_collect", [])),
                "page_ids": [],
                "page_slugs": [],
                "arguments": {"page_slugs": []},
                "suggested_tool_calls": [],
                "approval_boundary": remediation["approval_boundary"],
                "writes_governance_records": False,
                "executes_tool_calls": False,
                "samples_duckdb_tables": False,
                "checks_lineage_records": False,
                "proves_page_execution": False,
                "runs_ui_or_api_smoke": False,
                "captures_business_owner_approval": False,
                "approves_metric_or_page": False,
            },
        )
        work_item["page_ids"].append(str(row["page_id"]))
        work_item["page_slugs"].append(str(row["page_slug"]))
        work_item["arguments"]["page_slugs"].append(str(row["page_slug"]))

    work_items = list(work_items_by_type.values())
    for work_item in work_items:
        work_item["work_item_count"] = len(work_item["page_ids"])
        if work_item["remediation_type"] == "none":
            work_item["suggested_tool_calls"] = page_catalog_date_lineage_ready_record_review_work_item_tool_calls(
                work_item["arguments"],
            )
        else:
            work_item["suggested_tool_calls"] = page_catalog_date_lineage_record_remediation_work_item_tool_calls(
                work_item["arguments"],
            )
        work_item["suggested_tool_call_count"] = len(work_item["suggested_tool_calls"])
        work_item["suggested_tool_names"] = [
            str(call["tool"]) for call in work_item["suggested_tool_calls"]
        ]
    work_items.sort(
        key=lambda item: (
            remediation_order.get(str(item["remediation_type"]), len(remediation_order)),
            str(item["remediation_type"]),
        )
    )
    return work_items


def page_catalog_date_lineage_record_gap_execution_plan(
    record_remediation_work_items: list[dict[str, Any]],
    record_remediation_evidence_work_items: list[dict[str, Any]],
    record_remediation_review_lane_work_items: list[dict[str, Any]],
    record_remediation_scope_audit: dict[str, Any],
) -> dict[str, Any]:
    stage_definitions = [
        {
            "stage_type": "remediation_type_batches",
            "work_item_group": "record_remediation_work_items",
            "work_items": record_remediation_work_items,
            "next_step": "batch_requirements_and_blueprint_collection_by_remediation_type",
            "must_complete_before": ["evidence_key_batches", "review_lane_batches"],
        },
        {
            "stage_type": "evidence_key_batches",
            "work_item_group": "record_remediation_evidence_work_items",
            "work_items": record_remediation_evidence_work_items,
            "next_step": "collect_missing_record_evidence_by_evidence_key",
            "must_complete_before": ["review_lane_batches"],
        },
        {
            "stage_type": "review_lane_batches",
            "work_item_group": "record_remediation_review_lane_work_items",
            "work_items": record_remediation_review_lane_work_items,
            "next_step": "assign_record_gap_batches_by_review_lane_priority",
            "must_complete_before": [],
        },
    ]
    stage_scope = page_catalog_date_lineage_record_gap_execution_stage_scope()
    execution_stages = []
    for index, definition in enumerate(stage_definitions, start=1):
        work_items = definition["work_items"]
        page_slugs = page_catalog_date_lineage_record_gap_work_item_page_slugs(work_items)
        execution_stages.append(
            {
                "stage": index,
                "stage_type": definition["stage_type"],
                "work_item_group": definition["work_item_group"],
                "work_item_count": len(work_items),
                "page_count": len(page_slugs),
                "record_gap_page_count": page_catalog_date_lineage_record_gap_page_count(work_items),
                "ready_manual_review_page_count": page_catalog_date_lineage_ready_manual_review_page_count(
                    work_items,
                ),
                "includes_ready_manual_review_pages": False,
                "suggested_tool_call_count": sum(
                    int(item.get("suggested_tool_call_count") or len(item.get("suggested_tool_calls", [])))
                    for item in work_items
                ),
                "arguments": {"page_slugs": page_slugs},
                "next_step": definition["next_step"],
                "uses_work_item_groups": [definition["work_item_group"]],
                "must_complete_before": definition["must_complete_before"],
                **stage_scope,
            }
        )

    record_gap_page_slugs = page_catalog_date_lineage_unique_work_item_page_slugs(
        [
            item
            for item in record_remediation_work_items
            if str(item.get("remediation_type")) != "none"
        ]
    )
    suggested_tool_names = []
    for item in record_remediation_work_items:
        for tool_name in item.get("suggested_tool_names", []):
            page_catalog_date_lineage_append_unique(suggested_tool_names, str(tool_name))
    return {
        "scope": "record_gap_remediation_dispatch_plan",
        "status": (
            "record_gap_remediation_required"
            if record_gap_page_slugs
            else "record_gap_remediation_not_required"
        ),
        "blocked_page_count": len(record_gap_page_slugs),
        "ready_manual_review_page_count": page_catalog_date_lineage_ready_manual_review_page_count(
            record_remediation_work_items,
        ),
        "execution_stage_count": len(execution_stages),
        "execution_stage_order": [stage["stage_type"] for stage in execution_stages],
        "work_item_group_counts": {
            "record_remediation_work_items": len(record_remediation_work_items),
            "record_remediation_evidence_work_items": len(record_remediation_evidence_work_items),
            "record_remediation_review_lane_work_items": len(record_remediation_review_lane_work_items),
        },
        "suggested_tool_call_count": int(record_remediation_scope_audit.get("suggested_tool_call_count") or 0),
        "suggested_tool_names": suggested_tool_names,
        "record_gap_arguments": {"page_slugs": record_gap_page_slugs},
        "execution_stages": execution_stages,
        **page_catalog_date_lineage_record_gap_execution_plan_scope(),
    }


def page_catalog_date_lineage_record_gap_execution_stage_scope() -> dict[str, bool]:
    return {
        "writes_governance_records": False,
        "executes_tool_calls": False,
        "samples_duckdb_tables": False,
        "checks_lineage_records": False,
        "proves_page_execution": False,
        "runs_ui_or_api_smoke": False,
        "captures_business_owner_approval": False,
        "approves_metric_or_page": False,
    }


def page_catalog_date_lineage_record_gap_execution_plan_scope() -> dict[str, bool]:
    return {
        **page_catalog_date_lineage_record_gap_execution_stage_scope(),
        "queue_grants_closure": False,
    }


def page_catalog_date_lineage_record_gap_execution_plan_scope_audit(
    execution_plan: dict[str, Any],
) -> dict[str, Any]:
    scope_keys = [
        "writes_governance_records",
        "executes_tool_calls",
        "samples_duckdb_tables",
        "checks_lineage_records",
        "proves_page_execution",
        "runs_ui_or_api_smoke",
        "captures_business_owner_approval",
        "approves_metric_or_page",
    ]
    scope_flags = {key: False for key in scope_keys}
    scope_violations = []
    stages = execution_plan.get("execution_stages", [])
    for index, item in enumerate(stages):
        for key in scope_keys:
            value = item.get(key) if isinstance(item, dict) else None
            if value is True:
                scope_flags[key] = True
            if value is not False:
                scope_violations.append(
                    {
                        "work_item_group": "record_gap_execution_plan.execution_stages",
                        "work_item_index": index,
                        "scope_key": key,
                        "scope_value": value,
                    }
                )

    queue_grants_closure = execution_plan.get("queue_grants_closure") is True
    if execution_plan.get("queue_grants_closure") is not False:
        scope_violations.append(
            {
                "work_item_group": "record_gap_execution_plan",
                "work_item_index": None,
                "scope_key": "queue_grants_closure",
                "scope_value": execution_plan.get("queue_grants_closure"),
            }
        )

    return {
        "work_item_count": len(stages),
        "checked_work_item_group": "record_gap_execution_plan.execution_stages",
        "writes_governance_records": scope_flags["writes_governance_records"],
        "executes_tool_calls": scope_flags["executes_tool_calls"],
        "samples_duckdb_tables": scope_flags["samples_duckdb_tables"],
        "checks_lineage_records": scope_flags["checks_lineage_records"],
        "proves_page_execution": scope_flags["proves_page_execution"],
        "runs_ui_or_api_smoke": scope_flags["runs_ui_or_api_smoke"],
        "captures_business_owner_approval": scope_flags["captures_business_owner_approval"],
        "approves_metric_or_page": scope_flags["approves_metric_or_page"],
        "queue_grants_closure": queue_grants_closure,
        "scope_violations": scope_violations,
    }


def page_catalog_date_lineage_unique_work_item_page_slugs(
    work_items: list[dict[str, Any]],
) -> list[str]:
    page_slugs: list[str] = []
    for item in work_items:
        for page_slug in item.get("page_slugs", []):
            page_catalog_date_lineage_append_unique(page_slugs, str(page_slug))
    return page_slugs


def page_catalog_date_lineage_record_gap_work_item_page_slugs(
    work_items: list[dict[str, Any]],
) -> list[str]:
    page_slugs: list[str] = []
    for item in work_items:
        if str(item.get("remediation_type")) == "none":
            continue
        for page_slug in item.get("page_slugs", []):
            page_catalog_date_lineage_append_unique(page_slugs, str(page_slug))
    return page_slugs


def page_catalog_date_lineage_record_gap_page_count(work_items: list[dict[str, Any]]) -> int:
    return len(page_catalog_date_lineage_record_gap_work_item_page_slugs(work_items))


def page_catalog_date_lineage_ready_manual_review_page_count(
    record_remediation_work_items: list[dict[str, Any]],
) -> int:
    page_slugs: list[str] = []
    for item in record_remediation_work_items:
        if str(item.get("remediation_type")) != "none":
            continue
        for page_slug in item.get("page_slugs", []):
            page_catalog_date_lineage_append_unique(page_slugs, str(page_slug))
    return len(page_slugs)


def page_catalog_date_lineage_record_remediation_work_item_tool_calls(
    arguments: dict[str, list[str]],
) -> list[dict[str, Any]]:
    return [
        {
            "tool": "moss-lineage-evidence.get_page_governance_record_requirements",
            "arguments": arguments,
        },
        {
            "tool": "moss-lineage-evidence.get_page_governance_record_blueprint_queue",
            "arguments": arguments,
        },
    ]


def page_catalog_date_lineage_ready_record_review_work_item_tool_calls(
    arguments: dict[str, list[str]],
) -> list[dict[str, Any]]:
    return [
        {
            "tool": "moss-lineage-evidence.get_page_governance_audit_review_queue",
            "arguments": arguments,
        },
        {
            "tool": "moss-lineage-evidence.get_page_governance_audit_evidence_packet_queue",
            "arguments": arguments,
        },
    ]


def page_catalog_date_lineage_record_remediation_evidence_work_items(
    queue_rows: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    remediation_order = {
        "create_direct_record": 0,
        "repair_primary_page_anchor": 1,
        "complete_direct_record_fields": 2,
    }
    work_items_by_key: dict[str, dict[str, Any]] = {}
    for row_index, row in enumerate(queue_rows):
        remediation = row["record_remediation"]
        remediation_type = str(remediation["remediation_type"])
        if remediation_type == "none":
            continue
        next_step = str(remediation["next_step"])
        for evidence_key in remediation.get("evidence_to_collect", []):
            key = str(evidence_key)
            work_item = work_items_by_key.setdefault(
                key,
                {
                    "evidence_key": key,
                    "pages": [],
                    "page_ids": [],
                    "page_slugs": [],
                    "arguments": {"page_slugs": []},
                    "remediation_types": set(),
                    "next_steps": set(),
                    "approval_boundary": "record_remediation_evidence_collection_only",
                    "writes_governance_records": False,
                    "executes_tool_calls": False,
                    "samples_duckdb_tables": False,
                    "checks_lineage_records": False,
                    "proves_page_execution": False,
                    "runs_ui_or_api_smoke": False,
                    "captures_business_owner_approval": False,
                    "approves_metric_or_page": False,
                    "_page_refs": [],
                },
            )
            work_item["remediation_types"].add(remediation_type)
            work_item["next_steps"].add(next_step)
            work_item["_page_refs"].append(
                {
                    "sort_key": (
                        remediation_order.get(remediation_type, len(remediation_order)),
                        row_index,
                    ),
                    "page_id": str(row["page_id"]),
                    "page_slug": str(row["page_slug"]),
                    "remediation_type": remediation_type,
                    "next_step": next_step,
                }
            )

    work_items = []
    for item in work_items_by_key.values():
        page_refs = sorted(item.pop("_page_refs"), key=lambda ref: ref["sort_key"])
        item["pages"] = [
            {
                "page_id": ref["page_id"],
                "page_slug": ref["page_slug"],
                "remediation_type": ref["remediation_type"],
                "next_step": ref["next_step"],
            }
            for ref in page_refs
        ]
        item["page_ids"] = [ref["page_id"] for ref in page_refs]
        item["page_slugs"] = [ref["page_slug"] for ref in page_refs]
        item["arguments"] = {"page_slugs": item["page_slugs"]}
        item["work_item_count"] = len(page_refs)
        item["remediation_types"] = sorted(item["remediation_types"])
        item["next_steps"] = sorted(item["next_steps"])
        work_items.append(item)
    return sorted(work_items, key=lambda item: str(item["evidence_key"]))


def page_catalog_date_lineage_record_remediation_review_lane_work_items(
    queue_rows: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    lane_order = [
        "formal_governed_catalog_date_lineage_review",
        "candidate_formal_source_mixed_review",
        "candidate_or_mixed_catalog_date_lineage_review",
        "gap_observational_separate_review",
        "deferred_no_direct_table_config_review",
    ]
    remediation_order = {
        "create_direct_record": 0,
        "repair_primary_page_anchor": 1,
        "complete_direct_record_fields": 2,
        "none": 3,
    }
    priority_order = {"P1": 0, "P2": 1}
    work_items_by_key: dict[tuple[str, str], dict[str, Any]] = {}
    for row in queue_rows:
        remediation = row["record_remediation"]
        review_lane = str(row["review_lane"])
        remediation_type = str(remediation["remediation_type"])
        key = (review_lane, remediation_type)
        work_item = work_items_by_key.setdefault(
            key,
            {
                "review_lane": review_lane,
                "remediation_type": remediation_type,
                "review_priority": str(row["review_priority"]),
                "page_ids": [],
                "page_slugs": [],
                "arguments": {"page_slugs": []},
                "next_steps": [],
                "evidence_to_collect": [],
                "approval_boundary": remediation["approval_boundary"],
                "writes_governance_records": False,
                "executes_tool_calls": False,
                "samples_duckdb_tables": False,
                "checks_lineage_records": False,
                "proves_page_execution": False,
                "runs_ui_or_api_smoke": False,
                "captures_business_owner_approval": False,
                "approves_metric_or_page": False,
            },
        )
        if priority_order.get(str(row["review_priority"]), 99) < priority_order.get(
            str(work_item["review_priority"]),
            99,
        ):
            work_item["review_priority"] = str(row["review_priority"])
        work_item["page_ids"].append(str(row["page_id"]))
        work_item["page_slugs"].append(str(row["page_slug"]))
        work_item["arguments"]["page_slugs"].append(str(row["page_slug"]))
        page_catalog_date_lineage_append_unique(work_item["next_steps"], str(remediation["next_step"]))
        for evidence_key in remediation.get("evidence_to_collect", []):
            page_catalog_date_lineage_append_unique(
                work_item["evidence_to_collect"],
                str(evidence_key),
            )

    work_items = list(work_items_by_key.values())
    for work_item in work_items:
        work_item["work_item_count"] = len(work_item["page_ids"])
    work_items.sort(
        key=lambda item: (
            lane_order.index(str(item["review_lane"]))
            if str(item["review_lane"]) in lane_order
            else len(lane_order),
            remediation_order.get(str(item["remediation_type"]), len(remediation_order)),
        )
    )
    return work_items


def page_catalog_date_lineage_append_unique(values: list[str], value: str) -> None:
    if value not in values:
        values.append(value)


def page_catalog_date_lineage_record_remediation_scope_audit(
    work_item_groups: list[dict[str, Any]] | dict[str, list[dict[str, Any]]],
) -> dict[str, Any]:
    if isinstance(work_item_groups, list):
        grouped_work_items = {"record_remediation_work_items": work_item_groups}
        checked_groups = ["record_remediation_work_items"]
    else:
        grouped_work_items = work_item_groups
        checked_groups = [
            "record_remediation_work_items",
            "record_remediation_evidence_work_items",
            "record_remediation_review_lane_work_items",
        ]
    scope_keys = [
        "writes_governance_records",
        "executes_tool_calls",
        "samples_duckdb_tables",
        "checks_lineage_records",
        "proves_page_execution",
        "runs_ui_or_api_smoke",
        "captures_business_owner_approval",
        "approves_metric_or_page",
    ]
    scope_flags = {key: False for key in scope_keys}
    scope_violations = []
    allowed_suggested_tools = [
        "moss-lineage-evidence.get_page_governance_record_requirements",
        "moss-lineage-evidence.get_page_governance_record_blueprint_queue",
        "moss-lineage-evidence.get_page_governance_audit_review_queue",
        "moss-lineage-evidence.get_page_governance_audit_evidence_packet_queue",
    ]
    allowed_suggested_tool_set = set(allowed_suggested_tools)
    suggested_tool_call_count = 0
    suggested_tool_call_violations = []
    work_item_count = 0
    for group in checked_groups:
        for index, item in enumerate(grouped_work_items.get(group, [])):
            work_item_count += 1
            for key in scope_keys:
                value = item.get(key)
                if value is True:
                    scope_flags[key] = True
                if value is not False:
                    scope_violations.append(
                        {
                            "work_item_group": group,
                            "work_item_index": index,
                            "scope_key": key,
                            "scope_value": value,
                        }
                    )
            for call_index, call in enumerate(item.get("suggested_tool_calls", [])):
                suggested_tool_call_count += 1
                tool = call.get("tool") if isinstance(call, dict) else None
                if tool not in allowed_suggested_tool_set:
                    suggested_tool_call_violations.append(
                        {
                            "work_item_group": group,
                            "work_item_index": index,
                            "suggested_tool_call_index": call_index,
                            "tool": tool,
                        }
                    )
    return {
        "work_item_count": work_item_count,
        "checked_work_item_groups": checked_groups,
        "writes_governance_records": scope_flags["writes_governance_records"],
        "executes_tool_calls": scope_flags["executes_tool_calls"],
        "samples_duckdb_tables": scope_flags["samples_duckdb_tables"],
        "checks_lineage_records": scope_flags["checks_lineage_records"],
        "proves_page_execution": scope_flags["proves_page_execution"],
        "runs_ui_or_api_smoke": scope_flags["runs_ui_or_api_smoke"],
        "captures_business_owner_approval": scope_flags["captures_business_owner_approval"],
        "approves_metric_or_page": scope_flags["approves_metric_or_page"],
        "suggested_tool_call_count": suggested_tool_call_count,
        "allowed_suggested_tools": allowed_suggested_tools,
        "suggested_tool_call_violations": suggested_tool_call_violations,
        "scope_violations": scope_violations,
    }


def page_catalog_date_lineage_record_readiness(page: dict[str, Any]) -> dict[str, Any]:
    return {
        "record_validation_status": page["record_validation_status"],
        "audit_review_status": page["audit_review_status"],
        "ready_record_count": page["ready_record_count"],
        "direct_record_count": page["direct_record_count"],
        "incomplete_record_count": page["incomplete_record_count"],
        "expanded_anchor_record_count": page["expanded_anchor_record_count"],
        "residual_gaps": page["residual_gaps"],
    }


def page_catalog_date_lineage_unknown_record_readiness() -> dict[str, Any]:
    return {
        "record_validation_status": "not_checked",
        "audit_review_status": "not_checked",
        "ready_record_count": 0,
        "direct_record_count": 0,
        "incomplete_record_count": 0,
        "expanded_anchor_record_count": 0,
        "residual_gaps": [
            "Direct governance-record readiness was not checked for this queue call.",
        ],
    }


def page_catalog_date_lineage_review_lane_breakdown(
    queue_rows: list[dict[str, Any]],
) -> dict[str, dict[str, Any]]:
    lane_order = [
        "formal_governed_catalog_date_lineage_review",
        "candidate_formal_source_mixed_review",
        "candidate_or_mixed_catalog_date_lineage_review",
        "gap_observational_separate_review",
        "deferred_no_direct_table_config_review",
    ]
    breakdown: dict[str, dict[str, Any]] = {}
    for lane in lane_order:
        lane_rows = [row for row in queue_rows if row["review_lane"] == lane]
        breakdown[lane] = {
            "item_count": len(lane_rows),
            "page_ids": [row["page_id"] for row in lane_rows],
        }
    return breakdown


def page_catalog_date_lineage_suggested_tool_call_work_items(
    queue_rows: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    lane_order = [
        "formal_governed_catalog_date_lineage_review",
        "candidate_formal_source_mixed_review",
        "candidate_or_mixed_catalog_date_lineage_review",
        "gap_observational_separate_review",
        "deferred_no_direct_table_config_review",
    ]
    lane_rank = {lane: index for index, lane in enumerate(lane_order)}
    work_items_by_key: dict[tuple[str, str], dict[str, Any]] = {}
    for row in queue_rows:
        review_lane = str(row["review_lane"])
        for call in row["suggested_tool_calls"]:
            tool_name = str(call["tool"])
            key = (review_lane, tool_name)
            work_item = work_items_by_key.setdefault(
                key,
                {
                    "review_lane": review_lane,
                    "tool": tool_name,
                    "review_priority": row["review_priority"],
                    "page_ids": [],
                    "page_slugs": [],
                    "arguments": {"page_slugs": []},
                    "executes_tool_call": False,
                    "samples_duckdb_tables": False,
                    "checks_lineage_records": False,
                    "proves_page_execution": False,
                    "approves_metric_or_page": False,
                },
            )
            work_item["page_ids"].append(row["page_id"])
            work_item["page_slugs"].append(row["page_slug"])
            work_item["arguments"]["page_slugs"].append(row["page_slug"])

    work_items = list(work_items_by_key.values())
    for work_item in work_items:
        work_item["work_item_count"] = len(work_item["page_ids"])
    work_items.sort(
        key=lambda item: (
            lane_rank.get(str(item["review_lane"]), len(lane_order)),
            str(item["tool"]),
        ),
    )
    return work_items


def page_catalog_date_lineage_suggested_tool_call_scope_audit(
    work_items: list[dict[str, Any]],
) -> dict[str, Any]:
    scope_keys = [
        "executes_tool_call",
        "samples_duckdb_tables",
        "checks_lineage_records",
        "proves_page_execution",
        "approves_metric_or_page",
    ]
    scope_flags = {key: False for key in scope_keys}
    scope_violations = []
    allowed_suggested_tools = [
        "moss-data-catalog.get_page_catalog_date_evidence",
        "moss-data-catalog.get_page_catalog_date_coverage",
        "moss-lineage-evidence.get_page_lineage_evidence",
        "moss-lineage-evidence.validate_page_governance_records",
        "moss-lineage-evidence.get_page_governance_gap_queue",
    ]
    allowed_suggested_tool_set = set(allowed_suggested_tools)
    suggested_tool_violations = []
    for index, item in enumerate(work_items):
        for key in scope_keys:
            value = item.get(key)
            if value is True:
                scope_flags[key] = True
            if value is not False:
                scope_violations.append(
                    {
                        "work_item_group": "suggested_tool_call_work_items",
                        "work_item_index": index,
                        "scope_key": key,
                        "scope_value": value,
                    }
                )
        tool = item.get("tool")
        if tool not in allowed_suggested_tool_set:
            suggested_tool_violations.append(
                {
                    "work_item_group": "suggested_tool_call_work_items",
                    "work_item_index": index,
                    "tool": tool,
                }
            )

    return {
        "work_item_count": len(work_items),
        "checked_work_item_group": "suggested_tool_call_work_items",
        "allowed_suggested_tools": allowed_suggested_tools,
        "executes_tool_call": scope_flags["executes_tool_call"],
        "samples_duckdb_tables": scope_flags["samples_duckdb_tables"],
        "checks_lineage_records": scope_flags["checks_lineage_records"],
        "proves_page_execution": scope_flags["proves_page_execution"],
        "approves_metric_or_page": scope_flags["approves_metric_or_page"],
        "suggested_tool_violations": suggested_tool_violations,
        "scope_violations": scope_violations,
    }


def page_catalog_date_lineage_evidence_collection_execution_plan(
    suggested_tool_call_work_items: list[dict[str, Any]],
    suggested_tool_call_scope_audit: dict[str, Any],
) -> dict[str, Any]:
    stage_definitions = [
        {
            "stage_type": "catalog_date_evidence_batches",
            "tool": "moss-data-catalog.get_page_catalog_date_evidence",
            "next_step": "collect_catalog_date_evidence_by_review_lane",
            "must_complete_before": [
                "lineage_evidence_batches",
                "governance_validation_batches",
            ],
        },
        {
            "stage_type": "lineage_evidence_batches",
            "tool": "moss-lineage-evidence.get_page_lineage_evidence",
            "next_step": "collect_lineage_evidence_by_review_lane",
            "must_complete_before": ["governance_validation_batches"],
        },
        {
            "stage_type": "governance_validation_batches",
            "tool": "moss-lineage-evidence.validate_page_governance_records",
            "next_step": "validate_governance_records_after_catalog_and_lineage_evidence",
            "must_complete_before": [],
        },
        {
            "stage_type": "deferred_catalog_date_coverage_batches",
            "tool": "moss-data-catalog.get_page_catalog_date_coverage",
            "next_step": "review_deferred_catalog_date_coverage_without_sampling",
            "must_complete_before": ["deferred_governance_gap_queue_batches"],
        },
        {
            "stage_type": "deferred_governance_gap_queue_batches",
            "tool": "moss-lineage-evidence.get_page_governance_gap_queue",
            "next_step": "review_deferred_governance_gap_queue_without_record_write",
            "must_complete_before": [],
        },
    ]
    stage_scope = page_catalog_date_lineage_evidence_collection_execution_stage_scope()
    execution_stages = []
    for index, definition in enumerate(stage_definitions, start=1):
        work_items = [
            item
            for item in suggested_tool_call_work_items
            if str(item.get("tool")) == definition["tool"]
        ]
        page_slugs = page_catalog_date_lineage_unique_work_item_page_slugs(work_items)
        execution_stages.append(
            {
                "stage": index,
                "stage_type": definition["stage_type"],
                "work_item_group": "suggested_tool_call_work_items",
                "tool": definition["tool"],
                "work_item_count": len(work_items),
                "page_count": len(page_slugs),
                "suggested_tool_call_count": len(work_items),
                "arguments": {"page_slugs": page_slugs},
                "next_step": definition["next_step"],
                "uses_work_item_groups": ["suggested_tool_call_work_items"],
                "must_complete_before": definition["must_complete_before"],
                **stage_scope,
            }
        )

    collection_page_slugs = page_catalog_date_lineage_unique_work_item_page_slugs(
        suggested_tool_call_work_items,
    )
    return {
        "scope": "catalog_date_lineage_evidence_collection_dispatch_plan",
        "status": (
            "catalog_date_lineage_evidence_collection_required"
            if suggested_tool_call_work_items
            else "catalog_date_lineage_evidence_collection_not_required"
        ),
        "page_count": len(collection_page_slugs),
        "execution_stage_count": len(execution_stages),
        "execution_stage_order": [stage["stage_type"] for stage in execution_stages],
        "work_item_group_counts": {
            "suggested_tool_call_work_items": len(suggested_tool_call_work_items),
        },
        "suggested_tool_call_count": int(suggested_tool_call_scope_audit.get("work_item_count") or 0),
        "collection_arguments": {"page_slugs": collection_page_slugs},
        "execution_stages": execution_stages,
        **page_catalog_date_lineage_evidence_collection_execution_plan_scope(),
    }


def page_catalog_date_lineage_evidence_collection_execution_stage_scope() -> dict[str, bool]:
    return {
        "writes_governance_records": False,
        "executes_tool_calls": False,
        "samples_duckdb_tables": False,
        "checks_lineage_records": False,
        "proves_page_execution": False,
        "runs_ui_or_api_smoke": False,
        "captures_business_owner_approval": False,
        "approves_metric_or_page": False,
    }


def page_catalog_date_lineage_evidence_collection_execution_plan_scope() -> dict[str, bool]:
    return {
        **page_catalog_date_lineage_evidence_collection_execution_stage_scope(),
        "queue_grants_closure": False,
    }


def page_catalog_date_lineage_evidence_collection_execution_plan_scope_audit(
    execution_plan: dict[str, Any],
) -> dict[str, Any]:
    scope_keys = [
        "writes_governance_records",
        "executes_tool_calls",
        "samples_duckdb_tables",
        "checks_lineage_records",
        "proves_page_execution",
        "runs_ui_or_api_smoke",
        "captures_business_owner_approval",
        "approves_metric_or_page",
    ]
    scope_flags = {key: False for key in scope_keys}
    scope_violations = []
    stages = execution_plan.get("execution_stages", [])
    for index, item in enumerate(stages):
        for key in scope_keys:
            value = item.get(key) if isinstance(item, dict) else None
            if value is True:
                scope_flags[key] = True
            if value is not False:
                scope_violations.append(
                    {
                        "work_item_group": "evidence_collection_execution_plan.execution_stages",
                        "work_item_index": index,
                        "scope_key": key,
                        "scope_value": value,
                    }
                )

    queue_grants_closure = execution_plan.get("queue_grants_closure") is True
    if execution_plan.get("queue_grants_closure") is not False:
        scope_violations.append(
            {
                "work_item_group": "evidence_collection_execution_plan",
                "work_item_index": None,
                "scope_key": "queue_grants_closure",
                "scope_value": execution_plan.get("queue_grants_closure"),
            }
        )

    return {
        "work_item_count": len(stages),
        "checked_work_item_group": "evidence_collection_execution_plan.execution_stages",
        "writes_governance_records": scope_flags["writes_governance_records"],
        "executes_tool_calls": scope_flags["executes_tool_calls"],
        "samples_duckdb_tables": scope_flags["samples_duckdb_tables"],
        "checks_lineage_records": scope_flags["checks_lineage_records"],
        "proves_page_execution": scope_flags["proves_page_execution"],
        "runs_ui_or_api_smoke": scope_flags["runs_ui_or_api_smoke"],
        "captures_business_owner_approval": scope_flags["captures_business_owner_approval"],
        "approves_metric_or_page": scope_flags["approves_metric_or_page"],
        "queue_grants_closure": queue_grants_closure,
        "scope_violations": scope_violations,
    }


def page_catalog_date_lineage_manual_audit_review_execution_plan(
    record_remediation_work_items: list[dict[str, Any]],
) -> dict[str, Any]:
    ready_work_items = [
        item
        for item in record_remediation_work_items
        if str(item.get("remediation_type")) == "none"
    ]
    stage_definitions = [
        {
            "stage_type": "audit_review_queue_batches",
            "tool": "moss-lineage-evidence.get_page_governance_audit_review_queue",
            "next_step": "collect_manual_audit_review_queue_without_approval",
            "must_complete_before": ["audit_evidence_packet_queue_batches"],
        },
        {
            "stage_type": "audit_evidence_packet_queue_batches",
            "tool": "moss-lineage-evidence.get_page_governance_audit_evidence_packet_queue",
            "next_step": "collect_manual_audit_evidence_packets_without_closure",
            "must_complete_before": [],
        },
    ]
    stage_scope = page_catalog_date_lineage_manual_audit_review_execution_stage_scope()
    execution_stages = []
    for index, definition in enumerate(stage_definitions, start=1):
        matching_work_items = [
            item
            for item in ready_work_items
            if any(call.get("tool") == definition["tool"] for call in item.get("suggested_tool_calls", []))
        ]
        page_slugs = page_catalog_date_lineage_unique_work_item_page_slugs(matching_work_items)
        execution_stages.append(
            {
                "stage": index,
                "stage_type": definition["stage_type"],
                "work_item_group": "record_remediation_work_items",
                "tool": definition["tool"],
                "work_item_count": len(matching_work_items),
                "page_count": len(page_slugs),
                "suggested_tool_call_count": len(matching_work_items),
                "arguments": {"page_slugs": page_slugs},
                "next_step": definition["next_step"],
                "uses_work_item_groups": ["record_remediation_work_items"],
                "must_complete_before": definition["must_complete_before"],
                **stage_scope,
            }
        )

    ready_page_slugs = page_catalog_date_lineage_unique_work_item_page_slugs(ready_work_items)
    suggested_tool_names: list[str] = []
    for item in ready_work_items:
        for tool_name in item.get("suggested_tool_names", []):
            page_catalog_date_lineage_append_unique(suggested_tool_names, str(tool_name))
    return {
        "scope": "manual_audit_review_dispatch_plan",
        "status": "manual_audit_review_required" if ready_page_slugs else "manual_audit_review_not_required",
        "ready_page_count": len(ready_page_slugs),
        "execution_stage_count": len(execution_stages),
        "execution_stage_order": [stage["stage_type"] for stage in execution_stages],
        "work_item_group_counts": {
            "record_remediation_work_items": len(ready_work_items),
        },
        "suggested_tool_call_count": sum(
            int(item.get("suggested_tool_call_count") or len(item.get("suggested_tool_calls", [])))
            for item in ready_work_items
        ),
        "suggested_tool_names": suggested_tool_names,
        "manual_review_arguments": {"page_slugs": ready_page_slugs},
        "execution_stages": execution_stages,
        **page_catalog_date_lineage_manual_audit_review_execution_plan_scope(),
    }


def page_catalog_date_lineage_manual_audit_review_execution_stage_scope() -> dict[str, bool]:
    return {
        "writes_governance_records": False,
        "executes_tool_calls": False,
        "samples_duckdb_tables": False,
        "checks_lineage_records": False,
        "proves_page_execution": False,
        "runs_ui_or_api_smoke": False,
        "captures_business_owner_approval": False,
        "approves_metric_or_page": False,
    }


def page_catalog_date_lineage_manual_audit_review_execution_plan_scope() -> dict[str, bool]:
    return {
        **page_catalog_date_lineage_manual_audit_review_execution_stage_scope(),
        "queue_grants_closure": False,
    }


def page_catalog_date_lineage_manual_audit_review_execution_plan_scope_audit(
    execution_plan: dict[str, Any],
) -> dict[str, Any]:
    scope_keys = [
        "writes_governance_records",
        "executes_tool_calls",
        "samples_duckdb_tables",
        "checks_lineage_records",
        "proves_page_execution",
        "runs_ui_or_api_smoke",
        "captures_business_owner_approval",
        "approves_metric_or_page",
    ]
    scope_flags = {key: False for key in scope_keys}
    scope_violations = []
    stages = execution_plan.get("execution_stages", [])
    for index, item in enumerate(stages):
        for key in scope_keys:
            value = item.get(key) if isinstance(item, dict) else None
            if value is True:
                scope_flags[key] = True
            if value is not False:
                scope_violations.append(
                    {
                        "work_item_group": "manual_audit_review_execution_plan.execution_stages",
                        "work_item_index": index,
                        "scope_key": key,
                        "scope_value": value,
                    }
                )

    queue_grants_closure = execution_plan.get("queue_grants_closure") is True
    if execution_plan.get("queue_grants_closure") is not False:
        scope_violations.append(
            {
                "work_item_group": "manual_audit_review_execution_plan",
                "work_item_index": None,
                "scope_key": "queue_grants_closure",
                "scope_value": execution_plan.get("queue_grants_closure"),
            }
        )

    return {
        "work_item_count": len(stages),
        "checked_work_item_group": "manual_audit_review_execution_plan.execution_stages",
        "writes_governance_records": scope_flags["writes_governance_records"],
        "executes_tool_calls": scope_flags["executes_tool_calls"],
        "samples_duckdb_tables": scope_flags["samples_duckdb_tables"],
        "checks_lineage_records": scope_flags["checks_lineage_records"],
        "proves_page_execution": scope_flags["proves_page_execution"],
        "runs_ui_or_api_smoke": scope_flags["runs_ui_or_api_smoke"],
        "captures_business_owner_approval": scope_flags["captures_business_owner_approval"],
        "approves_metric_or_page": scope_flags["approves_metric_or_page"],
        "queue_grants_closure": queue_grants_closure,
        "scope_violations": scope_violations,
    }


def page_catalog_date_lineage_business_owner_approval_execution_plan(
    record_remediation_work_items: list[dict[str, Any]],
) -> dict[str, Any]:
    ready_work_items = [
        item
        for item in record_remediation_work_items
        if str(item.get("remediation_type")) == "none"
    ]
    stage_definitions = [
        {
            "stage_type": "owner_approval_request_batches",
            "next_step": "prepare_owner_approval_request_after_manual_audit_review",
            "must_complete_before": ["owner_approval_receipt_review_batches"],
        },
        {
            "stage_type": "owner_approval_receipt_review_batches",
            "next_step": "review_external_owner_approval_receipt_without_granting_closure",
            "must_complete_before": [],
        },
    ]
    stage_scope = page_catalog_date_lineage_business_owner_approval_execution_stage_scope()
    ready_page_slugs = page_catalog_date_lineage_unique_work_item_page_slugs(ready_work_items)
    execution_stages = []
    for index, definition in enumerate(stage_definitions, start=1):
        execution_stages.append(
            {
                "stage": index,
                "stage_type": definition["stage_type"],
                "work_item_group": "record_remediation_work_items",
                "work_item_count": len(ready_work_items),
                "page_count": len(ready_page_slugs),
                "arguments": {"page_slugs": ready_page_slugs},
                "next_step": definition["next_step"],
                "uses_work_item_groups": ["record_remediation_work_items"],
                "must_complete_before": definition["must_complete_before"],
                **stage_scope,
            }
        )

    return {
        "scope": "business_owner_approval_dispatch_plan",
        "status": "business_owner_approval_required" if ready_page_slugs else "business_owner_approval_not_required",
        "ready_page_count": len(ready_page_slugs),
        "execution_stage_count": len(execution_stages),
        "execution_stage_order": [stage["stage_type"] for stage in execution_stages],
        "work_item_group_counts": {
            "record_remediation_work_items": len(ready_work_items),
        },
        "approval_arguments": {"page_slugs": ready_page_slugs},
        "execution_stages": execution_stages,
        **page_catalog_date_lineage_business_owner_approval_execution_plan_scope(),
    }


def page_catalog_date_lineage_business_owner_approval_execution_stage_scope() -> dict[str, bool]:
    return {
        "writes_governance_records": False,
        "executes_tool_calls": False,
        "samples_duckdb_tables": False,
        "checks_lineage_records": False,
        "proves_page_execution": False,
        "runs_ui_or_api_smoke": False,
        "captures_business_owner_approval": False,
        "approves_metric_or_page": False,
    }


def page_catalog_date_lineage_business_owner_approval_execution_plan_scope() -> dict[str, bool]:
    return {
        **page_catalog_date_lineage_business_owner_approval_execution_stage_scope(),
        "queue_grants_closure": False,
    }


def page_catalog_date_lineage_business_owner_approval_execution_plan_scope_audit(
    execution_plan: dict[str, Any],
) -> dict[str, Any]:
    scope_keys = [
        "writes_governance_records",
        "executes_tool_calls",
        "samples_duckdb_tables",
        "checks_lineage_records",
        "proves_page_execution",
        "runs_ui_or_api_smoke",
        "captures_business_owner_approval",
        "approves_metric_or_page",
    ]
    scope_flags = {key: False for key in scope_keys}
    scope_violations = []
    stages = execution_plan.get("execution_stages", [])
    for index, item in enumerate(stages):
        for key in scope_keys:
            value = item.get(key) if isinstance(item, dict) else None
            if value is True:
                scope_flags[key] = True
            if value is not False:
                scope_violations.append(
                    {
                        "work_item_group": "business_owner_approval_execution_plan.execution_stages",
                        "work_item_index": index,
                        "scope_key": key,
                        "scope_value": value,
                    }
                )

    queue_grants_closure = execution_plan.get("queue_grants_closure") is True
    if execution_plan.get("queue_grants_closure") is not False:
        scope_violations.append(
            {
                "work_item_group": "business_owner_approval_execution_plan",
                "work_item_index": None,
                "scope_key": "queue_grants_closure",
                "scope_value": execution_plan.get("queue_grants_closure"),
            }
        )

    return {
        "work_item_count": len(stages),
        "checked_work_item_group": "business_owner_approval_execution_plan.execution_stages",
        "writes_governance_records": scope_flags["writes_governance_records"],
        "executes_tool_calls": scope_flags["executes_tool_calls"],
        "samples_duckdb_tables": scope_flags["samples_duckdb_tables"],
        "checks_lineage_records": scope_flags["checks_lineage_records"],
        "proves_page_execution": scope_flags["proves_page_execution"],
        "runs_ui_or_api_smoke": scope_flags["runs_ui_or_api_smoke"],
        "captures_business_owner_approval": scope_flags["captures_business_owner_approval"],
        "approves_metric_or_page": scope_flags["approves_metric_or_page"],
        "queue_grants_closure": queue_grants_closure,
        "scope_violations": scope_violations,
    }


def page_catalog_date_lineage_queue_boundary_audit(
    scope_audits: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    checked_scope_audits = [
        "record_gap_execution_plan_scope_audit",
        "record_remediation_scope_audit",
        "suggested_tool_call_scope_audit",
        "evidence_collection_execution_plan_scope_audit",
        "manual_audit_review_execution_plan_scope_audit",
        "business_owner_approval_execution_plan_scope_audit",
        "closure_blocker_scope_audit",
        "next_closure_action_scope_audit",
        "closure_dispatch_packet_scope_audit",
    ]
    scope_flags = {
        "writes_governance_records": False,
        "executes_tool_calls": False,
        "samples_duckdb_tables": False,
        "checks_lineage_records": False,
        "proves_page_execution": False,
        "runs_ui_or_api_smoke": False,
        "captures_business_owner_approval": False,
        "approves_metric_or_page": False,
    }
    work_item_count = 0
    work_item_counts: dict[str, int] = {}
    queue_grants_closure = False
    scope_violations = []
    suggested_tool_violations = []
    execution_target_violations = []
    packet_consistency_violations = []
    source_consistency_violations = []
    for audit_name in checked_scope_audits:
        audit = scope_audits.get(audit_name, {})
        audit_work_item_count = int(audit.get("work_item_count") or 0)
        work_item_counts[audit_name] = audit_work_item_count
        work_item_count += audit_work_item_count
        if audit_name in {
            "record_gap_execution_plan_scope_audit",
            "record_remediation_scope_audit",
            "evidence_collection_execution_plan_scope_audit",
            "manual_audit_review_execution_plan_scope_audit",
            "business_owner_approval_execution_plan_scope_audit",
        }:
            for key in scope_flags:
                if audit.get(key) is True:
                    scope_flags[key] = True
            if audit.get("queue_grants_closure") is True:
                queue_grants_closure = True
            tool_violations = audit.get("suggested_tool_call_violations", [])
        elif audit_name == "suggested_tool_call_scope_audit":
            if audit.get("executes_tool_call") is True:
                scope_flags["executes_tool_calls"] = True
            for key in [
                "samples_duckdb_tables",
                "checks_lineage_records",
                "proves_page_execution",
                "approves_metric_or_page",
            ]:
                if audit.get(key) is True:
                    scope_flags[key] = True
            tool_violations = audit.get("suggested_tool_violations", [])
        else:
            for key in scope_flags:
                if audit.get(key) is True:
                    scope_flags[key] = True
            if audit.get("queue_grants_closure") is True:
                queue_grants_closure = True
            tool_violations = []
        for violation in audit.get("scope_violations", []):
            violation_with_source = dict(violation)
            violation_with_source["scope_audit"] = audit_name
            scope_violations.append(violation_with_source)
        for violation in tool_violations:
            violation_with_source = dict(violation)
            violation_with_source["scope_audit"] = audit_name
            suggested_tool_violations.append(violation_with_source)
        for violation in audit.get("execution_target_violations", []):
            violation_with_source = dict(violation)
            violation_with_source["scope_audit"] = audit_name
            execution_target_violations.append(violation_with_source)
        for violation in audit.get("packet_consistency_violations", []):
            violation_with_source = dict(violation)
            violation_with_source["scope_audit"] = audit_name
            packet_consistency_violations.append(violation_with_source)
        for violation in audit.get("source_consistency_violations", []):
            violation_with_source = dict(violation)
            violation_with_source["scope_audit"] = audit_name
            source_consistency_violations.append(violation_with_source)

    return {
        "work_item_count": work_item_count,
        "checked_scope_audits": checked_scope_audits,
        "checked_scope_audit_work_item_counts": work_item_counts,
        "writes_governance_records": scope_flags["writes_governance_records"],
        "executes_tool_calls": scope_flags["executes_tool_calls"],
        "samples_duckdb_tables": scope_flags["samples_duckdb_tables"],
        "checks_lineage_records": scope_flags["checks_lineage_records"],
        "proves_page_execution": scope_flags["proves_page_execution"],
        "runs_ui_or_api_smoke": scope_flags["runs_ui_or_api_smoke"],
        "captures_business_owner_approval": scope_flags["captures_business_owner_approval"],
        "approves_metric_or_page": scope_flags["approves_metric_or_page"],
        "queue_grants_closure": queue_grants_closure,
        "scope_violations": scope_violations,
        "suggested_tool_violations": suggested_tool_violations,
        "execution_target_violations": execution_target_violations,
        "packet_consistency_violations": packet_consistency_violations,
        "source_consistency_violations": source_consistency_violations,
    }


def page_catalog_date_lineage_review_queue_item(
    coverage_row: dict[str, Any],
    bundle: dict[str, Any],
    *,
    record_readiness: dict[str, Any] | None = None,
) -> dict[str, Any]:
    review_lane = page_catalog_date_lineage_review_lane(coverage_row)
    effective_record_readiness = record_readiness or page_catalog_date_lineage_unknown_record_readiness()
    return {
        "page_slug": coverage_row["page_slug"],
        "page_id": coverage_row["page_id"],
        "page_name": coverage_row["page_name"],
        "frontend_route": coverage_row["frontend_route"],
        "primary_api": coverage_row["primary_api"],
        "approval_status": coverage_row["approval_status"],
        "coverage_status": coverage_row["coverage_status"],
        "review_priority": page_catalog_date_lineage_review_priority(coverage_row, review_lane),
        "review_lane": review_lane,
        "formal_page_closure_allowed": False,
        "configured_table_names": coverage_row["configured_table_names"],
        "candidate_table_names": coverage_row["candidate_table_names"],
        "deferred_no_direct_table_config_reason": coverage_row["deferred_no_direct_table_config_reason"],
        "catalog_date_anchors": coverage_row["catalog_date_anchors"],
        "risk_reasons": page_catalog_date_lineage_review_risk_reasons(coverage_row, bundle, review_lane),
        "suggested_tool_calls": page_catalog_date_lineage_review_tool_calls(coverage_row, review_lane),
        "next_actions": page_catalog_date_lineage_review_next_actions(coverage_row, review_lane),
        "record_readiness": effective_record_readiness,
        "record_remediation": page_catalog_date_lineage_record_remediation(
            coverage_row,
            effective_record_readiness,
        ),
        "evidence_scope": {
            "queues_evidence_collection": True,
            "samples_duckdb_tables": False,
            "checks_lineage_records": False,
            "checks_data_quality": False,
            "checks_ui_api_payload": False,
            "proves_page_execution": False,
            "approves_metric_or_page": False,
        },
    }


def page_catalog_date_lineage_record_remediation(
    coverage_row: dict[str, Any],
    record_readiness: dict[str, Any],
) -> dict[str, Any]:
    evidence_scope = {
        "writes_governance_records": False,
        "approves_metric_or_page": False,
        "proves_page_execution": False,
        "executes_tool_calls": False,
        "runs_ui_or_api_smoke": False,
        "captures_business_owner_approval": False,
    }
    if str(record_readiness.get("audit_review_status") or "") == "ready_for_audit_review":
        return {
            "remediation_type": "none",
            "next_step": "manual_audit_review",
            "approval_boundary": "review_routing_only",
            "evidence_scope": evidence_scope,
        }

    remediation_type = page_catalog_date_lineage_record_remediation_type(record_readiness)
    return {
        "remediation_type": remediation_type,
        **page_governance_record_gap_next_step_fields(remediation_type),
        "suggested_tool_calls": page_governance_record_gap_remediation_tool_calls(
            {
                "page_slug": coverage_row["page_slug"],
            },
        ),
        "approval_boundary": "record_remediation_only",
        "evidence_scope": evidence_scope,
    }


def page_catalog_date_lineage_record_remediation_type(record_readiness: dict[str, Any]) -> str:
    status = str(record_readiness.get("record_validation_status") or "")
    if status == "missing_direct_records":
        return "create_direct_record"
    residual_gaps = [str(gap) for gap in record_readiness.get("residual_gaps", [])]
    if any("primary page/API anchor is missing" in gap for gap in residual_gaps):
        return "repair_primary_page_anchor"
    return "complete_direct_record_fields"


def page_catalog_date_lineage_review_lane(coverage_row: dict[str, Any]) -> str:
    approval_status = str(coverage_row["approval_status"])
    coverage_status = str(coverage_row["coverage_status"])
    if coverage_status == "deferred_no_direct_table_config":
        return "deferred_no_direct_table_config_review"
    if approval_status == "formal_or_governed":
        return "formal_governed_catalog_date_lineage_review"
    if approval_status == "gap_or_observational" and not coverage_row.get("configured_table_names"):
        return "gap_observational_separate_review"
    if page_catalog_date_lineage_has_formal_source_tables(coverage_row):
        return "candidate_formal_source_mixed_review"
    return "candidate_or_mixed_catalog_date_lineage_review"


def page_catalog_date_lineage_review_priority(
    coverage_row: dict[str, Any],
    review_lane: str,
) -> str:
    if review_lane in {
        "formal_governed_catalog_date_lineage_review",
        "candidate_formal_source_mixed_review",
    }:
        return "P1"
    if review_lane == "deferred_no_direct_table_config_review":
        return "P2"
    if str(coverage_row["coverage_status"]) == "missing_explicit_table_config":
        return "P1"
    return "P2"


def page_catalog_date_lineage_has_formal_source_tables(coverage_row: dict[str, Any]) -> bool:
    table_names = [str(table).casefold() for table in coverage_row.get("configured_table_names", [])]
    return any(
        table.startswith("fact_formal_")
        or table in {
            "product_category_pnl_formal_read_model",
            "fact_formal_bond_analytics_daily",
            "fact_formal_risk_tensor_daily",
        }
        for table in table_names
    )


def page_catalog_date_lineage_review_risk_reasons(
    coverage_row: dict[str, Any],
    bundle: dict[str, Any],
    review_lane: str,
) -> list[str]:
    if review_lane == "formal_governed_catalog_date_lineage_review":
        return [
            "formal/governed page requires direct catalog/date, lineage, payload, and owner review before closure.",
        ]
    if review_lane == "candidate_formal_source_mixed_review":
        return [
            "candidate or mixed-source page uses formal source tables; do not promote candidate output from source-table evidence alone.",
        ]
    if review_lane == "gap_observational_separate_review":
        return [
            "GAP/observational page must stay separate from formal PAGE, MTR, golden-sample, or trading-instruction closure.",
        ]
    if review_lane == "deferred_no_direct_table_config_review":
        reason = str(coverage_row.get("deferred_no_direct_table_config_reason") or "")
        return [
            reason or "no direct table contract is configured for this page.",
            "direct table sampling is deferred until a page table contract exists.",
        ]
    if str(coverage_row["coverage_status"]) == "missing_explicit_table_config":
        return [
            "explicit catalog/date table configuration is missing for a seeded page.",
        ]
    if bundle.get("golden_samples"):
        return ["page has supporting sample evidence, but sample evidence is not catalog/date-lineage closure."]
    return ["catalog/date-lineage review remains required before page-level closure."]


def page_catalog_date_lineage_review_tool_calls(
    coverage_row: dict[str, Any],
    review_lane: str,
) -> list[dict[str, Any]]:
    page_slug = str(coverage_row["page_slug"])
    if review_lane == "deferred_no_direct_table_config_review":
        return [
            {
                "tool": "moss-data-catalog.get_page_catalog_date_coverage",
                "arguments": {"page_slugs": [page_slug]},
            },
            {
                "tool": "moss-lineage-evidence.get_page_governance_gap_queue",
                "arguments": {"page_slugs": [page_slug]},
            },
        ]
    return [
        {
            "tool": "moss-data-catalog.get_page_catalog_date_evidence",
            "arguments": {"page_slugs": [page_slug]},
        },
        {
            "tool": "moss-lineage-evidence.get_page_lineage_evidence",
            "arguments": {"page_slugs": [page_slug]},
        },
        {
            "tool": "moss-lineage-evidence.validate_page_governance_records",
            "arguments": {"page_slugs": [page_slug]},
        },
    ]


def page_catalog_date_lineage_review_next_actions(
    coverage_row: dict[str, Any],
    review_lane: str,
) -> list[str]:
    page_id = str(coverage_row["page_id"])
    if review_lane == "formal_governed_catalog_date_lineage_review":
        return [
            f"Collect catalog/date samples and direct lineage evidence for {page_id}.",
            "Compare sampled dates, source versions, and direct governance records before any closure claim.",
        ]
    if review_lane == "candidate_formal_source_mixed_review":
        return [
            f"Collect catalog/date and lineage evidence for {page_id}, but do not promote candidate output from formal source tables.",
            "Require direct page/API governance records, UI/API payload review, live smoke evidence, and business-owner approval before closure.",
        ]
    if review_lane == "gap_observational_separate_review":
        return [
            "Keep GAP/observational evidence separate from formal PAGE/MTR/golden-sample closure.",
            f"Collect catalog/date and lineage evidence for {page_id} as observational support only.",
        ]
    if review_lane == "deferred_no_direct_table_config_review":
        return [
            f"Resolve {page_id} through coverage and governance gap queues; do not invent tables_used for this page.",
            "Review upstream/page-run evidence, result_meta, and visible no-data/stale/fallback states instead of direct table sampling.",
        ]
    return [
        f"Review explicit catalog/date configuration and lineage evidence for {page_id} before closure.",
    ]


def page_catalog_date_lineage_review_queue_sort_key(
    row: dict[str, Any],
    page_order: dict[str, int],
) -> tuple[int, int]:
    priority_rank = {"P1": 0, "P2": 1, "P3": 2}.get(str(row.get("review_priority") or ""), 9)
    return (priority_rank, page_order.get(str(row.get("page_id") or ""), len(page_order)))


def selected_unique_page_bundles(
    bundles: dict[str, dict[str, Any]],
    page_slugs: list[str],
) -> list[dict[str, Any]]:
    if page_slugs:
        return [page_trace_bundle(bundles, page_slug) for page_slug in page_slugs]
    selected: list[dict[str, Any]] = []
    seen_page_ids: set[str] = set()
    for bundle in bundles.values():
        page_id = str(bundle.get("page_id") or "")
        if page_id in seen_page_ids:
            continue
        seen_page_ids.add(page_id)
        selected.append(bundle)
    return selected


def selected_catalog_date_page_bundles(
    bundles: dict[str, dict[str, Any]],
    page_slugs: list[str],
) -> list[dict[str, Any]]:
    selected = selected_unique_page_bundles(bundles, page_slugs)
    if page_slugs:
        return selected
    return [
        bundle
        for bundle in selected
        if str(bundle.get("page_id") or "") not in DEFAULT_CATALOG_DATE_EXCLUDED_PAGE_IDS
    ]


def selected_governance_page_bundles(
    bundles: dict[str, dict[str, Any]],
    page_slugs: list[str],
) -> list[dict[str, Any]]:
    return selected_unique_page_bundles(bundles, page_slugs)


def page_catalog_date_coverage_row(bundle: dict[str, Any]) -> dict[str, Any]:
    page_id = str(bundle.get("page_id") or "")
    approval_readiness = page_approval_readiness(bundle, bundle_text(bundle))
    approval_status = approval_readiness["status"]
    lineage_status = lineage_readiness(bundle)
    catalog_anchors = catalog_date_readiness_anchors(bundle, lineage_status["anchors"])
    configured_tables = filter_readiness_anchors(PAGE_CATALOG_DATE_TABLES.get(page_id, []), limit=80)
    candidate_tables = page_catalog_candidate_table_names(bundle, catalog_anchors)
    deferred_reason = PAGE_CATALOG_DATE_DEFERRED_REASONS.get(page_id, "")
    if configured_tables:
        coverage_status = "configured_direct_tables"
    elif deferred_reason:
        coverage_status = "deferred_no_direct_table_config"
    else:
        coverage_status = "missing_explicit_table_config"
    return {
        "page_slug": bundle["page_slug"],
        "page_id": page_id,
        "page_name": bundle["page_name"],
        "frontend_route": bundle["frontend_route"],
        "primary_api": bundle["primary_api"],
        "approval_status": approval_status,
        "approval_status_source": approval_readiness["source"],
        "coverage_status": coverage_status,
        "priority": page_catalog_date_coverage_priority(approval_status, coverage_status),
        "configured_table_names": configured_tables,
        "candidate_table_names": candidate_tables,
        "deferred_no_direct_table_config_reason": deferred_reason,
        "catalog_date_anchors": catalog_anchors,
        "next_actions": page_catalog_date_coverage_next_actions(page_id, approval_status, coverage_status),
        "evidence_scope": {
            "checks_explicit_config": True,
            "samples_duckdb_tables": False,
            "checks_data_quality": False,
            "checks_lineage_records": False,
            "proves_page_execution": False,
            "approves_metric_or_page": False,
        },
    }


def page_catalog_date_coverage_priority(approval_status: str, coverage_status: str) -> str:
    if coverage_status == "configured_direct_tables":
        return "P3"
    if coverage_status == "deferred_no_direct_table_config":
        return "P2"
    if approval_status == "formal_or_governed":
        return "P1"
    return "P2"


def page_catalog_date_coverage_next_actions(
    page_id: str,
    approval_status: str,
    coverage_status: str,
) -> list[str]:
    if coverage_status == "configured_direct_tables":
        return [
            f"Run page catalog/date evidence for {page_id} and review sampled table/date results before closure.",
        ]
    if coverage_status == "deferred_no_direct_table_config":
        return [
            f"Keep {page_id} out of direct catalog/date table sampling until a direct page table contract exists.",
            "Audit upstream source pages, direct page/API governance records, visible stale/fallback/no-data states, and result_meta instead.",
        ]
    action = f"Add explicit catalog/date table config for {page_id} from the candidate table anchors, then sample DuckDB dates."
    if approval_status == "formal_or_governed":
        return [
            action,
            "Prioritize this formal/governed page before relying on trace-bundle anchors for release evidence.",
        ]
    return [
        action,
        "Keep candidate, mixed-source, GAP, and observational pages out of formal-use closure until direct evidence exists.",
    ]


def page_catalog_date_coverage_sort_key(
    page: dict[str, Any],
    page_order: dict[str, int],
) -> tuple[int, int, int]:
    priority_rank = {"P1": 0, "P2": 1, "P3": 2}.get(str(page.get("priority") or ""), 9)
    configured_rank = 1 if page["coverage_status"] == "configured_direct_tables" else 0
    return (
        priority_rank,
        configured_rank,
        page_order.get(str(page.get("page_id") or ""), len(page_order)),
    )


def page_catalog_date_evidence_row(bundle: dict[str, Any], duckdb_path: Path, *, limit: int) -> dict[str, Any]:
    lineage_status = lineage_readiness(bundle)
    catalog_anchors = catalog_date_readiness_anchors(bundle, lineage_status["anchors"])
    table_names = page_catalog_table_names(bundle, catalog_anchors)
    return {
        "page_slug": bundle["page_slug"],
        "page_id": bundle["page_id"],
        "page_name": bundle["page_name"],
        "frontend_route": bundle["frontend_route"],
        "primary_api": bundle["primary_api"],
        "catalog_date_anchors": catalog_anchors,
        "sampled_table_names": table_names,
        "evidence_scope": {
            "catalog_describe_checked": True,
            "date_sample_checked": True,
            "quality_checked": False,
            "lineage_checked": False,
            "formal_metric_approval_checked": False,
            "page_execution_checked": False,
        },
        "table_evidence": [
            catalog_date_table_evidence(duckdb_path, table_name, limit=limit) for table_name in table_names
        ],
    }


def page_catalog_table_names(bundle: dict[str, Any], catalog_anchors: list[str]) -> list[str]:
    page_id = str(bundle.get("page_id") or "")
    configured_tables = PAGE_CATALOG_DATE_TABLES.get(page_id, [])
    if configured_tables:
        return filter_readiness_anchors(configured_tables, limit=80)
    if page_id in PAGE_CATALOG_DATE_DEFERRED_REASONS:
        return []
    return filter_readiness_anchors(candidate_table_names_from_anchors(catalog_anchors), limit=80)


def page_catalog_candidate_table_names(bundle: dict[str, Any], catalog_anchors: list[str]) -> list[str]:
    bundle_anchors = [
        *catalog_anchors,
        *list(bundle.get("truth_chain") or []),
        *list(bundle.get("backend_touchpoints") or []),
        *list(bundle.get("verification_focus") or []),
    ]
    return filter_readiness_anchors(candidate_table_names_from_anchors(bundle_anchors), limit=80)


def candidate_table_names_from_anchors(anchors: list[str]) -> list[str]:
    candidates: list[str] = []
    for anchor in anchors:
        for token in re.findall(r"\b[A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z_][A-Za-z0-9_]*)?\b", anchor):
            if "." in token:
                continue
            if token.casefold() == "fact_table":
                continue
            if is_catalog_date_anchor(token):
                candidates.append(token)
    return candidates


def catalog_date_table_evidence(duckdb_path: Path, table_name: str, *, limit: int) -> dict[str, Any]:
    base = {
        "table_name": table_name,
        "status": "duckdb_missing",
        "column_count": 0,
        "date_column": None,
        "available_dates": [],
        "error": None,
    }
    if not duckdb_path.is_file():
        base["error"] = f"DuckDB file does not exist: {duckdb_path}"
        return base

    try:
        description = describe_duckdb_table(duckdb_path, table_name)
    except McpError as exc:
        base["status"] = "unknown_table" if exc.code == -32602 else "catalog_unavailable"
        base["error"] = exc.message
        return base

    column_names = [str(column["name"]) for column in description["columns"]]
    date_column = choose_date_column(column_names)
    base.update({"status": "present", "column_count": len(column_names), "date_column": date_column})
    if date_column is None:
        base["status"] = "present_no_date_column"
        return base

    try:
        dates = list_available_dates(duckdb_path, table_name, date_column, limit=limit)
    except McpError as exc:
        base["status"] = "date_sample_failed"
        base["error"] = exc.message
        return base

    base["available_dates"] = dates["values"]
    return base


def choose_date_column(column_names: list[str]) -> str | None:
    columns_by_casefold = {column.casefold(): column for column in column_names}
    for preferred in DATE_COLUMN_PRIORITY:
        column = columns_by_casefold.get(preferred.casefold())
        if column is not None:
            return column
    return None


def page_evidence_readiness_row(bundle: dict[str, Any]) -> dict[str, Any]:
    combined = bundle_text(bundle)
    approval_readiness = page_approval_readiness(bundle, combined)
    approval_status = approval_readiness["status"]
    formal_use_allowed = approval_status == "formal_or_governed"
    golden_samples = list(bundle.get("golden_samples") or [])
    golden_status = golden_sample_status(bundle, approval_status)
    lineage_status = lineage_readiness(bundle)
    lineage_anchors = lineage_status["anchors"]
    catalog_anchors = catalog_date_readiness_anchors(bundle, lineage_anchors)
    return {
        "page_slug": bundle["page_slug"],
        "page_id": bundle["page_id"],
        "page_name": bundle["page_name"],
        "frontend_route": bundle["frontend_route"],
        "primary_api": bundle["primary_api"],
        "approval_status": approval_status,
        "approval_status_source": approval_readiness["source"],
        "formal_use_allowed": formal_use_allowed,
        "checks": {
            "trace_bundle": {
                "status": "present",
                "anchors": [bundle["page_id"], bundle["primary_api"], *bundle.get("contract_docs", [])],
            },
            "lineage_mapping": {
                "status": lineage_status["status"],
                "anchors": lineage_anchors,
            },
            "catalog_date": {
                "status": "direct_review_required",
                "anchors": catalog_anchors,
            },
            "golden_sample": {
                "status": golden_status,
                "anchors": golden_samples,
            },
        },
        "residual_gaps": residual_evidence_gaps(bundle, approval_status, golden_status),
        "guardrails": list(bundle.get("guardrails") or []),
    }


def bundle_text(bundle: dict[str, Any]) -> str:
    values: list[str] = []
    for key in (
        "page_slug",
        "page_id",
        "page_name",
        "frontend_route",
        "primary_api",
        "supporting_apis",
        "contract_docs",
        "truth_chain",
        "backend_touchpoints",
        "frontend_touchpoints",
        "test_touchpoints",
        "golden_samples",
        "verification_focus",
        "guardrails",
    ):
        value = bundle.get(key)
        if isinstance(value, list):
            values.extend(str(item) for item in value)
        elif value is not None:
            values.append(str(value))
    return "\n".join(values)


def page_approval_readiness(bundle: dict[str, Any], combined: str) -> dict[str, str]:
    page_id = str(bundle.get("page_id") or "")
    if page_id in EVIDENCE_READINESS_STATUS_BY_PAGE_ID:
        return {"status": EVIDENCE_READINESS_STATUS_BY_PAGE_ID[page_id], "source": "explicit_status_map"}
    return {"status": "unclassified_review_required", "source": "unclassified_fallback"}


def lineage_page_slugs_from_arguments(arguments: dict[str, Any]) -> list[str]:
    if arguments.get("all_seeded_pages") is True:
        return []
    raw_page_slugs = arguments.get("page_slugs")
    if raw_page_slugs is None:
        return list(DEFAULT_EVIDENCE_READINESS_PAGES)
    if isinstance(raw_page_slugs, list):
        return [str(item).strip() for item in raw_page_slugs if str(item).strip()]
    raise McpError(-32602, "page_slugs must be an array of strings.")


def page_lineage_evidence(
    bundles: dict[str, dict[str, Any]],
    streams: dict[str, Path],
    page_slugs: list[str],
    stream_names: list[str],
    *,
    max_results: int,
) -> dict[str, Any]:
    if max_results < 1 or max_results > 100:
        raise McpError(-32602, "max_results must be between 1 and 100.")
    selected_bundles = selected_governance_page_bundles(bundles, page_slugs)
    pages = [
        page_lineage_evidence_row(
            bundle,
            streams,
            stream_names,
            max_results=max_results,
        )
        for bundle in selected_bundles
    ]
    direct_count = sum(len(page["direct_page_or_api_records"]) for page in pages)
    expanded_count = sum(len(page["expanded_anchor_records"]) for page in pages)
    missing_direct_count = sum(1 for page in pages if not page["direct_page_or_api_records"])
    return {
        "scope": "page-lineage-evidence",
        "disclaimer": (
            "This tool separates direct page/API governance records from expanded source-table or metric-anchor "
            "records; it does not prove page execution completeness, metric definition, or formal approval."
        ),
        "pages": pages,
        "summary": {
            "page_count": len(pages),
            "direct_page_or_api_record_count": direct_count,
            "expanded_anchor_record_count": expanded_count,
            "missing_direct_page_or_api_record_count": missing_direct_count,
        },
    }


def page_governance_record_requirements(
    bundles: dict[str, dict[str, Any]],
    page_slugs: list[str],
) -> dict[str, Any]:
    selected_bundles = selected_governance_page_bundles(bundles, page_slugs)
    pages = [
        page_governance_record_requirements_row(bundle)
        for bundle in selected_bundles
    ]
    return {
        "scope": "page-governance-record-requirements",
        "disclaimer": (
            "This tool describes evidence requirements only; it does not create governance records, validate that "
            "records exist, prove page/API execution, or approve metric/page formal use."
        ),
        "pages": pages,
        "summary": {
            "page_count": len(pages),
            "direct_record_required_count": sum(1 for page in pages if page["direct_record_required"]),
        },
    }


def page_governance_record_validation(
    bundles: dict[str, dict[str, Any]],
    streams: dict[str, Path],
    page_slugs: list[str],
    stream_names: list[str],
    *,
    max_results: int,
) -> dict[str, Any]:
    if max_results < 1 or max_results > 100:
        raise McpError(-32602, "max_results must be between 1 and 100.")
    selected_bundles = selected_governance_page_bundles(bundles, page_slugs)
    pages = [
        page_governance_record_validation_row(
            bundle,
            streams,
            stream_names,
            max_results=max_results,
        )
        for bundle in selected_bundles
    ]
    ready_count = sum(
        1
        for page in pages
        for validation in page["direct_record_validations"]
        if validation["validation_status"] == "ready_for_audit_review"
    )
    incomplete_count = sum(
        1
        for page in pages
        for validation in page["direct_record_validations"]
        if validation["validation_status"] == "incomplete"
    )
    return {
        "scope": "page-governance-record-validation",
        "disclaimer": (
            "This tool validates existing direct page/API governance records against checklist fields only; it "
            "does not write records, does not prove page execution completeness, and does not approve metric/page "
            "formal use."
        ),
        "pages": pages,
        "summary": {
            "page_count": len(pages),
            "ready_record_count": ready_count,
            "incomplete_record_count": incomplete_count,
            "missing_record_page_count": sum(
                1 for page in pages if page["validation_status"] == "missing_direct_records"
            ),
        },
    }


def page_governance_audit_review_checklist(
    bundles: dict[str, dict[str, Any]],
    streams: dict[str, Path],
    page_slugs: list[str],
    stream_names: list[str],
    *,
    max_results: int,
) -> dict[str, Any]:
    validation_payload = page_governance_record_validation(
        bundles,
        streams,
        page_slugs,
        stream_names,
        max_results=max_results,
    )
    pages = [
        page_governance_audit_review_checklist_row(page)
        for page in validation_payload["pages"]
    ]
    return {
        "scope": "page-governance-audit-review-checklist",
        "disclaimer": (
            "This checklist routes manual audit review after direct-record field validation; it does not write "
            "governance records, prove page/API execution, and does not approve metric/page formal use."
        ),
        "pages": pages,
        "summary": {
            "page_count": len(pages),
            "ready_for_audit_review_count": sum(
                1 for page in pages if page["audit_review_status"] == "ready_for_audit_review"
            ),
            "blocked_by_record_gaps_count": sum(
                1 for page in pages if page["audit_review_status"] == "blocked_by_record_gaps"
            ),
            "closure_approved_count": sum(1 for page in pages if page["closure_approved"]),
        },
    }


def page_governance_audit_review_queue(
    bundles: dict[str, dict[str, Any]],
    streams: dict[str, Path],
    page_slugs: list[str],
    stream_names: list[str],
    *,
    max_results: int,
) -> dict[str, Any]:
    checklist = page_governance_audit_review_checklist(
        bundles,
        streams,
        page_slugs,
        stream_names,
        max_results=max_results,
    )
    items = [
        page_governance_audit_review_queue_item(page)
        for page in checklist["pages"]
        if page["audit_review_status"] == "ready_for_audit_review"
    ]
    return {
        "scope": "page-governance-audit-review-queue",
        "disclaimer": (
            "This read-only queue routes field-complete direct records to manual audit review; it does not "
            "write governance records, prove page/API execution, and does not approve metric/page formal use."
        ),
        "items": items,
        "summary": {
            **checklist["summary"],
            "queue_count": len(items),
            "remaining_manual_check_count": sum(len(item["remaining_manual_checks"]) for item in items),
        },
    }


def page_governance_audit_evidence_packet(
    bundles: dict[str, dict[str, Any]],
    streams: dict[str, Path],
    page_slug: str,
    stream_names: list[str],
    duckdb_path: Path,
    *,
    max_results: int,
) -> dict[str, Any]:
    bundle = page_trace_bundle(bundles, page_slug)
    canonical_page_slug = str(bundle["page_slug"])
    queue_payload = page_governance_audit_review_queue(
        bundles,
        streams,
        [canonical_page_slug],
        stream_names,
        max_results=max_results,
    )
    queue_item = next(
        (item for item in queue_payload["items"] if item["page_id"] == bundle["page_id"]),
        None,
    )
    if queue_item is None:
        checklist = page_governance_audit_review_checklist(
            bundles,
            streams,
            [canonical_page_slug],
            stream_names,
            max_results=max_results,
        )
        page_status = checklist["pages"][0] if checklist["pages"] else {}
        audit_review_status = str(page_status.get("audit_review_status") or "blocked_by_record_gaps")
        return {
            "scope": "page-governance-audit-evidence-packet",
            "disclaimer": page_governance_audit_evidence_packet_disclaimer(),
            "page_slug": canonical_page_slug,
            "page_id": bundle["page_id"],
            "audit_review_status": audit_review_status,
            "closure_approved": False,
            "blocked_reason": "direct_record_not_ready_for_audit_review",
            "audit_review_queue_item": None,
            "manual_review_blockers": ["direct_page_api_record_fields"],
            "evidence_scope": page_governance_audit_evidence_packet_scope(),
            "summary": {
                "mcp_evidence_sections": [],
                "manual_review_blocker_count": 1,
                "closure_approved": False,
            },
        }

    contract_trace = page_trace_bundle(bundles, canonical_page_slug)
    catalog_date = page_catalog_date_evidence(
        bundles,
        duckdb_path,
        [canonical_page_slug],
        limit=min(max_results, 100),
    )
    lineage = page_lineage_evidence(
        bundles,
        streams,
        [canonical_page_slug],
        stream_names,
        max_results=max_results,
    )
    manual_evidence_present = page_governance_manual_review_evidence_present(queue_item)
    manual_blockers = page_governance_manual_review_blockers(queue_item, manual_evidence_present)
    return {
        "scope": "page-governance-audit-evidence-packet",
        "disclaimer": page_governance_audit_evidence_packet_disclaimer(),
        "page_slug": canonical_page_slug,
        "page_id": bundle["page_id"],
        "audit_review_status": queue_item["audit_review_status"],
        "closure_approved": False,
        "contract_trace": contract_trace,
        "contract_trace_summary": page_governance_contract_trace_summary(contract_trace),
        "catalog_date_evidence": catalog_date,
        "lineage_evidence": lineage,
        "audit_review_queue_item": queue_item,
        "manual_review_blockers": manual_blockers,
        "manual_review_blocker_targets": page_governance_manual_review_blocker_targets(
            queue_item,
            manual_blockers,
        ),
        "manual_review_evidence_present": manual_evidence_present,
        "evidence_scope": page_governance_audit_evidence_packet_scope(),
        "summary": {
            "mcp_evidence_sections": [
                "contract_trace",
                "catalog_date_evidence",
                "lineage_evidence",
                "audit_review_queue_item",
            ],
            "manual_review_blocker_count": len(manual_blockers),
            "manual_review_evidence_present_count": len(manual_evidence_present),
            "closure_approved": False,
        },
    }


def page_governance_audit_evidence_packet_queue(
    bundles: dict[str, dict[str, Any]],
    streams: dict[str, Path],
    page_slugs: list[str],
    stream_names: list[str],
    duckdb_path: Path,
    *,
    max_results: int,
) -> dict[str, Any]:
    review_queue = page_governance_audit_review_queue(
        bundles,
        streams,
        page_slugs,
        stream_names,
        max_results=max_results,
    )
    checklist = page_governance_audit_review_checklist(
        bundles,
        streams,
        page_slugs,
        stream_names,
        max_results=max_results,
    )
    items = [
        page_governance_audit_evidence_packet(
            bundles,
            streams,
            str(item["page_slug"]),
            stream_names,
            duckdb_path,
            max_results=max_results,
        )
        for item in review_queue["items"]
    ]
    blocked_pages = page_governance_blocked_record_gap_pages(
        bundles,
        checklist["pages"],
    )
    blocked_next_steps = page_governance_blocked_record_gap_next_steps(blocked_pages)
    create_table_anchor_work_items = page_governance_create_direct_record_table_anchor_work_items(
        blocked_pages,
    )
    create_evidence_work_items = page_governance_create_direct_record_evidence_work_items(
        blocked_pages,
    )
    repair_evidence_work_items = page_governance_repair_direct_record_evidence_work_items(
        blocked_pages,
    )
    direct_remediation_work_items = page_governance_direct_record_remediation_work_items(
        blocked_pages,
    )
    manual_review_mcp_work_items = page_governance_manual_review_mcp_work_items(items)
    manual_review_work_items = page_governance_manual_review_work_items(items)
    manual_review_evidence_present_work_items = page_governance_manual_review_evidence_present_work_items(
        items,
    )
    manual_review_blocker_count = sum(len(item["manual_review_blockers"]) for item in items)
    manual_review_evidence_present_count = sum(
        len(item.get("manual_review_evidence_present", [])) for item in items
    )
    direct_remediation_scope_audit = page_governance_direct_record_remediation_scope_audit(
        {
            "blocked_by_record_gap_next_steps": blocked_next_steps,
            "create_direct_record_evidence_work_items": create_evidence_work_items,
            "create_direct_record_table_anchor_work_items": create_table_anchor_work_items,
            "direct_record_remediation_work_items": direct_remediation_work_items,
            "repair_direct_record_evidence_work_items": repair_evidence_work_items,
        },
    )
    manual_review_mcp_scope_audit = page_governance_manual_review_mcp_scope_audit(
        manual_review_mcp_work_items,
    )
    manual_review_scope_audit = page_governance_manual_review_scope_audit(
        {
            "manual_review_work_items": manual_review_work_items,
            "manual_review_evidence_present_work_items": manual_review_evidence_present_work_items,
        },
    )
    queue_boundary_audit = page_governance_queue_boundary_audit(
        {
            "manual_review_mcp_scope_audit": manual_review_mcp_scope_audit,
            "manual_review_scope_audit": manual_review_scope_audit,
            "direct_record_remediation_scope_audit": direct_remediation_scope_audit,
        },
        work_item_count=(
            manual_review_mcp_scope_audit["work_item_count"]
            + manual_review_scope_audit["work_item_count"]
            + direct_remediation_scope_audit["work_item_count"]
        ),
    )
    return {
        "scope": "page-governance-audit-evidence-packet-queue",
        "disclaimer": (
            "This queue aggregates read-only MCP evidence packets for manual audit review; it does not write "
            "governance records, run UI/API smoke checks, prove page/API execution, capture business-owner "
            "approval, and does not approve metric/page formal use."
        ),
        "items": items,
        "summary": {
            "page_count": review_queue["summary"]["page_count"],
            "ready_for_audit_review_count": review_queue["summary"]["ready_for_audit_review_count"],
            "packet_count": len(items),
            "blocked_by_record_gaps_count": review_queue["summary"]["blocked_by_record_gaps_count"],
            "closure_approved_count": review_queue["summary"]["closure_approved_count"],
            "manual_review_blocker_count": manual_review_blocker_count,
            "manual_review_evidence_present_count": manual_review_evidence_present_count,
            "closure_readiness": page_governance_queue_closure_readiness(
                page_count=review_queue["summary"]["page_count"],
                ready_for_audit_review_count=review_queue["summary"]["ready_for_audit_review_count"],
                blocked_by_record_gaps_count=review_queue["summary"]["blocked_by_record_gaps_count"],
                manual_review_mcp_work_item_count=len(manual_review_mcp_work_items),
                manual_review_blocker_count=manual_review_blocker_count,
                manual_review_evidence_present_count=manual_review_evidence_present_count,
                closure_approved_count=review_queue["summary"]["closure_approved_count"],
            ),
            "manual_review_blocker_breakdown": page_governance_count_values(
                check
                for item in items
                for check in item["manual_review_blockers"]
            ),
            "manual_review_evidence_present_breakdown": page_governance_count_values(
                str(evidence.get("check"))
                for item in items
                for evidence in item.get("manual_review_evidence_present", [])
                if evidence.get("check")
            ),
            "manual_review_blocker_pages": page_governance_pages_by_check(
                items,
                "manual_review_blockers",
            ),
            "manual_review_evidence_present_pages": page_governance_pages_by_evidence_check(
                items,
                "manual_review_evidence_present",
            ),
            "ready_for_audit_review_pages": [
                {"page_id": item["page_id"], "page_slug": item["page_slug"]}
                for item in items
            ],
            "manual_review_evidence_present_work_items": manual_review_evidence_present_work_items,
            "manual_review_mcp_work_items": manual_review_mcp_work_items,
            "manual_review_mcp_scope_audit": manual_review_mcp_scope_audit,
            "manual_review_work_items": manual_review_work_items,
            "manual_review_scope_audit": manual_review_scope_audit,
            "queue_boundary_audit": queue_boundary_audit,
            "blocked_by_record_gap_remediation_breakdown": page_governance_count_values(
                page["remediation_type"] for page in blocked_pages
            ),
            "blocked_by_record_gap_remediation_pages": page_governance_pages_by_remediation_type(
                blocked_pages,
            ),
            "blocked_by_record_gap_next_step_breakdown": page_governance_count_values(
                step["next_step"] for step in blocked_next_steps
            ),
            "blocked_by_record_gap_next_step_pages": page_governance_pages_by_next_step(
                blocked_next_steps,
            ),
            "blocked_by_record_gap_next_steps": blocked_next_steps,
            "create_direct_record_table_anchor_work_items": create_table_anchor_work_items,
            "direct_record_remediation_scope_audit": direct_remediation_scope_audit,
            "create_direct_record_evidence_work_items": create_evidence_work_items,
            "repair_direct_record_evidence_work_items": repair_evidence_work_items,
            "direct_record_remediation_work_items": direct_remediation_work_items,
            "blocked_by_record_gap_pages": blocked_pages,
        },
        "evidence_scope": page_governance_audit_evidence_packet_scope(),
    }


def page_governance_blocked_record_gap_pages(
    bundles: dict[str, dict[str, Any]],
    pages: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    return [
        {
            "page_id": str(page["page_id"]),
            "page_slug": str(page["page_slug"]),
            "page_name": str(page["page_name"]),
            "primary_api": str(page["primary_api"]),
            "record_validation_status": str(page["record_validation_status"]),
            "direct_record_count": int(page["direct_record_count"]),
            "incomplete_record_count": int(page["incomplete_record_count"]),
            "remediation_type": page_governance_record_gap_remediation_type(page),
            "remediation_tool_calls": page_governance_record_gap_remediation_tool_calls(page),
            "repair_targets": page_governance_repair_targets(
                page_governance_gap_direct_record_diagnostics(
                    page,
                    include_records=True,
                ),
                page_governance_record_blueprint(bundles, str(page["page_slug"])),
            ),
            **page_governance_record_gap_creation_target(bundles, page),
            **page_governance_record_gap_anchor_repair_target(bundles, page),
            "residual_gaps": list(page.get("residual_gaps", [])),
        }
        for page in pages
        if page["audit_review_status"] == "blocked_by_record_gaps"
    ]


def page_governance_record_gap_remediation_type(page: dict[str, Any]) -> str:
    if page["record_validation_status"] == "missing_direct_records":
        return "create_direct_record"
    residual_gaps = [str(gap) for gap in page.get("residual_gaps", [])]
    if any("primary page/API anchor is missing" in gap for gap in residual_gaps):
        return "repair_primary_page_anchor"
    return "complete_direct_record_fields"


def page_governance_record_gap_remediation_tool_calls(page: dict[str, Any]) -> list[dict[str, Any]]:
    page_slug = str(page["page_slug"])
    return [
        {
            "tool": "moss-lineage-evidence.get_page_governance_record_requirements",
            "arguments": {"page_slugs": [page_slug]},
        },
        {
            "tool": "moss-lineage-evidence.get_page_governance_record_blueprint",
            "arguments": {"page_slug": page_slug},
        },
    ]


def page_governance_record_gap_creation_target(
    bundles: dict[str, dict[str, Any]],
    page: dict[str, Any],
) -> dict[str, Any]:
    if page_governance_record_gap_remediation_type(page) != "create_direct_record":
        return {}
    blueprint = page_governance_record_blueprint(bundles, str(page["page_slug"]))
    validation = blueprint["preflight"]["validation"]
    failed_groups = [
        str(group.get("name") or "")
        for group in validation.get("failed_required_field_groups", [])
    ]
    candidate = blueprint["candidate_record"]
    gap_type = page_governance_gap_type(
        str(page["record_validation_status"]),
        expanded_anchor_record_count=int(page.get("expanded_anchor_record_count", 0)),
    )
    return {
        "creation_target": {
            "manual_fill_priority": page_governance_missing_direct_record_fill_priority(gap_type),
            "candidate_record": {
                "page_id": candidate.get("page_id"),
                "page_slug": candidate.get("page_slug"),
                "frontend_route": candidate.get("frontend_route"),
                "primary_api": candidate.get("primary_api"),
                "tables_used": candidate.get("tables_used"),
                "formal_use_allowed": candidate.get("formal_use_allowed"),
            },
            "preflight_submission_template": page_governance_preflight_submission_template(blueprint),
            "manual_fill_fields": blueprint["manual_fill_fields"],
            "manual_fill_field_details": page_governance_manual_fill_field_details(blueprint),
            "missing_required_fields": validation.get("missing_required_fields", []),
            "failed_required_field_groups": failed_groups,
            "direct_anchor_targets": blueprint["direct_anchor_targets"],
            "configured_table_names": blueprint["configured_table_names"],
            **page_governance_table_anchor_resolution_target(blueprint),
        }
    }


def page_governance_preflight_submission_template(blueprint: dict[str, Any]) -> dict[str, Any]:
    candidate = blueprint["candidate_record"]
    return {
        "tool": "moss-lineage-evidence.preflight_page_governance_record",
        "arguments": {
            "page_slug": blueprint["page_slug"],
            "record": {
                "page_id": candidate.get("page_id"),
                "page_slug": candidate.get("page_slug"),
                "frontend_route": candidate.get("frontend_route"),
                "primary_api": candidate.get("primary_api"),
                "tables_used": candidate.get("tables_used"),
                "formal_use_allowed": candidate.get("formal_use_allowed"),
                "report_date": candidate.get("report_date"),
                "basis": candidate.get("basis"),
                "source_surface": candidate.get("source_surface"),
                "source_version": candidate.get("source_version"),
                "rule_version": candidate.get("rule_version"),
                "created_at": candidate.get("created_at"),
                "cache_key": candidate.get("cache_key"),
                "run_id": candidate.get("run_id"),
            },
        },
        "manual_placeholders": list(blueprint["manual_fill_fields"]),
        "approval_boundary": "preflight_only_no_write_no_approval",
        "evidence_scope": {
            "writes_governance_records": False,
            "approves_metric_or_page": False,
            "proves_page_execution": False,
            "checks_record_existence": False,
        },
    }


def page_governance_record_gap_anchor_repair_target(
    bundles: dict[str, dict[str, Any]],
    page: dict[str, Any],
) -> dict[str, Any]:
    if page_governance_record_gap_remediation_type(page) != "repair_primary_page_anchor":
        return {}
    blueprint = page_governance_record_blueprint(bundles, str(page["page_slug"]))
    diagnostics = page_governance_gap_direct_record_diagnostics(
        page,
        include_records=True,
    )
    repair_targets = page_governance_repair_targets(
        diagnostics
    )
    supporting_matches = [
        target.get("direct_anchor_match", {})
        for target in repair_targets
        if target.get("direct_anchor_match", {}).get("anchor_type") == "supporting_api"
    ]
    return {
        "anchor_repair_target": {
            "required_primary_anchor_types": ["page_id", "frontend_route", "primary_api"],
            "direct_anchor_targets": blueprint["direct_anchor_targets"],
            "current_supporting_anchor_matches": supporting_matches,
            "preflight_repair_templates": page_governance_anchor_repair_preflight_templates(
                blueprint,
                diagnostics,
            ),
        }
    }


def page_governance_anchor_repair_preflight_templates(
    blueprint: dict[str, Any],
    diagnostics: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    templates = []
    for diagnostic in diagnostics:
        if diagnostic.get("direct_anchor_match", {}).get("anchor_type") != "supporting_api":
            continue
        repaired_record = page_governance_anchor_repair_candidate_record(
            blueprint,
            diagnostic.get("record", {}),
        )
        templates.append(
            {
                "record_location": diagnostic.get("record_location", {}),
                "tool": "moss-lineage-evidence.preflight_page_governance_record",
                "arguments": {
                    "page_slug": blueprint["page_slug"],
                    "record": repaired_record,
                },
                "manual_placeholders": page_governance_repaired_record_manual_placeholders(
                    blueprint,
                    repaired_record,
                ),
                "approval_boundary": "preflight_only_no_write_no_approval",
                "evidence_scope": {
                    "writes_governance_records": False,
                    "approves_metric_or_page": False,
                    "proves_page_execution": False,
                    "checks_record_existence": False,
                },
            }
        )
    return templates


def page_governance_anchor_repair_candidate_record(
    blueprint: dict[str, Any],
    record: dict[str, Any],
) -> dict[str, Any]:
    candidate = dict(record) if isinstance(record, dict) else {}
    return {
        "page_id": blueprint["page_id"],
        "page_slug": blueprint["page_slug"],
        "frontend_route": blueprint["frontend_route"],
        "primary_api": blueprint["primary_api"],
        "tables_used": candidate.get("tables_used"),
        "formal_use_allowed": False,
        "report_date": candidate.get("report_date"),
        "basis": candidate.get("basis"),
        "source_surface": candidate.get("source_surface"),
        "source_version": candidate.get("source_version"),
        "rule_version": candidate.get("rule_version"),
        "created_at": candidate.get("created_at"),
        "cache_key": candidate.get("cache_key"),
        "run_id": candidate.get("run_id"),
    }


def page_governance_repaired_record_manual_placeholders(
    blueprint: dict[str, Any],
    record: dict[str, Any],
) -> list[str]:
    placeholders = [
        field
        for field in blueprint["required_fields"]
        if governance_record_value_missing(record.get(field))
    ]
    if any(
        str(group.get("name") or "") == "execution_identifier"
        and governance_required_field_group_failed(record, group)
        for group in blueprint["required_field_groups"]
    ):
        placeholders.append("cache_key_or_run_id")
    return placeholders


def page_governance_missing_direct_record_fill_priority(gap_type: str) -> str:
    if gap_type == "missing_direct_and_expanded_records":
        return "create_direct_record_and_supporting_lineage"
    if gap_type == "missing_direct_record_expanded_only":
        return "create_direct_record_from_existing_supporting_lineage"
    return "create_direct_record"


def page_governance_table_anchor_resolution_target(blueprint: dict[str, Any]) -> dict[str, Any]:
    page_id = str(blueprint.get("page_id") or "")
    deferred_reason = PAGE_CATALOG_DATE_DEFERRED_REASONS.get(page_id)
    if not deferred_reason:
        return {}
    return {
        "table_anchor_resolution_target": {
            "resolution_type": "deferred_no_direct_table_config",
            "deferred_reason": deferred_reason,
            "required_action": "do_not_invent_tables_used",
            "review_targets": [
                "upstream source pages",
                "direct page/API governance record",
                "visible stale/fallback/no-data state",
                "result_meta",
            ],
            "suggested_tool_calls": [
                {
                    "tool": "moss-data-catalog.get_page_catalog_date_coverage",
                    "arguments": {"page_slugs": [str(blueprint.get("page_slug") or "")]},
                },
            ],
            "evidence_scope": {
                "writes_governance_records": False,
                "approves_metric_or_page": False,
                "proves_page_execution": False,
                "samples_duckdb_tables": False,
            },
        }
    }


def page_governance_pages_by_remediation_type(
    pages: list[dict[str, Any]],
) -> dict[str, list[dict[str, str]]]:
    pages_by_type: dict[str, list[dict[str, str]]] = {}
    for page in pages:
        pages_by_type.setdefault(str(page["remediation_type"]), []).append(
            {
                "page_id": str(page["page_id"]),
                "page_slug": str(page["page_slug"]),
            }
        )
    return dict(sorted(pages_by_type.items()))


def page_governance_pages_by_next_step(
    next_steps: list[dict[str, Any]],
) -> dict[str, list[dict[str, str]]]:
    pages_by_next_step: dict[str, list[dict[str, str]]] = {}
    for step in next_steps:
        pages_by_next_step.setdefault(str(step["next_step"]), []).append(
            {
                "page_id": str(step["page_id"]),
                "page_slug": str(step["page_slug"]),
            }
        )
    return dict(sorted(pages_by_next_step.items()))


def page_governance_create_direct_record_table_anchor_work_items(
    pages: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    work_items_by_status: dict[str, dict[str, Any]] = {}
    for page in pages:
        if str(page.get("remediation_type") or "") != "create_direct_record":
            continue
        creation_target = page.get("creation_target") if isinstance(page.get("creation_target"), dict) else {}
        table_anchor_target = creation_target.get("table_anchor_resolution_target")
        if isinstance(table_anchor_target, dict):
            status = str(table_anchor_target.get("resolution_type") or "deferred_no_direct_table_config")
            page_ref = {
                "page_id": str(page["page_id"]),
                "page_slug": str(page["page_slug"]),
                "deferred_reason": str(table_anchor_target.get("deferred_reason") or ""),
            }
            next_action = "resolve_without_inventing_tables_used"
        else:
            status = "configured_table_anchor_available"
            page_ref = {
                "page_id": str(page["page_id"]),
                "page_slug": str(page["page_slug"]),
                "configured_table_names": list(creation_target.get("configured_table_names", [])),
            }
            next_action = "collect_page_run_evidence_for_configured_table_anchors"
        item = work_items_by_status.setdefault(
            status,
            {
                "table_anchor_status": status,
                "pages": [],
                "next_action": next_action,
                "approval_boundary": "record_creation_table_anchor_routing_only",
                "evidence_scope": {
                    "writes_governance_records": False,
                    "approves_metric_or_page": False,
                    "proves_page_execution": False,
                    "executes_tool_calls": False,
                    "runs_ui_or_api_smoke": False,
                    "captures_business_owner_approval": False,
                },
            },
        )
        item["pages"].append(page_ref)
    work_items = []
    for item in work_items_by_status.values():
        item["page_count"] = len(item["pages"])
        work_items.append(item)
    return sorted(work_items, key=lambda item: str(item["table_anchor_status"]))


def page_governance_blocked_record_gap_next_steps(
    pages: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    return [
        {
            "page_id": str(page["page_id"]),
            "page_slug": str(page["page_slug"]),
            "remediation_type": str(page["remediation_type"]),
            **page_governance_record_gap_next_step_fields(str(page["remediation_type"])),
            "suggested_tool_calls": list(page.get("remediation_tool_calls", [])),
            "approval_boundary": "record_remediation_only",
            "evidence_scope": {
                "writes_governance_records": False,
                "approves_metric_or_page": False,
                "proves_page_execution": False,
                "executes_tool_calls": False,
                "runs_ui_or_api_smoke": False,
                "captures_business_owner_approval": False,
            },
        }
        for page in pages
    ]


def page_governance_record_gap_next_step_fields(remediation_type: str) -> dict[str, Any]:
    if remediation_type == "create_direct_record":
        return {
            "next_step": "collect_direct_page_api_record_evidence_then_preflight_candidate",
            "evidence_to_collect": [
                "direct_page_or_primary_api_anchor",
                "required_record_fields",
                "page_api_execution_identifier",
                "configured_or_deferred_table_anchors",
            ],
        }
    if remediation_type == "repair_primary_page_anchor":
        return {
            "next_step": "repair_primary_page_api_anchor_then_preflight_candidate",
            "evidence_to_collect": [
                "primary_page_id_or_frontend_route_or_primary_api_anchor",
                "supporting_record_reusable_execution_fields",
                "remaining_missing_required_fields",
            ],
        }
    return {
        "next_step": "complete_existing_direct_record_fields_then_preflight",
        "evidence_to_collect": [
            "missing_required_fields",
            "failed_required_field_groups",
            "page_api_execution_identifier",
        ],
    }


def page_governance_direct_record_remediation_work_items(
    pages: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    work_items = []
    for page in pages:
        remediation_type = str(page["remediation_type"])
        item = {
            "work_type": page_governance_direct_record_work_type(remediation_type),
            "remediation_type": remediation_type,
            "page_id": str(page["page_id"]),
            "page_slug": str(page["page_slug"]),
            "page_name": str(page["page_name"]),
            "primary_api": str(page["primary_api"]),
            "record_validation_status": str(page["record_validation_status"]),
            "direct_record_count": int(page["direct_record_count"]),
            "incomplete_record_count": int(page["incomplete_record_count"]),
            "remediation_tool_calls": list(page.get("remediation_tool_calls", [])),
            "repair_targets": list(page.get("repair_targets", [])),
            "residual_gaps": list(page.get("residual_gaps", [])),
            "approval_boundary": "record_remediation_only",
            "evidence_scope": {
                "writes_governance_records": False,
                "approves_metric_or_page": False,
                "proves_page_execution": False,
                "executes_tool_calls": False,
                "runs_ui_or_api_smoke": False,
                "captures_business_owner_approval": False,
            },
        }
        if "creation_target" in page:
            item["creation_target"] = page["creation_target"]
        if "anchor_repair_target" in page:
            item["anchor_repair_target"] = page["anchor_repair_target"]
        work_items.append(item)
    return work_items


def page_governance_create_direct_record_evidence_work_items(
    pages: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    work_items_by_key: dict[str, dict[str, Any]] = {}
    for page in pages:
        if str(page.get("remediation_type") or "") != "create_direct_record":
            continue
        creation_target = page.get("creation_target") if isinstance(page.get("creation_target"), dict) else {}
        for detail in creation_target.get("manual_fill_field_details", []):
            if detail.get("status") not in {"missing", "failed"}:
                continue
            evidence_key = str(detail.get("name") or "")
            if not evidence_key:
                continue
            item = work_items_by_key.setdefault(
                evidence_key,
                {
                    "evidence_key": evidence_key,
                    "kind": str(detail.get("kind") or ""),
                    "status": str(detail.get("status") or ""),
                    "pages": [],
                    "evidence_hints": list(detail.get("evidence_hints", [])),
                    "approval_boundary": "record_creation_evidence_collection_only",
                    "evidence_scope": {
                        "writes_governance_records": False,
                        "approves_metric_or_page": False,
                        "proves_page_execution": False,
                        "executes_tool_calls": False,
                        "runs_ui_or_api_smoke": False,
                        "captures_business_owner_approval": False,
                    },
                },
            )
            item["pages"].append(
                {
                    "page_id": str(page["page_id"]),
                    "page_slug": str(page["page_slug"]),
                }
            )
    work_items = []
    for item in work_items_by_key.values():
        item["page_count"] = len(item["pages"])
        work_items.append(item)
    return sorted(work_items, key=lambda item: str(item["evidence_key"]))


def page_governance_repair_direct_record_evidence_work_items(
    pages: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    work_items_by_key: dict[str, dict[str, Any]] = {}
    for page in pages:
        remediation_type = str(page.get("remediation_type") or "")
        if remediation_type == "create_direct_record":
            continue
        for repair_target in page.get("repair_targets", []):
            page_ref = {
                "page_id": str(page["page_id"]),
                "page_slug": str(page["page_slug"]),
            }
            record_ref = {
                **page_ref,
                "record_location": repair_target.get("record_location", {}),
            }
            evidence_hints = repair_target.get("evidence_hints", {})
            for field in repair_target.get("missing_required_fields", []):
                page_governance_add_repair_evidence_work_item(
                    work_items_by_key,
                    evidence_key=str(field),
                    kind="field",
                    status="missing",
                    page_ref=page_ref,
                    record_ref=record_ref,
                    remediation_type=remediation_type,
                    evidence_hints=list(
                        evidence_hints.get("missing_required_fields", {}).get(str(field), [])
                    ),
                )
            for group in repair_target.get("failed_required_field_groups", []):
                page_governance_add_repair_evidence_work_item(
                    work_items_by_key,
                    evidence_key=str(group),
                    kind="group",
                    status="failed",
                    page_ref=page_ref,
                    record_ref=record_ref,
                    remediation_type=remediation_type,
                    evidence_hints=list(
                        evidence_hints.get("failed_required_field_groups", {}).get(str(group), [])
                    ),
                )
    work_items = []
    for item in work_items_by_key.values():
        item["page_count"] = len(item["pages"])
        item["remediation_types"] = sorted(item["remediation_types"])
        work_items.append(item)
    return sorted(work_items, key=lambda item: str(item["evidence_key"]))


def page_governance_add_repair_evidence_work_item(
    work_items_by_key: dict[str, dict[str, Any]],
    *,
    evidence_key: str,
    kind: str,
    status: str,
    page_ref: dict[str, str],
    record_ref: dict[str, Any],
    remediation_type: str,
    evidence_hints: list[str],
) -> None:
    item = work_items_by_key.setdefault(
        evidence_key,
        {
            "evidence_key": evidence_key,
            "kind": kind,
            "status": status,
            "pages": [],
            "remediation_types": set(),
            "record_locations": [],
            "evidence_hints": evidence_hints,
            "approval_boundary": "record_repair_evidence_collection_only",
            "evidence_scope": {
                "writes_governance_records": False,
                "approves_metric_or_page": False,
                "proves_page_execution": False,
                "executes_tool_calls": False,
                "runs_ui_or_api_smoke": False,
                "captures_business_owner_approval": False,
            },
        },
    )
    item["pages"].append(page_ref)
    item["remediation_types"].add(remediation_type)
    item["record_locations"].append(record_ref)


def page_governance_direct_record_remediation_scope_audit(
    work_item_groups: dict[str, list[dict[str, Any]]],
) -> dict[str, Any]:
    checked_groups = [
        "blocked_by_record_gap_next_steps",
        "create_direct_record_evidence_work_items",
        "create_direct_record_table_anchor_work_items",
        "direct_record_remediation_work_items",
        "repair_direct_record_evidence_work_items",
    ]
    scope_keys = [
        "writes_governance_records",
        "approves_metric_or_page",
        "proves_page_execution",
        "executes_tool_calls",
        "runs_ui_or_api_smoke",
        "captures_business_owner_approval",
    ]
    scope_flags = {key: False for key in scope_keys}
    scope_violations = []
    work_item_count = 0
    for group in checked_groups:
        for index, item in enumerate(work_item_groups.get(group, [])):
            work_item_count += 1
            evidence_scope = item.get("evidence_scope") if isinstance(item, dict) else None
            scope = evidence_scope if isinstance(evidence_scope, dict) else {}
            for key in scope_keys:
                value = scope.get(key)
                if value is True:
                    scope_flags[key] = True
                if value is not False:
                    scope_violations.append(
                        {
                            "work_item_group": group,
                            "work_item_index": index,
                            "scope_key": key,
                            "scope_value": value,
                        }
                    )
    return {
        "work_item_count": work_item_count,
        "checked_work_item_groups": checked_groups,
        "writes_governance_records": scope_flags["writes_governance_records"],
        "approves_metric_or_page": scope_flags["approves_metric_or_page"],
        "proves_page_execution": scope_flags["proves_page_execution"],
        "executes_tool_calls": scope_flags["executes_tool_calls"],
        "runs_ui_or_api_smoke": scope_flags["runs_ui_or_api_smoke"],
        "captures_business_owner_approval": scope_flags["captures_business_owner_approval"],
        "scope_violations": scope_violations,
    }


def page_governance_direct_record_work_type(remediation_type: str) -> str:
    if remediation_type == "complete_direct_record_fields":
        return "complete_existing_direct_record"
    if remediation_type == "repair_primary_page_anchor":
        return "repair_primary_page_anchor"
    return "create_direct_record"


def page_governance_count_values(values: Iterable[str]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for value in values:
        counts[value] = counts.get(value, 0) + 1
    return dict(sorted(counts.items()))


def page_governance_pages_by_check(
    items: list[dict[str, Any]],
    checks_field: str,
) -> dict[str, list[dict[str, str]]]:
    pages_by_check: dict[str, list[dict[str, str]]] = {}
    for item in items:
        page_ref = page_governance_packet_page_ref(item)
        for check in item.get(checks_field, []):
            pages_by_check.setdefault(str(check), []).append(page_ref)
    return dict(sorted(pages_by_check.items()))


def page_governance_pages_by_evidence_check(
    items: list[dict[str, Any]],
    evidence_field: str,
) -> dict[str, list[dict[str, str]]]:
    pages_by_check: dict[str, list[dict[str, str]]] = {}
    for item in items:
        page_ref = page_governance_packet_page_ref(item)
        for evidence in item.get(evidence_field, []):
            check = evidence.get("check") if isinstance(evidence, dict) else None
            if check:
                pages_by_check.setdefault(str(check), []).append(page_ref)
    return dict(sorted(pages_by_check.items()))


def page_governance_manual_review_work_items(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    work_items = []
    assignment_checks = {
        "ui_api_payload_review",
        "live_smoke_evidence_review",
        "business_owner_approval",
    }
    for item in items:
        record_primary_api = page_governance_packet_ready_record_primary_api(item)
        for target in item.get("manual_review_blocker_targets", []):
            if not isinstance(target, dict):
                continue
            check = str(target.get("check") or "")
            if check not in assignment_checks:
                continue
            primary_api = str(record_primary_api or target.get("primary_api") or "")
            review_targets = dict(target.get("review_targets", {}))
            if check == "ui_api_payload_review":
                review_targets["api_payload"] = primary_api
            if check == "live_smoke_evidence_review":
                review_targets["primary_api"] = primary_api
            work_items.append(
                {
                    "check": check,
                    "page_id": str(target.get("page_id") or ""),
                    "page_slug": str(target.get("page_slug") or ""),
                    "frontend_route": str(target.get("frontend_route") or ""),
                    "primary_api": primary_api,
                    "review_targets": review_targets,
                    "approval_boundary": str(target.get("approval_boundary") or "manual_review_only"),
                    "evidence_scope": {
                        "writes_governance_records": False,
                        "approves_metric_or_page": False,
                        "proves_page_execution": False,
                        "runs_ui_or_api_smoke": False,
                        "captures_business_owner_approval": False,
                    },
                }
            )
    return work_items


def page_governance_manual_review_evidence_present_work_items(
    items: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    work_items = []
    for item in items:
        queue_item = item.get("audit_review_queue_item") if isinstance(item, dict) else {}
        if not isinstance(queue_item, dict):
            queue_item = {}
        record_primary_api = page_governance_packet_ready_record_primary_api(item)
        primary_api = str(record_primary_api or queue_item.get("primary_api") or "")
        for evidence in item.get("manual_review_evidence_present", []):
            if not isinstance(evidence, dict):
                continue
            work_items.append(
                {
                    "check": str(evidence.get("check") or ""),
                    "page_id": str(item.get("page_id") or queue_item.get("page_id") or ""),
                    "page_slug": str(item.get("page_slug") or queue_item.get("page_slug") or ""),
                    "frontend_route": str(queue_item.get("frontend_route") or ""),
                    "primary_api": primary_api,
                    "evidence_field": str(evidence.get("evidence_field") or ""),
                    "evidence_value": str(evidence.get("evidence_value") or ""),
                    "review_status": str(evidence.get("status") or "evidence_present_needs_review"),
                    "approval_boundary": "manual_review_evidence_present_review_only",
                    "evidence_scope": {
                        "writes_governance_records": False,
                        "approves_metric_or_page": False,
                        "proves_page_execution": False,
                        "runs_ui_or_api_smoke": False,
                        "captures_business_owner_approval": False,
                    },
                }
            )
    return work_items


def page_governance_manual_review_scope_audit(
    work_items: list[dict[str, Any]] | dict[str, list[dict[str, Any]]],
) -> dict[str, Any]:
    scope_keys = [
        "writes_governance_records",
        "approves_metric_or_page",
        "proves_page_execution",
        "runs_ui_or_api_smoke",
        "captures_business_owner_approval",
    ]
    work_item_groups = (
        {"manual_review_work_items": work_items}
        if isinstance(work_items, list)
        else work_items
    )
    scope_flags = {key: False for key in scope_keys}
    scope_violations = []
    for group, grouped_work_items in work_item_groups.items():
        for index, item in enumerate(grouped_work_items):
            evidence_scope = item.get("evidence_scope") if isinstance(item, dict) else None
            scope = evidence_scope if isinstance(evidence_scope, dict) else {}
            for key in scope_keys:
                value = scope.get(key)
                if value is True:
                    scope_flags[key] = True
                if value is not False:
                    scope_violations.append(
                        {
                            "work_item_group": str(group),
                            "work_item_index": index,
                            "scope_key": key,
                            "scope_value": value,
                        }
                    )
    return {
        "work_item_count": sum(len(grouped_work_items) for grouped_work_items in work_item_groups.values()),
        "checked_work_item_groups": list(work_item_groups),
        "writes_governance_records": scope_flags["writes_governance_records"],
        "approves_metric_or_page": scope_flags["approves_metric_or_page"],
        "proves_page_execution": scope_flags["proves_page_execution"],
        "runs_ui_or_api_smoke": scope_flags["runs_ui_or_api_smoke"],
        "captures_business_owner_approval": scope_flags["captures_business_owner_approval"],
        "scope_violations": scope_violations,
    }


def page_governance_manual_review_mcp_work_items(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    mcp_evidence_checks = {
        "page_contract_review",
        "catalog_date_sampling",
        "lineage_freshness_review",
    }
    work_items_by_check: dict[str, dict[str, Any]] = {}
    for item in items:
        queue_item = item.get("audit_review_queue_item") if isinstance(item, dict) else {}
        if not isinstance(queue_item, dict):
            continue
        for step in queue_item.get("manual_review_steps", []):
            if not isinstance(step, dict) or not step.get("tool_calls"):
                continue
            check = str(step.get("check") or "")
            if check not in mcp_evidence_checks:
                continue
            work_item = work_items_by_check.setdefault(
                check,
                {
                    "check": check,
                    "page_count": 0,
                    "pages": [],
                    "evidence_to_collect": list(step.get("evidence_to_collect", [])),
                    "suggested_tools": list(step.get("suggested_tools", [])),
                    "approval_boundary": "manual_review_mcp_evidence_collection_only",
                    "evidence_scope": {
                        "writes_governance_records": False,
                        "approves_metric_or_page": False,
                        "proves_page_execution": False,
                        "executes_tool_calls": False,
                    },
                },
            )
            work_item["pages"].append(
                {
                    "page_id": str(queue_item.get("page_id") or ""),
                    "page_slug": str(queue_item.get("page_slug") or ""),
                    "tool_calls": list(step.get("tool_calls", [])),
                }
            )
            work_item["page_count"] = len(work_item["pages"])
    return list(work_items_by_check.values())


def page_governance_manual_review_mcp_scope_audit(
    work_items: list[dict[str, Any]],
) -> dict[str, Any]:
    scope_keys = [
        "writes_governance_records",
        "approves_metric_or_page",
        "proves_page_execution",
        "executes_tool_calls",
    ]
    scope_flags = {key: False for key in scope_keys}
    scope_violations = []
    for index, item in enumerate(work_items):
        evidence_scope = item.get("evidence_scope") if isinstance(item, dict) else None
        scope = evidence_scope if isinstance(evidence_scope, dict) else {}
        for key in scope_keys:
            value = scope.get(key)
            if value is True:
                scope_flags[key] = True
            if value is not False:
                scope_violations.append(
                    {
                        "work_item_group": "manual_review_mcp_work_items",
                        "work_item_index": index,
                        "scope_key": key,
                        "scope_value": value,
                    }
                )
    return {
        "work_item_count": len(work_items),
        "checked_work_item_groups": ["manual_review_mcp_work_items"],
        "writes_governance_records": scope_flags["writes_governance_records"],
        "approves_metric_or_page": scope_flags["approves_metric_or_page"],
        "proves_page_execution": scope_flags["proves_page_execution"],
        "executes_tool_calls": scope_flags["executes_tool_calls"],
        "scope_violations": scope_violations,
    }


def page_governance_queue_closure_readiness(
    *,
    page_count: int,
    ready_for_audit_review_count: int,
    blocked_by_record_gaps_count: int,
    manual_review_mcp_work_item_count: int,
    manual_review_blocker_count: int,
    manual_review_evidence_present_count: int,
    closure_approved_count: int,
) -> dict[str, Any]:
    residual_requirements = []
    if blocked_by_record_gaps_count:
        residual_requirements.append("record_gap_remediation")
    if manual_review_mcp_work_item_count:
        residual_requirements.append("mcp_evidence_collection")
    if manual_review_blocker_count:
        residual_requirements.append("manual_review_blockers")
    if manual_review_evidence_present_count:
        residual_requirements.append("present_evidence_review")
    if ready_for_audit_review_count and closure_approved_count < ready_for_audit_review_count:
        residual_requirements.append("business_owner_approval")
    closure_ready_count = min(closure_approved_count, ready_for_audit_review_count)
    return {
        "page_count": page_count,
        "ready_for_audit_review_count": ready_for_audit_review_count,
        "blocked_by_record_gaps_count": blocked_by_record_gaps_count,
        "manual_review_mcp_work_item_count": manual_review_mcp_work_item_count,
        "manual_review_blocker_count": manual_review_blocker_count,
        "manual_review_evidence_present_needs_review_count": manual_review_evidence_present_count,
        "closure_approved_count": closure_approved_count,
        "closure_ready_count": closure_ready_count,
        "closure_blocked_count": page_count - closure_ready_count,
        "queue_grants_closure": False,
        "status": page_governance_queue_closure_status(
            blocked_by_record_gaps_count=blocked_by_record_gaps_count,
            manual_review_mcp_work_item_count=manual_review_mcp_work_item_count,
            manual_review_blocker_count=manual_review_blocker_count,
            manual_review_evidence_present_count=manual_review_evidence_present_count,
            closure_approved_count=closure_approved_count,
            ready_for_audit_review_count=ready_for_audit_review_count,
        ),
        "residual_closure_requirements": residual_requirements,
    }


def page_governance_queue_closure_status(
    *,
    blocked_by_record_gaps_count: int,
    manual_review_mcp_work_item_count: int,
    manual_review_blocker_count: int,
    manual_review_evidence_present_count: int,
    closure_approved_count: int,
    ready_for_audit_review_count: int,
) -> str:
    manual_review_count = (
        manual_review_mcp_work_item_count
        + manual_review_blocker_count
        + manual_review_evidence_present_count
    )
    if blocked_by_record_gaps_count and manual_review_count:
        return "manual_review_and_record_remediation_required"
    if blocked_by_record_gaps_count:
        return "record_remediation_required"
    if manual_review_count:
        return "manual_review_required"
    if closure_approved_count < ready_for_audit_review_count:
        return "business_owner_approval_required"
    return "closure_not_granted_by_queue"


def page_governance_queue_boundary_audit(
    scope_audits: dict[str, dict[str, Any]],
    *,
    work_item_count: int,
) -> dict[str, Any]:
    checked_scope_audits = [
        "manual_review_mcp_scope_audit",
        "manual_review_scope_audit",
        "direct_record_remediation_scope_audit",
    ]
    scope_keys = [
        "writes_governance_records",
        "approves_metric_or_page",
        "proves_page_execution",
        "executes_tool_calls",
        "runs_ui_or_api_smoke",
        "captures_business_owner_approval",
    ]
    scope_flags = {key: False for key in scope_keys}
    scope_violations = []
    for audit_name in checked_scope_audits:
        audit = scope_audits.get(audit_name, {})
        for key in scope_keys:
            if audit.get(key) is True:
                scope_flags[key] = True
        for violation in audit.get("scope_violations", []):
            violation_with_source = dict(violation)
            violation_with_source["scope_audit"] = audit_name
            scope_violations.append(violation_with_source)
    return {
        "work_item_count": work_item_count,
        "checked_scope_audits": checked_scope_audits,
        "writes_governance_records": scope_flags["writes_governance_records"],
        "approves_metric_or_page": scope_flags["approves_metric_or_page"],
        "proves_page_execution": scope_flags["proves_page_execution"],
        "executes_tool_calls": scope_flags["executes_tool_calls"],
        "runs_ui_or_api_smoke": scope_flags["runs_ui_or_api_smoke"],
        "captures_business_owner_approval": scope_flags["captures_business_owner_approval"],
        "scope_violations": scope_violations,
    }


def page_governance_packet_ready_record_primary_api(item: dict[str, Any]) -> str | None:
    queue_item = item.get("audit_review_queue_item")
    if not isinstance(queue_item, dict):
        return None
    for validation in queue_item.get("direct_record_validations", []):
        if not isinstance(validation, dict) or validation.get("validation_status") != "ready_for_audit_review":
            continue
        record = validation.get("record") if isinstance(validation.get("record"), dict) else {}
        primary_api = record.get("primary_api")
        if not governance_record_value_missing(primary_api):
            return str(primary_api)
    return None


def page_governance_packet_page_ref(item: dict[str, Any]) -> dict[str, str]:
    return {
        "page_id": str(item["page_id"]),
        "page_slug": str(item["page_slug"]),
    }


def page_governance_manual_review_evidence_present(queue_item: dict[str, Any]) -> list[dict[str, Any]]:
    evidence_hints = queue_item.get("review_evidence_hints")
    if not isinstance(evidence_hints, dict):
        return []

    present: list[dict[str, Any]] = []
    ui_api_payload_evidence = evidence_hints.get("ui_api_payload_evidence")
    if (
        "ui_api_payload_review" in queue_item.get("remaining_manual_checks", [])
        and not governance_record_value_missing(ui_api_payload_evidence)
    ):
        present.append(
            {
                "check": "ui_api_payload_review",
                "evidence_field": "ui_api_payload_evidence",
                "evidence_value": ui_api_payload_evidence,
                "status": "evidence_present_needs_review",
            }
        )
    live_smoke_evidence = evidence_hints.get("live_smoke_evidence")
    if (
        "live_smoke_evidence_review" in queue_item.get("remaining_manual_checks", [])
        and not governance_record_value_missing(live_smoke_evidence)
    ):
        present.append(
            {
                "check": "live_smoke_evidence_review",
                "evidence_field": "live_smoke_evidence",
                "evidence_value": live_smoke_evidence,
                "status": "evidence_present_needs_review",
            }
        )
    return present


def page_governance_manual_review_blockers(
    queue_item: dict[str, Any],
    evidence_present: list[dict[str, Any]],
) -> list[str]:
    present_checks = {str(item.get("check")) for item in evidence_present}
    return [
        check
        for check in queue_item["remaining_manual_checks"]
        if check in {"ui_api_payload_review", "live_smoke_evidence_review", "business_owner_approval"}
        and check not in present_checks
    ]


def page_governance_manual_review_blocker_targets(
    queue_item: dict[str, Any],
    manual_blockers: list[str],
) -> list[dict[str, Any]]:
    steps = {
        str(step.get("check") or ""): step
        for step in queue_item.get("manual_review_steps", [])
        if isinstance(step, dict)
    }
    targets = []
    for check in manual_blockers:
        step = steps.get(check, {})
        target = {
            "check": check,
            "page_id": str(queue_item["page_id"]),
            "page_slug": str(queue_item["page_slug"]),
            "frontend_route": str(queue_item["frontend_route"]),
            "primary_api": str(queue_item["primary_api"]),
            "evidence_to_collect": list(step.get("evidence_to_collect", [])),
            "suggested_tools": list(step.get("suggested_tools", [])),
            "review_targets": page_governance_manual_review_target_details(check, queue_item),
            "approval_boundary": "manual_review_only",
        }
        targets.append(target)
    return targets


def page_governance_manual_review_target_details(
    check: str,
    queue_item: dict[str, Any],
) -> dict[str, Any]:
    if check == "ui_api_payload_review":
        return {
            "api_payload": str(queue_item["primary_api"]),
            "frontend_route": str(queue_item["frontend_route"]),
            "result_meta_required": True,
            "contract_page_id": str(queue_item["page_id"]),
        }
    if check == "business_owner_approval":
        return {
            "approval_record_page_id": str(queue_item["page_id"]),
            "approval_record_page_slug": str(queue_item["page_slug"]),
            "closure_approved": False,
        }
    if check == "live_smoke_evidence_review":
        return {
            "frontend_route": str(queue_item["frontend_route"]),
            "primary_api": str(queue_item["primary_api"]),
            "visible_state_review_required": True,
            "contract_page_id": str(queue_item["page_id"]),
        }
    return {}


def page_governance_contract_trace_summary(contract_trace: dict[str, Any]) -> dict[str, Any]:
    return {
        "contract_doc_count": len(contract_trace.get("contract_docs", [])),
        "golden_sample_ids": [
            Path(str(sample)).name
            for sample in contract_trace.get("golden_samples", [])
        ],
        "backend_touchpoint_count": len(contract_trace.get("backend_touchpoints", [])),
        "frontend_touchpoint_count": len(contract_trace.get("frontend_touchpoints", [])),
        "test_touchpoint_count": len(contract_trace.get("test_touchpoints", [])),
    }


def page_governance_audit_evidence_packet_disclaimer() -> str:
    return (
        "This packet aggregates read-only MCP evidence for manual audit review; it does not write governance "
        "records, run UI/API smoke checks, prove page/API execution, capture business-owner approval, and does "
        "not approve metric/page formal use."
    )


def page_governance_audit_evidence_packet_scope() -> dict[str, bool]:
    return {
        "writes_governance_records": False,
        "approves_metric_or_page": False,
        "proves_page_execution": False,
        "runs_ui_or_api_smoke": False,
        "captures_business_owner_approval": False,
        "aggregates_mcp_evidence": True,
    }


def page_governance_audit_review_queue_item(page: dict[str, Any]) -> dict[str, Any]:
    remaining_checks = [
        str(check.get("name") or "")
        for check in page["checks"]
        if check.get("status") == "manual_review_required"
    ]
    return {
        **page,
        "review_priority": "manual_review_required",
        "remaining_manual_checks": remaining_checks,
        "manual_review_steps": [
            page_governance_manual_review_step(check, page)
            for check in remaining_checks
        ],
    }


def page_governance_manual_review_step(check: str, page: dict[str, Any]) -> dict[str, Any]:
    page_slug = str(page.get("page_slug") or "")
    page_id = str(page.get("page_id") or "")
    steps = {
        "page_contract_review": {
            "evidence_to_collect": [
                "page contract",
                "metric dictionary",
                "calculation rules",
                "golden samples",
            ],
            "suggested_tools": [
                "moss-metric-contracts.get_page_trace_bundle",
                "moss-metric-contracts.search_contract_docs",
            ],
            "tool_calls": [
                {
                    "tool": "moss-metric-contracts.get_page_trace_bundle",
                    "arguments": {"page_slug": page_slug},
                },
                {
                    "tool": "moss-metric-contracts.search_contract_docs",
                    "arguments": {"query": page_id},
                },
            ],
        },
        "catalog_date_sampling": {
            "evidence_to_collect": [
                "configured page table descriptions",
                "available report/as-of dates",
                "date semantics comparison",
            ],
            "suggested_tools": [
                "moss-data-catalog.get_page_catalog_date_evidence",
                "moss-data-catalog.get_page_catalog_date_coverage",
            ],
            "tool_calls": [
                {
                    "tool": "moss-data-catalog.get_page_catalog_date_evidence",
                    "arguments": {"page_slugs": [page_slug]},
                },
                {
                    "tool": "moss-data-catalog.get_page_catalog_date_coverage",
                    "arguments": {"page_slugs": [page_slug]},
                },
            ],
        },
        "lineage_freshness_review": {
            "evidence_to_collect": [
                "direct lineage freshness",
                "source version",
                "rule version",
                "cache/run identifier",
                "fallback or stale status",
            ],
            "suggested_tools": [
                "moss-lineage-evidence.find_lineage_records",
                "moss-lineage-evidence.get_page_lineage_evidence",
            ],
            "tool_calls": [
                {
                    "tool": "moss-lineage-evidence.find_lineage_records",
                    "arguments": {"query": page_id, "max_results": 8},
                },
                {
                    "tool": "moss-lineage-evidence.get_page_lineage_evidence",
                    "arguments": {"page_slugs": [page_slug], "max_results": 8},
                },
            ],
        },
        "ui_api_payload_review": {
            "evidence_to_collect": [
                "current API payload",
                "result_meta",
                "visible UI state",
                "page contract comparison",
            ],
            "suggested_tools": [
                "page-specific API smoke",
                "frontend page/model tests",
            ],
        },
        "live_smoke_evidence_review": {
            "evidence_to_collect": [
                "live smoke output",
                "browser evidence",
                "visible stale/fallback/no-data state",
            ],
            "suggested_tools": [
                "scripts/codex-verify-page.ps1",
                "scripts/codex-page-smoke.ps1",
            ],
        },
        "business_owner_approval": {
            "evidence_to_collect": [
                "business owner review",
                "approval record",
                "remaining exception decision",
            ],
            "suggested_tools": [
                "manual sign-off",
            ],
        },
    }
    step = steps.get(check, {"evidence_to_collect": [], "suggested_tools": [], "tool_calls": []})
    return {
        "check": check,
        "evidence_to_collect": step["evidence_to_collect"],
        "suggested_tools": step["suggested_tools"],
        **({"tool_calls": step["tool_calls"]} if step.get("tool_calls") else {}),
        "approval_boundary": "manual_review_only",
    }


def page_governance_audit_review_checklist_row(page: dict[str, Any]) -> dict[str, Any]:
    ready_record_count = sum(
        1
        for validation in page["direct_record_validations"]
        if validation["validation_status"] == "ready_for_audit_review"
    )
    incomplete_record_count = sum(
        1
        for validation in page["direct_record_validations"]
        if validation["validation_status"] == "incomplete"
    )
    record_ready = page["validation_status"] == "direct_records_ready_for_audit_review"
    audit_review_status = "ready_for_audit_review" if record_ready else "blocked_by_record_gaps"
    return {
        "page_slug": page["page_slug"],
        "page_id": page["page_id"],
        "page_name": page["page_name"],
        "frontend_route": page["frontend_route"],
        "primary_api": page["primary_api"],
        "approval_status": page["approval_status"],
        "record_formal_use_policy": page["record_formal_use_policy"],
        "record_validation_status": page["validation_status"],
        "audit_review_status": audit_review_status,
        "closure_approved": False,
        "ready_record_count": ready_record_count,
        "incomplete_record_count": incomplete_record_count,
        "direct_record_count": len(page["direct_record_validations"]),
        "direct_record_validations": page["direct_record_validations"],
        "expanded_anchor_record_count": len(page["expanded_anchor_records"]),
        "review_evidence_hints": page_governance_audit_review_evidence_hints(page),
        "checks": page_governance_audit_review_checks(page, ready_record_count),
        "next_actions": page_governance_audit_review_next_actions(record_ready),
        "residual_gaps": page["residual_gaps"],
        "evidence_scope": {
            "writes_governance_records": False,
            "approves_metric_or_page": False,
            "proves_page_execution": False,
            "validates_required_fields": True,
            "checks_contract_docs": False,
            "checks_catalog_date_samples": False,
            "checks_lineage_freshness": False,
            "checks_ui_api_payload": False,
            "checks_live_smoke": False,
        },
    }


def page_governance_audit_review_evidence_hints(page: dict[str, Any]) -> dict[str, Any]:
    ready_record = next(
        (
            validation
            for validation in page["direct_record_validations"]
            if validation["validation_status"] == "ready_for_audit_review"
        ),
        None,
    )
    if ready_record is None:
        return {"status": "unavailable_until_direct_record_ready"}

    record = ready_record.get("record") if isinstance(ready_record.get("record"), dict) else {}
    execution_identifier = None
    if not governance_record_value_missing(record.get("run_id")):
        execution_identifier = {"field": "run_id", "value": record.get("run_id")}
    elif not governance_record_value_missing(record.get("cache_key")):
        execution_identifier = {"field": "cache_key", "value": record.get("cache_key")}

    return {
        "status": "direct_record_ready_for_manual_review",
        "record_location": {
            "stream": ready_record.get("stream"),
            "line": ready_record.get("line"),
            "matched_query": ready_record.get("matched_query"),
        },
        "report_date": record.get("report_date"),
        "basis": record.get("basis"),
        "source_surface": record.get("source_surface"),
        "source_version": record.get("source_version"),
        "rule_version": record.get("rule_version"),
        "result_kind": record.get("result_kind"),
        "tables_used": record.get("tables_used"),
        "execution_identifier": execution_identifier,
        "ui_api_payload_evidence": record.get("ui_api_payload_evidence"),
        "live_smoke_evidence": record.get("live_smoke_evidence"),
        "formal_use_allowed": record.get("formal_use_allowed"),
    }


def page_governance_audit_review_checks(
    page: dict[str, Any],
    ready_record_count: int,
) -> list[dict[str, str]]:
    record_ready = page["validation_status"] == "direct_records_ready_for_audit_review"
    if record_ready:
        record_check = {
            "name": "direct_page_api_record_fields",
            "status": "ready_for_audit_review",
            "evidence": f"{ready_record_count} direct record(s) have required fields and field groups.",
        }
    else:
        record_check = {
            "name": "direct_page_api_record_fields",
            "status": "blocked",
            "evidence": "Direct page/API governance records are missing or incomplete.",
        }
    return [
        record_check,
        {
            "name": "page_contract_review",
            "status": "manual_review_required",
            "evidence": "Review page contract, metric dictionary, calculation rules, and golden samples.",
        },
        {
            "name": "catalog_date_sampling",
            "status": "manual_review_required",
            "evidence": "Run catalog/date evidence for configured page tables and compare report-date semantics.",
        },
        {
            "name": "lineage_freshness_review",
            "status": "manual_review_required",
            "evidence": "Review direct lineage freshness, source/rule/cache versions, fallback, and stale status.",
        },
        {
            "name": "ui_api_payload_review",
            "status": "manual_review_required",
            "evidence": "Compare current API payload and UI state against the page contract and result_meta.",
        },
        {
            "name": "live_smoke_evidence_review",
            "status": "manual_review_required",
            "evidence": "Review current live smoke or browser evidence for visible stale/fallback/no-data states.",
        },
        {
            "name": "business_owner_approval",
            "status": "manual_review_required",
            "evidence": "Business owner approval is still required before closure.",
        },
    ]


def page_governance_audit_review_next_actions(record_ready: bool) -> list[str]:
    if record_ready:
        return [
            "Review page contract and metric dictionary evidence before closure.",
            "Run catalog/date, lineage freshness, UI/API payload, and live smoke checks before approving formal use.",
        ]
    return [
        "Complete direct page/API governance record fields and required field groups first.",
        "Re-run validation, then proceed to contract, catalog/date, lineage, UI/API, and live-smoke review.",
    ]


def page_governance_gap_queue(
    bundles: dict[str, dict[str, Any]],
    streams: dict[str, Path],
    page_slugs: list[str],
    stream_names: list[str],
    *,
    max_results: int,
) -> dict[str, Any]:
    selected_bundles = selected_governance_page_bundles(bundles, page_slugs)
    validation_payload = page_governance_record_validation(
        bundles,
        streams,
        [str(bundle["page_slug"]) for bundle in selected_bundles],
        stream_names,
        max_results=max_results,
    )
    page_order = {
        str(bundle["page_id"]): index
        for index, bundle in enumerate(selected_bundles)
    }
    pages = list(validation_payload["pages"])
    items = [
        page_governance_gap_queue_item(page)
        for page in pages
        if page["validation_status"] != "direct_records_ready_for_audit_review"
    ]
    items.sort(key=lambda item: page_governance_gap_queue_sort_key(item, page_order))
    return {
        "scope": "page-governance-gap-queue",
        "disclaimer": (
            "This read-only queue prioritizes page/API governance record gaps; it does not create governance "
            "records, prove page/API execution, or approve metric/page formal use."
        ),
        "items": items,
        "summary": {
            "page_count": len(pages),
            "open_gap_count": len(items),
            "missing_direct_record_count": sum(
                1 for page in pages if page["validation_status"] == "missing_direct_records"
            ),
            "ready_for_audit_review_count": sum(
                1 for page in pages if page["validation_status"] == "direct_records_ready_for_audit_review"
            ),
            "incomplete_direct_record_page_count": sum(
                1 for page in pages if page["validation_status"] == "direct_records_present_with_gaps"
            ),
            "missing_direct_and_expanded_record_count": sum(
                1
                for item in items
                if item["gap_type"] == "missing_direct_and_expanded_records"
            ),
            "missing_direct_record_expanded_only_count": sum(
                1 for item in items if item["gap_type"] == "missing_direct_record_expanded_only"
            ),
        },
    }


def page_governance_record_blueprint_queue(
    bundles: dict[str, dict[str, Any]],
    streams: dict[str, Path],
    page_slugs: list[str],
    stream_names: list[str],
    *,
    max_results: int,
) -> dict[str, Any]:
    gap_payload = page_governance_gap_queue(
        bundles,
        streams,
        page_slugs,
        stream_names,
        max_results=max_results,
    )
    items = [
        page_governance_record_blueprint_queue_item(bundles, item)
        for item in gap_payload["items"]
    ]
    return {
        "scope": "page-governance-record-blueprint-queue",
        "disclaimer": (
            "This read-only queue attaches candidate record templates to page/API governance gaps; it does not "
            "write governance records, check whether records exist, prove page/API execution, and does not "
            "approve metric/page formal use."
        ),
        "items": items,
        "summary": {
            "page_count": gap_payload["summary"]["page_count"],
            "open_gap_count": gap_payload["summary"]["open_gap_count"],
            "blueprint_count": len(items),
            "template_preflight_ready_count": sum(
                1
                for item in items
                if item["blueprint"]["preflight"]["validation"]["validation_status"] == "ready_for_audit_review"
            ),
            "template_preflight_incomplete_count": sum(
                1
                for item in items
                if item["blueprint"]["preflight"]["validation"]["validation_status"] == "incomplete"
            ),
            "ready_blueprint_count": sum(
                1
                for item in items
                if item["blueprint"]["preflight"]["validation"]["validation_status"] == "ready_for_audit_review"
            ),
            "incomplete_blueprint_count": sum(
                1
                for item in items
                if item["blueprint"]["preflight"]["validation"]["validation_status"] == "incomplete"
            ),
        },
    }


def page_governance_record_blueprint_queue_item(
    bundles: dict[str, dict[str, Any]],
    item: dict[str, Any],
) -> dict[str, Any]:
    blueprint = page_governance_record_blueprint(bundles, str(item["page_id"]))
    return {
        **item,
        "blueprint": blueprint,
        "candidate_record_readiness": page_governance_candidate_record_readiness(item, blueprint),
        "evidence_scope": {
            "writes_governance_records": False,
            "checks_record_existence": False,
            "approves_metric_or_page": False,
            "proves_page_execution": False,
            "validates_required_fields": True,
        },
    }


def page_governance_candidate_record_readiness(
    item: dict[str, Any],
    blueprint: dict[str, Any],
) -> dict[str, Any]:
    validation = blueprint["preflight"]["validation"]
    failed_groups = [
        str(group.get("name") or "")
        for group in validation.get("failed_required_field_groups", [])
    ]
    diagnostics = item.get("direct_record_diagnostics", [])
    diagnostic_missing_fields = sorted(
        {
            str(field)
            for diagnostic in diagnostics
            for field in diagnostic.get("missing_required_fields", [])
        }
    )
    diagnostic_failed_groups = sorted(
        {
            str(group)
            for diagnostic in diagnostics
            for group in diagnostic.get("failed_required_field_groups", [])
        }
    )
    gap_type = str(item.get("gap_type") or "")
    if gap_type == "direct_record_incomplete":
        manual_fill_priority = "complete_existing_direct_record"
    elif gap_type == "missing_direct_and_expanded_records":
        manual_fill_priority = "create_direct_record_and_supporting_lineage"
    elif gap_type == "missing_direct_record_expanded_only":
        manual_fill_priority = "create_direct_record_from_existing_supporting_lineage"
    else:
        manual_fill_priority = "review_required"
    return {
        "manual_fill_priority": manual_fill_priority,
        "validation_status": validation.get("validation_status"),
        "manual_fill_fields": blueprint["manual_fill_fields"],
        "manual_fill_field_details": page_governance_manual_fill_field_details(blueprint),
        "missing_required_fields": validation.get("missing_required_fields", []),
        "failed_required_field_groups": failed_groups,
        "repair_targets": page_governance_repair_targets(diagnostics),
        "existing_direct_record_missing_fields": diagnostic_missing_fields,
        "existing_direct_record_failed_field_groups": diagnostic_failed_groups,
        "accepted_direct_terms": blueprint["accepted_direct_terms"],
        "direct_anchor_targets": blueprint["direct_anchor_targets"],
        "configured_table_names": blueprint["configured_table_names"],
        "explanation": page_governance_candidate_record_readiness_explanation(
            str(item.get("page_id") or ""),
            gap_type,
            validation.get("missing_required_fields", []),
            failed_groups,
            diagnostic_missing_fields,
            diagnostic_failed_groups,
            repair_target_count=len(diagnostics),
        ),
    }


def page_governance_manual_fill_field_details(blueprint: dict[str, Any]) -> list[dict[str, Any]]:
    candidate_record = blueprint["candidate_record"]
    details = []
    for field in blueprint["required_fields"]:
        status = (
            "missing"
            if governance_record_value_missing(candidate_record.get(field))
            else "prefilled"
        )
        detail = {
            "kind": "field",
            "name": field,
            "status": status,
            "value": candidate_record.get(field),
            "satisfying_values": [],
        }
        hints = page_governance_manual_fill_evidence_hints(
            field,
            "field",
            status,
            page_id=str(blueprint.get("page_id") or ""),
        )
        if hints:
            detail["evidence_hints"] = hints
        details.append(detail)
    for group in blueprint["required_field_groups"]:
        group_name = str(group.get("name") or "")
        status = (
            "failed"
            if governance_required_field_group_failed(candidate_record, group)
            else "satisfied"
        )
        detail = {
            "kind": "group",
            "name": group_name,
            "status": status,
            "value": page_governance_required_group_current_value(candidate_record, group_name),
            "satisfying_values": [str(value) for value in list(group.get("one_of") or [])],
        }
        hints = page_governance_manual_fill_evidence_hints(
            group_name,
            "group",
            status,
            page_id=str(blueprint.get("page_id") or ""),
        )
        if hints:
            detail["evidence_hints"] = hints
        details.append(detail)
    return details


def page_governance_manual_fill_evidence_hints(
    name: str,
    kind: str,
    status: str,
    *,
    page_id: str = "",
) -> list[str]:
    if kind == "field" and status == "missing":
        if name == "tables_used" and page_id in PAGE_CATALOG_DATE_DEFERRED_REASONS:
            return [
                "This page has no direct table contract; do not invent tables_used. Resolve through the table_anchor_resolution_target and upstream/page-run evidence.",
            ]
        field_hints = {
            "report_date": [
                "Use catalog/date evidence or the audited page/API payload date binding for the reviewed run; do not infer the date from unrelated upstream tables.",
            ],
            "basis": [
                "Use explicit page contract, source basis, or approval-status evidence for the reviewed run; do not infer formal or analytical basis from the page slug alone.",
            ],
            "source_surface": [
                "Use page/API result metadata, route/service source-surface evidence, or direct lineage metadata for the reviewed run.",
            ],
            "source_version": [
                "Use source manifest, cache, run, or vendor/feed evidence tied to the reviewed run; do not invent a source version.",
            ],
            "rule_version": [
                "Use calculation rule, metric contract, service version, or release evidence tied to the reviewed run; do not invent a rule version.",
            ],
            "created_at": [
                "Use the governance record creation or review timestamp; do not substitute the report date.",
            ],
        }
        return field_hints.get(name, [])
    if kind == "group" and name == "execution_identifier" and status == "failed":
        return [
            "Use a cache_key or run_id from the audited page/API execution evidence; expanded source-table or result-kind anchors are supporting evidence only.",
        ]
    if kind == "group" and name == "record_formal_use_allowed" and status == "failed":
        return [
            "Set formal_use_allowed=false for candidate/pending pages until business-owner closure is separately approved; do not treat record repair as approval.",
        ]
    return []


def page_governance_required_group_current_value(record: dict[str, Any], group_name: str) -> Any:
    if group_name == "record_formal_use_allowed":
        return record.get("formal_use_allowed")
    return None


def page_governance_repair_targets(
    diagnostics: list[dict[str, Any]],
    blueprint: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    repair_targets = []
    for diagnostic in diagnostics:
        repair_target = {
            "record_location": diagnostic.get("record_location", {}),
            "missing_required_fields": diagnostic.get("missing_required_fields", []),
            "failed_required_field_groups": diagnostic.get("failed_required_field_groups", []),
            "direct_anchor_match": diagnostic.get("direct_anchor_match", {}),
            "record_formal_use_allowed": diagnostic.get("record_formal_use_allowed"),
        }
        evidence_hints = page_governance_repair_target_evidence_hints(diagnostic)
        if evidence_hints:
            repair_target["evidence_hints"] = evidence_hints
        if blueprint and diagnostic.get("direct_anchor_match", {}).get("proves_primary_page_anchor") is True:
            repair_target["preflight_completion_template"] = page_governance_completion_preflight_template(
                blueprint,
                diagnostic,
            )
        repair_targets.append(repair_target)
    return repair_targets


def page_governance_completion_preflight_template(
    blueprint: dict[str, Any],
    diagnostic: dict[str, Any],
) -> dict[str, Any]:
    record = page_governance_existing_record_completion_candidate(
        blueprint,
        diagnostic.get("record", {}),
    )
    return {
        "tool": "moss-lineage-evidence.preflight_page_governance_record",
        "arguments": {
            "page_slug": blueprint["page_slug"],
            "record": record,
        },
        "manual_placeholders": page_governance_repaired_record_manual_placeholders(
            blueprint,
            record,
        ),
        "approval_boundary": "preflight_only_no_write_no_approval",
        "evidence_scope": {
            "writes_governance_records": False,
            "approves_metric_or_page": False,
            "proves_page_execution": False,
            "checks_record_existence": False,
        },
    }


def page_governance_existing_record_completion_candidate(
    blueprint: dict[str, Any],
    record: dict[str, Any],
) -> dict[str, Any]:
    candidate = dict(record) if isinstance(record, dict) else {}
    return {
        "page_id": candidate.get("page_id"),
        "page_slug": candidate.get("page_slug"),
        "frontend_route": candidate.get("frontend_route"),
        "primary_api": candidate.get("primary_api"),
        "tables_used": candidate.get("tables_used"),
        "formal_use_allowed": False,
        "report_date": candidate.get("report_date"),
        "basis": candidate.get("basis"),
        "source_surface": candidate.get("source_surface"),
        "source_version": candidate.get("source_version"),
        "rule_version": candidate.get("rule_version"),
        "created_at": candidate.get("created_at"),
        "cache_key": candidate.get("cache_key"),
        "run_id": candidate.get("run_id"),
    }


def page_governance_repair_target_evidence_hints(diagnostic: dict[str, Any]) -> dict[str, dict[str, list[str]]]:
    field_hints = {
        field: hints
        for field in diagnostic.get("missing_required_fields", [])
        if (hints := page_governance_manual_fill_evidence_hints(str(field), "field", "missing"))
    }
    group_hints = {
        group: hints
        for group in diagnostic.get("failed_required_field_groups", [])
        if (hints := page_governance_manual_fill_evidence_hints(str(group), "group", "failed"))
    }
    hints_by_kind = {}
    if field_hints:
        hints_by_kind["missing_required_fields"] = field_hints
    if group_hints:
        hints_by_kind["failed_required_field_groups"] = group_hints
    return hints_by_kind


def page_governance_candidate_record_readiness_explanation(
    page_id: str,
    gap_type: str,
    missing_required_fields: list[str],
    failed_required_field_groups: list[str],
    existing_missing_fields: list[str],
    existing_failed_groups: list[str],
    *,
    repair_target_count: int = 0,
) -> str:
    if gap_type == "direct_record_incomplete":
        missing_text = ", ".join(existing_missing_fields or missing_required_fields) or "required fields"
        group_text = ", ".join(existing_failed_groups or failed_required_field_groups) or "required field groups"
        record_text = (
            f"{repair_target_count} existing direct page/API governance records"
            if repair_target_count > 1
            else "the existing direct page/API governance record"
        )
        return (
            f"Complete {record_text} for {page_id}: fill {missing_text} and "
            f"satisfy {group_text}; this read-only queue does not approve closure."
        )
    if gap_type == "missing_direct_and_expanded_records":
        missing_text = ", ".join(missing_required_fields) or "required fields"
        return (
            f"Create a direct page/API governance record for {page_id}, fill {missing_text}, add an execution "
            "identifier and supporting source-table/result-kind lineage; this read-only queue does not approve "
            "closure."
        )
    if gap_type == "missing_direct_record_expanded_only":
        missing_text = ", ".join(missing_required_fields) or "required fields"
        return (
            f"Create a direct page/API governance record for {page_id} using the existing expanded anchors only "
            f"as supporting evidence, then fill {missing_text}; this read-only queue does not approve closure."
        )
    return (
        f"Review the candidate governance record for {page_id} against required fields and field groups; this "
        "read-only queue does not approve closure."
    )


def page_governance_gap_queue_item(page: dict[str, Any]) -> dict[str, Any]:
    direct_record_count = len(page["direct_record_validations"])
    expanded_anchor_record_count = len(page["expanded_anchor_records"])
    gap_type = page_governance_gap_type(
        page["validation_status"],
        expanded_anchor_record_count=expanded_anchor_record_count,
    )
    return {
        "page_slug": page["page_slug"],
        "page_id": page["page_id"],
        "page_name": page["page_name"],
        "frontend_route": page["frontend_route"],
        "primary_api": page["primary_api"],
        "priority": page_governance_gap_priority(gap_type),
        "gap_type": gap_type,
        "approval_status": page["approval_status"],
        "record_formal_use_policy": page["record_formal_use_policy"],
        "validation_status": page["validation_status"],
        "direct_record_count": direct_record_count,
        "expanded_anchor_record_count": expanded_anchor_record_count,
        "expanded_anchor_samples": page_governance_expanded_anchor_samples(page["expanded_anchor_records"]),
        "accepted_direct_terms": page["accepted_direct_terms"],
        "direct_anchor_targets": page["direct_anchor_targets"],
        "direct_record_diagnostics": page_governance_gap_direct_record_diagnostics(page),
        "residual_gaps": page["residual_gaps"],
        "next_actions": page_governance_gap_next_actions(str(page["page_id"]), gap_type),
        "evidence_scope": page["evidence_scope"],
    }


def page_governance_expanded_anchor_samples(records: list[dict[str, Any]], limit: int = 3) -> list[dict[str, Any]]:
    return [
        {
            "record_location": {
                "stream": record.get("stream"),
                "line": record.get("line"),
                "matched_query": record.get("matched_query"),
            },
            "anchor_type": page_governance_expanded_anchor_type(record),
            "supporting_only": True,
            "proves_page_execution": False,
            "record_summary": page_governance_expanded_anchor_record_summary(record),
        }
        for record in records[:limit]
    ]


def page_governance_expanded_anchor_type(record: dict[str, Any]) -> str:
    raw_record = record.get("record") if isinstance(record.get("record"), dict) else {}
    if raw_record.get("table_name"):
        return "source_table"
    if raw_record.get("result_kind"):
        return "result_kind"
    if raw_record.get("metric_id") or raw_record.get("metric_ids"):
        return "metric"
    if raw_record.get("golden_sample_id"):
        return "golden_sample"
    if record.get("matched_query"):
        return "matched_query_anchor"
    return "expanded_anchor"


def page_governance_expanded_anchor_record_summary(record: dict[str, Any]) -> dict[str, Any]:
    raw_record = record.get("record") if isinstance(record.get("record"), dict) else {}
    summary_fields = [
        "table_name",
        "result_kind",
        "metric_id",
        "metric_ids",
        "golden_sample_id",
        "source_surface",
        "source_version",
        "rule_version",
        "report_date",
        "as_of_date",
        "basis",
    ]
    summary = {
        field: raw_record[field]
        for field in summary_fields
        if field in raw_record and not governance_record_value_missing(raw_record.get(field))
    }
    if not any(
        field in summary
        for field in ("table_name", "result_kind", "metric_id", "metric_ids", "golden_sample_id")
    ) and not governance_record_value_missing(record.get("matched_query")):
        summary = {"matched_query": record["matched_query"], **summary}
    return summary


def page_governance_gap_direct_record_diagnostics(
    page: dict[str, Any],
    *,
    include_records: bool = False,
) -> list[dict[str, Any]]:
    diagnostics = []
    for validation in page["direct_record_validations"]:
        if validation["validation_status"] == "ready_for_audit_review":
            continue
        diagnostic = {
            "record_location": {
                "stream": validation.get("stream"),
                "line": validation.get("line"),
                "matched_query": validation.get("matched_query"),
            },
            "validation_status": validation.get("validation_status"),
            "missing_required_fields": validation.get("missing_required_fields", []),
            "failed_required_field_groups": [
                str(group.get("name") or "")
                for group in validation.get("failed_required_field_groups", [])
            ],
            "direct_anchor_match": validation.get("direct_anchor_match", {}),
            "record_formal_use_allowed": validation.get("record_formal_use_allowed"),
        }
        if include_records:
            diagnostic["record"] = validation.get("record", {})
        diagnostics.append(diagnostic)
    return diagnostics


def page_governance_gap_type(
    validation_status: str,
    *,
    expanded_anchor_record_count: int,
) -> str:
    if validation_status == "missing_direct_records":
        if expanded_anchor_record_count:
            return "missing_direct_record_expanded_only"
        return "missing_direct_and_expanded_records"
    if validation_status == "direct_records_present_with_gaps":
        return "direct_record_incomplete"
    if validation_status == "direct_records_ready_for_audit_review":
        return "ready_for_audit_review"
    return "review_required"


def page_governance_gap_priority(gap_type: str) -> str:
    if gap_type == "missing_direct_and_expanded_records":
        return "P1"
    if gap_type in {"missing_direct_record_expanded_only", "direct_record_incomplete"}:
        return "P2"
    return "P3"


def page_governance_gap_next_actions(page_id: str, gap_type: str) -> list[str]:
    if gap_type == "missing_direct_and_expanded_records":
        return [
            f"Add or locate a direct {page_id}/API governance record for the audited page run or endpoint result.",
            "Add supporting source-table/result-kind lineage records, then validate required fields before audit closure.",
        ]
    if gap_type == "missing_direct_record_expanded_only":
        return [
            f"Add or locate a direct {page_id}/API governance record for the audited page run or endpoint result.",
            "Do not treat expanded anchors as page execution proof; keep them as supporting lineage until direct records exist.",
        ]
    if gap_type == "direct_record_incomplete":
        return [
            f"Complete the existing direct {page_id}/API governance record fields and required field groups.",
            "Re-run validation, then review contract, catalog/date, lineage, and UI/API payload evidence before closure.",
        ]
    return [
        "Review the page contract, catalog/date, lineage, and UI/API payload evidence before making any closure claim.",
    ]


def page_governance_gap_queue_sort_key(
    item: dict[str, Any],
    page_order: dict[str, int],
) -> tuple[int, int, int]:
    priority_rank = {"P1": 0, "P2": 1, "P3": 2}.get(str(item.get("priority") or ""), 9)
    gap_rank = {
        "missing_direct_and_expanded_records": 0,
        "missing_direct_record_expanded_only": 1,
        "direct_record_incomplete": 2,
        "review_required": 3,
        "ready_for_audit_review": 4,
    }.get(str(item.get("gap_type") or ""), 9)
    return (
        priority_rank,
        gap_rank,
        page_order.get(str(item.get("page_id") or ""), len(page_order)),
    )


def page_governance_record_validation_row(
    bundle: dict[str, Any],
    streams: dict[str, Path],
    stream_names: list[str],
    *,
    max_results: int,
) -> dict[str, Any]:
    requirements = page_governance_record_requirements_row(bundle)
    page_id = str(bundle.get("page_id") or "")
    direct_terms = page_direct_lineage_terms(bundle)
    expanded_terms = [
        term
        for term in lineage_query_terms(page_id, LineageEvidenceProvider._QUERY_EXPANSIONS)
        if term.casefold() not in {direct_term.casefold() for direct_term in direct_terms}
    ]
    direct_records = find_lineage_records_for_terms(
        streams,
        stream_names,
        direct_terms,
        max_results=max_results,
        exact_record_value_match=True,
    )
    direct_records, rejected_direct_anchor_records = page_governance_partition_direct_records(
        direct_records,
        requirements,
    )
    direct_record_keys = lineage_record_keys(direct_records)
    expanded_records = find_lineage_records_for_terms(
        streams,
        stream_names,
        expanded_terms,
        max_results=max_results,
        exclude_records={
            *direct_record_keys,
            *lineage_record_keys(rejected_direct_anchor_records),
        },
        longest_terms_first=True,
    )
    expanded_records = [
        *rejected_direct_anchor_records,
        *expanded_records,
    ][:max_results]
    validations = [
        validate_page_governance_record(record, requirements)
        for record in direct_records
    ]
    if not validations:
        validation_status = "missing_direct_records"
    elif any(validation["validation_status"] == "incomplete" for validation in validations):
        validation_status = "direct_records_present_with_gaps"
    elif not any(
        validation.get("direct_anchor_match", {}).get("proves_primary_page_anchor") is True
        for validation in validations
    ):
        validation_status = "direct_records_present_with_gaps"
    else:
        validation_status = "direct_records_ready_for_audit_review"
    return {
        "page_slug": bundle["page_slug"],
        "page_id": page_id,
        "page_name": bundle["page_name"],
        "frontend_route": bundle["frontend_route"],
        "primary_api": bundle["primary_api"],
        "approval_status": requirements["approval_status"],
        "record_formal_use_policy": requirements["record_formal_use_policy"],
        "validation_status": validation_status,
        "accepted_direct_terms": direct_terms,
        "direct_anchor_targets": page_direct_anchor_targets(bundle),
        "direct_record_validations": validations,
        "expanded_anchor_records": expanded_records,
        "residual_gaps": page_governance_validation_residual_gaps(
            validation_status,
            direct_record_validations=validations,
        ),
        "evidence_scope": {
            "writes_governance_records": False,
            "approves_metric_or_page": False,
            "proves_page_execution": False,
            "validates_required_fields": True,
        },
    }


def validate_page_governance_record(record: dict[str, Any], requirements: dict[str, Any]) -> dict[str, Any]:
    raw_record = record.get("record") if isinstance(record.get("record"), dict) else {}
    missing_required_fields = [
        field
        for field in requirements["required_fields"]
        if governance_record_value_missing(raw_record.get(field))
    ]
    failed_required_field_groups = [
        group
        for group in requirements["required_field_groups"]
        if governance_required_field_group_failed(raw_record, group)
    ]
    direct_anchor_match = page_governance_direct_anchor_match(record, requirements)
    validation_status = page_governance_record_validation_status(
        missing_required_fields,
        failed_required_field_groups,
        direct_anchor_match,
    )
    return {
        "stream": record.get("stream"),
        "line": record.get("line"),
        "matched_query": record.get("matched_query"),
        "validation_status": validation_status,
        "missing_required_fields": missing_required_fields,
        "failed_required_field_groups": failed_required_field_groups,
        "direct_anchor_match": direct_anchor_match,
        "record_formal_use_allowed": raw_record.get("formal_use_allowed"),
        "record": raw_record,
        "residual_gaps": page_governance_record_validation_gaps(
            validation_status,
            failed_required_field_groups=failed_required_field_groups,
        ),
    }


def page_governance_record_validation_status(
    missing_required_fields: list[str],
    failed_required_field_groups: list[dict[str, Any]],
    direct_anchor_match: dict[str, Any],
) -> str:
    if direct_anchor_match.get("proves_primary_page_anchor") is not True:
        return "supporting_anchor_only"
    if missing_required_fields or failed_required_field_groups:
        return "incomplete"
    return "ready_for_audit_review"


def page_governance_direct_anchor_match(record: dict[str, Any], requirements: dict[str, Any]) -> dict[str, Any]:
    matched_query = str(record.get("matched_query") or "")
    targets = requirements.get("direct_anchor_targets") if isinstance(requirements.get("direct_anchor_targets"), dict) else {}
    if matched_query == str(targets.get("page_id") or ""):
        anchor_type = "page_id"
    elif matched_query == str(targets.get("frontend_route") or ""):
        anchor_type = "frontend_route"
    elif matched_query == str(targets.get("primary_api") or ""):
        anchor_type = "primary_api"
    elif matched_query in {str(api) for api in targets.get("supporting_apis", [])}:
        anchor_type = "supporting_api"
    else:
        anchor_type = "unknown_direct_anchor"
    return {
        "anchor_type": anchor_type,
        "matched_query": matched_query,
        "proves_primary_page_anchor": anchor_type in {"page_id", "frontend_route", "primary_api"},
    }


def page_governance_partition_direct_records(
    records: list[dict[str, Any]],
    requirements: dict[str, Any],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    direct_records = []
    rejected_records = []
    for record in records:
        if page_governance_record_matches_page_identity(record, requirements):
            direct_records.append(record)
        else:
            rejected_records.append(record)
    return direct_records, rejected_records


def page_governance_record_matches_page_identity(
    record: dict[str, Any],
    requirements: dict[str, Any],
) -> bool:
    identity_values = page_governance_record_identity_values(record)
    if not identity_values:
        return True
    expected_values = {
        str(requirements.get("page_id") or "").casefold(),
        str(requirements.get("page_slug") or "").casefold(),
        str(requirements.get("frontend_route") or "").casefold(),
    }
    expected_values.discard("")
    return any(value.casefold() in expected_values for value in identity_values)


def page_governance_record_identity_values(record: dict[str, Any]) -> list[str]:
    raw_record = record.get("record") if isinstance(record.get("record"), dict) else {}
    sources = [raw_record]
    for nested_key in ("lineage", "result_meta"):
        nested = raw_record.get(nested_key)
        if isinstance(nested, dict):
            sources.append(nested)
    values = []
    for source in sources:
        for field in ("page_id", "page_slug", "frontend_route"):
            value = source.get(field)
            if not governance_record_value_missing(value):
                values.append(str(value))
    return values


def page_governance_record_preflight(
    bundles: dict[str, dict[str, Any]],
    page_slug: str,
    record: dict[str, Any],
) -> dict[str, Any]:
    bundle = page_trace_bundle(bundles, page_slug)
    requirements = page_governance_record_requirements_row(bundle)
    configured_table_names = filter_readiness_anchors(
        PAGE_CATALOG_DATE_TABLES.get(str(bundle.get("page_id") or ""), []),
        limit=80,
    )
    validation = validate_page_governance_record(
        {
            "stream": "candidate_record",
            "line": None,
            "matched_query": str(bundle["page_id"]),
            "record": record,
        },
        requirements,
    )
    return {
        "scope": "page-governance-record-preflight",
        "disclaimer": (
            "This preflight validates a candidate record against checklist fields only; it does not write "
            "governance records, check whether a record exists, prove page/API execution, or approve metric/page "
            "formal use."
        ),
        "page_slug": bundle["page_slug"],
        "page_id": bundle["page_id"],
        "page_name": bundle["page_name"],
        "frontend_route": bundle["frontend_route"],
        "primary_api": bundle["primary_api"],
        "approval_status": requirements["approval_status"],
        "record_formal_use_policy": requirements["record_formal_use_policy"],
        "accepted_direct_terms": requirements["accepted_direct_terms"],
        "direct_anchor_targets": requirements["direct_anchor_targets"],
        "configured_table_names": configured_table_names,
        "required_fields": requirements["required_fields"],
        "required_field_groups": requirements["required_field_groups"],
        "validation": validation,
        "evidence_scope": {
            "writes_governance_records": False,
            "checks_record_existence": False,
            "approves_metric_or_page": False,
            "proves_page_execution": False,
            "validates_required_fields": True,
        },
    }


def page_governance_record_blueprint(
    bundles: dict[str, dict[str, Any]],
    page_slug: str,
) -> dict[str, Any]:
    bundle = page_trace_bundle(bundles, page_slug)
    requirements = page_governance_record_requirements_row(bundle)
    configured_table_names = filter_readiness_anchors(
        PAGE_CATALOG_DATE_TABLES.get(str(bundle.get("page_id") or ""), []),
        limit=80,
    )
    candidate_record = {
        "page_id": bundle["page_id"],
        "page_slug": bundle["page_slug"],
        "frontend_route": bundle["frontend_route"],
        "primary_api": bundle["primary_api"],
        "report_date": None,
        "basis": None,
        "source_surface": None,
        "tables_used": configured_table_names,
        "source_version": None,
        "rule_version": None,
        "created_at": None,
        "cache_key": None,
        "run_id": None,
        "formal_use_allowed": False,
    }
    preflight = page_governance_record_preflight(bundles, page_slug, candidate_record)
    return {
        "scope": "page-governance-record-blueprint",
        "disclaimer": (
            "This tool builds a candidate record template only; it does not write governance records, check whether "
            "a record exists, prove page/API execution, and does not approve metric/page formal use."
        ),
        "page_slug": bundle["page_slug"],
        "page_id": bundle["page_id"],
        "page_name": bundle["page_name"],
        "frontend_route": bundle["frontend_route"],
        "primary_api": bundle["primary_api"],
        "approval_status": requirements["approval_status"],
        "record_formal_use_policy": requirements["record_formal_use_policy"],
        "accepted_direct_terms": requirements["accepted_direct_terms"],
        "direct_anchor_targets": requirements["direct_anchor_targets"],
        "configured_table_names": configured_table_names,
        "required_fields": requirements["required_fields"],
        "required_field_groups": requirements["required_field_groups"],
        "manual_fill_fields": page_governance_blueprint_manual_fill_fields(
            candidate_record,
            requirements["required_fields"],
            requirements["required_field_groups"],
        ),
        "candidate_record": candidate_record,
        "preflight": preflight,
        "evidence_scope": {
            "writes_governance_records": False,
            "checks_record_existence": False,
            "approves_metric_or_page": False,
            "proves_page_execution": False,
            "validates_required_fields": True,
        },
    }


def page_governance_blueprint_manual_fill_fields(
    candidate_record: dict[str, Any],
    required_fields: list[str],
    required_field_groups: list[dict[str, Any]],
) -> list[str]:
    fields = [
        field
        for field in required_fields
        if governance_record_value_missing(candidate_record.get(field))
    ]
    if any(
        str(group.get("name") or "") == "execution_identifier"
        and governance_required_field_group_failed(candidate_record, group)
        for group in required_field_groups
    ):
        fields.append("cache_key_or_run_id")
    return fields


def governance_record_value_missing(value: Any) -> bool:
    if value is None:
        return True
    if isinstance(value, str):
        return not value.strip()
    if isinstance(value, list | tuple | set | dict):
        return not value
    return False


def governance_required_field_group_failed(record: dict[str, Any], group: dict[str, Any]) -> bool:
    group_name = str(group.get("name") or "")
    allowed_values = list(group.get("one_of") or [])
    if group_name == "execution_identifier":
        return all(governance_record_value_missing(record.get(field)) for field in allowed_values)
    if group_name == "record_formal_use_allowed":
        return not governance_formal_use_allowed_matches(record.get("formal_use_allowed"), allowed_values)
    if group_name == "direct_page_or_api_anchor":
        return not governance_record_contains_any_term(record, allowed_values)
    if group_name == "configured_table_anchor":
        return not governance_record_contains_any_term(record, allowed_values)
    return False


def governance_formal_use_allowed_matches(value: Any, allowed_values: list[Any]) -> bool:
    allowed = {str(item).casefold() for item in allowed_values}
    if value is True:
        serialized = "formal_use_allowed=true"
    elif value is False:
        serialized = "formal_use_allowed=false"
    else:
        serialized = f"formal_use_allowed={value}"
    return serialized.casefold() in allowed


def governance_record_contains_any_term(record: dict[str, Any], terms: list[Any]) -> bool:
    text = json.dumps(record, ensure_ascii=False, sort_keys=True).casefold()
    return any(str(term).casefold() in text for term in terms if str(term).strip())


def page_governance_validation_residual_gaps(
    validation_status: str,
    *,
    direct_record_validations: list[dict[str, Any]] | None = None,
) -> list[str]:
    if validation_status == "direct_records_ready_for_audit_review":
        return [
            "Direct record fields are present, but this still does not prove page execution completeness or metric/page approval.",
        ]
    if validation_status == "direct_records_present_with_gaps":
        if direct_record_validations and all(
            validation.get("direct_anchor_match", {}).get("proves_primary_page_anchor") is not True
            for validation in direct_record_validations
        ):
            return [
                "A primary page/API anchor is missing; supporting API anchors alone cannot route the page to audit review.",
            ]
        return [
            "At least one direct page/API governance record is present but missing required fields or required field-group constraints.",
        ]
    return [
        "A direct page/API governance record is missing; expanded anchors cannot prove page/API execution.",
    ]


def page_governance_record_validation_gaps(
    validation_status: str,
    *,
    failed_required_field_groups: list[dict[str, Any]] | None = None,
) -> list[str]:
    if validation_status == "supporting_anchor_only":
        return [
            "A direct record matched only a supporting API; a primary page/API anchor is missing.",
            "Supporting API anchors alone do not prove the primary page/API execution, even when other required fields are present or repairable.",
        ]
    if validation_status == "ready_for_audit_review":
        return [
            "Required checklist fields are present, but this does not prove page execution completeness and still needs audit review against page contract, lineage, date/catalog, and current UI/API payloads.",
        ]
    failed_group_names = {
        str(group.get("name") or "")
        for group in failed_required_field_groups or []
    }
    if "direct_page_or_api_anchor" in failed_group_names:
        gaps = [
            "A direct page/API anchor is missing; expanded source-table or result-kind anchors cannot prove page/API execution.",
            "Required checklist fields or field groups are missing; this record is not ready for audit review.",
        ]
        if "configured_table_anchor" in failed_group_names:
            gaps.insert(1, "A configured table anchor is missing from the candidate governance record.")
        return gaps
    if "configured_table_anchor" in failed_group_names:
        return [
            "A configured table anchor is missing from the candidate governance record.",
            "Required checklist fields or field groups are missing; this record is not ready for audit review.",
        ]
    return [
        "Required checklist fields or field groups are missing; this record is not ready for audit review.",
    ]


def page_governance_record_requirements_row(bundle: dict[str, Any]) -> dict[str, Any]:
    approval_readiness = page_approval_readiness(bundle, bundle_text(bundle))
    approval_status = approval_readiness["status"]
    required_fields = [
        "page_id",
        "page_slug",
        "frontend_route",
        "primary_api",
        "report_date",
        "basis",
        "source_surface",
        "tables_used",
        "source_version",
        "rule_version",
        "created_at",
    ]
    required_field_groups = [
        {
            "name": "direct_page_or_api_anchor",
            "one_of": page_direct_lineage_terms(bundle),
            "reason": "A direct record must contain at least one accepted page ID, frontend route, primary API, or supporting API anchor.",
        },
        {
            "name": "execution_identifier",
            "one_of": ["cache_key", "run_id"],
            "reason": "A direct record needs either a stable cache key or an execution/run identifier.",
        }
    ]
    configured_table_names = filter_readiness_anchors(
        PAGE_CATALOG_DATE_TABLES.get(str(bundle.get("page_id") or ""), []),
        limit=80,
    )
    if configured_table_names:
        required_field_groups.append(
            {
                "name": "configured_table_anchor",
                "one_of": configured_table_names,
                "reason": "A direct record should include at least one explicitly configured catalog/date table anchor for this page.",
            }
        )
    required_field_groups.append(page_governance_formal_use_field_group(approval_status))
    return {
        "page_slug": bundle["page_slug"],
        "page_id": bundle["page_id"],
        "page_name": bundle["page_name"],
        "frontend_route": bundle["frontend_route"],
        "primary_api": bundle["primary_api"],
        "approval_status": approval_status,
        "approval_status_source": approval_readiness["source"],
        "record_formal_use_policy": page_governance_formal_use_policy(approval_status),
        "direct_record_required": True,
        "accepted_direct_terms": page_direct_lineage_terms(bundle),
        "direct_anchor_targets": page_direct_anchor_targets(bundle),
        "required_fields": required_fields,
        "required_field_groups": required_field_groups,
        "recommended_metadata_fields": [
            "result_kind",
            "metric_ids",
            "golden_sample_id",
        ],
        "recommended_optional_fields": [
            "cache_key",
            "run_id",
            "generated_at",
            "requested_report_date",
            "resolved_report_date",
            "as_of_date",
            "date_basis",
            "quality_flag",
            "fallback_reason",
            "stale_status",
            "evidence_row_count",
            "applied_filters",
        ],
        "status_specific_requirements": page_governance_status_requirements(
            str(bundle.get("page_id") or ""),
            approval_status,
        ),
        "insufficient_evidence_examples": [
            "expanded source-table anchors without a matching page ID, frontend route, API route, or page result kind",
            "metric dictionary or golden-sample references without a page/API run record",
            "cache/source manifest rows that only mention upstream tables",
            "synthetic regression fixtures that do not reflect a real page/API execution",
        ],
        "evidence_scope": {
            "writes_governance_records": False,
            "checks_record_existence": False,
            "approves_metric_or_page": False,
            "proves_page_execution": False,
        },
    }


def page_governance_formal_use_policy(approval_status: str) -> str:
    if approval_status == "formal_or_governed":
        return "may_be_true_only_after_direct_record_and_contract_evidence"
    if approval_status == "candidate_or_pending":
        return "must_be_false_until_candidate_closure"
    if approval_status == "gap_or_observational":
        return "must_be_false_for_gap_or_observational"
    return "must_be_false_for_mixed_or_unclassified"


def page_governance_formal_use_field_group(approval_status: str) -> dict[str, Any]:
    if approval_status == "formal_or_governed":
        return {
            "name": "record_formal_use_allowed",
            "one_of": ["formal_use_allowed=true", "formal_use_allowed=false"],
            "reason": (
                "Formal/governed page status is not enough; the audited record still needs direct execution, "
                "contract, lineage, date/catalog, and result metadata evidence before true is allowed."
            ),
        }
    return {
        "name": "record_formal_use_allowed",
        "one_of": ["formal_use_allowed=false"],
        "reason": "Candidate, mixed-source, GAP, and unclassified pages must not claim formal-use approval.",
    }


def page_governance_status_requirements(page_id: str, approval_status: str) -> list[str]:
    if approval_status == "formal_or_governed":
        return [
            "formal_or_governed pages still need a direct page/API governance record for the audited execution.",
            "formal_use_allowed may be true only when the record also matches page contract, metric dictionary, golden sample, source lineage, and date/catalog evidence.",
        ]
    if approval_status == "candidate_or_pending":
        return [
            "candidate_or_pending page records must remain false for formal_use_allowed until dictionary, page-contract, golden-sample, lineage, and catalog/date closure exist.",
            "Record candidate basis, warning/quality state, source tables, report-date binding, and why approval is still pending.",
        ]
    if approval_status == "mixed_source_or_observational":
        return [
            "mixed_source_or_observational page records must keep formal_use_allowed=false for the full page unless a narrower governed fragment is separately identified.",
            "Record which fields are formal, analytical, supplemental, stale, fallback, or observational instead of collapsing the page into full-page formal truth.",
        ]
    if approval_status == "gap_or_observational":
        return [
            f"GAP/observational records for {page_id} must keep formal_use_allowed=false.",
            "Do not create PAGE-STOCK, MTR, golden-sample, trading-instruction, or formal page-closure claims from observational records.",
        ]
    return [
        "unclassified pages require explicit approval-status mapping before governance records can be used for audit closure.",
        "Keep formal_use_allowed=false until the page status is classified and direct evidence is reviewed.",
    ]


def page_lineage_evidence_row(
    bundle: dict[str, Any],
    streams: dict[str, Path],
    stream_names: list[str],
    *,
    max_results: int,
) -> dict[str, Any]:
    page_id = str(bundle.get("page_id") or "")
    direct_terms = page_direct_lineage_terms(bundle)
    expanded_terms = [
        term
        for term in lineage_query_terms(page_id, LineageEvidenceProvider._QUERY_EXPANSIONS)
        if term.casefold() not in {direct_term.casefold() for direct_term in direct_terms}
    ]
    direct_records = find_lineage_records_for_terms(
        streams,
        stream_names,
        direct_terms,
        max_results=max_results,
    )
    requirements = page_governance_record_requirements_row(bundle)
    direct_records, rejected_direct_anchor_records = page_governance_partition_direct_records(
        direct_records,
        requirements,
    )
    direct_record_keys = lineage_record_keys(direct_records)
    expanded_records = find_lineage_records_for_terms(
        streams,
        stream_names,
        expanded_terms,
        max_results=max_results,
        exclude_records={
            *direct_record_keys,
            *lineage_record_keys(rejected_direct_anchor_records),
        },
        longest_terms_first=True,
    )
    expanded_records = [
        *rejected_direct_anchor_records,
        *expanded_records,
    ][:max_results]
    if direct_records:
        lineage_status = "direct_page_or_api_records_present"
    elif expanded_records:
        lineage_status = "expanded_anchor_only"
    else:
        lineage_status = "missing"
    return {
        "page_slug": bundle["page_slug"],
        "page_id": page_id,
        "page_name": bundle["page_name"],
        "frontend_route": bundle["frontend_route"],
        "primary_api": bundle["primary_api"],
        "lineage_status": lineage_status,
        "direct_query_terms": direct_terms,
        "expanded_query_terms": expanded_terms,
        "direct_page_or_api_records": direct_records,
        "expanded_anchor_records": expanded_records,
        "residual_gaps": page_lineage_residual_gaps(lineage_status),
        "recommended_next_actions": page_lineage_recommended_next_actions(page_id, lineage_status),
    }


def page_direct_lineage_terms(bundle: dict[str, Any]) -> list[str]:
    targets = page_direct_anchor_targets(bundle)
    direct_terms = [
        targets["page_id"],
        targets["frontend_route"],
        targets["primary_api"],
        *targets["supporting_apis"],
    ]
    return filter_readiness_anchors(direct_terms, limit=80)


def page_direct_anchor_targets(bundle: dict[str, Any]) -> dict[str, Any]:
    return {
        "page_id": str(bundle.get("page_id") or ""),
        "frontend_route": str(bundle.get("frontend_route") or ""),
        "primary_api": str(bundle.get("primary_api") or ""),
        "supporting_apis": [
            str(api)
            for api in list(bundle.get("supporting_apis") or [])
            if str(api).strip()
        ],
    }


def find_lineage_records_for_terms(
    streams: dict[str, Path],
    stream_names: list[str],
    terms: list[str],
    *,
    max_results: int,
    exclude_records: set[tuple[str, int]] | None = None,
    longest_terms_first: bool = False,
    exact_record_value_match: bool = False,
) -> list[dict[str, Any]]:
    records = []
    seen_records: set[tuple[str, int]] = set()
    excluded = exclude_records or set()
    query_terms = sorted(terms, key=len, reverse=True) if longest_terms_first else terms
    for stream in stream_names:
        path = streams.get(stream)
        if path is None:
            raise McpError(-32602, f"Unknown governance stream: {stream}")
        for term in query_terms:
            for record in find_jsonl_records(path, stream=stream, query=term, max_results=max_results):
                if exact_record_value_match and not lineage_record_has_exact_value(record, term):
                    continue
                record_key = (str(record.get("stream") or stream), int(record.get("line") or 0))
                if record_key in excluded:
                    continue
                if record_key in seen_records:
                    continue
                seen_records.add(record_key)
                records.append({"matched_query": term, **record})
                if len(records) >= max_results:
                    return records
    return records


def lineage_record_has_exact_value(record: dict[str, Any], term: str) -> bool:
    raw_record = record.get("record")
    return lineage_value_matches_term(raw_record, term)


def lineage_value_matches_term(value: Any, term: str) -> bool:
    needle = term.casefold()
    if isinstance(value, str):
        return value.casefold() == needle
    if isinstance(value, list | tuple | set):
        return any(lineage_value_matches_term(item, term) for item in value)
    if isinstance(value, dict):
        return any(lineage_value_matches_term(item, term) for item in value.values())
    return False


def lineage_record_keys(records: list[dict[str, Any]]) -> set[tuple[str, int]]:
    return {
        (str(record.get("stream") or ""), int(record.get("line") or 0))
        for record in records
    }


def page_lineage_residual_gaps(lineage_status: str) -> list[str]:
    if lineage_status == "direct_page_or_api_records_present":
        return [
            "Direct page/API governance records are present, but this still does not prove page execution completeness or metric approval.",
        ]
    if lineage_status == "expanded_anchor_only":
        return [
            "Expanded source-table or metric-anchor records exist, but a direct page/API governance record is missing.",
        ]
    return [
        "No direct page/API or expanded anchor governance records were found in the selected streams.",
    ]


def page_lineage_recommended_next_actions(page_id: str, lineage_status: str) -> list[str]:
    if lineage_status == "direct_page_or_api_records_present":
        return [
            f"Review the direct {page_id}/API governance records and verify page/API execution completeness, report-date binding, source versions, and result metadata before any closure claim.",
            "Confirm direct records align with the page contract, metric dictionary, golden samples, and current UI/API payloads.",
        ]
    if lineage_status == "expanded_anchor_only":
        return [
            f"Add or locate a direct {page_id}/API governance record for the page run or endpoint result being audited.",
            "Do not treat expanded anchor records as page execution proof until direct page/API records exist.",
        ]
    return [
        f"Add or locate both direct {page_id}/API governance records and supporting source-table/result-kind lineage records before audit closure.",
    ]


def golden_sample_status(bundle: dict[str, Any], approval_status: str) -> str:
    golden_samples = list(bundle.get("golden_samples") or [])
    if not golden_samples:
        return "missing"
    text = bundle_text(bundle).casefold()
    if approval_status != "formal_or_governed":
        if "dto" in text or "page headline" in text or "page-level dto" in text:
            return "page_dto_only"
        return "supporting_or_fragment_only"
    return "approved"


def lineage_readiness(bundle: dict[str, Any]) -> dict[str, Any]:
    page_id = str(bundle.get("page_id") or "")
    anchors = lineage_query_terms(page_id, LineageEvidenceProvider._QUERY_EXPANSIONS)
    has_query_mapping = len(anchors) > 1
    if len(anchors) <= 1:
        anchors = []
    contract_anchors = [
        item
        for item in list(bundle.get("truth_chain") or [])
        if is_contract_readiness_anchor(str(item))
    ]
    filtered_anchors = filter_readiness_anchors([*anchors, *contract_anchors])
    if has_query_mapping:
        status = "query_mapping_present"
    elif contract_anchors:
        status = "contract_anchor_only"
    else:
        status = "missing"
    return {"status": status, "anchors": filtered_anchors}


def catalog_date_readiness_anchors(bundle: dict[str, Any], lineage_anchors: list[str]) -> list[str]:
    combined_anchors = [
        *lineage_anchors,
        *list(bundle.get("truth_chain") or []),
        *list(bundle.get("backend_touchpoints") or []),
        *list(bundle.get("verification_focus") or []),
    ]
    return filter_readiness_anchors(
        [
            anchor
            for anchor in combined_anchors
            if is_catalog_date_anchor(anchor) or is_source_contract_anchor(anchor)
        ]
    )


def is_catalog_date_anchor(anchor: str) -> bool:
    text = anchor.casefold()
    return any(
        marker in text
        for marker in (
            "fact_",
            "_fact",
            "rv_",
            "cv_",
            "read_model",
            "snapshot",
            "workbook",
            "ledger",
            "qdb",
            "fx_daily_mid",
            "choice_",
            "market_data_series_category",
            "livermore",
            "report_date",
            "as_of_date",
            "trade_date",
        )
    )


def is_source_contract_anchor(anchor: str) -> bool:
    text = anchor.casefold()
    return "source_contract" in text or "source-contract" in text


def is_contract_readiness_anchor(anchor: str) -> bool:
    return any(marker in anchor for marker in ("PAGE-", "MTR-", "GAP-", "GS-"))


def filter_readiness_anchors(anchors: list[str], *, limit: int = 40) -> list[str]:
    filtered: list[str] = []
    seen: set[str] = set()
    for anchor in anchors:
        normalized = str(anchor).strip()
        if not normalized:
            continue
        key = normalized.casefold()
        if key in seen:
            continue
        seen.add(key)
        filtered.append(normalized)
        if len(filtered) >= limit:
            break
    return filtered


def residual_evidence_gaps(bundle: dict[str, Any], approval_status: str, golden_status: str) -> list[str]:
    page_id = str(bundle.get("page_id") or "")
    gaps = [
        "full data-catalog/date review required before page-level closure.",
        "direct page-keyed governance records are still required before treating this as proof of a specific page/API execution.",
    ]
    if approval_status == "candidate_or_pending":
        gaps.append("Candidate metric dictionary-level approval remains pending.")
    if approval_status == "mixed_source_or_observational":
        gaps.append("Mixed-source page cannot be collapsed into full-page formal truth.")
    if approval_status == "gap_or_observational":
        gaps.append("GAP/observational route lacks standalone formal page contract closure.")
    if golden_status == "missing":
        gaps.append("dedicated golden sample is missing for the page-level metric surface.")
    elif golden_status != "approved":
        gaps.append("Existing golden sample is supporting or page DTO evidence only, not dictionary-level approval.")
    if page_id == "PAGE-BOND-001":
        gaps.append("MTR-BOND-* dictionary-level approval remains pending.")
    if page_id == "PAGE-BOND-ANALYSIS-001":
        gaps.append("Bond-analysis direct candidate contract is routed, but owner approval, governance validation, and manual audit closure remain pending.")
        gaps.append("GS-BOND-HEADLINE-A belongs to /bond-dashboard and must not certify /bond-analysis.")
        gaps.append("Direct fixed-income metric certification remains missing for DV01, duration, KRD, yield/YTM, bp movement, credit-spread, holdings, accounting-class, and action-attribution PnL.")
    if page_id == "PAGE-OPS-001":
        gaps.append("GAP-OPS-MACRO-FX mixed-source strip remains open; do not create MTR-OPS-* from this matrix.")
    if page_id == "GAP-STOCK-ANALYSIS-PAGE":
        gaps.append("Stock-analysis observational lane is routed, but owner approval, governance validation, and manual audit closure remain pending.")
        gaps.append("Trading instructions, PAGE-STOCK contracts, MTR-* creation, and formal approval remain out of scope.")
        gaps.append("Dedicated sample GS-STOCK-ANALYSIS-OBS-A is page DTO evidence only, not formal stock-analysis truth.")
    return gaps


def list_golden_samples(*, limit: int) -> list[dict[str, Any]]:
    root = REPO_ROOT / "tests" / "golden_samples"
    if not root.is_dir():
        return []
    samples = []
    for path in sorted(root.iterdir()):
        if not path.is_dir():
            continue
        samples.append(
            {
                "sample_id": path.name,
                "request": (path / "request.json").is_file(),
                "response": (path / "response.json").is_file(),
                "assertions": (path / "assertions.md").is_file(),
                "approval": (path / "approval.md").is_file(),
            }
        )
        if len(samples) >= limit:
            break
    return samples


def search_files(paths: Any, *, query: str, max_results: int) -> list[dict[str, Any]]:
    needle = query.casefold()
    matches: list[dict[str, Any]] = []
    for path in paths:
        safe_path = assert_repo_path(Path(path))
        if not safe_path.is_file():
            continue
        for lineno, line in enumerate(safe_path.read_text(encoding="utf-8", errors="replace").splitlines(), start=1):
            if needle in line.casefold():
                matches.append(
                    {
                        "path": str(safe_path.relative_to(REPO_ROOT)),
                        "line": lineno,
                        "text": line.strip()[:500],
                    }
                )
                if len(matches) >= max_results:
                    return matches
    return matches


def stream_status(path: Path) -> dict[str, Any]:
    return {
        "path": str(path),
        "exists": path.is_file(),
        "bytes": path.stat().st_size if path.is_file() else 0,
        "latest_records": read_jsonl_tail(path, limit=2) if path.is_file() else [],
    }


def read_jsonl_tail(path: Path, *, limit: int) -> list[dict[str, Any]]:
    if not path.is_file():
        return []
    lines = tail_lines(path, limit=limit)
    records = []
    for line in lines:
        record = parse_json_line(line)
        if record is not None:
            records.append(record)
    return records


def tail_lines(path: Path, *, limit: int) -> list[str]:
    # Governance streams are append-only JSONL. A bounded backward scan avoids
    # loading large lineage indices into memory.
    block_size = 8192
    data = b""
    with path.open("rb") as handle:
        handle.seek(0, os.SEEK_END)
        position = handle.tell()
        while position > 0 and data.count(b"\n") <= limit:
            read_size = min(block_size, position)
            position -= read_size
            handle.seek(position)
            data = handle.read(read_size) + data
    lines = [line for line in data.decode("utf-8", errors="replace").splitlines() if line.strip()]
    return lines[-limit:]


def find_jsonl_records(path: Path, *, stream: str, query: str, max_results: int) -> list[dict[str, Any]]:
    if not path.is_file():
        return []
    needle = query.casefold()
    matches: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8", errors="replace") as handle:
        for line_number, line in enumerate(handle, start=1):
            if needle not in line.casefold():
                continue
            record = parse_json_line(line) or {"raw": line.strip()}
            matches.append({"stream": stream, "line": line_number, "record": record})
            if len(matches) >= max_results:
                break
    return matches


def lineage_query_terms(query: str, expansions: dict[str, list[str]]) -> list[str]:
    terms: list[str] = []
    seen: set[str] = set()
    for term in [query, *expansions.get(query.casefold(), [])]:
        normalized = term.strip()
        if not normalized or normalized.casefold() in seen:
            continue
        seen.add(normalized.casefold())
        terms.append(normalized)
    return terms


def parse_json_line(line: str) -> dict[str, Any] | None:
    try:
        value = json.loads(line)
    except json.JSONDecodeError:
        return None
    return value if isinstance(value, dict) else {"value": value}


def schema_registry_summary(schema_dir: Path) -> dict[str, Any]:
    if not schema_dir.is_dir():
        return {"path": str(schema_dir), "exists": False, "files": []}
    files = []
    for path in sorted(schema_dir.glob("*.sql")):
        files.append(
            {
                "path": str(path.relative_to(REPO_ROOT)),
                "bytes": path.stat().st_size,
            }
        )
    manifest = schema_dir / "manifest.json"
    return {
        "path": str(schema_dir.relative_to(REPO_ROOT)),
        "exists": True,
        "manifest": read_json_file(manifest) if manifest.is_file() else None,
        "files": files,
    }


def read_json_file(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None


def duckdb_tables(duckdb_path: Path, *, limit: int) -> list[dict[str, Any]]:
    conn = open_duckdb_read_only(duckdb_path)
    if conn is None:
        return []
    try:
        rows = conn.execute(
            """
            select table_schema, table_name, table_type
            from information_schema.tables
            where table_schema not in ('information_schema', 'pg_catalog')
            order by table_schema, table_name
            limit ?
            """,
            [limit],
        ).fetchall()
        return [
            {"schema": str(schema), "table": str(table), "type": str(table_type)}
            for schema, table, table_type in rows
        ]
    finally:
        conn.close()


def duckdb_quality_targets(duckdb_path: Path, *, limit: int) -> list[dict[str, Any]]:
    conn = open_duckdb_read_only(duckdb_path)
    if conn is None:
        return []
    try:
        rows = conn.execute(
            """
            with date_columns as (
                select
                    table_schema,
                    table_name,
                    string_agg(column_name, ', ' order by column_name) as date_columns
                from information_schema.columns
                where column_name in ('report_date', 'as_of_date')
                group by table_schema, table_name
            )
            select
                t.table_schema,
                t.table_name,
                t.table_type,
                coalesce(d.date_columns, '') as date_columns
            from information_schema.tables t
            left join date_columns d
                on d.table_schema = t.table_schema
               and d.table_name = t.table_name
            where t.table_schema not in ('information_schema', 'pg_catalog')
            order by t.table_schema, t.table_name
            limit ?
            """,
            [limit],
        ).fetchall()
        return [
            {
                "table_name": f"{schema}.{table}",
                "schema": str(schema),
                "table": str(table),
                "type": str(table_type),
                "date_columns": [part.strip() for part in str(date_columns).split(",") if part.strip()],
            }
            for schema, table, table_type, date_columns in rows
        ]
    finally:
        conn.close()


def describe_duckdb_table(duckdb_path: Path, table_name: str) -> dict[str, Any]:
    validate_identifier(table_name, "table_name")
    conn = require_duckdb(duckdb_path)
    try:
        metadata = duckdb_table_metadata(conn, table_name)
        return {
            "table_name": table_name,
            "columns": [
                {"name": item["name"], "type": item["type"], "nullable": item["nullable"]}
                for item in metadata["columns"]
            ],
        }
    finally:
        conn.close()


def list_available_dates(duckdb_path: Path, table_name: str, date_column: str, *, limit: int) -> dict[str, Any]:
    validate_identifier(table_name, "table_name")
    validate_identifier(date_column, "date_column")
    describe_duckdb_table(duckdb_path, table_name)
    conn = require_duckdb(duckdb_path)
    try:
        quoted_table = ".".join(quote_identifier(part) for part in split_table_name(table_name))
        quoted_column = quote_identifier(date_column)
        rows = conn.execute(
            f"select distinct cast({quoted_column} as varchar) as value from {quoted_table} "
            "where {column} is not null order by value desc limit ?".format(column=quoted_column),
            [limit],
        ).fetchall()
        return {
            "table_name": table_name,
            "date_column": date_column,
            "values": [str(row[0]) for row in rows],
        }
    finally:
        conn.close()


def open_duckdb_read_only(duckdb_path: Path) -> Any | None:
    if not duckdb_path.is_file():
        return None
    try:
        import duckdb  # type: ignore[import-not-found]
    except ImportError:
        return None
    try:
        return duckdb.connect(str(duckdb_path), read_only=True)
    except Exception:
        return None


def require_duckdb(duckdb_path: Path) -> Any:
    if not duckdb_path.is_file():
        raise McpError(-32602, f"DuckDB file does not exist: {duckdb_path}")
    try:
        import duckdb  # type: ignore[import-not-found]
    except ImportError as exc:
        raise McpError(-32603, "duckdb package is not installed in this Python environment.") from exc
    try:
        return duckdb.connect(str(duckdb_path), read_only=True)
    except Exception as exc:
        raise McpError(-32603, f"Could not open DuckDB read-only: {exc}") from exc


def duckdb_table_metadata(conn: Any, table_name: str) -> dict[str, Any]:
    schema_name, bare_table_name = split_table_name(table_name)
    object_rows = conn.execute(
        """
        select table_type
        from information_schema.tables
        where table_schema = ? and table_name = ?
        """,
        [schema_name, bare_table_name],
    ).fetchall()
    if not object_rows:
        raise McpError(-32602, f"Unknown table: {table_name}")

    column_rows = conn.execute(
        """
        select column_name, data_type, is_nullable
        from information_schema.columns
        where table_schema = ? and table_name = ?
        order by ordinal_position
        """,
        [schema_name, bare_table_name],
    ).fetchall()
    if not column_rows:
        raise McpError(-32602, f"Unknown table: {table_name}")

    return {
        "schema_name": schema_name,
        "table_name": bare_table_name,
        "object_type": str(object_rows[0][0]),
        "columns": [
            {"name": str(column), "type": str(data_type), "nullable": str(nullable)}
            for column, data_type, nullable in column_rows
        ],
    }


def duckdb_quality_summary(duckdb_path: Path, table_name: str, *, column_limit: int) -> dict[str, Any]:
    validate_identifier(table_name, "table_name")
    if column_limit < 1 or column_limit > 100:
        raise McpError(-32602, "column_limit must be between 1 and 100.")

    conn = require_duckdb(duckdb_path)
    try:
        metadata = duckdb_table_metadata(conn, table_name)
        qualified_table = ".".join(
            quote_identifier(part) for part in (metadata["schema_name"], metadata["table_name"])
        )
        columns = metadata["columns"]
        preview_columns = columns[:column_limit]

        row_count = int(conn.execute(f"select count(*) from {qualified_table}").fetchone()[0])
        null_counts = duckdb_null_counts(conn, qualified_table, preview_columns)
        date_coverage = duckdb_date_coverage(conn, qualified_table, columns)

        return {
            "table_name": f'{metadata["schema_name"]}.{metadata["table_name"]}',
            "object_type": metadata["object_type"],
            "row_count": row_count,
            "column_count": len(columns),
            "profiled_columns": [column["name"] for column in preview_columns],
            "columns": columns,
            "null_counts": null_counts,
            "date_coverage": date_coverage,
            "golden_sample_matches": find_golden_sample_mentions(metadata["table_name"], limit=10),
        }
    finally:
        conn.close()


def duckdb_null_counts(conn: Any, qualified_table: str, columns: list[dict[str, Any]]) -> dict[str, int]:
    if not columns:
        return {}
    expressions = []
    aliases = []
    for index, column in enumerate(columns):
        alias = f"c{index}"
        aliases.append((alias, column["name"]))
        expressions.append(
            f"sum(case when {quote_identifier(column['name'])} is null then 1 else 0 end) as {quote_identifier(alias)}"
        )
    row = conn.execute(f"select {', '.join(expressions)} from {qualified_table}").fetchone()
    return {column_name: int(row[index]) for index, (_, column_name) in enumerate(aliases)}


def duckdb_date_coverage(conn: Any, qualified_table: str, columns: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    coverage: dict[str, dict[str, Any]] = {}
    for column in columns:
        column_name = column["name"]
        if column_name not in {"report_date", "as_of_date"}:
            continue
        quoted_column = quote_identifier(column_name)
        row = conn.execute(
            f"""
            select
                cast(min({quoted_column}) as varchar),
                cast(max({quoted_column}) as varchar),
                sum(case when {quoted_column} is null then 1 else 0 end),
                count(distinct {quoted_column}) filter (where {quoted_column} is not null)
            from {qualified_table}
            """
        ).fetchone()
        coverage[column_name] = {
            "min": row[0],
            "max": row[1],
            "null_count": int(row[2]),
            "distinct_non_null_count": int(row[3]),
        }
    return coverage


def find_golden_sample_mentions(query: str, *, limit: int) -> list[dict[str, Any]]:
    paths = []
    catalog = REPO_ROOT / "docs" / "golden_sample_catalog.md"
    if catalog.is_file():
        paths.append(catalog)

    root = REPO_ROOT / "tests" / "golden_samples"
    if root.is_dir():
        for sample_dir in sorted(root.iterdir()):
            if not sample_dir.is_dir():
                continue
            for name in ("request.json", "response.json", "assertions.md"):
                path = sample_dir / name
                if path.is_file():
                    paths.append(path)

    return search_files(paths, query=query, max_results=limit)


def validate_identifier(value: str, field: str) -> None:
    if not value:
        raise McpError(-32602, f"{field} is required.")
    if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*(\.[A-Za-z_][A-Za-z0-9_]*)?", value):
        raise McpError(-32602, f"{field} must be an identifier, optionally schema-qualified.")


def split_table_name(table_name: str) -> tuple[str, str]:
    if "." in table_name:
        schema_name, bare_table_name = table_name.split(".", 1)
        return schema_name, bare_table_name
    return "main", table_name


def quote_identifier(value: str) -> str:
    return '"' + value.replace('"', '""') + '"'


if __name__ == "__main__":
    raise SystemExit(main())
