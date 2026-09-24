from __future__ import annotations

from tests.helpers import ROOT

DOCS_DIR = ROOT / "docs"


def _read_doc(name: str) -> str:
    return (DOCS_DIR / name).read_text(encoding="utf-8")


def test_dashboard_page_contract_documents_snapshot_mvp_matrix():
    page_contracts = _read_doc("page_contracts.md")
    cockpit_contract = _read_doc("dashboard_cockpit_contract.md")
    dashboard_contract = page_contracts.split("## 5. PAGE-DASH-001", maxsplit=1)[1].split(
        "## 6. PAGE-BALANCE-001",
        maxsplit=1,
    )[0]

    for required in (
        "`/ui/home/snapshot`",
        "最新严格交集",
        "`landed`",
        "`supplemental`",
        "`reserved`",
        "`demo`",
        "`blocked`",
        "`overview_metrics`",
        "`core_metrics`",
        "`daily_changes`",
        "`market_context`",
        "`risk_overview`",
        "补充读面报告日必须等于首页快照 `report_date`",
    ):
        assert required in dashboard_contract

    for required in (
        "Dashboard Cockpit Contract",
        "`supplemental` only when `result.report_date == snapshot.report_date`",
        "`trade_date`; same date is `landed`, non-same date is `stale`",
        "`reserved`; must not be requested or rendered as normal first-screen conclusions",
        "Components must not directly decide whether mismatched supplemental data is trusted.",
    ):
        assert required in cockpit_contract


def test_dashboard_page_contract_documents_macro_release_context():
    page_contracts = _read_doc("page_contracts.md")
    dashboard_contract = page_contracts.split("## 5. PAGE-DASH-001", maxsplit=1)[1].split(
        "## 6. PAGE-BALANCE-001",
        maxsplit=1,
    )[0]

    for required in (
        "`macro_release_context`",
        "`/ui/home/macro-release-context`",
        "`home.macro_release_context`",
        "`formal_use_allowed=false`",
        "`source_surface=market_data`",
        "`start_date` / `end_date` / `history_limit`",
        "不参与首页主判断",
        "`ready` / `partial` / `stale` / `fallback` / `source_pending` / `error`",
        "`no-data`",
        "`自动数据暂不可用`",
        "静态历史数值回退",
        "`source_pending`",
    ):
        assert required in dashboard_contract


def test_dashboard_cockpit_and_runbook_document_macro_release_context():
    cockpit_contract = _read_doc("dashboard_cockpit_contract.md")
    runbook = _read_doc("MCP_RUNBOOK.md")

    for required in (
        "`/ui/home/macro-release-context`",
        "natural-day context only",
        "does not participate in the main judgment",
        "not tied to snapshot report-date admission",
        "no static historical numeric fallback",
        "`stale` / `fallback` / `source_pending` / `error`",
    ):
        assert required in cockpit_contract

    for required in (
        "`/ui/home/macro-release-context`",
        "`source_pending`",
        "MCP-unavailable work must record the unavailable server and the local substitute evidence",
        "unresolved items remain `source_pending`",
    ):
        assert required in runbook
