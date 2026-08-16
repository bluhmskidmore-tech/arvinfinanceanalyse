from dataclasses import dataclass
from typing import Literal

from backend.app.api.routes.accounting_asset_movement import router as accounting_asset_movement_router
from backend.app.api.routes.adb_analysis import router as adb_analysis_router
from backend.app.api.routes.balance_analysis import router as balance_analysis_router
from backend.app.api.routes.bond_analytics import router as bond_analytics_router
from backend.app.api.routes.bond_dashboard import router as bond_dashboard_router
from backend.app.api.routes.campisi_attribution import router as campisi_attribution_router
from backend.app.api.routes.cashflow_projection import router as cashflow_projection_router
from backend.app.api.routes.choice_news import router as choice_news_router
from backend.app.api.routes.choice_news import router_api_news as choice_news_api_router
from backend.app.api.routes.credit_spread_analysis import router as credit_spread_analysis_router
from backend.app.api.routes.cube_query import router as cube_query_router
from backend.app.api.routes.dashboard import router as dashboard_router
from backend.app.api.routes.data_health import router as data_health_router
from backend.app.api.routes.executive import router as executive_router
from backend.app.api.routes.external_data import router as external_data_router
from backend.app.api.routes.health import router as health_router
from backend.app.api.routes.kpi import router as kpi_router
from backend.app.api.routes.ledger import router as ledger_router
from backend.app.api.routes.ledger_pnl import router as ledger_pnl_router
from backend.app.api.routes.liability_analytics import router as liability_analytics_router
from backend.app.api.routes.macro_bond_linkage import router as macro_bond_linkage_router
from backend.app.api.routes.macro_etf_strategy import router as macro_etf_strategy_router
from backend.app.api.routes.macro_toolkit import router as macro_toolkit_router
from backend.app.api.routes.macro_vendor import router as macro_vendor_router
from backend.app.api.routes.market_data_livermore import router as market_data_livermore_router
from backend.app.api.routes.market_data_ncd_proxy import router as market_data_ncd_proxy_router
from backend.app.api.routes.pnl import router as pnl_router
from backend.app.api.routes.pnl_attribution import router as pnl_attribution_router
from backend.app.api.routes.positions import router as positions_router
from backend.app.api.routes.pretrade_checklist import router as pretrade_checklist_router
from backend.app.api.routes.product_category_pnl import router as product_category_pnl_router
from backend.app.api.routes.qdb_gl_monthly_analysis import router as qdb_gl_monthly_analysis_router
from backend.app.api.routes.research_calendar import router as research_calendar_router
from backend.app.api.routes.risk_tensor import router as risk_tensor_router
from backend.app.api.routes.source_preview import router as source_preview_router
from backend.app.api.routes.strategy_reports import router as strategy_reports_router
from backend.app.api.routes.team_performance import router as team_performance_router
from backend.app.governance.settings import get_settings
from fastapi import APIRouter

router = APIRouter()

RouteGroup = Literal[
    "formal_mainline",
    "analytical_compatibility",
    "preview",
    "macro_market",
    "agent_experimental",
    "support",
]


@dataclass(frozen=True)
class RouteRegistryEntry:
    name: str
    router: APIRouter
    group: RouteGroup
    tags: tuple[str, ...]
    owner: str


@dataclass(frozen=True)
class RouteGroupMetadata:
    label: str
    claim_boundary: str
    risk_boundary: str
    owner: str


ROUTE_GROUP_METADATA: dict[RouteGroup, RouteGroupMetadata] = {
    "formal_mainline": RouteGroupMetadata(
        label="Formal mainline",
        claim_boundary="Governed business workflow surfaces that may carry formal page-level claims only after route-specific evidence and owner approval.",
        risk_boundary="Do not infer certification from registration; metric definitions, dates, units, and golden approvals remain page-scoped gates.",
        owner="Business metric governance owner",
    ),
    "analytical_compatibility": RouteGroupMetadata(
        label="Analytical compatibility",
        claim_boundary="Compatibility analysis surfaces that preserve mixed-source and analytical-only status without claiming formal business truth.",
        risk_boundary="Live availability does not promote these routes to formal balance or PnL truth; source and compatibility limits remain explicit.",
        owner="Business analytics compatibility owner",
    ),
    "preview": RouteGroupMetadata(
        label="Preview",
        claim_boundary="Read-only preview and source-inspection surfaces for data review, not formal business certification.",
        risk_boundary="Preview output may be stale, partial, or exploratory and must surface that status instead of promoting formal-use claims.",
        owner="Reports and data owner",
    ),
    "macro_market": RouteGroupMetadata(
        label="Macro and market",
        claim_boundary="Market, macro, and vendor-data analysis surfaces for decision support and research context.",
        risk_boundary="These routes must not be treated as governed books-and-records truth or trading instructions without separate approval.",
        owner="Market data governance owner",
    ),
    "agent_experimental": RouteGroupMetadata(
        label="Agent experimental",
        claim_boundary="Agent workbench and orchestration surfaces for assisted analysis and exploratory business context.",
        risk_boundary="External-provider, generated, or suggested-action output requires explicit evidence, isolation, and confirmation-token controls.",
        owner="Agent workbench owner",
    ),
    "support": RouteGroupMetadata(
        label="Support",
        claim_boundary="Operational, health, query, and executive-support surfaces that help navigation or diagnostics.",
        risk_boundary="Support surfaces may expose status or summaries but must not be used as standalone metric certification.",
        owner="Platform support owner",
    ),
}


