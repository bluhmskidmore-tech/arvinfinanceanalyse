# Cursor Parallel System Closure Wave 1 Prompt

You are the lead Cursor coding agent. The workspace is `F:\MOSS-V3`.

**Model:** Run this prompt as **Composer** (lead agent and integration work).

Execute this prompt autonomously until the work is ready for Codex review. Do not pause to ask "should I continue?". Ask the human only for destructive actions, external production writes, missing credentials, or business metric ambiguity that cannot be resolved from repository evidence.

## 0. Operating Contract

Read and obey these files first:

- `AGENTS.md`
- `docs/DOCUMENT_AUTHORITY.md`
- `docs/CURRENT_EFFECTIVE_ENTRYPOINT.md`
- `docs/page_contracts.md`
- `docs/metric_dictionary.md`
- `docs/golden_sample_catalog.md`
- `docs/golden_sample_plan.md`
- `scripts/audit_frontend_debt.mjs`

Priority order:

1. business metric correctness
2. page-level closure
3. traceability and validation
4. minimal, reviewable changes

Hard constraints:

- Do not change database schema.
- Do not change auth or permission framework.
- Do not change queue, scheduler, or cache base layers.
- Do not add dependencies.
- Do not rewrite the global API client architecture.
- Do not promote mock, candidate, or analytical data into formal truth.
- Do not grow `frontend/src/api/client.ts`.
- Do not add repeated inline `style={{ ... }}` debt.
- Do not overwrite, revert, or reformat unrelated existing changes.

If you must commit, use the Lore Commit Protocol from `AGENTS.md`. Unless this execution environment explicitly requires commits, leave changes uncommitted and produce a reviewable diff.

## 1. Mission

This wave is not a platform refactor. It is the first pass over repeated closure work:

- Close page contracts for high-priority live pages.
- Tighten the binding between page contracts, metric dictionary entries, and golden sample catalog entries.
- Improve page-local stale / fallback / vendor-unavailable visibility for 1 to 2 pages.
- Run narrow verification and ensure frontend debt does not grow.
- Produce a review packet for Codex.

Wave 1 priority pages:

1. `/bond-dashboard`
2. `/positions`
3. `/market-data`
4. `/operations-analysis`

If the business definition for a metric or section is unclear, do not guess. Mark it as `pending-confirmation` and cite the evidence.

## 2. Required Parallelization

Use Cursor subagents / Background Agents / Agent tabs in parallel. Use at most 6 child agents.

**Subagent model:** Every child agent (Agents A–F) must run on **Composer**. Same stack as the lead: **Composer** only for this wave, unless a lane is blocked and the human explicitly overrides.

Lead agent responsibilities:

- Start the child agents.
- Give every child agent a strict write scope.
- Integrate results.
- Resolve conflicts.
- Run verification.
- Write the final review packet.

Every child agent must start with:

```powershell
git status --short
```

Before editing any dirty file, inspect the existing diff:

```powershell
git diff -- <path>
```

Never delete, revert, or reformat unrelated changes.

## 3. Subagent Assignments

Each lane below: spawned subagent **Composer**.

### Agent A: Route And Contract Gap Auditor

Mode: read-only.

Goal: Produce the current live-route to page-contract coverage gap.

Inspect:

- `frontend/src/router/routes.tsx`
- `frontend/src/mocks/navigation.ts`
- `docs/page_contracts.md`
- `docs/V2_V3_PARITY_MATRIX.md`
- `docs/superpowers/specs/2026-04-18-v1-v3-parity-matrix.md`

Return to the lead agent:

- live route list
- routes that already have `PAGE-*` contracts
- missing page contracts
- top 4 routes to close first
- placeholder or excluded routes that must not be promoted

Do not edit files.

### Agent B: Page Contract Writer

Write scope:

- `docs/page_contracts.md`

Goal: Add or update contracts for Wave 1 pages where repository evidence is sufficient:

- `/bond-dashboard`
- `/positions`
- `/market-data`
- `/operations-analysis`

