# 宏观策略研究 P0 业务 Owner 签核包（2026-07-19）

- 关联合同：`docs/strategy_contracts/macro_strategy_research.md`（下称"合同"）§2 策略目录、§3 catalog 必填字段、§9 P0 待证据冻结项、§10.1 证据审计进展。
- 数据面证据：`docs/strategy_contracts/macro_strategy_p0_evidence_2026-07-19.md`（下称"证据审计"）§1—§3。
- 代码锚点：`backend/app/api/routes/macro_toolkit.py` 的 `_CAPABILITY_DEFINITIONS`（能力矩阵 M7—M16 + Crisis）与 `_CAPABILITY_INPUT_REQUIREMENTS`（字段级输入要求，仅覆盖 M7/M10/M14）；`backend/app/core_finance/macro/toolkit/system_sources.py` 的 `_LEGACY_ALIAS_CANDIDATES`（别名→实际序列解析）；`config/choice_macro_catalog.json`（Choice 序列 refresh_tier / 频率）。

---

## 1. 评审说明（先读）

### 1.1 本包性质

本包是**决策辅助材料，不是既成事实**。它把合同 §9 中"必须由业务 owner 拍板"的待冻结项，逐策略家族整理成可当场签核的表格，并附上每项的现有证据边界。本包本身不冻结任何业务真值；任何一栏在 owner 签核前均视为未确认。

### 1.2 合同约束（评审时必须遵守）

- 合同 §3：字段缺失、空 owner、无证据的占位值或未确认的关键业务值，不得进入主策略矩阵。**禁止用统一默认值补齐** `owner`、`minimum_history`、`update_frequency` 或输入矩阵。
- 合同 §9：待冻结值禁止从页面文案、样例、脚本默认值或当前最新日期猜测。
- 本包给出的 `minimum_history` 只有"证据允许的上限"（即当前数据实际可支撑的最长历史）；owner 只能在上限内定值。本包**不提供推荐默认值**。
- 本包给出的 stale SLA 只有"当前实测滞后基线"；SLA 数值由 owner 拍板。
- 所有数字均可追溯到 §1 开头列出的输入材料；无法追溯处标注「待证据」，评审时不得口头补数。

### 1.3 签核后的落地路径

- 签核结果由**合同维护人**（本轮为宏观策略研究合同的文档 owner，即执行本次评审记录的工程侧负责人）在评审会后更新到 `macro_strategy_research.md` §3/§9，并将本包归档为签核记录；本包本身不再修改合同以外的口径。
- 更新合同时逐项引用本包的「owner 决定值 / 签核人 / 日期」栏；未签核项在合同中保持"仍开放"状态，对应策略维持非 `ready` 状态（合同 §5、§9）。

### 1.4 阅读指引

- 第 2 节按合同 §2 的 9 个策略家族逐家族给出签核表。
- 第 3 节列出**已被证据冻结、无需 owner 拍板**的项（签核会上只需知悉）。
- 第 4 节列出**证据无法支持、必须 owner 决定**的项（签核会上必须拍板或明确挂起）。
- 「历史深度 / 最新日期 / 滞后」均引自证据审计 §2/§3（审计日 2026-07-19）；「refresh_tier / 频率」引自 `config/choice_macro_catalog.json`（版本 `2026-04-11.choice-macro.v2`）。catalog 只覆盖 Choice `EMM*` 序列；`CA.*`、`NCD.SHIBOR.*`、tushare 序列不在该 catalog 内，其刷新层级标注「不适用（非 catalog 序列）」。

---

## 2. 逐策略家族签核表

每个家族包含四个签核块：**Owner**、**required_inputs 确认**、**minimum_history**、**stale SLA**。「证据上限」指当前数据可支撑的最长历史，owner 定值不得超过该上限；超过即意味着该策略在数据回补完成前只能是 `insufficient_history`（合同 §5）。

能力矩阵（M7—M16 + Crisis）与合同 §2 家族并非一一映射；下文的能力归属是本包的整理口径，评审时如 owner 认为归属不当，请在备注栏写明（见第 4.6 项）。

### 2.1 A 股趋势（均线、均值回归 + 动量）

来源锚点：`backend/app/core_finance/macro/equity_strategies.py`（合同 §2）。

**Owner 签核**

| 项 | 值 |
| --- | --- |
| 待定 owner | ____________ |
| 审批责任人 | ____________ |
| 签核人 / 日期 | ____________ / ____________ |

**required_inputs（证据现状）**

| 输入 | 实际来源 | 历史深度（证据审计 §2） | 最新日期 / 滞后（§2/§3） | refresh_tier |
| --- | --- | --- | --- | --- |
| A 股个股日行情 | `choice_stock_daily_observation`（318 万行） | 2024-01-02 起，约 2.5 年 | 2026-07-14 / 5 天 | 不适用（非 catalog 序列） |
| 沪深300 / 中证500 指数 | `CA.CSI300` / `CA.CSI500`（各 732 行） | 2023-07-04 起，约 3 年 | 2026-07-10 | 不适用（非 catalog 序列） |

