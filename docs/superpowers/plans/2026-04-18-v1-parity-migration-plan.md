# MOSS-V1 → MOSS-V3 前端对齐迁移计划（2026-04-18）

**依据**：`docs/superpowers/specs/2026-04-18-v1-v3-parity-matrix.md`；已有 `docs/superpowers/plans/composer/wave-{1..5}/*.md` 数值与契约工作不在本计划重复展开。

---

## 批次 0 — 零成本对齐（路由别名 / 标题 / readiness 标签修正等）

| 任务 | V1 参照 | V3 文件 | 动作 | 规模 |
|------|---------|---------|------|------|
| 落盘 Gap 矩阵 | `moduleRegistry.tsx` | `docs/superpowers/specs/2026-04-18-v1-v3-parity-matrix.md` | 新建矩阵表与统计 | XS |
| 落盘本迁移计划 | 矩阵 | `docs/superpowers/plans/2026-04-18-v1-parity-migration-plan.md` | 新建批次 1–4 与批次 0 清单 | XS |
| 决策事项导航与路由一致 | V1 无独立聚合页 | `frontend/src/mocks/navigation.ts` | `decision-items`：`readiness` 改为 `placeholder`，`readinessLabel`/`readinessNote` 改为「保留入口」语义 | XS |
| 报表中心导航与路由一致 | V1 分散导出 | `frontend/src/mocks/navigation.ts` | `reports-center`：同上改为 `placeholder` | XS |
| V1 书签 `/market` | `/market` | `frontend/src/router/routes.tsx`、`frontend/src/mocks/navigation.ts` | 在 `WorkbenchShell` 子路由增加 `<Navigate to="/market-data" replace />`；`workbenchPathAliases` 增加 `"/market"` | XS |
| V1 书签 `/assets` | `/assets`（=BondAnalytics） | 同上 | `<Navigate to="/bond-dashboard" replace />`；别名 `"/assets"` | XS |
| ADB 页说明对齐中文读者 | `/adb` | `frontend/src/mocks/navigation.ts` | `average-balance` 的 `description` 改为简短中文职责说明 | XS |
| 债券总览文案点出 V1 `/bonds` | `/bonds` | `frontend/src/mocks/navigation.ts` | `bond-dashboard` 的 `description` 增加「承接 V1 /bonds 书签」一句 | XS |
| 多维查询标签收敛 | — | `frontend/src/mocks/navigation.ts` | `cube-query` 的 `readinessLabel`/`readinessNote` 缩短为可读中文短语（不改路由逻辑） | XS |
| 导航单测补强 | — | `frontend/src/test/navigation.test.ts` | 断言 `decision-items`、`reports-center` 仅在 `secondaryWorkbenchNavigation` | XS |
| 路由单测补强 | — | `frontend/src/test/RouteRegistry.test.tsx` | 各新增 1 条：`/market`、`/assets` 入口渲染目标页关键 testid | XS |

**批次 0 条数**：**11**（含 2 个文档文件）。

---

## 批次 1 — V3 已有数据链路但缺 UI 模块（优先级 P0）

| 任务 | V1 参照 | V3 文件 | 动作 | 规模 |
|------|---------|---------|------|------|
| 驾驶舱模块 parity | `pages/Dashboard.tsx` | `frontend/src/features/executive-dashboard/**`、`DashboardPage.tsx` | 按矩阵缺口对照 V1 模块列表，在 OverviewSection/后续 section 增量挂载图表与跳转（仅用 `Numeric`/adapter） | L |
| 债券组合单页体验对齐 | `BondAnalytics.tsx` | `frontend/src/features/bond-dashboard/**`、`bond-analytics/**` | 在 bond-dashboard 补齐 V1 级「总览+分布+重仓」叙事或提供「经典视图」切换 | L |
| 负债结构全量模块 | `LiabilityAnalytics.tsx` | `frontend/src/features/liability-analytics/**` | 移除「仅 compat」占位主导：接入 wave-5 计划中的 governed 读模型与图表 | L |
| 业务线损益 vs Ledger | `PnLByBusiness.tsx` | `frontend/src/features/ledger-pnl/**` | 增加「业务线」维度视图或双模式切换，对齐 `/api/pnl/by-business` 与 yearly-summary | M |
| 损益明细与收益管理壳 | `YieldAnalysis.tsx` `/pnl` | `frontend/src/features/pnl/**`、路由 | 明确「收益管理」Tab 或子路由，复用现有 PnL 查询与 yield KPI 端点（若后端已有） | M |
| 宏观深度 Tab | `MacroAnalysis.tsx` | `frontend/src/features/market-data/**` 或新 `macro-analysis` feature | 将 M7–M16 模块按 V1 Tab 迁入市场数据或独立子路由，接现有 `/api/macro/*` | L |
| 流动性缺口专页 | `LiquidityGap.tsx` | 新路由 `liquidity-gap` 或扩展 `CashflowProjectionPage` | 调用 V1 同源 `GET /api/analysis/liquidity_gap`（若 V3 后端已暴露）并做 Numeric 适配 | M |

---

## 批次 2 — V3 完全缺失但后端有端点

| 任务 | V1 参照 | V3 文件 | 动作 | 规模 |
|------|---------|---------|------|------|
| 全局对账 | `features/reconciliation` | 新建 `frontend/src/features/reconciliation/**`、注册 `routes.tsx` 与 `navigation.ts` | 从 V1 复制特性目录结构并改为 `ApiClient` + contracts 类型生成 | L |
| 风险告警规则引擎 | `RiskAlerts.tsx` | 新建 `frontend/src/features/risk-alerts/**` | 接 V1 所用 alerts/rules REST；列表+对话框 CRUD | L |

---

## 批次 3 — V3 缺且后端也缺（需要先找后端）

| 任务 | V1 参照 | V3 文件 | 动作 | 规模 |
|------|---------|---------|------|------|
| 财务分析组合页 | `FinancialAnalysis.tsx` | 待定 feature 目录 | 与后端确认是否合并到 executive 或 cube；再实现页面骨架 | L |
| 比较分析 | `ComparativeAnalysis.tsx` | 同上 | 需要趋势/对比专用 API 或物化视图 | L |
| 管理报告 | `ManagementReportView` | 同上 | 依赖模板与导出流水线设计 | M |

---

## 批次 4 — 宏观驾驶舱等新页面（需要 UI 设计）

| 任务 | V1 参照 | V3 文件 | 动作 | 规模 |
|------|---------|---------|------|------|
| V1 风格「宏观驾驶舱」独立页 | `MacroAnalysis` Tab 集合 | 新页面 + 设计稿 | 信息架构与 Tab 视觉统一后再开发 | L |
| Agent 投研报告 | `Agent.tsx` | `AgentWorkbenchPage.tsx` 等 | 产品/安全评审后恢复 LLM 报告流与历史库 | L |

**批次计数汇总**：批次 0：**11**；批次 1：**7**；批次 2：**2**；批次 3：**3**；批次 4：**2**。

---

## 下一执行者注意

- 批次 0 实施前若工作区有本地修改，先 `git stash` 或提交，避免与 `navigation.ts` / `routes.tsx` 冲突。
- 禁止修改 `frontend/src/api/contracts.ts`、`client.ts`、数值 `numeric`/`format` 核心文件；对齐以 adapter 与 UI 为主。
- 用户已添加之 V1 重定向（`/macro-analysis` 等）保持不动；新增别名与矩阵保持一致即可。
