# 2026-08-27 未提交工作拆分提交执行手册

## 摘要

工作树当前有 **474 个受跟踪变更**（426 M + 48 D；其中 422 个属 2026-08-27 12:31 基线，另外 52 个 M 是手册成文与复核期间在途并行会话陆续新落的，见第 30 组），另有约 213 个未跟踪文件，其中约 110 个属于各提交组的必须/建议捆绑文件，其余为会话残留不提交。全部变更收口为 **30 个提交组 + 1 个暂缓项**。

依赖关系一句话：bond-dashboard 后端 schema 先于其前端重构；stock-analysis 后端先于其前端与调度组；stock-analysis 后端与 livermore 先于 macro-toolkit 后端，macro-toolkit 后端先于其前端与 market-data 组；agent 后端先于 agent 前端；其余组互相独立。

三个跨域文档（`docs/page_contracts.md`、`docs/metric_dictionary.md`、`docs/calc_rules.md`）与 `tests/test_governance_doc_contract.py` 含多个域的 hunk，默认走第 29 组统一同步（简单，但中间提交点治理测试红）；进阶方案是 `git add -p` 按 hunk 跟随各域提交（见第 29 组说明）。

两个此前存疑文件的明确论断：

- `contracts/openapi/openapi.default.json` 与 `contracts/openapi/openapi.full.json` 的**全部** diff 是 `backend/app/schemas/bond_dashboard.py` 的 `weighted_avg_ytm` 字段治理化生成的（`weighted_avg_ytm_pct` string 删除、`weighted_avg_ytm` Numeric 加入 required），**归第 5 组（bond-dashboard 后端）**，不是独立契约组。
- `frontend/package-lock.json` 的 27/757 行 diff **全部**是 tailwindcss、@tailwindcss/vite、tailwind-merge、tailwind-variants、@heroui/styles 五个依赖树的移除，无任何新增依赖，**归第 22 组（tailwind 移除）**，与 `package.json` 同笔。

## 执行前提

1. **并行会话必须先收口**。目前有两个在途：market-data/module-home 前端会话（影响第 12、25 组）与后端基础层会话（bond_analytics / bootstrap / 研究日历，影响第 30 组）。判断方法：间隔 5 分钟以上连续两次运行 `git status --porcelain`，比对对应目录条目与 `git diff --stat -- <对应目录>` 的行数统计，两次完全一致才视为收口。收口前第 12、25、30 组不得提交，其余组不受影响。
2. 每笔提交前运行该组"提交前验证"命令；命令失败先修复或回报，不带红提交。
3. 提交顺序遵循"依赖顺序"一节；无依赖关系的组可按需调整先后。
4. 本手册基线为 2026-08-27 12:31 的 `git status`。若执行时输出与手册清单不一致（并行会话又产生新文件），新增文件按其目录就近归组，并在提交信息中注明。
5. 两个文件行尾是 CRLF（`frontend/src/features/agent/AgentWorkbenchPage.tsx`、`tests/test_agent_runs_api.py`），git 会提示转 LF，属预期，不影响提交。
6. 未跟踪文件用 `git add <明确路径>` 逐一添加，禁止 `git add .` 或 `git add -A`（工作区仍有大量会话残留）。

## 依赖顺序（4 条硬依赖，涉及组用组名指代）

1. **bond-dashboard 后端 YTM 治理**（第 5 组）→ **bond-dashboard 前端重构**（第 6 组）：前端消费 Numeric 载荷。
2. **stock-analysis 后端生产收口**（第 7 组）→ **stock-analysis 前端**（第 8 组）与 **调度与数据健康**（第 13 组）：前端消费 replay_closure 契约；调度链引用第 7 组新增的复权因子/涨跌停任务。
3. **stock-analysis 后端**（第 7 组）+ **livermore 策略核心**（第 9 组）→ **macro-toolkit 后端**（第 10 组）→ **macro-toolkit 前端**（第 11 组）与 **market-data 重构**（第 12 组）：macro_toolkit_service 代理了第 7 组的 `publish_choice_stock_observation_manifest` 与第 9 组的 `run_livermore_daily_pretrade_refresh`；前端与 market-data 页消费第 10 组的刷新状态与 derived spreads 契约。
4. **agent 后端 hermes 本地恢复**（第 20 组）→ **agent 前端工作流卡片与接力**（第 21 组）。

建议整体执行序：1→2→3→4→5→6→7→8→9→10→11→13→14→15→16→17→18→19→20→21→22→23→24→26→27→28→（并行会话收口后）12→25→29。

---

## 第 1 组 chore(repo) — 仓库卫生（清理战役）

- 性质：忽略规则扩充 + 论文构建脚本归档登记。
- commit message：`chore(repo): archive legacy paper build scripts and ignore root scratch`
- 文件清单：
  - M `.gitignore`（含编码审计时期与清理战役两段忽略规则，均为纯忽略行，整体提交）
  - M `docs/paper/moss-financial-agent-paper/VERSIONS.md`
  - ?? `docs/paper/moss-financial-agent-paper/export/legacy-build-scripts/` 整目录（32 个文件，`git add "docs/paper/moss-financial-agent-paper/export/legacy-build-scripts"`）
- 提交前验证：`git status --porcelain | Select-String "^\?\?"` 确认新忽略规则生效后根目录 `_*.py`、`_pending_*`、`.tmp_*` 等残留不再出现在未跟踪列表。
- 风险备注：无代码影响。`unused/` 目录的处理见"归属模糊与待决事项"。

## 第 2 组 docs(agents) — 根规则文档

- 性质：治理文档更新——AGENTS.md 新增文件编码纪律与 docs/plans 历史证据说明，CLAUDE.md 去重瘦身，CLAUDE.local.md 补数据运维偏好。
- commit message：`docs(agents): add the file-encoding discipline and trim duplicated claude guidance`
- 文件清单：
  - M `AGENTS.md`
  - M `CLAUDE.md`
  - M `CLAUDE.local.md`
- 提交前验证：无需测试（纯文档）。
- 风险备注：AGENTS.md 中"docs/plans 历史证据"hunk 与第 4 组归档在语义上配套，但先后提交均不破坏任何东西，无需 hunk 拆分。

## 第 3 组 chore(audit) — 编码完整性护栏

- 性质：debt:audit 链新增编码完整性审计；顺带把 cross-asset CSS 注释里一个已损坏的替换字符（U+FFFD，原为章节号）修复回 `§8`。
- commit message：`chore(audit): add the encoding integrity guard to the debt audit chain`
- 文件清单：
  - M `scripts/run_frontend_debt_audits.mjs`
  - M `frontend/src/features/cross-asset/pages/CrossAssetDriversPage.css`
  - **?? `scripts/audit_encoding_integrity.mjs`（漏掉会导致 debt:audit 链无法运行）**
  - **?? `scripts/audit_encoding_integrity.baseline.json`（同上，审计脚本读取基线）**
- 提交前验证：`node scripts/audit_encoding_integrity.mjs`，随后 `node scripts/run_frontend_debt_audits.mjs`（后者较慢，可选）。
- 风险备注：无业务影响。

## 第 4 组 docs(plans) — 计划与审计文档归档

- 性质：文档归档移动——39 篇历史 plans/audits 移入 archive/ 子目录，零引用校验已通过。**D 与 archive/ 未跟踪副本必须同一笔提交**，否则历史文档凭空消失。
- commit message：`docs(plans): move superseded plans and audits into the archive`
- 文件清单（39 D + 未跟踪副本）：
  - D `docs/audits/2026-05-16-business-closure-audit.md`
  - D `docs/audits/2026-06-07-doc-process-artifact-debt-audit.md`
  - D `docs/plans/2026-04-11-balance-analysis-excel-integration.md`
  - D `docs/plans/2026-04-11-balance-analysis-next-window-prompt.md`
  - D `docs/plans/2026-04-11-choice-macro-refresh-strategy-design.md`
  - D `docs/plans/2026-04-11-pnl-bridge-start-pack.md`
  - D `docs/plans/2026-04-11-zqtz-tyw-formal-balance-analysis.md`
  - D `docs/plans/2026-04-12-balance-analysis-closeout-next-window-prompt.md`
  - D `docs/plans/2026-04-12-macro-bond-linkage-implementation.md`
  - D `docs/plans/2026-04-12-remaining-worktree-closeout-cursor-prompt-v2.md`
  - D `docs/plans/2026-04-12-yield-curve-isolation-manifest.md`
  - D `docs/plans/2026-04-13-macro-bond-linkage-statistical-hardening-plan.md`
  - D `docs/plans/2026-04-15-backend-launch-foundations.md`
  - D `docs/plans/2026-04-16-adb-architecture-convergence.md`
  - D `docs/plans/2026-04-21-bond-analysis-foundation-design.md`
  - D `docs/plans/2026-04-21-external-data-warehouse-m2a-prd.md`
  - D `docs/plans/2026-04-21-external-data-warehouse-m2b-prd.md`
  - D `docs/plans/2026-04-21-pnl-page-boundary-design.md`
  - D `docs/plans/2026-04-23-cross-asset-investment-research-design.md`
  - D `docs/plans/2026-04-23-cross-asset-investment-research-implementation-plan.md`
  - D `docs/plans/2026-04-24-cursor-balance-analysis-p1-prompt.md`
  - D `docs/plans/2026-04-24-cursor-cross-asset-feature-surfacing-prompt.md`
  - D `docs/plans/2026-04-24-cursor-decision-items-hub-prompt.md`
  - D `docs/plans/2026-04-26-ncd-proxy-frontend-alignment.md`
  - D `docs/plans/2026-05-08-stock-analysis-stage4-evidence-first-pattern-extension.md`
  - D `docs/plans/2026-05-08-stock-analysis-stage4-p1-followups.md`
  - D `docs/plans/2026-05-08-stock-analysis-stage4-perf-observability.md`
  - D `docs/plans/2026-05-11-livermore-real-theme-data.md`
  - D `docs/plans/2026-05-11-livermore-theme-breakout.md`
  - D `docs/plans/2026-05-11-livermore-theme-evidence-miss-review.md`
  - D `docs/plans/2026-05-11-strategy-closed-loop.md`
  - D `docs/plans/2026-05-13-livermore-backtest-maturity-market-state.md`
  - D `docs/plans/2026-05-15-livermore-strategy-gate-tightening.md`
  - D `docs/plans/2026-05-30-backend-classification-compute-api-closure.md`
  - D `docs/plans/2026-05-31-dashboard-bond-news-intelligence-plan.md`
  - D `docs/plans/2026-05-31-stock-analysis-performance-optimization.md`
  - D `docs/plans/2026-06-02-polar-moss-agent-bench-design.md`
  - D `docs/plans/2026-06-06-database-readiness-next-closure-plan.md`
  - D `docs/plans/2026-06-10-choice-shibor-landing-plan.md`
  - **?? `docs/plans/archive/` 整目录（38 项：37 篇对应副本 + README.md；漏掉即丢失历史文档）**
  - **?? `docs/audits/archive/` 整目录（2 篇对应副本；同上）**
- 提交前验证：`python -m pytest tests/test_governance_doc_contract.py`（确认无测试硬编码旧路径；零引用校验已由另一流程通过，此处兜底）。
- 风险备注：提交后若任何 tests/scripts 仍引用旧路径会立即红；已确认零引用，风险低。

## 第 5 组 fix(bond-dashboard) — 后端 YTM Numeric 治理

- 性质：口径修正——business-type `weighted_avg_ytm` 由百分点字符串改为治理 Numeric，缺覆盖时返回 null 而非 0。
- commit message：`fix(bond-dashboard): default business-type weighted YTM to null numeric instead of zero`
- 文件清单：
  - M `backend/app/schemas/bond_dashboard.py`
  - M `contracts/openapi/openapi.default.json`（由本 schema 生成）
  - M `contracts/openapi/openapi.full.json`（由本 schema 生成）
  - M `tests/test_bond_dashboard_numeric_migration.py`
- 提交前验证：`python -m pytest tests/test_bond_dashboard_numeric_migration.py`
- 风险备注：DTO 破坏性变更（删字段），必须先于第 6 组；旧前端消费方已在第 6 组同步。

## 第 6 组 refactor(bond-dashboard) — 页面重构到共享布局原语

- 性质：页面重构——本地 KpiBand/SectionLead 替换为新共享布局原语（KpiStrip/SectionHead/StateSurface），净删码。
- commit message：`refactor(bond-dashboard): rebuild the page on shared layout primitives`
- 文件清单（19 M + 3 D）：
  - D `frontend/src/features/bond-dashboard/bondDashboard.module.css`
  - D `frontend/src/features/bond-dashboard/components/BondDashboardKpiBand.tsx`
  - D `frontend/src/features/bond-dashboard/components/BondDashboardSectionLead.tsx`
  - M `frontend/src/features/bond-dashboard/components/AssetStructurePie.tsx`
  - M `frontend/src/features/bond-dashboard/components/CreditRatingBlocks.tsx`
  - M `frontend/src/features/bond-dashboard/components/IndustryTable.tsx`
  - M `frontend/src/features/bond-dashboard/components/MaturityStructureChart.tsx`
  - M `frontend/src/features/bond-dashboard/components/PortfolioTable.tsx`
  - M `frontend/src/features/bond-dashboard/components/RiskIndicatorsPanel.tsx`
  - M `frontend/src/features/bond-dashboard/components/SpreadTable.tsx`
  - M `frontend/src/features/bond-dashboard/components/YieldDistributionBar.tsx`
  - M `frontend/src/features/bond-dashboard/pages/BondDashboardPage.css`
  - M `frontend/src/features/bond-dashboard/pages/BondDashboardPage.tsx`
  - M `frontend/src/features/bond-dashboard/sections/BondDashboardChartSections.css`
  - M `frontend/src/features/bond-dashboard/sections/BondDashboardTableSections.css`
  - M `frontend/src/features/bond-dashboard/sections/BondStructureSection.tsx`
  - M `frontend/src/features/bond-dashboard/sections/BusinessTypeSection.tsx`
  - M `frontend/src/features/bond-dashboard/sections/EvidenceSection.tsx`
  - M `frontend/src/features/bond-dashboard/sections/MaturityIndustrySection.tsx`
  - M `frontend/src/features/bond-dashboard/sections/PortfolioRiskSection.tsx`
  - M `frontend/src/test/BondDashboardPage.test.tsx`
  - M `frontend/src/test/BusinessTypeSection.test.tsx`
  - **?? `frontend/src/components/layout/` 整目录（共享布局原语；页面已 import，漏掉无法构建）**
  - **?? `frontend/src/features/bond-dashboard/components/BondSectionSurface.tsx`（同上）**
  - **?? `frontend/src/features/bond-dashboard/sectionStatus.ts`（同上）**
