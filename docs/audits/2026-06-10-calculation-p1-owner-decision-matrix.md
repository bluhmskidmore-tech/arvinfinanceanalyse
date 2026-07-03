# 2026-06-10 Calculation P1 Owner Decision Matrix

## Purpose

This matrix converts the 10 remaining open P1 findings from `docs/audits/2026-06-10-calculation-logic-audit.md` into owner-decision items. P1-08 bond-dashboard null handling is recorded below as verified closed in the current worktree, not as an owner-decision item. This matrix does not change code, approve metrics, or close any page. Its job is to make the next review meeting executable: each open row names the rule decision that must happen before implementation should proceed.

**2026-07-03 P1-07 overlay**: owner/chat decision selected Option B for macro liquidity polarity. `liquidity_score` remains looseness-positive for display and downstream compatibility, while `composite_score` is bond-unfavorable/tightness-positive and now enters liquidity as `-0.3*liquidity_score`. The 2026-06-10 generated snapshot files were not regenerated; this note is the human-readable closure overlay for P1-07.

## Closure Rule

For each P1 item:

1. Owner chooses the authoritative business rule.
2. The rule is written into `docs/calc_rules.md`, the metric dictionary, or the page contract where applicable.
3. The implementation is normalized at the authoritative layer.
4. Tests that currently freeze the losing convention are changed with numeric regression evidence.
5. Page/readiness gates remain fail-closed until verification and owner approval are captured.

## Decision Matrix

| ID | Area | Decision Needed | Candidate Decisions | Proposed Default For Review | Impact If Unresolved | Closure Evidence |
| --- | --- | --- | --- | --- | --- | --- |
| P1-01 | Campisi coupon income | Define the stored and calculation unit for `coupon_rate`. | A: source values are decimals; B: source values are percentages and must be divided by 100; C: source must carry explicit unit metadata and fail if absent. | Prefer C, then normalize through one rate-unit helper. | Coupon income can be off by 100x and both current implementations have tests preserving opposite behavior. | `docs/calc_rules.md` unit rule; one implementation path; numeric golden test for decimal and percent-shaped inputs. |
| P1-02 | Bond analytics rate unit | Define the authoritative unit for `ytm_value` and coupon rates before DV01/duration. | A: all source rates are decimals; B: all source rates are percentages; C: source supplies explicit unit metadata. | Prefer C; remove `abs>1 -> /100` heuristics from formal paths. | Low-rate inputs such as `0.85` can be read as 85%, corrupting duration, convexity, and DV01. | Data-catalog/source contract evidence; formal engine regression for sub-1% rates; no heuristic in formal path. |
| P1-03 | Roll-down sign | Decide the business sign convention for curve roll-down. | A: `attribution_daily` convention, `-MD * (y_realized - y_prior) * MV`; B: current `pnl_bridge` convention; C: report both with explicit labels. | Prefer A unless owner explicitly wants the bridge convention. | PnL bridge and daily attribution can tell opposite stories for the same curve movement. | `docs/calc_rules.md` section for roll-down sign; one shared helper or adapter; tests updated on the losing side. |
| P1-04 | QDB position-vs-ledger reconciliation | Decide whether the current check is a control or only a diagnostic. | A: require independent position and ledger source anchors; B: keep current same-source comparison but label it non-control. | Prefer A for any governance/control claim. | Same-source formulas make diff permanently zero and create false assurance. | Reconciliation evidence uses two independent sources, or UI/report explicitly marks the check as non-control. |
| P1-05 | Period yield denominator | Define the denominator for quarterly/yearly yield. | A: period average scale; B: sum of month-end snapshots; C: weighted daily average when daily facts exist. | Prefer A/C; avoid summing snapshots as scale. | Quarterly yield can be understated by roughly 3x and yearly view by roughly 12x. | Rule written to `calc_rules.md`; numeric tests for monthly, quarterly, and yearly buckets. |
| P1-06 | PnL bridge zero-actual residual | Decide how reconciliation quality behaves when `actual_pnl=0`. | A: nonzero explained/residual with zero actual is warning/undefined; B: force ratio to 0 and mark ok. | Prefer A, consistent with fail-loud controls. | Material residuals can be hidden behind `quality_flag=ok`. | Regression where `actual_pnl=0` and explained amount nonzero returns warning and visible diagnostics. |
| P1-07 | Macro liquidity score polarity | Selected 2026-07-03: composite stays bond-unfavorable/tightness-positive while `liquidity_score` stays looseness-positive. | B: liquidity remains looseness-positive but enters composite with inverse sign. | Implemented as `0.4*rate - 0.3*liquidity + 0.2*growth + 0.1*inflation`; `build_macro_context_v1` exposes score polarity and formula metadata. | Closed for the "funding looseness increases tightening / shorten duration" defect. | Isolated liquidity regression in `tests/test_macro_bond_linkage.py`; macro-context metadata assertions; frontend copy states polarity. |
| P1-09 | Balance movement share source | Decide authoritative source for current-balance share. | A: backend `current_balance_pct` is authoritative; B: frontend recomputes from visible rows; C: backend provides both official and visible-row share. | Prefer A, with C only if users need visible-row share. | Frontend can override governed backend percentages and show 0% when calculation is unavailable. | Component/model tests prove backend value wins and missing share remains missing. |
| P1-10 | Frontend formal aggregation | Decide where formal PnL/yield/ADB aggregations are computed. | A: backend DTO only; B: frontend may derive display aggregates; C: frontend derives only clearly non-formal UI helpers. | Prefer A for formal metrics and C for labeled non-formal helpers. | Decimal values are converted to floating point, category trees are duplicated, and frontend can diverge from governed rules. | Backend DTO added or confirmed; frontend removes formal aggregation; adapter/component tests consume DTO values. |
| P1-11 | Credit spread rating-tenor matrix | Decide owner of rating-tenor bucket aggregation. | A: backend provides governed matrix; B: frontend aggregates rows and owns bucket mapping. | Prefer A. | Frontend hard-coded buckets can drift from backend tenor/rating rules without detection. | API contract for rating-tenor matrix; frontend renders provided matrix only; regression covers bucket boundaries. |

