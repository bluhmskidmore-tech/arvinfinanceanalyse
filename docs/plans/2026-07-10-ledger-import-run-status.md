# Ledger Import Run Status Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Give every asynchronous Ledger import a durable, authorized status query covering queued, running, succeeded, duplicate, and failed outcomes.

**Architecture:** Reuse the existing append-only `CACHE_BUILD_RUN_STREAM` as the primary lifecycle fact source without changing its repository or schema. Store standard internal statuses (`queued`, `running`, `completed`, `failed`) plus an `outcome` field, map completed outcomes to the public `succeeded` or `duplicate` states, and optionally mirror standard fields to `JobStateRepository` as best-effort only. Keep broker messages free of database credentials; the worker resolves DSNs from its own settings.

**Tech Stack:** FastAPI, Dramatiq, Pydantic settings, GovernanceRepository JSONL/SQL authority, optional SQLAlchemy JobStateRepository, Pytest.

---

## Scope and constraints

- Do not modify `GovernanceRepository`, `JobStateRepository`, database models, migrations, auth policy, broker configuration, frontend code, or worker bootstrap.
- Do not put `governance_sql_dsn` or `job_state_dsn` into the Dramatiq message payload.
- The governance stream is authoritative. Optional JobState writes are best-effort and must never block dispatch or cause a completed import to retry.
- Governance records use `queued`, `running`, `completed`, and `failed`. Public API states are `queued`, `running`, `succeeded`, `duplicate`, and `failed`.
- Public responses expose only a whitelist of fields. They must not expose DSNs, DuckDB paths, SQL, stack traces, or raw exception text.
- Normalize uploaded filenames to a basename before validation, enqueueing, governance recording, and public output.
- Preserve the existing `202` import response and `run_id` format.

### Task 1: Define the Ledger run lifecycle service

**Files:**

- Create: `backend/app/services/ledger_import_run_service.py`
- Test: `tests/test_ledger_import_flow.py`

**Step 1: Write failing lifecycle tests**

Add focused tests proving:

- A queued record can be read back by exact `run_id`.
- Internal `completed + outcome=success` maps to public `succeeded`.
- Internal `completed + outcome=duplicate` maps to public `duplicate` and carries `duplicate_of_batch_id`.
- Unknown `run_id` raises a Ledger-specific not-found exception.
- Public status contains only `run_id`, `status`, `trigger_mode`, `file_name`, `batch_id`, `duplicate_of_batch_id`, `queued_at`, `started_at`, `finished_at`, `error_category`, and `error_message` when applicable.
- A successful completed record is not replaced by a later duplicate/retry record.
- A failed record may be superseded by a later running/completed retry.
- JSONL and SQL-authority reads produce the same public status.
- JobState mirror failure is logged and does not fail the primary governance transition.

Run:

```powershell
python -m pytest tests/test_ledger_import_flow.py -q -k "run_status or run_transition"
```

Expected: FAIL because the Ledger run lifecycle service does not exist.

**Step 2: Implement the minimal service**

Create constants for the Ledger job/cache identity and implement:

- `record_ledger_import_transition(...)`
- `get_ledger_import_run_status(...)`
- `LedgerImportRunNotFoundError`
- basename normalization
- stable safe error categories/messages
- a monotonic reducer over records for one `run_id`
- best-effort optional JobState mirroring after the primary append succeeds

Each governance record must include the existing stream contract fields plus Ledger-specific payload fields. Use `settings.governance_backend` and `settings.governance_sql_dsn` locally; do not change shared repository behavior.

**Step 3: Verify GREEN**

Run the same targeted command and confirm all lifecycle tests pass.

### Task 2: Record queued and dispatch-failed states in the API route

**Files:**

- Modify: `backend/app/api/routes/ledger.py:23-106`
- Test: `tests/test_ledger_import_flow.py`

**Step 1: Write failing route tests**

Add tests proving:

- Valid import records `queued` before `.send()` and still returns `202` with the same `run_id`.
- Broker/task import failure records a safe terminal `failed` transition.
- Governance queued-write failure returns structured `503` and does not enqueue.
- Dispatch failure error text is stable and does not expose the underlying exception.
- A path-like multipart filename is normalized to its basename before enqueue and response.
- Broker payload contains `governance_dir` but no SQL DSN or JobState DSN.

Run:

```powershell
python -m pytest tests/test_ledger_import_flow.py -q -k "queues_json_safe or dispatch or filename"
```

Expected: FAIL on the new status assertions.

**Step 2: Implement the minimal route orchestration**

- Dynamically import the Ledger run service without broker side effects.
- Normalize filename before suffix validation.
- Record queued using the request-process settings.
- Enqueue only non-secret arguments: file content, normalized filename, DuckDB path, governance directory, and run ID.
- On dispatch failure, attempt a safe failed transition; preserve the structured `503` contract even if failure recording also fails.

**Step 3: Verify GREEN**

Run the targeted route tests and the existing upload limit/suffix/OpenAPI tests.

### Task 3: Record worker running and terminal states

**Files:**

- Modify: `backend/app/tasks/ledger_import.py:13-38`
- Test: `tests/test_ledger_import_flow.py`
- Test: `tests/test_ledger_import_worker_e2e.py`

**Step 1: Write failing actor tests**

Add tests proving:

- Actor records `running` before decoding/import work.
- Successful import records internal `completed/outcome=success` with batch and lineage identifiers.
- Duplicate import records internal `completed/outcome=duplicate` with `duplicate_of_batch_id`.
- Invalid base64 and parser `ValueError` failures record safe `failed` fields and re-raise the deterministic error; retryable repository errors are converted to a stable safe retry exception without chaining the original.
- Governance primary-write failure before import prevents the DuckDB write.
- JobState mirror failure does not fail or retry a successful actor.
- Actor resolves SQL and JobState DSNs from worker-local settings; the message signature has no secret DSN fields.