- 提交前验证：`cd frontend; npx vitest run src/test/BondDashboardPage.test.tsx src/test/BusinessTypeSection.test.tsx src/components/layout`
- 风险备注：必须在第 5 组之后。`components/layout/` 目前仅 bond-dashboard 消费，其内测试文件一并提交。

## 第 7 组 feat(stock-analysis) — 后端生产数据收口

- 性质：功能开发——current-rule cohort 受控存储（DuckDB v46 迁移）、涨跌停/复权因子数据链、观察清单发布、workbench rv v1→v2。
- commit message：`feat(stock-analysis): land the current-rule cohort storage and vendor factor closure`
- 文件清单（19 M）：
  - M `backend/app/repositories/duckdb_migrations.py`（+252 行全部为 v46 迁移）
  - M `backend/app/services/stock_analysis_workbench_service.py`
  - M `backend/app/tasks/choice_stock_materialize.py`
  - M `backend/app/tasks/choice_stock_observation_manifest.py`
  - M `backend/app/tasks/choice_stock_refresh.py`
  - M `backend/app/tasks/concept_membership_intervalize.py`
  - M `backend/app/tasks/stock_limit_price_ingest.py`
  - M `scripts/choice_stock_daily_refresh.py`
  - M `scripts/mcp/moss_project_mcp.py`（rv/cv 版本号 v1→v2）
  - M `docs/stock_analysis_workbench_api_contract.md`
  - M `tests/test_choice_stock_async_refresh.py`
  - M `tests/test_choice_stock_daily_refresh.py`
  - M `tests/test_choice_stock_materialize.py`
  - M `tests/test_concept_membership_intervalize.py`
  - M `tests/test_project_mcp_servers.py`
  - M `tests/test_repository_support_contracts.py`
  - M `tests/test_stock_analysis_workbench_api.py`
  - M `tests/test_stock_analysis_workbench_mcp_binding.py`
  - M `tests/test_stock_limit_price_ingest.py`
- 必须捆绑的未跟踪文件（漏掉会导致迁移/任务/测试无法运行）：
  - **?? `backend/app/governance/stock_analysis_calendar_approval_decision.py`**
  - **?? `backend/app/governance/stock_analysis_calendar_receipt.py`**
  - **?? `backend/app/governance/stock_analysis_current_rule_certificate.py`**
  - **?? `backend/app/governance/stock_analysis_current_rule_factor_vendor_receipt.py`**
  - **?? `backend/app/governance/stock_analysis_current_rule_version_tuple.py`**
  - **?? `backend/app/governance/stock_analysis_page_gap_factor_vendor_receipt.py`**
  - **?? `backend/app/governance/stock_analysis_source_availability_receipt.py`**
  - **?? `backend/app/repositories/stock_analysis_current_rule_cohort_reader.py`**
  - **?? `backend/app/schema_registry/duckdb/controlled/` 整目录（v46 迁移读取的受控 SQL）**
  - **?? `backend/app/tasks/stock_adjustment_factor_daily_refresh.py`、`backend/app/tasks/stock_limit_price_daily_refresh.py`**
  - **?? `backend/app/tasks/stock_analysis_*.py`（9 个：cohort_bundle_producer / cohort_evidence / cohort_materialize / current_rule_factor_manifest / current_rule_factor_write / page_gap_execution_materialize / page_gap_factor_manifest / page_gap_factor_write / page_gap_manifest）**
  - **?? `scripts/stock_adjustment_factor_daily_refresh.py` 与 `scripts/stock_analysis_*.py`（13 个 CLI）**
  - **?? `tests/test_stock_analysis_*.py`（30 个新测试）、`tests/test_stock_adjustment_factor_daily_refresh.py`、`tests/test_stock_limit_price_daily_refresh.py`**
  - 可选捆绑（同一战役的文档证据）：?? `docs/plans/2026-08-21-stock-analysis-m1a-cohort-persistence-design.md`、?? `docs/plans/2026-08-21-stock-analysis-production-data-closure-prd.md`、?? `docs/audits/2026-08-21-stock-analysis-d6a-preflight.md`、?? `docs/audits/2026-08-21-stock-analysis-production-data-closure-prd-evaluation.md`、?? `docs/audits/2026-08-22-stock-analysis-d6a-d6b-controlled-implementation.md`、?? `docs/audits/2026-08-22-stock-analysis-m1a-proof-contract-implementation.md`、?? `docs/audits/2026-08-23-stock-analysis-d6-final-preflight.md`
- 提交前验证：`python -m pytest tests/test_repository_support_contracts.py tests/test_stock_limit_price_ingest.py tests/test_choice_stock_materialize.py tests/test_choice_stock_async_refresh.py tests/test_stock_analysis_workbench_api.py tests/test_project_mcp_servers.py tests/test_stock_analysis_current_rule_cohort_schema_controlled.py`
- 风险备注：含 DuckDB schema 迁移（受保护边界，本组即根因证据）；是第 8、13 组和第 10 组（间接）的前置。

## 第 8 组 feat(stock-analysis) — 前端 replay closure 与 walk-forward 展示

- 性质：功能开发——候选来源池标签、walk-forward 判定、复盘收口面板、K 线雷达、信号窗口模型。
- commit message：`feat(stock-analysis): surface replay closure and walk-forward verdicts on the page`
- 文件清单（36 M）：
  - M `frontend/src/api/marketDataMockClient.ts`（新增 replay_closure 等 mock，为本组测试服务）
  - M `frontend/src/features/stock-analysis/components/StockAnalysisAccessibleControls.test.tsx`
  - M `frontend/src/features/stock-analysis/components/StockAnalysisCandidateComparison.test.tsx`
  - M `frontend/src/features/stock-analysis/components/StockAnalysisCandidateComparison.tsx`
  - M `frontend/src/features/stock-analysis/components/StockAnalysisCandidateLedgerTable.test.tsx`
  - M `frontend/src/features/stock-analysis/components/StockAnalysisCandidateLedgerTable.tsx`
  - M `frontend/src/features/stock-analysis/components/StockAnalysisClosedLoopRail.tsx`
  - M `frontend/src/features/stock-analysis/components/StockAnalysisDecisionFirstScreen.tsx`
  - M `frontend/src/features/stock-analysis/components/StockAnalysisDeepResearchZone.tsx`
  - M `frontend/src/features/stock-analysis/components/StockAnalysisFirstScreenRail.tsx`
  - M `frontend/src/features/stock-analysis/components/StockAnalysisKlineRadarPanel.tsx`
  - M `frontend/src/features/stock-analysis/components/StockAnalysisMacroCycleCard.tsx`
  - M `frontend/src/features/stock-analysis/components/StockAnalysisObservationClosurePanel.tsx`
  - M `frontend/src/features/stock-analysis/components/StockAnalysisSectorStrengthCard.test.tsx`
  - M `frontend/src/features/stock-analysis/components/StockAnalysisSectorStrengthCard.tsx`
  - M `frontend/src/features/stock-analysis/components/StockAnalysisStrategyLensSection.tsx`
  - M `frontend/src/features/stock-analysis/hooks/useStockSelectionRefresh.test.tsx`
  - M `frontend/src/features/stock-analysis/hooks/useStockSelectionRefresh.ts`
  - M `frontend/src/features/stock-analysis/lib/stockAnalysisBacktestModel.ts`
  - M `frontend/src/features/stock-analysis/lib/stockAnalysisChartModel.ts`
  - M `frontend/src/features/stock-analysis/lib/stockAnalysisFirstScreenModel.ts`
  - M `frontend/src/features/stock-analysis/lib/stockAnalysisKlineRadarModel.test.ts`
  - M `frontend/src/features/stock-analysis/lib/stockAnalysisKlineRadarModel.ts`
  - M `frontend/src/features/stock-analysis/lib/stockAnalysisPageModel.ts`
  - M `frontend/src/features/stock-analysis/lib/stockAnalysisWorkbenchQueueModel.ts`
  - M `frontend/src/features/stock-analysis/pages/StockAnalysisPage.css`
  - M `frontend/src/features/stock-analysis/pages/StockAnalysisPageImpl.tsx`
  - M `frontend/src/test/StockAnalysisBacktestModel.test.ts`
  - M `frontend/src/test/StockAnalysisChartModel.test.ts`
  - M `frontend/src/test/StockAnalysisFirstScreenContractGap.test.ts`
  - M `frontend/src/test/StockAnalysisFirstScreenRail.test.tsx`
  - M `frontend/src/test/StockAnalysisPage.test.tsx`
  - M `frontend/src/test/StockAnalysisPageModel.test.ts`
  - M `frontend/src/test/StockAnalysisPageSizeGuard.test.ts`
  - M `frontend/src/test/StockAnalysisStrategyLensSection.test.tsx`
  - M `frontend/src/test/StockAnalysisWorkbenchQueueModel.test.ts`
  - **?? `frontend/src/features/stock-analysis/lib/stockAnalysisSignalWindowModel.ts`（pageModel 已 import，漏掉无法构建）**
  - **?? `frontend/src/features/stock-analysis/lib/stockAnalysisSignalWindow.test.ts`**
  - **?? `frontend/src/features/stock-analysis/components/StockAnalysisObservationClosurePanel.test.tsx`**
  - **?? `frontend/src/test/StockAnalysisFirstScreenModel.test.ts`**
- 提交前验证：`cd frontend; npx vitest run src/test/StockAnalysis src/features/stock-analysis`
- 风险备注：必须在第 7 组之后（消费 replay_closure 契约）。

## 第 9 组 feat(livermore) — 策略核心与候选历史

- 性质：功能开发 + 口径澄清——matched baseline 时点（PIT）证明行、walk-forward 判定模块、超跌反弹参数显式化、信号汇流与候选历史服务扩展。
- commit message：`feat(livermore): add matched-baseline PIT proofs and explicit strategy params`
- 文件清单（32 M）：
  - M `backend/app/api/routes/market_data_livermore.py`
  - M `backend/app/core_finance/candidate_history_proxy_backtest.py`
  - M `backend/app/core_finance/factor_screen_candidates.py`
  - M `backend/app/core_finance/gate_macro_overlay.py`
  - M `backend/app/core_finance/market_derived.py`
  - M `backend/app/core_finance/matched_baseline.py`
  - M `backend/app/core_finance/mean_reversion_candidates.py`
  - M `backend/app/core_finance/strategy_policy.py`
  - M `backend/app/repositories/livermore_candidate_history_repo.py`
  - M `backend/app/services/livermore_candidate_history_read_support.py`
  - M `backend/app/services/livermore_candidate_history_service.py`
  - M `backend/app/services/livermore_candidate_history_strategy_support.py`
  - M `backend/app/services/livermore_candidate_history_window_stats.py`
  - M `backend/app/services/livermore_gate_supplement_compute_service.py`
  - M `backend/app/services/livermore_sector_rank_series_service.py`
  - M `backend/app/services/livermore_signal_confluence_service.py`
  - M `backend/app/services/market_data_livermore_route_support.py`
  - M `backend/app/services/market_data_livermore_service.py`
  - M `backend/app/tasks/livermore_candidate_history_materialize.py`
  - M `scripts/run_livermore_daily_pretrade_refresh.py`
  - M `backend/tests/core_finance/test_factor_screen_candidates.py`
  - M `backend/tests/core_finance/test_strategy_policy.py`
  - M `tests/test_candidate_history_proxy_backtest.py`
  - M `tests/test_gate_macro_overlay.py`
  - M `tests/test_livermore_daily_pretrade_refresh.py`
  - M `tests/test_livermore_signal_confluence.py`
  - M `tests/test_market_breadth_gate_supplement.py`
  - M `tests/test_market_data_livermore_api.py`
  - M `tests/test_market_data_livermore_candidate_history.py`
  - M `tests/test_market_data_livermore_sector_rank_series.py`
  - M `tests/test_market_derived.py`
  - M `tests/test_matched_baseline.py`
  - **?? `backend/app/core_finance/strategy_walk_forward_verdicts.py`（新正式计算模块，服务层大概率已 import，漏掉无法构建）**
  - **?? `tests/test_strategy_walk_forward_verdicts.py`**
- 提交前验证：`python -m pytest tests/test_matched_baseline.py tests/test_strategy_walk_forward_verdicts.py tests/test_livermore_signal_confluence.py tests/test_market_data_livermore_api.py tests/test_livermore_daily_pretrade_refresh.py backend/tests/core_finance/`
- 风险备注：正式金融计算路径（core_finance）有实质改动，属高影响面；测试必须绿再提交。是第 10 组的前置。

## 第 10 组 feat(macro-toolkit) — 后端刷新链路与 vendor 衍生数据

- 性质：功能开发——刷新 run manifest 版本化、异步写刷新、商品期货刷新状态、vendor 衍生利差、宏观模型链扩展。
- commit message：`feat(macro-toolkit): version refresh runs and add derived vendor spreads`
- 文件清单（34 M）：
  - M `backend/app/api/routes/macro_toolkit.py`
  - M `backend/app/api/routes/macro_vendor.py`
  - M `backend/app/schemas/macro_vendor.py`
  - M `backend/app/core_finance/macro/credit_spread_percentile.py`
  - M `backend/app/core_finance/macro/rate_turning_point.py`
  - M `backend/app/core_finance/macro/toolkit/scripts/backtest_cn.py`
  - M `backend/app/core_finance/macro/yield_curve_shape.py`
  - M `backend/app/services/macro_toolkit_analysis_service.py`
  - M `backend/app/services/macro_toolkit_refresh_receipt_service.py`
  - M `backend/app/services/macro_toolkit_route_support.py`
  - M `backend/app/services/macro_toolkit_service.py`
  - M `backend/app/services/macro_toolkit_service_model_chain.py`
  - M `backend/app/services/macro_vendor_refresh_service.py`
  - M `backend/app/services/macro_vendor_service.py`
  - M `backend/app/services/market_home_warmup_service.py`
  - M `backend/app/tasks/choice_macro.py`
  - M `backend/app/tasks/macro_toolkit_refresh.py`
  - M `backend/app/tasks/macro_toolkit_write_refresh.py`
  - M `scripts/install_macro_toolkit_freshness_timer.ps1`
  - M `scripts/macro_toolkit_freshness_refresh.py`
  - M `tests/test_credit_spread_percentile.py`
  - M `tests/test_macro_model_chain_results.py`
  - M `tests/test_macro_model_performance.py`
  - M `tests/test_macro_partial_capabilities_honesty.py`
  - M `tests/test_macro_query_contract_smoke.py`
  - M `tests/test_macro_report_asset_analysis.py`
  - M `tests/test_macro_toolkit_async_write_refresh.py`
  - M `tests/test_macro_toolkit_freshness_refresh.py`
  - M `tests/test_macro_toolkit_math_fixes.py`
  - M `tests/test_macro_toolkit_refresh.py`
  - M `tests/test_macro_toolkit_scripts.py`
  - M `tests/test_macro_vendor_schema_contract.py`
  - M `tests/test_market_home_warmup.py`
  - M `tests/test_write_route_auth_contract.py`
