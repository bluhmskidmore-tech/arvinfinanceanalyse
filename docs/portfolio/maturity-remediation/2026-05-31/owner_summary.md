# Portfolio Home Maturity Remediation Summary

This summary is not an approval.

- Page: `portfolio` (`PAGE-PORTFOLIO-HOME-001`)
- Report date: `2026-05-31`
- Export status: `blocked`
- Required fields: `proposed_maturity_date`, `owner_decision`, `owner_comment`
- Allowed decisions: `remediate_source`, `approve_scoped_exclusion`, `reject`
- Strict gate: `python scripts/portfolio_home_maturity_remediation_queue.py --require-empty`
- Bond missing maturity rows: `114`
- Bond missing maturity market value: `37622164239.83000008`
- TYW liability missing maturity rows: `1455`
- TYW liability missing maturity principal: `43822652393.01000002`
- Decision queue: `bond_missing_maturity.csv`, `tyw_liability_missing_maturity.csv`
- Generated owner fields must be blank: `true`
- Boundary: generated CSV fields are blank and do not fill or infer maturity dates.

## Owner Instructions

- Fill `owner_decision` on every bond and TYW liability row.
- Fill `owner_comment` on every bond and TYW liability row for every decision value.
- Use `remediate_source` only when the source maturity date will be fixed and rematerialized.
- Use `approve_scoped_exclusion` only with a signed exclusion rationale in `owner_comment`.
- Do not use frontend-inferred dates or synthetic maturity dates as remediation evidence.
- Do not edit `manifest.json`; rerun the export after owner decisions are captured.

## Post-Decision Verification

- `python scripts/portfolio_home_maturity_remediation_queue.py --require-empty`
- `python scripts/portfolio_home_dependency_consistency_check.py --limit 3 --require-consistent`
- `python scripts/portfolio_home_owner_decision_intake_check.py --limit 3 --require-ready`
- `python scripts/portfolio_home_closure_scorecard.py --limit 3 --require-full-score`

A filled CSV is still not approval until source remediation or signed exclusion evidence is captured and the business-owner approval template is completed.
