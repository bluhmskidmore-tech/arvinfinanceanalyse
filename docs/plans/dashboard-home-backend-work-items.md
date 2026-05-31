# Dashboard Home Backend Work Items

Scope: `经营驾驶舱首页` content area only. Sidebar and global shell are out of scope.

Existing endpoints now wired by the frontend:

| Block | Endpoint | Frontend use |
| --- | --- | --- |
| KPI strip | `/ui/home/snapshot`, `/api/bond-dashboard/headline-kpis`, `/api/bond-analytics/portfolio-headlines` | Display only, date-gated by report date |
| Key risk strip | `/ui/macro/choice-series/latest`, `/api/bond-dashboard/risk-indicators` | Supplemental risk/market ticker |
| Holdings table | `/api/bond-analytics/top-holdings` | Top holdings table |
| Position change TOP5 | `/api/bond-analytics/position-changes` | Adjacent report-date position change list |
| Rating distribution | `/api/bond-dashboard/asset-structure?group_by=rating` | Rating distribution chart |
| Maturity distribution | `/api/bond-dashboard/maturity-structure` | Maturity distribution chart |
| Industry distribution | `/api/bond-dashboard/industry-distribution` | Industry market-value distribution |
| Risk exposure | `/api/bond-dashboard/risk-indicators` | DV01, duration, credit ratio, convexity, spread DV01 |
| Research report list | `/ui/home/research-reports` | `fact_news_event` rows with `source_kind=research` |
| Recent income trend | `/ui/home/income-trend` | Monthly `grand_total.business_net_income` from `product_category_pnl_formal_read_model`; response is `partial` while benchmark/excess PnL are unavailable |
| Research calendar | existing research calendar feed | Supply / auction calendar only |

Backend tickets for missing reference blocks:

| Ticket | Needed endpoint | Required fields | Why frontend must not fake it |
| --- | --- | --- | --- |
| Income trend benchmark/excess | `GET /ui/home/income-trend?report_date=&window=7d` | governed `benchmark_pnl` and `excess_pnl` fields for each trend point | Portfolio PnL is now wired from product-category monthly data, but benchmark/excess PnL still have no governed source. |
| Leverage ratio | `GET /ui/home/leverage?report_date=` | `leverage_ratio`, `numerator`, `denominator`, `caliber_label`, `source_status` | No existing bond-risk endpoint defines the official leverage ratio caliber. |

Acceptance notes:

- Every response should include `report_date` and a source/status flag so the page can mark `ready`, `empty`, `loading`, `stale`, or `error`.
- Frontend should keep rendering backend work-item cards for missing components until governed fields exist.
- Metric definitions and units must be confirmed server-side before replacing the gap cards.
