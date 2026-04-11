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

### 文档归属

- 本文是标准化表与事实表结构语义的唯一契约文档；对外 `result_meta` / cache semantics 不在本文定义。
- 对 `zqtz_bond_daily_snapshot` 与 `tyw_interbank_daily_snapshot`，本文是以下内容的唯一 normative owner：
  - 表层级归属
  - canonical grain
  - hard-required lineage
  - 直接允许 / 禁止消费者
  - `required now / deferred enrichment / formal-only derived later`
- `basis / formal_use_allowed / scenario_flag` 属于对外读面与缓存语义，由 [CACHE_SPEC.md](CACHE_SPEC.md) 统一定义；本文只引用，不重复维护独立真值表。
- 若其他文档需要引用 snapshot 合同，应按本文引用，不应再维护第二套字段、主键、lineage 或消费者规则清单。

## 4. 标准表清单

### 4.1 zqtz_bond_daily_snapshot

用途：债券逐日快照。

层级归属：
- 属于 `Standardized`
- 属于 canonical standardized storage
- 不是 analytical output
- 不是 formal fact

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
- `face_value_native` decimal(24,8)
- `market_value_native` decimal(24,8)
- `amortized_cost_native` decimal(24,8)
- `accrued_interest_native` decimal(24,8)
- `coupon_rate` decimal(18,8)
- `ytm_value` decimal(18,8)
- `maturity_date` date
- `next_call_date` date
- `overdue_days` integer
- `is_issuance_like` boolean
- `interest_mode` varchar
- `source_version` varchar

hard-required lineage：
- `source_version`
- `rule_version`
- `ingest_batch_id`
- `trace_id`

canonical grain：
- `(report_date, instrument_code, portfolio_name, cost_center, currency_code)`

first-wave required now：
- `report_date`
- `instrument_code`
- `portfolio_name`
- `cost_center`
- `currency_code`
- `face_value_native`
- `market_value_native`
- `amortized_cost_native`
- `accrued_interest_native`
- `is_issuance_like`

deferred enrichment：
- `issuer_name`
- `industry_name`
- `rating`
- `interest_mode`
- `next_call_date`
- `overdue_days`

formal-only derived later：
- `invest_type_std`
- `accounting_basis`
- `position_scope`
- `currency_basis`

直接允许消费者：
- formal balance materialize / `core_finance` 输入
- 治理 / 数据质量校验

直接禁止消费者：
- `executive.*`
- workbench read model
- formal-facing service adapter
- 任何把该表直接重标成 formal result 的服务路径

单位约定：
- 金额字段为原币金额
- `ytm_value`、`coupon_rate` 统一为小数口径

### 4.2 tyw_interbank_daily_snapshot

用途：同业/资金逐日快照。

层级归属：
- 属于 `Standardized`
- 属于 canonical standardized storage
- 不是 analytical output
- 不是 formal fact

关键字段：
- `report_date`
- `position_id`
- `product_type`
- `position_side`
- `counterparty_name`
- `account_type`
- `special_account_type`
- `core_customer_type`
- `currency_code`
- `principal_native`
- `accrued_interest_native`
- `funding_cost_rate`
- `maturity_date`
- `pledged_bond_code`
- `source_version`

hard-required lineage：
- `source_version`
- `rule_version`
- `ingest_batch_id`
- `trace_id`

canonical grain：
- `(report_date, position_id)`

first-wave required now：
- `report_date`
- `position_id`
- `product_type`
- `position_side`
- `counterparty_name`
- `currency_code`
- `principal_native`
- `accrued_interest_native`
- `maturity_date`

deferred enrichment：
- `account_type`
- `special_account_type`
- `pledged_bond_code`
- `funding_cost_rate`

formal-only derived later：
- `invest_type_std`
- `accounting_basis`
- `position_scope`
- `currency_basis`

直接允许消费者：
- formal balance materialize / `core_finance` 输入
- 治理 / 数据质量校验

