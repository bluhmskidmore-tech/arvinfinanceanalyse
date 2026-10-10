# GS-RISK-WARN-B Approval

- Sample ID: `GS-RISK-WARN-B`
- Status: `captured-awaiting-approval`
- Sample type: `capture-ready`
- Owner: `TBD`
- Approver: `TBD`
- Approved at: `TBD`

## Capture note

The deterministic fixture was recaptured on 2026-09-05 with `rv_risk_tensor_formal_materialize_v8`. Every field in `result`, including warning disclosures, is identical to the previous capture. Prior/new responses and the comparison receipt are retained in `.codex-tmp/global-repair-2026-09-05/fixed-income/golden-recapture-4dxb_rc9/`. This records technical recapture only; owner approval remains pending.

- `response.json` has been captured from a deterministic degraded-snapshot path.
- Re-recorded `2026-08-13` because `e8fbafa6` (`fix(convexity): replace the zero-coupon approximation with cash-flow convexity`) moved the risk-tensor materialization rule version to `rv_risk_tensor_formal_materialize_v6`. The re-capture was diffed against the previous file first: the only changes are `rule_version`/`cache_version` v5→v6 and `portfolio_convexity.raw` `174.83326646` → `210.17236948`. Both values were independently reproduced from the two duration-denominator bonds to all 8 decimals — the old one under the retired `D(D+1)/(1+y/f)²` caliber, the new one under the standard cash-flow convexity — while duration/DV01/KRD/CS01, all exclusion disclosures, and the warning list stayed bit-identical.
- Approval is still pending.

## Truth note

- This sample protects current risk warning semantics for partial materialized snapshot rows.

## Recapture record — 2026-09-02

- Reason: the fixed-income caliber version set moved to `rv_risk_tensor_formal_materialize_v7` because the engine now merges a coupon schedule to the nearest whole period when the ACT/365 drift is within a tenor-scaled leap-day tolerance (`min(N/4 + 2, 365/(2f) − 1)` days, see `docs/calc_rules.md` "正式口径的整期日历归并与负收益率"; previously only ≤ 0.01 period, otherwise `ROUND_CEILING`). CB-001 matures 2048-03-31: 8036 days = 22.0164 years (six leap days), so the old caliber priced 23 annual cash flows including a phantom coupon 6 days after the report date; the new caliber prices 22 whole periods.
- Key changes: `portfolio_modified_duration` / `rate_risk_modified_duration` `12.245511 → 12.5096929`; `portfolio_dv01` / `rate_risk_dv01` / `regulatory_dv01` / `cs01` `0.42748515 → 0.436662`; `krd_30y` `0.30694319 → 0.31612004`; `portfolio_convexity` `210.17236948 → 215.33698505`; `rule_version` / `cache_version` v6→v7. Exclusion disclosures (`duration_excluded_*`, `missing_maturity_*`, `payment_frequency_fallback_*`), warnings, and bond counts are unchanged.
- Independent reproduction: both durations were re-derived outside the engine from the two duration-denominator bonds (CB-001 coupon 3% / ytm 3.2% / annual, MV 190; CB-002 coupon 4% / ytm 4.5% / annual, 10 whole years, MV 140) — old `12.245511` from a 23-cash-flow sum with first period 0.0164y, new `12.5096929` from the 22-period closed form `D = (1+y)/y − [(1+y) + n(c−y)] / [c((1+y)^n − 1) + y]`, `Dmod = D/(1+y)`, MV-weighted over 330; DV01 `(200·Dmod₁ + 150·Dmod₂)/10000` reproduces `0.42748515` and `0.436662` respectively.
- Approval boundary: this records the re-capture only; final approver and approval timestamp remain pending.

## Isolated technical recapture — 2026-09-05, full-worktree acceptance

The existing capture-ready fixture was executed against a fresh temporary database using `rv_risk_tensor_formal_materialize_v9`. Every business field in result is unchanged. Only rule/cache metadata and per-run identifiers or timestamps differ. No production database was read or written.

Before SHA-256: `7974282ba27db3c5252e4b37f61030b5816d90584314f520c4458280704f1ef0`. Captured response SHA-256: `99e5946f446943cd44bbedaef3c8e58526a9468c48e60fdfd9be6432445da317`. The before/after payloads, isolation receipt and semantic diff are retained under `.codex-tmp/full-worktree-acceptance-2026-09-05/golden-recapture/GS-RISK-WARN-B/`. This is technical recapture evidence only; business-owner approval remains PENDING and no formal-use permission is added.

## Isolated technical recapture — 2026-09-18, v10 liability-maturity disclosure

The deterministic degraded fixture was executed against a fresh temporary database using `rv_risk_tensor_formal_materialize_v10`; no production DuckDB was read or written. The response adds `missing_liability_maturity_count == 0` and `missing_liability_maturity_principal_amount.raw == 0.0`. Its existing missing-maturity warning is asset-side, so this fixture has no excluded undated liability. Every pre-existing business value, warning, and 30/90-day liquidity gap is unchanged. The other differences are the v9→v10 rule/cache metadata and per-run `trace_id` / `generated_at` values.

Before SHA-256: `99e5946f446943cd44bbedaef3c8e58526a9468c48e60fdfd9be6432445da317`. Captured response SHA-256: `aa793441edc35c70b7276caea7964b6e394a7e27bb45d80f964afd77627c06ab`. The before/after payloads, isolation receipt and semantic diff are retained under `.codex-tmp/risk-tensor-v10-golden-recapture-20260918/GS-RISK-WARN-B/`. This is technical recapture evidence only; business-owner approval remains PENDING, and the `Owner` / `Approver` fields above remain intentionally unfilled.

## Technical recapture — 2026-09-27

The undated TB-001 is unknown maturity 1/99, not a fund; prior DV01 and duration-scope values did not change. This is a deterministic technical recapture only; business-owner approval and formal-use permissions remain unchanged. Evidence: output/audits/2026-09-27/release-repair/backend/golden-diffs/ and golden-semantic-review/REPORT.md.
