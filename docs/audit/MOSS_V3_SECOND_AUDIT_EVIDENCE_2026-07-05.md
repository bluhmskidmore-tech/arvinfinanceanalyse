# MOSS-V3 Second Audit Evidence Lock

Generated: 2026-07-05 America/New_York
Repository: F:\MOSS-V3
Purpose: evidence lock for Pro second-pass architecture audit after the 2026-07-04 handoff package was judged usable but not independently verifiable.

## Scope

This file records current repository evidence only. It intentionally does not modify business code, frontend code, backend code, schemas, routes, tests, or configuration.

The prior handoff package was generated on 2026-07-04. This evidence was collected on 2026-07-05, so it supersedes the older handoff statements where current command output differs.

Post-build-unblock update: later on 2026-07-05, the stock-analysis / Livermore `return_10d` frontend contract drift that blocked `npm run build` was fixed and reverified. The original failed build evidence is retained below as pre-fix history; the current result is the later passing build entry.

## Git Identity

- Branch: opt/2026-07-position-gate-batch2
- HEAD: a1e1ce80d0ef56ef149b95727e20bae4004517ac
- Dirty entries before creating this evidence file/directory: 264
- Current dirty entries including this untracked evidence directory: 265
- Git displays the untracked evidence path as: ?? docs/audit/
- Final dirty entries after the stock-analysis build unblock and evidence-package refresh, reported by `git status --short | Measure-Object -Line`: 265

## Current Dirty Worktree

The worktree is materially dirty and contains many files that cannot be attributed to the 03A / 06 / 12 remediation without a separate ownership pass. This is a P1 audit-process risk: future review must not treat every dirty file as part of the architecture remediation.

