# Project Retrospective

*A living document updated after each milestone. Lessons feed forward into future planning.*

## Milestone: v1.0 - Audit Remediation

**Completed and verified:** 2026-05-11

**Final audit evidence snapshot:** 2026-05-16 (`25c815252`)

**Archived:** 2026-07-15
**Phases:** 1 | **Plans:** 1 | **Tasks:** 6 | **Sessions:** not recorded

### What Was Built

- Explicit dev/test auth trust and restored backend release-gate behavior.
- Formal contracts for three live pages and a narrow display-only DV01 exception.
- Governed Dashboard fallback semantics plus focused macro, agent, GitNexus, and MCP boundary controls.
- CI and release-suite coverage for the release-critical build and contract checks.

### What Worked

- Requirements were tied across REQUIREMENTS, VERIFICATION, SUMMARY, and the final audit.
- Focused boundary tests provided reviewable evidence without a platform rewrite.
- The remediation scope and accepted debt were stated explicitly.
- Platform-aware MCP assertions kept Windows-specific launch details out of portable CI checks.

### What Was Inefficient

- PROJECT.md and STATE.md were missing until milestone archival.
- The final audit snapshot was recorded after the remediation completion date, and archival happened later still.
- Historical remediation commits contained unrelated work, so trustworthy milestone LOC and file-count statistics could not be derived.

### Patterns Established

- Gate development identity trust behind an explicit environment switch.
- Give live business pages formal page contracts instead of temporary exceptions.
- Scope finance-boundary exceptions by file, snippet, and display-only intent.
- Include boundary contracts in release gates and maintain GSD evidence prospectively.

### Key Lessons

1. Archive and tag verified snapshots when verification finishes, before later work obscures the boundary.
2. Create PROJECT.md and STATE.md at milestone start, not at archival.
3. Keep milestone commits scope-pure when file, LOC, and release claims will matter later.

### Cost Observations

- Model mix: not recorded
- Sessions: not recorded
- Coverage percentage: not recorded; targeted and release suites passed in the archived audit

---

## Cross-Milestone Trends

One milestone is not enough to establish cross-milestone trends.