- 必须捆绑的未跟踪文件：
  - **?? `backend/app/services/macro_toolkit_read_service.py`（market_home_warmup_service 已 import，漏掉后端起不来）**
  - **?? `backend/app/services/macro_toolkit_allocation_snapshot_service.py`**
  - ?? `backend/tests/services/test_macro_vendor_display_name.py`
  - ?? `tests/test_macro_toolkit_allocation_snapshot_read_contract.py`
  - ?? `tests/test_macro_toolkit_choice_dependency_gate.py`
  - ?? `tests/test_macro_toolkit_curve_snapshot_contract.py`
  - ?? `tests/test_macro_toolkit_directional_conclusion_contract.py`
  - ?? `tests/test_macro_toolkit_freshness_failure_contract.py`
  - ?? `tests/test_macro_toolkit_freshness_timer_safety.py`
  - ?? `tests/test_macro_toolkit_monthly_freshness_contract.py`
  - ?? `tests/test_macro_toolkit_portfolio_curve_snapshot_contract.py`
  - ?? `tests/test_macro_toolkit_refresh_failure_health.py`
  - ?? `tests/test_macro_vendor_derived_spreads.py`
  - ?? `tests/test_macro_vendor_refresh_async_contract.py`
- 提交前验证：`python -m pytest tests/test_macro_toolkit_refresh.py tests/test_macro_toolkit_async_write_refresh.py tests/test_macro_vendor_derived_spreads.py tests/test_macro_vendor_refresh_async_contract.py tests/test_market_home_warmup.py tests/test_write_route_auth_contract.py`（`tests/test_macro_toolkit_scripts.py` 很重，时间允许再跑）
- 风险备注：必须在第 7、9 组之后（macro_toolkit_service 代理二者的函数）。本组最大（+6800 行级），若想再拆分需 route 文件 hunk 手术，不推荐。

## 第 11 组 refactor(macro-toolkit) — 前端观察页拆分与操作台重构

- 性质：功能开发 + 页面拆分——`/macro-observation` 独立锚点、操作动作收口、模型链面板、刷新状态结构化错误展示。
- commit message：`refactor(macro-toolkit): split the observation page and rebuild the operations view`
- 文件清单（31 M）：
  - M `frontend/src/api/clientContext.ts`
  - M `frontend/src/api/contracts/marketMacro.ts`
  - M `frontend/src/api/httpResponseError.ts`
  - M `frontend/src/api/macroToolkitClient.ts`
  - M `frontend/src/api/macroToolkitMockClient.ts`
  - M `frontend/src/features/macro-observation/pages/MacroObservationPage.css`
  - M `frontend/src/features/macro-observation/pages/MacroObservationPage.tsx`
  - M `frontend/src/features/macro-toolkit/lib/macroToolkitStrategyDisplaySupport.ts`
  - M `frontend/src/features/macro-toolkit/pages/MacroToolkitOperationsView.tsx`
  - M `frontend/src/features/macro-toolkit/pages/MacroToolkitPage.css`
  - M `frontend/src/features/macro-toolkit/pages/MacroToolkitPage.tsx`
  - M `frontend/src/features/macro-toolkit/pages/useMacroToolkitDeferredContent.ts`
  - M `frontend/src/features/macro-toolkit/pages/useMacroToolkitOperationActions.ts`
  - M `frontend/src/features/macro-toolkit/panels/MacroToolkitCrisisPanels.tsx`
  - M `frontend/src/features/macro-toolkit/panels/MacroToolkitModelChainPanel.tsx`
  - M `frontend/src/features/macro-toolkit/panels/MacroToolkitReportBundlePanel.css`
  - M `frontend/src/features/macro-toolkit/panels/MacroToolkitSignalPanels.tsx`
  - M `frontend/src/features/macro-toolkit/sections/MacroToolkitCapabilityCards.tsx`
  - M `frontend/src/features/macro-toolkit/sections/MacroToolkitDataHealthSections.tsx`
  - M `frontend/src/features/macro-toolkit/sections/MacroToolkitIndicatorSections.tsx`
  - M `frontend/src/features/macro-toolkit/sections/MacroToolkitPrimitives.tsx`
  - M `frontend/src/features/macro-toolkit/sections/MacroToolkitSignalSections.tsx`
  - M `frontend/src/features/macro-toolkit/sections/MacroToolkitStrategySections.tsx`
  - M `frontend/src/test/ApiClient.test.ts`
  - M `frontend/src/test/ApiClientCompositionBoundary.test.ts`
  - M `frontend/src/test/MacroObservationPage.test.tsx`
  - M `frontend/src/test/MacroToolkitModelChainPanel.test.tsx`
  - M `frontend/src/test/MacroToolkitPage.test.tsx`
  - M `frontend/src/test/macroToolkitClient.test.ts`
  - M `frontend/src/test/liveRouteReadinessContracts.ts`（`macro-toolkit-tailwind-cockpit`→`macro-toolkit-cockpit` 锚点改名，锚点定义在本组页面文件里，必须同笔）
  - M `frontend/tests/playwright/a11y-visual-smoke.spec.mjs`（同上锚点改名）
  - **?? `frontend/src/test/MacroToolkitDependencyGate.test.tsx`**
- 提交前验证：`cd frontend; npx vitest run src/test/MacroToolkitPage.test.tsx src/test/MacroToolkitModelChainPanel.test.tsx src/test/MacroObservationPage.test.tsx src/test/MacroToolkitDependencyGate.test.tsx src/test/macroToolkitClient.test.ts src/test/ApiClient.test.ts src/test/liveRouteReadinessContracts`
- 风险备注：必须在第 10 组之后。两个锚点文件放本组而非第 22 组（tailwind），否则中间提交点路由就绪测试红。

## 第 12 组 refactor(market-data) — tape cockpit 替换为宏观序列终端（并行会话收口后）

- 性质：页面大重构——删除 tape cockpit / hero / ticker（−4800 行级），换成宏观序列 deck、紧凑表与序列时序图。
- commit message：`refactor(market-data): replace the tape cockpit with the macro series terminal`
- 文件清单（22 M + 4 D）：
  - D `frontend/src/features/market-data/components/MarketTerminalTicker.tsx`
  - D `frontend/src/features/market-data/pages/MarketDataHeroSection.tsx`
  - D `frontend/src/features/market-data/pages/marketDataTapeCockpitModel.test.ts`
  - D `frontend/src/features/market-data/pages/marketDataTapeCockpitModel.ts`
  - M `frontend/src/features/market-data/components/MarketDataLinkageCharts.tsx`
  - M `frontend/src/features/market-data/components/MarketDataMacroSeriesDeck.test.tsx`
  - M `frontend/src/features/market-data/components/MarketDataMacroSeriesDeck.tsx`
  - M `frontend/src/features/market-data/components/MarketDataMacroThemeCard.tsx`
  - M `frontend/src/features/market-data/components/MarketDataSeriesCompactTable.test.tsx`
  - M `frontend/src/features/market-data/components/MarketDataSeriesCompactTable.tsx`
  - M `frontend/src/features/market-data/hooks/useMarketDataPageData.ts`
  - M `frontend/src/features/market-data/lib/charts/linkageEnvironmentBarChartOption.ts`
  - M `frontend/src/features/market-data/lib/charts/marketDataLinkageCharts.test.ts`
  - M `frontend/src/features/market-data/lib/charts/marketDataSeriesTimeChartOption.test.ts`
  - M `frontend/src/features/market-data/lib/charts/marketDataSeriesTimeChartOption.ts`
  - M `frontend/src/features/market-data/lib/marketDataFormat.test.ts`
  - M `frontend/src/features/market-data/lib/marketDataFormat.ts`
  - M `frontend/src/features/market-data/lib/marketDataMacroThemeGroups.test.ts`
  - M `frontend/src/features/market-data/lib/marketDataMacroThemeGroups.ts`
  - M `frontend/src/features/market-data/lib/marketDataTerminalModel.ts`
  - M `frontend/src/features/market-data/pages/MarketDataMacroDepthTabs.tsx`
  - M `frontend/src/features/market-data/pages/MarketDataPage.css`
  - M `frontend/src/features/market-data/pages/MarketDataPage.tsx`
  - M `frontend/src/features/market-data/pages/marketDataPageModel.ts`
  - M `frontend/src/test/MarketDataPage.test.tsx`
  - M `frontend/src/test/MarketDataPageCssBudget.test.ts`
  - **?? `frontend/src/features/market-data/components/MarketDataLinkageCharts.test.tsx`**
- 提交前验证：`cd frontend; npx vitest run src/test/MarketDataPage src/features/market-data`
- 风险备注：**该域并行会话仍在活动，收口前禁止提交**（判断方法见"执行前提"第 1 条）。提交时按当时 `git status` 重新核对本组清单，新增文件就近归入。必须在第 10 组之后（依赖 derived spreads 契约）。

## 第 13 组 feat(scheduling) — 日刷新链与数据健康

- 性质：功能开发——日刷新链插入复权因子/涨跌停两步（上游被跳过时 fail-closed）、数据健康新增复权因子新鲜度与任务"从未首跑"识别。
- commit message：`feat(scheduling): chain factor and limit-price refreshes with fail-closed dependencies`
- 文件清单（9 M）：
  - M `scripts/scheduling/README.md`
  - M `scripts/scheduling/daily_data_refresh.ps1`
  - M `scripts/scheduling/register_scheduled_tasks.ps1`
  - M `backend/app/services/data_health_service.py`
  - M `backend/app/services/health_service.py`
  - M `backend/app/services/supply_freshness_service.py`
  - M `tests/test_data_health.py`
  - M `tests/test_health_endpoints.py`
  - M `tests/test_supply_freshness_check.py`
  - **?? `tests/test_daily_data_refresh_scheduler.py`**
  - **?? `tests/test_register_scheduled_tasks.py`**
- 提交前验证：`python -m pytest tests/test_data_health.py tests/test_health_endpoints.py tests/test_supply_freshness_check.py tests/test_daily_data_refresh_scheduler.py tests/test_register_scheduled_tasks.py`
- 风险备注：必须在第 7 组之后（调度链引用其新任务模块）。

## 第 14 组 feat(dashboard-home) — 宏观发布日历与周期供数

- 性质：功能开发——发布日历补下半年与海外事件，home 宏观刷新纳入社融/M2 周期序列，首页简报模型适配。
- commit message：`feat(dashboard-home): extend the macro release calendar and cycle credit inputs`
- 文件清单（9 M）：
  - M `backend/app/tasks/home_macro_release_refresh.py`
  - M `config/cycle_rotation_macro_official_availability.json`
  - M `config/cycle_rotation_macro_official_releases.json`
  - M `config/dashboard_macro_release_calendar_2026.json`
  - M `frontend/src/features/workbench/dashboard-home/adapters/buildHomeMacroBriefingModel.test.ts`
  - M `frontend/src/features/workbench/dashboard-home/adapters/buildHomeMacroBriefingModel.ts`
  - M `tests/test_cycle_macro_input_contract.py`
  - M `tests/test_home_macro_release_refresh_nbs.py`
  - M `tests/test_home_macro_release_refresh_task.py`
- 提交前验证：`python -m pytest tests/test_home_macro_release_refresh_task.py tests/test_home_macro_release_refresh_nbs.py tests/test_cycle_macro_input_contract.py`，另 `cd frontend; npx vitest run src/features/workbench/dashboard-home/adapters`
- 风险备注：两个 cycle_rotation 配置若被第 9 组的 `test_gate_macro_overlay` 引用，需挪到第 9 组（见"归属模糊"节）。

## 第 15 组 feat(liability-analytics) — 月度 summary/detail 拆分与环比同比

- 性质：功能开发——月度接口拆 summary/detail，新增 MTR-LIAB-009/010（月均负债环比/同比），ADB LOCF 语义修正。
- commit message：`feat(liability-analytics): split monthly summary/detail and add MoM/YoY average changes`
- 文件清单（17 M）：
  - M `backend/app/api/routes/liability_analytics.py`
  - M `backend/app/core_finance/liability_analytics_compat.py`
  - M `backend/app/repositories/liability_analytics_repo.py`
  - M `backend/app/schemas/liability_analytics.py`
  - M `backend/app/services/adb_analysis_service.py`
  - M `frontend/src/api/liabilityAdbClient.ts`
  - M `frontend/src/api/liabilityAdbContracts.ts`
  - M `frontend/src/features/liability-analytics/components/LiabilityMonthlySnapshotCards.tsx`
  - M `frontend/src/features/liability-analytics/components/LiabilityNimStressMonthlyPanel.tsx`
  - M `frontend/src/features/liability-analytics/components/LiabilityStructureGrids.tsx`
  - M `frontend/src/features/liability-analytics/pages/LiabilityAnalyticsPage.css`
  - M `frontend/src/features/liability-analytics/pages/LiabilityAnalyticsPage.tsx`
  - M `frontend/src/test/LiabilityAnalyticsPage.test.tsx`
  - M `tests/test_adb_analysis_api.py`
  - M `tests/test_liability_analytics_compat_contract.py`
  - M `tests/test_liability_analytics_numeric_migration.py`
  - M `docs/pnl/average-balance-page-contract.md`（ADB LOCF 语义同步）
  - **?? `frontend/src/features/liability-analytics/components/LiabilityYieldTrendPanel.tsx`（页面已 import，漏掉无法构建）**
- 提交前验证：`python -m pytest tests/test_liability_analytics_compat_contract.py tests/test_adb_analysis_api.py tests/test_liability_analytics_numeric_migration.py`，另 `cd frontend; npx vitest run src/test/LiabilityAnalyticsPage.test.tsx`
- 风险备注：core_finance 兼容层跨年取数是口径改动，测试必须绿。

## 第 16 组 fix(ledger-pnl) — 展示整改与业务阅读 IA

