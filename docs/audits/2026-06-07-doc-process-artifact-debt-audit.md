# Document And Process Artifact Debt Audit

Date: 2026-06-07

Status label: supporting

This audit is a cleanup inventory only. It does not authorize deletion,
archival movement, or business-surface changes.

## Scope

Included:

- `docs/plans/**`
- `docs/audits/**`
- `docs/portfolio/**`
- `.planning/reports/**`
- references from docs, tests, scripts, backend, and frontend

Excluded:

- business metric code
- frontend pages
- database schema
- auth, queue, cache, and global infrastructure
- staging, committing, deleting, or moving files

## Inventory

Working tree status before this pass was broad and mixed:

| Area | Status entries |
| --- | ---: |
| tests | 227 |
| frontend | 178 |
| docs | 89 |
| backend | 89 |
| scripts | 59 |
| local process | 1 |
| repo config | 1 |

Document/process artifact counts:

| Path | Tracked | Untracked | Notes |
| --- | ---: | ---: | --- |
| `docs/plans/**` | 70 | 34 | Supporting planning history; 104 files total. |
| `docs/audits/**` | 7 | 15 | Mixed governed evidence and historical audit packets. |
| `docs/portfolio/**` | 0 | 12 | Referenced owner/governance packets; not safe to treat as junk. |
| `.planning/reports/**` | 0 | 5 | Local process output; now ignored by `.gitignore`. |
| `product-manager/moss-finance-audit-cluster/**` | 0 | 77 | Wrong-path local process output; hold visible, do not stage. |

## Classification

### KEEP

Keep files that are referenced by tests, scripts, document authority, MCP
metadata, or owner/governance packets.

Examples:

- `docs/plans/2026-04-12-balance-analysis-advanced-attribution-boundary.md`
- `docs/plans/2026-04-12-balance-analysis-cursor-prompt-pack.md`
- `docs/plans/2026-04-12-balance-analysis-gap-closure.md`
- `docs/plans/market-workbench-cursor-prompts.md`
- `docs/plans/2026-06-07-agent-audit-remediation-plan.md`
- `docs/plans/2026-06-07-database-formal-closure-next-steps.md`
- `docs/plans/2026-06-07-hermes-five-agent-team-plan.md`
- `docs/plans/2026-06-07-pnl-adb-true-zero-closure.md`
- `docs/plans/2026-06-05-top-investment-bank-frontend-certification-roadmap.md`
- `docs/plans/2026-06-06-deep-audit-goal-queue.md`
- `docs/plans/2026-06-06-top-investment-bank-standard-continuation-owner-signable-ui-hardening-plan.md`
- `docs/plans/2026-06-06-top-investment-bank-standard-next-optimization-route-certification-plan.md`
- `docs/plans/2026-06-06-top-investment-bank-standard-owner-signable-closure-plan.md`
- `docs/audits/2026-06-06-bond-analysis-gate-i-lane.md`
- `docs/audits/2026-06-06-stock-analysis-gate-i-lane.md`
- `docs/audits/2026-06-05-portfolio-readiness-gate-audit.md`
- `docs/portfolio/portfolio-home-full-closure-sign-off-packet.md`
- `docs/portfolio/portfolio-home-business-owner-approval-template.md`
- `docs/portfolio/portfolio-home-evidence-snapshot.json`

Evidence:

- `docs/plans/README.md` defines `docs/plans/**` as supporting,
  non-authorizing planning history.
- `docs/README.md` lists `docs/plans/**` and `docs/plans/artifacts/**` as
  supporting material.
- `docs/DOCUMENT_AUTHORITY.md` references
  `docs/plans/market-workbench-cursor-prompts.md` as role-specific supporting
  reference material.
- `tests/test_balance_analysis_docs_contract.py` reads three historical
  balance-analysis plan files directly.
- Portfolio-home scripts and tests reference `docs/portfolio/**` artifacts
  directly, so those untracked files are not disposable noise.
- The four `docs/plans/2026-06-07-*` files are active implementation plans for
  current dirty worktree lanes: agent audit remediation, database formal
  closure, Hermes team launcher, and PnL ADB true-zero handling.
