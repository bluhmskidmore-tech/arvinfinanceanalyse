# MOSS MCP Runbook

This repository has project-level MCP configuration for both Codex and
Cursor-style clients:

- Codex: `.codex/config.toml`
- Cursor-compatible clients: `.mcp.json`

Existing Codex sessions do not hot-reload MCP registrations. Start a new
thread/session after changing MCP config.

## App Surface Fallback

If the current Codex App tool surface does not directly expose the `moss-*`
resources, do not treat that alone as a repo configuration failure.

1. Verify the project registration with `codex mcp list`.
2. Confirm the local config files still declare the servers:
   `.codex/config.toml` and `.mcp.json`.
3. If those checks pass, treat the missing tool surface as a client/session
   exposure limitation and retry in a fresh session.
4. For a cwd-independent local handshake, use the launcher helper directly:

```powershell
python scripts/mcp/moss_mcp_launcher.py metric-contracts
```

The launcher forces the workspace root before loading
`scripts/mcp/moss_project_mcp.py`, which is useful when a client launches MCP
from the wrong working directory.

## Servers

| Server | Purpose | Command |
| --- | --- | --- |
| `gitnexus` | Repository graph, context, and processes. | `node scripts/mcp/gitnexus_mcp_launcher.mjs` |
| `moss-metric-contracts` | Read-only access to page contracts, metric dictionary, calc rules, product-category truth docs, and golden-sample catalog. | `cmd.exe /d /s /c scripts\mcp\moss_contracts.cmd` |
| `moss-lineage-evidence` | Read-only access to governance JSONL streams, latest evidence records, and lineage search. | `cmd.exe /d /s /c scripts\mcp\moss_lineage.cmd` |
| `moss-data-catalog` | Read-only DuckDB table inventory, schema registry, table description, and available date lookup. | `cmd.exe /d /s /c scripts\mcp\moss_catalog.cmd` |
| `moss-data-quality` | Read-only DuckDB quality summaries: row counts, null counts, date coverage, and golden-sample hints. | `cmd.exe /d /s /c scripts\mcp\moss_data_quality.cmd` |
| `playwright` | Browser/page QA through Playwright MCP. | `npx -y @playwright/mcp@latest` |

## Boundaries

- The local MOSS servers are read-only.
- `moss-data-catalog` only uses `information_schema` and fixed date-list queries; it does not accept arbitrary SQL.
- `moss-data-quality` validates table identifiers, rejects unknown tables/views, and only runs bounded read-only profiling queries.
- `moss-lineage-evidence` reads whitelisted governance streams only.
- `moss-metric-contracts` reads whitelisted docs and golden-sample metadata only.
- Browser MCP can interact with a running frontend, but it does not change backend data by itself.
- Do not add write-capable DB or task-runner MCP servers without a separate boundary review.

## Useful Resources

Metric contracts:

- `moss://metric-contracts/summary`
- `moss://metric-contracts/doc/page_contracts`
- `moss://metric-contracts/doc/calc_rules`
- `moss://metric-contracts/doc/metric_dictionary`
- `moss://metric-contracts/doc/product_category_truth`
- `moss://metric-contracts/doc/golden_sample_catalog`

Lineage/evidence:

- `moss://lineage/summary`
- `moss://lineage/streams`
- `moss://lineage/stream/cache_manifest`
- `moss://lineage/stream/source_manifest_latest`
- `moss://lineage/stream/agent_audit`

Data catalog:

- `moss://data-catalog/summary`
- `moss://data-catalog/schema-registry`
- `moss://data-catalog/tables`

Data quality:

- `moss://data-quality/summary`
- `moss://data-quality/targets`

## Useful Tools

Metric contracts:

- `search_contract_docs`
- `get_page_trace_bundle`

Lineage/evidence:

- `read_governance_stream`
- `find_lineage_records`

Data catalog:

- `describe_table`
- `list_available_dates`

Data quality:

- `list_quality_targets`
- `get_quality_summary`

## Page Trace Bundle

Use `moss-metric-contracts.get_page_trace_bundle` before changing a seeded business metric page. It returns a read-only evidence bundle with the page route, governed API, contract documents, truth chain, backend/frontend touchpoints, existing tests, golden samples, verification focus, and page-specific guardrails.

Seeded pages:

- `dashboard-home`
- `product-category-pnl`

Boundary:

