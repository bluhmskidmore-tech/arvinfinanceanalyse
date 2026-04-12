# Remaining Worktree Closeout Cursor Prompt (V2)

把下面整段作为 Cursor 新窗口的首条消息发送。

---

你在 `F:\MOSS-V3` 工作。先严格遵循仓库 `AGENTS.md` 和作用域内更深层 `AGENTS.md`。

当前目标不是继续自由开发，而是**把当前剩余 dirty worktree 再拆成最小 coherent commits**。不要 amend 已有提交。不要把无关 workstream 混在一起。不要新增与当前改动无关的功能。

## 已有提交锚点（不要改写）

这些提交已经存在，视为稳定边界：

- `52b8fad` — `balance-analysis` governed workbook / fact / docs 主切片
- `bcfc861` — `balance-analysis` handoff prompt docs
- `c9f03b0` — `bond-analytics / risk-overview` cockpit readiness 切片
- `7a9126f` — `advanced_attribution` analytical not-ready contract
- `bae7355` — governance / dev postgres healthcheck slice
- `36c2884` — analysis adapters / tasks / PnL bridge hardening
- `d3e45c8` — shared ECharts boundary + analytics cockpit view tightening

不要 amend，不要 squash 进这些提交。

## 当前任务

处理**剩余未提交文件**，继续按最小 coherent workstream 收口。  
如果某些文件你无法高置信归组，**先不要提交它们**，在最终汇报里单列说明。

## 先做的事

运行：

```powershell
git status --short
git diff --name-only
```

然后按下面的优先分组策略挑一组执行。一次只做一组。

## 当前剩余文件的推荐分组

### Group A: advanced attribution boundary wiring

优先考虑这些文件：

- `backend/app/api/routes/balance_analysis.py`
- `backend/app/services/formal_result_runtime.py`
- `backend/app/schemas/advanced_attribution.py`
- `backend/app/services/advanced_attribution_service.py`
- `docs/plans/2026-04-12-advanced-attribution-implementation-plan.md`
- `tests/test_advanced_attribution_contract.py`
- `tests/test_balance_analysis_consumer_surface.py`

目标：

- 只交付 analytical / not-ready contract 与边界 wiring
- 不返回伪 attribution 数值
- 不把 `advanced_attribution_bundle` 塞进 governed workbook

最小验证：

```powershell
pytest tests/test_advanced_attribution_contract.py tests/test_balance_analysis_consumer_surface.py -q
pytest tests/test_balance_analysis_api.py -q
```

### Group B: executive metrics read seam

优先考虑这些文件：

- `backend/app/services/executive_service.py`
- `backend/app/repositories/formal_zqtz_balance_metrics_repo.py`

目标：

- 让 executive overview / dashboard 读取 `fact_formal_zqtz_balance_daily` 的只读指标 seam 清晰独立
- 不要混入 balance-analysis workbook 正式路径

最小验证：

```powershell
pytest tests/test_analysis_service_adapters.py tests/test_analysis_service_contract.py -q
pytest tests/test_repository_healthchecks.py -q
```

如果这组缺少足够直接的测试入口，可以先做 docs-only / test-only 收口，或者保留不提交。

### Group C: residual shared frontend chart boundary

优先考虑这些文件：

- `frontend/src/lib/echarts.tsx`
- `frontend/src/lib/agGridSetup.ts`
- `frontend/src/features/bond-analytics/components/CreditSpreadView.tsx`
- `frontend/src/features/bond-analytics/components/KRDCurveRiskView.tsx`
- `frontend/src/features/bond-analytics/components/ReturnDecompositionView.tsx`
- `frontend/src/features/executive-dashboard/components/PnlAttributionSection.tsx`
- `frontend/src/features/pnl/PnlBridgePage.tsx`
- `frontend/src/features/risk-tensor/RiskTensorPage.tsx`
- `frontend/src/test/EchartsBoundary.test.ts`
- `frontend/vite.config.ts`

目标：

- 只做 shared chart / frontend boundary 收口
- 不混入 backend service 逻辑

最小验证：

```powershell
pnpm --dir frontend test -- EchartsBoundary RiskTensorPage BondAnalyticsView
pnpm --dir frontend typecheck
```