## Suggested Review Order

1. P1-09, P1-10, and P1-11: fastest remaining frontend/user-facing risk reduction once owner accepts the boundary.
2. P1-02, P1-01, and P1-05: highest numeric magnitude risk.
3. P1-03, P1-06, and P1-07: narrative/sign quality risks that need explicit wording.
4. P1-04: governance/control classification decision before any control claim.

## Non-Approvals

- This matrix does not approve any calculation convention.
- This matrix does not certify any route or page.
- This matrix does not change `formal_use_allowed` or `closure_approved`.
- This matrix does not replace MCP metric-contract, lineage, or catalog evidence.

## Latest Verification Refresh

Refreshed at `2026-06-10T21:25:00+08:00`.

- Original 2026-06-10 snapshot open owner-decision rows: `P1-01`, `P1-02`, `P1-03`, `P1-04`, `P1-05`, `P1-06`, `P1-07`, `P1-09`, `P1-10`, `P1-11`.
- After the 2026-07-03 P1-07 overlay, rows still needing owner-decision work are: `P1-01`, `P1-02`, `P1-03`, `P1-04`, `P1-05`, `P1-06`, `P1-09`, `P1-10`, `P1-11`.
- `P1-08` remains in the verified-closed section only.
- `npm.cmd test -- src/features/bond-dashboard/utils/format.test.ts src/test/BondDashboardPage.test.tsx` was rerun at `2026-06-10T19:29:53+08:00` and passed with 2 test files and 16 tests.
- This refresh does not choose any owner convention, approve any metric, certify any route/page, or replace MCP metric-contract, lineage, or catalog evidence.

## Verified Closed Before Owner Review

| ID | Area | Closure Evidence | Residual Boundary |
| --- | --- | --- | --- |
| P1-08 | Bond dashboard null handling and false MoM | `frontend/src/features/bond-dashboard/utils/format.ts` preserves null governed numerics; `PortfolioTable.tsx` summary sums fail closed when a governed value is missing; `npm.cmd test -- src/features/bond-dashboard/utils/format.test.ts src/test/BondDashboardPage.test.tsx` passed with 2 files / 16 tests. | This closes the null-to-zero and false-MoM display hazard only. It does not certify Bond Dashboard business ownership, formal metric approval, or fixed-income rate-unit conventions. |

## Verified Closed After Owner Decision