| 项 | owner 决定值 | 签核人 | 日期 |
| --- | --- | --- | --- |
| required_inputs 清单确认（含单位/复权口径，见第 4.4 项） | | | |

**minimum_history**

- 证据上限：个股约 **2.5 年**（2024-01-02 起）；指数约 **3 年**（2023-07-04 起）。要求超过 2.5 年个股历史的回测当前不可行（证据审计 §2）。

| 项 | owner 决定值 | 签核人 | 日期 |
| --- | --- | --- | --- |
| minimum_history（≤ 上限） | | | |

**stale SLA**

- 实测基线：个股日行情滞后 **5 天**（2026-07-14，证据审计 §3）；指数最新 2026-07-10。

| 项 | owner 决定值 | 签核人 | 日期 |
| --- | --- | --- | --- |
| stale SLA / update_frequency | | | |

### 2.2 A 股横截面（多因子、行业中性、低拥挤多因子）

来源锚点：`equity_strategies.py` 的 `multi_factor_selection`、`low_crowding_multifactor_selection`（合同 §2）。

**Owner 签核**

| 项 | 值 |
| --- | --- |
| 待定 owner | ____________ |
| 审批责任人 | ____________ |
| 签核人 / 日期 | ____________ / ____________ |

**required_inputs（证据现状）**

| 输入 | 实际来源 | 历史深度 | 最新日期 / 滞后 | refresh_tier |
| --- | --- | --- | --- | --- |
| A 股个股日行情 | `choice_stock_daily_observation` | 2024-01-02 起，约 2.5 年 | 2026-07-14 / 5 天 | 不适用 |
| Choice 因子表 | 合同 §2 引用实施计划 §2.2，本轮证据审计未单列因子表历史 | **待证据** | **待证据** | 不适用 |

| 项 | owner 决定值 | 签核人 | 日期 |
| --- | --- | --- | --- |
| required_inputs 清单确认（因子表待证据补齐后复核） | | | |

**minimum_history**

- 证据上限：日行情约 **2.5 年**；因子面历史深度**待证据**，在补齐前该家族的 minimum_history 只能以日行情上限为参考，且不得据此宣称因子历史充足。

| 项 | owner 决定值 | 签核人 | 日期 |
| --- | --- | --- | --- |
| minimum_history（≤ 上限） | | | |

**stale SLA**

- 实测基线：日行情滞后 **5 天**；因子面滞后**待证据**。

| 项 | owner 决定值 | 签核人 | 日期 |
| --- | --- | --- | --- |
| stale SLA / update_frequency | | | |

### 2.3 A 股风险（踩踏风险、拥挤、涨跌停质量）

来源锚点：`equity_strategies.py` crowding 计算入口（合同 §2）。

**Owner 签核**

| 项 | 值 |
| --- | --- |
| 待定 owner | ____________ |
| 审批责任人 | ____________ |
| 签核人 / 日期 | ____________ / ____________ |

**required_inputs（证据现状）**

| 输入 | 实际来源 | 历史深度 | 最新日期 / 滞后 | refresh_tier |
| --- | --- | --- | --- | --- |
| A 股个股日行情（含涨跌停字段） | `choice_stock_daily_observation` | 2024-01-02 起，约 2.5 年 | 2026-07-14 / 5 天 | 不适用 |
| 中金所席位（拥挤度） | `fact_cffex_member_rank_daily`（15731 行） | 2023-03-30 起 | **2026-06-26 / 滞后 23 天（当前 stale）** | 不适用 |

| 项 | owner 决定值 | 签核人 | 日期 |
| --- | --- | --- | --- |
| required_inputs 清单确认 | | | |

**minimum_history**

- 证据上限：日行情约 **2.5 年**；席位数据自 **2023-03-30**（约 3.3 年）。

| 项 | owner 决定值 | 签核人 | 日期 |
| --- | --- | --- | --- |
| minimum_history（≤ 上限） | | | |

**stale SLA**

- 实测基线：日行情滞后 **5 天**；席位数据滞后 **23 天**。证据审计 §3 明确：若 SLA 定为"T+5 交易日"级别，席位数据当前即为 stale，相关策略应显示 `stale` 而非 `ready`。

| 项 | owner 决定值 | 签核人 | 日期 |
| --- | --- | --- | --- |
| stale SLA / update_frequency | | | |

### 2.4 A 股组合（影子组合及成本情景）

来源锚点：`backend/app/core_finance/macro/equity_shadow_portfolio.py`（`COST_BPS = [0, 10, 20, 50]`，即合同 §6 提到的 `0/10/20/50bp` 成本情景）。

**Owner 签核**

| 项 | 值 |
| --- | --- |
| 待定 owner | ____________ |
| 审批责任人 | ____________ |
| 签核人 / 日期 | ____________ / ____________ |

**required_inputs（证据现状）**

| 输入 | 实际来源 | 历史深度 | 最新日期 / 滞后 | refresh_tier |
| --- | --- | --- | --- | --- |
| 横截面选股信号（上游 2.2 家族） | `equity_strategies.py` 输出 | 受 2.2 家族约束 | 同 2.2 | — |
| A 股个股日行情 | `choice_stock_daily_observation` | 2024-01-02 起，约 2.5 年 | 2026-07-14 / 5 天 | 不适用 |
| 成本情景参数 | 代码常量 `COST_BPS = [0, 10, 20, 50]` | — | — | — |

