# ReportManifest Schema Draft

**Date:** 2026-04-11

**Status:** Draft

**Scope:** Define the draft contract for a future governed report manifest that can be consumed by a renderer adapter after service-layer assembly.

## Intent

`ReportManifest` is a renderer-agnostic contract.

It is not:

- a compute contract
- a DuckDB query contract
- a route-chaining contract
- an authorization to reopen Agent reporting

The manifest exists to let MOSS describe a report in governed terms after the service layer has already assembled the report payload.

## Normative References

This draft does not redefine existing truth sources.

- outward `result_meta`, `basis`, `formal_use_allowed`, and `scenario_flag` semantics:
  [CACHE_SPEC.md](/F:/MOSS-V3/docs/CACHE_SPEC.md)
- standardized and fact-table contract ownership:
  [data_contracts.md](/F:/MOSS-V3/docs/data_contracts.md)
- renderer and Quarto design boundary:
  [2026-04-11-report-manifest-and-quarto-design.md](/F:/MOSS-V3/docs/plans/2026-04-11-report-manifest-and-quarto-design.md)
- renderer authorization decision:
  [adr-report-contract-before-quarto-renderer.md](/F:/MOSS-V3/.omx/plans/adr-report-contract-before-quarto-renderer.md)

If this draft conflicts with `CACHE_SPEC.md` on outward semantics, `CACHE_SPEC.md` wins.

## Report Path Position

The intended future path is:

`governed service outputs -> ReportManifest -> renderer adapter -> preview or persisted artifact`

The manifest must never instruct the renderer to compute business results or access raw storage directly.

## Top-Level Shape

```json
{
  "report_id": "rpt_balance_summary_2026-03-31_formal_cny",
  "report_family": "balance_analysis_summary",
  "report_title": "Balance Analysis Summary",
  "report_version": "rm_v1_draft",
  "basis": "formal",
  "scenario_flag": false,
  "as_of_date": "2026-03-31",
  "artifact_mode": "preview",
  "preview_mode": "interactive",
  "filters": {
    "report_date": "2026-03-31",
    "position_scope": "asset",
    "currency_basis": "CNY"
  },
  "sections": [],
  "result_meta": {},
  "provenance_refs": [],
  "evidence_refs": [],
  "renderer_inputs": {},
  "quality_flag": "ok"
}
```

## Field Definitions

### Identity Fields

- `report_id`
  - string
  - unique per rendered report intent
  - should be deterministic for the same family, basis, date, and filter identity
- `report_family`
  - string
  - names the report contract family, for example `balance_analysis_summary`
- `report_title`
  - string
  - human-readable title
- `report_version`
  - string
  - version of the report manifest contract or family profile

### Basis Fields

- `basis`
  - enum: `formal` / `scenario` / `analytical`
  - outward semantics are owned by `CACHE_SPEC.md`
- `scenario_flag`
  - boolean
  - must be consistent with `basis`
  - only `basis=scenario` may use `true`

### Scope Fields

- `as_of_date`
  - ISO date string
  - report point-in-time anchor
- `filters`
  - object
  - report-family-specific filter identity
  - must only describe governed outward filters

### Delivery Fields

- `artifact_mode`
  - enum: `preview` / `persisted`
  - determines whether this manifest is intended for preview or durable artifact generation
- `preview_mode`
  - enum: `interactive` / `none`
  - `interactive` is allowed only for preview flows
  - `none` is required for persisted artifact-only execution paths

### Data and Provenance Fields

- `sections`
  - array of section descriptors
- `result_meta`
  - object
  - must conform to outward semantics defined by `CACHE_SPEC.md`
- `provenance_refs`
  - array of provenance reference objects
- `evidence_refs`
  - array of evidence reference objects
- `renderer_inputs`
  - object
  - renderer hints only
- `quality_flag`
  - string
  - report-level quality posture
  - should align with upstream governed result quality

## Required Fields

The following are always required:

- `report_id`
- `report_family`
- `report_title`
- `report_version`
- `basis`
- `scenario_flag`
- `as_of_date`
- `artifact_mode`
- `preview_mode`
- `filters`
- `sections`
- `result_meta`
- `provenance_refs`
- `evidence_refs`
- `renderer_inputs`
- `quality_flag`

