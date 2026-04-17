# Current Boundary Handoff (2026-04-10)

> Status update (2026-04-17): this handoff now reflects the adopted default interpretation for repo-wide `Phase 2` formal-compute cutover, with explicit exclusions for non-cutover consumers and surfaces.

## 目的

用一页文档对齐“当前代码状态”和“当前阶段边界”，避免把已落地薄切片、Phase 1 closeout、next-slice 计划、dated override 混为一谈。

## 当前边界结论

- 仓库默认边界已切换为 `repo-wide Phase 2（通用正式计算）`。
- 本次 cutover 只覆盖 formal-compute 主链：
  - formal balance
  - formal PnL
  - formal FX
  - formal yield curve
  - PnL bridge
  - risk tensor
  - 核心 bond analytics formal read surfaces
- `Phase 1 closeout` 仍作为历史收口解释保留，但只适用于未纳入本次 cutover 的骨架、预览、占位与治理收口面。
- `.omx/plans/` 中的 `next-slice`、`closeout`、`execution-plan` 文档是计划，不是自动执行授权。
- 历史 dated execution update 仍是命名工作流的 scoped override 记录，但不再否定 repo-wide formal-compute 主链的默认授权。
- 本次 cutover 明确不包含：
  - `executive.*` 中除 `executive-consumer cutover v1` 以外的其余路由
  - `executive-consumer cutover v1` 当前已纳入：
    - `/ui/home/overview`
    - `/ui/home/summary`
    - `/ui/pnl/attribution`
  - `executive-consumer cutover v1` 当前仍排除：
    - `/ui/risk/overview`
    - `/ui/home/alerts`
    - `/ui/home/contribution`
  - Agent MVP / `/api/agent/query` / `/agent`
  - `source_preview` / `macro-data` / `choice-news` / `market-data` 的 preview/vendor/analytical surface
  - `qdb_gl_monthly_analysis`、`liability_analytics_compat` 等 analytical-only / compatibility 模块
  - cube-query、broad frontend rollout、以及其他 `Phase 3 / Phase 4` 风格扩张项
- 当前排除面的公开行为应按“显式保留 / fail-closed”解释，而不是按“已晋升但缺数据”解释：
  - `/ui/risk/overview`、`/ui/home/alerts`、`/ui/home/contribution` 当前返回显式 `503`
  - `/api/cube/query` 与 `/api/cube/dimensions/*` 当前返回显式 `503 reserved surface`
  - `/api/risk/buckets`、`/api/analysis/yield_metrics`、`/api/analysis/liabilities/counterparty`、`/api/liabilities/monthly` 当前返回显式 `503 reserved surface`
  - 前端工作台当前将 `/risk-overview`、`/liability-analytics`、`/cube-query` 作为 placeholder / compat 入口，而不是 live primary navigation

## 当前代码状态

### 1. 基础底座

已落地：

- FastAPI 入口与主路由注册
- `frontend -> api -> services -> (repositories / core_finance / governance) -> storage` 主调用方向
- PostgreSQL / DuckDB / Redis / object store / worker 基础链路
- `result_meta` 基础契约
- 读写分离约束测试

当前判断：

- 属于 `Phase 1` 已完成主体

### 2. 驾驶舱与工作台壳层

已落地：

- 工作台主导航与壳层
- 驾驶舱 overview/summary/pnl/risk/contribution/alerts 薄接口
- 多个前端页面占位或半实装页面

当前判断：

- 仍按 `Phase 1 shell + preview + closeout` 解释
- 不自动等于 `Phase 4` 已开始
- `executive-consumer cutover v1` 现已纳入当前边界
- 其余 `executive.*` 路由仍不属于本次 repo-wide `Phase 2` cutover 范围
- 当前工作台导航已把 `/risk-overview` 从 live 主导航降回 placeholder 语义，避免把 excluded executive surface 误读为已晋升 governed page

### 3. Source Preview / Preview Closeout

已落地：

- source foundation summary
- history / rows / traces
- family / batch drilldown
- 对应前后端测试

当前判断：