~~~text
 M .codex/skills/moss-fixed-income-portfolio/SKILL.md
 M .codex/skills/moss-lineage-break-trace/SKILL.md
 M .codex/skills/moss-metric-audit/SKILL.md
 M .codex/skills/moss-page-contract-tieout/SKILL.md
 M .codex/skills/moss-rollforward-variance/SKILL.md
 M AGENTS.md
 M CLAUDE.md
 M audit_pack/00_AUDIT_PACKAGE_README.md
 M backend/app/api/__init__.py
 M backend/app/api/routes/executive.py
 M backend/app/api/routes/pnl_attribution.py
 M backend/app/core_finance/adb_analytics.py
 M backend/app/core_finance/adb_rate_normalize.py
 M backend/app/core_finance/campisi.py
 M backend/app/core_finance/decimal_utils.py
 M backend/app/core_finance/factor_screen_candidates.py
 M backend/app/core_finance/hybrid_fusion_candidates.py
 M backend/app/core_finance/livermore_risk_exit.py
 M backend/app/core_finance/mean_reversion_candidates.py
 M backend/app/schema_registry/duckdb/28_livermore_candidate_history.sql
 M backend/app/schema_registry/duckdb/manifest.json
 M backend/app/schemas/bond_analytics.py
 M backend/app/schemas/executive_dashboard.py
 M backend/app/schemas/liability_analytics.py
 M backend/app/schemas/pnl_attribution.py
 M backend/app/services/adb_analysis_service.py
 M backend/app/services/bond_analytics_service.py
 M backend/app/services/campisi_attribution_service.py
 M backend/app/services/liability_analytics_service.py
 M backend/app/services/market_data_livermore_service.py
 M backend/app/tasks/livermore_candidate_history_materialize.py
 M backend/app/tasks/livermore_candidate_history_run.py
 M backend/tests/core_finance/test_factor_screen_candidates.py
 M backend/tests/core_finance/test_uptrend_momentum_candidates.py
 M config/dashboard_macro_release_calendar_2026.json
 M docs/BALANCE_ANALYSIS_FX_SOURCE_RUNBOOK.md
 M docs/V3_CUTOFF_DECLARATION_2026-04-17.md
 M docs/audits/2026-06-10-direct-app-mcp-gitnexus-tool-surface-snapshot.json
 M docs/audits/2026-06-10-local-secret-hygiene-snapshot.json
 M docs/calc_rules.md
 M docs/design-artifacts/README.md
 M docs/golden_sample_catalog.md
 M docs/golden_sample_plan.md
 M docs/live_route_maturity.md
 M docs/metric_dictionary.md
 M frontend/src/api/bondAnalyticsClient.ts
 M frontend/src/api/executiveClient.ts
 M frontend/src/api/homeMarketTickerMockClient.ts
 M frontend/src/api/homeSupplementalClient.ts
 M frontend/src/api/liabilityAdbClient.ts
 M frontend/src/app/providers.tsx
 M frontend/src/components/LightIcon.tsx
 M frontend/src/components/grid/gridDefaults.ts
 M frontend/src/features/agent/AgentWorkbenchPage.css
 M frontend/src/features/agent/AgentWorkbenchPage.tsx
 M frontend/src/features/agent/components/AgentGenericCardsGrid.tsx
 M frontend/src/features/agent/components/AgentQueryForm.tsx
 M frontend/src/features/average-balance/components/AdbCoverageDiagnostics.tsx
 M frontend/src/features/average-balance/components/AverageBalanceView.tsx
 M frontend/src/features/bond-analytics/components/BondAnalyticsInstitutionalCockpit.tsx
 M frontend/src/features/bond-analytics/lib/bondAnalyticsModuleReadiness.test.ts
 M frontend/src/features/bond-analytics/lib/bondAnalyticsModuleReadiness.ts
 M frontend/src/features/cross-asset/pages/CrossAssetDriversPage.css
 M frontend/src/features/cross-asset/pages/CrossAssetDriversPage.tsx
 M frontend/src/features/executive-dashboard/components/ContributionSection.tsx
 M frontend/src/features/executive-dashboard/components/DashboardBondHeadlineSection.tsx
 M frontend/src/features/executive-dashboard/components/DashboardCockpitSection.tsx
 M frontend/src/features/executive-dashboard/components/SummarySection.tsx
 M frontend/src/features/liability-analytics/utils/nimStress.test.ts
 M frontend/src/features/liability-analytics/utils/nimStress.ts
 M frontend/src/features/news-events/NewsEventsPage.tsx
 M frontend/src/features/pnl-attribution/components/CampisiDecisionGradePanel.tsx
 M frontend/src/features/pnl/YieldAnalysisPage.tsx
 M frontend/src/features/pnl/zqtzAdbAvgRollup.test.ts
 M frontend/src/features/pnl/zqtzAdbAvgRollup.ts
 M frontend/src/features/risk-tensor/RiskTensorPage.css
 M frontend/src/features/risk-tensor/RiskTensorPage.tsx
 M frontend/src/features/stock-analysis/components/StockAnalysisStrategyReviewCards.tsx
 M frontend/src/features/stock-analysis/lib/stockAnalysisBacktestModel.ts
 M frontend/src/features/stock-analysis/lib/stockAnalysisPageCopy.ts
 M frontend/src/features/stock-analysis/lib/stockAnalysisPageModel.ts
 M frontend/src/features/workbench/dashboard-home/DashboardHomePage.tsx
 M frontend/src/features/workbench/dashboard-home/DeferredTerminalHomeBody.tsx
 M frontend/src/features/workbench/dashboard-home/DeferredTerminalHomeContent.tsx
 M frontend/src/features/workbench/dashboard-home/HomeSparkline.tsx
 M frontend/src/features/workbench/dashboard-home/TerminalHomeContent.drilldowns.test.tsx
 M frontend/src/features/workbench/dashboard-home/TerminalHomeContent.tsx
 M frontend/src/features/workbench/dashboard-home/TerminalHomeDeferredSections.tsx
 M frontend/src/features/workbench/dashboard-home/TerminalHomeFirstScreen.tsx
 M frontend/src/features/workbench/dashboard-home/TerminalHomeWorkGrid.tsx
 M frontend/src/features/workbench/dashboard-home/adapters/buildHomeBondNewsModel.ts
 M frontend/src/features/workbench/dashboard-home/adapters/buildHomeMacroBriefingModel.test.ts
 M frontend/src/features/workbench/dashboard-home/adapters/buildHomeMacroBriefingModel.ts
 M frontend/src/features/workbench/dashboard-home/adapters/dashboardHomeAdapters.test.ts
 M frontend/src/features/workbench/dashboard-home/dashboardHome.module.css
 M frontend/src/features/workbench/dashboard-home/dashboardHomeBodyView.ts
 M frontend/src/features/workbench/dashboard-home/dashboardHomeFirstScreenActions.test.tsx
 M frontend/src/features/workbench/dashboard-home/dashboardHomeFirstScreenTypes.ts
 M frontend/src/features/workbench/dashboard-home/dashboardHomeFirstScreenView.ts
 M frontend/src/features/workbench/dashboard-home/dashboardHomeShell.module.css
 M frontend/src/features/workbench/dashboard-home/dashboardHomeView.test.ts
 M frontend/src/features/workbench/dashboard-home/sections/DashboardHomeToolbar.tsx
 M frontend/src/features/workbench/dashboard-home/sections/DecisionRailSection.tsx
 M frontend/src/features/workbench/dashboard-home/sections/ResearchCalendarSection.test.tsx
 M frontend/src/features/workbench/dashboard-home/sections/ResearchCalendarSection.tsx
 M frontend/src/features/workbench/dashboard-home/useDashboardHomeFirstScreenViewModel.ts
 M frontend/src/features/workbench/dashboard-home/useDashboardHomeViewModel.ts
 M frontend/src/features/workbench/module-home/MarketActionQueue.tsx
 M frontend/src/features/workbench/module-home/MarketCrisisExplainBand.tsx
 M frontend/src/features/workbench/module-home/MarketDepthPanel.test.tsx
 M frontend/src/features/workbench/module-home/MarketHomeLayout.tsx
 M frontend/src/features/workbench/module-home/MarketHomePage.tsx
 M frontend/src/features/workbench/module-home/MarketMacroTickerBar.tsx
 M frontend/src/features/workbench/module-home/ModuleWorkbenchHomePage.tsx
 M frontend/src/features/workbench/module-home/PortfolioHoldingsHeroBand.tsx
 M frontend/src/features/workbench/module-home/PortfolioHomeLayout.tsx
 M frontend/src/features/workbench/module-home/PortfolioHomePage.tsx
 M frontend/src/features/workbench/module-home/PortfolioRiskTickerBar.tsx
 M frontend/src/features/workbench/module-home/PortfolioStructureChart.tsx
 M frontend/src/features/workbench/module-home/PortfolioStructureTabPanel.tsx
 M frontend/src/features/workbench/module-home/marketHome.module.css
 M frontend/src/features/workbench/module-home/moduleHomeModel.ts
 M frontend/src/features/workbench/module-home/moduleWorkbenchHome.module.css
 M frontend/src/features/workbench/module-home/portfolioDecisionModel.ts
 M frontend/src/features/workbench/module-home/portfolioDistributionChart.ts
 M frontend/src/features/workbench/module-home/portfolioHome.module.css
 M frontend/src/fixtures/dashboardCoreWorkbenchSamples.ts
 M frontend/src/layouts/WorkbenchShell.tsx
 M frontend/src/lib/echarts.tsx
 M frontend/src/mocks/mockApiEnvelope.ts
 M frontend/src/mocks/navigation.ts
 M frontend/src/styles/dashboardCockpit.css
 M frontend/src/styles/global.css
 M frontend/src/styles/workbenchShell.css
 M frontend/src/test/AgentWorkbenchPage.test.tsx
 M frontend/src/test/ApiClient.test.ts
 M frontend/src/test/AppProvidersTheme.test.tsx
 M frontend/src/test/AverageBalanceView.test.tsx
 M frontend/src/test/BondAnalyticsClient.test.ts
 M frontend/src/test/CampisiDecisionGradePanel.test.tsx
 M frontend/src/test/DashboardBondHeadlineSection.test.tsx
 M frontend/src/test/DashboardHomePage.test.tsx
 M frontend/src/test/DashboardHomeStatus.test.tsx
 M frontend/src/test/DeferredTerminalHomeContent.test.tsx
 M frontend/src/test/HomeStartupClient.test.ts
 M frontend/src/test/LiveRouteReadiness.test.tsx
 M frontend/src/test/ModuleWorkbenchHomeModel.test.ts
 M frontend/src/test/ModuleWorkbenchHomePage.test.tsx
 M frontend/src/test/MossAgGrid.test.tsx
 M frontend/src/test/NewsEventsPage.test.tsx
 M frontend/src/test/PortfolioDecisionModel.test.ts
 M frontend/src/test/PortfolioHomeCrossPageConsistency.test.tsx
 M frontend/src/test/RiskTensorPage.test.tsx
 M frontend/src/test/StartupPerformanceGuards.test.ts
 M frontend/src/test/StockAnalysisBacktestModel.test.ts
 M frontend/src/test/StockAnalysisPageModel.test.ts
 M frontend/src/test/TailwindIntegration.test.ts
 M frontend/src/test/WorkbenchShell.test.tsx
 M frontend/src/test/liveRouteReadinessContracts.ts
 M frontend/src/test/navigation.test.ts
 M frontend/src/test/portfolioCrossPageGoldenSample.ts
 M scripts/codex-page-readiness.ps1
 M scripts/dev-agent-api.cmd
 M scripts/dev-agent-api.ps1
 M scripts/dev_postgres_cluster.py
 M scripts/stock_strategy_health_diagnostic.py
 M tests/core_finance/test_rate_normalization_heuristic.py
 M tests/golden_samples/GS-CONCENTRATION-MONITOR-A/response.json
 M tests/test_adb_analysis_api.py
 M tests/test_adb_rate_normalize.py
 M tests/test_bond_analytics_curve_effects.py
 M tests/test_bond_analytics_numeric_migration.py
 M tests/test_bond_analytics_service_real_data.py
 M tests/test_campisi.py
 M tests/test_campisi_attribution_service.py
 M tests/test_decimal_utils_strict.py
 M tests/test_duckdb_schema_registry_contract.py
 M tests/test_executive_dashboard_endpoints.py
 M tests/test_home_snapshot_endpoint.py
 M tests/test_hybrid_fusion_candidates.py
 M tests/test_liability_analytics_api.py
 M tests/test_liability_analytics_numeric_migration.py
 M tests/test_live_route_page_contract_completeness.py
 M tests/test_livermore_risk_exit.py
 M tests/test_no_finance_logic_in_frontend.py
 M tests/test_stock_strategy_health_diagnostic.py
