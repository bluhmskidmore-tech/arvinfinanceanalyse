# 黄金样本计划

## 1. 目标

黄金样本不是单元测试替代品，而是把当前仓库已经进入治理范围的主链，冻结成一组：

- 有明确 request
- 有冻结 response
- 有核心断言
- 有业务审批
- 可跨页面对账
- 可纳入 release gate

的“系统真值样本”。

## 2. 当前仓库现状

## 2.1 已经具备的样本基础

- `tests/test_golden_samples_capture_ready.py` 已经存在，并且会校验每个样本目录下的 `request.json`、`response.json`、`assertions.md`、`approval.md`。
- `tests/golden_samples/` 已经存在 11 个样本包：
  - `GS-BAL-OVERVIEW-A`
  - `GS-BAL-WORKBOOK-A`
  - `GS-PNL-OVERVIEW-A`
  - `GS-PNL-DATA-A`
  - `GS-BRIDGE-A`
  - `GS-BRIDGE-WARN-B`
  - `GS-RISK-A`
  - `GS-RISK-WARN-B`
  - `GS-EXEC-OVERVIEW-A`
  - `GS-EXEC-SUMMARY-A`
  - `GS-EXEC-PNL-ATTR-A`
- `scripts/backend_release_suite.py` 已经把 `tests/test_golden_samples_capture_ready.py` 纳入固定 release suite。

结论：当前缺的不是“从零开始做黄金样本”，而是把已有样本资产变成正式、版本化、可维护的治理体系。

## 2.2 当前缺口

- `docs/golden_sample_plan.md`、`docs/golden_sample_catalog.md`、`tests/golden_samples/` 当前都不在 `git ls-files` 结果中，说明它们还没有进入版本基线。
- 当前样本集中没有首页 `/` 的聚合样本。
- `GS-BOND-HEADLINE-A` 仍未冻结，根因不是没有 API，而是页面契约和指标映射还没补齐。
- 还没有把 `sample_id -> page_id -> metric_id -> test file` 做成强约束。

## 3. 什么样的样本才算“黄金样本”

一个合格黄金样本包必须同时包含：

1. 一个明确的业务目标。
2. 一个明确的 request。
3. 一个冻结的 `report_date`。
4. 一个冻结的 `basis`。
5. 一份冻结的 `result_meta`。
6. 一组必须断言的核心指标或结构。
7. 一份对账说明。
8. 一位审批人和审批日期。

如果缺少上述任一项，它最多只能算 fixture，不算黄金样本。

## 4. 当前 Batch A 覆盖范围

首批样本只覆盖“当前已有页面契约或已经明确进入 governed 主链”的面：

| sample_id | surface | 当前状态 | 当前证据 | 下一步动作 |
| --- | --- | --- | --- | --- |
| `GS-BAL-OVERVIEW-A` | `/ui/balance-analysis/overview` | 已有样本包 | `tests/test_balance_analysis_api.py` + `tests/golden_samples/GS-BAL-OVERVIEW-A/` | 纳入版本基线 |
| `GS-BAL-WORKBOOK-A` | `/ui/balance-analysis/workbook` | 已有样本包 | `tests/test_balance_analysis_workbook_contract.py` + 样本目录 | 纳入版本基线 |
| `GS-PNL-OVERVIEW-A` | `/api/pnl/overview` | 已有样本包 | `tests/test_pnl_api_contract.py` + 样本目录 | 纳入版本基线 |
| `GS-PNL-DATA-A` | `/api/pnl/data` | 已有样本包 | `tests/test_pnl_api_contract.py` + 样本目录 | 纳入版本基线 |
| `GS-BRIDGE-A` | `/api/pnl/bridge` | 已有样本包 | `tests/test_pnl_api_contract.py` + 样本目录 | 纳入版本基线 |
| `GS-BRIDGE-WARN-B` | `/api/pnl/bridge` | 已有样本包 | `tests/test_pnl_api_contract.py` + 样本目录 | 作为受控 warning profile 样本纳入版本基线 |
| `GS-RISK-A` | `/api/risk/tensor` | 已有样本包 | `tests/test_risk_tensor_service.py` + 样本目录 | 纳入版本基线 |
| `GS-RISK-WARN-B` | `/api/risk/tensor` | 已有样本包 | `tests/test_risk_tensor_api.py` + 样本目录 | 作为受控 warning profile 样本纳入版本基线 |
| `GS-EXEC-OVERVIEW-A` | `/ui/home/overview` | 已有样本包 | `tests/test_executive_service_contract.py` + 样本目录 | 与 page contract 对齐 |
| `GS-EXEC-SUMMARY-A` | `/ui/home/summary` | 已有样本包 | `tests/test_executive_service_contract.py` + 样本目录 | 与 page contract 对齐 |
| `GS-EXEC-PNL-ATTR-A` | `/ui/pnl/attribution` | 已有样本包 | `tests/test_executive_service_contract.py` + 样本目录 | 与 page contract 对齐 |