Each page contract must include:

- page id
- route
- page status: `active`, `mixed-source`, `candidate`, or `excluded`
- primary business question
- what this page must not answer
- required sections
- optional sections
- forbidden sections
- endpoint / DTO table
- metric mapping table
- `requested_report_date`, `resolved_report_date`, `as_of_date`, `generated_at`
- loading / empty / stale / fallback / error behavior
- test anchors
- golden sample anchors, if any
- explicit pending confirmations

Rules:

- Do not invent metric ids.
- If a page has real UI but no formal metric dictionary entry, write `pending metric_id binding` with evidence.
- If a section is analytical-only, label it as analytical-only.
- If a page mixes mock and real data, say so explicitly.
- Keep edits localized to the relevant document sections.

Validation:

```powershell
pytest tests/test_balance_analysis_docs_contract.py tests/test_backend_release_gate_docs.py -q
```

If these tests are unrelated but pass, report that. If they fail because the docs contract needs a small update, make the smallest update and rerun.

### Agent C: Metric Dictionary And Sample Binding Writer

Write scope:

- `docs/metric_dictionary.md`
- `docs/golden_sample_catalog.md`
- `docs/golden_sample_plan.md`

Goal: Continue binding `page_id -> metric_id -> sample_id -> test file` for Wave 1 pages.

Required behavior:

- Add metric dictionary rows only when the source field and display semantics are clear from code, tests, or docs.
- For unapproved or ambiguous product, bond, market, or operations metrics, add an explicit gap entry instead of guessing.
- Keep `GS-BOND-HEADLINE-A` blocked unless page contract plus metric mapping is genuinely ready.
- Do not create new golden sample JSON in this lane.
- Do not change backend calculation logic.

Inspect:

- `docs/metric_dictionary.md`
- `docs/golden_sample_catalog.md`
- `docs/golden_sample_plan.md`
- `tests/test_golden_samples_capture_ready.py`
- `frontend/src/features/bond-dashboard/pages/BondDashboardPage.tsx`
- `frontend/src/features/positions/components/PositionsView.tsx`
- `frontend/src/features/market-data/pages/MarketDataPage.tsx`
- `frontend/src/features/workbench/pages/OperationsAnalysisPage.tsx`

Validation:

```powershell
pytest tests/test_golden_samples_capture_ready.py -q
```

If full golden sample replay is too slow or environment-sensitive, at minimum run:

```powershell
pytest tests/test_golden_samples_capture_ready.py::test_capture_ready_golden_sample_files_exist tests/test_golden_samples_capture_ready.py::test_capture_ready_golden_sample_metadata_is_in_expected_state -q
```

Report exactly what ran.

### Agent D: Market Data Page Closure

Write scope:

- `frontend/src/features/market-data/pages/MarketDataPage.tsx`
- page-local components under `frontend/src/features/market-data/components/`
- existing tests under `frontend/src/test/MarketDataPage.test.tsx`
- page-local model/helper tests only if needed

Goal: Improve `/market-data` page-level closure without broad refactor.

Tasks:

- Trace displayed metrics from API/client contract to page rendering.
- Identify repeated local formatter/state logic that can move to a page-local helper without behavior change.
- Make `result_meta` quality/fallback/vendor status user-visible for primary live sections if currently hidden.
- Ensure no-data, stale, fallback, and loading failure are distinguishable.
- Reduce inline styles only when the reduction is local and low risk.

Rules:

- Do not edit shared API client unless strictly required.
- Do not add dependencies.
- Do not change business calculations.
- Do not turn analytical data into formal truth.
- Do not grow total `style=` count.

Validation:

```powershell
npm run test -- MarketDataPage
npm run debt:audit
```

If that test selector is not supported, use the nearest Vitest command and report the exact command.

### Agent E: Operations Analysis Page Closure

Write scope:

