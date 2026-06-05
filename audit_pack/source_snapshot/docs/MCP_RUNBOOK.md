# MOSS MCP Runbook

This repository has a project-level MCP configuration in `.mcp.json`.

## Servers

| Server | Purpose | Command |
| --- | --- | --- |
| `gitnexus` | Repository graph, context, and processes. | `node .tmp-gitnexus-v13/node_modules/gitnexus/dist/cli/index.js mcp` |
| `moss-metric-contracts` | Read-only access to page contracts, metric dictionary, calc rules, product-category truth docs, and golden-sample catalog. | `python scripts/mcp/moss_project_mcp.py metric-contracts` |
| `moss-lineage-evidence` | Read-only access to governance JSONL streams, latest evidence records, and lineage search. | `python scripts/mcp/moss_project_mcp.py lineage-evidence` |
| `moss-data-catalog` | Read-only DuckDB table inventory, schema registry, table description, and available date lookup. | `python scripts/mcp/moss_project_mcp.py data-catalog` |
| `playwright` | Browser/page QA through Playwright MCP. | `npx -y @playwright/mcp@latest` |

## Boundaries

- The local MOSS servers are read-only.
- `moss-data-catalog` only uses `information_schema` and fixed date-list queries; it does not accept arbitrary SQL.
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

## Page Trace Bundle

Use `moss-metric-contracts.get_page_trace_bundle` before changing a seeded business metric page. It returns a read-only evidence bundle with the page route, governed API, contract documents, truth chain, backend/frontend touchpoints, existing tests, golden samples, verification focus, and page-specific guardrails.

First seeded page:

- `product-category-pnl`

Boundary:

- The bundle is an evidence index only. It does not calculate metrics, inspect DuckDB rows, mutate data, or replace the contract documents it points to.
- For `product-category-pnl`, row meaning must stay tied to the paired ledger reconciliation + daily average source chain. Do not infer page rows from ZQTZ holdings-side logic or research buckets.

## Codex Page Helpers

Use the local helper scripts after the trace bundle has identified the page surface.

Dry-run the verification plan:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/codex-verify-page.ps1 -PageSlug product-category-pnl
```

Run the page-specific verification plan:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/codex-verify-page.ps1 -PageSlug product-category-pnl -Run
```

Emit the page smoke checklist:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/codex-page-smoke.ps1 -PageSlug product-category-pnl
```

The smoke helper intentionally prints the route, governed API, expected visible states, and Playwright MCP checklist. It does not replace browser verification or add a new browser automation dependency.

## Local Verification

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