## result_meta Rules

`result_meta` is not redefined here. It must carry the outward semantics already required by `CACHE_SPEC.md`.

At minimum, the manifest expects `result_meta` to include:

- `basis`
- `formal_use_allowed`
- `scenario_flag`
- `source_version`
- `rule_version`
- `cache_version`
- `generated_at`
- `trace_id`

If a renderer path uses vendor-backed payloads, `vendor_version` should also be present when governed upstream outputs expose it.

Top-level and nested consistency rules:

- `manifest.basis == result_meta.basis`
- `manifest.scenario_flag == result_meta.scenario_flag`
- `basis=formal` implies `result_meta.formal_use_allowed=true`
- `basis=scenario` implies `result_meta.formal_use_allowed=false`
- `basis=analytical` implies `result_meta.formal_use_allowed=false`

## Required Fields By Basis

### Formal

Required:

- `basis = formal`
- `scenario_flag = false`
- `result_meta.basis = formal`
- `result_meta.formal_use_allowed = true`
- `result_meta.source_version`
- `result_meta.rule_version`
- `result_meta.cache_version`
- `result_meta.trace_id`
- at least one `evidence_ref`
- at least one `provenance_ref`

Expected upstream lineage should point to governed formal facts, not snapshots or preview tables.

### Scenario

Required:

- `basis = scenario`
- `scenario_flag = true`
- `result_meta.basis = scenario`
- `result_meta.formal_use_allowed = false`
- `result_meta.source_version`
- `result_meta.rule_version`
- `result_meta.cache_version`
- `result_meta.trace_id`
- scenario parameter reference inside `provenance_refs` or section-scoped provenance
- at least one `evidence_ref`

Scenario manifests must preserve separation from Formal in basis, cache identity, and provenance.

### Analytical

Required:

- `basis = analytical`
- `scenario_flag = false`
- `result_meta.basis = analytical`
- `result_meta.formal_use_allowed = false`
- `result_meta.source_version`
- `result_meta.rule_version`
- `result_meta.cache_version`
- `result_meta.trace_id`

Analytical manifests must not claim formal usage rights through report wording or adapter behavior.

## Section Contract

Each `sections[]` entry describes a renderer-consumable report section.

Draft shape:

```json
{
  "section_id": "overview_cards",
  "section_kind": "kpi_grid",
  "title": "Overview",
  "payload_ref": "payload.overview.cards",
  "evidence_refs": ["ev_balance_overview_1"],
  "provenance_refs": ["prov_formal_balance_fact"],
  "renderer_hints": {
    "columns": 4
  }
}
```

Required fields:

- `section_id`
- `section_kind`
- `title`
- `payload_ref`
- `renderer_hints`

Optional but recommended:

- `evidence_refs`
- `provenance_refs`
- `quality_flag`

Rules:

- `payload_ref` points to governed assembled payload blocks, not to SQL or direct storage paths
- sections may declare display behavior only
- sections may not declare formulas, reconciliations, or fallback query logic

## provenance_refs Contract

`provenance_refs[]` identifies upstream governed inputs behind the report.

Draft shape:

```json
{
  "provenance_id": "prov_formal_balance_fact",
  "kind": "fact_table",
  "ref": "fact_formal_zqtz_balance_daily",
  "basis": "formal",
  "source_version": "sv_xxx",
  "rule_version": "rv_xxx",
  "trace_id": "tr_xxx"
}
```

Required fields:

- `provenance_id`
- `kind`
- `ref`
- `basis`

Recommended fields when available:

- `source_version`
- `rule_version`
- `vendor_version`
- `trace_id`

## evidence_refs Contract

`evidence_refs[]` identifies evidence anchors that support rendered claims or sections.

Draft shape:

```json
{
  "evidence_id": "ev_balance_overview_1",
  "kind": "result_block",
  "ref": "overview.total_market_value",
  "label": "Total market value card"
}
```

Required fields:

- `evidence_id`
- `kind`
- `ref`

Optional:

- `label`
- `section_id`
- `quality_flag`

## renderer_inputs Contract

