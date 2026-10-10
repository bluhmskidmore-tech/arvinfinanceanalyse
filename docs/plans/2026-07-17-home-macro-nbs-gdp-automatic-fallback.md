# Home Macro NBS GDP Automatic Fallback Implementation Plan

> **Implementation instruction:** Use the repository's `executing-plans` workflow to implement this plan task by task.

**Goal:** Automatically ingest quarterly China GDP YoY from the National Bureau of Statistics release pages and use it as the homepage primary source, with Tushare retained as a traceable fallback when the official source is unavailable.

**Architecture:** Add a separate `nbs.macro.cn_gdp.quarterly` series rather than writing official data under a Tushare identity. A governed NBS adapter discovers release pages from a stable official listing, validates the exact trusted host, archives the source HTML and a normalized JSON payload with SHA-256 evidence, and materializes explicit NBS lineage into `std_external_macro_daily`. The homepage binding selects the freshest valid candidate, preferring NBS when both sources cover the same observation period; no database schema, global freshness policy, or scheduler base changes are required.

**Tech Stack:** Python 3.14, Requests, BeautifulSoup, DuckDB, Pydantic, Dramatiq, pytest, Ruff.

---

## 1. Confirmed evidence and non-negotiable rules

- On 2026-07-17, live Tushare `cn_gdp()` returned 177 rows and stopped at `2026Q1 = 5.0`.
- The NBS official 2026-07-15 release states `2026Q2 = 4.3` YoY.
- Existing raw, standard-table, repository, and homepage results are internally consistent; the break is at the Tushare upstream boundary.
- New official rows must use `series_id=nbs.macro.cn_gdp.quarterly`, `vendor_name=nbs`, and `source_family=nbs_gdp_release`.
- Never write NBS values under `tushare.macro.cn_gdp.quarterly` and never relabel existing Tushare rows.
- Discovery must start from a stable NBS listing URL. Per-release URLs and values must not require manual configuration.
- Only `https://stats.gov.cn` and `https://www.stats.gov.cn` are trusted. Revalidate the final redirect host.
- Archive original HTML bytes before parsing. Persist content SHA-256, release URL, parser rule version, batch ID, and report period.
- `null`, missing, non-finite, conflicting, or ambiguous GDP values fail closed. `0.0` remains valid.
- Homepage selection order is based on validity and period, not vendor labels:
  1. discard invalid candidates;
  2. prefer non-stale candidates;
  3. prefer the latest observation period;
  4. for the same period, prefer NBS priority 1 over Tushare priority 2.
- A fresh Tushare selection is visibly `fallback`; a stale selection remains `stale` regardless of vendor.
- Do not enable an external timer in this plan. Repository completion and operations completion remain separate.

---

### Task 0: Freeze the governed source contract and fixtures

**Files:**
- Create: `config/nbs_gdp_release_source.json`
- Create: `tests/fixtures/nbs_gdp_release/listing.html`
- Create: `tests/fixtures/nbs_gdp_release/2026_h1_release.html`
- Create: `tests/test_nbs_gdp_release_source_contract.py`
- Create: `docs/handoff/2026-07-17-nbs-gdp-fallback-evidence.md`

**Step 1: Write the failing contract test**

Assert the config contains only stable discovery metadata, not a release value or a pinned per-release URL:

```python
def test_nbs_gdp_source_contract_is_automatic_and_lineage_complete() -> None:
    payload = json.loads(SOURCE_CONFIG.read_text(encoding="utf-8"))
    assert payload == {
        "series_id": "nbs.macro.cn_gdp.quarterly",
        "series_name": "China GDP YoY (NBS official release)",
        "listing_url": "https://www.stats.gov.cn/sj/xwfbh/fbhwd/",
        "allowed_hosts": ["stats.gov.cn", "www.stats.gov.cn"],
        "frequency": "quarterly",
        "unit": "pct",
        "rule_version": "rv_nbs_gdp_release_v1",
        "catalog_version": "m2b.nbs_gdp_release.v1",
        "max_document_bytes": 2_000_000,
    }
    text = SOURCE_CONFIG.read_text(encoding="utf-8")
    assert "4.3" not in text
    assert "t20260715" not in text
```

