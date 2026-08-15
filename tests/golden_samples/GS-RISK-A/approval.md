# GS-RISK-A Approval

- Sample ID: `GS-RISK-A`
- Status: `captured-awaiting-approval`
- Sample type: `capture-ready`
- Owner: `TBD`
- Approver: `TBD`
- Approved at: `TBD`

## Capture note

- `response.json` has been captured from the deterministic `REPORT_DATE=2026-03-31` fixture-backed materialization path.
- Re-recorded `2026-08-13` because `e8fbafa6` (`fix(convexity): replace the zero-coupon approximation with cash-flow convexity`) moved the risk-tensor materialization rule version to `rv_risk_tensor_formal_materialize_v6`. The re-capture was diffed against the previous file first: the only changes are `rule_version`/`cache_version` v5→v6 and `portfolio_convexity.raw` `35.23794449` → `37.92819750`. Both values were independently reproduced from the fixture bonds to all 8 decimals — the old one under the retired duration-approximation caliber `D(D+1)/(1+y/f)²`, the new one under the standard cash-flow convexity — while duration/DV01/KRD/CS01 and every other field stayed bit-identical.
- Approval is still pending.

## Truth note

- This sample is the first formal risk-tensor truth pack.
- Treat any changes to DV01/KRD/CS01/convexity/liquidity metrics as high-risk contract changes.
