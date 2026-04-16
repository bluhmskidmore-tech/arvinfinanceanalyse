# Next Window Prompt: Balance Analysis Residual Closeout

把下面整段作为新窗口的首条消息发送给 Codex。

---

你在 `F:\MOSS-V3` 工作。先严格遵循仓库 `AGENTS.md` 和作用域内更深层 `AGENTS.md`。

当前工作流是 `zqtz / tyw` formal balance-analysis reconciliation closeout。不要扩到无关 workstream。不要做 broad frontend rollout。不要改无关功能。

## 当前状态

已经完成：

- `2026-03-01` 真实源文件已接入对账：
  - `C:/Users/arvin/Desktop/ZQTZSHOW-20260301.xls`
  - `C:/Users/arvin/Desktop/TYWLSHOW-20260301.xls`
  - `C:/Users/arvin/Desktop/资产负债分析_20260301_1.xlsx`
- workbook 读面已对齐大部分结果：
  - 总览卡片
  - 债券业务种类金额
  - 评级金额
  - 行业金额
  - 对手方净头寸
  - 计息方式金额
  - 期限缺口
  - Campisi spread / spread income
- 全仓测试已 fresh 通过：

```powershell
pytest tests -q
```

最近验证结果是：

```text
314 passed in 165.20s (0:02:45)
```

## 唯一剩余问题

只剩一个很小的 reconciliation 残差：

- 债券业务种类页 `其他` 的 `加权期限(年)`
- 系统值：`4.497542197779637719121830875`
- Excel 值：`4.497201648705183`
- 差值：`0.000340549074455` 年

这是 display/day-count 级别的小残差，不是金额错位。

## 已知根因边界

以下都已经确认并修过，不要重复走回头路：

1. workbook 通用页用 `native` 金额口径，币种拆分页单独用 `CNY`
2. `发行类债券` 已正确识别为 issuance-like
3. `同业存放` 已归为 liability
4. `其他` 的加权期限已经忽略：
   - 空 `到期日`
   - `到期日 < 报告日` 的记录
5. Campisi benchmark 已固定为 `政策性金融债`

## 目标

只处理这一个残差，尽量做到：

- 把 `其他` 加权期限进一步对齐到 Excel
- 若确认只是 Excel 显示/舍入差异，给出证据并把残差解释写进文档

不要因为这个小残差重构整条链路。

## 建议排查顺序

1. 重新读取：
   - `backend/app/core_finance/balance_analysis_workbook.py`
   - `docs/BALANCE_ANALYSIS_RECONCILIATION_2026-03-01.md`
   - `tests/test_balance_analysis_workbook_contract.py`
2. 用真实桌面文件重跑 `2026-03-01` 对账
3. 只聚焦 `bond_type == "其他"` 的记录
4. 逐项验证以下可能性：
   - Excel 是否按不同 day-count 分母
   - Excel 是否对单条期限先舍入再加权
   - Excel 是否对某些 `其他` 子类使用不同期限字段
   - Excel 是否剔除了某些特定 `其他` 子类记录
5. 先写 failing test，再最小改动实现

## 必须保留的业务口径

- `应收投资款项 -> H / AC`
- `发行类债券 -> liability-scoped issue read model，不回资产端`

## 验收标准

至少满足其一：

1. `其他` 加权期限与 Excel 对齐到可忽略误差
2. 证明现有差值仅来自 Excel 显示/舍入方式，并把证据写入 reconciliation 文档

## 必跑验证

```powershell
pytest tests/test_balance_analysis_workbook_contract.py -q
pytest tests/test_balance_analysis_contracts.py tests/test_balance_analysis_core.py tests/test_balance_analysis_materialize_flow.py tests/test_balance_analysis_api.py tests/test_balance_analysis_service.py tests/test_balance_analysis_boundary_guards.py tests/test_balance_analysis_workbook_contract.py -q
pnpm --dir F:\MOSS-V3\frontend test -- BalanceAnalysisPage ApiClient
pnpm --dir F:\MOSS-V3\frontend typecheck
pytest tests -q
```

## 输出要求

最终回复必须包含：

- 变更文件列表
- 新增或修改的测试列表
- 测试结果
- 风险点
- 是否影响正式金融口径
- 未完成项
- 下一轮建议

如果你判断不值得再改正式逻辑，也必须给出具体证据，而不是直接说“可以忽略”。

---
