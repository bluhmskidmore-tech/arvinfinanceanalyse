# 2026-06-10 Direct App MCP/GitNexus Tool Surface Runbook

## Purpose

Use this runbook to close the direct Codex App MCP/GitNexus evidence gap after a fresh session exposes the configured tools. It is a tool-surface validation procedure only. It does not approve metrics, pages, governance records, route certification, formal use, or business-owner signoff.

## Current Recorded State

- `tool_search` query: `moss metric contracts lineage evidence data catalog gitnexus MCP tools`
- Last recorded result at `2026-06-10T21:25:00+08:00`: 0 relevant direct MOSS/GitNexus tools found in the current Codex App tool surface.
- Focused rechecks at `2026-06-10T21:25:00+08:00`:
  - `moss metric contracts lineage evidence data catalog MCP tools` returned 0 tools.
  - `moss-data-catalog moss-lineage-evidence moss-metric-contracts` returned 0 tools.
  - `gitnexus MCP impact call path symbol repository evidence` returned 3 Codex App management tools (`codex_app.handoff_thread`, `codex_app.fork_thread`, and `codex_app.automation_update`), but 0 relevant direct GitNexus or MOSS evidence tools.
- Local registration files declare the expected servers:
  - `.codex/config.toml`
  - `.mcp.json`
- `docs/MCP_RUNBOOK.md` documents that existing Codex sessions do not hot-reload MCP registrations and that a fresh session retry is required before treating the gap as a repository configuration failure.

## Do Not Use As Closure

Do not treat any of the following as direct App-surface closure:

- Local stdio MCP handshake success.
- Local MCP contract tests.
- Local governance JSONL search.
- Dry-run governance blueprints.
- Static page readiness.
- Route-mocked or mock browser smoke.

Those are useful fallback evidence, but they do not replace direct Codex App MCP/GitNexus tool evidence.

## Closure Procedure

1. Start a fresh Codex App session from `F:\MOSS-V3`, or otherwise reload MCP registrations.
2. If available in that session, verify the MCP registry from the repository root:

```powershell
codex mcp list
```

3. Repeat direct App tool discovery with:

```text
moss metric contracts lineage evidence data catalog gitnexus MCP tools
```

4. Confirm direct tools are exposed for all expected lanes:
   - `moss-metric-contracts`
   - `moss-lineage-evidence`
   - `moss-data-catalog`
   - `moss-data-quality`
   - `gitnexus`
5. Collect direct App-surface evidence for the audited pages and workflows:
   - page contracts and trace bundles
   - lineage and governance evidence
   - catalog/date coverage
   - data-quality summaries where relevant
   - GitNexus call-path or impact evidence for shared code paths
6. Compare direct App evidence against the local stdio evidence already recorded in the audit package.
7. Update `2026-06-10-direct-app-mcp-gitnexus-tool-surface-snapshot.json`, `2026-06-10-system-audit-manifest.json`, and `2026-06-10-system-wide-skills-audit.md` with the result.
8. Rerun:

```powershell
pytest tests/test_system_audit_manifest_contract.py -q
```

## Acceptance Criteria

- Direct App tool discovery returns the expected MOSS MCP and GitNexus surfaces.
- Direct App evidence is captured or explicitly compared to local stdio evidence.
- Any discrepancy is recorded as an open finding.
- The audit package still states that tool evidence alone does not approve pages, metrics, governance records, or owner signoff.

## If Tools Are Still Missing

Keep the blocker open as a client/session exposure limitation if local config still declares the expected servers. Record the new timestamp, discovery query, and focused recheck results in the snapshot and manifest. Do not promote local stdio evidence or unrelated Codex App tools, if any appear, to direct App MCP/GitNexus evidence.
