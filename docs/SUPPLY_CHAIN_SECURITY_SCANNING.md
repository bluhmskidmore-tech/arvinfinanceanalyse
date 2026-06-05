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
- `OSV Dependency Scan` uses the official OSV reusable workflow against
  `backend/uv.lock` and `frontend/package-lock.json`.

The repo-local wrapper still supports `--tool osv` for local environments where
`osv-scanner` is installed.
