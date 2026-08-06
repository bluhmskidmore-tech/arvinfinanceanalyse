# Supply-Chain Security Scanning

This repository keeps supply-chain/security scanning repo-local and CI-friendly without modifying application code.

## Included assets

- `.gitleaks.toml`
  - Extends Gitleaks defaults.
  - Ignores generated snapshots, local cache directories, and transient verification output only.
  - Does not exclude `backend/app/`, `frontend/src/`, or other live source trees.
- `scripts/supply_chain_security_scan.py`
  - Dry-run plan mode for CI wiring: `python scripts/supply_chain_security_scan.py --dry-run`
  - Runner mode for local or CI execution: `python scripts/supply_chain_security_scan.py --tool all`
  - Writes JSON reports under `test_output/security-scans/` by default.
- `scripts/osv_reconciliation_gate.py`
  - Runs the SHA-256-pinned OSV-Scanner binary in `scan` mode and writes a
    machine-readable completion/coverage receipt.
  - Reads the unmodified raw OSV JSON report and a tracked reconciliation ledger.
  - Writes a separate adjudication with `raw`, `reconciled`, and `unresolved`
    findings.
  - Returns non-zero unless every raw finding is either absent or matched by one
    valid, active, exact-tuple reconciliation record.
- `docs/audits/osv-reconciliation-records.json`
  - Stores review records keyed by lockfile, ecosystem, package, version, and
    advisory ID.
  - Binds each record to the lockfile and boundary-test content hashes.
  - Requires different, non-placeholder owner and approver identities, approval
    time, expiry, and source URLs in the trusted maintainer/advisory repositories
    before the record can pass the gate.

## Expected tool installation

This repo does not vendor scanner binaries. Install them in the local shell or CI runner:

- Gitleaks: `gitleaks`
- OSV-Scanner v2: `osv-scanner`

## Local commands

```powershell
python scripts/supply_chain_security_scan.py --dry-run
python scripts/supply_chain_security_scan.py --tool gitleaks
python scripts/supply_chain_security_scan.py --tool osv
python scripts/supply_chain_security_scan.py --tool all --report-dir test_output/security-scans
```

The admission-gate scan uses the same pinned Linux artifact as CI:

```bash
python scripts/osv_reconciliation_gate.py scan \
  --scanner /path/to/the/pinned/v2.3.0/osv-scanner_linux_amd64 \
  --raw-report test_output/security-scans/osv-report.json \
  --scan-receipt test_output/security-scans/osv-scan-receipt.json
python scripts/osv_reconciliation_gate.py evaluate \
  --raw-report test_output/security-scans/osv-report.json \
  --scan-receipt test_output/security-scans/osv-scan-receipt.json \
  --records docs/audits/osv-reconciliation-records.json \
  --output test_output/security-scans/osv-adjudication.json
```

The `scan` command accepts only the pinned OSV-Scanner v2.3.0 Linux artifact
SHA-256 used in CI. It records the scanner digest and documented result exit code,
the exact two lockfile paths and current hashes, the exact scan arguments, and the
raw-report hash. Exit code 0 means a completed clean scan and exit code 1 means a
completed scan with findings; every other code is an operational failure. The
`evaluate` command never infers completion from GitHub step outcome. Its output
may not overwrite the raw report, scan receipt, or reconciliation ledger.

## Scan coverage

- Gitleaks scans the repo with the repo-local `.gitleaks.toml`.
- OSV-Scanner targets the authoritative lockfiles currently present in-repo:
  - `backend/uv.lock`
  - `frontend/package-lock.json`

`backend/pyproject.toml` is documented context, not the resolved dependency source of truth. The wrapper therefore scans `backend/uv.lock` instead.

## CI

`.github/workflows/ci.yml` runs two separate security surfaces:

- `Secret Scan` installs Gitleaks, runs
  `python scripts/supply_chain_security_scan.py --tool gitleaks`, and uploads
  `test_output/security-scans/gitleaks-report.json`.
- `OSV Dependency Scan` downloads the official OSV-Scanner v2.3.0 Linux binary,
  verifies its published SHA-256, and scans exactly `backend/uv.lock` and
  `frontend/package-lock.json`. The runner preserves `osv-report.json` and writes
  `osv-scan-receipt.json`, even when findings produce scanner result code 1. The
  exact-tuple gate then writes `osv-adjudication.json`; raw report, completion
  receipt, adjudication, and reporter-produced SARIF are uploaded. The job
  depends on the frontend test job, so a failing React Router security-boundary
  test cannot be bypassed by a reconciliation record.

The repo-local wrapper still supports `--tool osv` for local environments where
`osv-scanner` is installed.

## Exact-tuple reconciliation rules

The ledger is not an ID-wide ignore list. A record is usable only when all of
these values match the raw finding exactly:

- repo-relative lockfile
- ecosystem
- package name
- package version
- advisory ID

The gate also verifies the current lockfile and boundary-test SHA-256 digests.
It separately verifies a completed receipt for the exact two expected lockfiles,
including scanner binary, command, exit code, lockfile hashes, and raw-report
hash. Wildcards and patterns are rejected. A package version change, either
evidence hash changing, expiry, missing or self-approved identities, untrusted
source URL, duplicate record, partial/failed scan, or any additional
vulnerability leaves the gate closed. An active record with no matching raw
finding also fails and must be removed; stale active exceptions cannot linger.
OSV's native `IgnoredVulns` mechanism is intentionally not used because it is
ID-wide and would suppress the finding from the configured scan rather than
preserve the raw evidence.

## Current React Router record

The single React Router record is deliberately
`status=pending_owner_approval`. No repository `CODEOWNERS` file or existing
governance artifact identifies a concrete person authorized to own and approve
this dependency reconciliation. Existing governance evidence names only the
`security_owner` role. Therefore `owner`, `approver`, and `approved_at` remain
null and the release gate remains closed until an authorized security owner
supplies those identities and changes the status to `active`.

The record expires on `2026-08-21T23:59:59+08:00`. Remove it when the global
GitHub Advisory Database/OSV range is corrected; do not renew it merely to make
the scan green.
