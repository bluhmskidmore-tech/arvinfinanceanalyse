# GS-BAL-WORKBOOK-A Approval

- Sample ID: `GS-BAL-WORKBOOK-A`
- Status: `captured-awaiting-approval`
- Sample type: `capture-ready`
- Owner: `arvin`
- Approver: `TBD`
- Approved at: `TBD`

## Capture note

- Workbook payload has been captured.
- Before approval, confirm section inventory against:
  - `GOVERNED_WORKBOOK_SUPPORTED_TABLE_KEYS`
  - `NOT_GOVERNED_OR_NOT_SUPPORTED_KEYS`

## Truth note

- This sample protects governed workbook structure and right-rail governance sections.
- Do not treat it as proof that every workbook table is numerically frozen.

## Recapture record — 2026-07-20

- Owner authorization: `arvin` authorized this recapture in-session.
- Reason: balance H-2 `currency_basis` remediation from the calculation-audit
  sequence (`fa074e13f` / `f9697fe4b`; direct service fetch wiring in
  `d440c11a3`) now uses CNY-projected facts for CNY workbook requests.
- Key changes: bond assets `0.01000000 → 0.07200000`, interbank liabilities
  `0.00100000 → 0.00720000`, and net position
  `0.00900000 → 0.06480000`; dependent table and operational-section values
  were recaptured consistently.
- Approval boundary: this records owner authorization to recapture; final
  approver and approval timestamp remain pending.

## Metadata-only recapture record — 2026-08-14

- Deterministic fixture recapture added explicit report-date, filter,
  source-table, and evidence-row fields; no workbook business value changed.
- Approval boundary is unchanged: final approver and approval timestamp remain
  pending.

## Recapture record — 2026-09-02

- Reason: the previous file predated `result_meta.source_surface`, `data_source`, and `calibration`, so `BalanceAnalysisWorkbookEnvelope` rejected it (`tests/test_api_response_model_field_preservation.py`). The full re-capture also surfaced three committed caliber changes that the selected-path validator never compared:
  - `tables[0]`（债券业务种类）`rows[0].bond_type` `国债 → 其它`: since `7081771c` (2026-05-05) the table uses the governed `classify_zqtz_asset_bond_label`, whose 国债 row is CNY-only; the fixture bond is USD-denominated (FX 7.20), so it falls to 其它. The Campisi table still groups by raw `bond_type`, hence shows 国债.
  - `tables[15]`（规则引用）4 → 7 rows: `bal_overdue_interest_days_placeholder`, `bal_campisi_benchmark_missing_null`, `bal_wb_rating_default_001` were registered after the previous capture.
  - `tables[22]`（Campisi）`spread_bp` / `spread_income_amount` `2.50000000 / 0.0000180000000000 → null`: rule `bal_campisi_benchmark_missing_null` — the fixture has no benchmark curve, so the spread is fail-closed to null instead of being assumed.
- Owner authorization: `arvin` (sample owner) reviewed the three content changes above and authorized this recapture in-session on 2026-09-02, mirroring the 2026-07-20 record.
- Approval boundary: this records owner authorization to recapture; the three content changes are committed governed behaviour, not new decisions. Final approver and approval timestamp remain pending.

## FIN002 limited recapture record — 2026-10-08

The user approved the complete/known coupon-income split and the necessary synthetic sample update in-session. This recapture reused the existing isolated balance fixture and workbook request. Only the FIN002 query rule/cache identity, its missing-benchmark warning, the Campisi fields/labels, and the corresponding rule-reference disclosure were updated. The sample has one coupon-observed asset with no policy-bond benchmark: coupon income and its known subtotal agree, absolute-face coverage is 100%, and both full and known spread comparisons remain null.

Trace and capture timestamps, all other workbook tables, cards, operational sections and the existing validator are retained. The candidate also contains an unrelated rate-distribution change; that change was not adopted in this limited update. This records the approved FIN002 recapture scope and preserves the sample's existing overall approval status.