?? .claude/skills/
?? audit_pack/09_WEB_PRO_ARCHITECTURE_AUDIT_PROMPT.md
?? backend/app/api/routes/macro_etf_strategy.py
?? backend/app/core_finance/adjusted_returns.py
?? backend/app/core_finance/gate_exposure_series.py
?? backend/app/core_finance/macro/macro_etf_strategy.py
?? backend/app/core_finance/matched_baseline.py
?? backend/app/core_finance/portfolio_backtest.py
?? backend/app/core_finance/portfolio_paths.py
?? backend/app/core_finance/strategy_policy.py
?? backend/app/core_finance/vol_target_overlay.py
?? backend/app/schema_registry/duckdb/30_stock_adjustment_factor.sql
?? backend/app/schema_registry/duckdb/31_livermore_matched_baseline.sql
?? backend/app/services/macro_etf_strategy_service.py
?? backend/tests/core_finance/test_strategy_policy.py
?? config/macro_etf_macro_state.json
?? config/macro_etf_strategy.json
?? docs/audit/
?? docs/plans/2026-07-04-product-category-pnl-optimization/
?? docs/pnl/2026-07-04-opt-batch-baseline.md
?? docs/pnl/2026-07-adjusted-vs-unadjusted-report.md
?? docs/pnl/2026-07-batch2-baseline.md
?? docs/pnl/2026-07-batch2-entry-premium-report.md
?? docs/pnl/2026-07-batch2-gate-flip-report.md
?? docs/pnl/2026-07-batch2-hold-progress-matrix.md
?? docs/pnl/2026-07-batch2-macro-multiplier-report.md
?? docs/pnl/2026-07-batch2-overheat-holdings-report.md
?? docs/pnl/2026-07-batch3-data-readiness-report.md
?? docs/pnl/2026-07-batch3-entry-premium-interaction-report.md
?? docs/pnl/2026-07-batch3-hold-progress-exit-simulation-report.md
?? docs/pnl/2026-07-batch3-package-manifest.md
?? docs/pnl/2026-07-batch3-risk-budget-robustness-report.md
?? docs/pnl/2026-07-batch3-summary.md
?? docs/pnl/2026-07-portfolio-backtest-report.md
?? docs/pnl/2026-07-risk-exit-validation.md
?? docs/pnl/2026-07-walk-forward-report.md
?? frontend/src/components/Skeletons.tsx
?? frontend/src/features/cross-asset/components/AssetAnalysisPanels.tsx
?? frontend/src/features/cross-asset/components/CorrelationAndRegimePanels.tsx
?? frontend/src/features/cross-asset/components/CrossAssetDecisionZone.tsx
?? frontend/src/features/cross-asset/components/LegacyPanels.tsx
?? frontend/src/features/cross-asset/components/LivermorePanels.tsx
?? frontend/src/features/cross-asset/components/MarketTapePanels.tsx
?? frontend/src/features/cross-asset/components/MomentumAndVolatilityPanels.tsx
?? frontend/src/features/cross-asset/components/ReferencePanels.tsx
?? frontend/src/features/cross-asset/components/shared.ts
?? frontend/src/features/cross-asset/components/utils.ts
?? frontend/src/features/cross-asset/hooks/
?? frontend/src/features/pnl/__fixtures__/
?? frontend/src/features/workbench/dashboard-home/DashboardHomeAmbientCanvas.tsx
?? frontend/src/features/workbench/dashboard-home/DeferredEvidenceIndexPreview.tsx
?? frontend/src/features/workbench/dashboard-home/adapters/mapHomeSummaryDistributions.ts
?? frontend/src/mocks/mockApiEnvelope.test.ts
?? scripts/backfill_adjusted_returns.py
?? scripts/backfill_stock_adjustment_factor.py
?? scripts/diagnose_entry_premium.py
?? scripts/diagnose_gate_state_flips.py
?? scripts/diagnose_macro_multiplier.py
?? scripts/diagnose_overheat_holdings.py
?? scripts/export_zqtz_adb_rollup_fixture.py
?? scripts/run_batch3_stock_strategy_research.py
?? scripts/run_matched_baseline_backfill.py
?? scripts/run_portfolio_backtest.py
?? scripts/validate_risk_exit_rules.py
?? scripts/walk_forward_threshold_scan.py
?? tests/test_adjusted_returns_backfill.py
?? tests/test_batch3_stock_strategy_research.py
?? tests/test_entry_premium_diagnostic.py
?? tests/test_envelope_contract.py
?? tests/test_gate_exposure_series.py
?? tests/test_gate_state_flip_diagnostic.py
?? tests/test_macro_etf_strategy.py
?? tests/test_macro_multiplier_diagnostic.py
?? tests/test_matched_baseline.py
?? tests/test_overheat_holdings_diagnostic.py
?? tests/test_portfolio_backtest.py
?? tests/test_portfolio_paths.py
?? tests/test_vol_target_overlay.py
?? tests/test_walk_forward_threshold_scan.py
~~~

