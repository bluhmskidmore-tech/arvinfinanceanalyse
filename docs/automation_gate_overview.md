# Automation Gate Overview

This file is an index only; it is non-authoritative. It does not override `AGENTS.md`,
`docs/DOCUMENT_AUTHORITY.md`, `.github/workflows/ci.yml`, `scripts/`, or package
scripts. When this index conflicts with an executable gate source, the executable
source wins.

These gates prove that specific automated checks exist and run. They do not prove
all business metric definitions, page-level requirements, data lineage decisions,
or human review judgments are correct.

| Gate | Source of truth / command | Protects against | Does not prove | Defined in |
| --- | --- | --- | --- | --- |
| Backend release suite | `python scripts/backend_release_suite.py` | The governed backend release path drifting away from its fixed matrix, including governance doc and golden sample readiness checks. | That every backend behavior or every business metric caliber is correct. | `scripts/backend_release_suite.py` |
| CI backend job | `python scripts/backend_release_suite.py --governance-audit-output governance-lineage-audit.json`; uploads `governance-lineage-audit.json` with `actions/upload-artifact@v4`. | The CI execution wrapper still runs the backend release suite and preserves governance lineage audit evidence as an artifact. | Any independent business assertion beyond the backend release suite and uploaded audit evidence. | `.github/workflows/ci.yml` |
| Governance doc contract | `tests/test_governance_doc_contract.py` in the backend release suite. | Governance/page-contract documentation drifting away from required contract language and golden-sample bindings. | That each referenced page or metric is fully correct at runtime. | `scripts/backend_release_suite.py`, `tests/test_governance_doc_contract.py` |
| Golden sample capture-ready contract | `tests/test_golden_samples_capture_ready.py` in the backend release suite. | Frozen golden sample packages losing required request, response, assertion, approval, metadata, unit, date, or result fields. | Coverage of all production data combinations or every possible metric edge case. | `scripts/backend_release_suite.py`, `tests/test_golden_samples_capture_ready.py`, `tests/golden_samples/` |
| Frontend typecheck | `npx tsc --noEmit` in CI; package script `typecheck` is `tsc --noEmit`. | TypeScript contract drift, missing fields, incompatible imports, and obvious typed API usage errors. | Correct business meaning, visual correctness, or realistic browser behavior. | `.github/workflows/ci.yml`, `frontend/package.json` |
| Frontend Vitest | `npx vitest run` in CI; package script `test` is `vitest run`. | Component, page, adapter, model, selector, and interaction regressions covered by frontend tests. | Full browser end-to-end behavior or all page-level business requirements. | `.github/workflows/ci.yml`, `frontend/package.json`, `frontend/src/test/` |
| Frontend debt audit | `npm run debt:audit`; package script runs `node ../scripts/audit_frontend_debt.mjs`. | Growth in tracked frontend debt baselines such as `api/client.ts`, mock occurrences, and repeated inline style props. | That the frontend is well designed, fully refactored, or free of existing debt. | `.github/workflows/ci.yml`, `frontend/package.json`, `scripts/audit_frontend_debt.mjs` |
| Surface naming check | `node scripts/check_surface_naming.mjs` in CI. | Drift in guarded route, page, and surface vocabulary rules. | That all names are business-optimal or that unlisted surfaces are covered. | `.github/workflows/ci.yml`, `scripts/check_surface_naming.mjs` |
| ESLint | `npx eslint .` in CI; package script `lint` is `eslint .`. | Static code-quality rule drift, syntax-level lint violations, and configured frontend lint failures. | Business correctness, metric caliber, or runtime data correctness. | `.github/workflows/ci.yml`, `frontend/package.json` |

Use this index to decide which machine evidence should accompany a review. Use
metric contracts, lineage evidence, page-level acceptance criteria, and human business
review to decide whether the result is actually correct.