| ID | Area | Closure Evidence | Residual Boundary |
| --- | --- | --- | --- |
| P1-07 | Macro liquidity score polarity | Option B selected and implemented: `liquidity_score` remains looseness-positive, `composite_score` remains bond-unfavorable/tightness-positive, and the composite formula uses `-0.3*liquidity_score`; regression isolates liquidity movement and checks `build_macro_context_v1` formula/polarity metadata. | Generated 2026-06-10 JSON snapshots were not regenerated in this remediation pass; caches/materialized outputs using prior rule/cache versions must be refreshed before production use. |

## Engineering Prework / Impact Slice Map

This section is non-closing engineering prework. It does not choose or approve any convention; it does not change code; it does not certify routes/pages. It only maps the smallest implementation and regression-test slice to use after the owner decision and authoritative rule evidence are captured.

- **P1-01 Campisi coupon income**: after the owner selects the `coupon_rate` unit rule, update `docs/calc_rules.md` and normalize the affected Campisi workbook paths in `backend/app/core_finance/balance_analysis_workbook.py` and `backend/app/core_finance/balance_workbook/_analysis_tables.py`; regression should cover decimal-shaped and percent-shaped coupon inputs, including `tests/test_balance_workbook_campisi_rate.py` and Campisi golden samples.
- **P1-02 Bond analytics rate unit**: after source-unit evidence is captured for `ytm_value` and coupon rates, remove or quarantine the formal-path heuristic in `backend/app/core_finance/bond_analytics/engine.py`; regression should include sub-1% rate examples in the bond analytics engine/service tests and preserve explicit-unit handling.
- **P1-03 Roll-down sign**: after owner sign convention is selected, align `backend/app/core_finance/pnl_bridge.py` with the authoritative attribution convention or label both conventions explicitly; regression should update `tests/test_pnl_bridge_roll_down_sign.py` and any attribution comparison test that freezes the losing sign.
- **P1-04 QDB position-vs-ledger reconciliation**: after governance classifies the check as a control or diagnostic, update `backend/app/core_finance/qdb_gl_monthly_analysis.py` so control claims require independent anchors, or label same-source checks as non-control; regression should use QDB GL core/API tests to prove the selected label and evidence path.
- **P1-05 Period yield denominator**: after the denominator rule is approved, normalize `backend/app/core_finance/yield_by_period.py` and the `frontend/src/features/pnl/yieldAnalysis/YieldByPeriodPanel.tsx` display contract; regression should extend `tests/test_yield_by_period_core.py` across monthly, quarterly, and yearly buckets.
- **P1-06 PnL bridge zero-actual residual**: after reconciliation-quality behavior is selected, align `backend/app/core_finance/pnl_bridge.py` with `backend/app/core_finance/attribution_core.py` or document the explicit difference; regression should cover `actual_pnl=0` with nonzero explained/residual in `tests/test_pnl_bridge_core.py`.
- **P1-07 Macro liquidity score polarity**: completed 2026-07-03 under Option B; keep any future cross-asset narrative aligned with `liquidity_score` as looseness-positive and `composite_score` as bond-unfavorable/tightness-positive.
- **P1-09 Balance movement share source**: after the authoritative share source is selected, update `frontend/src/features/balance-movement-analysis/pages/BalanceMovementAnalysisPage.tsx` to prefer the governed backend value or clearly label visible-row share; regression should extend `frontend/src/test/BalanceMovementAnalysisPage.test.tsx` for backend value precedence and missing-share display.
- **P1-10 Frontend formal aggregation**: after backend-vs-frontend aggregation ownership is approved, move or label formal aggregation currently in `frontend/src/features/pnl/yieldAnalysis/yieldAnalysisAggregates.ts` and `frontend/src/features/pnl/zqtzAdbAvgRollup.ts`; regression should keep DTO consumption and non-formal helper boundaries explicit in the corresponding frontend tests.
- **P1-11 Credit spread rating-tenor matrix**: after matrix ownership is approved, render a governed backend matrix or explicitly document frontend ownership in `frontend/src/features/bond-analytics/components/CreditSpreadView.tsx`; regression should update `frontend/src/test/CreditSpreadView.test.tsx` for rating/tenor bucket boundaries and missing governed matrix behavior.