## Overall Diff Stat

~~~text
 .codex/skills/moss-fixed-income-portfolio/SKILL.md |    2 +-
 .codex/skills/moss-lineage-break-trace/SKILL.md    |    2 +-
 .codex/skills/moss-metric-audit/SKILL.md           |    2 +-
 .codex/skills/moss-page-contract-tieout/SKILL.md   |    2 +-
 .codex/skills/moss-rollforward-variance/SKILL.md   |    2 +-
 AGENTS.md                                          |   44 +
 CLAUDE.md                                          |   44 +
 audit_pack/00_AUDIT_PACKAGE_README.md              |    8 +-
 backend/app/api/__init__.py                        |    2 +
 backend/app/api/routes/executive.py                |   12 +-
 backend/app/api/routes/pnl_attribution.py          |   16 +-
 backend/app/core_finance/adb_analytics.py          |   42 +-
 backend/app/core_finance/adb_rate_normalize.py     |   14 +-
 backend/app/core_finance/campisi.py                |   47 +-
 backend/app/core_finance/decimal_utils.py          |   34 +-
 .../app/core_finance/factor_screen_candidates.py   |   62 +-
 .../app/core_finance/hybrid_fusion_candidates.py   |   27 +-
 backend/app/core_finance/livermore_risk_exit.py    |   20 +-
 .../app/core_finance/mean_reversion_candidates.py  |    4 +-
 .../duckdb/28_livermore_candidate_history.sql      |   58 +
 backend/app/schema_registry/duckdb/manifest.json   |   10 +
 backend/app/schemas/bond_analytics.py              |   74 +
 backend/app/schemas/executive_dashboard.py         |   10 +-
 backend/app/schemas/liability_analytics.py         |   18 +
 backend/app/schemas/pnl_attribution.py             |   21 +-
 backend/app/services/adb_analysis_service.py       |  124 +-
 backend/app/services/bond_analytics_service.py     |  102 +-
 .../app/services/campisi_attribution_service.py    |   45 +-
 .../app/services/liability_analytics_service.py    |   30 +
 .../app/services/market_data_livermore_service.py  |    9 +-
 .../livermore_candidate_history_materialize.py     |  782 ++-
 .../app/tasks/livermore_candidate_history_run.py   |   21 +-
 .../core_finance/test_factor_screen_candidates.py  |    8 +
 .../test_uptrend_momentum_candidates.py            |   21 +-
 config/dashboard_macro_release_calendar_2026.json  |   78 +-
 docs/BALANCE_ANALYSIS_FX_SOURCE_RUNBOOK.md         |   30 +
 docs/V3_CUTOFF_DECLARATION_2026-04-17.md           |   17 +
 ...ect-app-mcp-gitnexus-tool-surface-snapshot.json |   32 +-
 .../2026-06-10-local-secret-hygiene-snapshot.json  |    2 +-
 docs/calc_rules.md                                 |   13 +
 docs/design-artifacts/README.md                    |    6 +
 docs/golden_sample_catalog.md                      |    4 +-
 docs/golden_sample_plan.md                         |   10 +-
 docs/live_route_maturity.md                        |    4 +-
 docs/metric_dictionary.md                          |    7 +-
 frontend/src/api/bondAnalyticsClient.ts            |  129 +-
 frontend/src/api/executiveClient.ts                |  125 +
 frontend/src/api/homeMarketTickerMockClient.ts     |   43 +
 frontend/src/api/homeSupplementalClient.ts         |   23 +-
 frontend/src/api/liabilityAdbClient.ts             |   10 +
 frontend/src/app/providers.tsx                     |   57 +-
 frontend/src/components/LightIcon.tsx              |   16 +
 frontend/src/components/grid/gridDefaults.ts       |   35 +-
 frontend/src/features/agent/AgentWorkbenchPage.css |  278 +-
 frontend/src/features/agent/AgentWorkbenchPage.tsx |  490 +-
 .../agent/components/AgentGenericCardsGrid.tsx     |   85 +
 .../features/agent/components/AgentQueryForm.tsx   |    8 +-
 .../components/AdbCoverageDiagnostics.tsx          |   29 +-
 .../components/AverageBalanceView.tsx              |   47 +-
 .../BondAnalyticsInstitutionalCockpit.tsx          |   88 +-
 .../lib/bondAnalyticsModuleReadiness.test.ts       |   37 +
 .../lib/bondAnalyticsModuleReadiness.ts            |   51 +-
 .../cross-asset/pages/CrossAssetDriversPage.css    |    9 +-
 .../cross-asset/pages/CrossAssetDriversPage.tsx    | 3796 +------------
 .../components/ContributionSection.tsx             |   73 +-
 .../components/DashboardBondHeadlineSection.tsx    |   20 +-
 .../components/DashboardCockpitSection.tsx         |   31 +-
 .../components/SummarySection.tsx                  |   46 +-
 .../liability-analytics/utils/nimStress.test.ts    |   27 +-
 .../liability-analytics/utils/nimStress.ts         |   32 +-
 .../src/features/news-events/NewsEventsPage.tsx    |   86 +-
 .../components/CampisiDecisionGradePanel.tsx       |    5 +-
 frontend/src/features/pnl/YieldAnalysisPage.tsx    |    7 +-
 frontend/src/features/pnl/zqtzAdbAvgRollup.test.ts |   22 +-
 frontend/src/features/pnl/zqtzAdbAvgRollup.ts      |   10 +-
 .../src/features/risk-tensor/RiskTensorPage.css    |  226 +-
 .../src/features/risk-tensor/RiskTensorPage.tsx    |  180 +-
 .../StockAnalysisStrategyReviewCards.tsx           |    6 +
 .../lib/stockAnalysisBacktestModel.ts              |   23 +-
 .../stock-analysis/lib/stockAnalysisPageCopy.ts    |    7 +
 .../stock-analysis/lib/stockAnalysisPageModel.ts   |    7 +-
 .../workbench/dashboard-home/DashboardHomePage.tsx |   96 +-
 .../dashboard-home/DeferredTerminalHomeBody.tsx    |    3 +
 .../dashboard-home/DeferredTerminalHomeContent.tsx |    9 +-
 .../workbench/dashboard-home/HomeSparkline.tsx     |   62 +-
 .../TerminalHomeContent.drilldowns.test.tsx        |  334 +-
 .../dashboard-home/TerminalHomeContent.tsx         |   73 +-
 .../TerminalHomeDeferredSections.tsx               |    7 -
 .../dashboard-home/TerminalHomeFirstScreen.tsx     |  446 +-
 .../dashboard-home/TerminalHomeWorkGrid.tsx        | 1616 +++++-
 .../adapters/buildHomeBondNewsModel.ts             |   38 +-
 .../adapters/buildHomeMacroBriefingModel.test.ts   |   39 +
 .../adapters/buildHomeMacroBriefingModel.ts        |  101 +-
 .../adapters/dashboardHomeAdapters.test.ts         |  101 +
 .../dashboard-home/dashboardHome.module.css        | 3817 ++++++++++++-
 .../dashboard-home/dashboardHomeBodyView.ts        |  281 +-
 .../dashboardHomeFirstScreenActions.test.tsx       |  258 +-
 .../dashboardHomeFirstScreenTypes.ts               |    2 +-
 .../dashboard-home/dashboardHomeFirstScreenView.ts |   28 +-
 .../dashboard-home/dashboardHomeShell.module.css   | 4047 ++++++++++++-
 .../dashboard-home/dashboardHomeView.test.ts       |    2 +-
 .../sections/DashboardHomeToolbar.tsx              |   40 +-
 .../sections/DecisionRailSection.tsx               |  428 +-
 .../sections/ResearchCalendarSection.test.tsx      |   68 +-
 .../sections/ResearchCalendarSection.tsx           |   78 +
 .../useDashboardHomeFirstScreenViewModel.ts        |    7 +-
 .../dashboard-home/useDashboardHomeViewModel.ts    |   27 +-
 .../workbench/module-home/MarketActionQueue.tsx    |    2 +
 .../module-home/MarketCrisisExplainBand.tsx        |   12 +-
 .../module-home/MarketDepthPanel.test.tsx          |    6 +
 .../workbench/module-home/MarketHomeLayout.tsx     |  184 +-
 .../workbench/module-home/MarketHomePage.tsx       |   77 +
 .../workbench/module-home/MarketMacroTickerBar.tsx |    4 +-
 .../module-home/ModuleWorkbenchHomePage.tsx        |  187 +-
 .../module-home/PortfolioHoldingsHeroBand.tsx      |  232 +-
 .../workbench/module-home/PortfolioHomeLayout.tsx  |  639 ++-
 .../workbench/module-home/PortfolioHomePage.tsx    |    3 +-
 .../module-home/PortfolioRiskTickerBar.tsx         |    4 +-
 .../module-home/PortfolioStructureChart.tsx        |   33 +-
 .../module-home/PortfolioStructureTabPanel.tsx     |   49 +-
 .../workbench/module-home/marketHome.module.css    |  159 +-
 .../workbench/module-home/moduleHomeModel.ts       |   49 +-
 .../module-home/moduleWorkbenchHome.module.css     |   25 +
 .../module-home/portfolioDecisionModel.ts          |   27 +-
 .../module-home/portfolioDistributionChart.ts      |   18 +-
 .../workbench/module-home/portfolioHome.module.css | 5931 ++++++++++++++++----
 .../src/fixtures/dashboardCoreWorkbenchSamples.ts  |   37 +-
 frontend/src/layouts/WorkbenchShell.tsx            |   13 +-
 frontend/src/lib/echarts.tsx                       |   52 +-
 frontend/src/mocks/mockApiEnvelope.ts              |    7 +-
 frontend/src/mocks/navigation.ts                   |    9 +-
 frontend/src/styles/dashboardCockpit.css           |    8 +-
 frontend/src/styles/global.css                     |    1 +
 frontend/src/styles/workbenchShell.css             |   10 +-
 frontend/src/test/AgentWorkbenchPage.test.tsx      |  410 +-
 frontend/src/test/ApiClient.test.ts                |  194 +-
 frontend/src/test/AppProvidersTheme.test.tsx       |   14 +-
 frontend/src/test/AverageBalanceView.test.tsx      |    4 +
 frontend/src/test/BondAnalyticsClient.test.ts      |    9 +-
 .../src/test/CampisiDecisionGradePanel.test.tsx    |   18 +
 .../src/test/DashboardBondHeadlineSection.test.tsx |   54 +-
 frontend/src/test/DashboardHomePage.test.tsx       |  112 +-
 frontend/src/test/DashboardHomeStatus.test.tsx     |   20 +-
 .../src/test/DeferredTerminalHomeContent.test.tsx  |   19 +-
 frontend/src/test/HomeStartupClient.test.ts        |   52 +
 frontend/src/test/LiveRouteReadiness.test.tsx      |   17 +-
 frontend/src/test/ModuleWorkbenchHomeModel.test.ts |    2 +-
 frontend/src/test/ModuleWorkbenchHomePage.test.tsx |  439 +-
 frontend/src/test/MossAgGrid.test.tsx              |   11 +-
 frontend/src/test/NewsEventsPage.test.tsx          |   49 +
 frontend/src/test/PortfolioDecisionModel.test.ts   |   69 +-
 .../PortfolioHomeCrossPageConsistency.test.tsx     |   71 +-
 frontend/src/test/RiskTensorPage.test.tsx          |  152 +-
 frontend/src/test/StartupPerformanceGuards.test.ts |   18 +-
 .../src/test/StockAnalysisBacktestModel.test.ts    |   74 +
 frontend/src/test/StockAnalysisPageModel.test.ts   |   90 +
 frontend/src/test/TailwindIntegration.test.ts      |   19 +-
 frontend/src/test/WorkbenchShell.test.tsx          |   14 +-
 frontend/src/test/liveRouteReadinessContracts.ts   |   12 +-
 frontend/src/test/navigation.test.ts               |    5 +-
 .../src/test/portfolioCrossPageGoldenSample.ts     |  277 +-
 scripts/codex-page-readiness.ps1                   |    3 +
 scripts/dev-agent-api.cmd                          |    2 +
 scripts/dev-agent-api.ps1                          |    2 +
 scripts/dev_postgres_cluster.py                    |    2 +
 scripts/stock_strategy_health_diagnostic.py        |  229 +-
 .../test_rate_normalization_heuristic.py           |   19 +-
 .../GS-CONCENTRATION-MONITOR-A/response.json       |   36 +-
 tests/test_adb_analysis_api.py                     |   67 +
 tests/test_adb_rate_normalize.py                   |   12 +-
 tests/test_bond_analytics_curve_effects.py         |    4 +
 tests/test_bond_analytics_numeric_migration.py     |   19 +
 tests/test_bond_analytics_service_real_data.py     |   36 +-
 tests/test_campisi.py                              |   82 +
 tests/test_campisi_attribution_service.py          |   86 +-
 tests/test_decimal_utils_strict.py                 |   61 +
 tests/test_duckdb_schema_registry_contract.py      |    1 +
 tests/test_executive_dashboard_endpoints.py        |   38 +-
 tests/test_home_snapshot_endpoint.py               |  175 +-
 tests/test_hybrid_fusion_candidates.py             |   10 +-
 tests/test_liability_analytics_api.py              |   58 +
 .../test_liability_analytics_numeric_migration.py  |   16 +
 .../test_live_route_page_contract_completeness.py  |    4 -
 tests/test_livermore_risk_exit.py                  |    2 +
 tests/test_no_finance_logic_in_frontend.py         |   31 +
 tests/test_stock_strategy_health_diagnostic.py     |  159 +-
 186 files changed, 24011 insertions(+), 7240 deletions(-)