Use small synthetic HTML fixtures that reproduce the listing-link structure and the sentence `分季度看，一季度……二季度增长4.3%`. Do not copy the full official page.

**Step 2: Run the test and confirm RED**

```powershell
pytest tests/test_nbs_gdp_release_source_contract.py -q
```

Expected: FAIL because the contract and evidence file do not exist.

**Step 3: Add the minimal contract and evidence record**

The evidence record must include the diagnostic date, live Tushare latest quarter, official NBS release URL, expected Q2 value, and the required lineage fields. Mark implementation and live tie-out as pending.

**Step 4: Run the test and confirm GREEN**

```powershell
pytest tests/test_nbs_gdp_release_source_contract.py -q
```

Expected: PASS.

**Step 5: Commit**

```powershell
git add config/nbs_gdp_release_source.json tests/fixtures/nbs_gdp_release tests/test_nbs_gdp_release_source_contract.py docs/handoff/2026-07-17-nbs-gdp-fallback-evidence.md
git commit -m "test: define automated NBS GDP source contract"
```

---

### Task 1: Implement trusted NBS discovery and GDP parsing

**Files:**
- Create: `backend/app/repositories/nbs_gdp_release_adapter.py`
- Create: `tests/test_nbs_gdp_release_adapter.py`

**Step 1: Perform impact and evidence gates**

- Query GitNexus context and upstream impact for the new adapter consumers before connecting it to shared code.
- Query metric contracts and lineage MCP for GDP unit, cadence, observation-date convention, and required versions.
- If MCP remains unavailable, record local official evidence and residual risk; do not change the `pct` unit or quarterly period-end convention.

**Step 2: Write failing parser/security tests**

Cover:

- relative listing links resolve only to the allowed NBS hosts;
- an initial or redirected `stats.gov.cn.evil.example` URL is rejected;
- HTTP status, content type, timeout, and `max_document_bytes` fail closed;
- the release sentence maps Q1/Q2 to `2026-03-31` and `2026-06-30`;
- the parser returns `5.0` and `4.3`, preserving `0.0`;
- missing `分季度看`, duplicate conflicting values, `NaN`, and unsupported quarter text raise a typed error;
- discovery scans a bounded number of newest listing links and selects the newest valid GDP release;
- no value is inferred from cumulative first-half GDP growth.

Desired public surface:

```python
@dataclass(frozen=True)
class NbsGdpReleaseDocument:
    release_url: str
    fetched_at: datetime
    html_bytes: bytes
    observations: list[dict[str, object]]


class NbsGdpReleaseAdapter:
    vendor_name = "nbs"

    def discover_and_fetch(self, *, reference_date: date) -> NbsGdpReleaseDocument: ...
```

**Step 3: Run tests and confirm RED**

```powershell
pytest tests/test_nbs_gdp_release_adapter.py -q
```

Expected: FAIL because the adapter is missing.

**Step 4: Implement the smallest secure adapter**

- Use `requests.get(..., timeout=(5, 20), allow_redirects=True)`.
- Validate both requested URL and `response.url` with `urllib.parse.urlparse`.
- Parse HTML with `BeautifulSoup(..., "html.parser")`.
- Limit listing candidates, for example the newest 20 matching official news links.
- Extract year from the release date/page metadata and quarter/value pairs only from the `分季度看` GDP sentence.
- Return normalized rows shaped as:

```python
{
    "trade_date": "2026-06-30",
    "value": 4.3,
    "source_version": "nbs_gdp_release_sha256_<digest>",
}
```

Do not archive or write DuckDB in the adapter.

**Step 5: Run tests and Ruff**

```powershell
pytest tests/test_nbs_gdp_release_adapter.py -q
ruff check backend/app/repositories/nbs_gdp_release_adapter.py tests/test_nbs_gdp_release_adapter.py
```

Expected: PASS.

**Step 6: Commit**

```powershell
git add backend/app/repositories/nbs_gdp_release_adapter.py tests/test_nbs_gdp_release_adapter.py
git commit -m "feat: discover and parse official NBS GDP releases"
```

---

### Task 2: Preserve official provenance through the shared standard ETL

**Files:**
- Modify: `backend/app/services/external_std_macro_etl_service.py`
- Modify: `tests/test_external_std_macro_etl_service.py`

