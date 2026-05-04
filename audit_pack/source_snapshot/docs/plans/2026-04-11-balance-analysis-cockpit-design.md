# Balance Analysis Cockpit Design

**Date:** 2026-04-11

**Scope:** Upgrade `/balance-analysis` from a first governed consumer into a dashboard-style workbench page with richer overview cards, pagination, CSV export, and clear drill-down boundaries.

## Audience

- Middle and back office management
- Researchers and portfolio analysts
- Formal-data consumers who need both visual overview and governance provenance

## Design Intent

The page should feel like a management cockpit rather than a plain data table. It must keep the current governed formal-data chain intact:

`formal facts -> governed overview/detail APIs -> workbench page`

The page should look dense and operational, but it must not hide provenance. `result_meta` remains visible.

## Page Structure

### 1. Top Status Band

The top band stays inside the existing workbench shell and adds:

- Page title: `资产负债分析`
- Current `report_date`
- Refresh status
- `刷新` action
- `导出` action
- Compact market strip on the right:
  - `10Y国债`
  - `10Y国开`
  - `DR007`
  - `AAA`

This row should read like a quick market context strip, not a full toolbar.

### 2. Filter Bar

Keep filters as a fixed horizontal row, not a modal workflow.

Default visible filters:

- 日期
- 组合
- 券种
- 信用等级
- 币种口径
- 更多筛选

`更多筛选` can hold:

- 久期桶
- 是否发行类
- 是否异常
- 期限区间

## Overview Card Zone

The first major visual block is a row of 6 to 8 KPI cards.

Recommended cards:

- 债券估值规模
- 浮动盈亏
- 加权到期收益率
- 加权久期
- 平均票息
- 信用利差中位数
- 逾期余额
- 异常预警数

Card style:

- Main number
- Small comparison text like `较上月`
- Optional light trend line

All values must come from governed overview payloads, not frontend-local calculations.

## Main Dashboard Body

The body is split into three dashboard rows.

### Row 1

- 债券资产结构
- 收益率与久期分布
- 信用等级分布

### Row 2

- 债券/组合汇总表现
- 利差分析
- 决策事项

### Row 3

- 期限结构
- 行业分布
- 风险指标 + 关键事件日历

This keeps the page visually close to the desired cockpit layout without forcing all information into one oversized chart zone.

## Table and Pagination

The main table uses the default grain:

- 单券 / 组合汇总

Not the most atomic position rows.

Initial columns:

- 组合名称
- 规模(亿)
- 收益率(%)
- 利差中位数(bp)
- 久期(年)
- 最大回撤(%)
- 变动比率
- 趋势

Pagination should be real backend pagination using `limit/offset`, not frontend-only slicing.

## Export

Phase 1 export behavior:

- Export current filtered summary table as CSV

Do not export a full dashboard data package yet.

CSV should include:

- Table-visible columns
- `report_date`
- `position_scope`
- `currency_basis`
- `source_version`
- `rule_version`

## Drill-down Boundary

This version keeps drill-down as an explicit next-step affordance, not a full second page.

Allowed in this slice:

- `查看明细` action placeholder
- row-level affordance for future drill-down

Not included yet:

- full second-layer single-position detail page

## Provenance

The page continues to expose governed provenance:

- overview `result_meta`
- detail `result_meta`

This is a deliberate product choice. The page is not only a dashboard; it is also a governed formal-data consumer.

## Implementation Direction

Recommended next implementation order:

1. richer overview header cards
2. paginated summary table
3. CSV export
4. chart blocks
5. decisions/calendar panels

## Non-Goals

- No frontend-side financial formulas
- No snapshot or preview reads on the page
- No hidden CNX semantics reintroduced without formal materialization support
- No second-page drill-down implementation in this slice