合同 §6：现有 `0/10/20/50bp` 只可作为 A 股影子组合 V1 基线，不授权跨资产家族比较，也不自动产生 `admitted` 结论。成本情景是否扩充/修改属于第 4 节 owner 决定项。

| 项 | owner 决定值 | 签核人 | 日期 |
| --- | --- | --- | --- |
| required_inputs 清单确认 | | | |

**minimum_history**

- 证据上限：约 **2.5 年**（受日行情约束；证据审计 §2 明确"要求 >2.5 年历史的回测不可行"）。

| 项 | owner 决定值 | 签核人 | 日期 |
| --- | --- | --- | --- |
| minimum_history（≤ 上限） | | | |

**stale SLA**

- 实测基线：日行情滞后 **5 天**。

| 项 | owner 决定值 | 签核人 | 日期 |
| --- | --- | --- | --- |
| stale SLA / update_frequency | | | |

### 2.5 宏观状态（Merrill Clock、经济周期、领先指标、流动性/利率状态）

来源锚点：`toolkit/runner.py` 脚本注册入口（合同 §2）。对应能力矩阵：M7 货币政策立场、M10 宏观领先指标、M11 流动性压力测试、M14 经济周期定位（本包整理口径）。M7/M10/M14 在 `_CAPABILITY_INPUT_REQUIREMENTS` 有字段级输入明细，M11 及 Merrill Clock 无字段级明细（仅 `data_aliases` 级别）。

**Owner 签核**

| 项 | 值 |
| --- | --- |
| 待定 owner | ____________ |
| 审批责任人 | ____________ |
| 签核人 / 日期 | ____________ / ____________ |

**required_inputs（证据现状）**

M14 经济周期定位（字段级，全部 required=True）：

| 字段 | 声明别名 | 实际解析来源（`system_sources.py`） | 历史深度 | 最新日期 / 滞后 | refresh_tier（catalog） |
| --- | --- | --- | --- | --- | --- |
| PMI | `M0017126` | 别名表中无该键，解析路径**待证据** | **待证据** | **待证据** | 不在 catalog |
| CPI 同比 | `M0000612` | `EMM00072301` / tushare `cn_cpi_yoy` | tushare：1951/1978 年起，月频（`std_external_macro_daily`） | 2026-06-01 或 2026-06-30 / 最长 19 天；**无 vintage** | `EMM00072301`：fallback（latest-only，频率 unknown） |
| PPI 同比 | `M0001227` | tushare `cn_ppi_yoy` | 同上（月频，历史充足） | 同上；**无 vintage** | 不在 catalog（tushare 源） |
| M2 同比 | `M0001385` | tushare `cn_m2_yoy` | 同上（月频，历史充足） | 同上；**无 vintage** | 不在 catalog（tushare 源） |
| 社融同比 | `M5525763` | `EMM00191807` | `EMM*` 快照族，逐序列行数**待证据**（约 80 个 `EMM*` 序列仅 1 行快照，证据审计 §2） | **待证据** | fallback（latest-only，频率 unknown）——latest-only 通道不积累历史 |

M10 宏观领先指标（字段级，全部 required=True）：

| 字段 | 声明别名 | 实际解析来源 | 历史深度 | 最新日期 / 滞后 | refresh_tier |
| --- | --- | --- | --- | --- | --- |
| PMI / M2 / 社融 | 同 M14 | 同 M14 | 同 M14 | 同 M14 | 同 M14 |
| 10Y-1Y 期限利差（derived） | `S0059743` + `S0059749` | 1Y：`EMM00166458`；10Y：`EMM00166466` | 1Y：仅 1 行快照（"其余期限各 1 行快照"，证据审计 §2）；10Y：122 行，自 2026-01-12（约 6 个月） | 2026-07-07/10 | 均在 stable（date_slice 日更；1Y 标注 daily/%，与仅 1 行快照的实况不符，见第 4.6 项） |
| AAA 信用利差（derived） | `S0059670` | `legacy.yield.moss_derived.credit_spread_aaa.3Y`（由 Choice 信用序列派生） | Choice 信用序列 `EMM001666xx` 各 1 行快照 → **派生利差无历史** | 2026-07-07 | 底层 `EMM00166657` 等在 stable，但实况 1 行（同上不符） |
| 布伦特油价 | `CA.BRENT` | `CA.BRENT` | 商品序列约 119 行，**2026-01-12 起（约 6 个月）** | 2026-07-10 | 不适用（非 catalog 序列） |

M7 货币政策立场（字段级）：

