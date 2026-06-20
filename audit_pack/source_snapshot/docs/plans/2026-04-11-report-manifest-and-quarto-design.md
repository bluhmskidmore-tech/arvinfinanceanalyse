# Report Manifest And Quarto Design

**Date:** 2026-04-11

**Scope:** Define a boundary-safe reporting design for future Quarto integration without reopening Agent MVP or introducing a new compute path.

## Design Intent

MOSS should own the report contract. A renderer should consume governed report payloads after the service layer has already assembled the result.

This keeps reporting aligned with the system definition:

- frontend, management reports, and Agent are different consumers of the same analytics substrate
- renderers do not compute formal metrics
- Agent remains disabled until the documented upstream prerequisites are complete

## Current Boundary

This design does not authorize runtime implementation.

Still deferred:

- real Agent report generation
- Quarto renderer implementation
- persisted report generation tasks
- any UI that implies live report generation

Existing export routes are seam-mapping references only:

- [balance_analysis.py](/F:/MOSS-V3/backend/app/api/routes/balance_analysis.py:124)
- [product_category_pnl.py](/F:/MOSS-V3/backend/app/api/routes/product_category_pnl.py:109)

They must not become route-chaining dependencies for the future report path.

## Proposed Reporting Boundary

The future report path should be:

`governed service outputs -> ReportManifest + provenance envelope -> renderer adapter -> preview or persisted artifact`

Not allowed:

- renderer -> DuckDB
- renderer -> repository
- renderer -> storage internals
- renderer-side formal calculations
- renderer-side Formal and Scenario merge logic

## ReportManifest

### Minimum Required Fields

- `report_id`
- `report_family`
- `report_title`
- `basis`
- `scenario_flag`
- `as_of_date`
- `filters`
- `sections`
- `result_meta`
- `provenance_refs`
- `evidence_refs`
- `renderer_inputs`
- `artifact_mode`
- `preview_mode`
- `quality_flag`

### Renderer Inputs May Include

- section order
- chart and table block descriptors
- formatting hints
- output target hints

### Renderer Inputs May Not Include

- SQL
- DuckDB paths
- repository access instructions
- finance formulas
- route invocation instructions

## Formal Versus Scenario Requirements

### Formal Output Requirements

- `basis = formal`
- `scenario_flag = false`
- full `result_meta`
- `result_meta.source_version`
- `result_meta.rule_version`
- `result_meta.cache_version`
- `quality_flag`
- at least one `evidence_ref`

### Scenario Output Requirements

- `basis = scenario`
- `scenario_flag = true`
- full `result_meta`
- scenario parameter references
- provenance to upstream baseline inputs
- `quality_flag`

## Invalid Manifest Conditions

A manifest is invalid if any of the following is true:

- `basis` is missing
- `basis` conflicts with `scenario_flag`
- `result_meta` is absent
- provenance or evidence references are absent
- `artifact_mode` is absent
- `preview_mode` is absent
- renderer inputs contain raw-query or raw-storage instructions
- any section requires computation not already present in governed payloads

## Preview Flow

Preview is a read-only inspection surface.

Required properties:

- stateless
- read-only
- no storage write
- no task queue
- no artifact registration
- no claim of durable output

## Persisted Artifact Flow

Persisted artifacts are a governed output path.

Required properties:

- task-driven
- storage-backed
- auditable
- versioned
- artifact metadata recorded
- reproducible from manifest plus governed inputs

The intended future path is:

`request -> report service -> task -> storage artifact -> metadata and audit record`

## Boundary-Safe First Slice

The first allowed slice is documentation only.

It includes:

- `ReportManifest` schema draft
- provenance and evidence envelope draft
- renderer adapter interface draft
- preview flow contract
- persisted artifact flow contract
- renderer authorization checklist

## Exact Out-Of-Scope Slices

- real Agent-authored report generation
- Quarto renderer implementation
- PDF or HTML artifact persistence
- report task execution in `backend/app/tasks/`
- route-to-route composition
- CSV-to-report chaining
- Formal and Scenario merge logic
- any UI exposure implying the report path is live

## Renderer Adapter Authorization Review

Quarto can be authorized as the first renderer adapter only after the following are all true:

- `ReportManifest` schema approved
- provenance and evidence envelope approved
- renderer adapter contract approved
- preview versus artifact split documented
- non-goals documented and testable
- at least one report family mapped to governed service outputs without route chaining
- written note confirms Agent MVP remains closed

Owner:

- lead `architect`
- `verifier` sign-off
- user approval

## Verification Matrix

### Architecture Check

Pass:

- report path is `service/report-contract -> renderer adapter`

Fail:

- renderer touches DuckDB or repositories directly

### Boundary Check

Pass:

- design text keeps Agent reporting deferred

Fail:

- any text implies Agent MVP is reopened

### Non-Goal Enforcement

Pass:

- docs and review checklist explicitly forbid Quarto-side formal calculations, direct querying, route chaining, and CSV chaining

Fail:

- any allowed path includes one of those behaviors

### Preview Check

Pass:

- preview remains stateless, read-only, non-persistent

Fail:

- preview writes storage, registers artifacts, or depends on async generation

### Artifact Check

Pass:

- persisted artifacts require task execution, storage metadata, provenance, and reproducibility markers

Fail:

- persisted output exists without task, metadata, or audit path

### Golden Output Check

Pass:

- one approved fixture-backed manifest renders deterministically through the adapter boundary with required metadata present

Fail:

- rendering drops required fields, changes section meaning, or cannot reproduce the fixture output

## Non-Goals

- no renderer-side financial formulas
- no renderer-owned business semantics
- no replacement of the governed service layer
- no renderer-side Formal and Scenario reconciliation
- no reopening of Agent MVP through reporting language

## Recommended Next Step

Turn this design into:

1. an ADR-backed `ReportManifest` draft
2. a provenance and evidence envelope draft
3. a renderer adapter checklist

Only after that should MOSS decide whether Quarto is approved as the first renderer adapter.

Current draft artifact:

- [2026-04-11-report-manifest-schema-draft.md](/F:/MOSS-V3/docs/plans/2026-04-11-report-manifest-schema-draft.md)
