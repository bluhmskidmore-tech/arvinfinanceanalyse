# 2026-06-10 Local Secret Hygiene Runbook

## Purpose

This runbook handles the remaining local secret hygiene audit lane without exposing credential values. The current audit evidence identifies secret names in an ignored, untracked local `config/.env`; this runbook defines how to close or owner-accept that finding outside the repository commit path.

Machine-readable snapshot: `docs/audits/2026-06-10-local-secret-hygiene-snapshot.json`.

## Current Evidence

- Detected names only: `MOSS_TUSHARE_TOKEN`, `STITCH_API_KEY`
- Values captured in audit artifacts: no
- Local file existence: `config/.env` exists in this workspace
- Ignore rule: `.gitignore:4:config/.env`
- Tracked status: `git ls-files -- config/.env` returns no tracked path
- Ignored status: `git status --ignored --short -- config/.env` returns `!! config/.env`
- Scan plan: `python scripts\supply_chain_security_scan.py --dry-run`
- Gitleaks command includes `--redact`

## Non-Closure Boundary

This runbook does not:

- read or copy secret values
- rotate credentials by itself
- approve deployment
- clear the gitleaks finding
- make `config/.env` safe to commit
- replace a clean-runner secret scan

## Owner Actions

1. Confirm whether the local `MOSS_TUSHARE_TOKEN` and `STITCH_API_KEY` values were ever shared outside the trusted local machine.
2. If exposure is possible, rotate the credentials at the provider side.
3. Replace local values through the normal local environment provisioning path.
4. Keep `config/.env` ignored and untracked.
5. Do not paste credential values into issues, docs, commits, screenshots, logs, or chat.
6. Record only the owner decision: rotated, accepted local-only, or removed.

## Verification Procedure

Run these checks after rotation, removal, or owner acceptance:

1. Confirm the file remains ignored:
   `git check-ignore -v config/.env`
2. Confirm the file remains untracked:
   `git ls-files -- config/.env`
3. Confirm the redacted scan plan:
   `python scripts\supply_chain_security_scan.py --dry-run`
4. Run gitleaks with redaction in a clean runner:
   `python scripts\supply_chain_security_scan.py --tool gitleaks --report-dir test_output\security-scans`
5. Run OSV dependency scan:
   `python scripts\supply_chain_security_scan.py --tool osv --report-dir test_output\security-scans`
6. Run the secret hygiene tests:
   `python -m pytest tests/test_supply_chain_security_scanning.py tests/test_secret_hygiene.py -q`

## Acceptance Criteria

- No secret value appears in repository files, audit artifacts, logs, or committed output.
- `config/.env` remains ignored and untracked.
- Clean-runner gitleaks either passes or produces an owner-accepted local-only finding record outside source control.
- OSV remains clean for `backend/uv.lock` and `frontend/package-lock.json`.
- The system audit manifest records the final owner decision without including credential values.

## Do Not

- Do not remove `.gitignore` protections.
- Do not add `config/.env` to Git.
- Do not weaken gitleaks rules to hide real source findings.
- Do not broaden allowlists over `backend/app` or `frontend/src`.
- Do not write secrets into replacement docs, templates, fixtures, tests, or screenshots.
