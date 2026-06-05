# Next Window Prompt: Balance Analysis Closeout And Commit Preparation

把下面整段作为新窗口的首条消息发送给 Codex。

---

你在 `F:\MOSS-V3` 工作。先严格遵循仓库 `AGENTS.md` 和作用域内更深层 `AGENTS.md`。

当前工作流是 `zqtz / tyw` governed `balance-analysis` closeout。不要扩到无关 workstream。不要做 broad frontend rollout。不要实现 `advanced_attribution_bundle`。不要触碰与本次 `balance-analysis` slice 无关的改动。

## 当前 grounded state

`balance-analysis` governed workbook 当前已经支持：

- `bond_business_types`
- `maturity_gap`
- `cashflow_calendar`
- `currency_split`
- `issuer_concentration`
- `liquidity_layers`
- `regulatory_limits`
- `overdue_credit_quality`
- `overdue_credit_quality_ratings`
- `vintage_analysis`
- `customer_attribute_analysis`
- `portfolio_comparison`
- `account_category_comparison`
- `ifrs9_classification`
- `ifrs9_position_scope`
- `ifrs9_source_family`
- `rule_reference`

当前 docs 只把以下内容留在 gap：

- `advanced_attribution_bundle`

当前已验证状态：

```powershell
pytest tests -q
pnpm --dir frontend typecheck
```

最近本地结果是：

```text
461 passed in 221.60s
frontend typecheck passed
```

## 重要背景

当前工作区是脏的，存在很多与 `balance-analysis` 无关的改动。你的目标不是“处理所有未提交文件”，而是只处理这次 `balance-analysis` 最小可提交范围。

## 本次只允许关注的文件

只在下面这些文件里工作；其余改动一律视为外部噪音，不要回滚，不要顺带整理，不要一起提交：

- `backend/app/core_finance/balance_analysis.py`
- `backend/app/core_finance/balance_analysis_workbook.py`
- `backend/app/repositories/balance_analysis_repo.py`
- `backend/app/repositories/snapshot_repo.py`
- `backend/app/services/balance_analysis_service.py`
- `docs/BALANCE_ANALYSIS_SPEC_FOR_CODEX.md`
- `docs/BALANCE_ANALYSIS_RECONCILIATION_2026-03-01.md`
- `docs/data_contracts.md`
- `docs/plans/2026-04-12-balance-analysis-advanced-attribution-boundary.md`
- `tests/test_balance_analysis_contracts.py`
- `tests/test_balance_analysis_docs_contract.py`
- `tests/test_balance_analysis_materialize_flow.py`
- `tests/test_balance_analysis_workbook_contract.py`

## 目标

完成一次干净的 `balance-analysis` closeout：

1. 重新审查上述最小文件范围内的改动
2. 找出真实 bug / 回归 / contract 风险
3. 若发现问题，只在允许范围内最小修复
4. 重新跑验证
5. 如果验证通过，**只 stage 上述最小范围文件**
6. 产出一条可直接使用的 Lore-format commit message

不要 push，不要开 PR，不要处理无关文件。

## 必查风险点

至少检查下面这些点：

1. `fact_formal_zqtz_balance_daily` 老 schema 兼容：
   - 缺列时是否能自动补 `account_category`
   - insert 是否使用显式列名，避免旧列顺序错位
2. `account_category_comparison` 是否只消费 formal fact，而不是 snapshot 泄漏
3. `regulatory_limits` 是否明确仍是参考值 / proxy，而不是完整监管引擎
4. `ifrs9_classification` 是否没有偷偷引入 `ecl_stage` 或 `account_category` 伪真值
5. docs 是否和当前代码一致：
   - 支持 section 列表
   - future gap 列表
6. 测试是否覆盖：
   - workbook contract
   - docs contract
   - old-schema materialize compatibility

## 必跑验证

先跑最小相关验证：

```powershell
pytest tests/test_balance_analysis_contracts.py tests/test_balance_analysis_docs_contract.py tests/test_balance_analysis_workbook_contract.py tests/test_balance_analysis_api.py tests/test_balance_analysis_service.py tests/test_balance_analysis_excel_export.py tests/test_balance_analysis_materialize_flow.py -q
```

然后跑全量：

```powershell
pytest tests -q
pnpm --dir frontend typecheck
```

## 如果验证通过

只 stage 本次最小范围文件。不要 stage 其他文件。

可用的 stage 目标范围就是本 prompt 上面列出的 13 个文件。

然后给出一条 Lore-format commit message，要求：

- 第一行写“为什么”
- body 简要说明 approach
- trailers 至少包含：
  - `Confidence:`
  - `Scope-risk:`
  - `Directive:`
  - `Tested:`
  - `Not-tested:`

## 输出要求

最终回复必须包含：

- 变更文件列表
- 新增或修改的测试列表
- 测试结果
- 风险点
- 是否影响正式金融口径
- 未完成项
- 下一轮建议
- 若验证通过，再附：
  - staged 文件清单
  - 一条可直接使用的 Lore-format commit message

如果你发现这批最小范围里仍有阻塞问题，不要 commit，先修到通过再停。

---