| 字段 | 声明别名 | required | 实际解析来源 | 历史深度 | 最新日期 / 滞后 | refresh_tier |
| --- | --- | --- | --- | --- | --- | --- |
| 7 天逆回购政策利率 | `M0041653` | 是 | 首选 `EMM00088132`（次选 `cn_repo_7d` 等） | **待证据**（`EMM00088132` 不在 catalog 且证据审计未单列） | **待证据** | **不在 catalog**（catalog 只有 14 天逆回购 `EMM00088133/134`，见第 4.6 项） |
| DR007 | `DR007.IB` | 是 | `CA.DR007`（249 行） | 2025-07-10 起，**仅 1 年** | 2026-07-10 | 不适用 |
| 10Y 国债 | `S0059749` | 否 | `EMM00166466` | 122 行，自 2026-01-12 | 2026-07-07/10 | stable |

M11 流动性压力测试（`data_aliases` 级）：

| 输入 | 声明别名 | 实际解析来源 | 历史深度 | 最新日期 / 滞后 | refresh_tier |
| --- | --- | --- | --- | --- | --- |
| DR007 | `DR007.IB` | `CA.DR007` | 1 年 | 2026-07-10 | 不适用 |
| 3M NCD | `M0041813` | `NCD.SHIBOR.3M`（9 行） | **2026-06-30 起（9 行）**——证据审计 §2："任何依赖 NCD 历史的信号今天都是 `insufficient_history`" | 2026-07-10 | 不适用（catalog 的 SHIBOR 为 `EMM001672xx/66252-54` 快照通道，与 `NCD.SHIBOR.*` 命名空间不同，见第 4.6 项） |

Merrill Clock 商品腿：商品序列（铜/铝/布油/钢）约 119 行、2026-01-12 起（约 6 个月）——证据审计 §2 明确"Merrill Clock 商品腿历史极薄"。

| 项 | owner 决定值 | 签核人 | 日期 |
| --- | --- | --- | --- |
| required_inputs 清单确认（含 PMI 解析路径、社融历史两处待证据） | | | |

**minimum_history**

- 证据上限（分输入族，不得共用统一门槛——合同 §9）：
  - CPI/PPI/M2（tushare 月频）：历史充足（1951/1978 年起），但**无 vintage**，历史复现受第 3 节 fail-closed 约束；
  - DR007：**1 年**；
  - 10Y 国债（Choice 源）：**约 6 个月**（122 行）；1Y 及其余期限、Choice 信用序列：**无历史**（1 行快照）；
  - 商品：**约 6 个月**；
  - NCD/SHIBOR：**9 个交易日**（实质无历史）；
  - PMI、社融：**待证据**。

| 项 | owner 决定值 | 签核人 | 日期 |
| --- | --- | --- | --- |
| minimum_history（逐输入族，≤ 各自上限） | | | |

**stale SLA**

- 实测基线：`fact_choice_macro_daily` 滞后 **9 天**；`std_external_macro_daily`（tushare 宏观）滞后 **19 天**（月频数据的自然发布节奏需 owner 判断是否算滞后）。

| 项 | owner 决定值 | 签核人 | 日期 |
| --- | --- | --- | --- |
| stale SLA / update_frequency（股票、宏观分别定，合同 §9） | | | |

### 2.6 趋势/波动（CTA Trend、Regime Switch、GARCH/DCC）

来源锚点：`toolkit/runner.py` 脚本注册入口（合同 §2）。能力矩阵未单列对应条目；输入按证据审计 §2 的商品/指数族整理。

**Owner 签核**

| 项 | 值 |
| --- | --- |
| 待定 owner | ____________ |
| 审批责任人 | ____________ |
| 签核人 / 日期 | ____________ / ____________ |

**required_inputs（证据现状）**

| 输入 | 实际来源 | 历史深度 | 最新日期 / 滞后 | refresh_tier |
| --- | --- | --- | --- | --- |
| 商品序列（铜/铝/布油/钢） | `CA.COPPER` 等（各约 119 行） | **2026-01-12 起（约 6 个月）** | 2026-07-10 | 不适用 |
| 指数（沪深300/中证500） | `CA.CSI300` / `CA.CSI500` | 2023-07-04 起，约 3 年 | 2026-07-10 | 不适用 |
| 南华商品指数（如策略引用） | `NH0100.NHF` → `NHCI.NH`（tushare） | **待证据** | **待证据** | 不适用 |

| 项 | owner 决定值 | 签核人 | 日期 |
| --- | --- | --- | --- |
| required_inputs 清单确认（逐策略核对实际引用序列，本轮未做代码级逐策略核对） | | | |

**minimum_history**

- 证据上限：商品腿 **约 6 个月**；指数腿 **约 3 年**。GARCH/DCC 等需要长窗口估计的模型，若 owner 定值超过 6 个月，商品腿策略在回补前只能是 `insufficient_history`。

| 项 | owner 决定值 | 签核人 | 日期 |
| --- | --- | --- | --- |
| minimum_history（商品/指数分别定，≤ 各自上限） | | | |

**stale SLA**

- 实测基线：商品/指数（`fact_choice_macro_daily` 族）滞后 **9 天**（最新 2026-07-10）。

| 项 | owner 决定值 | 签核人 | 日期 |
| --- | --- | --- | --- |
| stale SLA / update_frequency | | | |

### 2.7 资产配置（Risk Parity、风险预算、再平衡）

来源锚点：`toolkit/runner.py` 脚本注册入口（合同 §2）。跨资产权重估计依赖各资产腿的共同历史窗口。