- 性质：口径展示整改——环比小字、金额 -0.00 归一、并集口径注记、workbook 表格与章节导航。
- commit message：`fix(ledger-pnl): remediate display semantics and the business-reader IA`
- 文件清单（29 M）：
  - M `backend/app/core_finance/ledger_pnl_analysis.py`
  - M `backend/app/schemas/ledger_pnl_analysis.py`
  - M `backend/app/schemas/ledger_pnl_read.py`
  - M `backend/app/services/ledger_pnl_service.py`
  - M `frontend/src/api/contracts/balanceLedger.ts`
  - M `frontend/src/mocks/ledgerPnlMocks.ts`
  - M `frontend/src/features/ledger-pnl/components/LedgerPnlCandidateFinancialIndicatorsPanel.tsx`
  - M `frontend/src/features/ledger-pnl/components/LedgerPnlCandidatePeriodComparison.tsx`
  - M `frontend/src/features/ledger-pnl/components/LedgerPnlSectionNav.tsx`
  - M `frontend/src/features/ledger-pnl/components/LedgerPnlWorkbookTables.css`
  - M `frontend/src/features/ledger-pnl/components/LedgerPnlWorkbookTables.tsx`
  - M `frontend/src/features/ledger-pnl/models/candidatePeriodComparisonModel.ts`
  - M `frontend/src/features/ledger-pnl/pages/LedgerPnlPage.css`
  - M `frontend/src/features/ledger-pnl/pages/LedgerPnlPage.tsx`
  - M `frontend/src/test/LedgerPnlCandidateFinancialIndicatorsPanel.test.tsx`
  - M `frontend/src/test/LedgerPnlCandidatePeriodComparison.test.tsx`
  - M `frontend/src/test/LedgerPnlCandidatePeriodComparisonModel.test.ts`
  - M `frontend/src/test/LedgerPnlCurrencyBasis.test.tsx`
  - M `frontend/src/test/LedgerPnlDateSemanticsContract.test.tsx`
  - M `frontend/src/test/LedgerPnlNullMatrixContract.test.tsx`
  - M `frontend/src/test/LedgerPnlPage.test.tsx`
  - M `frontend/src/test/LedgerPnlPrecisionContract.test.tsx`
  - M `frontend/src/test/LedgerPnlRoutesSmoke.test.tsx`
  - M `frontend/src/test/LedgerPnlSectionNav.test.tsx`
  - M `frontend/src/test/LedgerPnlUnitContract.test.tsx`
  - M `frontend/src/test/LedgerPnlWorkbookTables.test.tsx`
  - M `tests/test_ledger_pnl_analysis.py`
  - M `tests/test_ledger_pnl_routes.py`
  - M `tests/test_ledger_pnl_service.py`
  - 可选捆绑：?? `docs/plans/2026-08-26-ledger-pnl-business-reader-ia-prd.md`、?? `docs/plans/2026-08-26-ledger-pnl-display-remediation-prd.md`、?? `docs/audits/2026-08-25-ledger-pnl-202607-rule-calculation-review.md`
- 提交前验证：`python -m pytest tests/test_ledger_pnl_service.py tests/test_ledger_pnl_analysis.py tests/test_ledger_pnl_routes.py`，另 `cd frontend; npx vitest run src/test/LedgerPnl`
- 风险备注：LedgerPnl 前端测试量大（12 个文件），跑全量 pattern。

## 第 17 组 fix(core-finance) — 517 累计已实现口径 + rv v4

- 性质：正式口径修正——`fi_cumulative_realized_517` 源契约（反号、÷1.06 去 VAT、H/A 派生 realized_formal / T 派生 realized_incremental），materialize 规则版本升 v4。
- commit message：`fix(core-finance): govern fi_cumulative_realized_517 and bump the materialize rv to v4`
- 文件清单（14 M）：
  - M `backend/app/core_finance/pnl.py`
  - M `backend/app/core_finance/pnl_constants.py`
  - M `backend/app/services/pnl_bridge_service.py`
  - M `backend/app/services/pnl_task_dispatch.py`
  - M `docs/golden_sample_catalog.md`（rv v3→v4 登记）
  - M `docs/pnl/pnl-by-business-2026h1-vat-backfill-runbook.md`
  - M `tests/golden_samples/GS-BRIDGE-WARN-B/assertions.md`
  - M `tests/golden_samples/GS-PNL-OVERVIEW-A/assertions.md`
  - M `tests/test_pnl_api_contract.py`
  - M `tests/test_pnl_by_business_insights_contract.py`
  - M `tests/test_pnl_by_business_insights_governance_record.py`
  - M `tests/test_pnl_by_business_precompute_ftp_parity.py`
  - M `tests/test_pnl_formal_semantics_contract.py`
  - M `tests/test_pnl_materialize_flow.py`
- 提交前验证：`python -m pytest tests/test_pnl_formal_semantics_contract.py tests/test_pnl_materialize_flow.py tests/test_pnl_api_contract.py tests/test_pnl_by_business_precompute_ftp_parity.py tests/test_pnl_by_business_insights_contract.py`
- 风险备注：**正式金融计算路径**；rv 升 v4 意味着 PnL 缓存/物化需按 runbook 重建，提交后安排重物化。`docs/calc_rules.md` 与 `docs/metric_dictionary.md` 的 517 hunk 默认走第 29 组（或按进阶方案 add -p 跟本组）。

## 第 18 组 feat(pnl) — 正式—系统口径桥（diagnostic-only）

- 性质：新只读诊断端点 `GET /api/pnl/basis-bridge`，跨口径对账，不新增 MTR-*。
- commit message：`feat(pnl): add the diagnostic formal-to-system basis bridge`
- 文件清单（1 M + 5 必捆）：
  - M `backend/app/api/routes/pnl.py`
  - **?? `backend/app/core_finance/pnl_basis_bridge.py`（路由动态 import，漏掉端点 503/ImportError）**
  - **?? `backend/app/schemas/pnl_basis_bridge.py`（同上）**
  - **?? `backend/app/services/pnl_basis_bridge_service.py`（路由直接调用，漏掉无法构建）**
  - **?? `tests/test_pnl_basis_bridge_contract.py`**
  - **?? `docs/pnl/pnl-basis-bridge-contract.md`（calc_rules §16 指向它，漏掉文档断链）**
- 提交前验证：`python -m pytest tests/test_pnl_basis_bridge_contract.py`
- 风险备注：`docs/calc_rules.md` 的 §16 hunk 默认走第 29 组（或 add -p 跟本组）。

## 第 19 组 fix(product-category-pnl) — 来源服务与页面模型

- 性质：来源服务与页面模型语义加固（本组抽查深度有限，提交前自查一眼 diff 确认修饰语）。
- commit message：`fix(product-category-pnl): harden the source service and page model semantics`
- 文件清单（7 M）：
  - M `backend/app/core_finance/product_category_pnl.py`
  - M `backend/app/services/product_category_source_service.py`
  - M `frontend/src/features/product-category-pnl/pages/ProductCategoryAttributionPanels.tsx`
  - M `frontend/src/features/product-category-pnl/pages/productCategoryPnlPageModel.test.ts`
  - M `frontend/src/features/product-category-pnl/pages/productCategoryPnlPageModel.ts`
  - M `frontend/src/test/ProductCategoryPnlPage.test.tsx`
  - M `tests/test_product_category_source_service.py`
- 提交前验证：`python -m pytest tests/test_product_category_source_service.py`，另 `cd frontend; npx vitest run src/test/ProductCategoryPnlPage.test.tsx src/features/product-category-pnl`
- 风险备注：`frontend/src/lib/echarts.tsx` 的 MarkArea 注册若被本组测试需要且本组先于第 25 组提交，则把它挪到本组（见"归属模糊"节）。

## 第 20 组 feat(agent) — 后端 hermes 本地恢复与工具面

- 性质：功能开发——hermes 失败经本地 resolver 恢复、toolset 白名单规范化、action token、dexter 服务与 SQL 披露护栏。
- commit message：`feat(agent): recover hermes failures through the local resolver`
- 文件清单（28 M）：
  - M `backend/app/agent/runtime/action_token.py`
  - M `backend/app/agent/runtime/local_request_resolution.py`
  - M `backend/app/agent/runtime/toolset_policy.py`
  - M `backend/app/agent/schemas/agent_request.py`
  - M `backend/app/agent/schemas/agent_run.py`
  - M `backend/app/agent/tools/analysis_view_tool.py`
  - M `backend/app/services/agent_run_service.py`
  - M `backend/app/services/dexter_agent_service.py`
  - M `backend/app/services/hermes_agent_service.py`
  - M `scripts/dev-agent-api.cmd`
  - M `scripts/dev-agent-api.ps1`
  - M `scripts/hermes_bridge_server.py`
  - M `scripts/hermes_stream_runner.py`
  - M `docs/AGENT_MVP_RUNBOOK.md`
  - M `docs/agent_financial_workflows.md`
  - M `tests/test_agent_action_token.py`
  - M `tests/test_agent_api.py`
  - M `tests/test_agent_api_contract.py`
  - M `tests/test_agent_financial_workflow_catalog.py`
  - M `tests/test_agent_intent_routing.py`
  - M `tests/test_agent_research_workflow_catalog.py`
  - M `tests/test_agent_run_service_lifecycle.py`
  - M `tests/test_agent_runs_api.py`
  - M `tests/test_agent_sql_disclosure_drift.py`
  - M `tests/test_agent_toolset_policy.py`
  - M `tests/test_analysis_view_tool.py`
  - M `tests/test_dexter_agent_service.py`
  - M `tests/test_hermes_agent_service.py`
  - **?? `backend/app/governance/agent_prompt.py`（新治理模块；提交前先 `rg "agent_prompt" backend tests` 确认引用面，若被 hermes/dexter import 则漏掉无法启动）**
  - ?? `tests/test_agent_eval_scoring_protocol_v2.py`
  - ?? `tests/test_agent_financial_workflow_date_contract.py`
- 提交前验证：`python -m pytest tests/test_hermes_agent_service.py tests/test_dexter_agent_service.py tests/test_agent_intent_routing.py tests/test_agent_api.py tests/test_agent_toolset_policy.py tests/test_agent_sql_disclosure_drift.py`
- 风险备注：`tests/test_agent_runs_api.py` 行尾 CRLF→LF 转换属预期。

## 第 21 组 feat(agent) — 前端工作流卡片与页面上下文接力

- 性质：功能开发——工作流标题/描述卡、路由态 page_context 接力、dashboard-home 与 pnl-attribution 的 agent 抽屉。
- commit message：`feat(agent): add workflow cards and page-context handoff from host pages`
- 文件清单（14 M）：
  - M `frontend/src/features/agent/AgentWorkbenchPage.css`
  - M `frontend/src/features/agent/AgentWorkbenchPage.tsx`
  - M `frontend/src/features/agent/components/AgentAnswerPanel.tsx`
  - M `frontend/src/features/agent/components/AgentGenericCardsGrid.css`
  - M `frontend/src/features/agent/components/AgentGenericCardsGrid.tsx`
  - M `frontend/src/router/AgentWorkbenchRoute.tsx`
  - M `frontend/src/features/workbench/dashboard-home/DashboardHomeAgentDrawer.tsx`
  - M `frontend/src/features/pnl-attribution/components/PnlAttributionView.css`
  - M `frontend/src/features/pnl-attribution/components/PnlAttributionView.tsx`
  - M `frontend/src/test/AgentAnswerPanel.test.tsx`
  - M `frontend/src/test/AgentEmbeddedReleaseGate.test.tsx`
  - M `frontend/src/test/AgentGenericCardsGrid.test.tsx`
  - M `frontend/src/test/AgentWorkbenchPage.test.tsx`
  - M `frontend/src/test/PnlAttributionPage.test.tsx`
  - **?? `frontend/src/features/pnl-attribution/components/PnlAttributionAgentDrawer.tsx`（PnlAttributionView 已 import，漏掉无法构建）**
  - **?? `frontend/src/test/AgentWorkbenchRoute.test.tsx`**
  - **?? `frontend/src/test/DashboardAgentHandoff.test.tsx`**
- 提交前验证：`cd frontend; npx vitest run src/test/AgentWorkbenchPage.test.tsx src/test/AgentWorkbenchRoute.test.tsx src/test/AgentGenericCardsGrid.test.tsx src/test/AgentAnswerPanel.test.tsx src/test/AgentEmbeddedReleaseGate.test.tsx src/test/DashboardAgentHandoff.test.tsx src/test/PnlAttributionPage.test.tsx`
- 风险备注：必须在第 20 组之后。`AgentWorkbenchPage.tsx` 行尾 CRLF→LF 转换属预期。

## 第 22 组 chore(frontend) — tailwind/heroui 工具链移除

- 性质：机械移除——删除未再使用的 tailwind + heroui 依赖与样式入口，注释措辞同步清理。
- commit message：`chore(frontend): remove the unused tailwind and heroui toolchain`
- 文件清单（6 M + 2 D）：
  - M `frontend/package.json`（仅删 tailwindcss、@tailwindcss/vite、tailwind-merge、tailwind-variants、@heroui/styles 五项，无新增）
  - M `frontend/package-lock.json`（27/757 全为上述依赖树移除，跟本组）
  - M `frontend/vite.config.ts`
  - M `frontend/src/styles/global.css`
  - D `frontend/src/styles/tailwind.css`
  - D `frontend/src/test/TailwindIntegration.test.ts`
  - M `frontend/src/features/balance-analysis/pages/BalanceAnalysisPage.css`（仅注释措辞去 tailwind 字样）
  - M `frontend/src/features/balance-analysis/pages/balanceAnalysisPageModel.ts`（同上）
- 提交前验证：`cd frontend; npm install; npx vite build`（或至少 `npx vitest run src/test/theme.test.ts` + `rg -i "tailwind|heroui" src/ --glob "!**/*.md"` 确认无残余引用）
- 风险备注：提交后其他工作副本需 `npm install` 同步。

## 第 23 组 fix(theme) — 深色映射收敛与 Nocturne 边界作用域

- 性质：主题缺陷修复——`--moss-color-warning-200` 深色映射收敛到 tokens.css 共享层（四个页面删除页根重声明），`themed-route-boundary` 获得自己的 Nocturne scope 列。
- commit message：`fix(theme): centralize the dark warning mapping and boundary nocturne scopes`
- 文件清单（6 M）：
  - M `frontend/src/styles/tokens.css`
  - M `frontend/src/test/theme.test.ts`
  - M `frontend/src/features/balance-movement-analysis/pages/BalanceMovementAnalysisPage.css`
  - M `frontend/src/features/cashflow-projection/pages/CashflowProjectionPage.module.css`
  - M `frontend/src/features/risk-tensor/RiskTensorPage.css`
  - M `frontend/src/features/team-performance/TeamPerformancePage.css`
