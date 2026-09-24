# 宏观策略研究 P0 证据审计（2026-07-19）

- 关联合同：`docs/strategy_contracts/macro_strategy_research.md` §9（P0 待证据冻结项）
- 性质：**只读证据采集**。本文件不冻结 owner、`minimum_history`、stale SLA 或 admission 阈值等业务真值；这些仍需业务 owner 确认。
- 证据方法与残余风险：本轮 `moss-metric-contracts` / `moss-data-catalog`（加载中）与 `moss-lineage-evidence` / `gitnexus`（连接失败）MCP 均不可用。改用等价的本地只读 DuckDB 审计（`information_schema` + 逐表 count/min/max 日期，库文件 `data/moss.duckdb`，与 `moss-data-catalog` 的查询边界一致）。残余风险：未经 MCP 服务器口径复核；后续 MCP 可用时应复跑核对。

## 1. 硬结论：PIT / vintage 完整率为 0

被审计的全部 8 张系统源表（`fact_choice_macro_daily`、`choice_market_snapshot`、`std_external_macro_daily`、`fact_commodity_futures_daily`、`fx_daily_mid`、`fact_formal_yield_curve_daily`、`choice_stock_daily_observation`、`fact_cffex_member_rank_daily`）**均不存在** `release_at` / `available_at` / `vintage` / `revision` / `publish_time` 任何一列。

按合同 §8 的 fail-closed 规则，这直接冻结以下证据结论：

- 任何声称"历史时点可复现"的结果（事件意外、修订敏感回归、历史宏观回测）当前**必须 fail closed**：不得输出 `ready`，不得进入 backtest/admission。
- 当前数据面**只能支持"当前观察"模式**，最多标 `degraded` 并注明 PIT 缺口。
- V2 候选中依赖可靠发布时点的策略（事件意外、跨国宏观）在 PIT 列落地前**没有准入路径**。

## 2. 各输入族可用历史深度（约束 minimum_history 的上限）

审计日 2026-07-19，按合同策略家族映射：

| 输入族 | 来源表/序列 | 历史深度 | 最新日期 | 对策略的含义 |
| --- | --- | --- | --- | --- |
| A 股日行情 | `choice_stock_daily_observation`（318 万行） | 2024-01-02 起（约 2.5 年） | 2026-07-14 | 趋势/横截面/踩踏风险可用；要求 >2.5 年历史的回测不可行 |
| 沪深300/中证500 | `CA.CSI300` / `CA.CSI500`（各 732 行） | 2023-07-04 起（约 3 年） | 2026-07-10 | 指数级趋势/动量可用 |
| 商品（铜/铝/布油/钢） | `CA.COPPER` 等（各约 119 行） | **2026-01-12 起（约 6 个月）** | 2026-07-10 | CTA Trend / Merrill Clock 商品腿历史极薄 |
| 债券期货 | `fact_commodity_futures_daily`（11043 行） | 2024-01-02 起 | **2026-06-26（滞后 23 天）** | 基差/IRR 可算但当前 stale |
| 资金利率 DR007 | `CA.DR007`（249 行） | 2025-07-10 起（1 年） | 2026-07-10 | 流动性/利率状态可用，历史仅 1 年 |
| NCD/SHIBOR | `NCD.SHIBOR.*`（各 **9 行**） | 2026-06-30 起 | 2026-07-10 | **任何依赖 NCD 历史的信号今天都是 `insufficient_history`** |
| 国债收益率（Choice） | `EMM00166466`（10Y，122 行）；其余期限 **各 1 行快照** | 10Y 自 2026-01-12；其余无历史 | 2026-07-07/10 | 曲线形态/利率拐点只有 10Y 有短历史；完整曲线历史需走 `tushare.yc_cb` / `fact_formal_yield_curve_daily` |
| 信用收益率（Choice） | `EMM001666xx` **各 1 行快照** | 无历史 | 2026-07-07 | 信用利差分位数在 Choice 源上不可算；`tushare.yc_cb.1001.CB.5Y` 有 286 行（至 2026-04-30，stale） |
| CPI/PPI/M2/GDP | `std_external_macro_daily`（tushare/nbs） | 1951/1978 年起，月频/季频 | 2026-06-01 / 2026-06-30 | 经济周期/领先指标历史深度充足，但**无 vintage**（见 §1） |
| 中金所席位 | `fact_cffex_member_rank_daily`（15731 行） | 2023-03-30 起 | **2026-06-26（滞后 23 天）** | 拥挤度可算但当前 stale |

大量 `EMM*` 序列（约 80 个）只有 1 行快照——它们能支撑"最新值"展示，**不能支撑任何需要历史窗口的信号**。为这些序列登记 `minimum_history` 前必须先解决历史回补。

## 3. 新鲜度实测（约束 stale SLA 的现状基线）

| 表 | 最新日期 | 距审计日滞后 |
| --- | --- | --- |
| `choice_stock_daily_observation` | 2026-07-14 | 5 天 |
| `fact_choice_macro_daily` | 2026-07-10 | 9 天 |
| `std_external_macro_daily` | 2026-06-30 | 19 天 |
| `fact_commodity_futures_daily` | 2026-06-26 | 23 天 |
| `fact_cffex_member_rank_daily` | 2026-06-26 | 23 天 |

SLA 数值仍需 owner 冻结，但证据表明：若 SLA 定为"T+5 交易日"级别，商品期货与席位数据**当前即为 stale**，相关策略应显示 `stale` 而非 `ready`。

## 4. §9 各待冻结项的证据状态

| §9 待冻结项 | 本轮证据结论 | 状态 |
| --- | --- | --- |
| 每条策略 owner / 审批责任人 | 证据无法替代业务决定 | **仍开放，需 owner** |
| `required_inputs` 表/字段/单位 | 8 张源表 schema 与字段清单已确认（见审计产物）；`unit` 列存在但逐序列单位未核对 | 部分证据化 |
| `minimum_history` | 各输入族可用历史上限已量化（§2）；具体门槛需 owner 在上限内定 | 部分证据化 |
| stale SLA / `update_frequency` | 当前滞后基线已量化（§3）；SLA 数值需 owner | 部分证据化 |
| 交易日/复权/股票池/退市/涨跌停/换月规则 | 本轮未审计（需逐策略代码级核对） | 仍开放 |
| 回测基准/样本/成本/admission 阈值 | 证据无法替代业务决定 | **仍开放，需 owner** |
| PIT `release_at/available_at/vintage/revision` 完整率 | **0%，全表无 PIT 列**（§1） | **已证据冻结** |

## 5. 审计产物与复跑方式

- 明细 JSON：`.codex-tmp/macro_p0_evidence_audit.json`（临时目录产物，随时可复跑再生）
- 复跑：MCP 可用时优先用 `moss-data-catalog` 的表清单/日期查询复核；否则以 `PYTHONPATH=<repo>` 运行等价的只读 `information_schema` + count/min(max) 日期查询（只读连接，不接受任意 SQL 之外的写操作）。