- The bundle is an evidence index only. It does not calculate metrics, inspect DuckDB rows, mutate data, or replace the contract documents it points to.
- For `dashboard-home`, `/ui/home/snapshot` is the primary evidence source. Supplemental dashboard, bond, market, and calendar surfaces must stay visibly supplemental and date-gated where the cockpit contract requires it.
- For `product-category-pnl`, row meaning must stay tied to the paired ledger reconciliation + daily average source chain. Do not infer page rows from ZQTZ holdings-side logic or research buckets.

### Coverage Matrix

| Page slug | Route | Primary API | Trace bundle | Golden sample status | Known gaps |
| --- | --- | --- | --- | --- | --- |
| `dashboard-home` | `/`, `/dashboard` | `/ui/home/snapshot` | seeded | Executive sub-surface samples only: `GS-EXEC-OVERVIEW-A`, `GS-EXEC-PNL-ATTR-A`, `GS-EXEC-SUMMARY-A` | Aggregate homepage remains analytical/mixed-source; no full-page formal golden sample. |
| `product-category-pnl` | `/product-category-pnl` | `/ui/pnl/product-category` | seeded | `GS-PROD-CAT-PNL-A` | Standalone `as_of_date` remains an explicit contract gap. |

### Onboarding Checklist

When adding another page trace bundle, include all of:

- `page_slug`, `page_id`, `page_name`, route aliases, `frontend_route`, and `primary_api`.
- Supporting APIs, contract docs, truth chain, backend touchpoints, frontend touchpoints, test touchpoints, and golden samples.
- `verification_focus` entries for unit consistency, precision, null-vs-zero, date semantics, stale/fallback state, and `result_meta` visibility.
- `guardrails` that say what must not be inferred or promoted.
- A dry-run entry in `scripts/codex-verify-page.ps1`, a smoke checklist in `scripts/codex-page-smoke.ps1`, and assertions in `tests/test_project_mcp_servers.py`.

### Fallback Rules

If a client session cannot directly call the `moss-*` MCP tools, use the local docs, tests, DuckDB catalog helpers, and governance JSONL streams as fallback evidence only after checking the local MCP registration. The final work report must say which MCP server was unavailable and what local evidence substituted for it. Do not convert a missing MCP response into a metric definition, source lineage claim, or formal sample approval.

## Codex Page Helpers

Use the local helper scripts after the trace bundle has identified the page surface.

Dry-run the verification plan:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/codex-verify-page.ps1 -PageSlug product-category-pnl
```

For the homepage cockpit:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/codex-verify-page.ps1 -PageSlug dashboard-home
```

Run the page-specific verification plan:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/codex-verify-page.ps1 -PageSlug product-category-pnl -Run
```

Emit the page smoke checklist:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/codex-page-smoke.ps1 -PageSlug product-category-pnl
```

For the homepage cockpit:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/codex-page-smoke.ps1 -PageSlug dashboard-home
```

The smoke helper intentionally prints the route, governed API, expected visible states, and Playwright MCP checklist. It does not replace browser verification or add a new browser automation dependency.

## Local Verification

Confirm Codex can see the configured MCP servers:

```powershell
codex mcp list
```

Run the local MCP contract tests:

```powershell
pytest tests/test_project_mcp_servers.py -q
```

Optional syntax check that does not write `__pycache__`:

```powershell
python -c "import ast, pathlib; ast.parse(pathlib.Path('scripts/mcp/moss_project_mcp.py').read_text(encoding='utf-8')); print('syntax ok')"
```

## GitNexus Index

The `.mcp.json` config enables the GitNexus MCP server through a local GitNexus 1.3.11 install under `.tmp-gitnexus-v13/`.

The `.gitnexus/` index has been generated for this workspace. At the time of indexing it contained:

- 1,429 files
- 10,347 nodes
- 32,344 edges
- 874 communities
- 300 processes

GitNexus records the index metadata in `.gitnexus/meta.json`.

Re-index from the repository root with:

```powershell
node .tmp-gitnexus-v13\node_modules\gitnexus\dist\cli\index.js analyze .
```

Troubleshooting:

- The latest `gitnexus@latest` package currently fails in this Windows workspace with either `EPERM: operation not permitted, symlink ... tree-sitter-proto` or native dependency load/build errors. The local GitNexus 1.3.11 install avoids that path and is the configured MCP/runtime command.
- If re-indexing fails with access denied on `.gitnexus/kuzu.wal`, stop any active GitNexus process and rerun the command from the repository root.
- `.gitnexus/` and `.tmp-gitnexus-v13/` are local generated/runtime directories and are ignored by git.
