# Bank Ledger Classification Backfill Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use subagent-driven-development to implement this plan task-by-task.

**Goal:** Add a controlled, auditable way to attest selected legacy Bank Ledger batches under rv_ledger_classification_v2 without silently changing financial values or executing a live write by default.

**Architecture:** A task-owned backfill command builds a deterministic read-only plan from explicit batch IDs, replaying the shared v2 classifier against every snapshot row and validating three-table lineage. Apply is opt-in and requires the exact dry-run digest, a byte-identical existing database backup, a new receipt path, the global DuckDB writer lock plus Ledger import lock, and one atomic transaction.

**Tech Stack:** Python 3.14, DuckDB, pytest, existing MOSS task-write guard and governance locks.

---

## Fixed contract

- Default invocation is read-only dry-run; there is no implicit all-history selection.
- Every selected batch ID is explicit and must exist, be success, have error_count=0, and use the allowed legacy rule.
- ledger_import_batch.row_count, raw rows, snapshot rows, and (batch_id,row_no) key sets must tie exactly.
- Raw JSON is replayed through the current standardizer and v2 classifier. Source version, date, standard fields, position key, and direction must match the stored snapshot.
- This first remediation tool refuses any direction difference. The current database has 14,731/14,731 matching directions, so eligible apply changes only rule lineage.
- Apply updates rule_version consistently in ledger_import_batch, ledger_raw_row, and position_snapshot; amounts, directions, position keys, raw JSON, source/file hash, dates, created time, and position_snapshot_agg remain unchanged.
- Apply requires --apply, repeated --batch-id, --expected-plan-digest, an existing backup file whose SHA-256 equals the target preimage, and a new receipt path.
- Apply re-plans under fixed lock order: global DuckDB writer lock, then Ledger import lock. Any digest or database preimage drift fails closed.
- All selected batches update in one transaction. Post-write invariants are checked before commit; failures roll back.
- A prepared receipt is written before the transaction and atomically replaced with a completed receipt after commit. No sensitive raw JSON is included.
- This turn runs dry-run only. It does not apply to data/moss.duckdb.

### Task 1: Deterministic audit plan

**Files:**
- Create: backend/app/tasks/ledger_classification_backfill.py
- Create: tests/test_ledger_classification_backfill.py

1. Write failing tests for explicit selection, deterministic digest, zero-write dry-run, transition counts, full raw replay, and all preflight blockers.
2. Run focused tests and confirm RED because the task does not exist.
3. Implement the smallest read-only planner using classify_ledger_direction and LEDGER_CLASSIFICATION_RULE_VERSION.
4. Run focused tests GREEN.

### Task 2: Guarded atomic apply

**Files:**
- Modify: backend/app/tasks/ledger_classification_backfill.py
- Modify: backend/app/repositories/ledger_import_repo.py
- Modify: tests/test_ledger_classification_backfill.py
- Modify: tests/test_repository_task_write_guard.py

1. Add failing tests for task-write scope, missing/incorrect digest, backup mismatch, receipt collision, lock order, TOCTOU drift, transaction rollback, immutable fields, and idempotent rerun.
2. Implement a narrow repository apply path guarded by require_repository_task_write_scope.
3. Acquire global then Ledger locks, verify backup/receipt/preimage, write prepared receipt, apply all updates in one transaction, verify, commit, and finalize the receipt.
4. Run focused tests GREEN.

### Task 3: Read-model and governance tie-out

**Files:**
- Modify: tests/test_ledger_analytics_api.py
- Modify: docs/page_contracts.md (Bank Ledger section only)
- Modify: scripts/mcp/moss_project_mcp.py (Bank Ledger trace only)
- Modify: tests/test_governance_doc_contract.py
- Modify: tests/test_project_mcp_servers.py

1. Add a failing integration test: legacy before backfill is fail-closed; successful attestation makes the same values ready without changing directions or amounts.
2. Document the tool as available but not yet applied to live history. Keep temporary-exception and formal_use_allowed=false.
3. Run focused backend and governance tests GREEN.

### Task 4: Verification and review

1. Run the new test file, Ledger import/analytics suites, repository write-guard tests, Ruff, governance/MCP tests, and git diff --check.
2. Run the tool in dry-run mode for explicit live batches 1 through 8 and compare its receipt counts with the independent audit: 8 batches, 14,731 rows, 13,679 ASSET, 1,052 LIABILITY, zero direction changes, complete raw trace.
3. Complete spec review, fix/re-review, then code-quality review.
4. Do not invoke --apply and do not modify data/moss.duckdb.
5. Do not commit unless the user explicitly requests it.
