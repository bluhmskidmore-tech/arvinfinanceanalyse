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
