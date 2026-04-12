from fastapi import APIRouter

from backend.app.api.routes.agent import router as agent_router
from backend.app.api.routes.balance_analysis import router as balance_analysis_router
from backend.app.api.routes.executive import router as executive_router
from backend.app.api.routes.health import router as health_router
from backend.app.api.routes.choice_news import router as choice_news_router
from backend.app.api.routes.cube_query import router as cube_query_router
from backend.app.api.routes.macro_vendor import router as macro_vendor_router
from backend.app.api.routes.pnl import router as pnl_router
from backend.app.api.routes.product_category_pnl import router as product_category_pnl_router
from backend.app.api.routes.qdb_gl_monthly_analysis import router as qdb_gl_monthly_analysis_router
from backend.app.api.routes.bond_analytics import router as bond_analytics_router
from backend.app.api.routes.risk_tensor import router as risk_tensor_router
from backend.app.api.routes.source_preview import router as source_preview_router

router = APIRouter()
router.include_router(agent_router, tags=["agent"])
router.include_router(balance_analysis_router, tags=["balance-analysis"])
router.include_router(bond_analytics_router, tags=["bond-analytics"])
router.include_router(choice_news_router, tags=["choice-news"])
router.include_router(cube_query_router, tags=["cube"])
router.include_router(health_router, tags=["health"])
router.include_router(macro_vendor_router, tags=["macro-preview"])
router.include_router(executive_router, tags=["executive"])
router.include_router(pnl_router, tags=["pnl"])
router.include_router(product_category_pnl_router, tags=["product-category-pnl"])
router.include_router(qdb_gl_monthly_analysis_router, tags=["qdb-gl-monthly-analysis"])
router.include_router(risk_tensor_router, tags=["risk"])
router.include_router(source_preview_router, tags=["preview"])