~~~

## Claimed Remediation Boundary

Codex previously claimed implementation/verification for Prompt 03A, Prompt 06, and Prompt 12 only. The current dirty boundary for those claims is:

~~~text
 M backend/app/api/routes/executive.py
 M backend/app/api/routes/pnl_attribution.py
 M backend/app/schemas/bond_analytics.py
 M backend/app/schemas/executive_dashboard.py
 M backend/app/schemas/pnl_attribution.py
 M backend/app/services/bond_analytics_service.py
 M docs/V3_CUTOFF_DECLARATION_2026-04-17.md
 M frontend/src/api/bondAnalyticsClient.ts
 M frontend/src/api/homeSupplementalClient.ts
 M frontend/src/features/bond-analytics/lib/bondAnalyticsModuleReadiness.test.ts
 M frontend/src/features/bond-analytics/lib/bondAnalyticsModuleReadiness.ts
 M frontend/src/test/BondAnalyticsClient.test.ts
 M frontend/src/test/HomeStartupClient.test.ts
 M tests/golden_samples/GS-CONCENTRATION-MONITOR-A/response.json
 M tests/test_bond_analytics_curve_effects.py
 M tests/test_bond_analytics_numeric_migration.py
 M tests/test_bond_analytics_service_real_data.py
 M tests/test_executive_dashboard_endpoints.py
 M tests/test_home_snapshot_endpoint.py
