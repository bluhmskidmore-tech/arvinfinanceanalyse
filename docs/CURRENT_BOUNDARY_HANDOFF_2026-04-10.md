# Current Boundary Handoff (2026-04-10)

## 目的

用一页文档对齐“当前代码状态”和“当前阶段边界”，避免把已落地薄切片、Phase 1 closeout、next-slice 计划、dated override 混为一谈。

## 当前边界结论

- 仓库默认边界仍是 `Phase 1`。
- `Phase 1 closeout` 仍算 `Phase 1`。
- `.omx/plans/` 中的 `next-slice`、`closeout`、`execution-plan` 文档是计划，不是自动执行授权。
- 当前唯一明确有效的 scoped override 是 `docs/CURRENT_EXECUTION_UPDATE_2026-04-09.md`。
- 该 override 仅适用于 macro-data stream，不代表仓库整体进入 `Phase 2`。

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

### 3. Source Preview / Preview Closeout

已落地：

- source foundation summary
- history / rows / traces
- family / batch drilldown
- 对应前后端测试

当前判断：

- 属于 `Phase 1 preview closeout`
- 即使 `.omx/plans/phase1-preview-*` 存在，也只说明这是已计划 / 已执行的 closeout 面，不等于进入 `Phase 2`
- `zqtz / tyw` 当前仅允许 docs-only 的 contract alignment / PRD / test-spec 收敛；这不构成 snapshot materialization、formal compute 或 workbench 消费授权。

### 4. Product Category PnL

已落地：

- 日期接口
- 详情页
- refresh / refresh-status
- manual adjustments
- 独立 audit 页面

当前判断：

- 这是已落地的业务薄切片 / start pack
- 不自动代表 formal finance 全域已进入 `Phase 2`
- 必须按“局部已落地、全仓未切换阶段”解释

### 5. PnL API 与 core_finance start pack

已落地：

- `/api/pnl/dates`
- `/api/pnl/data`
- `/api/pnl/overview`
- `backend/app/core_finance/pnl.py` 中的标准化与桥接起步包

仍未放开：

- 通用正式计算全量交付
- 全域 `Phase 2` cutover
- 以此为依据继续扩其它无关 formal finance 工作流

当前判断：

- 属于 `Phase 2 start pack already present in codebase`
- 不是“阶段授权已经切换”的证据

### 6. Macro-data stream

已落地：

- Choice-first macro thin slice
- live fetch / raw archival / vendor lineage / normalization / latest query surface

当前判断：

- 这是唯一被 dated execution update 明确 lifted stop line 的工作流
- 只能按 scoped override 解释

### 7. Agent

已落地：

- `/api/agent/query` disabled stub
- `/agent` hidden route
- Agent placeholder page

仍未落地：

- 真实 Agent query
- Agent MVP / Phase 4A / 4B

当前判断：

- 仍按 `Phase 1 Agent skeleton` 解释

## 当前验证状态

截至本次 handoff：

- 后端：`pytest tests -q` 通过
- 前端：`npm run typecheck` 通过
- 前端：`npm test` 通过

说明：

- 通过不代表仓库整体进入 `Phase 2`
- 只代表当前已落地代码与当前测试基线一致

## 执行判断规则

后续看到任一计划文件时，按以下顺序判断能否执行：

1. 是否仍在 `Phase 1` 或 `Phase 1 closeout` 边界内？
2. 如果不在，是否存在 dated execution update 明确授权该工作流？
3. 如果仍不满足，停止，不得仅凭 `.omx/plans/*next-slice*` 名称继续推进。

## 建议后续动作

### 可直接继续

- `Phase 1 closeout` 范围内的文档、验证、收口工作
- macro-data stream 范围内、且符合 `2026-04-09` override 的工作

### 不得自动继续

- 通用 `Phase 2` 正式金融扩张
- Agent MVP / Phase 4A / 4B
- 无关工作流的 next slice
- broad frontend rollout