**Step 1: Run GitNexus impact before editing the shared symbol**

Run upstream impact for `ExternalStdMacroEtlService.materialize_from_raw`. If impact is HIGH or CRITICAL, warn before editing and widen regression checks to every identified consumer.

**Step 2: Write the failing provenance-override test**

The existing Tushare behavior must remain unchanged. Add an explicit optional override case:

```python
count = service.materialize_from_raw(
    raw_path,
    nbs_catalog_entry,
    "nbs-gdp-batch-1",
    vendor_version="vv_nbs_gdp_release_sha256_deadbeef",
    rule_version="rv_nbs_gdp_release_v1",
)
row = conn.execute(
    "select vendor_name, vendor_version, source_version, rule_version from std_external_macro_daily"
).fetchone()
assert row == (
    "nbs",
    "vv_nbs_gdp_release_sha256_deadbeef",
    "nbs_gdp_release_sha256_deadbeef",
    "rv_nbs_gdp_release_v1",
)
```

**Step 3: Run test and confirm RED**

```powershell
pytest tests/test_external_std_macro_etl_service.py -q
```

Expected: FAIL because the keyword arguments are unsupported.

**Step 4: Add backward-compatible optional overrides**

Extend only the method signature and its two version assignments:

```python
def materialize_from_raw(
    self,
    raw_zone_path: str,
    catalog_entry: ExternalDataCatalogEntry,
    ingest_batch_id: str,
    *,
    vendor_version: str | None = None,
    rule_version: str | None = None,
) -> int:
    ...
    vver = vendor_version or f"{vendor}|{catalog_entry.catalog_version}"
    rver = rule_version or "m2b.external_std_macro_etl.v1"
```

Do not change the SQL schema, insert grain, existing default versions, or Tushare task calls.

**Step 5: Run narrow and consumer regressions**

```powershell
pytest tests/test_external_std_macro_etl_service.py tests/test_tushare_macro_ingest_service.py tests/test_tushare_macro_ingest_task.py -q
ruff check backend/app/services/external_std_macro_etl_service.py tests/test_external_std_macro_etl_service.py
```

Expected: PASS.

**Step 6: Commit**

```powershell
git add backend/app/services/external_std_macro_etl_service.py tests/test_external_std_macro_etl_service.py
git commit -m "feat: preserve governed macro provenance overrides"
```

---

### Task 3: Build the governed NBS ingest service and catalog entry

**Files:**
- Create: `backend/app/repositories/nbs_gdp_catalog_seed.py`
- Create: `backend/app/services/nbs_gdp_release_ingest_service.py`
- Create: `tests/test_nbs_gdp_release_ingest_service.py`

**Step 1: Write failing service tests**

Cover:

- series identity is `nbs.macro.cn_gdp.quarterly`;
- original HTML is archived immutably under vendor `nbs`;
- normalized JSON is separately archived and is the ETL input;
- SHA-256 of original HTML appears in source and vendor versions;
- catalog records `vendor_name=nbs`, `source_family=nbs_gdp_release`, `frequency=quarterly`, `unit=pct`;
- manifest records release URL, HTML archive path, normalized archive path, report date, batch ID, and source version;
- rerunning identical content is idempotent at the canonical read layer and records rerun lineage;
- conflicting content at the same immutable raw path fails;
- empty or invalid observations cause no catalog success registration and no standard rows.

**Step 2: Run tests and confirm RED**

```powershell
pytest tests/test_nbs_gdp_release_ingest_service.py -q
```

Expected: FAIL because the catalog seed and service are missing.

**Step 3: Implement the service by composing existing repositories**

Use `RawZoneRepository`, `ExternalDataCatalogRepository`, `SourceManifestRepository`, and `ExternalStdMacroEtlService`. Keep all writes inside one caller-supplied DuckDB connection.

Return a structured result:

```python
{
    "status": "success",
    "series_id": "nbs.macro.cn_gdp.quarterly",
    "release_url": document.release_url,
    "latest_observation": "2026-06-30",
    "materialized_rows": 2,
    "source_version": "nbs_gdp_release_sha256_<digest>",
    "vendor_version": "vv_nbs_gdp_release_sha256_<digest>",
    "rule_version": "rv_nbs_gdp_release_v1",
    "html_raw_zone_path": "...",
    "normalized_raw_zone_path": "...",
}
```

