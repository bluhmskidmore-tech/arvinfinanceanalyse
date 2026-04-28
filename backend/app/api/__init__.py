from backend.app.api.routes.accounting_asset_movement import router as accounting_asset_movement_router
from backend.app.api.routes.adb_analysis import router as adb_analysis_router
from backend.app.api.routes.agent import router as agent_router
from backend.app.api.routes.balance_analysis import router as balance_analysis_router
from backend.app.api.routes.bond_analytics import router as bond_analytics_router
from backend.app.api.routes.bond_dashboard import router as bond_dashboard_router
from backend.app.api.routes.campisi_attribution import router as campisi_attribution_router
from backend.app.api.routes.cashflow_projection import router as cashflow_projection_router
from backend.app.api.routes.choice_news import router as choice_news_router
from backend.app.api.routes.choice_news import router_api_news as choice_news_api_router
from backend.app.api.routes.credit_spread_analysis import router as credit_spread_analysis_router
from backend.app.api.routes.cube_query import router as cube_query_router
from backend.app.api.routes.executive import router as executive_router
from backend.app.api.routes.external_data import router as external_data_router
from backend.app.api.routes.health import router as health_router
from backend.app.api.routes.kpi import router as kpi_router
from backend.app.api.routes.ledger import router as ledger_router
from backend.app.api.routes.ledger_pnl import router as ledger_pnl_router
from backend.app.api.routes.liability_analytics import router as liability_analytics_router
from backend.app.api.routes.macro_bond_linkage import router as macro_bond_linkage_router
from backend.app.api.routes.macro_vendor import router as macro_vendor_router
from backend.app.api.routes.market_data_ncd_proxy import router as market_data_ncd_proxy_router
from backend.app.api.routes.pnl import router as pnl_router
from backend.app.api.routes.pnl_attribution import router as pnl_attribution_router
from backend.app.api.routes.positions import router as positions_router
from backend.app.api.routes.product_category_pnl import router as product_category_pnl_router
from backend.app.api.routes.qdb_gl_monthly_analysis import router as qdb_gl_monthly_analysis_router
from backend.app.api.routes.research_calendar import router as research_calendar_router
from backend.app.api.routes.risk_tensor import router as risk_tensor_router
from backend.app.api.routes.source_preview import router as source_preview_router
from fastapi import APIRouter

router = APIRouter()
router.include_router(accounting_asset_movement_router, tags=["balance-movement-analysis"])
router.include_router(adb_analysis_router)
router.include_router(agent_router, tags=["agent"])
router.include_router(balance_analysis_router, tags=["balance-analysis"])
router.include_router(bond_analytics_router, tags=["bond-analytics"])
router.include_router(bond_dashboard_router, tags=["bond-dashboard"])
router.include_router(cashflow_projection_router, tags=["cashflow-projection"])
router.include_router(choice_news_router, tags=["choice-news"])
router.include_router(choice_news_api_router, tags=["choice-news"])
router.include_router(credit_spread_analysis_router, tags=["credit-spread"])
router.include_router(cube_query_router, tags=["cube"])
router.include_router(health_router, tags=["health"])
router.include_router(liability_analytics_router, tags=["liability-analytics"])
router.include_router(macro_vendor_router, tags=["macro-preview"])
router.include_router(macro_bond_linkage_router, tags=["macro-analysis"])
router.include_router(market_data_ncd_proxy_router, tags=["market-data"])
router.include_router(executive_router, tags=["executive"])
router.include_router(external_data_router)
router.include_router(pnl_router, tags=["pnl"])
router.include_router(pnl_attribution_router)
router.include_router(positions_router, tags=["positions"])
router.include_router(product_category_pnl_router, tags=["product-category-pnl"])
router.include_router(qdb_gl_monthly_analysis_router, tags=["qdb-gl-monthly-analysis"])
router.include_router(research_calendar_router, tags=["calendar"])
router.include_router(campisi_attribution_router, tags=["campisi-attribution"])
router.include_router(kpi_router, tags=["kpi"])
router.include_router(ledger_router, tags=["ledger"])
router.include_router(ledger_pnl_router, tags=["ledger-pnl"])
router.include_router(risk_tensor_router, tags=["risk"])
router.include_router(source_preview_router, tags=["preview"])
