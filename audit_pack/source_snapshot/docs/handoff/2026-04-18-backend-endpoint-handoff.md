# V1 → V3 前端阻塞端点 · 后端交付清单（2026-04-18）

> 来源：composer-2 子代理 readonly 勘查 V1（`D:\MOSS-SYSTEM-V1\backend`）+ V3（`F:\MOSS-V3\backend`）后产出。  
> 用途：把当前阻塞前端 wave-6 推进的 11 个端点，按「需要后端做什么」分组，便于排期。  
> 复核请重点关注 §5「风险与未决」与 §6「附录」中标 **需后端工程师确认** 的项。

## 0. 摘要

- 11 个阻塞端点中：A 组（前端独立完成）**0** 个，B 组（后端小改）**2** 个，C 组（后端大改）**9** 个（其中条目 5 计为 1 项但覆盖 2 条 V1 路径；条目 7 计为 1 项但覆盖多组宏观子模块）。
- 推荐先做：**1、2、10、9**（P0：驾驶舱 KPI 带 / 余额变动 + 债券驾驶舱加权表 + 授信集中度契约对齐），随后 **5、6、8、11**（P1：损益主数据 / 流动性缺口专表 / 风险三桶 / 债券月统计），最后 **3、4、7**（P2：FX 历史 / 中美利差 / 宏观深度 Tab 全量 HTTP 面）。
- 已知风险：V3 若干「兼容占位」路由固定 **503**（`liability_analytics.py`），与真实落地治理批次强耦合；新建端点若走 V3 正式栈，**Numeric** 与 `result_meta`/lineage 需与现有 `formal_result_envelope` 模式对齐。

## 1. A 组：后端已就绪，仅需暴露到 client.ts（0 个）

| # | V1 端点 | V3 现有路由 | V3 现有 service | 需要前端做的事 | 估计前端工时 | 优先级 |
|---|----------|-------------|-----------------|----------------|-------------|--------|
| — | — | **未发现**可同时满足「路由已挂载 + 业务实现完整 + 契约等同 V1 下列 11 项」的条目 | — | — | — | — |

## 2. B 组：后端小改（2 个）

| # | V1 端点 | V3 现状 | 需要后端做什么（具体到文件/函数/契约改动） | 估计后端工时 | 是否需要 Numeric 改造 | 优先级 |
|---|----------|---------|---------------------------------------------|-------------|----------------------|--------|
| 8 | `/api/risk/buckets` | 路由：`backend/app/api/routes/liability_analytics.py` → `liability_risk_buckets`；实现仅调用 `_raise_liability_analytics_not_promoted`（永远 503），**未见**与 V1 `risk_analysis_service.get_risk_buckets_response` 等价的正式 wired service | 其一：将 `_raise_…` 替换为真实编排并在新或既有 service（建议新建 `risk_buckets_service` 或并入 `bond_dashboard_service`/`risk_tensor_service`）中返回 V1 形 `bonds_cashflow_buckets`/`bonds_duration_buckets`/`bonds_rate_buckets` + 负债桶；其二：或从治理路线图明确下线该兼容路由并改用已存在读模型（需产品裁定） | **M** | 新端点/统一响应若走执行层信封，金额字段建议 **Numeric**（对齐 `schemas/risk_tensor.py` 等既有范式） | **P1** |
| 9 | 表内写法：`/api/analytics/bonds/counterparty`（**V1 仓库未发现**该路径；`bonds_analytics.py` 仅有 `/overview`、`/business_type_metrics` 等） | 授信集中度相关能力在 V1 主要由 `/api/bonds/monthly` 内嵌字段 + 逻辑在 `app/services/bonds_service.py`（如 `_calculate_counterparty_distribution`）；V3 已有 **`GET /api/positions/counterparty/bonds`**：`backend/app/api/routes/positions.py` → `counterparty_bonds` → `positions_service.counterparty_bonds_envelope` → `positions_repo.aggregate_counterparty_bonds`，响应模型 `schemas/positions.py` → `CounterpartyStatsResponse` | 若前端强依赖 V1「月频 CR10 / Top10 单包」：在 `CounterpartyStatsResponse` / `aggregate_counterparty_bonds` 增字段（如 `cr10_ratio`）或新增薄封装路由；若可改用区间截面：仅需文档对齐 + **前端**改调用参数（本条不写「仅前端」因契约可能不足以覆盖 CR10） | **S–M** | 当前 schema 多为 **display `str`**；若统一 Numeric，改 `schemas/positions.py` + 服务组装层 | **P0**（按任务给定映射） |

