---
name: moss-fixed-income-portfolio
description: "【MOSS固收组合】用于债券仪表盘、持仓、收益率曲线、久期、DV01、利差、现金流和风险张量工作。"
---

# MOSS Fixed-Income Portfolio

Use this skill for MOSS fixed-income pages and analytics. It adapts fixed-income portfolio, bond relative value, and rates workflow patterns, but must use MOSS-approved data sources and contracts rather than assuming LSEG/S&P/FactSet access.

## Source Priority

1. MOSS contracts, lineage, data catalog, and existing tests.
2. Internal sources under `data_input/`, DuckDB materializations, repositories, and governed API results.
3. Approved external adapters already present in MOSS, such as Choice or AkShare boundaries.
4. Vendor MCPs only when configured and explicitly relevant; never invent missing vendor data.

## Portfolio Analytics Checklist

For portfolio-level metrics, confirm the weighting basis before computing or displaying:

- market value weighted yield, duration, convexity, spread, or rating
- position/notional weighted exposure where contract says so
- DV01 aggregation as additive currency amount
- key-rate duration and scenario P&L by bucket when available
- cashflow waterfall by coupon, principal, maturity, and reinvestment period

## Relative Value Checklist

For bond, curve, or spread pages:

1. Identify instrument universe, benchmark curve, credit/rating/sector grouping, and report date.
2. Keep spread metrics explicit: G-spread, Z-spread, OAS, credit spread, residual spread, bp units.
3. Separate rates movement, credit movement, carry/roll-down, FX, and data-quality effects.
4. Preserve callable/embedded-option semantics; do not treat OAS and nominal spread as interchangeable.
5. Validate scenario shocks and basis labels before presenting rich/cheap or risk conclusions.

## MOSS Page Discipline

Visible fixed-income outputs must surface no data, stale data, fallback date, loading failure, and metric-definition gaps. When changing pages, trace endpoint to adapter to state/view model to chart/table and run the narrowest relevant tests plus browser verification for visible behavior.
