# Stock Analysis Stage 4 — Evidence-first 模式向其它工作台页面扩展（B 方向）

## 0. 元信息

- **创建日期**：2026-05-08  
- **作者标识**：Stage 4 planning subagent  
- **关联 Stage 3 立项文档（如有）**：股票分析 Stage 1～3 实施与 `StockAnalysisPage`/`StockDetailDrawer` 现状（以代码为准）  
- **关联改造方案（背景）**：`c:\Users\arvin\.cursor\plans\stock_analysis_revamp_plan_d45b33b0.plan.md`  
- **关联代码 commit**：本会话依据的仓库快照 **HEAD：`1e9714a4`**

---

## 1. 背景与动机

- **Stage 1～3 已落地的程度（代码事实，概括）**  
  - **本日判断条 + token**：`frontend/src/features/stock-analysis/pages/StockAnalysisPage.tsx` 使用 `buildDailyJudgmentStrip`、`stockAnalysisPageCssVars`（`stockAnalysisTokens`），含日期选择与 stale 心智。  
  - **板块等多段证据**：同页 `useQuery` 拉 `getLivermoreSectorRankSeries`（`sector-rank-series-multi` 折叠区），并对 `sectorRankSeriesQuery` 的 loading/error/missing 分支显式渲染。  
  - **Drawer 诊断**：`boundaryDrawerOpen` + `Drawer` 展示口径（同一文件内 Collapse/Drawer 组合）。  
  - **个股 Drawer**：`StockDetailDrawer.tsx` 内 K 线、因子、`getLivermoreCandidateHistory`、`getChoiceNewsEvents` 分区，含入选历史说明文案。  
  - **Agent bridge**：`AgentPanel` + `buildStockAnalysisAgentPageContext`（import 于 `StockAnalysisPage.tsx`），`basis` 在 `AgentPanel.tsx` 中固定 `formal`（与业务 analytical 呈现需后续统一评审，此处仅记代码事实）。  
  - **Agent 契约**：`backend/app/agent/schemas/agent_request.py` 中 `page_context`；`context` 字段仍存在于 schema 与 `agent_service` 读取路径。  

- **为什么需要本项**  
  1. 其它「市场 / 研究 / 工具台」页面若缺少「结论优先 + 证据折叠 + 元数据条」，用户会在长表与多接口之间迷失，重复踩股票分析已修过的问题。  
  2. 复制**模式**而非复制 UI 皮肤，可在 `DESIGN.md` 约束下统一「先回答业务问题再展开证据」。  

- **不做的成本**  
  每页各自为政，stale/partial 状态不显眼；Agent 上下文难统一；评审与 onboarding 成本高。  

---

## 2. 业务目标与不做边界

### 必须做

- 从 `frontend/src/features/**/pages/*Page.tsx` 中选出 **3～5 个**高价值页面，逐页写明：**现状缺口** + **可复制的 evidence-first 片段**（对应股票分析：主结论条、inline meta、折叠证据、Drawer、Agent）。  
- 每页给 **复制策略**（复用 `PagePrimitives`、`PageStateSurface`、`AsyncSection`、`LiveResultMetaStrip` 等现有件，而非重写页面）。  
- 单独立项包保持可与股票分析并行，不要求一次改完全站。  

### 明确不做

- 不在本立项中直接批量改 25 个页面文件。  
- 不新增正式金融核心算法到 `frontend/`。  
- 不强行统一 `Agent` basis 字段（待与 agent 路由策略单独评审）。  

---

## 3. 后端能力差距清单（本方向以前端/产品为主）

| 能力 | 现状 | 缺口 | 工作量量级 |
|------|------|------|------------|
| 页面级 result_meta 暴露 | 多数页面已通过 client 拉到 envelope | 少数页面未把 meta 抬到首屏 | **S/Page** |
| Agent `page_context` | `AgentPanel` 已支持 props | 各页未接 `page_context` 的需补适配器 | **S/M per page** |
| 治理字段 | 各域不同 | B 方向页面需各自对齐 contracts | **M** 汇总 |

---

## 4. 数据契约草案 / 接口设计草案

- **模板化**：为每个目标页增加「页级 `WorkbenchEvidenceSummary`」TypeScript 类型（草案名），字段与 `ResultMeta` / `quality_flag` / `as_of_date` 对齐，放在 **领域 adapter 文件**（不扩张 `client.ts`）。  
- **路由**：无强制新 endpoint；若某页需轻量聚合，仍遵循 `/ui/<domain>/<path>`。  
- **监控**：可选在前端统一 `data-testid="page-meta-strip"` 以便 E2E（与 C 方向衔接）。  

---

## 5. 治理与合规风险

- 扩展 evidence 展示时，避免把 **analytical** 结果写成 formal 结论文案。  
- `macro-toolkit` 等页若暴露运行脚本能力，折叠区须保持「只读/显式触发」提示，与 `DESIGN.md` 语气一致。  
- News 相关页涉及 **choice_news.data** 权限，与 `choice_news.py` 一致，不在前端假设公开数据。  

---

## 6. 实施分解

> 以下为仓库 **真实存在** 的页面路径（glob：`frontend/src/features/**/pages/*Page.tsx`），从中挑出 **5** 个候选并给出策略。