补充说明：

- `GS-BRIDGE-WARN-B` 和 `GS-RISK-WARN-B` 不是“坏样本”，而是刻意冻结的 degraded / warning profile。
- 它们用于保护“系统在 warning 条件下仍返回受控结果”的行为，不应用“只有全绿样本才算黄金样本”的思路误删。

## 5. 当前明确不纳入首批的面

| surface / sample | 当前状态 | 不纳入首批的原因 | 什么时候再纳入 |
| --- | --- | --- | --- |
| `/` 驾驶舱聚合页 | 暂不冻结 | 页面混合了 live、placeholder、excluded section，不适合作为第一批系统真值页 | 首页 page contract 明确“允许 section / 禁止 section”后 |
| `GS-BOND-HEADLINE-A` | 暂缓 | `bond analytics` 还没有补齐首版 page contract 与 metric mapping | `docs/page_contracts.md` 和 `docs/metric_dictionary.md` 补齐 bond analytics 后 |
| `/ui/risk/overview`、`/ui/home/alerts`、`/ui/home/contribution` | excluded / compat | 当前 cutover 边界外，按 `503` / reserved 处理，不应该伪装成 live 样本 | 真正进入 governed cutover 后 |

## 6. 样本目录标准

建议继续沿用当前目录结构，不新增平台层：

```text
tests/golden_samples/
  GS-BAL-OVERVIEW-A/
    request.json
    response.json
    assertions.md
    approval.md
```

四个文件的职责：

- `request.json`
  - 固定 query/body。
- `response.json`
  - 冻结 `result_meta` 与 `result`。
- `assertions.md`
  - 只写核心断言，不写页面废话。
- `approval.md`
  - 记录审批人、日期、审批口径和限制说明。

## 7. 样本与指标字典 / 页面契约的绑定规则

后续每个黄金样本必须绑定三张清单：

### 7.1 绑定 `page_id`

- 每个 `sample_id` 必须能回指一个页面契约或一个明确的 API surface。
- 如果一个样本只针对 API，不针对完整页面，也必须写明它属于哪个页面 section。

### 7.2 绑定 `metric_id`

- 每个 `assertions.md` 至少要列出本样本冻结的 `metric_id`。
- 首屏 KPI 样本必须优先冻结 headline 指标。
- 如果样本冻结的是结构而不是数值，也要写明它保护的是哪些 section key / DTO shape。

### 7.3 绑定自动化测试

- 每个 `sample_id` 必须能对应到至少一个现有测试文件。
- 没有测试挂点的样本，不算“可维护样本”。

## 8. 首批最小行动

### 8.1 本周必须完成

1. 把 `docs/golden_sample_plan.md`、`docs/golden_sample_catalog.md`、`tests/golden_samples/` 纳入版本控制。
2. 复核 9 个现有样本目录是否都符合 `request/response/assertions/approval` 结构。
3. 在 catalog 中补充每个样本对应的 `page_id`、`metric_id`、`tests/...`。

### 8.2 下周必须完成

1. 让 `GS-EXEC-*` 三个样本与首页聚合页页面契约明确脱钩，只服务各自 governed executive section。
2. 在 `bond analytics` 页面契约补齐前，不新增 `GS-BOND-HEADLINE-A`。
3. 为缺 page contract 的 live 页面建立“不可冻结样本”的显式说明，避免样本膨胀。

## 9. 与 release gate 的关系

当前仓库已经把 `tests/test_golden_samples_capture_ready.py` 纳入 `scripts/backend_release_suite.py`。

这意味着黄金样本不是“参考资料”，而是 release evidence 的一部分。为了让这件事成立，需要满足两点：

- 样本目录必须进入版本基线。
- 样本目录必须和页面契约、指标字典保持同步。

## 10. 结论

当前仓库已经有首批黄金样本雏形，也已经有自动化检查入口。下一步不该扩张范围，而该先把现有样本：

- 版本化
- 绑定页面契约
- 绑定指标字典
- 绑定 release gate

做到真正可信。