?? tests/test_envelope_contract.py
~~~

Related tracked diff stat:

~~~text
 backend/app/api/routes/executive.py                |  12 +-
 backend/app/api/routes/pnl_attribution.py          |  16 +-
 backend/app/schemas/bond_analytics.py              |  74 +++++++++
 backend/app/schemas/executive_dashboard.py         |  10 +-
 backend/app/schemas/pnl_attribution.py             |  21 ++-
 backend/app/services/bond_analytics_service.py     | 102 ++++++++++--
 docs/V3_CUTOFF_DECLARATION_2026-04-17.md           |  17 ++
 frontend/src/api/bondAnalyticsClient.ts            | 129 ++++++++-------
 frontend/src/api/homeSupplementalClient.ts         |  23 +--
 .../lib/bondAnalyticsModuleReadiness.test.ts       |  37 +++++
 .../lib/bondAnalyticsModuleReadiness.ts            |  51 +++++-
 frontend/src/test/BondAnalyticsClient.test.ts      |   9 +-
 frontend/src/test/HomeStartupClient.test.ts        |  52 ++++++
 .../GS-CONCENTRATION-MONITOR-A/response.json       |  36 ++++-
 tests/test_bond_analytics_curve_effects.py         |   4 +
 tests/test_bond_analytics_numeric_migration.py     |  19 +++
 tests/test_bond_analytics_service_real_data.py     |  36 ++++-
 tests/test_executive_dashboard_endpoints.py        |  38 ++++-
 tests/test_home_snapshot_endpoint.py               | 175 ++++++++++++++-------
 19 files changed, 678 insertions(+), 183 deletions(-)