### Group D: residual backend infra / storage / scripts

优先考虑这些文件：

- `backend/app/governance/settings.py`
- `backend/app/repositories/governance_repo.py`
- `backend/app/repositories/postgres_repo.py`
- `sql/0001_bootstrap_governance.sql`
- `scripts/dev-api.ps1`
- `scripts/dev-env.ps1`
- `scripts/dev-worker.ps1`
- `scripts/dev-postgres-down.ps1`
- `scripts/dev-postgres-status.ps1`
- `scripts/dev-postgres-up.ps1`
- `scripts/dev-python.ps1`
- `scripts/dev_postgres_cluster.py`
- `tests/test_governance_logging.py`
- `tests/test_repository_healthchecks.py`
- `tests/test_dev_postgres_cluster.py`
- `tests/test_service_storage_boundaries.py`

目标：

- dev / storage / governance 基础设施单独收口
- 不混进 product or analytics UI

最小验证：

```powershell
pytest tests/test_governance_logging.py tests/test_repository_healthchecks.py tests/test_dev_postgres_cluster.py tests/test_service_storage_boundaries.py -q
```

### Group E: residual analysis / source preview / product category / bridge hardening

优先考虑这些文件：

- `backend/app/repositories/pnl_repo.py`
- `backend/app/repositories/product_category_pnl_repo.py`
- `backend/app/services/analysis_adapters.py`
- `backend/app/services/analysis_service.py`
- `backend/app/services/pnl_bridge_service.py`
- `backend/app/services/source_preview_refresh_service.py`
- `backend/app/tasks/ingest.py`
- `backend/app/tasks/materialize.py`
- `backend/app/tasks/product_category_pnl.py`
- `backend/app/tasks/source_preview_refresh.py`
- `tests/test_analysis_service_adapters.py`
- `tests/test_analysis_service_contract.py`
- `tests/test_ingest_foundation.py`
- `tests/test_pnl_api_contract.py`
- `tests/test_pnl_bridge_service_boundaries.py`
- `tests/test_product_category_formula_boundaries.py`
- `tests/test_product_category_pnl_flow.py`
- `tests/test_source_preview_flow.py`

目标：

- 只做 adapter/task/boundary hardening
- 不混进 cockpit UI

最小验证：

```powershell
pytest tests/test_analysis_service_adapters.py tests/test_analysis_service_contract.py tests/test_ingest_foundation.py tests/test_pnl_api_contract.py tests/test_pnl_bridge_service_boundaries.py tests/test_product_category_formula_boundaries.py tests/test_product_category_pnl_flow.py tests/test_source_preview_flow.py -q
```

## 执行规则

- 一次只处理一个 group
- 每个 group：
  1. 明确文件清单
  2. 跑最小相关测试
  3. 必要时做最小修复
  4. 重新跑测试
  5. 再 commit
- 如果你发现某个 group 其实不完整或不够自洽，不要硬提，保留到最后汇报

## Commit 要求

每个 commit message 必须遵循仓库 Lore 规范。

至少包含：

- intent line
- `Constraint:`
- `Rejected:`
- `Confidence:`
- `Scope-risk:`
- `Directive:`
- `Tested:`
- `Not-tested:`

## 最终全量确认

在你准备结束当前 group 时，至少再跑：

```powershell
pytest tests -q
pnpm --dir frontend typecheck
```

如果全量成本过高且当前 group 已局部验证充分，可以先停下并明确说明没跑全量。

## 停止条件

满足任一条件就停止并汇报：

1. 当前 group 已通过测试并成功 commit
2. 剩余文件无法高置信归组
3. 某组需要跨越当前 repo 边界或引入大范围重构

## 输出要求

最终回复必须包含：

- 你识别出的 group 列表
- 这次实际处理了哪一个 group
- 变更文件列表
- 新增或修改的测试列表
- 测试结果
- 风险点
- 是否影响正式金融口径
- 未完成项
- 下一轮建议
- 如果成功提交，再附：
  - commit hash
  - commit title

## 重要提醒

- 当前任务是 closeout / commit hygiene
- 不是继续自由扩功能
- 只有高置信、已验证、范围清晰的 group 才能提交

---
