# MOSS Performance Baseline After Bundle Optimizations

Date: 2026-07-08
Branch: `codex/V1`
Latest commit at capture time: `852ae8ac Guard bond curve bundle dedupe`
DuckDB: `F:\MOSS-V3\data\moss.duckdb`
Primary bond report date: `2026-06-30`

## Scope

This artifact records the post-optimization baseline for the recent MOSS performance work:

- home snapshot cache behavior
- bond dashboard and bond analytics cockpit bundle behavior
- macro toolkit full analysis
- Livermore market-data read path
- frontend request-shape evidence for bond analytics cockpit and mid-chart curve reuse

This is an engineering performance baseline only. It does not approve business closure, change metric definitions, certify formal fixed-income calculations, or write governance records.

## Measurement Method

The timing table below is service-level local timing, captured in the current Python process against the local governed DuckDB. It is not an HTTP server, browser, Playwright, or production infrastructure benchmark.

Cache reset used before the first sample for each case:

- bond bundles: `bond_dashboard_service.clear_bond_dashboard_runtime_cache()`
- home snapshot: `executive_service.invalidate_home_snapshot_cache()`
- macro toolkit: `market_home_response_cache.invalidate()` before direct `_build_macro_toolkit_analysis("full")`
- Livermore: `market_home_response_cache.invalidate()` before direct `livermore_strategy_envelope_from_catalog(...)`

Important caveat: "cold" here means process-local cache reset, not a fresh OS process with empty filesystem/OS cache. The numbers are suitable as a regression baseline for this branch, not as an SLA.

## Endpoint And Service Timing

| Surface | Measured entry | Cold first request | Hot cache average | Quality | Notes |
| --- | --- | ---: | ---: | --- | --- |
| Bond analytics cockpit bundle | `get_bond_dashboard_bundle`, 12 cockpit sections | 633.7ms | 316.5ms | ok | section failures `[]`; tail alternates between dashboard aggregate sections, DV01 aliases, and yield curve |
| Bond dashboard page bundle | `get_bond_dashboard_bundle`, 12 dashboard sections | 367.7ms | 173.4ms | ok | section failures `[]`; tail is risk/headline/asset aggregate SQL family |
| Home snapshot | `home_snapshot_envelope(report_date=None)` | 467.0ms | 4.3ms | ok | executive overview/home snapshot cache is now the decisive hot-path win |
| Macro toolkit full analysis | `_build_macro_toolkit_analysis("full")` | 4852.8ms | 2098.2ms | ok | largest remaining backend tail; direct builder timing bypasses route response-cache wrapper |
| Livermore market data | `livermore_strategy_envelope_from_catalog(...)` | 305.1ms | 0.6ms | warning | warning quality is data-state related; hot path is dominated by process cache hit |

### Bond Analytics Cockpit Bundle Section Tail

Cold sample: 633.7ms total.

| Tail section | Section duration |
| --- | ---: |
| `maturity-structure` | 387.471ms |
| `headline-kpis` | 387.022ms |
| `asset-structure` | 380.278ms |
| `risk-indicators` | 379.625ms |
| `portfolio-headlines` | 355.113ms |

Hot samples averaged 316.5ms. The observed hot tail rotated among `yield-curve-term-structure`, DV01 aliases, dashboard aggregate sections, and `top-holdings`.

### Bond Dashboard Page Bundle Section Tail

Cold sample: 367.7ms total.

| Tail section | Section duration |
| --- | ---: |
| `headline-kpis` | 296.915ms |
| `risk-indicators` | 295.736ms |
| `asset-structure` | 291.072ms |
| `asset-structure-rating` | 290.896ms |
| `asset-structure-portfolio-name` | 290.047ms |

Hot samples averaged 173.4ms. The persistent tail is the dashboard aggregate SQL family, not frontend request fan-out.

## Frontend Request Shape Baseline