## 3. C 组：后端大改（9 个）

| # | V1 端点 | V1 契约形状（关键字段） | V3 应建在哪个 service 模块 | 数据来源（事实表/物化视图/外部 API） | 是否需要新数据源 | 估计后端工时 | 优先级 |
|---|----------|------------------------|---------------------------|----------------------------------------|------------------|-------------|--------|
| 1 | `/api/dashboard/core_metrics` | `CoreMetricsResponse`：`report_date`、`bond_investments` / `interbank_assets` / `interbank_liabilities`（`CoreMetricsCardData`：`total_amount`、`weighted_avg_rate`、`change_amount`、`change_pct`、`top_3_details`）；路由 `dashboard.py` → `get_core_metrics`；service `dashboard_service.py` → `get_core_metrics_payload` | 建议：`executive_service.py` 扩展 snapshot 切片，或新建 `dashboard_compat_service` + `api/routes/dashboard_compat.py`（前缀需与现网统一） | V1 同源：`PositionBonds` / `PositionInterbank` + `get_comparison_dates` 口径 + `db_market` 市场字段 | 否（治理库已有快照/债券事实则可复用）；**需后端工程师确认** DuckDB / 正式表是否已具备同等派生 | **L** | **P0** |
| 2 | `/api/dashboard/daily-changes-v2` | 路由 `dashboard.py` → `get_daily_changes_v2_endpoint`；`daily_change_service_v2.py` → `get_daily_changes_v2` 返回 dict（周期 `day` / `week` / `month`） | 同上或与 `balance_analysis` / `positions` 日变衔接的新 `daily_change_service` 模块 | V1：逐日 `PositionBonds` 等对比逻辑 | 否为主；**需确认** V3 是否已有可映射的日切持仓事实 | **L** | **P0** |
| 3 | `/api/dashboard/exchange-rates/monthly` | 路由 `dashboard.py` → `get_exchange_rates_monthly`；返回 `{"data": [...]}`；`exchange_rate_service.py` → `get_month_end_exchange_rates` | 建议：`api/routes/macro_vendor.py` 旁新建市场 FX 只读路由，或 `source_preview` / `market` 类 read API | V1：`market_db` 月结汇率表（端点注释：`exchange_rate_monthly`） | **需确认** V3 market / Choice 落库是否已有对等月序表 | **M** | **P2** |
| 4 | `/api/dashboard/cn-us-treasury-yield` | 路由 `dashboard.py` → `get_cn_us_treasury_yield`；参数 `days`、`granularity`；读 `MarketDataDaily` | 建议：小型 `market_curve_service` + `/api/market/cn-us-treasury`（示例名，实施时与路由注册表对齐） | `MarketDataDaily`（中 / 美 10Y 及利差聚合） | 否（若有同步市场日库）；否则 **需外部 API / ETL** | **M** | **P2** |
| 5 | `/api/pnl/by-business` + `/api/pnl/yearly-summary` | 路由 `pnl_by_business.py` → `pnl_by_business`（`PnLByBusinessResponse`）、`pnl_yearly_summary`（`YearlyBusinessSummaryResponse`）；service `pnl_by_business_service.py` → `query_by_business`、`query_yearly_summary`；缓存 `warehouse.stores.pnl_cache` | 优先对齐 **`product_category_pnl_service.py`** 是否已覆盖「按业务种类 + 年序列」；否则新 `pnl_by_business_compat_service` 挂载到 `api/routes/pnl.py` 同源前缀下 | V1：`pnl_records` + warehouse 版本；V3：`PnlRepository` / product-category 物化事实 | **需确认** product-category 事实能否无损表达 V1 KPI | **L** | **P1** |
| 6 | `/api/analysis/liquidity_gap` | 路由 `analysis.py` → `get_liquidity_gap` → `analysis_service.py` → `get_liquidity_gap_response`（桶序列 `buckets`、累计缺口等 dict 形态） | V3 **无**该 HTTP 面；逻辑可参考 `core_finance/risk_tensor.py` 中 `_compute_liquidity_gaps` 但与 V1「按期限桶现金流表」**不等价** → 新 `liquidity_gap_service` + `api/routes/analysis_compat.py` 或并入 balance 分析 | V1：持仓现金流桶 + 负债桶混算；V3 另有张量字段 `liquidity_gap_30d` 等（不同语义） | **需确认** 是否复用张量或重建 V1 桶口径 | **L** | **P1** |
| 7 | `/api/macro/monetary-policy-stance` 及 M10–M14 / M16 等 | 路由 `macro.py`（prefix `/api/macro`）；service `macro_analysis/*` + `macro_decision_summary_service.build_macro_decision_summary`；列举端点含 `monetary-policy-stance`、`leading-indicator`、`macro-portfolio-impact`、`economic-cycle` 等（以 V1 `macro.py` 清单为准） | V3 **`backend/app/api/routes` 下未发现** `/api/macro/*`；纯函数已迁至 `backend/app/core_finance/macro/`（如 `monetary_policy_stance.py`、`leading_indicator.py`、`economic_cycle.py`、`credit_spread_percentile.py` 等）→ 需 **`macro_routes_service` + 新 `api/routes/macro.py`（或拆分模块）** 将纯函数封装为 HTTP + 信封 | V1：`macro_data_service.fetch_macro_data` + `market_db` / `WIND`；V3：已有 Choice / Wind 管线处复用（见 `macro_vendor.py`、`macro_bond_linkage_service.py`） | **高概率** 需统一 vendor 快照 / 序列存储以供 M 系列 | **L（每子端点可视作 M，整条线 XL）** | **P2** |
| 9 | 见 B 组：若判定不能靠 positions 满足 | V1 侧真实「CR10」紧贴 `BondsMonthlyResponse.counterparty_top10` 等（`schemas/bonds.py`） | `bonds_monthly_compat_service`（从 `bonds_service.py` 逻辑移植 / 重写）挂 `/api/bonds/monthly` | `PositionBonds` 日月聚合（V1 `calculate_bonds_monthly_stats`） | **需确认** V3 DuckDB 是否已有月聚合缓存键等价物 | **L**（若坚持 V1 单端打包） | **P0** |
| 10 | `/api/analytics/bonds/business_type_metrics`（V1 prefix `/api/analytics/bonds`） | 路由 `bonds_analytics.py` → `get_bonds_business_type_metrics`；返回 `{"report_date","items":[{"name","market_value","weighted_avg_ytm_pct","weighted_avg_duration","duration_source"}]}`；内部用 `position_bonds_bond_level.load_bond_collapsed_for_business_metrics` 等 | 建议挂载在 **`bond_dashboard_service.py`** 或 **`bond_analytics_service.py`**，新路由如 `/api/bond-dashboard/business-type-metrics`（最终以路由注册为准） | 正式债券持仓事实（与现有 bond-dashboard 同源） | 否 | **M** | **P0** |
| 11 | `/api/bonds/monthly` | 路由 `bonds.py` → `get_bonds_monthly_stats` / `get_bonds_monthly_stats_no_cache`；`BondsMonthlyResponse`（`schemas/bonds.py`：月度汇总 + `maturity_buckets` / `cashflow_buckets` / `duration_buckets` / `rate_buckets` / `counterparty_top10` / `business_type_metrics` 等）；service `bonds_service.py` → `calculate_bonds_monthly_stats_cached` / `calculate_bonds_monthly_stats` | 新建 **`bonds_monthly_service`**（或并入 `bond_dashboard` 若拆多 RPC）+ `api/routes/bonds.py` 注册 | V1：DuckDB `positions_cache` + 日持仓滚动聚合 | **需确认** V3 物化与缓存键策略 | **L** | **P1** |

