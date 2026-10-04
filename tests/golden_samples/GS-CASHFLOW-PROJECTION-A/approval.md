# GS-CASHFLOW-PROJECTION-A Approval

- Sample ID: `GS-CASHFLOW-PROJECTION-A`
- Status: `captured-awaiting-approval`
- Sample type: `capture-ready`
- Owner: `TBD`
- Approver: `TBD`
- Approved at: `TBD`
- Last reviewed: `2026-09-21`

## Capture Note

The deterministic fixture was recaptured on 2026-09-21 against `rv_cashflow_projection_read_v3` and the current `rv_bond_analytics_formal_materialize_v5` input rule. The controlled full-coverage scalar calculation values remain unchanged; the response now records duration coverage/exclusion amounts, coverage ratios, and all three direct input lineages. This records a technical recapture only; owner approval remains pending.

- `response.json` is captured from a deterministic fixture-backed service call for `GET /api/cashflow-projection?report_date=2026-04-30`.
- The fixture provides one formal asset row, one formal liability row, and one matching bond-analytics duration row, each with controlled source, rule, ingest-batch, and trace evidence.
- The sample freezes the `/cashflow-projection` candidate liquidity projection DTO boundary only.
- Re-captured `2026-08-14` after the monthly bucket boundary was corrected to include events through `report_date + horizon_months` inclusively. For report date `2026-04-30`, the deterministic response now includes the final `2028-04` calendar bucket; all previously frozen cashflow, duration, sensitivity, warning, unit, and precision values remain unchanged.

## Caveats

- This is route-scoped candidate evidence, not a page closure approval.
- It does not approve MTR-CFP metrics, formal liquidity truth, risk truth, balance truth, PnL truth, manual audit closure, or business-owner approval.
- `formal_use_allowed=false` must remain visible until the dedicated page contract, golden approval, governance evidence, manual audit, and owner approval are all closed.

## Metadata-only recapture record — 2026-09-02

- Reason: `cashflow_projection_service` now serializes Numeric fields with `preserve_decimal=True`, adding the exact-decimal `raw_text` sidecar.
- Key changes: `raw_text` added on every Numeric field (111 additions) and `result_meta.data_built_at`; every `raw` / `display` value is unchanged.
- Approval boundary: this records the re-capture only; final approver and approval timestamp remain pending.

## Technical recapture — 2026-09-27

The synthetic bond input now uses current v6 lineage; the stale-fact guard remained active, and the successful replay changed only that lineage identity. This is a deterministic technical recapture only; business-owner approval and formal-use permissions remain unchanged. Evidence: output/audits/2026-09-27/release-repair/backend/golden-diffs/ and golden-semantic-review/REPORT.md.
