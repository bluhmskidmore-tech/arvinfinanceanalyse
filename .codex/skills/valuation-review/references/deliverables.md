# Review Deliverables

Use the smallest deliverable set that answers the request. Keep reported, recomputed, adjusted, and selected values distinct in every table.

## 1. Scope and Evidence Register

| Field | Required content |
| --- | --- |
| Review object | Entity, security, ownership basis, workbook/package version |
| Dates | Valuation date, report date, source/as-of dates |
| Basis | Accounting/policy basis, enterprise/equity basis, scenario |
| Units | Currency, scale, per-share/total convention |
| Evidence | Source, owner, version, location, verification status |
| Limitation | Missing, stale, inaccessible, contradictory, or reviewer-supplied item |

Label each key input as `supplied`, `externally verified`, `model-derived`, `reviewer assumption`, or `unresolved`.

## 2. Valuation Summary

For each company/security, show reported value, independently recomputed range, absolute and percentage difference, methodology, major assumptions, integrity status, conclusion status, and top flags.

## 3. Findings Register

| ID | Severity | Area | Finding | Evidence | Value impact | Recommended action | Owner/status |
| --- | --- | --- | --- | --- | --- | --- | --- |

Use:

- **Critical:** foundational break or missing evidence makes the conclusion unreliable or materially misstated.
- **Warning:** potentially material weakness, policy deviation, stale input, or sensitivity that requires judgment or correction.
- **Info:** non-material observation, disclosure improvement, or control enhancement.

State the affected output and quantify impact as an amount/range where possible. Do not use severity as a substitute for materiality evidence.

## 4. Method and Valuation Bridge

Show reported and reviewer low/base/high by method, enterprise-to-equity adjustments, unweighted reconciliation, policy-approved weights, weighted contributions when authorized, selected range/mark, and residual difference. Every row must carry currency, unit, date, and source.

## 5. Sensitivity and Scenario Pack

Include the actual base case, symmetric or policy-approved axes, bull/base/bear assumptions, selected outputs, monotonicity/wiring result, and sample independent recalculations. Highlight a center cell only when it matches the active base assumptions.

## 6. NAV, Returns, and Waterfall

When in scope, deliver a fund NAV roll-forward, portfolio-company aggregation, realized/unrealized split, gross/net MOIC and IRR, value-creation attribution, LP/GP allocation, carry/clawback mechanics, and an explicit residual check.

## 7. Reviewer Conclusion

Use one of:

- `Supportable within the stated range`
- `Supportable subject to listed warnings`
- `Not supportable on current evidence`
- `Unable to conclude`

Then state verified facts, remaining human policy decisions, required remediation, approvals still outstanding, and whether the output is draft/staged or approved. Never label a staged pack as externally issued.