**Step 4: Run tests and Ruff**

```powershell
pytest tests/test_nbs_gdp_release_ingest_service.py -q
ruff check backend/app/repositories/nbs_gdp_catalog_seed.py backend/app/services/nbs_gdp_release_ingest_service.py tests/test_nbs_gdp_release_ingest_service.py
```

Expected: PASS.

**Step 5: Commit**

```powershell
git add backend/app/repositories/nbs_gdp_catalog_seed.py backend/app/services/nbs_gdp_release_ingest_service.py tests/test_nbs_gdp_release_ingest_service.py
git commit -m "feat: materialize official NBS GDP releases"
```

---

### Task 4: Add a schedulable NBS actor without adding a scheduler

**Files:**
- Create: `backend/app/tasks/nbs_gdp_release_ingest.py`
- Modify: `backend/app/tasks/worker_bootstrap.py`
- Create: `tests/test_nbs_gdp_release_task.py`
- Modify: `tests/test_worker_bootstrap.py`

**Step 1: Write failing task tests**

Assert:

- actor name is exactly `refresh_nbs_gdp_release`;
- task uses configured DuckDB/governance/raw paths;
- migrations run before materialization;
- the service receives a single writable connection and closes it;
- output contains batch ID, release URL, latest observation, versions, row count, elapsed time, and status;
- missing release, network error, parse ambiguity, and write error produce structured `blocked` or `error` output;
- worker bootstrap imports the actor module;
- no scheduler creation command or timer loop exists in the module.

**Step 2: Run tests and confirm RED**

```powershell
pytest tests/test_nbs_gdp_release_task.py tests/test_worker_bootstrap.py -q
```

Expected: FAIL because the task is absent.

**Step 3: Implement the task and stable actor registration**

Follow the existing `run_tushare_macro_ingest_once` and `register_actor_once` pattern. Do not modify broker, scheduler, cache, or worker architecture.

**Step 4: Run tests and Ruff**

```powershell
pytest tests/test_nbs_gdp_release_task.py tests/test_worker_bootstrap.py -q
ruff check backend/app/tasks/nbs_gdp_release_ingest.py backend/app/tasks/worker_bootstrap.py tests/test_nbs_gdp_release_task.py tests/test_worker_bootstrap.py
```

Expected: PASS.

**Step 5: Commit**

```powershell
git add backend/app/tasks/nbs_gdp_release_ingest.py backend/app/tasks/worker_bootstrap.py tests/test_nbs_gdp_release_task.py tests/test_worker_bootstrap.py
git commit -m "feat: register official NBS GDP refresh actor"
```

---

### Task 5: Add explicit multi-source GDP selection to the homepage contract

**Files:**
- Modify: `config/home_macro_release_bindings.json`
- Modify: `backend/app/services/home_macro_release_context_service.py`
- Modify: `tests/test_home_macro_release_bindings_contract.py`
- Modify: `tests/test_home_macro_release_context_service.py`

**Step 1: Run GitNexus impact for the service symbols**

Check upstream impact for `_MetricBinding`, `_automatic_item`, and `_build_metric`. This path should remain limited to `/ui/home/macro-release-context`; stop and warn if evidence shows cross-page consumers.

**Step 2: Write failing binding and selection tests**

Change only the GDP metric binding to:

```json
{
  "metric_key": "gdp_yoy",
  "label": "GDP YoY",
  "source_candidates": [
    {
      "table": "std_external_macro_daily",
      "series_id": "nbs.macro.cn_gdp.quarterly",
      "vendor_name": "NBS official release",
      "priority": 1
    },
    {
      "table": "std_external_macro_daily",
      "series_id": "tushare.macro.cn_gdp.quarterly",
      "vendor_name": "Tushare",
      "priority": 2
    }
  ],
  "cadence": "quarterly",
  "display_unit": "pct",
  "change_unit": "pct_point",
  "precision": 1
}
```

Tests must cover:

