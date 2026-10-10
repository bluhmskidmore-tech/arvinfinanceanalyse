# MOSS-V3 Merge Readiness Report

Date: 2026-07-05
Repository: F:\MOSS-V3
Branch: opt/2026-07-position-gate-batch2
HEAD: a1e1ce80d0ef56ef149b95727e20bae4004517ac

## Verdict

YELLOW. The Pro second-audit package is ready to hand off, but the repository is
not ready for release or merge from the current worktree.

Do not merge the current working tree as-is.

Primary reason: the worktree has a large, mixed dirty boundary. Fresh status
shows 272 dirty entries, 0 staged entries, 192 modified entries, and 80
untracked entries. A reviewer cannot safely attribute all current changes to
the architecture remediation or the frontend build unblock without a separate
ownership pass.

## Fresh Worktree Snapshot

Command: `git status --porcelain=v1`

Summary:

```text
Total dirty entries: 272
Modified entries:    192
Untracked entries:   80
Staged entries:      0
```

Dirty entries by area:

```text
frontend       138
backend         39
tests           35
docs            30
scripts         17
agent_config     6
config           3
audit_pack       2
root_or_other    2
```

## Pro Handoff Package

Desktop package:

```text
C:\Users\arvin\Desktop\MOSS_V3_Pro_Second_Audit_Evidence_2026-07-05.zip
```

SHA256:

```text
4BEDF35F475C442B04B6DD970FB51B5DA4433E91376DF1F9465357B105A0E237
```

Zip contents verified:

```text
MOSS_V3_SECOND_AUDIT_EVIDENCE_2026-07-05.md
PROMPT_PREFLIGHT_DECISIONS.md
PRO_SECOND_AUDIT_PROMPT.md
README.md
README_EVIDENCE.md
```

Status: suitable for Pro second audit. It is not a release artifact and does
not establish merge readiness by itself.

## Minimal PR Lane Candidates

### Lane A: Stock-analysis return_10d build unblock

Purpose: keep the frontend build green after the Livermore candidate history
contract widened to include `return_10d`.

Tracked file boundary:

```text
frontend/src/api/marketDataClient.ts
frontend/src/features/stock-analysis/components/StockAnalysisStrategyReviewCards.tsx
frontend/src/features/stock-analysis/lib/stockAnalysisPageModel.ts
frontend/src/test/StockAnalysisBacktestModel.test.ts
frontend/src/test/StockAnalysisPage.test.tsx
frontend/src/test/StockAnalysisPageModel.test.ts
frontend/src/test/StockAnalysisPriorityModel.test.ts
```

Diff stat:

```text
7 files changed, 475 insertions(+), 18 deletions(-)
```

Important staging note: some stock-analysis files already contained pre-existing
execution-basis edits before the `return_10d` unblock. A clean PR should use
patch-level review/staging, not blind whole-file staging, unless those existing
hunks are intentionally included.

Fresh verification:

```text
npm run typecheck
=> passed

npm run build
=> passed; Vite built successfully in 10.78s

npm run test -- src/test/StockAnalysisPage.test.tsx
=> 1 file passed, 148 tests passed

npm run test -- StockAnalysisBacktestModel StockAnalysisPageModel StockAnalysisPriorityModel
=> 3 files passed, 98 tests passed

npm run debt:audit
=> passed, no growth over baseline
```

Known non-blocking-to-this-lane red test:

```text
npm run test -- StockAnalysisPage
=> failed only in src/test/StockAnalysisPageSizeGuard.test.ts
=> AssertionError: expected 5160 to be less than or equal to 4000
=> 1 failed, 250 passed
```

Interpretation: the narrow behavior and model tests pass. The broad filter is
red because it also matches an existing page extraction guard. That guard must
be resolved or explicitly waived before release, but it is not evidence that
the `return_10d` build-unblock behavior regressed.

### Lane B: Prompt 03A / 06 / 12 remediation evidence

Purpose: architecture-audit remediation previously claimed for 03A, 06, and 12.

Current claimed boundary from the evidence file:

```text
backend/app/api/routes/executive.py
backend/app/api/routes/pnl_attribution.py
backend/app/schemas/bond_analytics.py
backend/app/schemas/executive_dashboard.py
backend/app/schemas/pnl_attribution.py
backend/app/services/bond_analytics_service.py
docs/V3_CUTOFF_DECLARATION_2026-04-17.md
frontend/src/api/bondAnalyticsClient.ts
frontend/src/api/homeSupplementalClient.ts
frontend/src/features/bond-analytics/lib/bondAnalyticsModuleReadiness.test.ts
frontend/src/features/bond-analytics/lib/bondAnalyticsModuleReadiness.ts
frontend/src/test/BondAnalyticsClient.test.ts
frontend/src/test/HomeStartupClient.test.ts
tests/golden_samples/GS-CONCENTRATION-MONITOR-A/response.json
tests/test_bond_analytics_curve_effects.py
tests/test_bond_analytics_numeric_migration.py
tests/test_bond_analytics_service_real_data.py
tests/test_executive_dashboard_endpoints.py
tests/test_home_snapshot_endpoint.py
tests/test_envelope_contract.py
```

