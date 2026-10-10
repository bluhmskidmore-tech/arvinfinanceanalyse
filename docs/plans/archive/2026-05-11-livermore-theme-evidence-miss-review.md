# Livermore Theme Evidence And Miss Review Plan

Date: 2026-05-11

## Scope

Finish the existing Livermore theme breakout workflow without adding a new endpoint.

This plan touches only the Livermore stock strategy evidence path:

- Choice stock optional concept/movement evidence state.
- Livermore theme breakout core selection and rejected-cluster review.
- Stock analysis theme breakout rendering and tests.

This plan does not touch auth, scheduler, cache infrastructure, database platform
refactors, unrelated dashboard pages, or macro toolkit flows.

## Evidence

- The catalog already contains optional `concept_membership` and
  `intraday_movement` templates, but the production catalog entries remain
  unconfirmed.
- The schema and materializer already support
  `choice_stock_concept_membership` and
  `choice_stock_intraday_movement_event`.
- Local `data/moss.duckdb` contains base stock universe, sector membership, and
  daily observations through 2026-05-08, but does not currently contain the two
  real concept/movement tables.
- Project MCP requirements were attempted; `moss-metric-contracts` and
  `moss-lineage-evidence` were not exposed as callable tools in this session.
  GitNexus was available, but its MOSS-V3 index predates this work and is used
  only as impact evidence.

## Decision

Use the existing `theme_breakout` payload and add two optional surfaces:

1. `evidence_state`: service-owned provenance for concept and movement inputs.
2. `review_items`: core-owned, capped near-miss explanations produced from the
   same gate evaluation used for selected `items`.

Do not compute miss reasons in the frontend or service. The core owns selection
gates and failed-gate reasons. The frontend only renders optional fields.

## Contract Boundaries

- Catalog confirms vendor activation only. It must not encode scoring semantics.
- Materializer normalizes and persists raw optional evidence only.
- Loader/service owns table presence, row counts, matching state, diagnostics,
  and data-gap wording.
- Core finance owns theme grouping, gate evaluation, selected items, and
  rejected review items.
- Frontend contracts and page model render optional evidence and review fields
  without changing existing selected theme `items` semantics.

## Execution Tasks

1. Add failing backend tests for explicit evidence states:
   `catalog_unconfirmed`, `table_missing`, `landed_no_rows`, and `matched_rows`.
2. Refactor the theme core to evaluate candidate groups once, then derive both
   selected `items` and capped `review_items` with concrete failed gate codes.
3. Add service provenance to the `theme_breakout` payload and make diagnostics
   distinguish unconfirmed/missing/empty/matched evidence instead of inferring
   from `is_proxy`.
4. Add frontend contract/model/page tests for evidence-state labels and
   miss-review rendering.
5. Implement the smallest frontend rendering block under the existing theme
   breakout section.

## Acceptance

- Existing selected theme cards keep their current meaning.
- Real concept mode remains observation-only and only claims landed evidence
  when matched rows exist.
- Missing local concept/movement tables render as an explicit boundary, not as a
  silent neutral condition.
- A strong semiconductor-like cluster that fails breadth/strength gates appears
  in `review_items` with failed gate codes and observational copy.
- Targeted backend tests, targeted frontend tests, and `frontend` debt audit
  pass before completion.