ROUTE_REGISTRY: tuple[RouteRegistryEntry, ...] = (
    RouteRegistryEntry("accounting_asset_movement", accounting_asset_movement_router, "formal_mainline", ("balance-movement-analysis",), "Balance movement owner"),
    RouteRegistryEntry("adb_analysis", adb_analysis_router, "formal_mainline", ("analysis-adb",), "Average balance owner"),
    RouteRegistryEntry("balance_analysis", balance_analysis_router, "formal_mainline", ("balance-analysis",), "Balance analysis owner"),
    RouteRegistryEntry("bond_analytics", bond_analytics_router, "formal_mainline", ("bond-analytics",), "Bond analytics owner"),
    RouteRegistryEntry("bond_dashboard", bond_dashboard_router, "formal_mainline", ("bond-dashboard",), "Bond dashboard owner"),
    RouteRegistryEntry("cashflow_projection", cashflow_projection_router, "formal_mainline", ("cashflow-projection",), "Cashflow owner"),
    RouteRegistryEntry("choice_news_ui", choice_news_router, "macro_market", ("choice-news",), "Market news owner"),
    RouteRegistryEntry("choice_news_api", choice_news_api_router, "macro_market", ("choice-news",), "Market news owner"),
    RouteRegistryEntry("credit_spread_analysis", credit_spread_analysis_router, "formal_mainline", ("credit-spread",), "Bond analytics owner"),
    RouteRegistryEntry("cube_query", cube_query_router, "support", ("cube",), "Query surface owner"),
    RouteRegistryEntry("dashboard", dashboard_router, "support", ("dashboard",), "Executive cockpit owner"),
    RouteRegistryEntry("data_health", data_health_router, "support", ("data-health",), "Platform health owner"),
    RouteRegistryEntry("health", health_router, "support", ("health",), "Platform health owner"),
    RouteRegistryEntry("liability_analytics", liability_analytics_router, "analytical_compatibility", ("liability-analytics",), "Liability analytics owner"),
    RouteRegistryEntry("macro_vendor", macro_vendor_router, "macro_market", ("macro-preview",), "Macro observation owner"),
    RouteRegistryEntry("macro_bond_linkage", macro_bond_linkage_router, "macro_market", ("macro-analysis",), "Market analytics owner"),
    RouteRegistryEntry("macro_etf_strategy", macro_etf_strategy_router, "macro_market", ("market-data",), "Market data owner"),
    RouteRegistryEntry("macro_toolkit", macro_toolkit_router, "macro_market", ("macro-toolkit",), "Macro tooling owner"),
    RouteRegistryEntry("market_data_livermore", market_data_livermore_router, "macro_market", ("market-data",), "Market data owner"),
    RouteRegistryEntry("market_data_ncd_proxy", market_data_ncd_proxy_router, "macro_market", ("market-data",), "Market data owner"),
    RouteRegistryEntry("executive", executive_router, "support", ("executive",), "Executive cockpit owner"),
    RouteRegistryEntry("external_data", external_data_router, "macro_market", ("external-data",), "Market data owner"),
    RouteRegistryEntry("pnl", pnl_router, "formal_mainline", ("pnl",), "Formal PnL owner"),
    RouteRegistryEntry("pnl_attribution", pnl_attribution_router, "formal_mainline", ("pnl-attribution",), "PnL attribution owner"),
    RouteRegistryEntry("positions", positions_router, "formal_mainline", ("positions",), "Positions owner"),
    RouteRegistryEntry("pretrade_checklist", pretrade_checklist_router, "macro_market", ("pretrade-checklist",), "Market data owner"),
    RouteRegistryEntry("product_category_pnl", product_category_pnl_router, "formal_mainline", ("product-category-pnl",), "Product category PnL owner"),
    RouteRegistryEntry("qdb_gl_monthly_analysis", qdb_gl_monthly_analysis_router, "formal_mainline", ("qdb-gl-monthly-analysis",), "QDB GL monthly analysis owner"),
    RouteRegistryEntry("research_calendar", research_calendar_router, "support", ("calendar",), "Research calendar owner"),
    RouteRegistryEntry("campisi_attribution", campisi_attribution_router, "formal_mainline", ("campisi-attribution",), "PnL attribution owner"),
    RouteRegistryEntry("kpi", kpi_router, "formal_mainline", ("kpi",), "KPI governance owner"),
    RouteRegistryEntry("ledger", ledger_router, "formal_mainline", ("ledger",), "Ledger dashboard owner"),
    RouteRegistryEntry("ledger_pnl", ledger_pnl_router, "formal_mainline", ("ledger-pnl",), "Ledger PnL owner"),
    RouteRegistryEntry("risk_tensor", risk_tensor_router, "formal_mainline", ("risk",), "Risk tensor owner"),
    RouteRegistryEntry("source_preview", source_preview_router, "preview", ("preview",), "Reports and data owner"),
    RouteRegistryEntry("strategy_reports", strategy_reports_router, "macro_market", ("strategy-reports",), "Market data owner"),
    RouteRegistryEntry("team_performance", team_performance_router, "analytical_compatibility", ("team-performance",), "Team performance workbook owner"),
)

if get_settings().agent_enabled:
    from backend.app.api.routes.agent import router as agent_router

    ROUTE_REGISTRY += (
        RouteRegistryEntry("agent", agent_router, "agent_experimental", ("agent",), "Agent workbench owner"),
    )

for entry in ROUTE_REGISTRY:
    router.include_router(entry.router, tags=list(entry.tags))