**Owner 签核**

| 项 | 值 |
| --- | --- |
| 待定 owner | ____________ |
| 审批责任人 | ____________ |
| 签核人 / 日期 | ____________ / ____________ |

**required_inputs（证据现状）**

| 输入 | 实际来源 | 历史深度 | 最新日期 / 滞后 | refresh_tier |
| --- | --- | --- | --- | --- |
| 股票腿（指数） | `CA.CSI300` / `CA.CSI500` | 约 3 年 | 2026-07-10 | 不适用 |
| 商品腿 | `CA.COPPER` 等 | **约 6 个月** | 2026-07-10 | 不适用 |
| 债券腿（期货） | `fact_commodity_futures_daily`（11043 行） | 2024-01-02 起 | **2026-06-26 / 滞后 23 天（当前 stale）** | 不适用 |
| 利率/资金腿 | `CA.DR007` | 1 年 | 2026-07-10 | 不适用 |

| 项 | owner 决定值 | 签核人 | 日期 |
| --- | --- | --- | --- |
| required_inputs 清单确认（逐策略核对实际资产腿） | | | |

**minimum_history**

- 证据上限：跨资产**共同**历史窗口受商品腿约束，为 **约 6 个月**（2026-01-12 起）；若剔除商品腿，受 DR007 约束为 **1 年**。

| 项 | owner 决定值 | 签核人 | 日期 |
| --- | --- | --- | --- |
| minimum_history（≤ 共同窗口上限；是否允许剔除资产腿由 owner 决定） | | | |

**stale SLA**

- 实测基线：债券期货滞后 **23 天**（当前 stale）；其余腿最长 9 天。

| 项 | owner 决定值 | 签核人 | 日期 |
| --- | --- | --- | --- |
| stale SLA / update_frequency（逐资产腿） | | | |

### 2.8 风险聚合（Crisis Score、Crowding、Final Signal、Risk Monitor）

来源锚点：`toolkit/runner.py` 脚本注册入口（合同 §2）。对应能力矩阵：Crisis Score（`crisis_score_cn`，route_status=wired）、M12 跨市场联动、M16 宏观决策摘要（本包整理口径）。

**Owner 签核**

| 项 | 值 |
| --- | --- |
| 待定 owner | ____________ |
| 审批责任人 | ____________ |
| 签核人 / 日期 | ____________ / ____________ |

**required_inputs（证据现状）**

Crisis Score（`data_aliases` 级）：

| 输入 | 声明别名 | 实际解析来源 | 历史深度 | 最新日期 / 滞后 | refresh_tier |
| --- | --- | --- | --- | --- | --- |
| 沪深300 | `sh000300` | `CA.CSI300` | 约 3 年 | 2026-07-10 | 不适用 |
| AA 5Y 信用收益率 | `S0059760` | `EMM00166683` | **1 行快照，无历史** | 2026-07-07 | stable（与实况不符，见第 4.6 项） |
| 5Y 国债 | `S0059747` | `EMM00166462`（次选 `tushare.yc_cb.1001.CB.5Y`） | Choice 源 **1 行快照**；tushare 备选 286 行 | Choice 2026-07-07；tushare **至 2026-04-30（stale）** | stable（同上） |
| 美元兑人民币 | `M0067855` | `EMM00058124` / `fx_daily_mid:USD/CNY` | `fx_daily_mid` 在 8 张被审计表中，但历史深度未单列——**待证据** | **待证据** | `EMM00058124`：stable |
| 南华商品指数 | `NH0100.NHF` | `NHCI.NH`（tushare） | **待证据** | **待证据** | 不适用 |
| DR007 | `DR007.IB` | `CA.DR007` | 1 年 | 2026-07-10 | 不适用 |
| 7 天逆回购利率 | `M0041653` | 首选 `EMM00088132` | **待证据** | **待证据** | **不在 catalog** |

M12 跨市场联动：`sh000300`（约 3 年）、`CU0` → `CA.COPPER`（**约 6 个月**）、`M0067855`（待证据）。
M16 宏观决策摘要：聚合 `DR007.IB`、`S0059749`、`sh000300`、`M0067855` 及其他能力卡结果，受各上游输入约束。

| 项 | owner 决定值 | 签核人 | 日期 |
| --- | --- | --- | --- |
| required_inputs 清单确认（信用/5Y 国债/FX/南华/7 天逆回购五处证据缺口） | | | |

**minimum_history**

- 证据上限：股票腿约 **3 年**；资金腿 **1 年**；商品联动腿 **约 6 个月**；信用与 5Y 国债的 Choice 源 **无历史**（1 行快照），tushare 5Y 备选约 **286 个交易日**且已 stale。任何要求信用利差历史分位数的聚合逻辑，在 Choice 源上当前**不可算**（证据审计 §2）。

| 项 | owner 决定值 | 签核人 | 日期 |
| --- | --- | --- | --- |
| minimum_history（逐输入族，≤ 各自上限） | | | |

**stale SLA**

- 实测基线：`fact_choice_macro_daily` 族滞后 **9 天**；tushare 5Y 备选已滞后至 **2026-04-30**。