- 属于 `Phase 1 preview closeout`
- 即使 `.omx/plans/phase1-preview-*` 存在，也只说明这是已计划 / 已执行的 closeout 面，不等于 preview surfaces 自动进入 repo-wide `Phase 2`
- **Contract sync（2026-04-12）：** `docs/BALANCE_ANALYSIS_SPEC_FOR_CODEX.md` §13 与 `tests/test_balance_analysis_workbook_contract.py` 已列出 **governed balance-analysis workbook** 当前宣称已支持的 section keys（`zqtz / tyw` formal 物化 + core_finance workbook + API + workbench 消费链）。在当前边界解释下，这些内容已属于 repo-wide `Phase 2` formal balance 主链，而不是仅 docs-only 状态。
- `docs/CURRENT_EXECUTION_UPDATE_2026-04-10.md` 与 `docs/CURRENT_EXECUTION_UPDATE_2026-04-11.md` 作为历史 scoped lane 记录保留，但不再代表 formal balance compute 仍需逐条单独授权。

### 4. Product Category PnL

已落地：

- 日期接口
- 详情页
- refresh / refresh-status
- manual adjustments
- 独立 audit 页面

当前判断：

- 这是已落地的业务薄切片 / start pack
- formal read path 可按 repo-wide `Phase 2` 主链解释
- scenario overlay、audit 扩张、以及更广义 workbench rollout 不因此自动进入 cutover

### 5. PnL API 与 core_finance start pack

已落地：

- `/api/pnl/dates`
- `/api/pnl/data`
- `/api/pnl/overview`
- `backend/app/core_finance/pnl.py` 中的标准化与桥接起步包

仍未放开：

- 更广义的 `Phase 3 / Phase 4` 扩张项
- 以此为依据继续扩其它无关 formal finance 工作流
- 不在 cutover 范围内的 analytical / consumer surface

当前判断：

- 现有 `/api/pnl/*` 与 `backend/app/core_finance/pnl.py` 属于 repo-wide `Phase 2` formal PnL 主链
- “start pack” 语义仍只约束已落地能力范围，不再作为“全仓未切换阶段”的证据

### 6. Macro-data stream

已落地：

- Choice-first macro thin slice
- live fetch / raw archival / vendor lineage / normalization / latest query surface

当前判断：

- macro-data 仍是历史 scoped override 工作流
- 它不属于本次 repo-wide `Phase 2` formal-compute cutover

### 7. Agent

已落地：

- `/api/agent/query` disabled stub
- `/agent` hidden route
- Agent placeholder page

仍未落地：

- 真实 Agent query
- Agent MVP / Phase 4A / 4B

当前判断：

- Agent 仍按 `Phase 1 Agent skeleton` 解释
- Agent 明确不在本次 repo-wide `Phase 2` cutover 范围内

### 8. Reserved compatibility / query surfaces

已落地：

- `cube_query_service`、`liability_analytics_compat` 等内部实现与测试资产仍保留
- 对应前端页面/客户端代码仍保留后续恢复入口

当前判断：

- 这些能力当前只保留“代码资产 / 后续恢复点”语义
- 公开 HTTP surface 当前按 reserved route 解释，并显式 `503 fail-closed`
- 不得把“实现仍在仓库中”误读为“当前已纳入 repo-wide Phase 2 governed rollout”

## 当前验证状态

截至本次 handoff：

- 后端 canonical gate：`python scripts/backend_release_suite.py` 当前结果为 `135 passed in 103.08s`
- 前端：`npm run typecheck` 通过
- 前端：`npm test` 通过

说明：

- frontend 通过不自动代表所有 consumer 已进入 cutover
- executive 当前边界应理解为“overview / summary / pnl-attribution 纳入，risk / alerts / contribution 继续排除”
- `python -m pytest -q` 仍可作为 broader diagnostic command 使用，但不再作为当前 release cutoff 的 canonical backend gate

## 执行判断规则

后续看到任一计划文件时，按以下顺序判断能否执行：

1. 该任务是否属于 repo-wide `Phase 2` 已纳入的 formal-compute 主链？
2. 如果不属于，是否属于本次 cutover 明确排除项？
3. 如果属于排除项，是否存在新的明确授权或后续阶段定义？
4. 如果仍不满足，停止，不得仅凭 `.omx/plans/*next-slice*` 名称继续推进。

## 建议后续动作

### 可直接继续

- repo-wide `Phase 2` 已纳入 formal-compute 主链内的文档、实现、验证、收口工作
- 未纳入 cutover 的历史 `Phase 1 closeout` 文档、验证、收口工作

### 不得自动继续

- 未纳入 `executive-consumer cutover v1` 的其余 `executive.*` governed rollout
- Agent MVP / Phase 4A / 4B
- preview/vendor/analytical-only surface 的无授权扩张
- 无关工作流的 next slice
- broad frontend rollout
