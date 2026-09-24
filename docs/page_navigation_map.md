# 页面直达导航表（Page Navigation Map）

- `Role`: 快速定位工具——从"页面 URL / API 前缀"直达"该打开的代码文件"。只做导航，不承载业务口径。
- `Not for`: 业务契约与指标口径（权威仍是 `docs/page_contracts.md`、`docs/metric_dictionary.md`）；目录级总览见 `docs/agent_codebase_map.md`。
- 快照日期: 2026-08-12。事实来源: `frontend/src/router/routes.tsx`、`backend/app/api/__init__.py` 的 `ROUTE_REGISTRY`、各 route/service 文件顶部 import。路由增删后需同步本表。

## 怎么用

- **页面上数字不对**: 查【表 1】拿到页面组件和数据层文件（先查 adapter/model 是否转换错），再按"后端端点前缀"跳到【表 2】，打开对应 service 与 core_finance 文件。
- **API 报错 / 后端逻辑问题**: 直接查【表 2】。
- **找回归测试**: 见【测试定位】一节。

## 表 1：前端页面 → 文件 → 后端端点

| 路由 path | 页面组件 | 数据层（model/hooks/client） | 后端端点前缀 |
| --- | --- | --- | --- |
| `/`、`/dashboard`、`/政策与资金面` | `frontend/src/features/workbench/dashboard-home/DashboardHomePage.tsx` | `dashboard-home/useDashboardHomeViewModel.ts`、`pages/useDashboardSnapshotBoundary.ts`、`src/api/executiveHomeSnapshotFetch.ts` | `/ui/home`, `/api/bond-dashboard`, `/api/bond-analytics`, `/ui/news/choice-events`, `/ui/calendar` |
| `/operations-analysis` | `frontend/src/features/workbench/pages/OperationsAnalysisPage.tsx` | 页内 + `src/api/marketDataClient.ts`、`src/api/balanceAnalysisClient.ts` | `/ui/preview/source-foundation`, `/ui/market-data`, `/ui/macro/choice-series`, `/ui/balance-analysis`, `/ui/pnl/product-category` |
| `/market-finance` | `frontend/src/features/market-finance/pages/MarketFinanceWorkbenchPage.tsx` | `pages/marketFinanceModel.ts`、`src/api/marketDataClient.ts`、`src/api/productCategoryClient.ts` | `/ui/market-data`, `/ui/pnl/product-category`, `/ui/balance-analysis` |
| `/portfolio` | `frontend/src/features/workbench/module-home/PortfolioHomePage.tsx` | `module-home/usePortfolioHomeQueries.ts`、`module-home/moduleHomeModel.ts` | `/api/bond-dashboard`, `/ui/balance-analysis`, `/api/pnl-attribution`, `/api/risk/tensor` |
| `/bond-analysis` | `frontend/src/features/bond-analytics/components/BondAnalyticsView.tsx` | `components/BondAnalyticsViewContent.tsx`、`lib/bondAnalyticsCockpitBundleQuery.ts`、`src/api/bondAnalyticsClient.ts` | `/api/bond-analytics`, `/api/bond-dashboard`, `/ui/calendar`, `/api/credit-spread-analysis` |
| `/bond-trading-desk` | `frontend/src/features/bond-trading-desk/pages/BondTradingDeskPage.tsx` | `lib/bondTradingDeskPageModel.ts`、`src/api/bondAnalyticsClient.ts`、`src/api/positionsClient.ts` | `/api/bond-analytics`, `/api/positions`, `/api/credit-spread-analysis` |
| `/bond-dashboard` | `frontend/src/features/bond-dashboard/pages/BondDashboardPage.tsx` | `hooks/useBondDashboardBundleQuery.ts`、`bondDashboardBundleModel.ts`、`src/api/bondAnalyticsClient.ts` | `/api/bond-dashboard` |
| `/positions` | `frontend/src/features/positions/pages/PositionsPage.tsx` | `components/PositionsView.tsx`、`src/api/positionsClient.ts` | `/api/positions`, `/ui/balance-analysis` |
| `/cross-asset`、`/cross-asset-drivers` | `frontend/src/features/cross-asset/pages/CrossAssetPage.tsx`（转 `CrossAssetDriversPage.tsx`） | `hooks/useCrossAssetViewModel.ts`、`src/api/marketDataClient.ts` | `/ui/macro/choice-series`, `/ui/calendar`, `/api/macro-bond-linkage`, `/ui/market-data` |
| `/market-overview` | `frontend/src/features/workbench/module-home/MarketHomePage.tsx` | `module-home/useMarketHomeQueries.ts`、`src/api/marketDataClient.ts`、`src/api/macroToolkitClient.ts` | `/ui/macro/choice-series`, `/ui/market-data`, `/ui/macro/toolkit`, `/ui/news/choice-events` |
| `/market-data` | `frontend/src/features/market-data/pages/MarketDataPage.tsx` | `hooks/useMarketDataPageData.ts`、`pages/marketDataPageModel.ts`、`src/api/marketDataClient.ts` | `/ui/market-data`, `/ui/macro/choice-series`, `/api/external-data`, `/api/macro-bond-linkage` |
| `/macro-observation`、`/macro-toolkit` | `frontend/src/features/macro-toolkit/pages/MacroToolkitPage.tsx` | 页内 + `src/api/macroToolkitClient.ts` | `/ui/macro/toolkit` |
| `/stock-analysis` | `frontend/src/features/stock-analysis/pages/StockAnalysisPage.tsx`（转 `StockAnalysisPageImpl.tsx`） | `lib/stockAnalysisPageModel.ts`、`src/api/marketDataClient.ts`、`src/api/stockAnalysisWorkbenchClient.ts` | `/ui/market-data` |
| `/news-events` | `frontend/src/features/news-events/NewsEventsPage.tsx` | 页内 + `src/api/marketDataClient.ts` | `/ui/news/choice-events` |
| `/balance-analysis` | `frontend/src/features/balance-analysis/pages/BalanceAnalysisPage.tsx` | `hooks/useBalanceAnalysisData.ts`、`pages/balanceAnalysisPageModel.ts`、`src/api/balanceAnalysisClient.ts` | `/ui/balance-analysis`, `/ui/balance-movement-analysis`, `/api/analysis/adb` |
| `/balance-movement-analysis` | `frontend/src/features/balance-movement-analysis/pages/BalanceMovementAnalysisPage.tsx` | `lib/balanceMovementShareModel.ts`、`src/api/balanceMovementClient.ts` | `/ui/balance-movement-analysis` |
| `/liability-analytics` | `frontend/src/features/liability-analytics/pages/LiabilityAnalyticsPage.tsx` | `pages/liabilityAnalyticsPageModel.ts`、`src/api/liabilityAdbClient.ts` | `/api/risk/buckets`, `/api/analysis`, `/api/liabilities`, `/ui/liability`, `/ui/balance-analysis` |
| `/average-balance` | `frontend/src/features/average-balance/pages/AverageBalancePage.tsx` | `components/AverageBalanceView.tsx`、`src/api/liabilityAdbClient.ts` | `/api/analysis/adb`, `/ui/balance-analysis` |
| `/decision-items` | `frontend/src/features/decision-items/pages/DecisionItemsPage.tsx` | `lib/decisionItemsPageModel.ts`、`src/api/balanceAnalysisClient.ts` | `/ui/balance-analysis` |
| `/pnl`、`/pnl-formal-v1` | `frontend/src/features/pnl/PnlPage.tsx`（re-export `FormalPnlV1Page.tsx`） | `FormalPnlV1Page.tsx`、`src/api/pnlCoreClient.ts`、`src/api/pnlClient.ts` | `/api/pnl`, `/api/analysis/yield_metrics`, `/api/data` |
| `/pnl-bridge` | `frontend/src/features/pnl/PnlBridgePage.tsx` | 页内 + `src/api/pnlCoreClient.ts` | `/api/pnl`, `/api/data` |
| `/pnl-attribution` | `frontend/src/features/pnl-attribution/pages/PnlAttributionPage.tsx` | `components/PnlAttributionView.tsx`、`src/api/pnlAttributionClient.ts`、`src/api/productCategoryClient.ts` | `/api/pnl-attribution`, `/api/pnl`, `/ui/pnl/product-category` |
| `/pnl-by-business` | `frontend/src/features/pnl/PnlByBusinessPage.tsx` | 页内 + `src/api/pnlClient.ts`、`src/api/liabilityAdbClient.ts` | `/api/pnl`, `/api/analysis/adb` |
| `/pnl-by-business-insights` | `frontend/src/features/pnl-business-insights/PnlByBusinessInsightsPage.tsx` | 页内 + `src/api/pnlClient.ts` | `/api/pnl` |
| `/product-category-pnl` | `frontend/src/features/product-category-pnl/pages/ProductCategoryPnlPage.tsx` | `pages/productCategoryPnlPageModel.ts`、`src/api/productCategoryClient.ts`、`src/api/qdbGlMonthlyAnalysisClient.ts` | `/ui/pnl/product-category`, `/ui/qdb-gl-monthly-analysis` |
| `/product-category-pnl/audit` | `frontend/src/features/product-category-pnl/pages/ProductCategoryAdjustmentAuditPage.tsx` | `pages/productCategoryAdjustmentAuditPageModel.ts`、`src/api/productCategoryClient.ts` | `/ui/pnl/product-category` |
| `/ledger-pnl` | `frontend/src/features/ledger-pnl/pages/LedgerPnlPage.tsx` | 页内 + `src/api/pnlCoreClient.ts` | `/api/ledger-pnl` |
| `/bank-ledger-dashboard` | `frontend/src/features/ledger-dashboard/pages/LedgerDashboardPage.tsx` | `pages/ledgerDashboardPageModel.ts`、`pages/useLedgerImportWorkflow.ts`、`src/api/ledgerClient.ts` | `/api/ledger` |
| `/team-performance` | `frontend/src/features/team-performance/TeamPerformancePage.tsx` | 页内 + `src/api/pnlClient.ts`、`src/api/productCategoryClient.ts` | `/api/pnl`, `/ui/pnl/product-category` |
| `/kpi` | `frontend/src/features/kpi-performance/pages/KpiPerformancePage.tsx` | 页内 + `src/api/kpiClient.ts` | `/api/kpi` |
| `/performance`、`/reports` | `frontend/src/features/workbench/module-home/ModuleWorkbenchHomePage.tsx` | 页内 + `src/api/kpiClient.ts`、`src/api/pnlClient.ts`、`src/api/cubeClient.ts`、`src/api/healthClient.ts` | `/api/kpi`, `/api/pnl`, `/api/risk`, `/api/cashflow-projection`, `/api/cube`, `/health` |
| `/risk-overview` | `frontend/src/features/workbench/module-home/RiskOverviewPage.tsx` | 页内 + `src/api/executiveClient.ts`、`src/api/bondAnalyticsClient.ts` | `/api/risk`, `/api/cashflow-projection`, `/api/bond-analytics` |
| `/risk-tensor` | `frontend/src/features/risk-tensor/RiskTensorPage.tsx` | 页内 + `src/api/executiveClient.ts` | `/api/risk` |
| `/concentration-monitor` | `frontend/src/features/concentration-monitor/ConcentrationMonitorPage.tsx` | 页内 + `src/api/bondAnalyticsClient.ts` | `/api/bond-analytics` |
| `/cashflow-projection` | `frontend/src/features/cashflow-projection/pages/CashflowProjectionPage.tsx` | `pages/cashflowProjectionPageModel.ts`、`src/api/cashflowClient.ts`、`src/api/balanceAnalysisClient.ts` | `/api/cashflow-projection`, `/ui/balance-analysis` |
| `/cube-query` | `frontend/src/features/cube-query/pages/CubeQueryPage.tsx` | 页内 + `src/api/cubeClient.ts` | `/api/cube` |
| `/platform-config` | `frontend/src/features/platform-config/PlatformConfigPage.tsx` | 页内 + `src/api/healthClient.ts`、`src/api/marketDataClient.ts` | `/health`, `/ui/preview/source-foundation` |
| `/agent`（需 `DEV` + `VITE_MOSS_AGENT_FRONTEND_ENABLED=true`） | `frontend/src/router/AgentWorkbenchRoute.tsx` → `features/agent/AgentWorkbenchPage.tsx` | `hooks/useAgentRunRestore.ts`、`src/api/agentClient.ts`、`src/api/agentRunStream.ts` | `/api/agent` |
| `/source-preview`（placeholder） | `frontend/src/features/workbench/pages/WorkbenchPlaceholderPage.tsx` | 本地信封，无请求（完整页 `features/source-preview/` 已实现但未挂载） | - |
| `/prototype/equity-cockpit`（prototype） | `frontend/src/features/prototype/EquityCockpitPrototypePage.tsx` | 页内硬编码 mock | - |

