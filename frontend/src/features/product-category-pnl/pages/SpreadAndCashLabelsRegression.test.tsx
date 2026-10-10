import { createRef } from "react";
import { render, screen, within } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import type {
  ProductCategoryAttributionPayload,
  ProductCategoryAttributionRow,
  ProductCategoryMetricValue,
  ProductCategoryPnlRow,
} from "../../../api/contracts";
import { ProductCategoryAttributionPanel } from "./ProductCategoryAttributionPanels";
import { ProductCategoryInterestSpreadAttributionPanel } from "./ProductCategoryComparisonChartPanels";
import {
  selectProductCategoryInterestSpreadAttributionSurface,
  type ProductCategoryInterestSpreadBasis,
  type ProductCategoryTrendSnapshot,
} from "./productCategoryPnlPageModel";

function pnlRow(categoryId: string, reportDate: string): ProductCategoryPnlRow {
  return {
    category_id: categoryId,
    category_name: categoryId,
    side: categoryId === "liability_total" ? "liability" : "asset",
    level: 0,
    view: "monthly",
    report_date: reportDate,
    baseline_ftp_rate_pct: "0",
    cnx_scale: "100000000",
    cny_scale: "100000000",
    foreign_scale: "0",
    cnx_cash: "225000000",
    cny_cash: "225000000",
    foreign_cash: "0",
    cny_ftp: "0",
    foreign_ftp: "0",
    cny_net: "225000000",
    foreign_net: "0",
    business_net_income: "225000000",
    weighted_yield: "99",
    is_total: true,
    children: [],
  };
}

function percentMetric(value: number): ProductCategoryMetricValue {
  return { raw: String(value), display: `${value.toFixed(2)}%`, unit: "percent" };
}

function snapshot(
  reportDate: string,
  assetYield: number,
  liabilityCost: number,
  spread: number,
): ProductCategoryTrendSnapshot {
  return {
    reportDate,
    view: "monthly",
    rows: [],
    assetTotal: pnlRow("asset_total", reportDate),
    liabilityTotal: pnlRow("liability_total", reportDate),
    interestSpread: {
      all_currency_asset_yield_pct: percentMetric(assetYield),
      all_currency_liability_yield_pct: percentMetric(liabilityCost),
      all_currency_spread_pct: percentMetric(spread),
      cny_asset_yield_pct: percentMetric(assetYield),
      cny_liability_yield_pct: percentMetric(liabilityCost),
      cny_spread_pct: percentMetric(spread),
    },
  };
}

function spreadSurface(basis: ProductCategoryInterestSpreadBasis = "weighted") {
  return selectProductCategoryInterestSpreadAttributionSurface(
    [snapshot("2025-03-31", 3, 2, 1), snapshot("2026-03-31", 4, 1, 3)],
    { basis, month: 3 },
    2026,
  );
}

function attributionPayload(): ProductCategoryAttributionPayload {
  const row: ProductCategoryAttributionRow = {
    category_id: "tpl_assets",
    category_name: "TPL资产",
    side: "asset",
    level: 0,
    state: "complete",
    current: {
      report_date: "2026-03-31",
      days: 31,
      scale: "100000000",
      yield_pct: "4",
      cash: "225000000",
      ftp: "25000000",
      business_net_income: "200000000",
    },
    prior: {
      report_date: "2025-03-31",
      days: 31,
      scale: "100000000",
      yield_pct: "3",
      cash: "150000000",
      ftp: "25000000",
      business_net_income: "125000000",
    },
    effects: {
      day_effect: "0",
      scale_effect: "0",
      rate_effect: "0",
      ftp_effect: "0",
      direct_effect: "75000000",
      unexplained_effect: "0",
      explained_effect: "75000000",
      delta_business_net_income: "75000000",
      closure_error: "0",
    },
  };
  return {
    report_date: "2026-03-31",
    compare: "yoy",
    current_report_date: "2026-03-31",
    prior_report_date: "2025-03-31",
    state: "complete",
    reason: null,
    rows: [row],
    totals: null,
  };
}

describe("interest spread field changes and cash labels", () => {
  it.each<ProductCategoryInterestSpreadBasis>(["weighted", "cny"])(
    "shows a falling liability cost as a negative field change for %s",
    (basis) => {
      const surface = spreadSurface(basis);
      const cost = surface.rows.find((row) => row.key === "liability_cost");

      expect(cost).toMatchObject({
        priorValue: 2,
        currentValue: 1,
        deltaBp: -100,
        contributionLabel: "-100.0 bp",
      });
      expect(surface.summary.assetContributionBp).toBe(100);
      expect(surface.summary.spreadDeltaBp).toBe(200);
      expect(
        surface.summary.assetContributionBp! -
          surface.summary.liabilityContributionBp!,
      ).toBe(surface.summary.spreadDeltaBp);
    },
  );

  it("keeps the spread change anchored to the backend spread field", () => {
    const surface = selectProductCategoryInterestSpreadAttributionSurface(
      [snapshot("2025-03-31", 3, 2, 1), snapshot("2026-03-31", 4, 1, 2.75)],
      { basis: "weighted", month: 3 },
      2026,
    );

    expect(surface.summary.spreadDeltaBp).toBe(175);
  });

  it("labels spread detail cash as income or expense before FTP and keeps yuan conversion", () => {
    render(<ProductCategoryInterestSpreadAttributionPanel surface={spreadSurface()} />);

    const panel = screen.getByTestId("product-category-interest-spread-attribution");
    expect(within(panel).getAllByText("收入/支出（FTP前） 2.25亿元")).toHaveLength(4);
    expect(within(panel).queryByText(/利息收支/)).not.toBeInTheDocument();
  });

  it("labels attribution cash evidence without narrowing it to interest", () => {
    render(
      <ProductCategoryAttributionPanel
        selectedView="monthly"
        compare="yoy"
        payload={attributionPayload()}
        isLoading={false}
        isError={false}
        detailsOpen
        detailsRef={createRef<HTMLDetailsElement>()}
        selectedDetailCategoryId="tpl_assets"
        onCompareChange={vi.fn()}
        onDetailsOpenChange={vi.fn()}
        onLocateFormalRow={vi.fn()}
        onSelectDetailCategory={vi.fn()}
        onRetry={vi.fn()}
      />,
    );

    const evidence = screen.getByTestId("product-category-attribution-selected-full-evidence");
    const currentLabel = within(evidence).getByText("本期收入/支出（FTP前）");
    const priorLabel = within(evidence).getByText("对比期收入/支出（FTP前）");
    expect(currentLabel.parentElement).toHaveTextContent("2.25");
    expect(priorLabel.parentElement).toHaveTextContent("1.50");
    expect(within(evidence).queryByText(/利息收支/)).not.toBeInTheDocument();
  });
});