- 提交前验证：`cd frontend; npx vitest run src/test/theme.test.ts`
- 风险备注：与第 22 组无依赖，但 theme.test.ts 若断言 tailwind 文件不存在，先提第 22 组更顺。

## 第 24 组 feat(frontend) — 投稿截图模式

- 性质：小功能——`publication_capture=1` 时解除 sticky/fixed 展开全页，用于论文配图截屏。
- commit message：`feat(frontend): add the publication capture mode for full-page screenshots`
- 文件清单（2 M）：
  - M `frontend/src/layouts/WorkbenchShell.tsx`
  - M `frontend/src/styles/workbenchShell.css`
  - **?? `frontend/src/router/PublicationShowcaseRoute.test.ts`**
- 提交前验证：`cd frontend; npx vitest run src/router/PublicationShowcaseRoute.test.ts src/test/theme.test.ts`
- 风险备注：无业务影响。

## 第 25 组 fix(market-overview) — 首页图表日轴对齐（并行会话收口后）

- 性质：展示修复 + 工作台扩展——共享日轴收敛到各序列共同起点（消除停更序列造成的左侧空窗）、密度首屏与后端数据工作台。
- commit message：`fix(market-overview): align shared chart date axes to the common series start`
- 文件清单（16 M）：
  - M `frontend/src/features/workbench/module-home/MarketBackendDataWorkbench.test.tsx`
  - M `frontend/src/features/workbench/module-home/MarketBackendDataWorkbench.tsx`
  - M `frontend/src/features/workbench/module-home/MarketFinancialChartsWorkbench.test.tsx`
  - M `frontend/src/features/workbench/module-home/MarketFinancialChartsWorkbench.tsx`
  - M `frontend/src/features/workbench/module-home/MarketHomePage.tsx`
  - M `frontend/src/features/workbench/module-home/MarketOverviewDenseFirstScreen.tsx`
  - M `frontend/src/features/workbench/module-home/marketFinancialChartsModel.test.ts`
  - M `frontend/src/features/workbench/module-home/marketFinancialChartsModel.ts`
  - M `frontend/src/features/workbench/module-home/marketHome.module.css`
  - M `frontend/src/features/workbench/module-home/marketOverviewDenseFirstScreen.module.css`
  - M `frontend/src/features/workbench/module-home/marketOverviewDenseLiquidityModel.test.ts`
  - M `frontend/src/features/workbench/module-home/marketOverviewDenseLiquidityModel.ts`
  - M `frontend/src/features/workbench/module-home/marketOverviewDenseModel.test.ts`
  - M `frontend/src/features/workbench/module-home/marketOverviewDenseModel.ts`
  - M `frontend/src/test/ModuleWorkbenchHomePage.test.tsx`
  - M `frontend/src/lib/echarts.tsx`（MarkArea 组件注册，本组图表消费；归属备选见"归属模糊"节）
- 提交前验证：`cd frontend; npx vitest run src/features/workbench/module-home src/test/ModuleWorkbenchHomePage.test.tsx`
- 风险备注：**该域并行会话仍在活动，收口前禁止提交**；提交时按当时 `git status` 重新核对清单。

## 第 26 组 fix(news) — choice 新闻日期口径

- 性质：口径修复——`received_to` 过滤按日截断比较，消除"当天 00:00 后的行次日才可见"的边界缺陷。
- commit message：`fix(news): compare received_to on the date grain instead of midnight`
- 文件清单（2 M）：
  - M `backend/app/repositories/choice_news_repo.py`
  - M `tests/test_choice_news_query.py`
- 提交前验证：`python -m pytest tests/test_choice_news_query.py`
- 风险备注：无依赖，任意时点可提。

## 第 27 组 docs(design) — DESIGN.md 决策日志外迁

- 性质：文档瘦身——历史决策日志移入归档文件。
- commit message：`docs(design): move the decisions log into the archive file`
- 文件清单（1 M）：
  - M `DESIGN.md`
  - **?? `docs/design-decisions-archive.md`（漏掉即历史决策凭空消失）**
- 提交前验证：无需测试（纯文档）；`rg "design-decisions-archive" docs DESIGN.md` 确认链接一致。
- 风险备注：`docs/design-drafts/`（未跟踪目录）归属未确认，见"归属模糊"节。

## 第 28 组 chore(repo) — 散件

- 性质：独立小修——就绪脚本导航源修复（mocks/navigation.ts 已删，改读 app/navigation.ts）、死样式清理、数据就绪报告小改。
- commit message：`chore(repo): fix the readiness navigation source and drop dead cockpit styles`
- 文件清单（4 M）：
  - M `scripts/codex_page_readiness.py`
  - M `frontend/src/styles/dashboardCockpit.css`
  - M `scripts/data_readiness_report.py`
  - M `tests/test_data_readiness_report.py`
- 提交前验证：`python -m pytest tests/test_data_readiness_report.py`
- 风险备注：无依赖。

## 第 29 组 docs(contracts) — 契约文档统一同步（回退方案）

- 性质：跨域契约文档与治理测试同步，含 liability 月度、PnL 517、macro-observation 锚点、market-data derived spreads 四个域的 hunk。
- commit message：`docs(contracts): sync page contracts and the metric dictionary`
- 文件清单（4 M）：
  - M `docs/page_contracts.md`
  - M `docs/metric_dictionary.md`
  - M `docs/calc_rules.md`
  - M `tests/test_governance_doc_contract.py`
- 提交前验证：`python -m pytest tests/test_governance_doc_contract.py`
- 两种执行方案：
  - **默认（简单）**：所有域提交完成后最后一笔统一提交。代价：第 11、12、15、17、18 组落库到本组落库之间，`test_governance_doc_contract.py` 在中间提交点可能红；只影响逐提交回放，不影响最终态。
  - **进阶（干净）**：`git add -p` 按 hunk 拆分——calc_rules 517 hunk 跟第 17 组、§16 basis-bridge hunk 跟第 18 组；metric_dictionary 的 MTR-LIAB-009/010 跟第 15 组、MTR-PNL-003 跟第 17 组、macro-observation/market-data 行跟第 11/12 组；page_contracts 的 liability/ADB hunk 跟第 15 组、macro-observation hunk 跟第 11 组、market-data hunk 跟第 12 组；test_governance_doc_contract 的 macro-observation 断言跟第 11 组、derived_spreads 断言跟第 12 组。拆完本组消失。

## 第 30 组 基线后漂移 — 后端基础层并行会话在途（收口后再归组提交）

- 性质：本组 52 个文件在手册基线（12:31）之后由在途并行会话陆续落下（12:44 起六轮核对各新增 25/8/11/4/3/1 个，且已扩散到 bond-dashboard、liability、livermore、agent 契约等前 29 组的域），性质未经本手册抽查，**必须等会话收口后按下列建议子簇核对再提交**，不要混入前 29 组。会话未收口前本组清单仍会继续增长，提交时以当时 `git status` 为准。
- 文件清单与建议子簇（均为 M）：
  - 固收计算引擎子簇（建议 `fix(core-finance): ...`，正式计算路径，提交前必跑对应测试）：
    - M `backend/app/core_finance/bond_analytics/common.py`
    - M `backend/app/core_finance/bond_analytics/engine.py`
    - M `backend/app/core_finance/bond_duration.py`
    - M `tests/test_bond_analytics_engine.py`
    - M `tests/test_bond_duration.py`
    - M `tests/test_krd_golden.py`
  - 口径与宏观数值安全子簇（建议随上簇或独立）：
    - M `backend/app/core_finance/calibers/rules/accounting_basis.py`
    - M `backend/app/core_finance/macro/helpers.py`
    - M `tests/test_macro_helpers_decimal_safety.py`
  - 存储/引导与设置子簇（**受保护边界**，建议 `chore(bootstrap)` 单独一笔并说明根因）：
    - M `backend/app/duckdb_schema_bootstrap.py`
    - M `backend/app/storage_bootstrap.py`
    - M `backend/app/tasks/worker_bootstrap.py`
    - M `backend/app/governance/settings.py`
    - M `tests/test_worker_bootstrap.py`
    - M `tests/test_repository_task_write_guard.py`
    - M `tests/test_governance_settings_cache.py`
    - M `tests/test_settings_contract.py`
  - 研究日历子簇（建议 `feat(research-calendar): ...`）：
    - M `backend/app/services/research_calendar_upstream_fetch_service.py`
    - M `backend/app/tasks/research_calendar_upstream_fetch.py`
    - M `tests/test_research_calendar_upstream_fetch_service.py`
    - M `tests/test_research_calendar_upstream_fetch_task.py`
  - 外部数据与新闻采集子簇（复核期间新增）：
    - M `tests/test_external_data_api.py`
    - M `tests/test_external_data_watermark_freshness.py`
    - M `tests/test_tushare_news_ingest.py`
  - 共享层散件（复核期间新增；`transport.ts` 属前端共享 API 层，改动需单独留意）：
    - M `backend/app/api/routes/cube_query.py`
    - M `frontend/src/api/transport.ts`
  - 仓储与定时器散件（小改，可并入本组任一子簇或第 13 组调度）：
    - M `backend/app/repositories/balance_analysis_repo.py`（+1 行）
    - M `backend/app/repositories/fact_load_gates.py`（+4 行）
    - M `scripts/install_analytics_coverage_timer.ps1`
    - M `scripts/install_balance_movement_freshness_timer.ps1`
  - 跨组回填（建议直接并入既有组）：
    - M `tests/test_livermore_gate_supplement_async_refresh.py` → 并入第 9 组（livermore）
    - M `tests/test_pnl_attribution_workbench_contract.py` → 并入第 21 组（agent 前端接力）或第 20 组
    - M `tests/test_hermes_team_dispatch_server.py` → 并入第 20 组（agent 后端）
  - 跨域漂移追加（12:47–12:50 间新落，漂移已扩散到前 29 组的域；建议并入括号内既有组，提交前重跑该组验证命令）：
    - M `backend/app/core_finance/balance_analysis_workbook.py`（→ 第 16 组或独立 balance 口径笔）
    - M `backend/app/core_finance/qdb_gl_monthly_analysis.py`（→ 第 16 组 ledger-pnl）
    - M `frontend/src/api/pnlClient.ts`（→ 第 16 组或第 18 组，视 diff 内容）
    - M `frontend/src/features/bond-dashboard/utils/format.ts`（→ 第 6 组 bond-dashboard 前端）
    - M `frontend/src/features/bond-dashboard/utils/format.test.ts`（→ 第 6 组）
    - M `frontend/src/utils/format.ts`（前端共享工具层，确认消费方后就近归组）
    - M `tests/liability_v1_disposition.py`（→ 第 15 组 liability）
    - M `tests/test_backfill_crisis_score_inputs.py`（→ 第 10 组 macro 后端）
    - M `tests/test_livermore_gate_history.py`（→ 第 9 组 livermore）
    - M `tests/test_macro_observation_capabilities.py`（→ 第 10 或 11 组，视 diff 内容）
    - M `tests/test_market_data_livermore_official_evidence.py`（→ 第 9 组 livermore）
    - M `frontend/src/api/contracts/agent.ts`（→ 第 21 组 agent 前端契约）
    - M `frontend/src/api/agentClient.ts`（→ 第 21 组）
    - M `frontend/src/test/AgentClient.test.ts`（→ 第 21 组）
    - M `frontend/src/test/AgentContractSync.test.ts`（→ 第 21 组）
    - M `frontend/src/api/numeric.ts`（前端共享数值层，确认消费方后就近归组）
    - M `frontend/src/test/transport.test.ts`（随 `frontend/src/api/transport.ts` 同笔）
    - M `tests/test_qdb_gl_monthly_analysis_core.py`（→ 第 16 组 ledger-pnl，随 `qdb_gl_monthly_analysis.py`）
    - M `frontend/src/api/balanceAnalysisClient.ts`（→ 第 15 或 16 组，视 diff 内容）
- 提交前验证（按子簇）：`python -m pytest tests/test_bond_analytics_engine.py tests/test_bond_duration.py tests/test_krd_golden.py`；`python -m pytest tests/test_worker_bootstrap.py tests/test_settings_contract.py tests/test_governance_settings_cache.py tests/test_repository_task_write_guard.py`；`python -m pytest tests/test_research_calendar_upstream_fetch_service.py tests/test_research_calendar_upstream_fetch_task.py`
- 风险备注：涉及固收正式计算与存储引导两个高敏区；该会话若仍在写码，本组清单会继续漂移，提交前以当时 `git status` 为准重新核对。

## 暂缓提交

- M `docs/agent_codebase_map.md`（+1 行）：新增"Management report templates"行，引用的 `docs/report-templates/` 与 `.codex/skills/moss-management-book/` 均为未跟踪内容，**建议与 report-templates 目录一起另行提交**（不在本手册范围）。若急于清空工作树，可与 ?? `docs/report-templates/` 目录同笔提交为 `docs(templates): register the management report templates`。

---

## 归属模糊文件（需用户判断）

| 文件 | 默认归属 | 备选 | 判断依据 |
| --- | --- | --- | --- |
| `config/cycle_rotation_macro_official_availability.json`、`config/cycle_rotation_macro_official_releases.json` | 第 14 组 | 第 9 组 | 若 `python -m pytest tests/test_gate_macro_overlay.py` 在第 9 组提交点因缺配置新条目而红，则挪第 9 组 |
| `frontend/src/lib/echarts.tsx`（MarkArea 注册） | 第 25 组 | 第 19 组 | markArea 被 module-home 与 product-category 图表共用；跟第 19、25 组中**先提交**的那组 |
| `frontend/src/api/contracts/marketMacro.ts` | 第 11 组 | 第 12 组 | 契约文件同时服务 macro 客户端与 market-data 页；第 11 组先提则归 11 |
| `frontend/src/api/marketDataMockClient.ts` | 第 8 组 | 第 12 组 | 本次 diff 主体是 stock workbench 的 replay_closure mock，归第 8 组；若第 12 组测试也依赖其新增 mock，两组都提完前不要跑全量前端测试下结论 |
| `.gitignore` | 第 1 组 | 第 3 组 | 含编码审计与清理战役两段忽略规则，皆为纯忽略行，整体归第 1 组即可 |
| ?? `docs/design-drafts/`（未跟踪目录） | 暂不提交 | 第 27 组 | 内容未审计；若确为 DESIGN 外迁的一部分则并入第 27 组 |
| ?? `unused/branch-cleanup-20260827.txt` | **保持本地** | 单独 chore 提交 | 69 个被删分支的 SHA 恢复凭据；对象在 reflog/远端仍可达，进主仓无长期价值。若需团队共享，建议转存 `docs/audits/` 作为清理审计凭据再提交 |
| ?? `unused/tmp-salvage-20260827/` | **保持本地** | — | 待终审抢救脚本；终审后要么正式化进 `scripts/` 要么删除，现在提交只会固化临时态 |

