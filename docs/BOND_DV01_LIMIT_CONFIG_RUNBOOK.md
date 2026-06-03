# Bond DV01 Limit Config Runbook

## Purpose

This runbook closes the handoff from the DV01 Risk tab's formal limit readiness state to a real business-owned limit file.

The system does not invent AC, OCI, TPL, or all DV01 limits. Risk, investment committee, or another approved business owner must provide the formal values.

## Template

Use `docs/templates/bond_dv01_limit_config_template.csv`.

Required accounting classes are `AC / OCI / TPL / all`. The `all` row is a portfolio-wide configuration row; it cannot replace the direct `AC / OCI / TPL` rows for acceptance.

Required fields:

- `accounting_class`: one of `AC`, `OCI`, `TPL`, `all`
- `limit_dv01`: approved hard DV01 limit, greater than 0
- `warning_dv01`: warning DV01 threshold, greater than 0
- `hedge_target_dv01`: target DV01 after hedge action, greater than 0
- `limit_source`: approval source, such as risk committee minutes
- `limit_source_version`: source evidence version
- `limit_rule_version`: rule or policy version
- `limit_effective_date`: ISO date, for example `2026-03-01`

Threshold order must satisfy `hedge_target_dv01 <= warning_dv01 <= limit_dv01`.

Do not put placeholder numeric limits in the template. Fill only real approved values.

To export the current holding DV01 reference baseline for business review:

```powershell
python -m backend.app.tasks.bond_dv01_limit_config_import --reference-baseline --report-date 2026-03-31
```

To write the same reference baseline as a fillable CSV:

```powershell
python -m backend.app.tasks.bond_dv01_limit_config_import --reference-baseline-csv path\to\bond_dv01_limit_config_review.csv --report-date 2026-03-31
```

To generate the business review package in one step:

```powershell
python -m backend.app.tasks.bond_dv01_limit_config_import --review-package-dir path\to\review-package --report-date 2026-03-31
```

Expected package result:

- `status` is `review_package_written`
- `csv_path` points to a fillable CSV with current reference DV01 and blank formal limit fields
- `todo_path` points to the business handoff checklist
- `missing_business_fields_by_class` lists the blank business fields that still require approval
- no governance rows are written

Expected result:

- `status` is `reference_baseline_built`
- rows show current face value, market value, face-weighted modified duration, and DV01 by `AC`, `OCI`, `TPL`, and `all`
- `business_limit_fields_blank` is `true`
- `limit_dv01`, `warning_dv01`, and `hedge_target_dv01` remain blank; business approval must still provide the formal limits
- `business_review_instruction` and `validation_instruction` are operator guidance columns, not governance fields
- `unmapped_accounting_classes` lists current formal rows outside direct `AC / OCI / TPL` mapping, if any

To generate a fresh blank template from the backend import contract:

```powershell
python -m backend.app.tasks.bond_dv01_limit_config_import --write-template path\to\bond_dv01_limit_config.csv
```

Expected result:

- `status` is `template_written`
- the generated CSV contains only `AC`, `OCI`, `TPL`, and `all`
- numeric limit fields are blank until business fills approved values

## Dry Run

Validate the file without writing to governance:

```powershell
python -m backend.app.tasks.bond_dv01_limit_config_import --config-path path\to\bond_dv01_limit_config.csv --report-date 2026-03-31 --dry-run
```

Expected result:

- `status` is `validated`
- `import_readiness_status` is `ready_for_import`
- `next_action` tells the operator to rerun without `--dry-run`
- if `limit_utilization_preview` has breached statuses, `next_action` first tells the operator to review those rows
- `ignored_input_fields` may list reference-only CSV columns; those columns are not written to governance
- if approved business fields are blank, `missing_business_fields_by_class` lists the missing fields for each `AC / OCI / TPL / all` row
- `limit_utilization_preview` shows `abs(current_total_dv01) / limit_dv01` by accounting class for the selected report date
- `limit_utilization_preview.summary` counts rows by threshold status and shows the highest utilization class
- `limit_utilization_preview.summary.highest_severity_status` gives the worst current status across accounting classes
- `limit_utilization_preview.rows[].threshold_status` labels the pre-import state as `within_target`, `hedge_target_exceeded`, `warning_breached`, or `hard_limit_breached`
- `validation_errors` is empty
- `configured_accounting_classes` is `["AC", "OCI", "TPL", "all"]`
- `records_written` is `0`

## Import

After business approval and dry-run validation, import the file:

```powershell
python -m backend.app.tasks.bond_dv01_limit_config_import --config-path path\to\bond_dv01_limit_config.csv --report-date 2026-03-31
```

Expected result:

- `status` is `imported`
- `records_written` is `4`
- `limit_config_status.result.acceptance_status` is `ready`

## Acceptance Check

The page and API both read the same governance stream, `bond_dv01_limit_config`.

Check the backend status endpoint:

```text
/api/bond-analytics/dv01-limit-config-status?report_date=2026-03-31
```

Or check the same status from the import CLI:

```powershell
python -m backend.app.tasks.bond_dv01_limit_config_import --check-status --report-date 2026-03-31
```

The DV01 Risk tab is accepted only when:

- `acceptance_status` is `ready`
- `configured_accounting_classes` contains `AC`, `OCI`, `TPL`, and `all`
- `missing_accounting_classes` is empty
- `invalid_accounting_classes` is empty

If any class is missing or invalid, the action plan stays on the page-threshold fallback path for the affected scope.
