# GS-RISK-WARN-B Approval

- Sample ID: `GS-RISK-WARN-B`
- Status: `captured-awaiting-approval`
- Sample type: `capture-ready`
- Owner: `TBD`
- Approver: `TBD`
- Approved at: `TBD`

## Capture note

- `response.json` has been captured from a deterministic degraded-snapshot path.
- Re-recorded `2026-08-13` because `e8fbafa6` (`fix(convexity): replace the zero-coupon approximation with cash-flow convexity`) moved the risk-tensor materialization rule version to `rv_risk_tensor_formal_materialize_v6`. The re-capture was diffed against the previous file first: the only changes are `rule_version`/`cache_version` v5→v6 and `portfolio_convexity.raw` `174.83326646` → `210.17236948`. Both values were independently reproduced from the two duration-denominator bonds to all 8 decimals — the old one under the retired `D(D+1)/(1+y/f)²` caliber, the new one under the standard cash-flow convexity — while duration/DV01/KRD/CS01, all exclusion disclosures, and the warning list stayed bit-identical.
- Approval is still pending.

## Truth note

- This sample protects current risk warning semantics for partial materialized snapshot rows.