- `tests/test_product_category_pnl_business_owner_approval_status.py` directly
  reads several 2026-06-05/06 plan files as current-status drift guards. Those
  paths must stay in the active `docs/plans/` surface while the tests require
  them.

### ARCHIVE CANDIDATE

These were likely historical plan packets or execution notes. They were not
deleted; the next archive lane moved eligible files after a second reference
check.

Examples now archived under
`docs/plans/archive/2026-06-07-debt-cleanup/`:

- `2026-06-04-home-startup-ag-grid-guard.md`
- `2026-06-05-pnl-attribution-batch-approval-gate.md`
- `2026-06-05-pnl-attribution-evidence-packet-sync.md`
- `2026-06-05-pnl-attribution-governance-gate-stabilization.md`
- `2026-06-06-top-investment-bank-standard-ledger-pnl-next-closure-plan.md`

### LOCAL-ONLY

`.planning/reports/**` is local process output. The directory contained:

- `.planning/reports/20260605-pnl-attribution-session-report.md`
- `.planning/reports/dirty-files-all.txt`
- `.planning/reports/dirty-modified-files.txt`
- `.planning/reports/dirty-untracked-files.txt`
- `.planning/reports/dirty-worktree-status.txt`

Low-risk action taken:

- Added `.planning/reports/` to `.gitignore`.

`product-manager/moss-finance-audit-cluster/**` is also local process output,
but it is a wrong-root generated directory rather than a reusable repository
artifact. It is intentionally not ignored in this pass so the misplaced output
remains visible as `LOCAL-ONLY/HOLD`. Do not stage it; remove or relocate it
only in a later explicit cleanup pass.

### REVIEW

The following untracked artifacts were not classified as junk because they are
close to governed evidence or owner handoff material:

- all untracked `docs/audits/**` except obvious isolated execution notes
- all untracked `docs/portfolio/**`
- recent `docs/plans/**` files that are linked by other plans or evidence docs

Specific untracked files with no external reference found in this pass, but
still needing human or lane-specific review before archival:

- `docs/audits/2026-06-06-wrapper-hardening-liability-adb-execution-report.md`
- `docs/portfolio/portfolio-home-option-b-execution-note.md`

## Recommended Next Batches

1. Keep `.planning/reports/**` ignored and regenerate local reports there when
   needed.
2. Continue from the archive lane below for any remaining unreviewed
   `docs/plans/**` packets. Move, do not delete.
3. Treat `docs/audits/**` and `docs/portfolio/**` as governed evidence until
   their owning tests/scripts say otherwise.
4. Do not raise `.gitignore` scope to all `.planning/**`; only reports were
   proven local-only in this pass.
5. Keep `product-manager/moss-finance-audit-cluster/**` visible as a wrong-path
   HOLD item until an explicit delete/relocate pass is authorized.

## Archive Lane Completed

The 2026-06-07 archive lane moved 30 untracked historical plan packets to
`docs/plans/archive/2026-06-07-debt-cleanup/`.
After the owner-approval fixture correction below, the net new archive payload
for this pass is 25 untracked historical plan packets plus the archive README.

Rules applied:

- eligible files were untracked `docs/plans/2026-06-04*`, `2026-06-05*`, and
  `2026-06-06*` packets;
- no file with an external reference from tests, scripts, authority docs,
  backend, or frontend code was moved;
- cross-links inside the moved batch were treated as historical internal links;
- 2026-06-07 plan files stayed in the active `docs/plans/` surface;
- no files were deleted.

Correction: owner-approval verification showed that five 2026-06-05/06 plan
files are direct test fixtures for current product-category status checks. They
were restored from the archive to their original active paths.

## Active 2026-06-07 Plans Kept

The following files were reviewed after the archive lane and intentionally kept
in the active `docs/plans/` surface:

- `docs/plans/2026-06-07-agent-audit-remediation-plan.md`
- `docs/plans/2026-06-07-database-formal-closure-next-steps.md`
- `docs/plans/2026-06-07-hermes-five-agent-team-plan.md`
- `docs/plans/2026-06-07-pnl-adb-true-zero-closure.md`

Reason: each file maps to a live uncommitted work lane rather than a stale
historical packet. Treat them as current planning context until their owning
code/test/doc batches are closed or superseded.
