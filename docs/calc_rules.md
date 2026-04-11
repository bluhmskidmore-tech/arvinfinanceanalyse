# calc_rules.md

## 1. 总则

本文件定义正式金融口径的核心计算规则。所有规则只允许实现于 `backend/app/core_finance/`，前端、API、Agent 不得重复实现。

## 2. H / A / T 映射

### 2.1 业务含义

| invest_type_std | 业务含义 | accounting_basis |
|---|---|---|
| H | 持有至到期 | AC |
| A | 可供出售 | FVOCI |
| T | 交易性 | FVTPL |

### 2.2 推导规则

优先顺序：
1. 直接读取源字段（若已给出 H/A/T）
2. 由资产分类文字推导：
   - 包含 `可供出售` / `AFS` → `A`
   - 包含 `交易` / `Trading` → `T`
   - 包含 `持有至到期` / `HTM` → `H`
3. 仍无法推导时，标记治理异常

## 3. Formal PnL

### 3.1 基础公式

```text
standardized_total_pnl = interest_income_514 + fair_value_change_516 + capital_gain_517 + manual_adjustment
```

`standardized_total_pnl` 只是标准化组件汇总，不直接等于 formal-recognized `total_pnl`；formal-recognized `total_pnl` 由 3.3 的归属矩阵判定。

### 3.2 会计口径

- `H / AC`：正式利润只保留利息与相关 realized 项，不将公允价值波动计入当期利润
- `A / FVOCI`：公允价值波动进入 OCI，不进入 formal PnL；分析口径可单列展示
- `T / FVTPL`：公允价值变动计入当期损益

### 3.3 Formal 归属矩阵

- `AC`：`514` 计入 formal；`516` 不计入 formal `total_pnl`；`517` 仅限 realized 且符合 formal 事件；`manual_adjustment` 仅限已批准 formal adjustment。
- `FVOCI`：`514` 计入 formal；`516` 不计入 formal `total_pnl`；`517` 仅计入已实现损益；OCI 变化不进 formal `total_pnl`。
- `FVTPL`：`514`、`516` 可进入 formal `total_pnl`；`517` 仍需满足 realized component / formal event semantics 才能进入 formal `total_pnl`；`manual_adjustment` 同样要求已批准。
- `manual_adjustment` 的批准判定必须来自治理/审批状态字段（如 `approval_status` / `governance_status`），不得由自由文本解释；未批准 adjustment 不进入 formal `total_pnl`。
- 当前 `backend/app/core_finance/pnl.py` 仍是 `standardization/materialize start-pack`，不等于完整 formal engine。

## 4. 516 规则

### 4.1 正式口径

- 正式层使用有符号金额 `signed_amount` 或 ETL 后的 `fair_value_change_516`
- 不允许在正式计算层再根据借贷标识拼符号

### 4.2 当前导入约定

- 若源表给出 `T损益516`，标准化时执行 `* -1` 形成统一口径
- 若源表给出 `金额 + 借贷标识`，必须在标准化阶段合成 `signed_amount`

## 5. 日均金额

### 5.1 basis

- `observed`：仅使用实际观测到的快照日
- `locf`：缺失日使用前一有效日沿用
- `calendar_zero`：缺失日按 0 处理

### 5.2 公式

```text
monthly_avg = sum(daily_value) / valid_day_count
```

其中：
- `observed`：`valid_day_count = observed_days`
- `locf`：`valid_day_count = calendar_days`
- `calendar_zero`：`valid_day_count = calendar_days`

### 5.3 正式与分析

- Formal：优先使用总账日均或正式定义的 `observed`
- Analytical：允许使用 `locf` / `calendar_zero`

## 6. 发行类债券排除规则

### 6.1 资产口径

债券资产月均、市值、摊余成本、应计利息默认排除发行类债券。

### 6.2 scope

- `asset`：排除发行类债券
- `liability`：仅看发行类债券 / 负债类债券
- `all`：全量审计视图

### 6.3 判断

优先使用标准化布尔字段 `is_issuance_like`，禁止散落 `LIKE '%发行%'` 作为长期正式规则。

## 7. FX 中间价折算

### 7.1 正式规则

- 使用当日官方中间价
- USD/CNY 正式口径来源为官方中间价源
- 周末/节假日允许沿用前一营业日中间价
- 缺失营业日中间价时，formal 失败