| 项 | owner 决定值 | 签核人 | 日期 |
| --- | --- | --- | --- |
| stale SLA / update_frequency | | | |

### 2.9 债券/跨资产（债券期货基差、IRR、安全边际、信用 carry、曲线趋势）

来源锚点：`toolkit/scripts/bond_futures_data.py`、`credit_bond_data.py`（合同 §2）。相关能力：M8 收益率曲线形态、M9 信用利差预警、M13 利率拐点、M15 宏观情景组合影响（本包整理口径；注意 M8/M9/M13/M15 的实际计算走正式曲线表，见下）。

**Owner 签核**

| 项 | 值 |
| --- | --- |
| 待定 owner | ____________ |
| 审批责任人 | ____________ |
| 签核人 / 日期 | ____________ / ____________ |

**required_inputs（证据现状）**

| 输入 | 实际来源 | 历史深度 | 最新日期 / 滞后 | refresh_tier |
| --- | --- | --- | --- | --- |
| 债券期货日行情（基差/IRR） | `fact_commodity_futures_daily`（11043 行） | 2024-01-02 起 | **2026-06-26 / 滞后 23 天（当前 stale）** | 不适用 |
| 正式收益率曲线（M8/M9/M13/M15 实际输入） | `fact_formal_yield_curve_daily`（`load_macro_capability_context` 的 `curve_rows`） | 在 8 张被审计表中，但历史深度未单列——**待证据** | **待证据** | 不适用 |
| Choice 国债/信用序列（能力矩阵声明别名） | `EMM00166466`（10Y，122 行）；其余期限与信用序列各 1 行快照 | 10Y 约 6 个月；其余**无历史** | 2026-07-07/10 | stable（与实况不符） |
| 信用 carry（tushare 备选） | `tushare.yc_cb.1001.CB.5Y`（286 行） | 约 286 个交易日 | **至 2026-04-30（stale）** | 不适用 |
| 中金所席位 | `fact_cffex_member_rank_daily` | 2023-03-30 起 | 2026-06-26 / 23 天 | 不适用 |
| 组合持仓 / 风险张量（M15） | `load_macro_capability_context` 的 positions / risk_tensor | 本轮未审计——**待证据** | **待证据** | 不适用 |

| 项 | owner 决定值 | 签核人 | 日期 |
| --- | --- | --- | --- |
| required_inputs 清单确认（正式曲线表与组合持仓两处待证据） | | | |

**minimum_history**

- 证据上限：债券期货 **2024-01-02 起（约 2.5 年）**；完整曲线历史依赖 `fact_formal_yield_curve_daily` / `tushare.yc_cb`（深度分别为待证据 / 约 286 个交易日）；Choice 曲线源仅 10Y 有约 6 个月短历史（证据审计 §2："曲线形态/利率拐点只有 10Y 有短历史"）。

| 项 | owner 决定值 | 签核人 | 日期 |
| --- | --- | --- | --- |
| minimum_history（期货/曲线/信用分别定，≤ 各自上限） | | | |

**stale SLA**

- 实测基线：债券期货与席位数据滞后 **23 天**（当前 stale）；tushare 信用曲线备选滞后至 **2026-04-30**。证据审计 §3：若 SLA 定为"T+5 交易日"级别，商品期货与席位数据当前即为 stale。

| 项 | owner 决定值 | 签核人 | 日期 |
| --- | --- | --- | --- |
| stale SLA / update_frequency（期货、席位、曲线分别定） | | | |

---

## 3. 已被证据冻结、无需 owner 拍板的项

以下结论由数据面证据直接决定，签核会上只需知悉，**不设 owner 决定栏**：

1. **PIT / vintage 完整率为 0**（证据审计 §1）：全部 8 张系统源表（`fact_choice_macro_daily`、`choice_market_snapshot`、`std_external_macro_daily`、`fact_commodity_futures_daily`、`fx_daily_mid`、`fact_formal_yield_curve_daily`、`choice_stock_daily_observation`、`fact_cffex_member_rank_daily`）均无 `release_at` / `available_at` / `vintage` / `revision` / `publish_time` 列。
2. 由此按合同 §8 直接生效（无需拍板）：
   - 任何声称"历史时点可复现"的结果（事件意外、修订敏感回归、历史宏观回测）**必须 fail closed**：不得输出 `ready`，不得进入 backtest/admission，不得中途用最新修订值回填历史。
   - 当前数据面只能支持"当前观察"模式，最多标 `degraded` 并注明 PIT 缺口，保持 `observation_only=true`、`formal_use_allowed=false`。
   - V2 候选中依赖可靠发布时点的策略（事件意外、跨国宏观）在 PIT 列落地前**没有准入路径**。
3. **约 80 个 `EMM*` 序列仅 1 行快照**（证据审计 §2）：这些序列只能支撑"最新值"展示，不能支撑任何需要历史窗口的信号；为它们登记 `minimum_history` 前必须先完成历史回补。owner 在第 2 节定值时不得越过这一事实。
4. **`observation_only=true` / `formal_use_allowed=false` 不可被本次签核覆盖**（合同 §1）：本包的任何签核结果都不构成从 observation-only 晋升为正式指标或投资信号的授权。

