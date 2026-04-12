# Balance Analysis Remaining Work Cursor Prompt Pack

把下面各段分别作为 Cursor 的首条消息使用。一次只跑一个 prompt，完成一张卡后停下并回传 diff / 测试结果，再继续下一张。

## 当前 grounded state

当前仓库在 `balance-analysis` governed lane 上已经落地：

- `maturity_gap` 全口径负债扩展
- `cashflow_calendar`
- `issuer_concentration`
- `rule_reference`
- `ifrs9_classification`
- `account_category_comparison`

当前支持边界已经记录在：

- [docs/BALANCE_ANALYSIS_SPEC_FOR_CODEX.md](/F:/MOSS-V3/docs/BALANCE_ANALYSIS_SPEC_FOR_CODEX.md)
- [docs/data_contracts.md](/F:/MOSS-V3/docs/data_contracts.md)
- [docs/plans/2026-04-12-balance-analysis-gap-closure.md](/F:/MOSS-V3/docs/plans/2026-04-12-balance-analysis-gap-closure.md)

当前仍未支持的未来 section，至少包括：

- `liquidity_layers`
- `regulatory_limits`

执行约束：

- 严格遵守 `AGENTS.md`
- 只在 `balance-analysis` governed lane 内工作
- 不要起新的旁路批处理系统
- 正式逻辑只放在 `backend/app/core_finance/`
- DuckDB 写入只允许经 `backend/app/tasks/`
- 完成每张 prompt 后停止，不要自动推进下一张

## 推荐执行顺序

1. Prompt 1: `liquidity_layers`
2. Prompt 2: `regulatory_limits`
3. Prompt 3: `overdue_credit_quality`
4. Prompt 4: `vintage_analysis`
5. Prompt 5: `customer_attribute_analysis`
6. Prompt 6: `portfolio_comparison`
7. Prompt 7: `ifrs9_deepening`
8. Prompt 8: `advanced_attribution_bundle`

---

## Cursor Prompt 1: Liquidity Layers

你在 `F:\MOSS-V3` 工作。先严格遵循仓库 `AGENTS.md` 和作用域内更深层 `AGENTS.md`。

当前工作流是 `zqtz / tyw` governed `balance-analysis` workbook 扩展。不要扩到无关 workstream。不要做 broad frontend rollout。不要创建新系统目录。

### 目标

新增一个 governed workbook section：`liquidity_layers`。

要求：

- section key: `liquidity_layers`
- 仅使用当前 formal workbook 输入行，不直读 snapshot
- 先做最小可用版，不要引入新依赖

### 口径

用当前 `zqtz` asset rows 做初版分类：

- `Level 1`: `国债` / `政策性金融债` / `凭证式国债`
- `Level 2A`: `地方政府债`
- `Level 2B`: `同业存单` + 高评级信用债
- `其他`: 其余资产

初版高评级信用债可先按：

- `rating in ("AAA", "AA+")`

初版输出字段至少包括：

- `liquidity_layer`
- `row_count`
- `balance_amount`
- `share_of_bond_assets`
- `weighted_rate_pct`
- `hqla_haircut`
- `hqla_amount`

其中 haircut 先用：

- `Level 1 = 1.00`
- `Level 2A = 0.85`
- `Level 2B = 0.75`
- `其他 = 0`

### 建议改动文件

- `backend/app/core_finance/balance_analysis_workbook.py`
- `tests/test_balance_analysis_workbook_contract.py`
- `tests/test_balance_analysis_docs_contract.py`
- `docs/BALANCE_ANALYSIS_SPEC_FOR_CODEX.md`

### 必须流程

1. 先写 failing test
2. 跑单测确认失败
3. 最小实现
4. 同步 docs 支持边界
5. 跑回归
6. 停止并汇报

### 必跑验证

```powershell
pytest tests/test_balance_analysis_workbook_contract.py -q
pytest tests/test_balance_analysis_docs_contract.py tests/test_balance_analysis_workbook_contract.py tests/test_balance_analysis_excel_export.py -q
```

### 输出要求

- 变更文件列表
- 新增或修改的测试列表
- 测试结果
- 风险点
- 是否影响正式金融口径
- 未完成项
- 下一轮建议

---

## Cursor Prompt 2: Regulatory Limits

