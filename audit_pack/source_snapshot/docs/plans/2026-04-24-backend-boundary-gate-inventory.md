# Backend Boundary Gate Inventory

## Status

- date: 2026-04-24
- scope: read-only inventory for boundary governance
- purpose: show which backend rules are already protected before adding new gates

## Current Backend Gates

| gate | protects | note |
| --- | --- | --- |
| `scripts/backend_release_suite.py` | bounded release gate | Includes result-meta and golden-sample checks; current canonical backend gate is documented in `docs/DOCUMENT_AUTHORITY.md`. |
| `scripts/governed_phase2_preflight.py` | live route smoke and reserved route status | Checks included routes and reserved/excluded public routes with expected statuses. |
| `tests/test_result_meta_required.py` | `ResultMeta` schema fields | Protects `quality_flag`, `fallback_mode`, `formal_use_allowed`, `scenario_flag`, and related governance fields. |
| `tests/test_result_meta_basis_contract.py` | basis semantics | Protects `formal/scenario/analytical` combinations for `formal_use_allowed` and `scenario_flag`. |
| `tests/test_result_meta_on_all_ui_endpoints.py` | UI/API envelope shape | Protects `{ result_meta, result }` on governed endpoints and verifies excluded executive surfaces fail closed without `result_meta`. |
| `tests/test_formal_compute_result_meta_contract.py` | shared formal result helper | Protects formal result helper semantics and envelope construction. |
| `tests/test_formal_compute_runtime_contract.py` | formal materialize runtime | Protects run records, manifest, and writer-failure lineage semantics. |
| `tests/test_balance_analysis_boundary_guards.py` | formal formulas in `core_finance` | Protects balance-analysis formal derivation boundary. |
| `tests/test_pnl_layer_boundary_guards.py` | PnL layer boundary | Protects formal PnL layer separation. |
| `tests/test_cube_query_api.py` | reserved cube-query public routes | Protects current `503 reserved surface` behavior. |
| `tests/test_liability_analytics_api.py` | reserved liability compatibility routes | Protects current `503 reserved surface` behavior. |
| `tests/test_liability_analytics_envelope_contract.py` | liability compatibility envelope semantics | Protects that retained compatibility assets do not imply current public rollout. |
| `tests/test_golden_samples_capture_ready.py` | golden sample package structure and validators | Protects request/response/assertions/approval structure and sample validators. |

## Rules Already Covered

- Governed UI/API result endpoints must return `result_meta` and `result`.
- Formal/scenario/analytical basis combinations must stay explicit.
- Reserved/excluded public routes must fail closed with `503`.
- Reserved routes must not return a governed `{ result_meta, result }` envelope.
- Formal compute read models must preserve lineage through result metadata.
- Existing golden samples must remain capture-ready.

## Visible Gaps

- The backend gate inventory is not yet linked to a single "new feature checklist" that developers can run before promoting a page.
- Some guarded rules are spread across tests and docs; a newcomer may not know which targeted test bundle to run for a new surface.
- Product-category PnL now has a golden sample but should be checked against the page-contract binding gap before treating it as fully cataloged in the main page contract file.
- Future promoted routes need a repeatable recipe for moving from `reserved fail-closed` to `analytical overlay` or `formal live`.

## Recommended Next Test/Docs Slice

Do not add broad new backend tests first. Add a small docs/test index that maps:

```text
boundary class -> required tests -> sample/page/metric evidence
```

Candidate follow-up:

- update or add a docs-contract test that verifies `docs/SYSTEM_BOUNDARY_GOVERNANCE_OPERATING_MODEL.md` references the current canonical gate and boundary classes.
- only after the first page closure slice, add one page-specific regression test for the promoted page.

## Useful Commands

```powershell
python scripts/backend_release_suite.py
python scripts/governed_phase2_preflight.py
python -m pytest -q tests/test_result_meta_required.py tests/test_result_meta_basis_contract.py tests/test_result_meta_on_all_ui_endpoints.py
python -m pytest -q tests/test_cube_query_api.py tests/test_liability_analytics_api.py tests/test_golden_samples_capture_ready.py
```