直接禁止消费者：
- `executive.*`
- workbench read model
- formal-facing service adapter
- 任何把该表直接重标成 formal result 的服务路径

### 4.3 fact_formal_zqtz_balance_daily

用途：`zqtz` 正式资产负债分析逐日事实表。

状态：
- 属于当前 governed formal fact contract
- 当前仓库已实现基于该表的 materialize 与 governed balance-analysis service / API；本文继续作为结构 contract 来源

层级归属：
- 属于 `Curated / Fact`
- 属于 formal fact
- 不是 preview output
- 不是 snapshot storage

上游输入边界：
- `zqtz_bond_daily_snapshot`
- `fx_daily_mid`
- 治理字段 / 已批准 mapping / manual adjustment（若后续设计引入）
- 不允许读取任何 `phase1_*preview*` 表

canonical grain：
- `(report_date, instrument_code, portfolio_name, cost_center, currency_basis, position_scope)`

first-wave required now：
- `report_date`
- `instrument_code`
- `portfolio_name`
- `cost_center`
- `invest_type_std`
- `accounting_basis`
- `position_scope`
- `currency_basis`
- `currency_code`
- `face_value_amount`
- `market_value_amount`
- `amortized_cost_amount`
- `accrued_interest_amount`
- `coupon_rate`
- `ytm_value`
- `maturity_date`
- `interest_mode`
- `is_issuance_like`
- `source_version`
- `rule_version`
- `ingest_batch_id`
- `trace_id`

deferred enrichment：
- `instrument_name`
- `asset_class`
- `bond_type`
- `issuer_name`
- `industry_name`
- `rating`
- `next_call_date`
- `overdue_days`

直接允许消费者：
- balance-analysis repository / `core_finance` read-model 组装
- 治理 / 数据质量校验
- 受治理的 balance-analysis repository / service path（当前已落地）

直接禁止消费者：
- preview page
- snapshot read API
- `executive.*`
- scenario result writer
- 任何把 standardized snapshot 直接冒充 formal fact 的服务路径

说明：
- `market_value_amount` / `amortized_cost_amount` / `accrued_interest_amount` 的单位由 `currency_basis` 决定。
- 当 `currency_basis = CNY` 时，金额必须已经过正式 FX 逐日折算，不允许“先月均后换汇”。
- `position_scope` 只允许 `asset / liability / all`。

### 4.4 fact_formal_tyw_balance_daily

用途：`tyw` 正式资产负债分析逐日事实表。

状态：
- 属于当前 governed formal fact contract
- 当前仓库已实现基于该表的 materialize 与 governed balance-analysis service / API；本文继续作为结构 contract 来源

层级归属：
- 属于 `Curated / Fact`
- 属于 formal fact
- 不是 preview output
- 不是 snapshot storage

上游输入边界：
- `tyw_interbank_daily_snapshot`
- `fx_daily_mid`
- 治理字段 / 已批准 mapping / manual adjustment（若后续设计引入）
- 不允许读取任何 `phase1_*preview*` 表

canonical grain：
- `(report_date, position_id, currency_basis, position_scope)`

first-wave required now：
- `report_date`
- `position_id`
- `product_type`
- `position_side`
- `counterparty_name`
- `invest_type_std`
- `accounting_basis`
- `position_scope`
- `currency_basis`
- `currency_code`
- `principal_amount`
- `accrued_interest_amount`
- `account_type`
- `special_account_type`
- `core_customer_type`
- `funding_cost_rate`
- `maturity_date`
- `source_version`
- `rule_version`
- `ingest_batch_id`
- `trace_id`

deferred enrichment：
- `pledged_bond_code`

直接允许消费者：
- balance-analysis repository / `core_finance` read-model 组装
- 治理 / 数据质量校验
- 受治理的 balance-analysis repository / service path（当前已落地）

直接禁止消费者：
- preview page
- snapshot read API
- `executive.*`
- scenario result writer
- 任何把 standardized snapshot 直接冒充 formal fact 的服务路径

