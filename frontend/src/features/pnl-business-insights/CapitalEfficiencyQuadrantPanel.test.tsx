import { render } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import type { PnlByBusinessScaleYieldQuadrantSummary } from "../../api/contracts";
import { CapitalEfficiencyQuadrantPanel } from "./CapitalEfficiencyQuadrantPanel";

function summary(
  overrides: Partial<PnlByBusinessScaleYieldQuadrantSummary> = {},
): PnlByBusinessScaleYieldQuadrantSummary {
  return {
    year: 2026,
    as_of_date: "2026-06-30",
    currency_basis: "CNY_EQUIVALENT",
    scale_basis: "YTD_AVG_BALANCE_SHARE",
    yield_basis: "FTP_NET_ANNUALIZED_YIELD_PCT",
    minimum_eligible_rows: 6,
    eligible_row_count: 6,
    total_avg_balance: "1000.00",
    available: true,
    scale_share_median_pct: "15.00",
    ftp_net_annualized_yield_median_pct: "1.500000",
    rows: [
      {
        row_key: "a",
        business_type: "业务A",
        avg_balance: "300.00",
        scale_share_pct: "30.00",
        ftp_net_annualized_yield_pct: "2.000000",
        quadrant_key: "LARGE_HIGH",
      },
      {
        row_key: "b",
        business_type: "业务B",
        avg_balance: "250.00",
        scale_share_pct: "25.00",
        ftp_net_annualized_yield_pct: "1.000000",
        quadrant_key: "LARGE_LOW",
      },
      {
        row_key: "c",
        business_type: "业务C",
        avg_balance: "100.00",
        scale_share_pct: "10.00",
        ftp_net_annualized_yield_pct: "1.800000",
        quadrant_key: "SMALL_HIGH",
      },
      {
        row_key: "d",
        business_type: "业务D",
        avg_balance: "50.00",
        scale_share_pct: "5.00",
        ftp_net_annualized_yield_pct: "0.800000",
        quadrant_key: "SMALL_LOW",
      },
    ],
    ...overrides,
  };
}

describe("CapitalEfficiencyQuadrantPanel", () => {
  it("renders the four backend-classified relative quadrants without browser recalculation", () => {
    const { getByTestId } = render(<CapitalEfficiencyQuadrantPanel summary={summary()} />);

    expect(getByTestId("capital-efficiency-quadrant-large_high")).toHaveTextContent("业务A");
    expect(getByTestId("capital-efficiency-quadrant-large_high")).toHaveTextContent("核心收益观察");
    expect(getByTestId("capital-efficiency-quadrant-large_low")).toHaveTextContent("业务B");
    expect(getByTestId("capital-efficiency-quadrant-large_low")).toHaveTextContent("优先核查收益成因");
    expect(getByTestId("capital-efficiency-quadrant-small_high")).toHaveTextContent("业务C");
    expect(getByTestId("capital-efficiency-quadrant-small_low")).toHaveTextContent("业务D");
    expect(getByTestId("capital-efficiency-quadrant-note")).toHaveTextContent("日均余额份额中位数 15.00%");
    expect(getByTestId("capital-efficiency-quadrant-note")).toHaveTextContent("FTP后年化收益率中位数 1.50%");
    expect(getByTestId("capital-efficiency-quadrant-panel")).not.toHaveTextContent("增配");
    expect(getByTestId("capital-efficiency-quadrant-panel")).not.toHaveTextContent("压降");
  });

  it("keeps backend precision but formats the displayed yield median to two decimals", () => {
    const { getByTestId } = render(
      <CapitalEfficiencyQuadrantPanel
        summary={summary({ ftp_net_annualized_yield_median_pct: "1.036546" })}
      />,
    );

    expect(getByTestId("capital-efficiency-quadrant-note")).toHaveTextContent(
      "FTP后年化收益率中位数 1.04%",
    );
    expect(getByTestId("capital-efficiency-quadrant-note")).not.toHaveTextContent("1.036546%");
  });

  it("fails closed when fewer than six eligible parent rows are available", () => {
    const { getByTestId, queryByTestId } = render(
      <CapitalEfficiencyQuadrantPanel
        summary={summary({
          available: false,
          eligible_row_count: 5,
          scale_share_median_pct: null,
          ftp_net_annualized_yield_median_pct: null,
          rows: [],
        })}
      />,
    );

    expect(getByTestId("capital-efficiency-quadrant-empty")).toHaveTextContent("有效父级业务 5 个");
    expect(getByTestId("capital-efficiency-quadrant-empty")).toHaveTextContent("至少需要 6 个");
    expect(queryByTestId("capital-efficiency-quadrant-grid")).toBeNull();
  });
});
