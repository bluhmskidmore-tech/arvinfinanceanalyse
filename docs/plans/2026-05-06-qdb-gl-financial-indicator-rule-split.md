# QDB GL Financial Indicator Rule Split Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 将 `2026年财务指标表-3月最终(1).xlsx` 中的总账对账、日均、财务指标和分部分析规则拆成可验证的系统规则。

**Architecture:** 先把 Excel 当作 golden sample 和规则证据，不直接把整本表搬到前端。后端负责科目组合、时间口径、单位换算和公式计算，前端只展示后端给出的结果、口径说明和差异状态。

**Tech Stack:** Python backend, FastAPI route/service, `backend/app/core_finance/qdb_gl_monthly_analysis.py`, existing QDB GL tests, `/ledger-pnl` frontend consumer.

---

## 1. 当前证据

来源文件：

- 用户口径样本：`C:/Users/arvin/Desktop/2026年财务指标表-3月最终(1).xlsx`
- 系统原始源：`data_input/pnl_总账对账-日均/总账对账202603.xlsx`
- 系统原始源：`data_input/pnl_总账对账-日均/日均202603.xlsx`

Excel 关键 sheet：

| sheet | 作用 | 系统拆分方式 |
| --- | --- | --- |
| `2026年账` | 2026 总账对账明细，月末时点余额 | 原始输入层 |
| `2026年日均` | 年日均、月日均、CNX/CNY、3/5/7/11 位科目 | 原始输入层 |
| `分部基础数据（2026）` | 存贷时点、年日均、月日均、分部基础规模 | 分部基础规则层 |
| `2026年营收总量` | 营收分项、利息净收入、非息、估值投资收益 | 营收/FTP 规则层 |
| `财务指标-计算表` | 集团、母行、子公司核心财务指标 | golden sample + 正式指标规则层 |
| `月度分析-总体` | 总体经营分析、同比、环比、利率、日均贡献 | 分析展示规则层 |
| `月度分析-分部情况` | 公司、零售、微贷、信用卡、金融市场分部 | 分部展示规则层 |

MCP 可用性：

- 已用 GitNexus 查询现有 QDB GL 路径，落点为 `backend/app/core_finance/qdb_gl_monthly_analysis.py`、`backend/app/services/qdb_gl_monthly_analysis_service.py` 及现有测试。
- 当前环境未发现 `moss-metric-contracts`、`moss-lineage-evidence`、`moss-data-catalog` 可调用工具；本轮以 Excel、现有源文件、GitNexus 和本地测试作为证据。

## 2. 规则层拆分

### Layer A: 源文件绑定

| rule_id | 规则 | 粒度 | 当前状态 |
| --- | --- | --- | --- |
| `QDB-SRC-LEDGER` | `总账对账YYYYMM.xlsx` 绑定报表月 | `report_month + sheet + account_code + currency` | 已有输入合同和测试 |
| `QDB-SRC-ADB` | `日均YYYYMM.xlsx` 绑定报表月 | `report_month + period_kind + currency + account_level + account_code` | 已有输入合同和测试 |
| `QDB-SRC-FIN-IND` | 财务指标表作为 golden sample | `report_month + metric_key + sheet_cell` | 待固化到 golden sample |

### Layer B: 科目组合规则

| metric_key | 中文名 | 规则 | 单位 | 现状 |
| --- | --- | --- | --- | --- |
| `qdb.loan_spot` | 贷款总额 | 3 位科目 `122/123/129/130/132/136` 期末余额求和 | 亿元 | 已进入后端第一版 |
| `qdb.deposit_spot` | 存款总额 | 3 位科目 `201/202/203/204/205/211/215/216/217/225/243/244/251` 期末余额绝对值求和 | 亿元 | 已进入后端第一版 |
| `qdb.investment_spot` | 投资总额 | 3 位科目 `141/142/143/144/145` 期末余额求和 | 亿元 | 已进入后端第一版 |
| `qdb.total_assets_ledger` | 总资产 QDB 源口径 | 1 字头资产类科目期末净额求和 | 亿元 | 已进入后端第一版 |
| `qdb.total_liabilities_ledger` | 总负债 QDB 源口径 | 2 字头负债类科目期末净额绝对值求和 | 亿元 | 已进入后端第一版 |
| `qdb.liquid_asset_spot` | 高流动性资产 | 3 位科目 `101/110/114/116` 期末余额求和 | 亿元 | 已进入后端第一版 |

### Layer C: 时间口径规则

| metric_family | 时间口径 | 来源 |
| --- | --- | --- |
| 时点规模 | 月末余额 | `总账对账YYYYMM.xlsx` / `2026年账` |
| 月日均 | 当月日均 | `日均YYYYMM.xlsx` 的 `月` sheet / `2026年日均` |
| 年日均 | 年初至当月日均 | `日均YYYYMM.xlsx` 的 `年` sheet / `2026年日均` |
| 同比 | 当年累计或当月 vs 上年同期 | `财务指标-计算表`、`月度分析-总体` |
| 环比 | 本月 vs 上月 | `月度分析-总体`、`月度分析-分部情况` |

### Layer D: 指标公式规则