Do not merge this lane until Pro reviews the second-audit package and confirms
that the claimed evidence for 03A / 06 / 12 is sufficient. The current package
is strong enough for Pro review, but it is not a final merge gate.

### Lane C: Evidence documents

Purpose: preserve the Pro second-audit handoff material in the repository.

Candidate files:

```text
docs/audit/MOSS_V3_SECOND_AUDIT_EVIDENCE_2026-07-05.md
docs/audit/PRO_SECOND_AUDIT_PROMPT_2026-07-05.md
docs/audit/PROMPT_PREFLIGHT_DECISIONS_2026-07-05.md
docs/audit/README_EVIDENCE_2026-07-05.md
docs/audit/MOSS_V3_MERGE_READINESS_2026-07-05.md
```

These may be committed as audit artifacts, but should not be confused with
production code closure.

## Do Not Include In A Clean PR Without Separate Review

The following dirty groups appear unrelated to the narrow `return_10d` unblock
and should not be swept into the same PR without explicit ownership:

```text
.claude/skills/
.codex/skills/
audit_pack/
backend/app/api/routes/macro_etf_strategy.py
backend/app/core_finance/adjusted_returns.py
backend/app/core_finance/gate_exposure_series.py
backend/app/core_finance/macro/
backend/app/core_finance/matched_baseline.py
backend/app/core_finance/portfolio_backtest.py
backend/app/core_finance/portfolio_paths.py
backend/app/core_finance/strategy_policy.py
backend/app/core_finance/vol_target_overlay.py
backend/app/services/macro_etf_strategy_service.py
config/macro_etf_macro_state.json
config/macro_etf_strategy.json
docs/pnl/
frontend/src/features/cross-asset/
frontend/src/features/workbench/
scripts/backfill_*.py
scripts/diagnose_*.py
scripts/run_*stock_strategy*.py
tests/test_macro_etf_strategy.py
tests/test_portfolio_backtest.py
tests/test_walk_forward_threshold_scan.py
```

This is a representative exclusion list, not a full ownership decision. The
current worktree requires a full attribution pass before any broad merge.

## Release / Merge Blockers

1. Mixed dirty worktree: 272 dirty entries, 0 staged entries.
2. No CI artifact attached for the combined current state.
3. `npm run test -- StockAnalysisPage` remains red because the size guard
   asserts `StockAnalysisPage.tsx` must be <= 4000 lines, but it is 5160.
4. Frontend dependency restoration still depends on `npm ci --legacy-peer-deps`
   because plain `npm ci` hits the React 18 / `@heroui/react` React 19 peer
   conflict recorded in the evidence package.
5. npm reported 4 vulnerabilities after dependency installation in the evidence
   package; no dependency remediation or waiver has been attached.
6. Global API contract coverage remains unaudited; Prompt 06 only proves the
   scoped endpoints recorded in the evidence package.
7. Route registry / cube-query boundary and auth-header trust remain fresh audit
   topics, not final closure items.

## Recommended Next Moves

1. Send the desktop zip to Pro for second audit now.
2. Create a clean worktree or branch for Lane A only, then apply/stage the
   `return_10d` patch at hunk level.
3. Resolve or explicitly waive the StockAnalysisPage size guard before any
   release branch is called green.
4. After Pro signs off, cut a separate Lane B PR for 03A / 06 / 12 remediation
   instead of mixing it with unrelated macro, PnL, workbench, and cross-asset
   dirty files.
5. Attach CI output, dependency-install policy, and npm audit disposition before
   asking for final release approval.

## Fresh Checks Run For This Report

```text
git status --porcelain=v1
git diff --cached --name-only
git diff --check
Get-FileHash C:\Users\arvin\Desktop\MOSS_V3_Pro_Second_Audit_Evidence_2026-07-05.zip -Algorithm SHA256
tar -tf C:\Users\arvin\Desktop\MOSS_V3_Pro_Second_Audit_Evidence_2026-07-05.zip
npm run typecheck
npm run build
npm run test -- src/test/StockAnalysisPage.test.tsx
npm run test -- StockAnalysisBacktestModel StockAnalysisPageModel StockAnalysisPriorityModel
npm run test -- StockAnalysisPage
npm run debt:audit
```

`git diff --check` passed with line-ending normalization warnings only.

