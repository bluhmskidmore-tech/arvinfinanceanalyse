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

Do not put placeholder numeric limits in the template. Fill only real approved values.

To export the current holding DV01 reference baseline for business review:

```powershell
python -m backend.app.tasks.bond_dv01_limit_config_import --reference-baseline --report-date 2026-03-31
```

To write the same reference baseline as a fillable CSV:

```powershell
python -m backend.app.tasks.bond_dv01_limit_config_import --reference-baseline-csv path\to\bond_dv01_limit_config_review.csv --report-date 2026-03-31
```

Expected result:

- `status` is `reference_baseline_built`
- rows show current face value, market value, face-weighted modified duration, and DV01 by `AC`, `OCI`, `TPL`, and `all`
- `business_limit_fields_blank` is `true`
- `limit_dv01`, `warning_dv01`, and `hedge_target_dv01` remain blank; business approval must still provide the formal limits
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