---

## 4. 无法由证据支持、必须 owner 决定的项

以下项证据只能提供边界，无法给出取值；评审会上必须逐项拍板或明确挂起（挂起即对应策略维持非 `ready` / `not_admitted`）：

### 4.1 回测基准

- 决策问题：各家族回测用什么基准（A 股类：沪深300？中证500？债券/跨资产：什么曲线或指数）？合同 §6 明确"基准……尚待 P0 证据与 owner 冻结；本合同不猜默认值"。
- 证据边界：可用基准序列本身受历史深度约束（`CA.CSI300`/`CA.CSI500` 约 3 年，商品约 6 个月）。

| 家族 | owner 决定值 | 签核人 | 日期 |
| --- | --- | --- | --- |
| A 股趋势 / 横截面 / 风险 / 组合 | | | |
| 趋势/波动、资产配置 | | | |
| 债券/跨资产 | | | |

### 4.2 成本 / 滑点情景

- 决策问题：`0/10/20/50bp`（`equity_shadow_portfolio.py` 的 `COST_BPS`）是否确认为 A 股影子组合 V1 基线？其他资产家族（期货换月成本、债券买卖价差）用什么情景？合同 §6 明确该基线不授权跨资产家族直接比较。

| 项 | owner 决定值 | 签核人 | 日期 |
| --- | --- | --- | --- |
| A 股成本情景（确认/修改 0/10/20/50bp） | | | |
| 期货 / 债券 / 跨资产成本情景 | | | |

### 4.3 admission 阈值与样本 / 延迟规则

- 决策问题：`admitted` / `conditional` / `rejected` 的通过阈值（收益、回撤、命中率、稳定性等，合同 §6 指标清单）；样本区间；执行延迟（T+0/T+1）；调仓频率；压力窗口定义。
- 证据边界：样本区间不得超过第 2 节各家族的历史上限；压力窗口表现在 PIT 缺口下受第 3 节 fail-closed 约束。

| 项 | owner 决定值 | 签核人 | 日期 |
| --- | --- | --- | --- |
| admission 通过阈值（逐家族或统一，需 owner 明示） | | | |
| 样本区间 / 执行延迟 / 调仓频率 | | | |
| 压力窗口定义 | | | |

### 4.4 交易日历与市场微观规则

- 决策问题（合同 §9，证据审计 §4 标注"本轮未审计"）：交易日 vs 自然日口径；复权方式；股票池定义；退市 / 停牌 / 涨跌停处理；期货连续合约、换月和价格调整规则。

| 项 | owner 决定值 | 签核人 | 日期 |
| --- | --- | --- | --- |
| 交易日/自然日与复权口径 | | | |
| 股票池 / 退市 / 停牌 / 涨跌停规则 | | | |
| 期货换月与价格调整规则 | | | |

### 4.5 数据回补优先级

- 决策问题：证据显示商品仅约 6 个月、NCD 仅 9 行、约 80 个 `EMM*` 序列无历史、tushare 信用曲线停在 2026-04-30。哪些输入族值得投入回补（决定了哪些策略能达到 owner 期望的 minimum_history），优先级如何排？

| 项 | owner 决定值 | 签核人 | 日期 |
| --- | --- | --- | --- |
| 回补优先级清单 | | | |

### 4.6 本包发现的合同 / 代码 / 配置不一致处（需 owner 知悉并裁定归属）

1. **`M0041653`（7 天逆回购）无 catalog 依据**：`system_sources.py` 将其首选解析到 `EMM00088132`，但 `choice_macro_catalog.json` 中不存在该序列（只有 14 天逆回购 `EMM00088133/134`）。该输入的刷新层级与历史深度均待证据。
2. **catalog 声明与数据实况不符**：多条国债/信用 `EMM` 序列（如 `EMM00166458`、`EMM00166462`、`EMM00166655/57/59/79/81/83`）在 catalog `stable_daily` 批次（date_slice 日更），但 DuckDB 实况仅 1 行快照（证据审计 §2）。需数据侧解释是新近接入未回补，还是刷新链路未生效。
3. **能力声明别名 ≠ 实际计算输入**：M8/M9/M13/M15 在 `_CAPABILITY_DEFINITIONS` 声明 `S00597xx` 系列别名，但实际计算通过 `load_macro_capability_context` 的 `curve_rows` 走 `fact_formal_yield_curve_daily`（正式曲线表）。登记 `required_inputs` 时应以实际计算路径为准；正式曲线表的历史深度本轮未单列，待证据。
   - 已修正（2026-07-19）：`_CAPABILITY_DEFINITIONS` 为 M8/M9/M13/M15 新增 `data_tables` 字段声明正式表输入（均含 `fact_formal_yield_curve_daily`，M15 另含 `fact_formal_bond_analytics_daily`），并在 `_capability_payload` 透传；`data_aliases` 收敛为仍真实作为曲线回退点消费的别名（删除 M9 的 `S0059670`、M13 的 `DR007.IB`/`S0059747`、M15 的 `S0059760`/`M0067855`，补齐实际消费的国债节点）。测试锁定见 `tests/test_macro_toolkit_scripts.py::test_capability_definitions_declare_actual_curve_inputs_via_data_tables`。正式曲线表历史深度仍待证据。