> 注：条目 9 在表中于 B/C 边际：若团队接受 **`/api/positions/counterparty/bonds`** 为权威来源并补齐 CR10 等字段，则整体降为 **B**；若必须坚持 V1 **`BondsMonthlyResponse`** 单包，则按上表 **C** 行实施 `GET /api/bonds/monthly`。

## 4. 实施建议

### 阶段 X1（A 组冲刺，前端独立做）
- 端点编号: **无**（当前检视下无「后端已全量就绪、仅差 client」项）
- 预估工时: **0 pd**

### 阶段 X2（后端小改并行）
- 端点编号: **8、9**
- 预估工时: **约 0.5–1.5 人周**（8 为中等接线；9 视是否仅补 `cr10` / `Numeric` 字段为小到中）

### 阶段 X3（后端大改，需要规划）
- 端点编号: **1、2、3、4、5、6、7、10、11**（及 9 的「全量月度包」变体）
- 前置条件: 治理数据面版本冻结；市场库 / 宏观 vendor 可用；与 `numeric_from_raw` / `build_result_envelope` 规范对齐的设计评审

## 5. 风险与未决

- **V1 路径勘误**：`/api/analytics/bonds/counterparty` 在 `D:\MOSS-SYSTEM-V1\backend\app\api\endpoints\bonds_analytics.py` 中 **未发现**；CR10 / 集中度请以 **`/api/bonds/monthly`** 或 V1 **`/api/positions/counterparty/bonds`**（若 V1 亦有）为准，需求和契约需再对齐。
- **503 占位面**：`liability_analytics.py` 中 `/api/risk/buckets`、`/api/analysis/liabilities/counterparty`、`/api/liabilities/monthly` 等为 **显式未提升**，与条目 8 / 其他负债能力耦合。
- **`/ui/home/snapshot`**（`executive_service.home_snapshot_envelope` + `schemas/executive_dashboard.py` → `HomeSnapshotPayload`）**是否**意图替代 1/2 部分驾驶舱数据：**未见**包含 core_metrics / daily_changes / fx / treasury 字段；若产品指望 snapshot 一次带回，需另增 schema 切片（属 **C**）。