- NBS Q2 plus Tushare Q1 selects NBS Q2 as `ready`;
- both sources on Q2 select NBS by priority;
- NBS missing/error plus fresh Tushare selects Tushare as `fallback`;
- NBS stale plus newer fresh Tushare selects Tushare as `fallback`;
- both stale selects the latest period as `stale`;
- invalid unit/cadence/null candidate is excluded, not silently converted;
- actual/previous/change come from one selected candidate series only;
- notes identify selected vendor and rejected/fallback reason;
- result-meta versions and evidence rows contain selected observations only;
- existing single-source PMI/CPI/PPI bindings remain valid;
- no static value appears in config.

**Step 3: Run tests and confirm RED**

```powershell
pytest tests/test_home_macro_release_bindings_contract.py tests/test_home_macro_release_context_service.py -q
```

Expected: FAIL because `source_candidates` is unsupported.

**Step 4: Implement minimal candidate selection**

Add a strict `_SourceCandidateBinding` model. Require exactly one of the legacy single source or a non-empty candidate list. Keep the current single-source path unchanged for PMI/CPI/PPI.

Candidate ranking must be deterministic and use the confirmed rules at the top of this plan. Do not merge current value from one vendor with previous value from another vendor.

**Step 5: Run tests and Ruff**

```powershell
pytest tests/test_home_macro_release_bindings_contract.py tests/test_home_macro_release_context_service.py tests/test_home_macro_release_context_repository.py tests/test_home_macro_release_context_endpoint.py -q
ruff check backend/app/services/home_macro_release_context_service.py tests/test_home_macro_release_context_service.py
```

Expected: PASS.

**Step 6: Commit**

```powershell
git add config/home_macro_release_bindings.json backend/app/services/home_macro_release_context_service.py tests/test_home_macro_release_bindings_contract.py tests/test_home_macro_release_context_service.py
git commit -m "feat: select official GDP with traceable fallback"
```

---

### Task 6: Integrate NBS GDP into the homepage refresh orchestrator

**Files:**
- Modify: `backend/app/tasks/home_macro_release_refresh.py`
- Modify: `tests/test_home_macro_release_refresh_task.py`
- Modify: `scripts/home_macro_release_refresh.py` only if output fields require CLI serialization coverage

**Step 1: Write failing orchestration tests**

Assert:

- NBS GDP ingest runs before the Tushare batch and Tushare-only PMI backfill;
- an NBS failure does not suppress Tushare fallback;
- GDP logical status is based on the selected fresh candidate, not whether the Tushare series advanced;
- NBS Q2 fresh produces GDP success with `selected_series_id=nbs.macro.cn_gdp.quarterly`;
- NBS unavailable plus fresh Tushare produces GDP success/fallback evidence without pretending it is NBS;
- both candidates stale keep the overall run `partial`;
- dry-run performs no NBS fetch and no writes, but reports both GDP candidates in the plan;
- structured warnings name the actual selected vendor.

**Step 2: Run tests and confirm RED**

```powershell
pytest tests/test_home_macro_release_refresh_task.py tests/test_home_macro_release_refresh_entrypoint.py -q
```

Expected: FAIL because the NBS task is not orchestrated.

**Step 3: Implement sequential single-writer orchestration**

Do not run NBS and Tushare DuckDB writes concurrently. Preserve the current PMI `series_names=["制造业PMI"]`, `sources_filter=["tushare_macro"]`, and 90-day overlap.

**Step 4: Run tests and Ruff**

```powershell
pytest tests/test_home_macro_release_refresh_task.py tests/test_home_macro_release_refresh_entrypoint.py tests/test_nbs_gdp_release_task.py -q
ruff check backend/app/tasks/home_macro_release_refresh.py scripts/home_macro_release_refresh.py tests/test_home_macro_release_refresh_task.py
```

Expected: PASS.

**Step 5: Commit**

```powershell
git add backend/app/tasks/home_macro_release_refresh.py tests/test_home_macro_release_refresh_task.py scripts/home_macro_release_refresh.py
git commit -m "feat: orchestrate official GDP before vendor fallback"
```

---

### Task 7: Extend operations handoff without enabling the timer