你在 `F:\MOSS-V3` 工作。先严格遵循仓库 `AGENTS.md` 和作用域内更深层 `AGENTS.md`。

当前工作流是 `zqtz / tyw` governed `balance-analysis` workbook 扩展。不要扩到无关 workstream。

### 目标

新增一个 governed workbook section：`regulatory_limits`。

### 口径

先做最小、可验证的参考值表，不要假装已经有完整监管引擎。

至少包含这些行：

- `top1_concentration`
- `interbank_liability_ratio`
- `usd_exposure_ratio`
- `portfolio_modified_duration`

每行至少输出：

- `metric_key`
- `metric_name`
- `current_value`
- `threshold_value`
- `status`
- `calculation_note`

允许的阈值：

- `top1_concentration = 0.15`
- `interbank_liability_ratio = 0.25`
- `usd_exposure_ratio = 0.05`
- `portfolio_modified_duration = 5.0`

### 数据来源

- `issuer_concentration` / asset totals / interbank totals / currency split / risk tensor
- 不要从前端现算
- 如果要复用现有 risk-tensor / workbook 结果，保持在后端读模型里完成

### 建议改动文件

- `backend/app/core_finance/balance_analysis_workbook.py`
- `tests/test_balance_analysis_workbook_contract.py`
- `tests/test_balance_analysis_docs_contract.py`
- `docs/BALANCE_ANALYSIS_SPEC_FOR_CODEX.md`

### 必跑验证

```powershell
pytest tests/test_balance_analysis_workbook_contract.py -q
pytest tests/test_balance_analysis_docs_contract.py tests/test_balance_analysis_workbook_contract.py tests/test_balance_analysis_excel_export.py -q
```

停止在该 prompt 内，不要顺带做流动性预警联动或 UI 大改。

---

## Cursor Prompt 3: Overdue Credit Quality

你在 `F:\MOSS-V3` 工作。先严格遵循仓库 `AGENTS.md` 和作用域内更深层 `AGENTS.md`。

### 目标

新增一个 governed workbook section：`overdue_credit_quality`。

### 前提提醒

当前 formal ZQTZ balance fact 还没有把 `overdue_days` 系列正式透传成 first-wave required 字段。你要先确认：

- 是不是已有足够 formal 字段可直接做
- 如果没有，就先最小扩 `fact_formal_zqtz_balance_daily` 合同，再做 workbook section

### section 最小要求

至少输出两块信息：

1. 逾期明细
2. 评级 / 信用质量汇总

最小字段可包括：

- `instrument_code`
- `instrument_name`
- `bond_type`
- `rating`
- `overdue_principal_days`
- `overdue_interest_days`
- `balance_amount`

### 重要约束

- 不允许 workbook 直接回读 snapshot 充当 formal 结果
- 如果 formal fact 不带该字段，先补 formal contract、repo schema、materialize、service reconstruction，再做 workbook
- 先写 failing tests 覆盖老 schema 兼容

### 建议改动文件

- `backend/app/core_finance/balance_analysis.py`
- `backend/app/repositories/balance_analysis_repo.py`
- `backend/app/services/balance_analysis_service.py`
- `backend/app/core_finance/balance_analysis_workbook.py`
- `docs/data_contracts.md`
- `tests/test_balance_analysis_contracts.py`
- `tests/test_balance_analysis_materialize_flow.py`
- `tests/test_balance_analysis_workbook_contract.py`

### 必跑验证

```powershell
pytest tests/test_balance_analysis_contracts.py tests/test_balance_analysis_materialize_flow.py tests/test_balance_analysis_workbook_contract.py -q
pytest tests/test_balance_analysis_api.py tests/test_balance_analysis_service.py tests/test_balance_analysis_excel_export.py -q
```

---

## Cursor Prompt 4: Vintage Analysis

你在 `F:\MOSS-V3` 工作。先严格遵循仓库 `AGENTS.md` 和作用域内更深层 `AGENTS.md`。

### 目标

新增一个 governed workbook section：`vintage_analysis`。

### 前提提醒

当前 formal ZQTZ balance fact 未明确保留 `start_date` / 起息日。先确认字段链路；若没有，就先做最小 formal contract 扩展，再做 read model。

### section 最小要求

按起息年份分组，至少输出：

- `start_year`
- `row_count`
- `balance_amount`
- `weighted_rate_pct`
- `weighted_term_years`

