import { describe, expect, it } from "vitest";

import type { ProductCategoryPnlPayload, ProductCategoryPnlRow } from "../../../api/contracts";
import { buildMockProductCategoryPnlEnvelope } from "../../../mocks/productCategoryPnl";
import {
  buildProductCategoryLiabilitySideTrendSurface,
  buildProductCategoryTrendSnapshot,
  selectProductCategoryOperatingActionBacktestSurface,
  selectProductCategoryScenarioSensitivitySurface,
} from "./productCategoryPnlPageModel";

const base = buildMockProductCategoryPnlEnvelope({ reportDate: "2026-08-31", view: "monthly" }).result;

function row(categoryId: string, overrides: Partial<ProductCategoryPnlRow>): ProductCategoryPnlRow {
  return {
    ...base.rows[0], category_id: categoryId, category_name: categoryId,
    side: "asset", children: [], is_total: false, ...overrides,
  };
}

function backtestPayload(reportDate: string, next: boolean): ProductCategoryPnlPayload {
  return {
    ...base, report_date: reportDate, scenario_rate_pct: null,
    rows: [
      row("repo_assets", {
        report_date: reportDate, cnx_scale: "10000000000", weighted_yield: "0.5",
        business_net_income: next ? "-4547983.89862751" : "-5040602.96507507",
      }),
      row("rate_watch", {
        report_date: reportDate, cnx_scale: "20000000000", business_net_income: "20000000",
        weighted_yield: next ? "1.234" : "1.231",
      }),
      row("growth", {
        report_date: reportDate, weighted_yield: "3", business_net_income: "10000000",
        cnx_scale: next ? "1000400000" : "1000100000",
      }),
    ],
  };
}

describe("product-category calculation precision", () => {
  it("judges sub-million income and scale improvements and sub-bp yield improvements before formatting", () => {
    const result = selectProductCategoryOperatingActionBacktestSurface({
      payloads: [backtestPayload("2026-07-31", false), backtestPayload("2026-08-31", true)],
    });
    const income = result.examples.find(item => item.categoryId === "repo_assets")!;
    const rate = result.examples.find(item => item.categoryId === "rate_watch")!;
    const growth = result.examples.find(item => item.categoryId === "growth")!;

    expect(income.outcomeLabel).toBe("命中");
    expect(income.netIncomeDelta).toBeCloseTo(0.0049261906644756, 12);
    expect(income.netIncomeDeltaLabel).toBe("+0.00");
    expect(rate.outcomeLabel).toBe("命中");
    expect(rate.yieldDeltaBp).toBeCloseTo(0.3, 12);
    expect(rate.yieldDeltaBpLabel).toBe("+0.3 bp");
    expect(growth.outcomeLabel).toBe("命中");
    expect(growth.scaleDelta).toBeCloseTo(0.003, 12);
  });

  it("keeps missing next-period yields unjudged instead of treating them as zero", () => {
    const next = backtestPayload("2026-08-31", true);
    next.rows = next.rows.map(item => item.category_id === "rate_watch" ? { ...item, weighted_yield: null } : item);
    const result = selectProductCategoryOperatingActionBacktestSurface({
      payloads: [backtestPayload("2026-07-31", false), next],
    });
    expect(result.examples.find(item => item.categoryId === "rate_watch")).toMatchObject({
      outcomeLabel: "待判定", yieldDeltaBp: null,
    });
  });

  it("subtracts raw scenario values for totals and product comparisons", () => {
    const baseline = {
      ...base, grand_total: { ...base.grand_total, business_net_income: "708926044.12570324" },
      rows: [row("sample", { business_net_income: "708926044.12570324" })],
    };
    const scenario = {
      ...baseline, scenario_rate_pct: "1.50",
      grand_total: { ...baseline.grand_total, business_net_income: "727442367.869721787500" },
      rows: [row("sample", { business_net_income: "727442367.869721787500" })],
    };
    const result = selectProductCategoryScenarioSensitivitySurface({ baseline, scenarios: [scenario] });

    expect(result.rows[0].grandDelta).toBeCloseTo(0.1851632374401855, 12);
    expect(result.rows[0].grandDeltaLabel).toBe("+0.19");
    expect(result.rows[0].topMoverDeltaLabel).toBe("+0.19");
    expect(result.comparisonRows[0].cells[0].deltaLabel).toBe("+0.19");
  });

  it("does not classify a nonzero scenario difference as an exact breakeven", () => {
    const baseline = { ...base, grand_total: { ...base.grand_total, business_net_income: "100010000" } };
    const scenario = {
      ...baseline, scenario_rate_pct: "1.50",
      grand_total: { ...baseline.grand_total, business_net_income: "100040000" },
    };
    const result = selectProductCategoryScenarioSensitivitySurface({ baseline, scenarios: [scenario] });

    expect(result.rows[0].grandDelta).toBeGreaterThan(0);
    expect(result.pressureSummary.breakeven.detailLabel).not.toContain("与正式基线持平");
  });

  it("calculates liability amount and bp changes from raw values in all currency matrices", () => {
    const snapshots = [
      { reportDate: "2026-07-31", scale: "-149490000", foreignScale: "149490000", rate: "1.23101" },
      { reportDate: "2026-08-31", scale: "-150510000", foreignScale: "150510000", rate: "1.23399" },
    ].map(({ reportDate, scale, foreignScale, rate }) => {
      const liability = row("liability_total", {
        side: "liability", is_total: true, report_date: reportDate,
        cnx_scale: scale, cny_scale: scale, foreign_scale: foreignScale, weighted_yield: rate,
      });
      return buildProductCategoryTrendSnapshot({ ...base, report_date: reportDate, liability_total: liability, rows: [liability] });
    });
    const result = buildProductCategoryLiabilitySideTrendSurface(snapshots);

    expect(result.totalReadout).toMatchObject({ amountDeltaLabel: "+0.01", rateDeltaLabel: "+0.3 bp" });
    expect(result.detailMatrix.rows[0].movement).toEqual({ amountLabel: "+0.01", rateLabel: "+0.3 bp" });
    expect(result.detailMatrix.currencyMatrices[0].rows[0].movement).toEqual({ amountLabel: "+0.01", rateLabel: "+0.3 bp" });
    expect(result.detailMatrix.currencyMatrices[1].rows[0].movement).toEqual({ amountLabel: "-0.01", rateLabel: "+0.3 bp" });
  });
});