| Page / component scope | Before bundle work | Current baseline | Evidence |
| --- | ---: | ---: | --- |
| Bond analytics Institutional Cockpit business data | about 14 parallel section requests | 1 `fetchBondDashboardBundle` request | `114cfd80`, `frontend/src/features/bond-analytics/lib/bondAnalyticsCockpitBundleQuery.ts` |
| Bond analytics cockpit supporting reads | dates + macro latest | dates + macro latest remain separate | intentional: date fallback and macro context are separate concerns |
| Bond analytics overview mid chart curve | standalone yield-curve request could duplicate bundle curve | 0 standalone yield-curve requests when bundled data is provided | `323ace29`, guarded by `852ae8ac` |
| Bond analytics overview cockpit + mid charts together | bundle could regress to duplicate calls | 1 shared cockpit bundle request + 1 return-decomposition summary request | `frontend/src/test/BondAnalyticsYieldCurveTermStructureChart.test.tsx` |
| Bond dashboard page business data | multiple section requests | 1 `fetchBondDashboardBundle` request after dates | `4408aca7` lineage plus current bundle model tests |

The latest guard test asserts that when a sibling cockpit bundle consumer and `BondAnalyticsOverviewMidCharts` mount together:

- `fetchBondDashboardBundle` is called exactly once
- `getBondAnalyticsYieldCurveTermStructure` is not called
- return decomposition still calls once, as expected for the waterfall chart

## Bottleneck Ranking

Current remaining bottlenecks by measured local service time:

1. `macro_toolkit_analysis?detail=full`: about 4.85s cold, about 2.10s hot through the direct builder. This is the largest remaining tail.
2. Bond analytics cockpit bundle: about 634ms cold, about 317ms hot. The remaining tail is inside backend bundle sections, not XHR fan-out.
3. Bond dashboard page bundle: about 368ms cold, about 173ms hot. Remaining cost is dashboard aggregate SQL and payload assembly.
4. Home snapshot cold build: about 467ms cold, but about 4ms hot; practical user-facing risk depends on prewarm/cache hit.
5. Livermore strategy: about 305ms cold, less than 1ms hot; practical risk is cache invalidation and data warning state, not steady-state read latency.

## Commits Covered

| Commit | Effect captured in this baseline |
| --- | --- |
| `4cc10a3e` family | DuckDB scoped/read-only connection reuse, macro SQL pushdown, governance JSONL cache, request timeout/frontend waterfall fixes |
| `114cfd80` | bond analytics cockpit bundle endpoint wiring, section failure isolation, dynamic mock binding |
| `323ace29` | curve chart reads bundled yield-curve data when provided |
| `016f7475` | return decomposition curve reads batched |
| `f1302816` | summary return decomposition skips per-bond detail payloads |
| `e8b63768` | bundle section timing exposed and fact-row fetches collapsed |
| `2b92ecfb` | bond dashboard bundle reuses per-bundle reads and headline snapshot |
| `852ae8ac` | frontend regression guard for cockpit bundle dedupe |

## Verification Evidence

Commands run in this optimization sequence:

```powershell
python -m pytest tests/test_bond_dashboard_bundle.py tests/test_bond_dashboard_api_contract.py tests/test_bond_analytics_service.py -q
npm run test -- BondAnalyticsYieldCurveTermStructureChart.test.tsx
npm run typecheck
npm run lint
npm run debt:audit
```

Observed results:

- backend related subset: `71 passed`
- bond yield-curve frontend test: `4 passed`
- frontend typecheck: passed
- frontend lint: 0 errors, 10 existing warnings
- frontend debt audit: passed, no growth over baseline

## Residual Risks

- These are local service timings, not production HTTP/browser timings.
- GitNexus `detect-changes` is currently polluted by unrelated concurrent dirty files in the shared worktree, so its medium-risk summary is not a clean read of only the performance commits.
- Macro toolkit full analysis remains the clear backend tail and should be the next measured target if user-perceived load is still slow.
- Bond bundle tail is now backend-section dominated; further gains require focused repository/service profiling, not more frontend request bundling.

## Next Measurement Step

For a production-grade baseline, run a browser-level capture with the dev API on `127.0.0.1:7888` and the frontend dev server, then append:

- page URL
- cold navigation request count
- XHR/fetch count by endpoint
- max waterfall depth
- first meaningful data paint timestamp
- screenshots or Playwright trace artifact path

Until that capture exists, use this document as the local service regression baseline.
