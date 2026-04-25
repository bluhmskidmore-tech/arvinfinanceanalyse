# System Boundary Governance Execution Split

## Status

- date: 2026-04-24
- purpose: split follow-up work across user, Codex, and Cursor Ultra
- scope: docs / contracts / tests / small page or workflow slices
- non-scope: platform refactor, broad frontend rollout, schema rebuild

## North Star

本轮核心主旨：

> 快速上线系统功能，但每个功能上线前必须先确定边界身份，并留下可追踪、可测试、可交接的最小证据。

衡量标准不是“治理文档写了多少”，而是：

- 页面是否能回答一个明确业务问题。
- 指标是否没有口径漂移。
- excluded/reserved surface 是否没有被误晋升。
- Cursor / Codex 是否能并行做事且不互相踩文件。
- 发布前是否能用小而稳定的验证命令证明。

## Work Ownership

### User owns

- 排业务优先级：下一批先上哪个页面或 workflow。
- 定业务口径 owner/reviewer。
- 对 excluded surface 晋升做明确授权。
- 对关键指标歧义拍板，例如：
  - 元 / 万元 / 亿元
  - % / bp
  - trade date / natural date
  - daily / month-end / YTD
  - formal / analytical / scenario

### Codex owns

- 判断任务是否在当前边界内。
- 为 Cursor 生成可直接执行的 prompt。
- 保持每个任务 write scope 不重叠。
- 接收 Cursor 输出，复核 diff，并补齐遗漏。
- 跑验证并汇报结果。
- 维护本执行拆分包。

### Cursor Ultra owns

- 领取单一、明确、可验证的执行切片。
- 只改 prompt 中允许的文件。
- 不做全局重构。
- 完成后返回：
  - changed files
  - exact behavior changed
  - tests run and results
  - blockers / residual risks

## First Batch: Parallelizable Tasks

### Task A - Backend Boundary Gate Inventory

Owner: Codex or Cursor

Write scope:

- preferred docs-only first:
  - `docs/plans/2026-04-24-backend-boundary-gate-inventory.md`
- if implementing follow-up tests, choose one target test file at a time.

Goal:

- Produce a compact inventory of existing backend boundary gates and the exact rule each gate protects.

Must include:

- `scripts/backend_release_suite.py`
- `scripts/governed_phase2_preflight.py`
- `tests/test_result_meta_on_all_ui_endpoints.py`
- `tests/test_result_meta_required.py`
- `tests/test_result_meta_basis_contract.py`
- `tests/test_balance_analysis_boundary_guards.py`
- `tests/test_pnl_layer_boundary_guards.py`
- `tests/test_cube_query_api.py`
- `tests/test_liability_analytics_api.py`
- `tests/test_golden_samples_capture_ready.py`

Verification:

```powershell
rg -n "backend_release_suite|governed_phase2_preflight|result_meta|reserved surface|boundary_guards|golden_samples" docs tests scripts
```

Output:

- covered rules
- uncovered rules
- recommended next single test to add

### Task B - Frontend Page Chain Audit

Owner: Cursor Ultra

Write scope:

- docs-only first:
  - `docs/plans/2026-04-24-frontend-page-chain-audit.md`
- no source edits in this first audit task.

Goal:

- Identify which pages already follow `API response -> adapter -> selector -> component`, and which pages still parse or calculate display metrics directly in components.

Search anchors:

```powershell
rg -n "parseFloat|Number\\(|result_meta|fallback_mode|quality_flag|vendor_status|adapter|selector" frontend/src -g "*.ts" -g "*.tsx"
```

Must classify examples into:

- good pattern: adapter owns state / formatting decision
- acceptable local display formatting
- risky formal metric calculation in component
- placeholder / excluded page behavior

Output:

- top 5 risky pages by business impact
- one recommended first page to close
- exact files to inspect in the implementation slice

### Task C - Page Contract And Golden Sample Binding

Owner: Cursor Ultra

Write scope:

- `docs/plans/2026-04-24-page-contract-golden-sample-binding.md`
- no source edits in first pass.

Goal:

- Bind existing `sample_id -> page_id -> metric_id -> test file` for the current golden samples.

Must read:

- `docs/page_contracts.md`
- `docs/metric_dictionary.md`
- `docs/golden_sample_plan.md`
- `tests/golden_samples/README.md`
- `tests/test_golden_samples_capture_ready.py`

Must cover current sample dirs:

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
- `GS-PROD-CAT-PNL-A`

Output:

- complete bindings
- missing bindings
- samples that should not be promoted yet
- smallest docs/test follow-up

### Task D - First Live Page Closure Slice

Owner: Codex after Tasks A-C return

Candidate page:

- choose one from current active/candidate pages after the audit.

Default preference:

- do not start with an excluded surface.
- prefer a page that already has tests and only needs boundary closure.

Required execution shape:

1. update or add page contract section
2. add or tighten one adapter/selector/component test
3. bind metric/sample if applicable
4. run targeted frontend/backend tests
5. report root cause and remaining risk

## Cursor Prompt Template

Use this template for each Cursor task:

```text
You are working in F:\MOSS-V3.

Read first:
- AGENTS.md
- docs/DOCUMENT_AUTHORITY.md
- docs/CURRENT_EFFECTIVE_ENTRYPOINT.md
- docs/REPO_WIDE_PHASE2_CUTOVER_DEFINITION.md
- docs/SYSTEM_BOUNDARY_GOVERNANCE_OPERATING_MODEL.md
- docs/plans/2026-04-24-system-boundary-governance-execution-split.md

Task:
<one task only>

Boundary class:
<formal live / analytical overlay / reserved fail-closed / placeholder / docs-only>

Write scope:
<exact files or directories>

Do not touch:
<explicit forbidden files or directories>

Goal:
<one sentence>

Required checks:
<commands>

Output back:
- changed files
- exact behavior changed
- tests/checks run and results
- blocker or residual risk

Stop after this task. Do not broaden scope.
```

## Recommended Immediate Sequence

1. Codex creates the operating model and this execution split.
2. Cursor can run Task B and Task C in parallel, using:
   - `docs/plans/2026-04-24-frontend-page-chain-audit.md`
   - `docs/plans/2026-04-24-page-contract-golden-sample-binding.md`
3. Codex owns Task A locally via:
   - `docs/plans/2026-04-24-backend-boundary-gate-inventory.md`
4. Recommended first closure candidate is product-category PnL documentation binding, because `GS-PROD-CAT-PNL-A` exists but the main `page_contracts` file does not yet expose a first-class page entry.
5. User chooses the first live code page/workflow after this docs binding is aligned.
6. Codex produces the implementation prompt and owns final verification.

## Current Guardrails

- Do not promote `/ui/risk/overview`, `/ui/home/alerts`, `/ui/home/contribution` without explicit new cutover authorization.
- Do not promote Agent MVP or `/api/agent/query`.
- Do not treat `source_preview`, `macro-data`, `choice-news`, market-data preview/vendor surfaces, `cube-query`, or `liability_analytics_compat` as live governed rollout by default.
- Do not let frontend components calculate formal finance metrics.
- Do not let public reserved routes return `{ result_meta, result }` as if governed.
