# API Contract Tooling

MOSS exports the FastAPI OpenAPI document, lints it, and compares it against a
committed baseline so that a breaking backend change fails CI instead of
reaching a page as `undefined`.

## Surfaces

Router registration is feature-flagged (`MOSS_AGENT_ENABLED`), so "the API" is
not one thing. Every contract command takes the same `--surface` switch as
`scripts/backend_api_inventory.py`:

| Surface   | Meaning                                                            |
| --------- | ------------------------------------------------------------------ |
| `default` | Release default, Agent routes off. Used by CI and by both baselines. |
| `full`    | Every known registration flag enabled. Superset of `default`.        |
| `current` | Honours the ambient environment. Never used for committed artifacts. |

Pinning the surface is what makes the export reproducible: without it a
developer's `config/.env` decides whether the Agent routes appear, and the same
command produces a different document on each machine.

## Commands

Export the OpenAPI document:

```powershell
python scripts/api_contract_check.py export-openapi --surface default --output .codex-tmp/openapi.json
```

Lint the exported contract with Spectral:

```powershell
cd frontend
npm run lint:openapi
```

Check the current code against the committed baseline:

```powershell
python scripts/api_contract_check.py baseline-check
python scripts/api_contract_check.py baseline-check --baseline-ref origin/main
```

Refresh the committed baseline snapshots:

```powershell
python scripts/api_contract_check.py baseline-update
```

Print the Schemathesis smoke command:

```powershell
python scripts/api_contract_check.py schemathesis-command
```

Generate the endpoint-level backend inventory:

```powershell
python scripts/backend_api_inventory.py --surface default --format json --output .codex-tmp/backend-api-inventory.default.json
python scripts/backend_api_inventory.py --surface full --format markdown --output .codex-tmp/backend-api-inventory.full.md
```

See `docs/BACKEND_API_INVENTORY.md` for the surface definitions, field
interpretation, and domain-enrichment boundary.

## The baseline and the breaking-change gate

Committed artifacts live in `contracts/openapi/`:

- `openapi.default.json` and `openapi.full.json` — key-sorted OpenAPI documents,
  one per baseline surface.
- `breaking-change-acknowledgements.json` — the only way to ship a breaking
  change.

`baseline-check` reports two independent things.

**Baseline freshness.** The committed snapshot must still equal what the code
produces. Any drift fails with a one-line fix (`baseline-update`). This is what
keeps the snapshot worth reviewing: a stale baseline degrades into a number
nobody trusts. Use `--allow-stale-baseline` to demote it to a warning locally.

**Breaking changes.** With `--baseline-ref`, the diff runs against the baseline
as committed on that ref — in CI, the pull request's base branch. Rewriting the
snapshot inside the same pull request therefore cannot clear a finding, because
the comparison never looks at the working-tree snapshot. Clearing one requires
an acknowledgement entry, which shows up in review.

Additive changes never fail the gate: new operations, new optional parameters,
new response fields, and new success statuses are reported and pass.

These changes fail:

| Kind                                                              | Why it breaks a consumer                        |
| ----------------------------------------------------------------- | ----------------------------------------------- |
| `operation_removed`, `operation_id_changed`                         | The call disappears or its generated name moves |
| `response_field_removed`, `response_field_type_changed`             | The client reads `undefined` or `NaN`           |
| `response_field_became_optional`, `response_schema_removed`         | A value the client relied on is no longer promised |
| `response_status_removed`                                           | A handled success path disappears               |
| `response_enum_value_added`                                         | An exhaustive client switch falls through       |
| `parameter_removed`, `parameter_became_required`                    | Existing calls are rejected or silently ignored |
| `required_parameter_added`, `required_request_field_added`          | Existing calls are rejected                     |
| `request_field_removed`, `request_field_type_changed`               | Submitted data is silently dropped              |
| `request_enum_value_removed`                                        | A previously valid value is rejected            |

Only 2xx responses are governed. Framework-generated error envelopes such as
`422 HTTPValidationError` are excluded, because their churn would bury the
signal.

### Shipping a breaking change

1. Run `baseline-check --baseline-ref origin/main` and copy the printed `id:` of
   each finding.
2. Add one entry per id to `contracts/openapi/breaking-change-acknowledgements.json`
   with a real `reason` and `approved_by`. Blank values are rejected. Replace the
   surface segment with `*` to cover both surfaces in one entry.
3. Run `baseline-update` and commit the refreshed snapshots in the same pull
   request. Explain the change in the pull request description.
