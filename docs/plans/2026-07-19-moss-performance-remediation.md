# MOSS V3 Performance Remediation Implementation Plan

> **For Codex:** Execute task-by-task with subagent-driven development, TDD, independent review, and fresh verification.

**Goal:** Remove the verified system-wide latency taxes without changing business metrics, permissions, database schema, or page contracts.

**Architecture:** First establish safe process/runtime behavior (settings caching, bounded cache waits, usable timing logs, stable frontend providers). Then optimize page-local DuckDB read paths using type-aligned predicates and request-scoped connections. Destructive storage maintenance, schema/index changes, and permission-policy changes are excluded from this plan.

**Tech Stack:** Python 3.11, FastAPI, Pydantic Settings, DuckDB, React 18, TanStack Query, Vitest, Pytest.

---

## Batch 1: Cross-cutting latency taxes with no business-meaning changes

### Task 1: Cache process settings correctly

**Files:**
- Modify: `backend/app/governance/settings.py`
- Create: `tests/test_governance_settings_cache.py`

**Acceptance criteria:**
1. Two calls to `get_settings()` return the same process-local instance.
2. `get_settings.cache_clear()` causes the next call to rebuild from current environment values.
3. Existing tests that mutate environment and call `cache_clear()` continue to work.
4. No Settings fields or defaults change.

**TDD sequence:** Add the two behavioral tests, verify they fail against the current no-op cache, implement the smallest real cache, rerun targeted tests and a representative settings-heavy API contract test.

### Task 2: Bound same-key cache waiting

**Files:**
- Modify: `backend/app/api/response_cache.py`
- Modify: `backend/app/services/runtime_cache.py`
- Modify: `tests/test_api_response_cache.py`
- Modify: `tests/test_runtime_cache.py`

**Acceptance criteria:**
1. A waiter cannot block forever if its producer never signals.
2. Timeout is configurable per cache instance and has a conservative default.
3. Timeout raises a specific exception containing the cache key/context.
4. Normal single-flight deduplication, producer error propagation, invalidation, and status reporting are unchanged.

**TDD sequence:** Add deterministic event-based timeout tests, verify RED, add minimal timeout support, verify both cache suites GREEN.

### Task 3: Make API performance logs operationally usable

**Files:**
- Modify: `backend/app/api/perf_logging.py`
- Modify only directly affected API logging assertions under `tests/`

**Acceptance criteria:**
1. The default formatter emits endpoint, duration, result kind, trace id, and DuckDB statement count in the actual message text.
2. Existing structured `LogRecord` attributes remain available.
3. No route response or metric logic changes.

**TDD sequence:** Add a focused log-message assertion that fails on the current constant message, implement the smallest compatible message format, update only exact old-message assertions, run all directly affected tests.

### Task 4: Keep the frontend provider tree stable

**Files:**
- Modify: `frontend/src/app/providers.tsx`
- Modify: `frontend/src/test/AppProvidersTheme.test.tsx`

**Acceptance criteria:**
1. Loading Ant Design theme support does not unmount/remount application children.
2. The workbench Ant Design theme remains available after async provider loading.
3. QueryClient and API client identity remain stable.
4. No eager full-AntD import is introduced into the initial bundle.

**TDD sequence:** Add a mount-count/state-preservation test, verify RED against the current root-type swap, implement a stable boundary, run the focused Vitest test, scoped lint, and home-startup bundle guard.

## Batch 2: Page-local DuckDB hot paths

### Task 5: Remove type-destroying date predicates from the Macro Toolkit full path

**Files:**
- Modify only the Macro Toolkit repositories/services identified by fresh GitNexus impact and contract tracing.
- Add/update the smallest repository or service tests for equivalent date semantics.

**Acceptance criteria:**
1. Normalize the input date once, then compare using the stored column type without wrapping the column in `CAST/TRY_CAST`.
2. Returned dates, fallback behavior, units, and row counts remain unchanged against golden/current samples.
3. `EXPLAIN ANALYZE` shows predicate pushdown or index/zone-map use on the verified queries.

### Task 6: Reuse a DuckDB connection within the Macro Toolkit request

**Files:**
- Modify only the Macro Toolkit request path and repository helpers proven by impact analysis.
- Add/update statement/connection-count tests.

**Acceptance criteria:**
1. One request reuses a scoped connection across its compatible read queries.
2. No connection is shared across concurrent requests or threads.
3. Error cleanup and Windows lock retry behavior remain correct.
4. Business payloads are byte-for-byte or semantically equivalent.

### Task 7: Narrow the risk tensor projection

**Files:**
- Modify the risk-tensor read query used by Macro Toolkit.
- Add/update payload contract tests.

**Acceptance criteria:**
1. Query only columns consumed by the route/service.
2. Response contract and metric definitions do not change.
3. Cold read benchmark is recorded before and after.

## Batch 3: Startup contention and governance reads

### Task 8: Stagger non-critical background warmups

**Files:**
- Modify: `backend/app/main.py`
- Modify relevant warmup service tests.

**Acceptance criteria:**
1. Readiness no longer competes immediately with market and income warmups.
2. Required migrations and correctness gates remain intact.
3. Warmup failure remains visible and does not crash unrelated requests.

### Task 9: Optimize governance latest lookups

**Files:**
- Modify: `backend/app/repositories/governance_repo.py`
- Add/update repository tests.

**Acceptance criteria:**
1. Latest-record reads do not copy and scan the entire in-memory history when a cached tail/index is available.
2. Append/invalidation semantics remain correct.
3. JSONL and SQL-authority behavior stay contract-equivalent.

## Explicitly excluded

- Database schema or index changes.
- DuckDB table compaction/rewrite or deletion of backups.
- Permission-policy relaxation or bypass.
- Moving formal KPI calculations or changing units/dates/fallback rules.
- Production topology/worker-count changes without an approved deployment design.

## Final gates

1. Fresh GitNexus impact before every edited symbol; warn before HIGH/CRITICAL edits.
2. GitNexus detect-changes after implementation, or document tool failure and local substitute evidence.
3. Targeted tests first, then proportional backend/frontend checks.
4. `npm run debt:audit` for touched frontend paths.
5. Repeat the settings, cache, homepage, Macro Toolkit, and frontend startup benchmarks.
6. Independent specification review, then code-quality review, then root-agent final review.
