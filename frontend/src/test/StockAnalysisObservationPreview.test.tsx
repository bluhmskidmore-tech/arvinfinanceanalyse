import { fireEvent, render, screen, within } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { StockAnalysisObservationPreview } from "../features/stock-analysis/components/StockAnalysisObservationPreview";
import type {
  FactorScreenCandidateItem,
  FactorScreenCandidatesPayload,
  MeanReversionCandidateItem,
  MeanReversionCandidatesPayload,
} from "../api/contracts";

const factorCandidate: FactorScreenCandidateItem = {
  rank: 1,
  stock_code: "600000.SH",
  stock_name: "Factor Alpha",
  sector_code: "801001",
  sector_name: "Banking",
  industry: "Commercial Bank",
  score: 0.8123,
  pe: 8.1,
  pb: 0.9,
  roe: 0.12,
  gross_margin: null,
  three_month_return: 0.08,
  twelve_month_return: 0.18,
  dividend_yield: 0.021,
};

const meanReversionCandidate: MeanReversionCandidateItem = {
  rank: 2,
  stock_code: "000002.SZ",
  stock_name: "Mean Beta",
  sector_code: "801002",
  sector_name: "Real Estate",
  close: 9.8,
  drawdown_20d: -0.126,
  drawdown_60d: -0.21,
  ma5: 9.7,
  ma10: 10.1,
  close_strength: 0.44,
  vol_ratio: 1.2,
  score: 0.76,
};

const factorPayload: FactorScreenCandidatesPayload = {
  as_of_date: "2026-04-29",
  formula_version: "rv_factor_screen_candidates_v1",
  market_state: "WARM",
  input_stock_count: 10,
  candidate_count: 1,
  coverage_note: "factor coverage ready",
  items: [factorCandidate],
};

const meanReversionPayload: MeanReversionCandidatesPayload = {
  as_of_date: "2026-04-29",
  formula_version: "rv_mean_reversion_candidates_v1",
  market_state: "WARM",
  input_stock_count: 10,
  candidate_count: 1,
  excluded_stock_count: 0,
  insufficient_history_count: 0,
  items: [meanReversionCandidate],
};

describe("StockAnalysisObservationPreview", () => {
  it("keeps factor and mean-reversion empty states explicit", () => {
    render(
      <StockAnalysisObservationPreview
        factorScreenPayload={undefined}
        factorPreviewItems={[]}
        factorScreenCoverageNote={null}
        meanReversionMarketActive={false}
        meanReversionPayload={undefined}
        meanReversionPreviewItems={[]}
        onOpenFactorDetail={vi.fn()}
        onOpenMeanReversionDetail={vi.fn()}
      />,
    );

    expect(screen.getByTestId("stock-analysis-factor-preview-empty")).toHaveTextContent("待返回");
    expect(screen.getByTestId("stock-analysis-mean-reversion-preview-empty")).toHaveTextContent("暂停");
    expect(screen.getByTestId("stock-analysis-observation-preview")).toHaveTextContent("超跌 暂停");
  });

  it("opens factor and mean-reversion candidate details from preview rows", () => {
    const onOpenFactorDetail = vi.fn();
    const onOpenMeanReversionDetail = vi.fn();

    render(
      <StockAnalysisObservationPreview
        factorScreenPayload={factorPayload}
        factorPreviewItems={[factorCandidate]}
        factorScreenCoverageNote="factor coverage ready"
        meanReversionMarketActive
        meanReversionPayload={meanReversionPayload}
        meanReversionPreviewItems={[meanReversionCandidate]}
        onOpenFactorDetail={onOpenFactorDetail}
        onOpenMeanReversionDetail={onOpenMeanReversionDetail}
      />,
    );

    const factorRow = screen.getByTestId("factor-preview-row-600000.SH");
    fireEvent.click(within(factorRow).getByRole("button", { name: "查看Factor Alpha（600000.SH）详情" }));
    expect(onOpenFactorDetail).toHaveBeenCalledTimes(1);
    expect(onOpenFactorDetail).toHaveBeenCalledWith(factorCandidate);

    const meanReversionRow = screen.getByTestId("mean-reversion-preview-row-000002.SZ");
    expect(meanReversionRow).toHaveTextContent("Mean Beta");
    expect(screen.getByText("factor coverage ready")).toBeInTheDocument();

    fireEvent.keyDown(meanReversionRow, { key: "Enter" });
    expect(onOpenMeanReversionDetail).toHaveBeenCalledWith(meanReversionCandidate);
  });
});