~~~

Notes:

- tests/test_envelope_contract.py is untracked and therefore does not appear in git diff --stat, but it is part of the Prompt 06 evidence boundary.
- tests/test_pnl_attribution_api_contract.py is referenced by validation but is not dirty at this evidence point.
- The broader worktree contains many unrelated modified and untracked files.

## Prompt 03A Evidence

Current code evidence found by search:

- backend/app/api/routes/executive.py imports and calls home_snapshot_envelope.
- backend/app/api/routes/executive.py contains /ui/home/snapshot route wiring through the executive route module.
- backend/app/api/routes/executive.py also has /home/overview with response_model=ExecutiveOverviewEnvelope.
- tests/test_executive_dashboard_endpoints.py contains /ui/home/snapshot route coverage, including route perf logging and invalid date 422 coverage.
- tests/test_home_snapshot_endpoint.py contains service and payload schema coverage for home_snapshot_envelope / HomeSnapshotPayload.
- docs/V3_CUTOFF_DECLARATION_2026-04-17.md records /ui/home/snapshot as promoted to landed executive-consumer cutover v1.

Closure status for Pro: provisionally closeable, but Pro should still inspect the current diff to confirm route semantics, response contract, error path, empty-data behavior, and ownership.

## Prompt 06 Evidence

Current code evidence found by search:

- backend/app/api/routes/pnl_attribution.py uses response_model=PnlAttributionAnalysisSummaryEnvelope and response_model=CampisiAttributionEnvelope with response_model_exclude_unset=True.
- backend/app/api/routes/executive.py uses response_model=ExecutiveOverviewEnvelope on /home/overview.
- backend/app/schemas/pnl_attribution.py defines PnlAttributionAnalysisSummaryEnvelope and CampisiAttributionEnvelope.
- backend/app/schemas/executive_dashboard.py defines ExecutiveOverviewEnvelope.
- tests/test_envelope_contract.py checks OpenAPI schema presence and byte/payload preservation cases for the three modeled endpoints.

Closure status for Pro: local closure for these three endpoints only. Global API response_model/envelope risk remains unaudited and should not be closed from this evidence alone.

## Prompt 12 Evidence

Current code evidence found by search:

- backend/app/services/bond_analytics_service.py preserves spread_scenarios[*].spread_change_bp as governed Numeric JSON after formal Q8 string collapse.
- backend/app/services/bond_analytics_service.py adds _warning_codes_for_payload and merges stable warning_codes into result payloads when present.
- backend/app/schemas/bond_analytics.py defines spread_change_bp: Numeric and multiple optional warning_codes fields with exclusion behavior for unset values.
- frontend/src/api/bondAnalyticsClient.ts and frontend/src/api/homeSupplementalClient.ts import/use parseNumericOrNull and normalize spread_change_bp without flattening governed Numeric objects to plain zero.
- frontend/src/features/bond-analytics/lib/bondAnalyticsModuleReadiness.ts reads warning_codes for readiness decisions.
- frontend/src/test/BondAnalyticsClient.test.ts, frontend/src/test/HomeStartupClient.test.ts, and frontend/src/features/bond-analytics/lib/bondAnalyticsModuleReadiness.test.ts contain frontend regression coverage. After restoring local frontend dependencies with legacy peer resolution, these targeted tests pass as noted below.
- tests/test_bond_analytics_numeric_migration.py, tests/test_bond_analytics_curve_effects.py, and tests/test_bond_analytics_service_real_data.py contain backend regression coverage.
- tests/golden_samples/GS-CONCENTRATION-MONITOR-A/response.json includes governed spread_change_bp and warning_codes evidence.

Closure status for Pro: frontend-targeted and backend-targeted Prompt 12 evidence is now current and passing. The earlier unrelated stock-analysis `return_10d` frontend build/type blocker was later fixed and reverified. Overall release closure is still not "done" because dirty-worktree attribution, CI absence, broad StockAnalysisPage size-guard debt, and global API/security audit gaps remain open.

## Verification Commands Run On 2026-07-05

Backend checks:

~~~text
python -m pytest --collect-only -q
=> 5555 tests collected in 7.86s

python -m pytest tests/test_home_snapshot_endpoint.py tests/test_executive_dashboard_endpoints.py -q
=> 32 passed in 10.66s

python -m pytest tests/test_envelope_contract.py -q
=> 12 passed in 11.96s

python -m pytest tests/test_pnl_attribution_api_contract.py tests/test_executive_dashboard_endpoints.py -q
=> 20 passed in 11.28s

python -m pytest -q tests/test_bond_analytics_numeric_migration.py tests/test_bond_analytics_curve_effects.py -k "credit_spread_migration or numeric or warning_codes"
=> 22 passed, 8 deselected in 5.46s

python -m pytest -q tests/test_bond_analytics_service_real_data.py -k "credit_spread_with_real_facts_returns_expected_scenario_and_concentration or return_decomposition_with_real_facts"
=> 2 passed, 7 deselected in 4.24s
~~~

Frontend checks:

~~~text
npm ci
=> FAILED: ERESOLVE peer conflict. @heroui/react@3.2.1 requires react >=19.0.0 while the project currently uses react 18.3.1.

npm ci --legacy-peer-deps
=> PASSED: added 958 packages and audited 959 packages in 36s. npm reported 4 vulnerabilities (2 moderate, 2 high); no npm audit fix was run.

npm run test -- HomeStartupClient
=> PASSED: 1 test file passed, 2 tests passed.

npm run test -- BondAnalyticsClient
=> PASSED: 1 test file passed, 2 tests passed.

npm run test -- bondAnalyticsModuleReadiness
=> PASSED: 1 test file passed, 7 tests passed.

npm run typecheck
=> PASSED: tsc --noEmit completed with exit code 0.

