# Executive Reserved Surfaces Decision Packet

日期：2026-07-06

范围：只锁定现状，不接通端点，不删除 service 实现，不改变前端消费行为，不生成任何投资建议性文案。

## 结论

待 owner 裁决：接通 / 删除 service 实现 / 维持保留。

当前 `GET /ui/risk/overview`、`GET /ui/home/contribution`、`GET /ui/home/alerts` 在路由层授权通过后直接返回 reserved `503`。对应 service 函数仍存在，并可从 DuckDB repository 读取最小可用数据。前端首页 Source Gate 和 cockpit 模型已把这些读面标注为 reserved，不进入首屏判断。

## 证据

- 路由现状：`backend/app/api/routes/executive.py:102`、`:111`、`:120` 分别注册三个 GET 端点；三者在 `:108`、`:117`、`:126` 调用 `_raise_executive_reserved_surface(...)`，detail 为 `Executive route <route_name> is reserved by the current boundary.`。
- Service 实现：`backend/app/services/executive_service.py:2292` 的 `executive_risk_overview` 读取 `BondAnalyticsRepository`；`:2431` 的 `executive_contribution` 读取 `ProductCategoryPnlRepository`；`:2455` 的 `executive_alerts` 读取 `BondAnalyticsRepository` 并调用 risk tensor / alert engine。
- 前端 endpoint client：`frontend/src/api/executiveClient.ts:506`、`:530`、`:536` 仍保留 `getRiskOverview`、`getContribution`、`getAlerts` 调用点。
- 前端 Source Gate：`frontend/src/features/workbench/dashboard-home/TerminalHomeFirstScreen.tsx:54` 把 `reserved` 行列入 Source Gate，`:145` 对 reserved 行返回不可用状态。
- 前端 cockpit：`frontend/src/features/workbench/dashboard/dashboardCockpitModel.ts:475` 的 `reservedSection` 将 `firstScreenAllowed` 置为 `false`，`:1272`-`:1274` 标注三个 executive reserved 面，`:1277`-`:1283` 将 reserved 排除出首屏。
- 前端结构覆盖：`frontend/src/features/workbench/dashboard-home/TerminalHomeWorkGrid.tsx:1426`-`:1430` 将 alerts、contribution、risk-overview 标注为 `reserved endpoint` / `503`。
- MCP/GitNexus：当前 Codex tool surface 未暴露 `gitnexus_*`、`moss-metric-contracts`、`moss-lineage-evidence` 或 `moss-data-catalog` 工具；本决策包使用本地代码、现有文档和新增 pytest 作为证据，不裁决指标定义或 owner 批准状态。

## Surface Inventory

| 读面 | 路由状态 | Service 状态 | DuckDB / 计算来源 | 前端消费点 | 打开工作量估计 |
| --- | --- | --- | --- | --- | --- |
| `/ui/risk/overview` | reserved `503`，route name `risk_overview` | 已实现 `executive_risk_overview` | `fact_formal_bond_analytics_daily` via `BondAnalyticsRepository.fetch_*risk_overview_snapshot` | `getRiskOverview`；cockpit `executive_risk_overview` reserved；结构覆盖 `risk-overview` 503 | M：接通路由、确认 result_meta/date/filter 契约、补 API/前端状态测试、移除 Source Gate reserved 标识 |
| `/ui/home/contribution` | reserved `503`，route name `contribution` | 已实现 `executive_contribution` | `product_category_pnl_formal_read_model` via `ProductCategoryPnlRepository.fetch_rows(view="monthly")` | `getContribution`；cockpit `executive_contribution` reserved；Source Gate `alerts / contribution` | M：接通路由、确认贡献口径/分组命名、补 API/前端状态测试、移除 reserved gate 文案 |
| `/ui/home/alerts` | reserved `503`，route name `alerts` | 已实现 `executive_alerts` | `fact_formal_bond_analytics_daily` -> `compute_portfolio_risk_tensor` -> `evaluate_alerts` | `getAlerts`；cockpit `executive_alerts` reserved；Source Gate `alerts / contribution` | M-L：接通路由、确认 alert rule owner/阈值治理、补 result_meta/空态/前端展示测试、移除 reserved gate 文案 |

## Owner 待裁决项

1. 接通：保留 service 实现，修改三条路由从 reserved `503` 切到已实现 service；同步更新 Source Gate、cockpit reserved 状态和端到端测试。
2. 删除 service 实现：若 owner 判定这些面不应成为当前业务系统读面，则删除未接通 service 和前端调用点，并同步 contract/docs，避免维护两套事实。
3. 维持保留：继续 fail-closed；保留 service 防腐测试，明确这些实现只是候选，不作为页面已接通证据。

## 当前锁定

- 新增后端 pytest 锁定三个 HTTP 端点返回 `503` 且 `detail` 结构稳定。
- 新增 service 最小 DuckDB 实读测试，分别覆盖 `executive_risk_overview`、`executive_contribution`、`executive_alerts`。
- 新增测试只证明当前契约和实现可运行，不改变用户可见行为。

回滚方式：revert 单 commit。
