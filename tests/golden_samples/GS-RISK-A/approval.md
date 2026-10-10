# GS-RISK-A Approval

- Sample ID: `GS-RISK-A`
- Status: `captured-awaiting-approval`
- Sample type: `capture-ready`
- Owner: `TBD`
- Approver: `TBD`
- Approved at: `TBD`

## Capture note

The deterministic fixture was recaptured on 2026-09-05 with `rv_risk_tensor_formal_materialize_v8`. Every field in `result` is identical to the previous capture. Prior/new responses and the comparison receipt are retained in `.codex-tmp/global-repair-2026-09-05/fixed-income/golden-recapture-4dxb_rc9/`. This records technical recapture only; owner approval remains pending.

- `response.json` has been captured from the deterministic `REPORT_DATE=2026-03-31` fixture-backed materialization path.
- Re-recorded `2026-08-13` because `e8fbafa6` (`fix(convexity): replace the zero-coupon approximation with cash-flow convexity`) moved the risk-tensor materialization rule version to `rv_risk_tensor_formal_materialize_v6`. The re-capture was diffed against the previous file first: the only changes are `rule_version`/`cache_version` v5→v6 and `portfolio_convexity.raw` `35.23794449` → `37.92819750`. Both values were independently reproduced from the fixture bonds to all 8 decimals — the old one under the retired duration-approximation caliber `D(D+1)/(1+y/f)²`, the new one under the standard cash-flow convexity — while duration/DV01/KRD/CS01 and every other field stayed bit-identical.
- Approval is still pending.

## Truth note

- This sample is the first formal risk-tensor truth pack.
- Treat any changes to DV01/KRD/CS01/convexity/liquidity metrics as high-risk contract changes.

## Metadata-only recapture record — 2026-09-02

- Reason: the fixed-income caliber version set moved to `rv_bond_analytics_formal_materialize_v3` / `rv_risk_tensor_formal_materialize_v7` (整期日历归并 + 合法负收益率贴现, see `docs/calc_rules.md` "Fractional-period duration dual caliber").
- Key changes: `result_meta.rule_version` / `cache_version` v6→v7 and `result_meta.data_built_at`. Every tensor value in `result` is numerically identical to the previous file (integer-valued fields now serialize as `0`/`1`/`14`/`429` instead of `0.0`/`1.0`/`14.0`/`429.0`, which is a JSON formatting difference only): the clean fixture has no whole-period bond affected by the calendar-merge change and no negative yield.
- Approval boundary: this records the re-capture only; final approver and approval timestamp remain pending.

## Isolated technical recapture — 2026-09-05, full-worktree acceptance

The existing capture-ready fixture was executed against a fresh temporary database using `rv_risk_tensor_formal_materialize_v9`. Every business field in result is unchanged. Only rule/cache metadata and per-run identifiers or timestamps differ. No production database was read or written.

Before SHA-256: `f67274b35cd8e8025e61afc6a14e26732b071f56915b0dcf72b46ea568cc3046`. Captured response SHA-256: `a775d461f560b3ce364c20f294c8ce61452c7f9a69d3f3de970900e990bc7d93`. The before/after payloads, isolation receipt and semantic diff are retained under `.codex-tmp/full-worktree-acceptance-2026-09-05/golden-recapture/GS-RISK-A/`. This is technical recapture evidence only; business-owner approval remains PENDING and no formal-use permission is added.

## Isolated technical recapture — 2026-09-18, v10 liability-maturity disclosure

The deterministic capture-ready fixture was executed against a fresh temporary database using `rv_risk_tensor_formal_materialize_v10`; no production DuckDB was read or written. The response adds `missing_liability_maturity_count == 0` and `missing_liability_maturity_principal_amount.raw == 0.0`, because this fixture contains no liability row without a maturity date. Every pre-existing business value, including the 30/90-day liquidity gaps, is unchanged. The other differences are the v9→v10 rule/cache metadata and per-run `trace_id` / `generated_at` values.

Before SHA-256: `a775d461f560b3ce364c20f294c8ce61452c7f9a69d3f3de970900e990bc7d93`. Captured response SHA-256: `e29eaa9f826b9635107bcc47a03045602a2ebb6eb9945e3fc5c4205b0c1dc9e4`. The before/after payloads, isolation receipt and semantic diff are retained under `.codex-tmp/risk-tensor-v10-golden-recapture-20260918/GS-RISK-A/`. This is technical recapture evidence only; business-owner approval remains PENDING, and the `Owner` / `Approver` fields above remain intentionally unfilled.

## Technical recapture — 2026-09-27

The new maturity groups are explicitly zero for the clean materialized seed; prior risk values did not change. This is a deterministic technical recapture only; business-owner approval and formal-use permissions remain unchanged. Evidence: output/audits/2026-09-27/release-repair/backend/golden-diffs/ and golden-semantic-review/REPORT.md.