说明：
- `principal_amount` / `accrued_interest_amount` 的单位由 `currency_basis` 决定。
- `position_scope` 由正式规则从 `position_side` 与治理映射生成，不允许在前端临时推导。
- `funding_cost_rate` 若参与正式读模型，必须在 `core_finance/` 中消费，不得在 service 或 UI 中直接写公式。

### 4.5 fi_pnl_record

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

- 对外 `basis / formal_use_allowed / scenario_flag` 语义以 [CACHE_SPEC.md](CACHE_SPEC.md) 为准；本文不单独维护独立真值表。
- `fi_pnl_record` 只承载 formal-scoped rows，scenario / analytical 结果不得写入该表，也不得复用它的 key 语义。

规则：
- `invest_type_std` 由正式映射规则生成
- `fi_pnl_record.total_pnl` 仅表示 standardized total = `514 + 516 + 517 + manual_adjustment`，不直接等于 formal-recognized total；formal-recognized total 由 `fact_formal_pnl_fi.total_pnl` 表示。

- `fi_pnl_record` 的 canonical grain = `(report_date, instrument_code, portfolio_name, cost_center, currency_basis)`
- `fair_value_change_516` 是 standardized component，不天然等于 formal-recognized pnl
- `capital_gain_517` 是 standardized realized component，是否进入 formal 取决于 `accounting_basis` 与 event semantics
- `manual_adjustment` 只有在治理/审批状态字段（如 `approval_status` / `governance_status`）为 approved 时才可进入 formal total；未批准 adjustment 不进入 formal total_pnl。

### 4.6 nonstd_journal_entry

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

- `nonstd_journal_entry` 是 standardized ledger grain，不是 formal fact grain。

### 4.7 ledger_daily_pnl

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

### 4.7A qdb_gl_baseline_input

用途：QDB GL baseline 原始输入合同，仅用于 `source-binding + input-contract validation`。

标签：
- `QDB baseline convention`

层级归属：
- 属于 `Raw baseline input contract`
- 不是 standardized table
- 不是 formal fact
- 不是 analytical/read-model output

source kind：
- `ledger_reconciliation` -> `总账对账YYYYMM.xlsx`
- `average_balance` -> `日均YYYYMM.xlsx`

文件级绑定规则：
- `ledger_reconciliation` 只绑定 canonical sheets：
  - `综本`
  - `人民币`
- `average_balance` 只绑定 canonical sheets：
  - `年`
  - `月`
- canonical sheet 缺失时，`source_binding` 必须直接失败。
- 识别失败的文件不得静默降级为 baseline input。

`ledger_reconciliation` header / row-shape：
- row 6 的前 7 列必须依次为：
  - `组合科目代码`
  - `组合科目名称`
  - `币种`
  - `期初余额`
  - `本期借方`
  - `本期贷方`
  - `期末余额`
- 数据行从 row 7 开始。
- 前 7 列是 baseline core contract。
- baseline core contract 之外允许存在 auxiliary trailing columns，但它们不得替代或覆盖前 7 列语义。

`ledger_reconciliation` required raw fields：
- `account_code_raw`
- `account_name_raw`
- `currency_raw`
- `beginning_balance_raw`
- `period_debit_raw`
- `period_credit_raw`
- `ending_balance_raw`

`average_balance` header / row-shape：
- `年` / `月` sheet 的 row 3 必须按 4 列 block 重复：
  - `币种`
  - `科目`
  - `科目日均余额`
  - blank spacer
- 最后一个 block 允许只有前 3 列，不强制追加尾部 spacer。
- 数据行从 row 4 开始。
- populated block 不允许缺字段，也不允许 spacer 列带值。

`average_balance` required raw fields：
- `currency_raw`
- `account_code_raw`
- `avg_balance_raw`

account-code text preservation：
- `account_code_raw` 必须以 digit-only text 解释。
- 不允许 scientific notation。
- 不允许带小数位的数值型科目号。
- 不允许在 admissibility 层把科目号改写成 float / Decimal 展示文本。

