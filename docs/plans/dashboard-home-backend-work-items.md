# Dashboard Home Backend Work Items

Scope: dashboard-home content area only. Sidebar and global shell are out of scope.

## Evidence Snapshot

Last audited: 2026-05-31.

Runtime target:

| Item | Value |
| --- | --- |
| Frontend route | `http://localhost:5888/` |
| API base | `http://127.0.0.1:7888` |
| Report date | `2026-04-30` |
| Latest screenshot | `docs/plans/artifacts/dashboard-home-visual-pass6-income-change.png` |

MCP evidence note:

- `codex mcp list` confirms the project MCP servers are registered, including `moss-metric-contracts`, `moss-lineage-evidence`, `moss-data-catalog`, and `gitnexus`.
- The current Codex tool surface did not expose direct callable `moss-*` tools in this session.
- This audit therefore uses the project page scripts, live API responses, and DOM-visible homepage blocks as local evidence.
- Residual risk: before changing backend formulas or metric definitions, re-check the metric-contract and lineage MCP tools when they are directly callable.

## Wired Runtime Blocks

| Block | Endpoint evidence | Observed runtime state | Frontend state |
| --- | --- | --- | --- |
| Primary snapshot and KPI strip | `/ui/home/snapshot`, `/api/dashboard/core_metrics`, `/api/bond-dashboard/headline-kpis`, `/api/bond-analytics/portfolio-headlines` | HTTP 200. Snapshot is analytical `ok`; bond headline and portfolio headline are formal `ok`. | Ready |
| Key risk strip | `/api/bond-dashboard/risk-indicators`, `/ui/market-data/rates` | HTTP 200. Market-rates response has 76 rows. | Ready |
| Holdings table | `/api/bond-analytics/top-holdings?top_n=8` | HTTP 200. Response has 8 rows. | Ready |
| Position change TOP5 | `/api/bond-analytics/position-changes?top_n=5` | HTTP 200. `source_status=ready`; response has 5 rows. | Ready |
| Asset distribution | `/api/bond-dashboard/asset-structure?group_by=bond_type` | HTTP 200. Response has 11 rows. | Ready |
| Rating distribution | `/api/bond-dashboard/asset-structure?group_by=rating` | HTTP 200. Response has 5 rows. | Ready |
| Maturity distribution | `/api/bond-dashboard/maturity-structure` | HTTP 200. Response has 7 rows. | Ready |
| Industry distribution | `/api/bond-dashboard/industry-distribution?top_n=10` | HTTP 200. Response has 10 rows. | Ready |
| Risk exposure | `/api/bond-dashboard/risk-indicators` | HTTP 200. DV01, duration, credit ratio, convexity, and spread DV01 are available. | Ready |
| Research report list | `/ui/home/research-reports?limit=5` | HTTP 200. `source_status=ready`; response has 5 rows. | Ready, analytical source |
| Recent income trend | `/ui/home/income-trend?window=7` | HTTP 200. Response quality is `warning`; `source_status=partial`; missing `benchmark_pnl` and `excess_pnl`. | Partial, explicit gap shown |
| Research calendar | `/ui/calendar/supply-auctions` | HTTP 200 for the endpoint. Current UI date window `2026-05-24` to `2026-06-14` has no visible events. | Empty state |
| AI decision rail alert support | `/ui/home/snapshot`, `/api/analysis/liabilities/cockpit-warnings` | HTTP 200. Snapshot drives conclusion; liability cockpit warnings are analytical `ok` with one alert event and no watch items. | Ready, analytical source |

## Backend Tickets

| Ticket | Needed endpoint or field | Required fields | Why frontend must not fake it |
| --- | --- | --- | --- |
| Income trend benchmark/excess | Extend `GET /ui/home/income-trend?report_date=&window=7` | Governed `benchmark_pnl` and `excess_pnl` for each trend point, plus source/status metadata | Portfolio PnL is now wired from product-category monthly data, but benchmark and excess PnL still have no governed source. |
| Leverage ratio | `GET /ui/home/leverage?report_date=` or a governed field on an existing risk endpoint | `leverage_ratio`, `numerator`, `denominator`, `caliber_label`, `report_date`, `source_status` | No existing bond-risk endpoint defines the official leverage ratio caliber. |
| Position change display unit | Extend `/api/bond-analytics/position-changes` only if the UI needs basis-point style deltas | Governed display unit for weight delta, for example `weight_delta_unit` and server-formatted display text | The current frontend displays existing fields only; it should not infer pp/bp semantics from raw numbers. |

## State Contract

- Ready: render the value, row, chart, or table with the backend `report_date`.
- Partial: render the available governed series and name the missing governed components.
- Empty: render a visible empty state for the requested date window.
- Loading: reserve the layout and show loading text instead of blank cards.
- Stale/fallback/error: keep the section visible and surface the backend source/status flag.

Current homepage state coverage:

| State | Visible examples |
| --- | --- |
| Ready | KPI strip, key risk strip, holdings table, asset/rating/maturity/risk blocks, position change TOP5, research reports |
| Partial | Recent income trend, missing benchmark and excess PnL |
| Empty | Research calendar for the current visible window |
| Analytical source | Snapshot, income trend, research reports, liability cockpit warnings |
| Formal source | Bond headline, portfolio headline, risk indicators, structure distributions |

## Visual Acceptance Notes

- Target style: dense fixed-income management cockpit with compact cards, visible table/chart internals, and no blank first-screen modules.
- Sidebar is excluded from the reference comparison.
- The latest checked screenshot is `docs/plans/artifacts/dashboard-home-visual-pass6-income-change.png`.
- Remaining visual gaps are backend-data-bound: benchmark/excess PnL, leverage ratio, and optional governed display units for position deltas.
- Until those governed fields exist, the frontend should keep explicit partial/gap states instead of synthesizing metrics for visual symmetry.
