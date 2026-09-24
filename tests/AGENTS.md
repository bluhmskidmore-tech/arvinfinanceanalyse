# AGENTS.md

## Default Test Boundary

Tests under `tests/` and `backend/tests/` default to validating the repo-wide `Phase 2` formal-compute mainline.

### Allowed default scope (no extra marker required)

- formal balance
- formal PnL
- formal FX
- formal yield curve
- PnL bridge
- risk tensor
- core bond-analytics formal read surfaces
- outward `result_meta` / `basis` / lineage semantics for the above

### Scoped allowance inside an otherwise excluded surface

These are not part of the formal-compute mainline, but existing tests are allowed as landed-surface regression guards:

- **Executive E1 stable surfaces** only (per `docs/V3_CUTOFF_EXIT_CRITERIA.md`):
  - golden/release contracts for GS-EXEC-OVERVIEW-A / GS-EXEC-PNL-ATTR-A / GS-EXEC-SUMMARY-A
  - included E1 route contracts and `formal_use_allowed=false` semantics
  - reserved/excluded executive routes that must stay 503 fail-closed
- **Fail-closed / contract-only tests** on excluded surfaces (404/503 guards, schema/envelope contracts, disclosure drift, governance compaction) when they do not assert new business behavior beyond the currently landed surface.

All other behavior on excluded surfaces requires an explicit scoped marker.

## Excluded surfaces — inventory reality (2026-08 audit)

The repo contains substantial legacy suites on excluded surfaces. They exist; they are not reinterpreted as Phase 2 formalization.

| Prefix / surface | Files (`tests/`) | Collected cases | Default CI |
| --- | ---: | ---: | --- |
| `agent*` (+ dexter/hermes agent) | 27 | 395 | excluded |
| `livermore*` / market-data livermore | 32 | 431 | excluded |
| `macro_toolkit*` | 16 | 287 | excluded |
| `qdb_gl*` | 6 | 91 | excluded |
| `liability_analytics*` | 6 | 56 | excluded |
| `source_preview*` | 5 | 70 | excluded |
| `choice_news*` | 5 | 53 | excluded |
| `executive*` (+ 1 backend reserved test) | 12 | 151 | partially scoped |
| `macro_vendor*` / non-livermore `market_data*` | 5 | 43 | excluded |
| frontend excluded-surface tests | ~150+ files | (vitest; not pytest) | excluded |

Total excluded-surface pytest inventory: about 1,577 cases. This inventory is regression debt, not evidence that these surfaces are repo-wide formalized.

## Three enforcement tiers

1. **Default mainline (allowed).** Phase 2 formal-compute tests run in default PR/local loops without special markers.
2. **Legacy regression protection on excluded surfaces (allowed, frozen).**
   - Existing fail-closed, schema/envelope, disclosure-drift, governance, and E1 executive guard tests may remain.
   - They carry `@pytest.mark.excluded_surface_regression` plus one surface tag.
   - Do not add new cases unless the task explicitly enters that excluded surface and the test proves fail-closed behavior, contract stability, or non-expanding regression of already-landed behavior.
3. **Excluded-surface feature acceptance (restricted).**
   - Tests that enable excluded features (`MOSS_AGENT_ENABLED=true`, source-preview HTTP, choice-news routes, livermore/materialize pipelines, qdb_gl analytical compute, macro_toolkit script/ETL expansion, liability compat compute expansion) are not default-boundary work.
   - Existing suites are grandfathered only if marked; new acceptance tests are forbidden unless the surface receives an explicit repo-wide boundary promotion in governance docs.
   - Default selection should use `-m "not excluded_surface_acceptance"`.

## Required markers

Registered in `pytest.ini`:

- `excluded_surface_regression`: grandfathered guard/contract tests on excluded surfaces
- `excluded_surface_acceptance`: feature/workflow/ETL/materialize acceptance on excluded surfaces
- Surface tags (exactly one primary tag per test module or class): `surface_agent_mvp`, `surface_agent_eval`, `surface_livermore`, `surface_macro_toolkit`, `surface_qdb_gl`, `surface_liability_analytics`, `surface_source_preview`, `surface_choice_news`, `surface_executive`, `surface_macro_data`, `surface_market_data`

Module-level `pytestmark` is preferred over per-test duplication.

## Directory convention (recommended follow-up)

Grandfathered excluded-surface suites should migrate to `tests/excluded_surfaces/<surface>/`. Default pytest `testpaths` stays `tests/` + `backend/tests/`, but release/PR fast loops should exclude that directory unless the task scope explicitly includes the surface.

## Explicitly excluded from default scope (unchanged intent)

- `executive.*` governed rollout beyond landed E1 stable surfaces and reserved-route fail-closed guards
- Agent MVP / real `/api/agent/query` production enablement
- `source_preview` / `macro-data` / `choice-news` / `market-data` preview-vendor-analytical expansion
- `qdb_gl_monthly_analysis`、`liability_analytics_compat` 等 analytical-only / compatibility 模块的范围扩张
- broad frontend rollout on excluded pages/workflows

Historical scoped overrides remain relevant for legacy streams, but must not reinterpret excluded surfaces as Phase 2 formal-compute mainline.

## Authoring rules

- Respect this file before adding tests.
- If a change touches an excluded surface, run only the smallest marked subset for that surface; do not widen default gates.
- Never use excluded-surface green tests as evidence of formalization unless matching governance docs promote the surface.