**Files:**
- Modify: `docs/templates/home_macro_release_refresh_scheduler_handoff.md`
- Modify: `docs/templates/home_macro_release_refresh_go_live_checklist.md`
- Modify: `docs/templates/home_macro_release_refresh_timer_enablement_packet.md`
- Modify: `docs/handoff/2026-07-16-home-macro-release-context-timer-preflight-status.md`
- Modify: `docs/handoff/2026-07-17-nbs-gdp-fallback-evidence.md`
- Modify: `docs/MAINTENANCE.md`
- Modify: `tests/test_home_macro_release_refresh_timer_preflight.py`

**Step 1: Write failing documentation/preflight tests**

Require:

- outbound allowlist includes only the two exact NBS hosts plus existing Tushare access;
- single-writer window remains explicit;
- first shadow run evidence includes release URL, hash, NBS series ID, selected vendor, value, period, and run ID;
- rollback disables NBS selection without deleting NBS or Tushare lineage rows;
- no `schtasks /Create`, `crontab`, or timer installation command appears;
- ops status remains blocked until owner, host, write window, log path, rollback, and first scheduled evidence are complete.

**Step 2: Run tests and confirm RED**

```powershell
pytest tests/test_home_macro_release_refresh_timer_preflight.py -q
```

Expected: FAIL because the NBS evidence gates are absent.

**Step 3: Update only the handoff and preflight contract**

Do not install a scheduler. Keep `--enqueue` as the only approved timer target.

**Step 4: Run tests**

```powershell
pytest tests/test_home_macro_release_refresh_timer_preflight.py -q
python scripts/home_macro_release_refresh_timer_preflight.py
```

Expected: tests PASS; repository status is complete and operations status remains intentionally blocked until external fields are filled.

**Step 5: Commit**

```powershell
git add docs/templates/home_macro_release_refresh_scheduler_handoff.md docs/templates/home_macro_release_refresh_go_live_checklist.md docs/templates/home_macro_release_refresh_timer_enablement_packet.md docs/handoff/2026-07-16-home-macro-release-context-timer-preflight-status.md docs/handoff/2026-07-17-nbs-gdp-fallback-evidence.md docs/MAINTENANCE.md tests/test_home_macro_release_refresh_timer_preflight.py
git commit -m "docs: govern automatic official GDP fallback"
```

---

### Task 8: Shadow run and real-data tie-out

**Files:**
- Update after evidence: `docs/handoff/2026-07-17-nbs-gdp-fallback-evidence.md`

**Step 1: Run all narrow tests before any write**

```powershell
pytest tests/test_nbs_gdp_release_source_contract.py tests/test_nbs_gdp_release_adapter.py tests/test_nbs_gdp_release_ingest_service.py tests/test_nbs_gdp_release_task.py tests/test_external_std_macro_etl_service.py tests/test_home_macro_release_bindings_contract.py tests/test_home_macro_release_context_repository.py tests/test_home_macro_release_context_service.py tests/test_home_macro_release_context_endpoint.py tests/test_home_macro_release_refresh_task.py tests/test_home_macro_release_refresh_entrypoint.py tests/test_worker_bootstrap.py -q
```

Expected: PASS.

**Step 2: Perform a network-only discovery preview**

Add or use a read-only preview entrypoint that prints release URL, quarter/value pairs, content hash, and parser version without writing DuckDB.

Expected for the confirmed official release: `2026-Q2 = 4.3`, unit `pct`, exact `stats.gov.cn` URL.

**Step 3: Obtain explicit authorization for a write run**

Do not infer production or timer authorization from repository implementation approval.

**Step 4: Run one approved shadow write**

Execute the NBS actor synchronously in the approved local/test environment, followed by the homepage refresh `--run-once`.

**Step 5: Tie out every layer**

Verify:

- raw HTML SHA-256 matches manifest evidence;
- normalized payload contains Q1 `5.0` and Q2 `4.3` with quarter-end dates;
- `std_external_macro_daily` contains separate NBS rows with correct versions;
- Tushare Q1 rows remain unchanged;
- repository canonical read has no duplicate period;
- homepage selects NBS Q2, previous NBS Q1, change `-0.7 pct_point`;
- homepage GDP status is `ready`, actual vendor note is NBS, and `as_of_date=2026-06-30`;
- no static JSON history value was added.

**Step 6: Record evidence and commit**

```powershell
git add docs/handoff/2026-07-17-nbs-gdp-fallback-evidence.md
git commit -m "docs: record official GDP fallback tie-out"
```

