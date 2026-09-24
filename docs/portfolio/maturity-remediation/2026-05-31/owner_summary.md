# Portfolio Home Maturity Remediation Summary

This summary is not an approval.

- Page: `portfolio` (`PAGE-PORTFOLIO-HOME-001`)
- Report date: `2026-05-31`
- Export status: `blocked`
- Required TYW fields on every row: `owner_decision`, `owner_comment`
- Conditionally required TYW field: `proposed_maturity_date` only when `owner_decision=remediate_source`
- Allowed decisions: `remediate_source`, `approve_scoped_exclusion`, `reject`
- Strict gate: `python scripts/portfolio_home_maturity_remediation_queue.py --report-date 2026-05-31 --require-empty`
- Bond no-maturity rows: `114`
- Bond no-maturity market value: `37622164239.83000008`
- Bond remediation rows (compatibility): `0`
- TYW liability missing maturity rows: `1455`
- TYW liability missing maturity principal: `43822652393.01000002`
- Decision queue: `tyw_liability_missing_maturity.csv` only
- Compatibility file: `bond_missing_maturity.csv` is header-only; no bond owner decision is required.
- Bond ledger boundary: null `maturity_date` means no maturity date and requires no owner-supplied date.
- Generated owner fields must be blank: `true`
- Boundary: generated CSV fields are blank and do not fill or infer maturity dates.

## Owner Instructions

- Fill `owner_decision` on every TYW liability row.
- Fill `owner_comment` on every TYW liability row for every decision value.
- Fill `proposed_maturity_date` only when `owner_decision` is `remediate_source`; leave it blank for `approve_scoped_exclusion` and `reject`.
- Use `remediate_source` only when the TYW source maturity date will be fixed and rematerialized.
- Use `approve_scoped_exclusion` only with a signed TYW exclusion rationale in `owner_comment`.
- Do not use frontend-inferred dates or synthetic TYW maturity dates as remediation evidence.
- After owner decisions are captured, do not rerun the normal export; use `--check-current` before owner-decision intake.

## Post-Decision Verification

- `python scripts/portfolio_home_maturity_remediation_export.py --report-date 2026-05-31 --output-dir docs/portfolio/maturity-remediation --check-current`
- `python scripts/portfolio_home_maturity_remediation_queue.py --report-date 2026-05-31 --require-empty`
- `python scripts/portfolio_home_dependency_consistency_check.py --report-date 2026-05-31 --limit 3 --require-consistent`
- `python scripts/portfolio_home_owner_decision_intake_check.py --report-date 2026-05-31 --limit 3 --require-ready`
- `python scripts/portfolio_home_closure_scorecard.py --report-date 2026-05-31 --limit 3 --require-full-score`

A filled TYW CSV is still not approval until source remediation or signed exclusion evidence is captured and the business-owner approval template is completed.