currency grouping：
- baseline 只允许 `CNX` / `CNY` 两个 currency groups。
- `ledger_reconciliation` 的 canonical sheet 行内 `currency_raw` 必须与 sheet 绑定币组一致。
- admissible workbook 必须同时暴露 `CNX` 与 `CNY` 两个 canonical currency groups。

reconciliation / status-label contract：
- `ledger_reconciliation` 每一行必须满足：
  - `期初余额 + 本期借方 - 本期贷方 = 期末余额`
- 允许 `±0.01` rounding tolerance。
- `average_balance` 不承载该勾稽公式，相关 evidence 的 `status_label` 只能为 `not_applicable`。
- contract evidence 允许的 `status_label` 仅有：
  - `pass`
  - `fail`
  - `not_applicable`

lineage for contract-level pass/fail evidence：
- `source_file`
- `source_kind`
- `report_month`
- `source_version`
- `rule_version`
- `trace_id`
- `sheet_name`
- `row_locator`

直接允许消费者：
- 内部 source-binding / input-contract validation seam
- 数据治理 / admissibility evidence

直接禁止消费者：
- normalization / classification runtime
- storage / materialization runtime
- analytical/read-model output
- formal-upstream integration
- API / frontend consumer rollout

### 4.8 fx_daily_mid

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

### 4.9 choice_market_snapshot / choice_market_curve

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
- `fact_formal_zqtz_balance_daily`
- `fact_formal_tyw_balance_daily`
- `fact_formal_pnl_fi`
- `fact_nonstd_pnl_bridge`
- `fact_fx_converted_positions_daily`
- `fact_pnl_bridge_daily`
- `fact_risk_tensor_daily`
- `fact_formal_analytical_bridge_daily`

- `fact_formal_zqtz_balance_daily` grain = `(report_date, instrument_code, portfolio_name, cost_center, currency_basis, position_scope)`
- `fact_formal_tyw_balance_daily` grain = `(report_date, position_id, currency_basis, position_scope)`
- `fact_formal_pnl_fi` grain = `(report_date, instrument_code, portfolio_name, cost_center, currency_basis)`
- `fact_nonstd_pnl_bridge` grain = `(report_date, bond_code, portfolio_name, cost_center)`
- `fact_nonstd_pnl_bridge` 是 bridge / aggregation fact，不是 raw ledger 明细。

### 5.1 Preview / Snapshot / Formal 三层关系

用途：定义 `zqtz / tyw` 在仓库中的三层位置关系，避免把 preview、snapshot、formal 写成同一层。

规则：
- preview surface 只用于解释、审阅、规则命中与 trace，下游不直接当作 canonical input。
- `zqtz_bond_daily_snapshot` 与 `tyw_interbank_daily_snapshot` 属于 standardized canonical storage，是后续正式计算的输入边界，不是 analytical output。
- formal facts 才属于正式结果域；snapshot 不得被直接重标成 formal result。
- `fact_formal_zqtz_balance_daily` 与 `fact_formal_tyw_balance_daily` 只允许读取 snapshot + 正式 FX / 治理输入，不允许读取 `phase1_*preview*`。
- `fact_formal_zqtz_balance_daily` 与 `fact_formal_tyw_balance_daily` 是当前 governed formal balance-analysis 的唯一事实输入边界；workbench 只能经由 governed service / API 消费它们，不得直接消费 snapshot 充当 formal 结果。
- 对外 `basis / formal_use_allowed / scenario_flag`、cache identity、cache namespace 语义由 [CACHE_SPEC.md](CACHE_SPEC.md) 统一定义。
- 若未来存在 snapshot read API，API envelope 可以带 outward `basis / result_meta` 语义，但这不改变 snapshot 表本身的层级归属。

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

### zqtz formal balance 主键
```text
(report_date, instrument_code, portfolio_name, cost_center, currency_basis, position_scope)
```

### tyw formal balance 主键
```text
(report_date, position_id, currency_basis, position_scope)
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