---

### Task 9: Full validation and cutover gate

**Files:**
- Review only: all files changed in Tasks 0–8

**Step 1: Run backend regressions and lint**

```powershell
pytest tests/test_tushare_adapter_m2a.py tests/test_tushare_macro_ingest_service.py tests/test_tushare_macro_ingest_task.py tests/test_tushare_macro_ingest_retry.py tests/test_external_std_macro_etl_service.py tests/test_nbs_gdp_release_source_contract.py tests/test_nbs_gdp_release_adapter.py tests/test_nbs_gdp_release_ingest_service.py tests/test_nbs_gdp_release_task.py tests/test_home_macro_release_bindings_contract.py tests/test_home_macro_release_context_repository.py tests/test_home_macro_release_context_service.py tests/test_home_macro_release_context_endpoint.py tests/test_home_macro_release_refresh_task.py tests/test_home_macro_release_refresh_entrypoint.py tests/test_home_macro_release_refresh_timer_preflight.py tests/test_worker_bootstrap.py -q
ruff check backend/app/repositories/nbs_gdp_release_adapter.py backend/app/repositories/nbs_gdp_catalog_seed.py backend/app/services/nbs_gdp_release_ingest_service.py backend/app/services/external_std_macro_etl_service.py backend/app/services/home_macro_release_context_service.py backend/app/tasks/nbs_gdp_release_ingest.py backend/app/tasks/home_macro_release_refresh.py scripts/home_macro_release_refresh.py
```

Expected: PASS.

**Step 2: Run required frontend gates because the page contract changed**

From `frontend/`:

```powershell
npm run test -- src/test/HomeMacroReleaseContextClient.test.ts src/features/workbench/dashboard-home/useDashboardHomeMacroReleaseContextQuery.test.tsx src/features/workbench/dashboard-home/adapters/buildHomeMacroBriefingModel.test.ts src/features/workbench/dashboard-home/sections/ResearchCalendarSection.test.tsx
npm run typecheck
npm run debt:audit
```

Expected: PASS and debt baseline does not grow.

**Step 3: Browser verification**

Verify the homepage shows GDP `2026-Q2`, `4.3%`, previous `5.0%`, change `-0.7 pct_point`, an official NBS source label, no manual-maintenance copy, and no horizontal overflow. Console must contain no error.

**Step 4: Run GitNexus change detection**

Expected affected scope: official GDP ingest, standard macro ETL optional provenance, homepage supplemental macro endpoint, and explicit task registration. `/ui/home/snapshot`, other pages, database schema, auth, broker, and scheduler base must be unaffected.

**Step 5: Cutover decision**

Only after the shadow tie-out and browser evidence pass may the existing homepage automation plan proceed to deleting static history. External timer enablement still requires separate operations authorization and a successful first scheduled-run record.

---

## 2. Rollback

- Disable the NBS source candidate in `config/home_macro_release_bindings.json`; retain the NBS rows and provenance for audit.
- Keep Tushare as the visible fallback and surface `fallback` or `stale` honestly.
- Do not delete raw HTML, manifests, standard rows, or existing Tushare batches.
- Do not restore manual GDP values to `dashboard_macro_release_calendar_2026.json`.
- Do not modify the database schema, global freshness engine, auth, broker, scheduler base, or `/ui/home/snapshot`.

## 3. Definition of done

### Repository complete

- Official GDP discovery needs no per-release URL or value edit.
- Trusted-host, redirect, size, parsing, conflict, null, zero, and lineage tests pass.
- NBS and Tushare remain separate series with reconstructable row-level provenance.
- Homepage selection is deterministic and never mixes actual/previous across vendors.
- NBS Q2 `4.3`, previous `5.0`, and change `-0.7 pct_point` tie out through raw → standard table → repository → service → UI.
- Tushare remains a visible fallback, not a relabeled official source.
- All narrow tests, Ruff, frontend typecheck, debt audit, and browser checks pass.

### Operations complete

- Named owner, timer host, single-writer window, log path, rollback, and outbound allowlist are approved.
- External timer is separately authorized and invokes only `--enqueue`.
- First scheduled run records configuration, logs, run ID, official URL/hash, selected vendor, period, and value.