## 6. 附录：探索元信息

- **V1 已 grep / 抽查文件**：`api/endpoints/dashboard.py`、`api/endpoints/pnl_by_business.py`、`api/endpoints/analysis.py`、`api/endpoints/macro.py`、`api/endpoints/risk.py`、`api/endpoints/bonds_analytics.py`、`api/endpoints/bonds.py`；service 命中含 `dashboard_service.py`、`daily_change_service_v2.py`、`exchange_rate_service.py`、`pnl_by_business_service.py`、`analysis_service.py`、`risk_analysis_service.py`、`bonds_service.py` 等（未整文件通读，仅路径与行号定位）。
- **V3 已 grep / 抽查文件**：`api/routes/executive.py`、`services/executive_service.py`（头部 + `home_snapshot_envelope` 段）、`api/routes/pnl.py`、`services/pnl_service.py` 头部、`api/routes/bond_dashboard.py`、`api/routes/bond_analytics.py`、`api/routes/positions.py`、`services/positions_service.py`（`counterparty_bonds_envelope`）、`api/routes/liability_analytics.py`、`api/routes/macro_bond_linkage.py`、`schemas/executive_dashboard.py`、`schemas/positions.py`；`core_finance/macro/` 下模块名 grep；**未发现** `api/routes` 下 `dashboard`、`/api/macro/`（除 `macro-bond-linkage` / `macro_vendor` UI 前缀）、`/api/dashboard/*`、`/api/bonds/monthly`、`/api/analysis/liquidity_gap` 的等价挂载。
- **Numeric 管线线索**：`schemas/executive_dashboard.py`、`schemas/bond_analytics.py`、`schemas/risk_tensor.py` 等已用 **`Numeric` / `numeric_from_raw`**；新建公开 JSON API 时建议统一，但 **positions 授信** 仍为 **字符串金额**，属技术债点。
- 元信息行：约 **V1 核心 7 个端点文件 + 若干 service 命中**；**V3 约 14 个 routes / service / schema 文件**（含重复 grep），未列全的文件标为 **需后端工程师确认**。
