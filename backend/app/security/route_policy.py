from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

RoutePolicyClass = Literal["public", "internal", "admin"]
RoutePolicyState = Literal["active", "reserved"]

ADMIN_SCOPE_ACTIONS = frozenset({"backfill", "delete", "execute", "import", "refresh", "write"})


@dataclass(frozen=True)
class RoutePolicySemantics:
    policy_class: RoutePolicyClass
    owner: str
    state: RoutePolicyState = "active"
    reason: str = ""


POLICY_SCOPE_SEMANTICS: dict[tuple[str, str], RoutePolicySemantics] = {
    ("accounting_asset_movement", "read"): RoutePolicySemantics("internal", "Balance movement owner"),
    ("accounting_asset_movement", "refresh"): RoutePolicySemantics("admin", "Balance movement owner"),
    ("adb_analysis", "backfill"): RoutePolicySemantics("admin", "Average balance owner"),
    ("adb_analysis", "read"): RoutePolicySemantics("internal", "Average balance owner"),
    ("agent", "read"): RoutePolicySemantics("internal", "Agent workbench owner"),
    ("balance_analysis", "read"): RoutePolicySemantics("internal", "Balance analysis owner"),
    ("balance_analysis", "refresh"): RoutePolicySemantics("admin", "Balance analysis owner"),
    ("balance_analysis.decision_status", "write"): RoutePolicySemantics("admin", "Balance governance owner"),
    ("bond_analytics", "read"): RoutePolicySemantics("internal", "Bond analytics owner"),
    ("bond_analytics", "refresh"): RoutePolicySemantics("admin", "Bond analytics owner"),
    ("bond_dashboard", "read"): RoutePolicySemantics("internal", "Bond dashboard owner"),
    ("cashflow_projection", "read"): RoutePolicySemantics("internal", "Cashflow owner"),
    ("choice_news.data", "import"): RoutePolicySemantics("admin", "Market news owner", state="reserved"),
    ("choice_news.data", "read"): RoutePolicySemantics("internal", "Market news owner"),
    ("credit_spread_analysis", "read"): RoutePolicySemantics("internal", "Bond analytics owner"),
    ("cube", "read"): RoutePolicySemantics("internal", "Query surface owner"),
    ("dashboard", "read"): RoutePolicySemantics("internal", "Executive cockpit owner"),
    ("executive", "read"): RoutePolicySemantics("internal", "Executive cockpit owner"),
    ("external_data", "read"): RoutePolicySemantics("internal", "Market data owner"),
    ("formal_pnl", "refresh"): RoutePolicySemantics("admin", "Formal PnL owner"),
    ("kpi", "read"): RoutePolicySemantics("internal", "KPI governance owner"),
    ("kpi.metric", "delete"): RoutePolicySemantics("admin", "KPI governance owner"),
    ("kpi.metric", "write"): RoutePolicySemantics("admin", "KPI governance owner"),
    ("kpi.value", "write"): RoutePolicySemantics("admin", "KPI governance owner"),
    ("ledger.data", "import"): RoutePolicySemantics("admin", "Ledger dashboard owner"),
    ("ledger.data", "read"): RoutePolicySemantics("internal", "Ledger dashboard owner"),
    ("ledger_pnl", "read"): RoutePolicySemantics("internal", "Ledger PnL owner"),
    ("liability_analytics", "read"): RoutePolicySemantics("internal", "Liability analytics owner"),
    ("macro_bond_linkage", "read"): RoutePolicySemantics("internal", "Market analytics owner"),
    ("macro_toolkit", "read"): RoutePolicySemantics("internal", "Macro tooling owner"),
    ("macro_toolkit.cffex_member_rank", "refresh"): RoutePolicySemantics("admin", "Macro tooling owner"),
    ("macro_toolkit.choice_stock", "refresh"): RoutePolicySemantics("admin", "Macro tooling owner"),
    ("macro_toolkit.commodity_futures", "refresh"): RoutePolicySemantics("admin", "Macro tooling owner"),
    ("macro_toolkit.script", "execute"): RoutePolicySemantics("admin", "Macro tooling owner"),
    ("macro_toolkit.source_backfill", "refresh"): RoutePolicySemantics("admin", "Macro tooling owner"),
    ("macro_vendor", "read"): RoutePolicySemantics("internal", "Macro observation owner"),
    ("macro_vendor.choice_series", "refresh"): RoutePolicySemantics("admin", "Macro observation owner"),
    ("market_data.macro_etf_strategy", "read"): RoutePolicySemantics("internal", "Market data owner"),
    ("market_data.livermore", "read"): RoutePolicySemantics("internal", "Market data owner"),
    ("market_data.livermore_gate_supplement", "refresh"): RoutePolicySemantics("admin", "Market data owner"),
    ("market_data.livermore_position_snapshot", "import"): RoutePolicySemantics("admin", "Market data owner"),
    ("market_data_ncd_proxy", "read"): RoutePolicySemantics("internal", "Market data owner"),
    ("pnl", "read"): RoutePolicySemantics("internal", "Formal PnL owner"),
    ("pnl_attribution", "read"): RoutePolicySemantics("internal", "PnL attribution owner"),
    ("pnl_by_business.adjustment", "approve"): RoutePolicySemantics("admin", "Business PnL owner"),
    ("pnl_by_business.adjustment", "write"): RoutePolicySemantics("admin", "Business PnL owner"),
    ("positions", "read"): RoutePolicySemantics("internal", "Positions owner"),
    ("product_category_pnl", "read"): RoutePolicySemantics("internal", "Product category PnL owner"),
    ("product_category_pnl", "refresh"): RoutePolicySemantics("admin", "Product category PnL owner"),
    ("product_category_pnl.adjustment", "write"): RoutePolicySemantics("admin", "Product category PnL owner"),
    ("qdb_gl_monthly_analysis", "read"): RoutePolicySemantics("internal", "QDB GL monthly analysis owner"),
    ("qdb_gl_monthly_analysis", "refresh"): RoutePolicySemantics("admin", "QDB GL monthly analysis owner"),
    ("qdb_gl_monthly_analysis.adjustment", "write"): RoutePolicySemantics("admin", "QDB GL monthly analysis owner"),
    ("research_calendar", "read"): RoutePolicySemantics("internal", "Research calendar owner"),
    ("risk_tensor", "read"): RoutePolicySemantics("internal", "Risk tensor owner"),
    ("source_preview.source_foundation", "read"): RoutePolicySemantics("internal", "Reports and data owner"),
    ("source_preview.source_foundation", "refresh"): RoutePolicySemantics("admin", "Reports and data owner"),
}