| metric_key | 中文名 | 公式 | 当前系统值 202603 | Excel 对照 |
| --- | --- | --- | ---: | --- |
| `qdb.loan_to_deposit_ratio` | 存贷比 | `贷款总额 / 存款总额` | `81.89%` | 母行贷款 `4189.47`，母行存款 `5120.64`，接近但存款仍差 `4.68` 亿 |
| `qdb.loan_loss_reserve_ratio` | 贷款减值准备率 | `131 类贷款减值准备 / 贷款总额` | `2.70%` | 正式拨贷比 `2.9178%` 不能仅用总账 131 直接还原 |
| `qdb.liquid_asset_ratio` | 高流动性占比 | `高流动性资产 / QDB 总资产` | `4.97%` | 财务指标表无直接同名对照 |
| `qdb.term_deposit_ratio` | 定期化率 | `205/215 / 存款总额` | `62.27%` | 需后续对齐分部基础数据 |
| `qdb.demand_deposit_ratio` | 活期率 | `201/211 / 存款总额` | `24.20%` | 需后续对齐分部基础数据 |

## 3. 已发现的关键口径差异

| 差异项 | 系统 QDB 源口径 | Excel 正式口径 | 判断 |
| --- | ---: | ---: | --- |
| 总资产 | `8144.05` 亿 | 母行 `8150.52` 亿，集团 `8342.03` 亿 | QDB 源可解释，正式口径仍差 `6.47` 亿，疑似需要外部调整项 |
| 存款余额 | `5115.96` 亿 | 母行 `5120.64` 亿 | 仍差 `4.68` 亿，需要定位是否有科目排除/调整 |
| 贷款余额 | `4189.47` 亿 | 母行 `4189.47` 亿 | 已对齐 |
| 拨贷比 | QDB 可算 `贷款减值准备率` | 正式 `贷款拨备率（拨贷比）= 贷款期末拨备余额 / 贷款余额` | 正式拨备余额使用贷款减值损失、核销、收回、ROA 调整等，不应冒充总账直算 |
| 集团指标 | 当前系统只做母行/QDB 源分析 | Excel 包含母行 + 金租 + 理财 + 村镇银行 | 后续需要合并范围规则 |

## 4. 实施批次

### Batch 1: 核心总览口径锁定

**Files:**

- Modify: `backend/app/core_finance/qdb_gl_monthly_analysis.py`
- Test: `tests/test_qdb_gl_monthly_analysis_core.py`

**内容：**

- 固化贷款、存款、投资、总资产、总负债、高流动性资产科目组合。
- 固化 202603 golden sample：贷款 `4189.47`、存款 `5115.96`、总资产 `8144.05`、存贷比 `81.89%`。
- 对“正式拨贷比”保持 blocked，不用 QDB 源口径冒充。

**验证：**

- `python -m pytest tests/test_qdb_gl_monthly_analysis_core.py -q`
- `python -m pytest tests/test_qdb_gl_monthly_analysis_api.py tests/test_qdb_gl_monthly_analysis_service.py tests/test_qdb_gl_monthly_analysis_excel_export.py -q`

### Batch 2: 日均与时点偏离

**Files:**

- Modify: `backend/app/core_finance/qdb_gl_monthly_analysis.py`
- Test: `tests/test_qdb_gl_monthly_analysis_core.py`

**内容：**

- 把 `2026年日均` 的年日均、月日均拆为统一规则：`period_kind=year_avg/month_avg`。
- 每个 3 位/5 位/11 位科目都保留：时点余额、月日均、年日均、偏离额、偏离率。
- 前端继续只消费后端结果，不新增前端重复计算。

**验证：**

- 对 `summary_3d`、`top_11d`、`alerts` 做最小 golden sample。

### Batch 3: 分部基础规模

**Files:**

- Create or extend: `backend/app/core_finance/qdb_gl_monthly_analysis.py` rule section, only if formulas remain local and small.
- Test: `tests/test_qdb_gl_monthly_analysis_core.py`

**内容：**

- 从 `分部基础数据（2026）` 拆出公司存款、储蓄存款、公司贷款、个人贷款、微贷、信用卡的时点、年日均、月日均。
- 先只做基础规模，不做营收归因。

**验证：**

- 202603 公司贷款年日均 `3339.26`、月日均 `3391.97`。
- 202603 存款年日均合计 `5067.03`。

### Batch 4: 营收与利率归因

**Files:**

- New backend rule module only if formula volume明显变大，例如 `backend/app/core_finance/qdb_gl_financial_indicator_rules.py`
- Test: new narrow tests for revenue/interest attribution

**内容：**

- `2026年营收总量`、`月度分析-总体` 中的贷款利息、存款利息、金融投资利息、同业净收入、非息拆成独立规则。
- 利率类指标必须带分母：日均规模、年化天数、累计/月度口径。

**验证：**

- 202603 母公司营收 `40.5058` 亿。
- 202603 贷款利息收入 `39.0070` 亿。
- 202603 存款利息支出 `18.8038` 亿。

### Batch 5: 正式财务指标与合并范围

**Files:**

- Defer until formal adjustment source is identified.

**内容：**

- 总资产正式值、集团值、正式拨贷比、ROA、ROE 不能只用 QDB 源强算。
- 需要新增或绑定正式调整项来源：贷款减值损失、贷款核销、贷款收回、其他拨备、子公司合并抵消、管理层调整。

**验证：**

- 202603 母行总资产 `8150.5171` 亿。
- 202603 集团总资产 `8342.0255` 亿。
- 202603 母行拨贷比 `2.9178%`。

## 5. 前端落地原则

- `/ledger-pnl` 不再新增公式，只展示后端结果。
- 每个展示块需要显示：报表月、source_version、rule_version、是否 fallback、是否 formal_use_allowed。
- 对 QDB 源口径和正式财务指标口径不同的地方，页面要明确标注“QDB 源分析”或“正式口径待接入”。

## 6. 不做的事

- 不改数据库 schema。
- 不改全局 API client 结构。
- 不把 Excel 公式整本照搬成前端逻辑。
- 不把缺正式调整源的指标伪装成已对齐。
- 不一次性实现所有 sheet，按批次验收。