## 不建议提交的未跟踪残留（保持本地或删除）

`frontend/probe-batch-perf.tmp.mjs`、`frontend/probe-kpi-modal.tmp.mjs`、`frontend/shots-tmp.mjs`、`frontend/tmp_shots/`、`frontend/.tmp-audit-evidence/`、`frontend/.tmp-test-out.txt`、`frontend/dup-selectors.txt`、`frontend/deepresearch-css-classes.txt`、`frontend/extract-classes.ps1`、`frontend/find-dup-selectors.ps1`、`frontend/check-classes-usage.ps1`、`scripts/tmp_refresh_market_data.py`、`missing-governance-dir/`、`deliverables/`、`output/`、`moss_v7.pdf`、`moss_v7_pdf_pages/`。其中部分已被第 1 组的忽略规则覆盖。`start_dev.cmd`、`frontend/README.md` 看似有意的新文件，由用户决定归组（候选：第 28 组散件）。

## 覆盖性自查

声明：以 2026-08-27 12:58 复核时的 `git status --porcelain` 为准，**全部 474 个 M/D 受跟踪变更均已出现在上述第 1–30 组或"暂缓提交"节中**，无遗漏（已用脚本对文档路径与 git status 全量清单做差集核对，差集为空）。各组 M/D 计数：第 1 组 2、第 2 组 3、第 3 组 2、第 4 组 39、第 5 组 4、第 6 组 22、第 7 组 19、第 8 组 36、第 9 组 32、第 10 组 34、第 11 组 31、第 12 组 26、第 13 组 9、第 14 组 9、第 15 组 17、第 16 组 29、第 17 组 14、第 18 组 1、第 19 组 7、第 20 组 28、第 21 组 14、第 22 组 8、第 23 组 6、第 24 组 2、第 25 组 16、第 26 组 2、第 27 组 1、第 28 组 4、第 29 组 4、第 30 组 52、暂缓 1，合计 474。

注意：在途并行会话在六轮核对之间（12:44→12:58）持续新增文件（25→33→44→48→51→52），且漂移已扩散到 bond-dashboard、liability、livermore、agent 契约等前 29 组的域，第 30 组清单是活动快照。因此：**开始执行任何一组之前，先重跑一次差集核对**（`git status --porcelain` 对比本手册清单），把新增文件按第 30 组子簇或就近域归入；凡被漂移波及的组（当前已知第 6、9、10、15、16 组），提交前必须重新核对该组清单并重跑验证命令。差集核对脚本：`node -e "const fs=require('fs');const {execSync}=require('child_process');const doc=fs.readFileSync('docs/plans/2026-08-27-uncommitted-work-split-plan.md','utf8');const st=execSync('git -c core.quotepath=false status --porcelain',{encoding:'utf8'}).split(/\r?\n/).filter(l=>l&&!l.startsWith('??')).map(l=>l.slice(3).trim());const m=st.filter(p=>!doc.includes(p));console.log('missing='+m.length);m.forEach(x=>console.log(x));"`

若执行时基线已再次漂移（并行会话新增文件），以"执行前提"第 4 条处理：新增文件按目录就近归组并在提交信息注明，不要求回改本手册。

---

## 2026-09-02 基线刷新（审计整改后追加）

本手册基线为 2026-08-27 12:31 的 `git status`（474 M/D + 约 213 ??）。2026-09-02 全局审计与整改后，`git status --porcelain` 为 **675 行**（2026-09-02 17:39 快照，含本节新增的第 31 组与黄金样本重录；并行前端会话仍在落新文件，执行前请重跑差集脚本刷新）。本节不重排前 30 组，只做三件事：定义第 31 组、列出必须同笔的原子性约束、把手册未显式登记的增量按领域列出供执行者按第 4 条规则就近归组。执行前仍须满足"执行前提"第 1 条（并行会话收口）。

### 第 31 组 fix(audit-remediation) — 2026-09-02 全局审计整改

- 性质：固收正式口径血缘补齐（`bond_analytics` v3 / `risk_tensor` v7）、负 YTM 脏值下界、Campisi par 回退单一来源、RBAC 高风险动作集合、跨资产页刷新决策、`api/response_cache` 双路径迁移收口、注册表隔离修复、walk-forward 裁决守卫、重物化 operator 脚本、16 个黄金样本重录与 `approval.md` 记录、`.gitignore` 噪声收敛。审计报告见本次会话记录；文档同步见 `docs/calc_rules.md`「正式口径的整期日历归并与负收益率」小节。
- commit message：`fix(fixed-income): bump bond_analytics v3 / risk_tensor v7 for the calendar-merge and negative-ytm caliber, re-record golden samples, and close the audit remediation batch`
- **原子性约束（必须同一提交）**：
  1. `backend/app/core_finance/fixed_income_version_set.py` 的版本递增 ↔ 所有钉住版本字符串的后端测试 ↔ 5 个固收黄金样本（`GS-BOND-*`、`GS-CONCENTRATION-MONITOR-A`、`GS-RISK-*`）↔ 前端 mock 常量 `frontend/src/api/executiveClient.ts` 与 4 个前端测试。拆开任一部分，中间提交点的 canonical 门禁或 vitest 即红。
  2. `scripts/backend_release_suite.py`（在途，已在第 30 组）新增引用的 5 个未跟踪测试 `tests/test_release_approval_registry.py`、`tests/test_release_approval_evidence_gate.py`、`tests/test_release_control_golden_blocker_review.py`、`tests/test_wp7_release_rehearsal.py`、`tests/test_wp7_fixed_income_pilot_preflight.py` 必须与门禁脚本同笔（属释放控制面组，见下文增量表）。
  3. `backend/app/api/response_cache.py`、`backend/app/api/perf_logging.py` 两个 shim 已删除；`backend/app/observability/{response_cache,perf_logging}.py`（?? 未跟踪）与所有改为 observability 路径的路由/任务/测试必须同笔，否则中间提交点 import 失败。
- 文件清单（99 项；黄金样本 37 项单列）：
  - M `.gitignore`
  - M `backend/app/api/routes/balance_analysis.py`
  - M `backend/app/api/routes/bond_analytics.py`
  - M `backend/app/api/routes/bond_dashboard.py`
  - M `backend/app/api/routes/campisi_attribution.py`
  - M `backend/app/api/routes/dashboard.py`
  - M `backend/app/api/routes/executive.py`
  - M `backend/app/api/routes/macro_toolkit.py`
  - M `backend/app/api/routes/macro_vendor.py`
  - M `backend/app/api/routes/market_data_livermore.py`
  - M `backend/app/api/routes/pnl.py`
  - M `backend/app/core_finance/bond_analytics/engine.py`
  - M `backend/app/core_finance/bond_four_effects.py`
  - M `backend/app/core_finance/credit_spread.py`
  - ?? `backend/app/core_finance/fixed_income_version_set.py`
  - M `backend/app/core_finance/krd.py`
  - M `backend/app/core_finance/pnl_attribution/workbench.py`
  - M `backend/app/core_finance/position_sizing.py`
  - ?? `backend/app/core_finance/stock_portfolio_risk.py`
  - M `backend/app/security/route_policy.py`
  - M `backend/app/tasks/choice_macro.py`
  - M `backend/app/tasks/livermore_gate_supplement.py`
  - M `backend/app/tasks/macro_toolkit_refresh.py`
  - M `backend/app/tasks/macro_toolkit_write_refresh.py`
  - M `backend/tests/core_finance/test_position_sizing.py`
  - M `docs/calc_rules.md`
  - M `docs/golden_sample_catalog.md`
  - M `frontend/src/api/executiveClient.ts`
  - M `frontend/src/features/workbench/module-home/riskHomeAdapter.test.ts`
  - M `frontend/src/test/CrossAssetDriversRoute.test.tsx`
  - M `frontend/src/test/HomeStartupClient.test.ts`
  - M `frontend/src/test/MacroToolkitPage.test.tsx`
  - M `frontend/src/test/ModuleWorkbenchHomePage.test.tsx`
  - M `frontend/src/test/RiskTensorPage.test.tsx`
  - ?? `scripts/rematerialize_fixed_income_versions.py`
  - M `tests/test_agent_enabled_path_smoke.py`
  - M `tests/test_api_response_cache.py`
  - M `tests/test_auth_context.py`
  - M `tests/test_bond_analytics_api.py`
  - M `tests/test_bond_analytics_core.py`
  - M `tests/test_bond_analytics_engine.py`
  - M `tests/test_bond_analytics_service_real_data.py`
  - M `tests/test_bond_analytics_service.py`
  - M `tests/test_bond_dashboard_api_contract.py`
  - ?? `tests/test_bond_risk_shadow_candidate.py`
  - M `tests/test_dashboard_home_backend_blocks.py`
  - ?? `tests/test_fixed_income_version_set.py`
  - M `tests/test_formal_compute_lineage.py`
  - M `tests/test_macro_toolkit_async_write_refresh.py`
  - M `tests/test_macro_vendor_refresh_async_contract.py`
  - M `tests/test_market_data_livermore_api.py`
  - M `tests/test_market_data_livermore_route_support_import.py`
  - ?? `tests/test_rematerialize_fixed_income_versions.py`
  - M `tests/test_risk_coupon_window_repair.py`
  - M `tests/test_risk_tensor_api.py`
  - M `tests/test_risk_tensor_materialize.py`
  - M `tests/test_risk_tensor_repo.py`
  - M `tests/test_risk_tensor_service.py`
  - ?? `tests/test_strategy_walk_forward_verdicts_report_anchor.py`
  - M `tests/test_user_scope_repo.py`
  - D `backend/app/api/response_cache.py`（shim 删除）
  - D `backend/app/api/perf_logging.py`（shim 删除）
  - 黄金样本重录（`response.json` + `approval.md`，固收 5 个另含 `assertions.md`）：
    - `tests/golden_samples/GS-AVERAGE-BALANCE-MONTHLY-A/`
    - `tests/golden_samples/GS-BAL-OVERVIEW-A/`
    - `tests/golden_samples/GS-BAL-WORKBOOK-A/`
    - `tests/golden_samples/GS-BOND-ANALYSIS-ACTION-ATTR-A/`
    - `tests/golden_samples/GS-BOND-HEADLINE-A/`
    - `tests/golden_samples/GS-BRIDGE-A/`
    - `tests/golden_samples/GS-BRIDGE-WARN-B/`
    - `tests/golden_samples/GS-CASHFLOW-PROJECTION-A/`
    - `tests/golden_samples/GS-CONCENTRATION-MONITOR-A/`
    - `tests/golden_samples/GS-PNL-ATTR-WB-A/`
    - `tests/golden_samples/GS-PNL-BUSINESS-INSIGHTS-A/`
    - `tests/golden_samples/GS-PNL-DATA-A/`
    - `tests/golden_samples/GS-PNL-OVERVIEW-A/`
    - `tests/golden_samples/GS-RISK-A/`
    - `tests/golden_samples/GS-RISK-WARN-B/`
    - `tests/golden_samples/GS-STOCK-ANALYSIS-OBS-A/`
- 提交前验证：
  - `.\.venv\Scripts\python.exe scripts/backend_release_suite.py`（2026-09-02 实测：762 通过，MCP 快速套件 8 通过）
  - `.\.venv\Scripts\python.exe -m pytest -q -n 4 tests/test_fixed_income_version_set.py tests/test_bond_analytics_engine.py tests/test_bond_analytics_core.py tests/test_bond_four_effects.py tests/test_auth_context.py tests/test_user_scope_repo.py tests/test_formal_compute_lineage.py tests/test_bond_analytics_purge_interruption.py tests/test_rematerialize_fixed_income_versions.py tests/test_strategy_walk_forward_verdicts_report_anchor.py tests/test_api_response_cache.py tests/test_market_data_livermore_route_support_import.py`
  - `cd frontend && npm run typecheck && npm run lint && npx vitest run src/test/CrossAssetDriversRoute.test.tsx src/test/RiskTensorPage.test.tsx src/test/ModuleWorkbenchHomePage.test.tsx src/test/HomeStartupClient.test.ts src/features/workbench/module-home/riskHomeAdapter.test.ts`
- 风险备注：历史事实按 v3/v7 重物化由 `scripts/rematerialize_fixed_income_versions.py` 完成（回执 `.codex-tmp/rematerialize/full-20260902.jsonl`）；重物化是数据操作，不进入提交。`GS-BAL-WORKBOOK-A` 的三处内容漂移已由 owner `arvin` 会话内授权重录，最终 approver 仍待定。

### 增量文件（手册未显式登记，按领域列出；按第 4 条规则就近归组，新增领域建议单开组）

共 398 项。匹配方式为路径关键词，仅作归组提示，不替代人工判断；`M` 为已跟踪修改，`??` 为未跟踪。

#### 其它（按目录就近归组）（74）

