# PnL End-to-End Acceptance Record - 2026-04-15

## Scope

This record covers the first deliverable PnL end-to-end loop:

- `/pnl`
- `/pnl-bridge`
- `/api/pnl/dates`
- `/api/pnl/overview`
- `/api/pnl/data`
- `/api/pnl/bridge`
- `/api/data/refresh_pnl`
- `/api/data/import_status/pnl`

Out of scope:

- `bond_analytics`
- `balance_analysis`
- `agent`
- new formal finance formulas
- frontend-side formal metric recomputation

## User-Visible Acceptance

The PnL workbench now supports:

- Open `/pnl` and `/pnl-bridge` through the workbench router.
- Select a backend-driven `report_date`.
- View PnL overview cards.
- View formal FI rows.
- View non-standard bridge rows.
- View PnL bridge summary, waterfall, warnings, and detail rows.
- See loading, empty, and error states.
- Trigger formal PnL refresh from the page.
- Inspect `result_meta` through a page-level debug panel.

## Dev Environment Used

Services were started locally:

- Frontend: `http://127.0.0.1:5888`
- API: `http://127.0.0.1:7888`
- PostgreSQL dev cluster: `127.0.0.1:55432`
- Dramatiq worker: `backend.app.tasks.worker_bootstrap`

Runtime PnL source files were copied into:

```text
tmp-governance/runtime-clean/data_input
```

This was required because the dev runtime data root points at `tmp-governance/runtime-clean/data_input`, not the repository `data_input` directory.

## Real API Evidence

`GET /api/pnl/dates` returned:

```json
{
  "report_dates": ["2026-02-28"],
  "basis": "formal",
  "result_kind": "pnl.dates",
  "cache_version": "cv_pnl_formal__rv_pnl_phase2_materialize_v1"
}
```

`GET /api/pnl/overview?report_date=2026-02-28` returned:

```json
{
  "report_date": "2026-02-28",
  "formal_fi_row_count": 1623,
  "nonstd_bridge_row_count": 141,
  "interest_income_514": "489386934.31",
  "fair_value_change_516": "50520633.95",
  "capital_gain_517": "36258436.24",
  "manual_adjustment": "0.00",
  "total_pnl": "576166004.50"
}
```

`GET /api/pnl/data?date=2026-02-28` returned:

```json
{
  "report_date": "2026-02-28",
  "formal_rows": 1623,
  "nonstd_rows": 141,
  "first_formal_instrument_code": "010221",
  "basis": "formal",
  "result_kind": "pnl.data"
}
```

`GET /api/pnl/bridge?report_date=2026-02-28` returned:

```json
{
  "report_date": "2026-02-28",
  "rows": 1623,
  "quality_flag": "error",
  "result_kind": "pnl.bridge"
}
```

The bridge `quality_flag=error` is a backend data-quality result, not a frontend failure.

## Refresh Evidence

`POST /api/data/refresh_pnl` returned queued:

```json
{
  "status": "queued",
  "job_name": "pnl_materialize",
  "trigger_mode": "async",
  "cache_key": "pnl:phase2:materialize:formal",
  "report_date": "2026-02-28"
}
```

`GET /api/data/import_status/pnl?run_id=...` reached completed:

```json
{
  "status": "completed",
  "job_name": "pnl_materialize",
  "cache_key": "pnl:phase2:materialize:formal",
  "cache_version": "cv_pnl_formal__rv_pnl_phase2_materialize_v1",
  "report_date": "2026-02-28",
  "trigger_mode": "terminal"
}
```

## Regression Coverage

Frontend:

```bash
npm test -- --run src/test/PnlPage.test.tsx src/test/PnlBridgePage.test.tsx src/test/PnlRoutesSmoke.test.tsx src/test/ApiClient.test.ts src/test/RouteRegistry.test.tsx
```

Result:

```text
96 passed
```

Backend:

```bash
python -m pytest tests/test_pnl_api_contract.py
```

Result:

```text
42 passed
```

Static checks:

```bash
npm run lint
npm run typecheck
```

Result:

```text
lint passed
typecheck passed
```

## Implementation Notes

The refresh dispatch path now converts `Decimal` values to JSON-safe strings before sending the Dramatiq message. Without this, Redis-backed Dramatiq dispatch failed with:

```text
TypeError: Object of type Decimal is not JSON serializable
```

Dispatch failures that are not safe for sync fallback now include:

- `error_message`
- `failure_category`
- `failure_reason`

This makes `/api/data/refresh_pnl` failures diagnosable from API detail and governance records.

## Formal Finance Impact

No formal finance formula changed.

The changes affect:

- UI consumption and debugging of existing formal PnL endpoints.
- Refresh dispatch serialization and failure diagnostics.
- Route-level smoke coverage.

They do not affect:

- H/A/T mapping.
- 514/516/517 formal semantics.
- formal/scenario isolation.
- PnL arithmetic.
- bridge formulas.

## Known Risks

- The dev runtime data root does not automatically include all PnL source folders; local acceptance required copying PnL source files into `tmp-governance/runtime-clean/data_input`.
- `/api/pnl/bridge` currently returns `quality_flag=error` for the accepted `2026-02-28` dataset. This is preserved as backend evidence and should be reviewed separately if business users expect clean bridge quality.
- The page-level `result_meta` panel is a debug view, not a full lineage drill UI.