重定向路由（无独立页面）: `/macro-analysis`→`/market-data`、`/adb`→`/average-balance`、`/liabilities`→`/liability-analytics`、`/bonds`→`/bond-dashboard`、`/bond-analytics-advanced`→`/bond-analysis`、`/market`→`/market-data`、`/assets`→`/bond-dashboard`。未匹配路由落 `frontend/src/router/WorkbenchRouteStatusPages.tsx`。

前端备注:

- 路由注册: `frontend/src/router/routes.tsx`；子路由导航由 `frontend/src/mocks/navigation.ts` 的 `workbenchNavigation` 驱动，`readiness !== "live"` 的入口统一落 placeholder。
- HTTP 客户端集中在 `frontend/src/api/*Client.ts`，feature 目录内基本没有独立 `api/`；查"请求发到哪"直接看对应 client 文件。
- 端点前缀同时存在 `/api/*` 与 `/ui/*` 两套，平台健康检查用 `/health`（无前缀）。
- 所有工作台页挂在 `frontend/src/layouts/WorkbenchShell.tsx` 下。

## 表 2：后端 API 前缀 → 路由文件 → service → core_finance / repositories

路由注册中心: `backend/app/api/__init__.py` 的 `ROUTE_REGISTRY`（`main.py` 只挂总 router）。下表文件名省略层目录: 路由在 `backend/app/api/routes/`，service 在 `backend/app/services/`，core_finance 在 `backend/app/core_finance/`，repo 在 `backend/app/repositories/`。