4. **字段级输入要求覆盖不全**：`_CAPABILITY_INPUT_REQUIREMENTS` 仅覆盖 M7/M10/M14 三个能力；其余能力（含已 wired 的 Crisis Score、M16）只有 `data_aliases` 级声明，无 required/derived 标记。
5. **家族与能力矩阵非一一映射**：合同 §2 的 9 个家族与 M7—M16 能力没有权威映射；M15（宏观情景组合影响）、M16（决策摘要）的家族归属是本包整理口径，需 owner 确认。
6. **SHIBOR 命名空间分裂**：`M0041813` 解析到 `NCD.SHIBOR.3M`（9 行），而 catalog 的 SHIBOR 走 `EMM00166252-54 / EMM001676xx / EMM00167708`（`choice_funding_shibor_latest` 批次，latest-only）。两套序列是否同源、能否互补历史，待数据侧确认。
7. **PMI（`M0017126`）解析路径缺失**：`_LEGACY_ALIAS_CANDIDATES` 中无 `m0017126` 键，catalog 中也无对应序列；M10/M14 均将 PMI 列为 required=True。PMI 的实际落库路径与历史深度待证据。

| 项 | owner 决定值 | 签核人 | 日期 |
| --- | --- | --- | --- |
| 上述 7 项的处置责任人与期限 | | | |

---

## 5. 附录：证据来源与复核方式

### 5.1 证据来源清单

| 证据 | 来源 | 用于本包哪部分 |
| --- | --- | --- |
| 策略家族、展示模式、来源锚点 | 合同 §2 | 第 2 节家族划分 |
| catalog 必填字段与"禁止默认值补齐"约束 | 合同 §3、§9 | 第 1.2 节、第 2 节签核栏设计 |
| PIT 完整率 0、fail-closed 规则 | 证据审计 §1；合同 §8 | 第 3 节 |
| 各输入族历史深度 / 最新日期 | 证据审计 §2 | 第 2 节 required_inputs 与 minimum_history 上限 |
| 新鲜度滞后基线 | 证据审计 §3 | 第 2 节 stale SLA 基线 |
| 能力矩阵与输入别名 | `backend/app/api/routes/macro_toolkit.py` `_CAPABILITY_DEFINITIONS`（约 L134—L256）、`_CAPABILITY_INPUT_REQUIREMENTS`（约 L1488—L1595） | 第 2.5/2.8/2.9 节输入表 |
| 别名 → 实际序列解析 | `backend/app/core_finance/macro/toolkit/system_sources.py` `_LEGACY_ALIAS_CANDIDATES`（约 L32—L88） | 第 2 节"实际解析来源"列 |
| 曲线类能力实际输入路径 | `backend/app/services/macro_toolkit_service.py` `load_macro_capability_context`（约 L1525） | 第 4.6 节第 3 项 |
| refresh_tier / 频率 / 单位 | `config/choice_macro_catalog.json`（版本 `2026-04-11.choice-macro.v2`） | 第 2 节"refresh_tier"列、第 4.6 节第 1/2/6 项 |
| A 股成本情景常量 | `backend/app/core_finance/macro/equity_shadow_portfolio.py` `COST_BPS`（L26） | 第 2.4 节、第 4.2 节 |

### 5.2 复核方式

- 历史深度 / 新鲜度：按证据审计 §5——MCP 可用时优先用 `moss-data-catalog` 的表清单/日期查询复核；否则以只读 DuckDB `information_schema` + 逐表 count/min/max 日期查询复跑（明细 JSON：`.codex-tmp/macro_p0_evidence_audit.json`，可再生）。
- 能力矩阵 / 别名解析：直接比对上表列出的代码位置；行号为 2026-07-19 快照，代码变动后以符号名检索为准。
- catalog：比对 `config/choice_macro_catalog.json` 中对应 `series_id` 的 `refresh_tier`（所在 batch）、`frequency`、`unit` 字段。
- 本轮 MCP（`moss-metric-contracts` / `moss-lineage-evidence` / `moss-data-catalog` / `gitnexus`）不可用状态沿袭证据审计 §5 记录；MCP 恢复后应复核本包所有「待证据」标注项。

### 5.3 「待证据」项汇总（MCP / 数据侧回补后需回填）

1. PMI（`M0017126`）落库路径与历史深度（2.5 节）。
2. 社融（`M5525763` → `EMM00191807`）历史行数（2.5 节）。
3. `M0041653` → `EMM00088132` 历史深度与刷新层级（2.5、2.8 节）。
4. Choice 因子表历史深度与新鲜度（2.2 节）。
5. `fx_daily_mid`（USD/CNY）历史深度（2.8 节）。
6. `NHCI.NH`（南华指数）历史深度（2.6、2.8 节）。
7. `fact_formal_yield_curve_daily` 历史深度（2.9 节）。
8. 组合持仓 / 风险张量输入的审计（2.9 节，M15）。
