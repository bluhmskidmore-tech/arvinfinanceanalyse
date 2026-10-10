# AGENTS.md

## Default Test Boundary

For `tests/` and `backend/tests/`, use DOCUMENT_AUTHORITY.md for [scope authorization](../docs/DOCUMENT_AUTHORITY.md#阶段边界规则) and [current surface boundaries](../docs/DOCUMENT_AUTHORITY.md#current-surface-boundaries). Development scope and CI selection are separate. Markers classify tests; neither existing suites nor green results establish formalization.

Open cube-query and liability-analytics endpoints retain their access, response, and basis disclosure contracts. Do not restore a historical blanket 503 or reclassify their existing suites merely because the endpoints are open.

## Test selection

The following entry points were checked on 2026-09-20. Read their current selectors before claiming gate coverage; configured selection alone is not a successful execution record.

- **Bounded backend release gate:** [`scripts/backend_release_suite.py`](../scripts/backend_release_suite.py) owns the explicit file lists and the default `not excluded_surface_acceptance` filter. Mainline classification alone does not add a file to this gate.
- **Other PR checks:** [`.github/workflows/ci.yml`](../.github/workflows/ci.yml) also has a `Run agent harness tests` step with its own explicit list. Agent tests are not categorically excluded from PR CI.
- **Frontend CI:** the workflow runs `npm test`; [`frontend/package.json`](../frontend/package.json), [`vitest-safe.mjs`](../frontend/scripts/vitest-safe.mjs), and [`vitest.config.ts`](../frontend/vitest.config.ts) define execution. There is no business-surface exclusion in the current Vitest selector.
- **Full backend CI:** the workflow's `backend-full-pytest` matrix runs on schedule, pushes to `main`, and main-targeted PRs explicitly labeled `full-backend-regression`. Linux and Windows both collect the complete suite, then execute complementary `windows_native` selections without the bounded gate's business-surface filter. `backend-full-pytest-partition` checks the complete Linux node ledger, matching Windows native nodes and test function inventories, and every selected node's JUnit result; legitimate unselected portable parameter variants are recorded, and Windows native contracts must execute without skips. Both platform artifacts and this combined check are required for a full-suite claim. The label keeps subsequent PR updates opted in until removed. This does not promote excluded surfaces.
- **Local task verification:** choose the smallest relevant files and, where applicable, markers. Interpreter and command guidance lives in [`tests/CLAUDE.md`](CLAUDE.md); full CI collection is not a requirement for every task.

## Three enforcement tiers

1. **Default mainline (allowed).** Formal-compute tests and their `result_meta` / `basis` / lineage contracts need no excluded-surface marker; execution depends on the selected files and gate.
2. **Legacy regression protection on excluded surfaces (allowed, frozen).**
   - Existing fail-closed, schema/envelope, disclosure-drift, governance, and E1 executive guard tests may remain.
   - Preserve E1 golden/release contracts (GS-EXEC-OVERVIEW-A / GS-EXEC-PNL-ATTR-A / GS-EXEC-SUMMARY-A), `formal_use_allowed=false`, and reserved executive 503 guards.
   - They carry `@pytest.mark.excluded_surface_regression` plus one surface tag.
   - Do not add new cases unless the task explicitly enters that excluded surface and the test proves fail-closed behavior, contract stability, or non-expanding regression of already-landed behavior.
3. **Excluded-surface feature acceptance (restricted).**
   - Tests that enable excluded features (`MOSS_AGENT_ENABLED=true`, source-preview HTTP, choice-news routes, livermore/materialize pipelines, qdb_gl analytical compute, macro_toolkit script/ETL expansion, liability compat compute expansion) are not default-boundary work.
   - New acceptance tests require task authorization or an applicable scoped override. An existing user instruction covering the workflow satisfies task authorization; do not ask again solely because the surface is excluded. Keep `excluded_surface_acceptance` plus the surface tag; scoped authorization does not imply repo-wide promotion.
   - Do not expand default gates as a side effect of scoped acceptance work. The bounded release gate excludes acceptance by default; the separate full-CI selector above remains unchanged.

## Required markers

Registered in `pytest.ini`:

- `excluded_surface_regression`: grandfathered guard/contract tests on excluded surfaces
- `excluded_surface_acceptance`: feature/workflow/ETL/materialize acceptance on excluded surfaces
- Surface tags (exactly one primary tag per test module or class): `surface_agent_mvp`, `surface_agent_eval`, `surface_livermore`, `surface_macro_toolkit`, `surface_qdb_gl`, `surface_liability_analytics`, `surface_source_preview`, `surface_choice_news`, `surface_executive`, `surface_macro_data`, `surface_market_data`

Module-level `pytestmark` is preferred over per-test duplication.

## Directory convention

Keep existing test paths unless the task requires a move. If suites move to `tests/excluded_surfaces/<surface>/`, update their explicit selectors and references in the same change; directory placement alone does not exclude them. Current pytest `testpaths` remains `tests/` + `backend/tests/`.

## Authoring rules

- If a change touches an excluded surface, run only the smallest marked subset for that surface; do not widen default gates.