| API 前缀 | 路由文件 | services | core_finance | repositories |
| --- | --- | --- | --- | --- |
| `/ui/home/*`、`/ui/pnl/attribution` 等 | `executive.py` | `executive_service.py`、`home_macro_release_context_service.py` | `alert_engine.py`、`liability_analytics_compat.py`、`risk_tensor.py` | `bond_analytics_repo.py`、`dashboard_repo.py`、`formal_zqtz_balance_metrics_repo.py`、`governance_repo.py`、`liability_analytics_repo.py`、`news_warehouse_repo.py` 等 |
| `/ui/balance-analysis` | `balance_analysis.py` | `balance_analysis_service.py`、`advanced_attribution_service.py` | `balance_calibration.py`、`module_contracts.py`、`module_registry.py` | `balance_analysis_repo.py`、`balance_analysis_decision_repo.py`、`governance_repo.py` |
| `/ui/balance-movement-analysis` | `accounting_asset_movement.py` | `accounting_asset_movement_service.py` | `accounting_asset_movement.py` | `accounting_asset_movement_repo.py` |
| `/api/analysis`（含 `/adb`） | `adb_analysis.py` | `adb_analysis_service.py` | `adb_analytics.py`、`adb_interbank_labels.py`、`adb_rate_normalize.py`、`balance_calibration.py`、`zqtz_asset_bond_category.py` | - |
| `/api/pnl/*`、`/api/data` | `pnl.py` | `pnl_service.py`、`pnl_bridge_service.py`、`pnl_by_business_candidate_insights.py` | `pnl.py`、`config/classification_rules.py`、`field_normalization.py`、`reconciliation_checks.py`、`zqtz_asset_bond_category.py`、`bond_analytics/common.py` 等 | `pnl_repo.py`、`accounting_asset_movement_repo.py`、`balance_analysis_repo.py`、`governance_repo.py` |
| `/api/pnl-attribution` | `pnl_attribution.py`、`campisi_attribution.py` | `pnl_attribution_service.py`、`campisi_attribution_service.py` | `campisi.py`、`campisi_decision_grade.py`、`pnl_attribution/`、`accounting_basis_constants.py`、`rate_units.py` | `bond_analytics_repo.py`、`pnl_repo.py`、`yield_curve_repo.py` |
| `/ui/pnl/product-category` | `product_category_pnl.py` | `product_category_pnl_service.py` | `product_category_pnl_attribution.py`、`reconciliation_checks.py` | `product_category_pnl_repo.py`、`governance_repo.py` |
| `/api/ledger-pnl/*` | `ledger_pnl.py` | `ledger_pnl_service.py`、`candidate_financial_indicator_service.py`、`candidate_financial_indicator_period_comparison_service.py`、`qdb_gl_monthly_analysis_service.py` | `formal_financial_indicators.py`、`formal_financial_indicator_rules.py`、`ledger_financial_indicator_summary.py`、`ledger_pnl_analysis.py`、`config/classification_rules.py`、`decimal_utils.py` 等 | `governance_repo.py` |
| `/api/ledger/*` | `ledger.py` | `ledger_import_service.py`、`ledger_import_run_service.py`、`ledger_analytics_service.py` | - | `ledger_import_repo.py`、`ledger_analytics_repo.py`、`job_state_repo.py`、`governance_repo.py` |
| `/ui/qdb-gl-monthly-analysis` | `qdb_gl_monthly_analysis.py` | `qdb_gl_monthly_analysis_service.py` | `qdb_gl_monthly_analysis.py` | `governance_repo.py` |
| `/api/bond-analytics` | `bond_analytics.py` | `bond_analytics_service.py`、`yield_curve_term_structure_service.py` | `bond_analytics/`（含 `common.py`、`read_models.py`）、`action_attribution.py` | `bond_analytics_repo.py`、`yield_curve_repo.py`、`pnl_repo.py`、`governance_repo.py` |
| `/api/bond-dashboard` | `bond_dashboard.py` | `bond_dashboard_service.py` | - | `bond_analytics_repo.py` |
| `/api/credit-spread-analysis` | `credit_spread_analysis.py` | `credit_spread_analysis_service.py` | `credit_spread_analysis.py` | `bond_analytics_repo.py`、`yield_curve_repo.py` |
| `/api/cashflow-projection` | `cashflow_projection.py` | `cashflow_projection_service.py` | `cashflow_projection.py`、`bond_duration.py`、`interest_mode.py` | `cashflow_projection_repo.py`、`bond_analytics_repo.py` |
| `/api/positions` | `positions.py` | `positions_service.py` | - | `positions_repo.py` |
| `/api/risk/*`、`/api/liabilities`、`/ui/liability`（装饰器内声明，文件无统一 prefix） | `liability_analytics.py` | `liability_analytics_service.py`、`liability_knowledge_service.py` | `liability_analytics_compat.py`、`liability_cockpit.py`、`yield_by_period.py` | `liability_analytics_repo.py`、`pnl_repo.py` |
| `/api/risk`（张量/情景） | `risk_tensor.py` | `risk_tensor_service.py`、`risk_scenario_stress_service.py`、`formal_result_runtime.py` | - | `risk_tensor_repo.py`、`governance_repo.py` |
| `/ui/market-data`（Livermore 选股） | `market_data_livermore.py` | `livermore_candidate_history_service.py`、`livermore_signal_confluence_service.py`、`livermore_sector_rank_series_service.py`、`livermore_stock_detail_service.py`、`livermore_gate_supplement_compute_service.py`、`macro_bond_linkage_service.py` 等 | `strategy_policy.py`、`candidate_history_proxy_backtest.py`、`matched_baseline.py`、`livermore_sector_rank.py`、`field_normalization.py`、`macro_bond_linkage.py` 等13个 | `governance_repo.py`、`choice_stock_adapter.py`、`choice_stock_units.py`、`stock_analysis_theme_overlay_reader.py`、`livermore_gate_supplement_repo.py` |
| `/ui/market-data`、`/ui/macro`、`/ui/preview`（多前缀在装饰器） | `macro_vendor.py` | `macro_vendor_service.py` | `fx_rates.py` | `cffex_member_rank_repo.py`、`choice_fx_catalog.py`、`governance_repo.py` |
| `/ui/market-data`（NCD 代理） | `market_data_ncd_proxy.py` | `market_data_ncd_proxy_service.py` | - | - |
| `/ui/market-data`（ETF 策略） | `macro_etf_strategy.py` | `macro_etf_strategy_service.py` | `macro/macro_etf_strategy.py`、`macro/dual_frequency_equity.py` | `dual_frequency_equity_repo.py` |
| `/ui/macro/toolkit` | `macro_toolkit.py` | `macro_toolkit_analysis_service.py`、`macro_adversarial_signal_service.py`、`macro_etf_strategy_service.py`、`macro_report_asset_service.py`、`macro_toolkit_refresh_receipt_service.py`、`formal_result_runtime.py` 等 | `macro/toolkit.py`、`macro/crisis_commodity_shadow.py`、`macro/equity_strategies.py`、`macro/dual_frequency_equity.py`、`macro/macro_etf_strategy.py`（路由文件自身还直接引 `core_finance.macro.*`） | `dual_frequency_equity_repo.py`、`cffex_member_rank_repo.py`、`governance_repo.py`、`choice_stock_units.py` |
| `/api/macro-bond-linkage` | `macro_bond_linkage.py` | `macro_bond_linkage_service.py` | `macro_bond_linkage.py` | - |
| `/ui/news`、`/api/news` | `choice_news.py` | `choice_news_service.py` | - | - |
| `/ui/calendar` | `research_calendar.py` | `research_calendar_service.py` | - | `research_calendar_repo.py` |
| `/api/external-data` | `external_data.py` | `external_data_service.py` | - | `external_data_catalog_repo.py` |
| `/ui/preview` | `source_preview.py` | `source_preview_service.py`、`source_preview_refresh_service.py` | `source_preview_parsers.py` | `source_preview_repo.py`、`job_state_repo.py`、`governance_repo.py` |
| `/api/kpi` | `kpi.py` | `kpi_service.py`、`kpi_workbench_service.py` | - | `kpi_repo.py` |
| `/api/cube` | `cube_query.py` | `cube_query_service.py`、`analytical_bridge_service.py` | `calibers/enums.py` | `cube_query_repo.py` |
| `/api/dashboard` | `dashboard.py` | `dashboard_service.py` | - | `dashboard_repo.py`、`bond_analytics_repo.py` |
| `/api/agent`（`agent_enabled` 时注册） | `agent.py`（挂 `agent_workspace.py`） | `agent_service.py`、`agent_run_service.py`、`agent_workspace_service.py`、`dexter_agent_service.py`、`hermes_agent_service.py` | `calibers/enums.py` | `agent_workspace_repo.py`、`governance_repo.py`、`bond_analytics_repo.py`、`pnl_repo.py`、`product_category_pnl_repo.py`、`risk_tensor_repo.py` |
| `/health` | `health.py` | `health_service.py` | - | `duckdb_repo.py`、`postgres_repo.py`、`redis_repo.py`、`object_store_repo.py` |

