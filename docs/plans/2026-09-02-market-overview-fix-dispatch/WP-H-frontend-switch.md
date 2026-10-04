# WP-H · 前端切到 `market.snapshot`（方案 Phase 2）

- 泳道：L2 前端·市场页，第二批（**WP-I 合入后才可派**；WP-B、WP-D 已合入）
- 层：TS/TSX + vitest + Playwright + 契约文档
- 难度：高
- 设计：`docs/plans/2026-09-02-market-overview-module-compute-plan.md` §2.6、§3 Phase 2
- 闸门已过：WP-G 影子比对 8/8 一致（`scripts/shadow_compare_market_snapshot.py`，2026-09-02 15:21）

## 目标

`/market-overview` 的 01 分析观察、02 市场证据两区改为消费 `GET /ui/market-overview/snapshot`；03/04 区的组件读全部惰性；删除前端派生计算。切换后首屏后端读 ≤ 2 条、解压后 ≤ 200 KB，hero 与焦点解读展示同一段后端 `gate.human_reason` / `conclusion`。

## 开工前必核（10 分钟）

1. `curl "http://127.0.0.1:7888/ui/market-overview/snapshot"` 的 `crisis.status == "ok"`（WP-I 的效果；仍 `degraded` 就停下，不要在前端兜底）。
2. 读一遍 `backend/app/services/market_overview_service.py` 顶部常量与各 `_build_*` 的返回结构——这就是响应契约，前端类型照它写，不要凭方案文档臆测字段名。
3. `git status --short -- frontend/src/features/workbench/module-home/` 应只含 WP-B/WP-D 的改动，没有别的会话的未提交内容。

## 任务

### H1 · API client

- `frontend/src/api/marketDataClient.ts`：`MarketDataClientMethods` 增 `getMarketOverviewSnapshot(options?: { include?: string[] }) => Promise<ApiEnvelope<MarketOverviewSnapshotPayload>>`，路径 `/ui/market-overview/snapshot`，`include` 逗号拼接。类型 `MarketOverviewSnapshotPayload` 放 `frontend/src/api/contracts/marketMacro.ts`（与现有市场契约同处），按后端 `_build_*` 结构逐字段定义，所有分区带 `status` 字面量。
- `frontend/src/api/clientContext.ts`：方法要登记进正确的域集合——`getMarketDataRates` 在 `HOME_MARKET_TICKER_METHODS`（`:114-121`），新方法放同一集合或 `STOCK_ANALYSIS_MARKET_DATA_METHODS`（`:127`）之外新建一个 `MARKET_OVERVIEW_METHODS`，看 `frontend/src/test/ApiClientCompositionBoundary.test.ts` 的守卫怎么分组再决定；不要绕过守卫。
- `frontend/src/api/marketDataMockClient.ts`：mock fixture 用 2026-09-02 15:21 真实响应裁剪（`.tmp-agent/market-overview-audit/` 里没有留档，直接 `curl` 一份存到 `frontend/src/api/mocks/` 现有 fixture 目录，遵循那里的命名）；`gate.level` 给 `review`，`crisis.status` 给 `ok`，`tape` 8 槽全 `ok`，另留一个 `unresolved` 槽位的 fixture 变体给测试用。

### H2 · 查询层

`useMarketHomeQueries.ts`：新增 `snapshot` 查询（键 `["module-home","market-snapshot",client.mode]`，沿用 `MARKET_HOME_QUERY_OPTIONS`）；五条组件读加 `enabled` 参数，由 `MarketHomeLayout` 传入"03 区已进入视口"或"用户展开了 04 区某 tab"的布尔值（`IntersectionObserver` 已在 `MarketHomeLayout.tsx:76-110` 有一套，复用其章节观察结果，不要再挂一个观察器）。`MarketHomePage.tsx` 的刷新流程 `refetchAfterMarketRefresh` 列表加上 snapshot。

### H3 · 01/02 区渲染

`MarketOverviewDenseFirstScreen.tsx`：