### 约束

- 只做 balance-analysis governed lane
- 不做趋势图，不做前端大改
- 如果需要 schema 兼容，补旧表 migration 测试

### 必跑验证

```powershell
pytest tests/test_balance_analysis_contracts.py tests/test_balance_analysis_materialize_flow.py tests/test_balance_analysis_workbook_contract.py -q
```

---

## Cursor Prompt 5: Customer Attribute Analysis

你在 `F:\MOSS-V3` 工作。先严格遵循仓库 `AGENTS.md` 和作用域内更深层 `AGENTS.md`。

### 目标

新增一个 governed workbook section：`customer_attribute_analysis`。

### 前提提醒

当前 formal ZQTZ balance fact 未明确保留 `customer_type` / 授信客户属性。先确认 formal fact 是否已有；若无，则按 governed formal path 最小扩字段。

### section 最小要求

按客户属性分组，至少输出：

- `customer_attribute`
- `row_count`
- `balance_amount`
- `weighted_rate_pct`
- `weighted_term_years`

### 约束

- 不允许 snapshot 直读
- 先写 failing contract test
- 若做 formal field 扩展，必须覆盖旧 schema migration

---

## Cursor Prompt 6: Portfolio Comparison

你在 `F:\MOSS-V3` 工作。先严格遵循仓库 `AGENTS.md` 和作用域内更深层 `AGENTS.md`。

### 目标

新增一个 governed workbook section：`portfolio_comparison`。

### 数据前提

优先使用已有 formal fields：

- `portfolio_name`
- `invest_type_std`
- `accounting_basis`
- `face_value_amount`
- `coupon_rate`
- `maturity_date`

### section 最小要求

按 `portfolio_name` 分组，至少输出：

- `portfolio_name`
- `row_count`
- `balance_amount`
- `weighted_rate_pct`
- `weighted_term_years`
- `floating_pnl_amount`

不要在这一步引入新的风险张量 join 或高级 attribution。

---

## Cursor Prompt 7: IFRS9 Deepening

你在 `F:\MOSS-V3` 工作。先严格遵循仓库 `AGENTS.md` 和作用域内更深层 `AGENTS.md`。

### 目标

在当前最小 `ifrs9_classification` section 基础上做第二层增强，但不要越界到 ECL engine。

### 范围

允许增强：

- 增加 `share_of_total`
- 增加 `source_family` 分层汇总
- 增加 asset/liability 分层

不允许在这一步实现：

- `ecl_stage`
- IFRS9 三阶段减值推断
- 账户类别逻辑复用成新的正式真值源

### 必跑验证

```powershell
pytest tests/test_balance_analysis_workbook_contract.py -q
pytest tests/test_balance_analysis_docs_contract.py tests/test_balance_analysis_workbook_contract.py tests/test_balance_analysis_excel_export.py -q
```

---

## Cursor Prompt 8: Advanced Attribution Bundle

你在 `F:\MOSS-V3` 工作。先严格遵循仓库 `AGENTS.md` 和作用域内更深层 `AGENTS.md`。

### 目标

只做高级归因的前置条件核查和 prompt 内最小收敛，不要直接假装 `carry / roll-down / reinvestment` 已经 ready。

### 任务

1. 先读取：
   - `backend/app/services/bond_analytics_service.py`
   - `backend/app/core_finance/bond_analytics/read_models.py`
   - `docs/plans/2026-04-12-balance-analysis-gap-closure.md`
2. 确认当前哪些字段仍是 placeholder / zero-filled
3. 只补一份 docs-only / test-only contract：
   - 哪些 workbook section 依赖 Phase 3 数据
   - 哪些 section 当前绝不能宣称已实现

### 明确禁止

- 不要直接把 `roll_down / rate_effect / spread_effect` 从 0 改成看起来合理的数
- 不要发明曲线或 trade 粒度数据
- 不要把 `advanced_attribution_bundle` 伪装成 balance-analysis 已支持 section

### 交付物

- 一份新的 docs/plans prompt 或 design note
- 必要的 docs contract 测试

---

## 使用方式

- 一次只发一张 prompt 给 Cursor
- 每张 prompt 完成后停下
- 把 Cursor 返回的 diff、测试结果和风险点拿回来，再决定是否继续下一张
