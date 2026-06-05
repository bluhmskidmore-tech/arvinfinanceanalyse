# gl_rules_spec.md

## Role

本文件是 QDB GL 规则的：

- index
- assembly doc
- baseline-boundary doc

本文件必须保持 assembly-only。

本文件 must not become：

- a second normative truth source
- a duplicate owner for source contract details already owned by `data_contracts.md`
- a hidden authorization for downstream runtime slices

## Current Boundary

当前 live runtime slice 只允许：

- `QDB GL baseline source-binding + input-contract validation`

继续 blocked：

- normalization / classification
- storage / materialization
- analytical/read-model outputs
- formal-upstream integration
- API / frontend consumer rollout

## Owner Map

### `data_contracts.md`

唯一 normative owner：

- QDB GL baseline source file contract
- header / row-shape
- required raw fields
- account-code text preservation
- currency grouping
- reconciliation / status-label contract
- lineage fields for contract-level pass/fail evidence

### `acceptance_tests.md`

唯一 verification owner：

- contract-level admissibility assertions
- slice-specific test-file mapping

### `calc_rules.md`

引用 owner，仅负责 future formal-upstream gating notes。

## Baseline Labels

当前 QDB GL baseline 合同按下列标签解释：

- `QDB baseline convention`

若未来进入跨银行抽象，需另行升级为：

- `future-generalization candidate`
- `system-wide governance invariant`

## Analytical / Reporting Families

以下条目在本文件中只做 assembly/index，不在这里重新维护 normative rule detail：

- balance-sheet reconstruction
- concentration analysis
- anomaly frameworks
- income / expense structure analysis
- interbank flow analysis
- precious-metal exposure analysis

## Brownfield Anti-Leak

以下资产只能保持为 overlap evidence / consumer：

- `backend/app/services/product_category_source_service.py`
- `backend/app/core_finance/product_category_pnl.py`
- `docs/BALANCE_ANALYSIS_SPEC_FOR_CODEX.md`
- `product_category_*`

它们不得被重写为：

- GL domain truth
- bootstrap architecture
- implicit authorization trigger