4. After the merge, delete the entry. The change is now part of the base-branch
   baseline, so `baseline-check` reports leftover entries as unused.

`tests/test_api_contract_baseline_gate.py` mutates the committed baseline to
prove each of these classes is still detected.

## Endpoint counts

`tests/test_backend_api_inventory.py` no longer asserts literal endpoint and
method counts. Those numbers could not distinguish an added endpoint from a
deleted one — both read as "the number moved", and both were fixed by editing
the number. The counting job belongs to the OpenAPI diff gate, which classifies
the direction of the change; the inventory test now pins the registry-to-router
correspondence by name and cross-checks its operation set against the committed
baseline.

## Spectral project rules

`.spectral.yaml` only carries rules that are at zero violations. A rule shipped
at `warn` because the codebase already breaks it is not a ruler, it is a log
line. Everything below was dry-run against `openapi.full.json`; the counts are
measured, not estimated.

Enabled today: `query-param-snake-case` (0 violations).

Not enabled, in the order they become cheap:

**`path-segment-kebab-case` — 7 violations.** The rule below is verified working
and reports exactly these paths: `/api/analysis/yield_metrics`,
`/api/dashboard/core_metrics`, `/api/data/import_status/pnl`,
`/api/data/refresh_pnl`, `/api/kpi/fetch_and_recalc`,
`/api/positions/bonds/sub_types`, `/api/positions/interbank/product_types`.
Enabling it first requires renaming those routes, which is a breaking change and
now has to clear the baseline gate with acknowledgement entries.

```yaml
  path-segment-kebab-case:
    description: Static path segments must be kebab-case.
    message: "Path '{{property}}' has a non-kebab-case segment."
    severity: error
    given: $.paths
    then:
      field: "@key"
      function: pattern
      functionOptions:
        match: "^(/([a-z0-9]+(-[a-z0-9]+)*|\\{[A-Za-z0-9_]+\\}))+$"
```

**"every 2xx has a field-level schema" — 228 violations.** Blocked on the
`response_model` work described below. Note that the naive form of this rule
("the 2xx has a `content` block") passes on all 269 operations and is therefore
worthless here; the rule has to require `$ref`, `properties`, or `items`.

**"one pagination vocabulary" — two competing schemes in use.** `limit` (16
operations) and `offset` (9) versus `page` (4) and `page_size` (4). This needs a
naming decision and a migration before a lint rule can express it.

**"date parameters come from a controlled vocabulary" — needs the vocabulary
first.** `report_date` (83), `as_of_date` (23), `end_date` (17), `start_date`
(16), `report_month` (14), and `date` (6) are already consistent. The open tail
is windows and periods rather than dates: `lookback_days` (8), `period_type`
(5), `days`, `window_days`, `report_dates`, `trend_months`, `months`, `periods`,
`backfill_days`, `sector_window_days`, `trade_date`, `evaluation_as_of_date`.

## What the gate cannot see

The diff gate can only compare structure that the OpenAPI document actually
declares, and most of this API declares none. On the full surface:

| Success body shape                                          | Operations |
| ----------------------------------------------------------- | ---------: |
| Field-level schema (`$ref` / `properties` / `items`)          |         41 |
| Free-form object (`response_model=dict`, `additionalProperties: true`) |    220 |
| Empty `{}` (no `response_model` at all)                       |          8 |

That is 2089 governed leaf fields across 41 operations, and 228 operations where
renaming a payload key is invisible to the gate.

`response_model=ResultEnvelope` is not the exception it looks like. Its `result`
member is `anyOf[object with additionalProperties, array]`, so the 12 operations
using it contribute exactly three governed fields — `calibration`, `result`,
`result_meta` — and nothing about the numbers inside. The genuinely protected
operations are the ones with bespoke typed envelopes, such as
`LedgerPnlAnalysisEnvelope` (146 fields) and `CampisiAttributionEnvelope` (177).

Closing this gap means giving endpoints real response models. Until then the
gate protects the shape of the API, not the shape of most of its payloads.

## Boundary

Spectral runs in CI against the exported document, but its ruleset is thin by
design, so a clean Spectral run means very little on its own — the
breaking-change gate, not Spectral, is the contract defence today.

Schemathesis stays an external command rather than a CI job. It is not a
declared backend dependency, and running it needs a live server. The historical
reason recorded here — a `pytest<9` pin conflicting with Schemathesis — no
longer applies: `backend/pyproject.toml` requires `pytest>=9.0.3,<10`, and
Schemathesis 4.x runs alongside it. Note that Schemathesis 4 replaced the old
`--app` option with a positional schema location plus `--url`.