后端备注:

- core_finance / repositories 列仅统计对应 service 文件顶部 import，`-` 表示顶部未见（不代表运行时无数据访问）。
- `liability_analytics.py`、`macro_vendor.py` 的前缀声明在各路由装饰器内，文件级没有统一 prefix，搜端点时直接全文搜路径字符串。

## 测试定位

- `tests/`: 约 700 个扁平 `test_*.py`，按文件名前缀对应域（`test_pnl_*`、`test_balance_*`、`test_bond_*`、`test_macro_*`、`test_executive_*` 等），改哪个域就按前缀挑测试。
- `tests/core_finance/`: 正式金融计算单元测试。
- `tests/golden_samples/`: 业务黄金样本（GS-BAL / GS-PNL / GS-BRIDGE / GS-RISK / GS-EXEC 等约 26 套）。
- `tests/fixtures/`: 共享夹具（formal_compute、ledger_pnl、liability_v1_samples 等）。
- `backend/tests/core_finance/`、`backend/tests/services/`: 后端侧补充单测（core_finance、executive/pnl_attribution 等）。

## 维护

本表是导航快照，不是自动生成物。重新核对入口:

- 前端路由: `frontend/src/router/routes.tsx`
- 后端注册: `backend/app/api/__init__.py`（`ROUTE_REGISTRY`）

新增/调整页面或路由时，请同步更新对应行。