- hero：`gate.level` 决定标题（`ok` → `conclusion.stance`；`review` → 标题为 stance、`observationAction` 前缀「需复核：」；`blocked` → 「暂停形成今日判断」），正文一律 `conclusion.summary` / `recommended_action` 原文，「使用边界」格显示 `gate.human_reason`，`recovery_action` 收进 title。`view.marketCrisisExplain` / `marketDeskIntel` 两个事实格改读 `crisis` 分区与 `tape`（曲线形态若 snapshot 未提供则暂保留旧来源，报告里注明）。
- 行情带：直接渲染 `tape.slots`，`unresolved` 槽位显示「未绑定」+ title 说明，不留空白；`basis` 打「正式/分析」角标；tone 仍由前端按 DESIGN §11 决议映射（利率上行=琥珀），只用后端 `tone_hint` 的方向。
- 指标变动表读 `pulse`，信号条读 `signals.cards` 并按 `kind` 分流（`ops_status` 进 01 区状态栏），核验队列读 `actions.items`，事件密度读 `news.density`（横轴标注 `tz`，脚注写明 `date_only_rows` 已排除），最新事件读 `news.latest`。
- 页头日期：`dates.tape_span.earliest–latest` 两端都显示，不再显示单一「行情日期」；`dates.surfaces` 里 `age_days ≥ 5` 的面在子页导航对应入口加「数据 N 天前」角标（`MarketHomeLayout.tsx` 的 `MARKET_SUBPAGES` 渲染处）。
- 焦点解读的「宏观工具」卡改读同一 `gate.conclusion`——这样 F1 的矛盾从根上消失。

### H4 · 03/04 区惰性

`MarketFinancialChartsWorkbench.tsx` 收到 `enabled=false` 的查询时渲染现有 `等待数据` 状态（`metaStatus(undefined)` 已有），不新增骨架。`MarketBackendDataWorkbench.tsx` 每个 tab 的读随 `activeKey` 启用（新闻 tab 已是此模式，照抄）。

### H5 · 删除

`marketOverviewDenseModel.ts` 的 `buildDenseTapeMetrics` / `buildDenseMacroPulseRows` / `buildDenseNewsDensity` / `buildDenseLedgerRows`（若无其它消费方）；`MarketOverviewDenseFirstScreen.tsx` 的 `buildMacroObservationGate` / `macroObservationState` / `OPS_SIGNAL_PATTERN`；`marketActionQueueModel.ts` 整文件；`marketDeskIntelModel.ts` 的 `crisisHistoryDelta`。每删一个先 `rg` 确认无第二消费方。保留全部纯格式化函数（`compactNumber`、`denseUnitSuffix`、`DENSE_UNIT_LABELS`、tone 映射）。

### H6 · 测试与契约

- `MarketOverviewDenseFirstScreen.test.tsx` 改为对 snapshot fixture 渲染断言：三种 `gate.level` 各一条；`unresolved` 槽位一条；hero 与焦点解读文本相等一条；`date_only_rows` 脚注一条。
- `ModuleWorkbenchHomePage.test.tsx` 的市场页用例：断言首屏只调用 `getMarketOverviewSnapshot` + `getMarketDataRates` + `getChoiceMacroLatest`（A–D 图仍需后两者），其余组件读在 03 区可见前未被调用。
- `market-overview-smoke.spec.mjs`：`DR007` / 6 张 dense chart / 5 张信号卡断言保持；新增 `#market-overview-judgment` 与 `#market-overview-focus` 内出现同一段 `conclusion.summary` 的断言。
- 契约：`docs/page_contracts.md` §14.6 C（数据链改 snapshot + 惰性组件读）、D（日期口径 per-surface）、E（新增 slot 注册表表格，标明 analytical、非 `MTR-*`，指向 `market_overview_service.py` 的 `MARKET_OVERVIEW_TAPE_SLOTS`）；`docs/metric_dictionary.md` §12.2 加一行指向；`docs/live_route_maturity.md` 的验证命令追加 `tests/test_market_overview_snapshot_api.py`。

## 不得触碰

后端任何文件；壳层行情条（Phase 3）；其他页的读；`DESIGN.md` 决议；`core_finance/`。

## 验收

```bash
cd frontend
npm run typecheck && npm run lint
npm run test -- ModuleWorkbenchHomePage MarketFinancialChartsWorkbench MarketBackendDataWorkbench \
  marketFinancialChartsModel marketOverviewDenseModel marketOverviewDenseLiquidityModel \
  MarketOverviewDenseFirstScreen LiveRouteReadiness ApiClientCompositionBoundary ApiClient
npx playwright test tests/playwright/market-overview-smoke.spec.mjs -c playwright.config.mjs
cd .. && python -m pytest tests/test_live_route_page_contract_completeness.py -q
```

数字（`.tmp-agent/market-overview-audit/timing.mjs`、`audit.mjs`、`hero-facts.mjs`，复制到 `frontend/.tmp-audit/` 执行）：首屏后端读 ≤ 3 条、`encodedBodySize` 合计 ≤ 80 KB；1440 视口 DOM 节点 < 3,000（04 区惰性后）；axe 不新增违规；`hero-facts` 的 `summary` 与 `focusMacro` 正文一致。

## 报告要求

按 H1–H6 逐条；整体风险至少写：切换是一次性的，没有 feature flag 双跑；`tape` 的 `unresolved` 在真实数据下是否出现（当前 8/8 解析成功）。对 `core_finance/` 的影响：无。
