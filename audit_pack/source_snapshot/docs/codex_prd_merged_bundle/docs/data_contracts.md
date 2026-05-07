# data_contracts.md

## 1. 目标

定义系统的标准化数据契约，作为 `zqtz`、`tyw`、FI 损益、非标分录、日均、FX、Choice、AkShare 接入后的统一语义层。

## 2. 设计原则

1. 原始数据不直接进入正式计算。
2. 所有正式计算只读取标准化表或事实表。
3. 同一业务字段只能有一个标准语义，不允许同名异义。
4. 币种、金额单位、利率单位必须显式声明。
5. 所有正式结果都必须可追溯到源表、源文件、源版本。

## 3. 数据层级

### Raw
- 原始 Excel / CSV / zip / API 响应
- 原样保留
- 增加 `source_file`、`ingest_batch_id`、`raw_row_num`

### Standardized
- 统一字段名、日期、单位、主键
- 建立标准表

### Curated / Fact
- 形成正式分析事实表
- 供 service / core_finance 使用

## 4. 标准表清单

### 4.1 zqtz_bond_daily_snapshot

用途：债券逐日快照。

关键字段：
- `report_date` date
- `instrument_code` varchar
- `instrument_name` varchar
- `portfolio_name` varchar
- `cost_center` varchar
- `account_category` varchar
- `asset_class` varchar
- `bond_type` varchar
- `issuer_name` varchar
- `industry_name` varchar
- `rating` varchar
- `currency_code` varchar
- `market_value_native` decimal(24,8)
- `amortized_cost_native` decimal(24,8)
- `accrued_interest_native` decimal(24,8)
- `ytm_value` decimal(18,8)
- `coupon_rate` decimal(18,8)
- `maturity_date` date
- `next_call_date` date
- `overdue_days` integer
- `is_issuance_like` boolean
- `source_version` varchar

单位约定：
- 金额字段为原币金额
- `ytm_value`、`coupon_rate` 统一为小数口径

### 4.2 tyw_interbank_daily_snapshot

用途：同业/资金逐日快照。

关键字段：
- `report_date`
- `position_id`
- `product_type`
- `position_side`
- `counterparty_name`
- `account_type`
- `special_account_type`
- `currency_code`
- `principal_native`
- `accrued_interest_native`
- `funding_cost_rate`
- `maturity_date`
- `pledged_bond_code`
- `source_version`

### 4.3 fi_pnl_record

用途：FI 正式损益记录。

关键字段：
- `report_date`
- `instrument_code`
- `portfolio_name`
- `cost_center`
- `invest_type_raw`
- `invest_type_std`  # H / A / T
- `accounting_basis` # AC / FVOCI / FVTPL
- `interest_income_514`
- `fair_value_change_516`
- `capital_gain_517`
- `total_pnl`
- `currency_basis`   # CNY / CNX
- `source_version`

规则：
- `invest_type_std` 由正式映射规则生成
- `total_pnl = 514 + 516 + 517 + manual_adjustment`

### 4.4 nonstd_journal_entry

用途：非标分录明细。

关键字段：
- `voucher_date`
- `account_code`
- `asset_code`
- `portfolio_name`
- `cost_center`
- `journal_type`  # 514 / 516 / 517 / adjustment
- `signed_amount`
- `dc_flag`
- `event_type`
- `source_file`
- `source_version`

规则：
- 若源只有金额 + 借贷标识，必须在标准化阶段合成 `signed_amount`
- 正式计算只使用 `signed_amount`

### 4.5 ledger_daily_pnl

用途：总账日均与月度损益正式源。

关键字段：
- `report_month`
- `currency_basis`  # CNX / CNY
- `account_code`
- `account_name`
- `avg_balance`
- `month_pnl`
- `annualized_yield`
- `product_category`
- `source_version`

规则：
- `CNX` = 综本
- `CNY` = 人民币账
- 外币展示 = `CNX - CNY`

### 4.6 fx_daily_mid

用途：正式 FX 中间价。

关键字段：
- `trade_date`
- `base_currency`
- `quote_currency`
- `mid_rate`
- `source_name`   # CFETS / SAFE / internal
- `is_business_day`
- `is_carry_forward`
- `source_version`

规则：
- 正式 USD/CNY 使用官方中间价
- 周末/节假日允许沿用前一营业日
- 缺失营业日中间价时，formal 失败，不静默补值

### 4.7 choice_market_snapshot / choice_market_curve

用途：Choice 市场增强与曲线。

关键字段：
- `trade_date`
- `series_id`
- `series_name`
- `field_name`
- `value`
- `source_version`

规则：
- 只作市场/宏观/情景增强
- 是否允许 formal 使用由配置决定

## 5. 事实表清单

- `fact_bond_monthly_avg`
- `fact_interbank_monthly_avg`
- `fact_formal_pnl_fi`
- `fact_nonstd_pnl_bridge`
- `fact_fx_converted_positions_daily`
- `fact_pnl_bridge_daily`
- `fact_risk_tensor_daily`
- `fact_formal_analytical_bridge_daily`

## 6. 主键建议

### bond snapshot 主键
```text
(report_date, instrument_code, portfolio_name, cost_center, currency_code)
```

### interbank snapshot 主键
```text
(report_date, position_id)
```

### fi pnl 主键
```text
(report_date, instrument_code, portfolio_name, cost_center, currency_basis)
```

### fx_daily_mid 主键
```text
(trade_date, base_currency, quote_currency)
```

## 7. 必要派生字段

- `invest_type_std`：H / A / T
- `accounting_basis`：AC / FVOCI / FVTPL
- `position_scope`：asset / liability / all
- `currency_basis`：native / CNY / CNX
- `maturity_bucket`
- `repricing_bucket`
- `rating_bucket`
- `position_side`
- `formal_use_allowed`

## 8. 缺失值规则

- 正式结果不允许静默填 0 替代关键业务字段
- 分析结果允许 `locf` / `calendar_zero`，但必须写入 `basis`
- 缺失映射必须打治理标记，不允许吞掉

## 9. 数据版本

所有标准表和事实表都必须带：
- `source_version`
- `rule_version`
- `ingest_batch_id`
- `trace_id`（事实表可选但建议）

## 10. 反模式

- 不允许在 API 层直接读 raw Excel
- 不允许在前端写任何 H/A/T、FX、月均金额正式公式
- 不允许把 `CNX` 当成币种代码处理
- 不允许把 `516` 的符号逻辑留到展示层
