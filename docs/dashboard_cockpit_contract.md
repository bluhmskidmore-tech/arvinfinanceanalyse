# Dashboard Cockpit Contract

## Scope

This contract applies to the `/` homepage cockpit only. It does not rewrite `/bond-analysis`, `/risk-tensor`, `/market-data`, `/pnl-attribution`, database schema, auth, scheduler, cache, or global SDK layers.

## Primary Read Model

- `/ui/home/snapshot` is the only primary source for the homepage report date, main judgment, governance status, and snapshot lineage.
- The cockpit view model must treat `snapshot.result.report_date` as the primary report date.
- The first screen may show less data when source evidence is missing; it must not fill gaps with demo, reserved, or stale figures.

## First-Screen Admission

| Section | Source | First screen status rule |
| --- | --- | --- |
| Main judgment | `/ui/home/snapshot.result.verdict` | `landed`; degraded to review/warning when snapshot is partial, mock, or quality is not ok. |
| Governance status | `/ui/home/snapshot.result_meta`, `domains_effective_date` | `landed`; always visible. |
| Market ticker | `/ui/macro/choice-series/latest` via market rates client | Show `trade_date`; same date is `landed`, non-same date is `stale` context only. |
| Core scale metrics | `/api/dashboard/core_metrics` | `supplemental` only when `result.report_date == snapshot.report_date`; otherwise `blocked`. |
| Daily changes | `/api/dashboard/daily-changes` | `supplemental` only when `result.report_date == snapshot.report_date`; otherwise `blocked`. |
| Bond headline KPIs | `/api/bond-dashboard/headline-kpis` | `supplemental` only when `result.report_date == snapshot.report_date`; otherwise `blocked`. |
| Portfolio headlines | `/api/bond-analytics/portfolio-headlines` | `supplemental` only when `result.report_date == snapshot.report_date`; otherwise `blocked`. |
| Calendar | `/ui/calendar/supply-auctions` | Context/downstream focus only; does not participate in the main judgment. |
| Risk overview / contribution / alerts live surfaces | excluded/reserved endpoints | `reserved`; must not be requested or rendered as normal first-screen conclusions. |

## Naming Boundaries

- "经营贡献拆解" in the cockpit is a scale/change context panel.
- It must not imply the same basis as the formal `/pnl-attribution` "损益归因" workflow.

## View Model

`DashboardCockpitVM` must expose:

- `reportDate`
- `sections`
- `firstScreenSections`
- `marketTicker`
- `metricRail`
- `analysisCards`
- `waterfall`
- `portfolioMix`
- `riskItems`
- `calendarItems`
- `watchRows`

Components render this view model. Components must not directly decide whether mismatched supplemental data is trusted.
