# Backend API Inventory

## Purpose

This inventory provides one deterministic row per registered FastAPI
`HTTP method + normalized path`. It is the route-surface baseline for later
business-domain, consumer, lineage, authorization, and test-coverage reviews.

It does not certify endpoint business correctness. In particular,
`formal_mainline` is a route ownership and risk boundary; it does not mean that
every endpoint in that group is formal-use approved.

## Sources

The generator joins two repository sources:

- `backend/app/api/__init__.py`: route registry, group, owner, claim boundary,
  risk boundary, and feature-gated registration.
- FastAPI `APIRoute` plus the generated OpenAPI document: method, path,
  operation ID, handler, parameters, request/response contract, tags, and
  dependencies.

The generator creates a small FastAPI inspection app around the aggregate
router. It does not start the application lifespan, connect to storage, or
execute endpoint handlers.

## Commands

Generate the release-default surface (`MOSS_AGENT_ENABLED=false`):

```powershell
python scripts/backend_api_inventory.py `
  --surface default `
  --format json `
  --output .codex-tmp/backend-api-inventory.default.json
```

Generate the union of all currently known registration feature flags:

```powershell
python scripts/backend_api_inventory.py `
  --surface full `
  --format json `
  --output .codex-tmp/backend-api-inventory.full.json

python scripts/backend_api_inventory.py `
  --surface full `
  --format markdown `
  --output .codex-tmp/backend-api-inventory.full.md

python scripts/backend_api_inventory.py `
  --surface full `
  --format csv `
  --output .codex-tmp/backend-api-inventory.full.csv
```

Use `--surface current` only when the goal is to inspect the current shell
configuration. Do not treat `current` as the release default.

## Current baseline

| Surface | Registry entries | Unique paths | Operations |
| --- | ---: | ---: | ---: |
| Release default | 34 | 245 | 252 |
| Full known surface | 35 | 258 | 269 |

The full surface contains 217 GET, 48 POST, 2 PUT, 1 PATCH, and 1 DELETE
operation. The additional 17 operations are the feature-gated Agent and nested
Agent Workspace surface.

## Field interpretation

- `route_group`, `claim_boundary`, and `risk_boundary` come directly from the
  route registry.
- `registration` and `feature_flag` distinguish always-registered routes from
  registration-gated routes.
- `action_class` is a deterministic method/path/handler heuristic. It helps
  split reads, refreshes, imports, exports, manual adjustments, streams, and
  workflow commands, but it still requires domain-owner review.
- `write_candidate` means the HTTP method is not GET/HEAD/OPTIONS. POST query
  endpoints can still be computationally read-only, so this field is not a
  storage-write assertion.
- `auth_dependency_present` only reports dependency-chain evidence. It does not
  infer the final resource/action scope enforced inside a handler.
- `request_schema` and `response_schema` summarize the outward OpenAPI
  contract. `unspecified_success` means the success response is registered but
  OpenAPI does not declare a concrete success schema; the generator does not
  substitute a validation-error schema. The exported OpenAPI document remains
  the full schema authority.

## Next enrichment pass

The route baseline should be enriched domain by domain, not by editing all
handlers at once:

1. balance, average balance, and balance movement;
2. bond analytics, cashflow, and credit spread;
3. PnL, product-category PnL, and attribution;
4. ledger, GL, and KPI;
5. positions, risk tensor, and liability compatibility;
6. macro, market, news, and external data;
7. executive, dashboard, health, preview, and query support;
8. Agent and Agent Workspace.

For each operation, the enrichment should add the confirmed frontend or
external consumer, page/workflow role, service/repository/core-finance/task
chain, result-meta basis, data lineage, authorization scope, and executed test
evidence.

Static repository evidence can identify a UI-orphan, repository-orphan
candidate, or test gap. It cannot prove that an endpoint has no external
consumer without gateway/access-log or consumer-registry evidence.

## Completed domain tie-outs

- Product-category PnL:
  `docs/audits/2026-07-27-product-category-pnl-api-tieout.md`