- M `backend/app/api/__init__.py`
- M `backend/app/main.py`
- M `backend/app/models/__init__.py`
- M `backend/app/repositories/source_preview_repo.py`
- M `backend/app/tasks/materialize.py`
- M `backend/app/tasks/source_preview_refresh.py`
- ?? `backend/tests/core_finance/test_fundamental_missing_inputs.py`
- M `frontend/scripts/sampleHomeStartupLive.mjs`
- M `frontend/scripts/verifyHomeStartupBundle.mjs`
- M `frontend/src/api/contracts/core.ts`
- M `frontend/src/api/cubeClient.ts`
- M `frontend/src/features/concentration-monitor/concentrationMonitor.module.css`
- M `frontend/src/features/concentration-monitor/ConcentrationMonitorPage.css`
- M `frontend/src/features/concentration-monitor/ConcentrationMonitorPage.tsx`
- M `frontend/src/features/cube-query/pages/CubeQueryPage.module.css`
- M `frontend/src/features/cube-query/pages/CubeQueryPage.tsx`
- ?? `frontend/src/features/decision-items/lib/decisionItemsPageModel.test.ts`
- M `frontend/src/features/decision-items/lib/decisionItemsPageModel.ts`
- M `frontend/src/features/decision-items/pages/DecisionItemsPage.css`
- M `frontend/src/features/decision-items/pages/DecisionItemsPage.tsx`
- M `frontend/src/features/kpi-performance/components/MetricTable.tsx`
- M `frontend/src/features/kpi-performance/components/OwnerList.tsx`
- M `frontend/src/features/kpi-performance/pages/KpiPerformancePage.css`
- M `frontend/src/features/platform-config/PlatformConfigPage.module.css`
- M `frontend/src/features/platform-config/PlatformConfigPage.tsx`
- M `frontend/src/features/positions/components/IndustryDistributionCard.tsx`
- M `frontend/src/features/positions/components/PositionsBondsConcentrationSection.tsx`
- M `frontend/src/features/positions/components/PositionsBondsDistributionSection.tsx`
- M `frontend/src/features/positions/components/PositionsBondsWorkspaceSection.tsx`
- M `frontend/src/features/positions/components/PositionsEvidenceSection.css`
- M `frontend/src/features/positions/components/PositionsInterbankSplitSection.tsx`
- M `frontend/src/features/positions/components/PositionsInterbankWorkspaceSection.tsx`
- D `frontend/src/features/positions/components/PositionsKpiBand.tsx`
- D `frontend/src/features/positions/components/PositionsSectionLead.tsx`
- ?? `frontend/src/features/positions/components/positionsTableState.ts`
- M `frontend/src/features/positions/components/PositionsView.css`
- M `frontend/src/features/positions/components/PositionsView.tsx`
- M `frontend/src/features/positions/components/RatingDistributionCard.tsx`
- M `frontend/src/features/team-performance/TeamPerformancePage.tsx`
- M `frontend/src/router/routes.tsx`
- M `frontend/src/test/BondAnalyticsEvidencePanels.test.tsx`
- M `frontend/src/test/BondAnalyticsOverviewPanels.test.tsx`
- M `frontend/src/test/BondAnalyticsView.test.tsx`
- ?? `frontend/src/test/contractSyncUtils.ts`
- M `frontend/src/test/CubeQueryPage.test.tsx`
- M `frontend/src/test/DashboardHomePage.test.tsx`
- M `frontend/src/test/FormalResultMetaPanel.test.tsx`
- M `frontend/src/test/KpiPerformancePage.test.tsx`
- M `frontend/src/test/OperationsAnalysisPage.governed.test.tsx`
- M `frontend/src/test/portfolioCrossPageGoldenSample.ts`
- ?? `frontend/src/test/PositionsContractSync.test.ts`
- M `frontend/src/test/RouteRegistry.test.tsx`
- M `frontend/src/test/SourcePreviewPage.test.tsx`
- M `frontend/src/test/StartupPerformanceGuards.test.ts`
- M `frontend/src/test/StockDetailDrawer.test.tsx`
- M `frontend/src/test/TeamPerformancePage.test.tsx`
- M `frontend/src/test/TPLMarketChart.test.tsx`
- M `frontend/src/utils/format.test.ts`
- ?? `frontend/tests/playwright/exact-numeric-boundary.spec.mjs`
- M `tests/test_akshare_adapter_fx.py`
- M `tests/test_api_contract_baseline_gate.py`
- M `tests/test_api_contract_tooling.py`
- ?? `tests/test_api_smoke_wave1_t01.py`
- M `tests/test_backend_release_suite.py`
- M `tests/test_ci_workflow_contents.py`
- M `tests/test_fx_analytical_view_api.py`
- M `tests/test_fx_analytical_view_service.py`
- M `tests/test_fx_docs_contract.py`
- M `tests/test_materialize_flow.py`
- M `tests/test_no_finance_logic_in_frontend.py`
- M `tests/test_pct_raw_scale_numeric_fields.py`
- M `tests/test_positions_api_contract.py`
- ?? `tests/test_postgres_schema_bootstrap.py`
- M `tests/test_source_preview_flow.py`

#### 股票分析 / 组合构建（stock-analysis）（46）

- M `backend/app/core_finance/fresh_trend_watchlist_candidates.py`
- M `backend/app/core_finance/livermore_stock_candidates.py`
- M `backend/app/core_finance/uptrend_momentum_candidates.py`
- M `backend/app/repositories/livermore_market_read_repo.py`
- M `backend/app/schema_registry/duckdb/27_choice_stock_factor_snapshot.sql`
- M `backend/app/services/livermore_stock_detail_service.py`
- ?? `backend/app/services/stock_portfolio_construction_service.py`
- M `backend/app/tasks/stock_factor_refresh.py`
- M `backend/app/tasks/tushare_news_ingest.py`
- ?? `backend/scripts/backfill_stock_factor_market_cap_tushare.py`
- ?? `backend/tests/core_finance/test_stock_portfolio_risk.py`
- ?? `docs/plans/2026-08-31-stock-strategy-cockpit-prd.md`
- ?? `docs/plans/2026-09-01-stock-analysis-reference-terminal-rebuild-plan.md`
- ?? `frontend/src/api/candidateFinancialIndicatorsClient.ts`
- M `frontend/src/api/stockAnalysisWorkbenchClient.test.ts`
- M `frontend/src/api/stockAnalysisWorkbenchClient.ts`
- ?? `frontend/src/features/stock-analysis/components/research-desk/`
- M `frontend/src/features/stock-analysis/components/StockAnalysisCandidateLedgerTable.module.css`
- M `frontend/src/features/stock-analysis/components/StockAnalysisDataHealthCard.test.tsx`
- M `frontend/src/features/stock-analysis/components/StockAnalysisDataHealthCard.tsx`
- M `frontend/src/features/stock-analysis/components/StockAnalysisFactorCandidatesCard.tsx`
- ?? `frontend/src/features/stock-analysis/components/StockAnalysisFirstScreenAccessibility.test.tsx`
- M `frontend/src/features/stock-analysis/components/StockAnalysisFirstScreenHero.tsx`
- M `frontend/src/features/stock-analysis/components/StockAnalysisGateConditionsCard.tsx`
- ?? `frontend/src/features/stock-analysis/components/StockAnalysisStageNav.module.css`
- ?? `frontend/src/features/stock-analysis/components/StockAnalysisStageNav.test.tsx`
- ?? `frontend/src/features/stock-analysis/components/StockAnalysisStageNav.tsx`
- M `frontend/src/features/stock-analysis/components/StockAnalysisWorkbenchActions.tsx`
- M `frontend/src/features/stock-analysis/components/StockDetailDrawer.tsx`
- ?? `frontend/src/features/stock-analysis/lib/stockAnalysisFormat.test.ts`
- ?? `frontend/src/features/stock-analysis/lib/stockAnalysisFormat.ts`
- ?? `frontend/src/features/stock-analysis/lib/stockAnalysisResearchDeskModel.test.ts`
- ?? `frontend/src/features/stock-analysis/lib/stockAnalysisResearchDeskModel.ts`
- ?? `frontend/src/features/stock-analysis/pages/StockAnalysisEditorialLedger.css`
- ?? `frontend/src/features/stock-analysis/pages/StockAnalysisResearchDesk.module.css`
- ?? `frontend/src/features/stock-analysis/pages/StockAnalysisResearchDesk.test.tsx`
- ?? `frontend/src/features/stock-analysis/pages/StockAnalysisResearchDesk.tsx`
- ?? `frontend/src/features/stock-analysis/pages/StockPortfolioConstructionPage.module.css`
- ?? `frontend/src/features/stock-analysis/pages/StockPortfolioConstructionPage.test.tsx`
- ?? `frontend/src/features/stock-analysis/pages/StockPortfolioConstructionPage.tsx`
- ?? `frontend/src/test/StockAnalysisPageChromeContract.test.ts`
- ?? `frontend/src/test/StockAnalysisReferenceTerminalContract.test.tsx`
- ?? `frontend/src/test/StockPortfolioConstructionPage.test.tsx`
- M `frontend/tests/playwright/stock-analysis-first-screen-geometry.spec.mjs`
- M `tests/test_stock_analysis_current_rule_factor_write.py`
- ?? `tests/test_stock_portfolio_construction_service.py`

#### 固收 / 风险张量后端（bond & risk）（46）

- M `backend/app/core_finance/risk_tensor.py`
- M `backend/app/repositories/bond_analytics_repo.py`
- M `backend/app/repositories/risk_tensor_repo.py`
- M `backend/app/schema_registry/duckdb/02_bond_analytics.sql`
- M `backend/app/schemas/bond_analytics.py`
- M `backend/app/services/bond_analytics_service.py`
- M `backend/app/services/bond_dashboard_service.py`
- M `backend/app/services/cashflow_projection_service.py`
- M `backend/app/services/risk_tensor_service.py`
- M `backend/app/tasks/bond_analytics_materialize.py`
- M `backend/app/tasks/risk_tensor_materialize.py`
- M `frontend/src/features/bond-analytics/components/AccountingClassAuditView.tsx`
- M `frontend/src/features/bond-analytics/components/ActionAttributionView.tsx`
- M `frontend/src/features/bond-analytics/components/BenchmarkExcessView.tsx`
- M `frontend/src/features/bond-analytics/components/BondAnalyticsDetailPrimitives.module.css`
- M `frontend/src/features/bond-analytics/components/BondAnalyticsInstitutionalCockpit.module.css`
- M `frontend/src/features/bond-analytics/components/BondAnalyticsInstitutionalCockpit.tsx`
- M `frontend/src/features/bond-analytics/components/BondAnalyticsOverviewPanels.tsx`
- M `frontend/src/features/bond-analytics/components/CreditSpreadView.tsx`
- M `frontend/src/features/bond-analytics/components/DV01RiskView.tsx`
- M `frontend/src/features/bond-analytics/components/KRDCurveRiskView.tsx`
- M `frontend/src/features/bond-analytics/components/PerformanceComparison.tsx`
- M `frontend/src/features/bond-analytics/components/ReturnDecompositionView.tsx`
- M `frontend/src/features/bond-analytics/components/RiskTrendChart.tsx`
- D `frontend/src/features/bond-analytics/components/SectionLead.tsx`
- ?? `frontend/src/features/bond-dashboard/model/bondDashboardExactNumeric.test.ts`
- M `frontend/src/features/bond-dashboard/model/bondDashboardPageModel.test.ts`
- M `frontend/src/features/bond-dashboard/model/bondDashboardPageModel.ts`
- M `frontend/src/features/bond-trading-desk/BondTradingDeskPage.module.css`
- M `frontend/src/features/bond-trading-desk/components/BondTradingDeskDecisionRail.tsx`
- M `frontend/src/features/bond-trading-desk/pages/BondTradingDeskPage.tsx`
- M `frontend/src/features/cashflow-projection/pages/CashflowProjectionPage.tsx`
- M `frontend/src/features/cashflow-projection/pages/cashflowProjectionPageModel.test.ts`
- M `frontend/src/features/cashflow-projection/pages/cashflowProjectionPageModel.ts`
- M `frontend/src/features/risk-tensor/RiskTensorPage.tsx`
- ?? `frontend/src/features/risk-tensor/riskTensorPageModel.test.ts`
- ?? `frontend/src/features/risk-tensor/riskTensorPageModel.ts`
- M `frontend/src/test/CashflowProjectionPage.test.tsx`
- M `frontend/src/test/RiskTensorUnitContract.test.tsx`
- M `tests/test_bond_analytics_numeric_migration.py`
- ?? `tests/test_bond_analytics_purge_interruption.py`
- M `tests/test_bond_analytics_repo.py`
- ?? `tests/test_bond_risk_shadow_batch.py`
- M `tests/test_cashflow_projection_numeric_migration.py`
- M `tests/test_cashflow_projection.py`
- M `tests/test_risk_tensor_core.py`

#### 余额 / 日均 / 负债（balance / ADB / liability）（43）

- M `backend/app/api/routes/adb_analysis.py`
- M `backend/app/repositories/choice_fx_catalog.py`
- M `backend/app/repositories/currency_codes.py`
- ?? `backend/app/schemas/adb_analysis.py`
- M `backend/app/schemas/balance_analysis.py`
- M `backend/app/tasks/fx_mid_backfill.py`
- M `docs/BALANCE_ANALYSIS_FX_SOURCE_RUNBOOK.md`
- M `docs/BALANCE_ANALYSIS_RECONCILIATION_2026-03-01.md`
- M `docs/BALANCE_ANALYSIS_SPEC_FOR_CODEX.md`
- M `docs/pnl/average-balance-owner-evidence-packet.md`
- M `frontend/src/api/contracts/cubeAdb.ts`
- M `frontend/src/features/average-balance/components/AdbConcentrationPanel.tsx`
- M `frontend/src/features/average-balance/components/AdbDeepAnalysisSection.tsx`
- M `frontend/src/features/average-balance/components/AdbKpiStrip.tsx`
- M `frontend/src/features/average-balance/components/AdbNimAttributionPanel.tsx`
- M `frontend/src/features/average-balance/components/AdbScaleAttributionPanel.tsx`
- ?? `frontend/src/features/average-balance/components/adbSectionHeadNumbering.ts`
- M `frontend/src/features/average-balance/components/AdbVolatilityPanel.tsx`
- M `frontend/src/features/average-balance/components/AverageBalanceView.css`
- M `frontend/src/features/average-balance/components/AverageBalanceView.tsx`
- M `frontend/src/features/balance-analysis/cockpit/BalanceAnalysisCockpit.tsx`
- D `frontend/src/features/balance-analysis/components/BalanceSectionHead.tsx`
- ?? `frontend/src/features/balance-analysis/components/balanceSectionNumbering.ts`
- M `frontend/src/features/balance-analysis/pages/BalanceAnalysisPage.tsx`
- M `frontend/src/features/balance-analysis/pages/balanceAnalysisPageModel.test.ts`
- M `frontend/src/features/balance-movement-analysis/pages/BalanceMovementAnalysisFigma.css`
- M `frontend/src/features/balance-movement-analysis/pages/BalanceMovementAnalysisPage.tsx`
- M `frontend/src/features/liability-analytics/components/LiabilityNimStressPanel.tsx`
- D `frontend/src/features/liability-analytics/components/LiabilitySectionLead.tsx`
- M `frontend/src/test/AverageBalanceView.test.tsx`
- M `frontend/src/test/BalanceAnalysisDateSemanticsContract.test.tsx`
- M `frontend/src/test/BalanceAnalysisPage.test.tsx`
- ?? `frontend/src/test/BalanceContractSync.test.ts`
- M `frontend/src/test/BalanceMovementAnalysisPage.test.tsx`
- M `tests/test_average_balance_owner_evidence_packet.py`
- M `tests/test_balance_analysis_api.py`
- M `tests/test_balance_analysis_contracts.py`
- M `tests/test_balance_analysis_materialize_flow.py`
- ?? `tests/test_capture_average_balance_monthly_golden_candidate.py`
- M `tests/test_choice_fx_catalog_selection.py`
- M `tests/test_fx_mid_backfill_governance.py`
- M `tests/test_fx_mid_backfill.py`
- M `tests/test_fx_mid_materialize.py`