### 7.2 逐日换算公式

```text
market_value_cny_daily = market_value_native * fx_mid_rate
amortized_cost_cny_daily = amortized_cost_native * fx_mid_rate
accrued_interest_cny_daily = accrued_interest_native * fx_mid_rate
```

### 7.3 月均人民币值

```text
monthly_avg_market_value_cny = average(market_value_cny_daily)
```

禁止：
- 先算原币月均，再乘月均汇率

## 8. CNX / CNY 规则

- `CNX`：综本
- `CNY`：人民币账
- 外币展示值：`CNX - CNY`

禁止把 `CNX` 当成 ISO 币种代码。

## 9. 桥接归因

PnL Bridge 结构：

```text
期初脏市值
+ carry
+ roll_down
+ treasury_curve
+ credit_spread
+ fx_translation
+ realized_trading
+ unrealized_fv
+ manual_adjustment
= 期末变化解释值
```

要求：
- `explained_pnl`
- `actual_pnl`
- `residual`
- `residual_ratio`
- `quality_flag`

## 10. 风险张量

最少输出：
- `dv01`
- `krd_1y`
- `krd_3y`
- `krd_5y`
- `krd_7y`
- `krd_10y`
- `krd_30y`
- `cs01`
- `convexity`
- `issuer_concentration`
- `liquidity_gap`

## 11. result_meta

所有正式结果必须返回：
- `basis`
- `formal_use_allowed`
- `source_version`
- `rule_version`
- `generated_at`
- `trace_id`

## 12. ZQTZ / TYW Formal Balance

### 12.1 输入边界

`zqtz / tyw` 正式资产负债分析只允许读取：
- `zqtz_bond_daily_snapshot`
- `tyw_interbank_daily_snapshot`
- `fx_daily_mid`
- 治理 / 审批 / mapping 输入

禁止：
- 直接读取任何 `phase1_*preview*` 表
- 在 API / service / frontend 中重新实现正式规则

### 12.2 zqtz formal fact 规则

- `fact_formal_zqtz_balance_daily` 的金额事实来自 `zqtz_bond_daily_snapshot` 的正式投影。
- `invest_type_std` / `accounting_basis` / `position_scope` / `currency_basis` 必须在 `core_finance/` 中派生。
- `position_scope=asset` 时，默认排除 `is_issuance_like=true` 的发行类债券。
- `position_scope=liability` 时，只允许保留发行类 / 负债侧债券语义行。
- `position_scope=all` 时保留全量，用于审计与对账。

### 12.3 tyw formal fact 规则

- `fact_formal_tyw_balance_daily` 的金额事实来自 `tyw_interbank_daily_snapshot` 的正式投影。
- `principal_amount` 与 `accrued_interest_amount` 是正式读模型的基础金额字段；是否进入某个读模型口径，必须在 `core_finance/` 判定。
- `position_scope` 必须由 `position_side` 与治理映射共同确定，不允许 UI 临时解释。
- `funding_cost_rate` 是正式属性，不是展示层现算字段。

### 12.4 月均与汇率顺序

- 必须先生成逐日 formal amount，再按所选 basis 求月均。
- 当 `currency_basis=CNY` 时，必须先按每日 FX 中间价换算，再进入逐日 formal amount，再求月均。
- 不允许“先原币月均，后乘汇率”。
- 不允许用 preview rows 直接代替 formal daily facts。

### 12.5 当前状态说明

- 本节是当前 `zqtz / tyw` formal balance-analysis 的规则来源之一。
- 当前仓库已落地 governed formal compute / materialize、service / API 与首个 workbench consumer；已落地面以 `backend/app/core_finance/balance_analysis.py`、`backend/app/tasks/balance_analysis_materialize.py`、`backend/app/services/balance_analysis_service.py`、`backend/app/api/routes/balance_analysis.py` 与 `frontend/src/features/balance-analysis/pages/BalanceAnalysisPage.tsx` 为准。
- 本节不宣称超出上述已落地面的更多分析能力；后续扩展仍必须遵守 `backend/app/core_finance/` 唯一正式计算入口原则。

## 13. 禁止事项

- 不允许在 endpoint 或前端实现任何正式公式
- 不允许 Scenario 结果写入 Formal 事实表
- 不允许静默降级为 0 且不打标记
- 不允许未经测试修改 H/A/T、FX、516、发行类排除规则
