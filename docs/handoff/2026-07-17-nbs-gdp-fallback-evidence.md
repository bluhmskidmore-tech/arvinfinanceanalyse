# NBS GDP Automatic Fallback Evidence

## Diagnostic baseline

- Diagnostic date: `2026-07-17`
- Live Tushare latest observation: `2026Q1 = 5.0`
- Official NBS release: `https://www.stats.gov.cn/sj/xwfbh/fbhwd/202607/t20260715_1964121.html`
- Expected official observation: `2026Q2 = 4.3`
- Classified lineage break: upstream vendor synchronization delay; the existing raw, standard, repository, and homepage chain agrees with the Tushare response.

## Required lineage receipt

Every successful official release ingest must record:

- `release_url`
- `content_sha256`
- `rule_version`
- `batch_id`
- `report_period`
- `value`
- immutable original HTML archive path
- normalized JSON archive path
- selected `series_id` (`nbs.macro.cn_gdp.quarterly` when NBS wins)
- `selected_vendor`
- refresh `run_id`

## Rollback contract

If official discovery or parsing becomes unreliable, disable NBS selection and
leave the governed Tushare candidate available as fallback. Do not delete NBS
observations, ingest batches, or immutable raw and normalized archives; retain
them for audit and correction.

Repository implementation is complete; final read-only preview is pending.
Live value and lineage tie-out remains pending an authorized shadow write.

## Status

- Repository implementation: **待实施**
- Live value and lineage tie-out: **待实数核对**
- External scheduler enablement: out of scope; separate operations authorization is required.

## Read-only preview receipt

- Preview date: `2026-07-17`
- `release_url`: `https://www.stats.gov.cn/sj/xwfbh/fbhwd/202607/t20260715_1964121.html`
- `content_sha256`: `0dec4989b388ec07eb5b9b73c44d68888cd7be741f7453c1078d393dc215ae4b`
- `series_id`: `nbs.macro.cn_gdp.quarterly`
- `rule_version`: `rv_nbs_gdp_release_v1`
- `report_period=2026-03-31`, `value=5.0`
- `report_period=2026-06-30`, `value=4.3`
- `writes_performed`: `false`

## Current gate

- Repository implementation and read-only official-source validation: **complete**
- Live governed value and lineage tie-out: **blocked pending explicit shadow-write authorization**
- External scheduler enablement: **out of scope and not performed**

## Governed shadow-write receipt

Pre-write inspection after explicit user authorization found that two governed
NBS batches had already been created by the earlier test-isolation leak. No
third batch was added. The existing records are retained under the rollback
contract; governed observations and immutable archives must not be deleted.

- Primary batch: `nbs-gdp-20260717T085742Z-3aeb4525`
- Manifest status: `completed`
- Rerun batch: `nbs-gdp-20260717T085746Z-0ff6dcd7`
- Manifest status: `rerun`, linked to the primary batch
- `release_url`: `https://www.stats.gov.cn/sj/xwfbh/fbhwd/202607/t20260715_1964121.html`
- Official HTML SHA-256: `0dec4989b388ec07eb5b9b73c44d68888cd7be741f7453c1078d393dc215ae4b`
- Normalized JSON SHA-256: `555c7a0cf33dc1fbfff17f3f2b140e00c670ce20e7f8a1099caec65485bff969`
- `2026-03-31`: `5.0 pct`
- `2026-06-30`: `4.3 pct`
- Catalog: `nbs.macro.cn_gdp.quarterly`, vendor `nbs`, frequency `quarterly`, unit `pct`
- Standardized table: `std_external_macro_daily`
- Rule version: `rv_nbs_gdp_release_v1`
- Raw and normalized archives exist for both batches and have identical hashes.

## Homepage closure receipt

- Selected source: `NBS official release (nbs.macro.cn_gdp.quarterly)`
- Current period/value: `2026-Q2 / 4.3%`
- Previous period/value: `2026-Q1 / 5.0%`

## Browser closure receipt

- API: `GET /ui/home/macro-release-context` returned HTTP `200`.
- Frontend data path: the existing macro release query hook is wired into the
  homepage body view; governed API history replaces the manually maintained
  calendar history for the real-data page.
- Browser assertions: `2026-Q2`, `4.3%`, `2026-Q1`, `5.0%`, and
  `NBS official release` were all visible in the homepage research-calendar section.
- Browser console errors: none.
- Screenshot: `frontend/.codex-tmp/home-nbs-gdp-shadow-write.png`