#### 前端壳层 / 布局 / 设计系统 / 首页（37）

- ?? `docs/prd-workbench-visual-noise-convergence.md`
- M `frontend/src/components/charts/BaseChart.tsx`
- M `frontend/src/components/page/FormalResultMetaPanel.css`
- M `frontend/src/components/page/FormalResultMetaPanel.tsx`
- M `frontend/src/components/page/PagePrimitives.module.css`
- M `frontend/src/components/page/PagePrimitives.tsx`
- M `frontend/src/components/page/PagePrimitiveStyles.ts`
- M `frontend/src/features/market-finance/pages/MarketFinanceWorkbenchPage.css`
- M `frontend/src/features/market-finance/pages/MarketFinanceWorkbenchPage.tsx`
- M `frontend/src/features/workbench/dashboard-home/useDashboardHomeSupplementalHydration.ts`
- M `frontend/src/features/workbench/market-shell/index.ts`
- M `frontend/src/features/workbench/market-shell/MarketWorkbenchFrame.module.css`
- M `frontend/src/features/workbench/market-shell/MarketWorkbenchFrame.tsx`
- M `frontend/src/features/workbench/market-shell/types.ts`
- M `frontend/src/features/workbench/module-home/marketBackendDataWorkbench.module.css`
- M `frontend/src/features/workbench/module-home/MarketHomeLayout.tsx`
- M `frontend/src/features/workbench/module-home/moduleHomeModel.ts`
- M `frontend/src/features/workbench/module-home/moduleWorkbenchHome.module.css`
- M `frontend/src/features/workbench/module-home/ModuleWorkbenchHomePage.tsx`
- M `frontend/src/features/workbench/module-home/PortfolioDistributionPanel.tsx`
- M `frontend/src/features/workbench/module-home/PortfolioHoldingsHeroBand.tsx`
- M `frontend/src/features/workbench/module-home/portfolioHome.module.css`
- M `frontend/src/features/workbench/module-home/PortfolioHomeLayout.tsx`
- M `frontend/src/features/workbench/module-home/riskHomeAdapter.ts`
- M `frontend/src/features/workbench/module-home/riskOverview.module.css`
- M `frontend/src/features/workbench/module-home/RiskOverviewPage.tsx`
- M `frontend/src/layouts/workbenchShellSections.ts`
- M `frontend/src/styles/workbenchDeferredChrome.css`
- M `frontend/src/styles/workbenchInstitutionalConsole.css`
- ?? `frontend/src/test/BaseChart.test.tsx`
- M `frontend/src/test/MarketFinanceWorkbenchPage.test.tsx`
- M `frontend/src/test/ModuleWorkbenchHomeModel.test.ts`
- M `frontend/src/test/PagePrimitivesV2.test.tsx`
- M `frontend/src/test/WorkbenchPlaceholderPage.test.tsx`
- M `frontend/src/test/WorkbenchShell.test.tsx`
- M `frontend/src/test/WorkbenchShellThemeGuard.test.ts`
- ?? `frontend/tests/playwright/workbench-shell-responsive.spec.mjs`

#### PnL / 归因 / 产品分类（36）

- M `backend/app/schemas/pnl_bridge.py`
- M `backend/app/services/campisi_attribution_service.py`
- M `backend/app/services/pnl_attribution_service.py`
- M `frontend/src/api/contracts/pnl.ts`
- M `frontend/src/api/pnlMockClient.ts`
- M `frontend/src/features/ledger-dashboard/pages/LedgerDashboardPage.css`
- M `frontend/src/features/ledger-dashboard/pages/LedgerDashboardPage.tsx`
- ?? `frontend/src/features/ledger-pnl/components/LedgerPnlWorkbookTables.test.tsx`
- M `frontend/src/features/pnl-attribution/components/PnlAttributionView.test.ts`
- M `frontend/src/features/pnl-attribution/components/pnlAttributionViewModel.ts`
- M `frontend/src/features/pnl-attribution/components/PnlAttributionVolumeRateTab.tsx`
- M `frontend/src/features/pnl-attribution/components/TPLMarketChart.tsx`
- M `frontend/src/features/pnl-business-insights/PnlByBusinessInsightsPage.css`
- M `frontend/src/features/pnl-business-insights/PnlByBusinessInsightsPage.tsx`
- M `frontend/src/features/pnl/FormalPnlV1Page.css`
- M `frontend/src/features/pnl/FormalPnlV1Page.tsx`
- M `frontend/src/features/pnl/PnlBridgePage.css`
- M `frontend/src/features/pnl/PnlBridgePage.tsx`
- M `frontend/src/features/pnl/pnlByBusinessExport.test.ts`
- M `frontend/src/features/pnl/PnlByBusinessPage.css`
- M `frontend/src/features/pnl/PnlByBusinessPage.tsx`
- M `frontend/src/features/pnl/pnlByBusinessPageModel.test.ts`
- M `frontend/src/features/product-category-pnl/pages/MonthlyOperatingAnalysisAuditPage.tsx`
- M `frontend/src/features/product-category-pnl/pages/MonthlyOperatingAnalysisBranch.tsx`
- M `frontend/src/features/product-category-pnl/pages/ProductCategoryAdjustmentAuditPage.tsx`
- M `frontend/src/features/product-category-pnl/pages/ProductCategoryPnlPage.css`
- M `frontend/src/features/product-category-pnl/pages/ProductCategoryPnlPage.tsx`
- M `frontend/src/test/LedgerDashboardPage.test.tsx`
- ?? `frontend/src/test/PnlContractSync.test.ts`
- M `frontend/src/test/PnlRoutesSmoke.test.tsx`
- M `frontend/src/test/ProductCategoryAdjustmentAuditPage.test.tsx`
- M `frontend/src/test/ProductCategoryBranchSwitcher.test.tsx`
- M `tests/test_campisi_four_effects_detail_summary.py`
- M `tests/test_pnl_bridge_curve_availability_contract.py`
- M `tests/test_pnl_bridge_curve_effects.py`
- M `tests/test_pnl_bridge_numeric_migration.py`

#### 宏观 / 市场数据 / 跨资产（35）

- M `backend/app/services/research_radar_compare.py`
- M `backend/app/services/research_radar_service.py`
- M `frontend/src/api/marketDataClient.ts`
- M `frontend/src/features/cross-asset/components/CrossAssetDecisionZone.tsx`
- D `frontend/src/features/cross-asset/components/CrossAssetKpiBand.css`
- M `frontend/src/features/cross-asset/components/CrossAssetKpiBand.tsx`
- M `frontend/src/features/cross-asset/components/crossAssetLayoutStability.test.ts`
- M `frontend/src/features/cross-asset/components/ReferencePanels.tsx`
- M `frontend/src/features/cross-asset/hooks/useCrossAssetViewModel.ts`
- M `frontend/src/features/cross-asset/pages/CrossAssetDriversPage.tsx`
- M `frontend/src/features/macro-observation/components/MacroObservationKpiBand.tsx`
- ?? `frontend/src/features/macro-observation/components/macroObservationSectionHeadNumbering.ts`
- D `frontend/src/features/macro-observation/components/MacroObservationSectionLead.tsx`
- M `frontend/src/features/macro-observation/sections/MacroObservationConclusionSignal.css`
- M `frontend/src/features/macro-observation/sections/MacroObservationCrisisSection.tsx`
- M `frontend/src/features/macro-observation/sections/MacroObservationDataHealthSection.tsx`
- M `frontend/src/features/macro-observation/sections/MacroObservationHealthEvidence.css`
- M `frontend/src/features/macro-observation/sections/MacroObservationModelCrisis.css`
- M `frontend/src/features/macro-observation/sections/MacroObservationModelStrategySection.tsx`
- M `frontend/src/features/macro-observation/sections/MacroObservationSignalRiskSection.tsx`
- M `frontend/src/features/macro-toolkit/sections/MacroToolkitExecutionSections.tsx`
- M `frontend/src/features/macro-toolkit/sections/MacroToolkitPageStates.tsx`
- M `frontend/src/features/macro-toolkit/sections/MacroToolkitRiskSections.tsx`
- M `frontend/src/features/news-events/NewsEventsPage.css`
- M `frontend/src/features/news-events/NewsEventsPage.tsx`
- ?? `frontend/src/features/workbench/dashboard-home/adapters/buildHomeBondNewsModel.test.ts`
- M `frontend/src/test/CrossAssetPage.test.tsx`
- M `frontend/src/test/MacroObservationConclusionSignalSections.test.tsx`
- M `frontend/src/test/MacroToolkitPageCssBudget.test.ts`
- M `frontend/src/test/NewsEventsPage.test.tsx`
- M `frontend/tests/playwright/market-data-terminal-smoke.spec.mjs`
- M `frontend/tests/playwright/market-data-workflow-smoke.spec.mjs`
- M `tests/test_choice_news_latest_batch.py`
- M `tests/test_choice_news_routes.py`
- M `tests/test_macro_toolkit_refresh_receipt_service.py`

#### 治理 / 血缘 / 存储引导 / 迁移（21）

- M `backend/alembic/env.py`
- ?? `backend/alembic/versions/7d1a2c3e4f50_add_agent_governance_stream_tables.py`
- M `backend/app/governance/formal_compute_lineage.py`
- M `backend/app/models/governance.py`
- M `backend/app/postgres_migrations.py`
- M `backend/app/repositories/duckdb_schema_registry.py`
- M `backend/app/repositories/governance_repo.py`
- M `backend/app/repositories/user_scope_repo.py`
- M `backend/app/schema_registry/duckdb_loader.py`
- M `backend/app/schema_registry/duckdb/manifest.json`
- M `backend/app/schemas/result_meta.py`
- M `backend/app/security/auth_context.py`
- M `backend/app/services/formal_result_runtime.py`
- M `backend/app/storage_migration_flags.py`
- ?? `backend/scripts/migrate_storage.py`
- M `tests/test_alembic_migrations.py`
- M `tests/test_duckdb_schema_bootstrap.py`
- M `tests/test_formal_compute_result_meta_contract.py`
- M `tests/test_governance_sql_authority.py`
- M `tests/test_schema_registry_consistency.py`
- ?? `tests/test_storage_bootstrap.py`

#### 释放控制面（release control plane，含 WP7 演练）（20）

- ?? `backend/alembic/versions/c2e94f6a8b10_add_release_control_tables.py`
- ?? `backend/app/governance/release_approval.py`
- ?? `backend/app/governance/release_control.py`
- ?? `backend/app/models/release_control.py`
- ?? `backend/app/repositories/release_control_repo.py`
- ?? `backend/app/schemas/release_approval.py`
- ?? `backend/app/schemas/release_control.py`
- ?? `config/release_approval_registry.v1.json`
- ?? `docs/prd-release-control-plane.md`
- ?? `docs/release-control-plane-execution-plan.md`
- ?? `tests/test_release_approval_evidence_gate.py`
- ?? `tests/test_release_approval_registry.py`
- ?? `tests/test_release_control_cli.py`
- ?? `tests/test_release_control_golden_blocker_review.py`
- ?? `tests/test_release_control_postgres_concurrency.py`
- ?? `tests/test_release_control_repo.py`
- ?? `tests/test_release_control_schema.py`
- ?? `tests/test_release_control_state_machine.py`
- ?? `tests/test_wp7_fixed_income_pilot_preflight.py`
- ?? `tests/test_wp7_release_rehearsal.py`

#### 精确数值策略（exact numeric）（13）

- ?? `backend/app/governance/exact_numeric_policy.py`
- M `backend/app/schemas/common_numeric.py`
- M `backend/app/services/explicit_numeric.py`
- ?? `config/exact_numeric_compat_registry.v1.json`
- ?? `docs/pnl/campisi-exact-numeric-owner-decision.md`
- ?? `frontend/src/api/numeric.test.ts`
- ?? `frontend/src/api/pnlClient.test.ts`
- ?? `frontend/src/features/bond-dashboard/components/exactNumericCharts.test.tsx`
- ?? `frontend/src/test/exactNumericPolicyGuard.test.ts`
- M `frontend/src/test/numeric.test.ts`
- M `tests/test_common_numeric.py`
- ?? `tests/test_exact_numeric_policy.py`
- M `tests/test_pnl_attribution_service_explicit_numeric.py`

#### 文档 / 计划 / 审计记录（10）

- M `docs/API_CONTRACT_TOOLING.md`
- M `docs/audit/MOSS_V3_SECOND_AUDIT_EVIDENCE_2026-07-05.md`
- M `docs/ci-release-suite.md`
- ?? `docs/fixed_income_whole_bundle_shadow_runbook.md`
- M `docs/MAINTENANCE.md`
- ?? `docs/plans/2026-08-27-audit-remediation-prd.md`
- ?? `docs/plans/2026-08-27-frontend-system-optimization-plan.md`
- ?? `docs/plans/2026-08-27-skipped-tests-inventory.md`
- ?? `docs/plans/2026-08-27-uncommitted-work-split-plan.md`
- ?? `docs/runbooks/`

#### 市场总览后端计算（market overview）（9）

- ?? `backend/app/api/routes/market_overview.py`
- ?? `backend/app/services/market_overview_service.py`
- ?? `docs/plans/2026-09-02-market-overview-fix-dispatch/`
- ?? `docs/plans/2026-09-02-market-overview-module-compute-plan.md`
- M `frontend/src/features/workbench/module-home/MarketOverviewDenseFirstScreen.test.tsx`
- ?? `frontend/src/features/workbench/module-home/moduleHomeQueryPermission.ts`
- M `frontend/src/features/workbench/module-home/useMarketHomeQueries.ts`
- M `frontend/tests/playwright/market-overview-smoke.spec.mjs`
- ?? `tests/test_market_overview_snapshot_api.py`

#### CI / 仓库配置（5）

- M `.github/workflows/ci.yml`
- ?? `.nvmrc`
- ?? `.python-version`
- M `tests/ci_skip_registry.json`
- M `tests/conftest.py`

#### 可观测性（observability）（2）

- ?? `backend/app/observability/perf_logging.py`
- ?? `backend/app/observability/response_cache.py`

#### 脚本 / 调度 / 审计工具（1）

- M `audit_pack/08_RUN_AND_TEST.md`

### 建议执行序更新

原序不变；第 31 组依赖第 5 组（bond-dashboard 后端 schema，`raw_text` 精确数值字段）与第 30 组（`scripts/backend_release_suite.py`），应在两者之后、第 29 组文档统一同步之前提交。释放控制面与市场总览为新领域，建议各自单开组并在第 31 组之前落地（第 31 组的 `backend_release_suite.py` 原子性约束 2 依赖释放控制面的 5 个测试文件）。