- `frontend/src/features/workbench/pages/OperationsAnalysisPage.tsx`
- `frontend/src/features/workbench/business-analysis/BusinessContributionTable.tsx`
- `frontend/src/test/OperationsAnalysisPage.test.tsx`
- `frontend/src/test/OperationsAnalysisPage.governed.test.tsx`

Goal: Improve `/operations-analysis` page-level closure without broad refactor.

Tasks:

- Identify where the page still mixes real data, mock data, or candidate business metrics.
- Surface fallback/stale/vendor status for live sections.
- Make ambiguous business metrics explicit rather than silently rendering final truth.
- Keep changes page-local.
- Add or update the smallest tests around changed display logic.

Rules:

- Do not change backend services.
- Do not change shared API client unless strictly required.
- Do not invent metric definitions.
- Do not grow frontend debt baseline.

Validation:

```powershell
npm run test -- OperationsAnalysisPage
npm run debt:audit
```

If test selection differs, use the nearest Vitest command and report it.

### Agent F: API Client Decomposition Scout

Mode: read-only.

Goal: Produce next safe extraction candidates for reducing `frontend/src/api/client.ts`.

Inspect:

- `frontend/src/api/client.ts`
- `frontend/src/api/balanceAnalysisClient.ts`
- `frontend/src/api/bondAnalyticsClient.ts`
- `frontend/src/api/executiveClient.ts`
- `frontend/src/api/marketDataClient.ts`
- `frontend/src/api/pnlClient.ts`
- `frontend/src/api/positionsClient.ts`
- `frontend/src/mocks/`

Return to the lead agent:

- top 5 domain blocks still inside `client.ts`
- mock payload blocks that should move first
- safest first extraction with exact file ownership
- tests that would prove extraction preserved behavior

Do not edit files in this wave unless the lead agent explicitly assigns a narrow follow-up.

## 4. Main-Agent Integration Steps

After all agents finish:

1. Read all child summaries.
2. Check for overlapping file edits.
3. If two agents edited the same file unexpectedly, resolve deliberately and preserve both intents.
4. Run:

```powershell
git diff --stat
npm run debt:audit
```

5. If frontend code changed, run the targeted Vitest commands from the relevant lanes.
6. If docs or golden sample files changed, run the docs/golden sample commands from Agents B/C.
7. If more than one frontend page changed, also run:

```powershell
npm run typecheck
```

8. If typecheck fails because of your changes, fix and rerun.

Only run full `npm run build`, full `npm run lint`, or backend release suite if the touched surface justifies it or targeted checks reveal integration risk.

## 5. Final Review Packet

Create or update:

- `docs/plans/2026-04-24-cursor-system-closure-wave1-review-packet.md`

The review packet must include:

- summary
- child-agent lane summaries
- changed files
- business root cause / repeated-work category addressed
- exact validation commands and results
- debt audit result
- unresolved ambiguities
- remaining risks
- recommended Wave 2 tasks
- files intentionally not touched

Do not hide failed or skipped verification. If a command cannot run, say why and what evidence remains.

## 6. Suggested Wave 2 Backlog

Do not implement these unless Wave 1 finishes cleanly and they are clearly safe:

- Extract one small domain from `frontend/src/api/client.ts` into its domain client/mock module.
- Add docs-contract tests for live route to page contract completeness.
- Add docs-contract tests for page contract to metric dictionary references.
- Promote `GS-BOND-HEADLINE-A` only after bond dashboard contract and metric mapping are review-ready.
- Continue one-page closure for `/ledger-pnl`, `/average-balance`, `/liability-analytics`, `/cashflow-projection`, `/concentration-monitor`.

## 7. Completion Criteria

Stop only when all are true:

- Wave 1 edits are complete or explicitly blocked with evidence.
- No unrelated files were reverted.
- `npm run debt:audit` passes.
- Relevant targeted tests/docs checks have passed or are honestly reported.
- Review packet exists and is specific enough for Codex review.

Final response should be concise and include:

- changed files
- validation results
- review packet path
- remaining risks