Run:

```powershell
python -m pytest tests/test_ledger_import_flow.py -q -k "actor and (status or transition or duplicate or failure)"
```

Expected: FAIL because the actor currently has no lifecycle recording.

**Step 2: Implement minimal actor transitions**

- Resolve settings inside the worker.
- Build the Ledger governance repository using the explicit non-secret `governance_dir` plus worker-local SQL/backend settings.
- Record `running`, invoke the existing import service under the existing repository task-write scope, then record `completed` with the correct outcome.
- On deterministic file errors, record a stable safe failed state. On retryable processing errors, log only the exception type and raise a stable safe retry exception without the original traceback or message.
- Do not allow optional JobState mirror errors to change actor success/failure.

**Step 3: Verify GREEN**

Run actor tests, duplicate/concurrency/rollback tests, and the live-worker E2E.

### Task 4: Add the authorized status endpoint

**Files:**

- Modify: `backend/app/api/routes/ledger.py` near `/ledger/imports`
- Test: `tests/test_ledger_import_flow.py`
- Test: `tests/test_ledger_analytics_api.py`

**Step 1: Write failing endpoint tests**

Add tests proving:

- `GET /api/ledger/import-status?run_id=...` requires `ledger.data/read`.
- Exact queued/running/succeeded/duplicate/failed envelopes are returned with `data` and `trace.run_id`.
- Unknown run IDs return structured `404 LEDGER_IMPORT_RUN_NOT_FOUND`.
- Missing/blank/extra query parameters return structured `400`.
- Governance read failure returns structured retryable `503`.
- Failed output contains a safe category/message and no path, DSN, SQL, or raw exception.

Run:

```powershell
python -m pytest tests/test_ledger_import_flow.py tests/test_ledger_analytics_api.py -q -k "import_status"
```

Expected: FAIL with a missing route or 404.

**Step 2: Implement the endpoint**

- Reuse `_ledger_read_auth_error`.
- Validate only `run_id` is accepted and require a non-blank value.
- Return the lifecycle service's whitelisted data plus a request trace.
- Map not-found, validation, and storage failures to the existing structured Ledger error envelope.

**Step 3: Verify GREEN**

Run the targeted endpoint tests and OpenAPI route registration test.

### Task 5: End-to-end verification and review

**Files:**

- Test: `tests/test_ledger_import_worker_e2e.py`
- Test: `tests/test_ledger_import_flow.py`
- Test: `tests/test_worker_bootstrap.py`
- Test: `tests/test_ledger_analytics_api.py`

**Step 1: Extend live E2E assertions**

Use the existing real Redis/worker fixture to poll the new status endpoint and prove:

- queued while worker is stopped;
- succeeded after worker processes a new file;
- duplicate after a duplicate-only run;
- failed after the invalid-message path where a route-created run exists;
- worker restart preserves queryable status.

Do not add Redis restart persistence or frontend polling to this task.

**Step 2: Run full targeted verification**

```powershell
python -m pytest tests/test_ledger_import_worker_e2e.py tests/test_ledger_import_flow.py tests/test_worker_bootstrap.py tests/test_ledger_analytics_api.py -q
python -m pytest tests/test_job_state_repo.py tests/test_governance_sql_authority_parity.py -q
python -m ruff check backend/app/api/routes/ledger.py backend/app/services/ledger_import_run_service.py backend/app/tasks/ledger_import.py tests/test_ledger_import_flow.py tests/test_ledger_import_worker_e2e.py tests/test_ledger_analytics_api.py
python -m mypy backend/app/services/ledger_import_run_service.py tests/test_ledger_import_worker_e2e.py
```

Expected: all commands exit 0.

**Step 3: Review and commit**

- Run an independent specification review.
- After spec approval, run an independent code-quality review.
- Fix and re-review all Critical/Important findings.
- Run GitNexus staged change detection.
- Commit only task-scoped files using the repository Lore trailers.

## Residual risks outside this plan

- Cross-store atomicity cannot guarantee a public succeeded state if the DuckDB commit succeeds but the primary governance terminal append repeatedly fails; a retry may later classify that run as duplicate.
- Redis service restart persistence and Docker Redis 7 deployment smoke remain separate verification work.
- Frontend polling and user-facing progress UI are not part of this backend status-contract task.

## Implemented retry and reconciliation semantics

- Both Ledger actors disable Dramatiq's built-in retries. Expected failures are handled inside the actor so middleware never serializes exception tracebacks or callback copies of the original message.
- Deterministic `ValueError` failures write safe terminal facts to the Ledger-private append-only terminal outbox and are not retried.
- Running-transition and retryable DuckDB/runtime failures use bounded manual re-enqueue with an explicit attempt counter and safe payload. Exhaustion writes safe `processing_failed` facts to the outbox.
- Success, duplicate, and final failure first attempt the authoritative build-run stream. If that fails, whitelisted terminal facts are sent through the broker to a governance-only reconciliation actor.
- The reconciliation message contains only safe terminal facts plus governance location and attempt number. It does not depend on a worker-local file and uses bounded manual retry without throwing expected failures.
- The private JSONL terminal spool is only a last-resort local operational artifact when both authoritative governance and broker delivery are unavailable; it is not a cluster-durable guarantee. The actor returns observable `terminal_pending` in that state, and the importer is not rerun after a committed write.
- Cluster recovery is available whenever either authoritative governance or the broker is available. If both are unavailable, local spool recovery requires later operational action on the same storage boundary.