`renderer_inputs` is intentionally narrow.

Allowed:

- section ordering
- layout hints
- typography or formatting hints
- output target hints like `html`, `pdf`, or `docx`
- asset slots that point to governed prepared assets

Forbidden:

- SQL
- DuckDB file paths
- repository access instructions
- service or route invocation instructions
- formulas
- transformation logic that changes basis semantics
- Formal and Scenario reconciliation logic

## Validity Rules

A `ReportManifest` is invalid if any of the following is true:

- required top-level fields are missing
- `basis` conflicts with `scenario_flag`
- `result_meta` is absent
- `result_meta.basis` conflicts with top-level `basis`
- `result_meta.scenario_flag` conflicts with top-level `scenario_flag`
- `provenance_refs` is empty
- `evidence_refs` is empty for `formal` or `scenario`
- `sections` references payload blocks that are not present in the governed assembled payload
- `renderer_inputs` includes raw-query or raw-storage instructions
- any section requires renderer-side computation
- `artifact_mode=preview` and `preview_mode=none`
- `artifact_mode=persisted` and `preview_mode=interactive` without an explicit separate preview manifest

## Preview And Persisted Artifact Rules

### Preview Manifest

Preview manifests must satisfy all of the following:

- `artifact_mode = preview`
- `preview_mode = interactive`
- no storage registration instructions
- no task requirement embedded in the manifest
- no durable artifact claim

### Persisted Artifact Manifest

Persisted manifests must satisfy all of the following:

- `artifact_mode = persisted`
- `preview_mode = none`
- reproducible from governed inputs
- suitable for task-driven execution
- expected to produce auditable artifact metadata outside the manifest

## Example: Formal Summary Manifest

```json
{
  "report_id": "rpt_balance_summary_2026-03-31_formal_asset_cny",
  "report_family": "balance_analysis_summary",
  "report_title": "Balance Analysis Summary",
  "report_version": "rm_v1_draft",
  "basis": "formal",
  "scenario_flag": false,
  "as_of_date": "2026-03-31",
  "artifact_mode": "preview",
  "preview_mode": "interactive",
  "filters": {
    "report_date": "2026-03-31",
    "position_scope": "asset",
    "currency_basis": "CNY"
  },
  "sections": [
    {
      "section_id": "overview_cards",
      "section_kind": "kpi_grid",
      "title": "Overview",
      "payload_ref": "payload.overview.cards",
      "evidence_refs": ["ev_balance_overview_1"],
      "provenance_refs": ["prov_formal_balance_fact"],
      "renderer_hints": {
        "columns": 4
      }
    }
  ],
  "result_meta": {
    "basis": "formal",
    "formal_use_allowed": true,
    "scenario_flag": false,
    "source_version": "sv_xxx",
    "rule_version": "rv_xxx",
    "cache_version": "cv_formal_xxx",
    "generated_at": "2026-04-11T21:30:00+08:00",
    "trace_id": "tr_xxx"
  },
  "provenance_refs": [
    {
      "provenance_id": "prov_formal_balance_fact",
      "kind": "fact_table",
      "ref": "fact_formal_zqtz_balance_daily",
      "basis": "formal",
      "source_version": "sv_xxx",
      "rule_version": "rv_xxx",
      "trace_id": "tr_xxx"
    }
  ],
  "evidence_refs": [
    {
      "evidence_id": "ev_balance_overview_1",
      "kind": "result_block",
      "ref": "overview.total_market_value",
      "label": "Total market value card"
    }
  ],
  "renderer_inputs": {
    "targets": ["html"],
    "layout_profile": "summary_v1"
  },
  "quality_flag": "ok"
}
```

## Review Checklist

Before this draft can be approved as the basis for renderer authorization, reviewers should confirm:

- it references `CACHE_SPEC.md` instead of redefining outward semantics
- it does not permit renderer-side finance logic
- it keeps `Formal`, `Scenario`, and `Analytical` basis semantics separated
- it requires provenance and evidence linkage
- it supports both preview and persisted artifact modes without mixing them

## Non-Goals

- no renderer implementation
- no Quarto authorization by this document alone
- no runtime task or API changes
- no Agent reactivation