1. **`frontend/src/features/macro-toolkit/pages/MacroToolkitPage.tsx`**  
   - **现状缺口**：已使用 `PageDecisionHero`、`PageStateSurface`、`DataStatusStrip`、`PageSectionLead`（文件头部 import），但信息结构偏「工具能力清单 + 运行表」，**缺少股票分析式「一句话主结论条」**（对应宏观/脚本的「本日判断」）。  
   - **复制策略**：增加顶部 **narrow judgment strip**（只读）：聚合最近一次 `MacroToolkitRunResponse` 的 `status` + 关键脚本 freshness；折叠区放完整 `PageOutput` 类证据；不改变脚本执行按钮位置。  
   - **验证**：`MacroToolkitPage` 现有测试 + visual debt audit。  

2. **`frontend/src/features/market-data/pages/MarketDataPage.tsx`**  
   - **现状缺口**：已有 `LiveResultMetaStrip`、`MacroLatestReadinessBanner`、`AsyncSection`、多 Collapse（宏观深度等），但区块多、**首屏主问题**依赖读者自行提炼。  
   - **复制策略**：在 `MarketDataHeroSection` 之上增加 **单句「市场可读性」结论**（仅展示客户端已有 KPI/闸门字段，不新算指标）；将 `livermore` / `macro` 的 `quality_flag` 并入一条 meta chip；复用股票页的「stale banner」交互模式。  
   - **验证**：`MarketData` 相关测试与手动回归表。  

3. **`frontend/src/features/news-events/NewsEventsPage.tsx`**  
   - **现状缺口**：大量 **inline style**（如 `#fbfcfe` 边框卡），`AsyncSection` + 列表；缺少 **统一 envelope meta 条**（`source_version` / 接收窗口）在首屏显著位置。  
   - **复制策略**：用 `DESIGN.md` token 替换硬编码壳子；顶部加 **证据条**（来自 `getChoiceNewsEvents` 返回的 `result_meta`）；列表行保留，细节进 Drawer（二次交互）。  
   - **验证**：新闻页若有 test 则增量；`npm run debt:audit`。  

4. **`frontend/src/features/cross-asset/pages/CrossAssetDriversPage.tsx`**（`CrossAssetPage.tsx` 仅 re-export 此页）  
   - **现状缺口**：页面体量大（多图表/矩阵），**认知负载高**；虽有 `PageHeader`、`KpiCard`、多种 `buildCrossAsset*` model，但没有股票分析那种 **折叠「口径与边界」** 的统一入口。  
   - **复制策略**：右侧或首屏下方增加 **「数据边界」Drawer**（复用 antd `Drawer` 模式与 `StockAnalysisPage` 的 `boundaryDrawerOpen` 交互）；把 `rule_version` / `as_of_date` 从子卡片提升到 strip；Agent 可接 `page_context` 传当前聚焦资产类别。  
   - **验证**：`CrossAssetPage.test.tsx` 与关键 model 测试。  

5. **`frontend/src/features/workbench/pages/DashboardPage.tsx`**  
   - **现状缺口**：综合驾驶舱，**模块多**；部分区块已有 `Dashboard*` 组件但与「单一主问题」页面哲学不同；证据散落在 `adaptDashboard` 之后。  
   - **复制策略**：不强改全页；在首屏 `DashboardOverviewHeroStrip` 周边增加 **只读质量摘要**（聚合已有 `ResultMeta` / `VerdictPayload`），折叠「各模块 lineage」链接到已有溯源入口；避免与债券分析 **争主视觉**（遵循 `DESIGN.md` 主结论优先级）。  
   - **验证**：`Dashboard` 相关测试 + 人工巡检关键卡片日期一致。  

### 统一前后端任务拆分（示例）

1. **前端模式库（薄层）**：从 `stock-analysis` 抽出可复用 **CSS 变量组**（不写代码，本立项仅建议命名：`workbenchEvidenceStrip`）→ **验证**：设计走查。  
2. **每页 0.5～1 轮迭代**：按上表 5 页次序落地 → **验证**：页级测试 + Playwright 可选。  

---

## 7. 验收清单

- [ ] 5 个候选页面均有书面「缺口 + 策略」并已获产品优先级确认（本文档为初稿输入）。  
- [ ] 至少 **2** 个页面在后续 sprint 落地 evidence-first 改造且通过测试。  
- [ ] 无新增 `client.ts` 体积告警；`debt:audit` 不比基线恶化（`AGENTS.md`）。  

---

## 8. 工作量评估与排期建议

- **后端**：**0～3 人日**（多数为前端；仅当某页需轻聚合 endpoint 时增量）  
- **前端**：每页约 **2～4 人日**；5 页滚动共 **10～20 人日**（含测试与 token 清理）  
- **整体**：**4～8 周**分波次（与 A/C 并行）  
- **是否需要 vendor / 外部审批**：**通常否**；触及 News 展示与权限时 **是**  

---

## 9. 依赖与前置

- **必须先完成**：`DESIGN.md` 走查确认主结论区与股票分析参考权重；股票分析页稳定为「参考实现」。  
- **可并行**：与各页所属业务 owner 排期；不阻塞 A 方向 P1。  
