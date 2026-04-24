# Cursor Boundary Governance Prompts

## 使用方式

一次只给 Cursor 一个 prompt。每个 prompt 完成后，让 Cursor 停下并回报：

- changed files
- exact behavior changed
- tests/checks run and results
- blocker or residual risk

不要让两个 Cursor 会话同时修改同一个文件。

---

## Prompt 1 - Product Category Page Contract Binding

```text
You are working in F:\MOSS-V3.

Read first:
- AGENTS.md
- docs/DOCUMENT_AUTHORITY.md
- docs/CURRENT_EFFECTIVE_ENTRYPOINT.md
- docs/SYSTEM_BOUNDARY_GOVERNANCE_OPERATING_MODEL.md
- docs/plans/2026-04-24-system-boundary-governance-execution-split.md
- docs/plans/2026-04-24-page-contract-golden-sample-binding.md
- docs/page_contract_template.md
- docs/pnl/product-category-page-truth-contract.md
- docs/pnl/product-category-closure-checklist.md
- tests/golden_samples/GS-PROD-CAT-PNL-A/assertions.md

Task:
Add a compact first-class product-category PnL page contract entry to docs/page_contracts.md.

Boundary class:
formal live documentation binding.

Write scope:
- docs/page_contracts.md

Do not touch:
- backend/
- frontend/
- tests/golden_samples/
- docs/metric_dictionary.md
- docs/golden_sample_plan.md
- docs/golden_sample_catalog.md

Goal:
Add `PAGE-PROD-CAT-PNL-001` or the repo-consistent equivalent, and bind it to `GS-PROD-CAT-PNL-A` plus the existing product-category truth contract.

Required content:
- page identity and route/surface
- what business question the page answers
- what it explicitly does not answer
- endpoint / DTO references from the existing truth contract
- basis and formal-truth boundary
- metric/sample/test anchors
- stale/fallback/error visibility expectations
- link to `GS-PROD-CAT-PNL-A`

Required checks:
```powershell
rg -n "PAGE-PROD-CAT-PNL|GS-PROD-CAT-PNL-A|product-category-page-truth-contract" docs/page_contracts.md docs/pnl tests/golden_samples
```

Output back:
- changed files
- exact section added
- checks run and results
- blocker or residual risk

Stop after this task. Do not broaden scope.
```

---

## Prompt 2 - Golden Sample Plan/Catalog Alignment

```text
You are working in F:\MOSS-V3.

Read first:
- AGENTS.md
- docs/DOCUMENT_AUTHORITY.md
- docs/CURRENT_EFFECTIVE_ENTRYPOINT.md
- docs/SYSTEM_BOUNDARY_GOVERNANCE_OPERATING_MODEL.md
- docs/plans/2026-04-24-page-contract-golden-sample-binding.md
- docs/golden_sample_plan.md
- docs/golden_sample_catalog.md
- tests/golden_samples/README.md
- tests/test_golden_samples_capture_ready.py

Task:
Align the docs-level golden sample plan/catalog with the current 12 sample directories and the capture-ready test matrix.

Boundary class:
docs-only governance alignment.

Write scope:
- docs/golden_sample_plan.md
- docs/golden_sample_catalog.md

Do not touch:
- backend/
- frontend/
- tests/golden_samples/
- tests/test_golden_samples_capture_ready.py
- docs/page_contracts.md
- docs/metric_dictionary.md

Goal:
Make the docs accurately reflect:
- `GS-PROD-CAT-PNL-A`
- `GS-BRIDGE-WARN-B`
- `GS-RISK-WARN-B`
- `GS-EXEC-OVERVIEW-A` current `caliber_label` frozen shape
- `GS-BOND-HEADLINE-A` remains blocked/candidate until page contract and metric mapping are complete

Important:
Do not edit sample response JSON in this task. If you believe a sample response should change, report it as a follow-up with evidence.

Required checks:
```powershell
rg -n "GS-PROD-CAT-PNL-A|GS-BRIDGE-WARN-B|GS-RISK-WARN-B|GS-EXEC-OVERVIEW-A|caliber_label|GS-BOND-HEADLINE-A" docs/golden_sample_plan.md docs/golden_sample_catalog.md tests/test_golden_samples_capture_ready.py tests/golden_samples
```

Output back:
- changed files
- sample statuses changed or clarified
- checks run and results
- blocker or residual risk

Stop after this task. Do not broaden scope.
```

---

## Prompt 3 - Metric Dictionary Sample Scope Pass

