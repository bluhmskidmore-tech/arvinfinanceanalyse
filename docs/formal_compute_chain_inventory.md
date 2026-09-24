# Formal Compute Chain Inventory

Status label: supporting-only

Boundary: non-authorizing

This inventory is not a metric contract and not a source of formal truth.
It does not approve page closure.
It does not change formal_use_allowed.
It does not set or imply closure_approved.

## Purpose

This file is a derived traceability index for the repo-wide Phase 2 formal-compute mainline. It records where each chain is implemented, read, tested, and governed. It links outward to existing authority anchors instead of restating business meaning.

Lane A completion proves only that trace links are present. It does not prove page maturity, metric approval, release readiness, or downstream bank-material readiness.

## Hard Rules

- No formulas.
- No unit definitions.
- No field semantics.
- No independent metric definitions.
- No page-closure approval.
- No formal-use promotion.

Business authority remains with `AGENTS.md`, `docs/DOCUMENT_AUTHORITY.md`, `docs/page_contracts.md`, `docs/metric_dictionary.md`, page-specific truth contracts, `docs/calc_rules.md`, `backend/app/core_finance/`, golden samples, and governing tests.

## Phase 2 Formal-Compute Mainline

| Chain | Route or read surface | Route maturity | Page contract | API and service anchors | Compute or materialization anchors | Fact or read surface anchors | Governing tests | Authority anchors | Gap or boundary note |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Formal balance | `/balance-analysis` | live / governed | `PAGE-BALANCE-001` | `backend/app/api/routes/balance_analysis.py`; `backend/app/services/balance_analysis_service.py`; `backend/app/services/balance_analysis_workbook_service.py` | `backend/app/core_finance/balance_analysis.py`; `backend/app/core_finance/balance_analysis_workbook.py`; `backend/app/tasks/balance_analysis_materialize.py`; `backend/app/tasks/formal_balance_pipeline.py` | `fact_formal_zqtz_balance_daily`; `fact_formal_tyw_balance_daily`; balance overview and workbook read models | `tests/test_balance_analysis_api.py`; `tests/test_balance_analysis_materialize_flow.py`; `tests/test_balance_analysis_workbook_contract.py`; `tests/test_golden_samples_capture_ready.py` | `docs/page_contracts.md` `PAGE-BALANCE-001`; `docs/metric_dictionary.md` `MTR-BAL-*`; `docs/calc_rules.md` | Average-balance and movement views are explanatory consumers, not replacements for this chain. |
| Formal PnL | `/pnl` | live / governed | `PAGE-PNL-001` | `backend/app/api/routes/pnl.py`; `backend/app/services/pnl_service.py` | `backend/app/core_finance/pnl.py`; `backend/app/tasks/pnl_materialize.py` | `fact_formal_pnl_fi`; `fact_nonstd_pnl_bridge`; PnL overview and data envelopes | `tests/test_pnl_api_contract.py`; `tests/test_pnl_materialize_flow.py`; `tests/test_pnl_formal_semantics_contract.py`; `tests/test_golden_samples_capture_ready.py` | `docs/page_contracts.md` `PAGE-PNL-001`; `docs/metric_dictionary.md` `MTR-PNL-*`; `docs/calc_rules.md` | Ledger and product-category pages remain separate governed or candidate consumers. |
| Formal FX | Market-data formal FX read surface | live / governed-mixed-source for `/market-data` | `PAGE-MKT-001` | `backend/app/api/routes/external_data.py`; `backend/app/services/external_data_service.py` | `backend/app/core_finance/fx_rates.py`; `backend/app/tasks/fx_mid_materialize.py`; `backend/app/tasks/fx_mid_backfill.py` | `fx_daily_mid`; formal FX status/read envelopes | `tests/test_fx_mid_materialize.py`; `tests/test_fx_docs_contract.py`; `tests/test_data_contracts_fx_daily_mid_section.py`; `tests/test_fx_analytical_view_api.py` | `docs/page_contracts.md` `PAGE-MKT-001`; `docs/metric_dictionary.md`; `docs/calc_rules.md` | Formal FX is a governed sub-surface inside a mixed-source market page. |
| Formal yield curve | Bond analytics term-structure read surface | non-route read surface | Linked through bond analytics contracts | `backend/app/api/routes/bond_analytics.py`; `backend/app/services/yield_curve_term_structure_service.py`; `backend/app/repositories/yield_curve_repo.py` | `backend/app/tasks/yield_curve_materialize.py`; `backend/app/core_finance/macro/yield_curve_shape.py` | `fact_formal_yield_curve_daily`; `yield_curve_daily`; term-structure envelope | `tests/test_yield_curve_term_structure_api.py`; `tests/test_yield_curve_materialize.py`; `tests/test_yield_curve_repo.py`; `tests/test_yield_curve_schema_contract.py` | `docs/calc_rules.md`; `docs/page_contracts.md`; `docs/metric_dictionary.md` | This row is a read-surface trace, not a standalone live route row. |
| PnL bridge | `/pnl-bridge` | live / governed | `PAGE-BRIDGE-001` | `backend/app/api/routes/pnl.py`; `backend/app/services/pnl_bridge_service.py` | `backend/app/core_finance/pnl_bridge.py`; `backend/app/tasks/pnl_materialize.py`; `backend/app/tasks/balance_analysis_materialize.py`; `backend/app/tasks/yield_curve_materialize.py` | PnL bridge envelope; formal PnL, formal balance, and yield-curve read inputs | `tests/test_pnl_api_contract.py`; `tests/test_pnl_bridge_core.py`; `tests/test_pnl_bridge_with_curve.py`; `tests/test_pnl_bridge_service_boundaries.py`; `tests/test_golden_samples_capture_ready.py` | `docs/page_contracts.md` `PAGE-BRIDGE-001`; `docs/metric_dictionary.md` `MTR-BRG-*`; `docs/calc_rules.md` | Bridge warning profiles are explicit read outcomes and must remain visible. |
| Risk tensor | `/risk-tensor` | live / governed | `PAGE-RISK-001` | `backend/app/api/routes/risk_tensor.py`; `backend/app/services/risk_tensor_service.py` | `backend/app/core_finance/risk_tensor.py`; `backend/app/core_finance/risk_tensor_regulatory_scope.py`; `backend/app/tasks/risk_tensor_materialize.py` | `fact_formal_risk_tensor_daily`; risk tensor dates and envelope | `tests/test_risk_tensor_api.py`; `tests/test_risk_tensor_core.py`; `tests/test_risk_tensor_materialize.py`; `tests/test_risk_tensor_service.py`; `tests/test_golden_samples_capture_ready.py` | `docs/page_contracts.md` `PAGE-RISK-001`; `docs/metric_dictionary.md` `MTR-RSK-*`; `docs/calc_rules.md` | Risk module-home summaries must point back to this formal risk page. |
| Core bond analytics formal read surfaces | Bond analytics API read surfaces; `/bond-analysis` route remains temporary-exception | temporary-exception for `/bond-analysis` | `GAP-BOND-ANALYSIS-PAGE`; related `PAGE-BOND-001` dashboard contract | `backend/app/api/routes/bond_analytics.py`; `backend/app/services/bond_analytics_service.py`; `backend/app/repositories/bond_analytics_repo.py` | `backend/app/core_finance/bond_analytics/`; `backend/app/tasks/bond_analytics_materialize.py` | `fact_formal_bond_analytics_daily`; bond analytics dates, headline, risk, and decomposition read models | `tests/test_bond_analytics_api.py`; `tests/test_bond_analytics_materialize_flow.py`; `tests/test_bond_analytics_core.py`; `tests/test_bond_analytics_service.py`; `tests/test_golden_samples_capture_ready.py` | `docs/page_contracts.md` `PAGE-BOND-001`; `docs/metric_dictionary.md`; `docs/calc_rules.md` | Dashboard samples do not automatically approve new dictionary rows. |

## Special Surface Boundary Notes

| Surface | Current source treatment | Inventory handling |
| --- | --- | --- |
| `/agent` | gated / hidden / development-only / `PAGE-AGENT-001` | Retained only to trace read-only and analytical development boundaries. This file does not authorize Agent MVP work, route publication, navigation exposure, or production enablement. |
| `/cube-query` | live / candidate / `PAGE-CUBE-QUERY-001` | Controlled query surface. It can expose result metadata for covered fact tables, but it is not a new page-level formal truth surface. |
| `/liability-analytics` | live / governed-mixed-source / `PAGE-LIAB-ANALYTICS-001` | Preserve formal, derived, and compatibility section boundaries. |
| `liability_analytics_compat` | non-route dependency note consumed by `/liability-analytics`; not a separate live frontend route | Record only as dependency context under `/liability-analytics`, not as a route row. |

## Execution Reporting Rules

- Lane A reports traceability coverage only.
- Lane B reports page and surface maturity using `docs/live_route_maturity.md`.
- Lane C reports regression status using targeted governance tests and `python scripts/backend_release_suite.py`.
- Bank-material generation stays deferred until page and evidence closure are explicit in their own authority surfaces.