npm run build
=> FAILED in tsc -b. Failures are unrelated stock-analysis / Livermore candidate history typing errors around missing return_10d fields, for example:
   - src/api/marketDataClient.ts(2692,9): Property 'return_10d' is missing.
   - src/features/stock-analysis/components/StockAnalysisStrategyReviewCards.tsx(467,38): Property 'return_10d' does not exist.
   - multiple src/test/StockAnalysis*.test.* fixtures miss return_10d.

npm run build
=> PASSED after stock-analysis / Livermore return_10d contract alignment: tsc -b completed and Vite built successfully in 15.93s on the latest rerun.

npm run test -- StockAnalysisBacktestModel
=> PASSED: 1 test file passed, 6 tests passed.

npm run test -- StockAnalysisPageModel
=> PASSED: 1 test file passed, 86 tests passed.

npm run test -- StockAnalysisPriorityModel
=> PASSED: 1 test file passed, 6 tests passed.

npm run test -- src/test/StockAnalysisPage.test.tsx
=> PASSED: 1 test file passed, 148 tests passed.

npm run test -- StockAnalysisPage
=> FAILED only because the broad Vitest filter also matched src/test/StockAnalysisPageSizeGuard.test.ts. The unrelated size guard currently asserts StockAnalysisPage.tsx line_count <= 4000, but the file has 5160 lines. This pass did not modify StockAnalysisPage.tsx or StockAnalysisPageSizeGuard.test.ts.

npm run debt:audit
=> PASSED: Frontend debt audit passed (no growth over baseline); api/client.ts lines 560/560, mock occurrences 55/55
~~~

Interpretation:

- Backend evidence is current and passing for the scoped checks above.
- Frontend targeted Prompt 12 tests and `npm run typecheck` are current and passing after dependency restoration.
- `npm run build` is now current and passing after the stock-analysis `return_10d` contract drift was fixed in the frontend client/mock/test fixture boundary.
- `npm run test -- StockAnalysisPage` remains red only because the broad filter includes an out-of-scope size guard for the existing 5160-line StockAnalysisPage.tsx container. The exact page behavior test file `src/test/StockAnalysisPage.test.tsx` passes.
- Independent subagent review initially found a T+10 display-label gap after `primaryHorizon` was widened. The gap was fixed by deriving strategy-score subtitle/KPI labels from the selected horizon, updating mock reason text, and adding a `primary_horizon: "return_10d"` rendering regression.

## Unexecuted Prompt Evidence

The following current evidence supports the earlier stop/rewrite decisions:

- Prompt 01: current `npm run build` can now be closed for the previously observed stock-analysis `return_10d` TypeScript blocker. Dependencies still require `npm ci --legacy-peer-deps` locally because plain `npm ci` hits the React 18 / @heroui React 19 peer conflict. Broad `npm run test -- StockAnalysisPage` remains blocked by the unrelated StockAnalysisPage size guard, not by build/type errors.
- Prompt 02: current backend collection succeeds with 5555 tests collected.
- Prompt 03B: mutually exclusive with implemented Prompt 03A.
- Prompt 04: backend search for STUB, spread = 0.0, or sel = 0.0 in backend/app returned 0 hits; frontend Numeric zero-coercion search returned 75 hits, so this should be rewritten as a frontend Numeric nullability audit rather than executed from the old backend+frontend prompt.
- Prompt 05: mock formal contamination search in frontend/src/api/client.ts and frontend/src/mocks returned 1 hit, located in frontend/src/mocks/mockApiEnvelope.test.ts as an intentional test override; current frontend/src/mocks/mockApiEnvelope.ts forces source_surface: "mock" after overrides but still deserves Pro review for basis / formal_use_allowed override hardening.
- Prompt 07: current route registry and cube query modules exist; backend/app/api/__init__.py has ROUTE_REGISTRY, and backend/app/api/routes/cube_query.py uses Depends(get_auth_context) plus _ensure_cube_read_allowed. Old prompt is stale, but boundary hardening still needs a fresh audit.
- Prompt 08: current auth context tests include default header ignore, opt-in dev trust, and startup guardrail coverage; old unconditional header trust prompt is stale. Gateway secret / proxy allowlist hardening remains a separate security question.
- Prompt 09: frontend/src/api/client.ts currently has 519 lines by Measure-Object -Line; old giant-client prompt is stale.
- Prompt 10: rg "bond-analysis-foundation" frontend/src returned 10 references, all in tests, so zero-reference migration preflight is false.
- Prompt 11: blocked on rewritten Prompt 07.
- Prompt 13: blocked on Prompt 10.

## Required Check Result

git diff --check was run after creating this evidence file, and then rerun after removing one unrelated trailing whitespace instance in frontend/src/features/workbench/module-home/MarketCrisisExplainBand.tsx:243.

Result: PASSED. Git still reports line-ending normalization warnings for a few existing files, but no whitespace errors remain.

After the stock-analysis build unblock, `git diff --check` was rerun and still passed with only line-ending normalization warnings.

## Remaining Evidence Gaps

- No CI artifact is attached.
- No commit was created.
- No staging was performed.
- Frontend dependency restoration required `npm ci --legacy-peer-deps` because plain `npm ci` hits a React 18 vs @heroui/react React 19 peer conflict.
- Frontend targeted tests, `npm run typecheck`, and `npm run build` now pass after the stock-analysis `return_10d` contract drift fix.
- `npm run test -- StockAnalysisPage` remains red because it also runs the pre-existing StockAnalysisPage extraction guard (`5160 <= 4000` failure). Exact `src/test/StockAnalysisPage.test.tsx` passes.
- npm reported 4 vulnerabilities after dependency installation (2 moderate, 2 high); no dependency tree fix was attempted.
- Full global API contract coverage remains unaudited; Prompt 06 only proves three endpoints.
- Route registry / cube query boundary and auth header trust should be reviewed with fresh prompts against current code.
- The worktree contains many unrelated dirty files, so ownership/attribution must be resolved before any final audit closure.
- Some execution-basis stock-analysis tests already existed in the dirty worktree before the `return_10d` build-unblock pass; future reviewers should not misattribute those pre-existing changes to the narrow build fix.


