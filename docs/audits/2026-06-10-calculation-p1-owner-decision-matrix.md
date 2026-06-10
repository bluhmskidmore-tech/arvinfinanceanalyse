# 2026-06-10 Calculation P1 Owner Decision Matrix

## Purpose

This matrix converts the 10 remaining open P1 findings from `docs/audits/2026-06-10-calculation-logic-audit.md` into owner-decision items. P1-08 bond-dashboard null handling is recorded below as verified closed in the current worktree, not as an owner-decision item. This matrix does not change code, approve metrics, or close any page. Its job is to make the next review meeting executable: each open row names the rule decision that must happen before implementation should proceed.

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
| P1-07 | Macro liquidity score polarity | Decide whether composite score components are tightness-positive or looseness-positive. | A: all components tightness-positive; B: liquidity remains looseness-positive but enters composite with inverse sign; C: separate liquidity narrative from composite. | Prefer A or B; current mixed polarity should not remain implicit. | Funding looseness can increase a "tightening / shorten duration" recommendation. | Unit test isolating liquidity movement with other components neutral; copy/contract states polarity. |
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

## Verified Closed Before Owner Review

| ID | Area | Closure Evidence | Residual Boundary |
| --- | --- | --- | --- |
| P1-08 | Bond dashboard null handling and false MoM | `frontend/src/features/bond-dashboard/utils/format.ts` preserves null governed numerics; `PortfolioTable.tsx` summary sums fail closed when a governed value is missing; `npm.cmd test -- src/features/bond-dashboard/utils/format.test.ts src/test/BondDashboardPage.test.tsx` passed with 2 files / 16 tests. | This closes the null-to-zero and false-MoM display hazard only. It does not certify Bond Dashboard business ownership, formal metric approval, or fixed-income rate-unit conventions. |