```text
You are working in F:\MOSS-V3.

Read first:
- AGENTS.md
- docs/DOCUMENT_AUTHORITY.md
- docs/CURRENT_EFFECTIVE_ENTRYPOINT.md
- docs/SYSTEM_BOUNDARY_GOVERNANCE_OPERATING_MODEL.md
- docs/metric_dictionary_template.md
- docs/metric_dictionary.md
- docs/golden_sample_plan.md
- docs/page_contracts.md
- docs/plans/2026-04-24-page-contract-golden-sample-binding.md

Task:
Add or clarify sample references in docs/metric_dictionary.md for metrics already covered by existing active golden samples.

Boundary class:
docs-only metric/sample traceability.

Write scope:
- docs/metric_dictionary.md

Do not touch:
- backend/
- frontend/
- tests/
- docs/page_contracts.md
- docs/golden_sample_plan.md
- docs/golden_sample_catalog.md

Goal:
Improve traceability from `metric_id -> page_scope -> sample_id -> test file`, without inventing new metrics or broadening the current cutover scope.

Rules:
- Only add sample references for metrics already covered by existing sample packages.
- Do not invent new `metric_id`s.
- Do not mark candidate/excluded surfaces as active.
- If product-category metrics are not yet fully defined in the dictionary, record the smallest explicit TODO rather than guessing.

Required checks:
```powershell
rg -n "sample_scope|GS-BAL|GS-PNL|GS-BRIDGE|GS-RISK|GS-EXEC|GS-PROD-CAT|metric_id" docs/metric_dictionary.md docs/metric_dictionary_template.md docs/golden_sample_plan.md
```

Output back:
- changed files
- metric/sample mappings added
- mappings intentionally deferred
- checks run and results
- blocker or residual risk

Stop after this task. Do not broaden scope.
```

---

## Prompt 4 - Frontend Formal Recompute Audit

```text
You are working in F:\MOSS-V3.

Read first:
- AGENTS.md
- docs/DOCUMENT_AUTHORITY.md
- docs/CURRENT_EFFECTIVE_ENTRYPOINT.md
- docs/SYSTEM_BOUNDARY_GOVERNANCE_OPERATING_MODEL.md
- docs/plans/2026-04-24-frontend-page-chain-audit.md
- frontend/src/utils/format.ts
- frontend/src/components/page/FormalResultMetaPanel.tsx

Task:
Create a docs-only audit of frontend locations that might parse, scale, or derive displayed business metrics inside components.

Boundary class:
docs-only frontend audit.

Write scope:
- docs/plans/2026-04-24-frontend-formal-recompute-audit.md

Do not touch:
- backend/
- frontend/
- tests/
- docs/page_contracts.md
- docs/metric_dictionary.md

Goal:
Classify component-level `Number(...)` / `parseFloat(...)` usage into:
- harmless local display formatting
- adapter-owned view-model conversion
- risky formal metric derivation in component
- mock/demo/placeholder-only behavior

Search command:
```powershell
rg -n "parseFloat|Number\\(|nativeToNumber|formatOverviewNumber|formatNumber" frontend/src -g "*.ts" -g "*.tsx"
```

Required output in the new doc:
- top 5 risky files by business impact
- why each is risky or safe
- recommended first code slice
- tests that should guard the first code slice

Output back:
- changed files
- audit summary
- checks run and results
- blocker or residual risk

Stop after this task. Do not broaden scope.
```

---

## Prompt 5 - First Frontend State-Test Closure Candidate

```text
You are working in F:\MOSS-V3.

Read first:
- AGENTS.md
- docs/DOCUMENT_AUTHORITY.md
- docs/CURRENT_EFFECTIVE_ENTRYPOINT.md
- docs/SYSTEM_BOUNDARY_GOVERNANCE_OPERATING_MODEL.md
- docs/plans/2026-04-24-frontend-page-chain-audit.md
- frontend/src/components/DataSection.tsx
- frontend/src/components/DataSection.types.ts
- frontend/src/components/DataSection.test.tsx

Task:
Pick one existing component or section that already uses the DataSection/state pattern and add a focused `.states.test.tsx` coverage file.

Boundary class:
frontend state visibility hardening.

Write scope:
Pick exactly one small component area after inspecting:
- frontend/src/features/executive-dashboard/components/
or
- frontend/src/features/pnl-attribution/components/
or
- frontend/src/features/cashflow-projection/

Do not touch:
- backend/
- docs/
- global frontend architecture
- routing
- contracts.ts unless the selected component cannot be tested without it

Goal:
Cover loading / error / empty / stale / fallback / ok visibility for one section, using the existing local testing style.

Required checks:
Run the narrowest relevant vitest command for the chosen test file, for example:
```powershell
cd frontend
npx vitest run src/features/<chosen-path>/<chosen-test>.tsx
```

Output back:
- selected component and why
- changed files
- tests run and results
- blocker or residual risk

Stop after this task. Do not broaden scope.
```
