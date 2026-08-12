import { render, screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import type { StockHeavyweightTrendsPayload } from "../../../api/contracts";
import { buildHeavyweightTrendIndex } from "../lib/stockHeavyweightTrendView";
import type {
  StockSectorHeavyweightPreviewSummary,
  StockSectorHeavyweightStockPreview,
} from "../lib/stockAnalysisPageModel";
import { StockAnalysisDeepSelectionOverview } from "./StockAnalysisDeepSelectionOverview";

function previewStock(
  code: string,
  name: string,
  overrides: Partial<StockSectorHeavyweightStockPreview> = {},
): StockSectorHeavyweightStockPreview {
  return {
    stockCode: code,
    stockName: name,
    pctChange: "+2.10%",
    turn: "3.20",
    closeStrength: "0.80",
    sourceLabel: "板块成分",
    detailSource: "sector_constituent",
    ...overrides,
  };
}

const preview: StockSectorHeavyweightPreviewSummary = {
  sectorLimit: 8,
  sectorsWithSamples: 1,
  totalSampleCount: 3,
  uncoveredSectorCount: 0,
  rows: [
    {
      sectorCode: "801001",
      sectorName: "电子",
      sectorRank: 1,
      sectorPctChange: "+3.10%",
      sectorScore: "0.92",
      stocks: [
        previewStock("000001.SZ", "阿尔法"),
        previewStock("000002.SZ", "贝塔"),
        previewStock("000003.SZ", "伽马"),
      ],
    },
  ],
};

const trendPayload: StockHeavyweightTrendsPayload = {
  basis: "analytical",
  state: "ok",
  contract_status: "observational_only",
  formal_use_allowed: false,
  requested_as_of_date: null,
  as_of_date: "2026-08-11",
  window_days: 20,
  sector_limit: 8,
  stocks_per_sector: 3,
  series_basis: "cum_pct_from_first_close",
  window_trade_dates: ["2026-07-15", "2026-08-10", "2026-08-11"],
  sectors: [
    {
      sector_code: "801001",
      sector_name: "电子",
      sector_rank: 1,
      stocks: [
        {
          rank: 1,
          stock_code: "000001.SZ",
          stock_name: "阿尔法",
          pctchange: 2.1,
          turn: 3.2,
          trade_dates: ["2026-07-15", "2026-08-10", "2026-08-11"],
          close_values: [10, 11, 12],
          cum_pct_changes: [0, 10, 20],
          point_count: 3,
          missing_point_count: 0,
          trend_state: "ok",
          trend_note: null,
          window_return_pct: 20,
        },
        {
          rank: 2,
          stock_code: "000002.SZ",
          stock_name: "贝塔",
          pctchange: -1.2,
          turn: 2.4,
          trade_dates: ["2026-07-15", "2026-08-11"],
          close_values: [20, 18],
          cum_pct_changes: [0, -10],
          point_count: 2,
          missing_point_count: 1,
          trend_state: "partial",
          trend_note: "missing_1_sessions",
          window_return_pct: -10,
        },
        {
          rank: 3,
          stock_code: "000003.SZ",
          stock_name: "伽马",
          pctchange: 0,
          turn: 1.1,
          trade_dates: [],
          close_values: [],
          cum_pct_changes: [],
          point_count: 0,
          missing_point_count: 3,
          trend_state: "missing",
          trend_note: "no_tradable_close_in_window",
          window_return_pct: null,
        },
      ],
    },
  ],
  coverage: {
    sector_count: 1,
    stock_count: 3,
    stock_with_series_count: 2,
    stock_missing_series_count: 1,
    window_trade_date_count: 3,
  },
  metric_notes: [],
  warnings: [],
};

function renderOverview(trends: StockHeavyweightTrendsPayload | null) {
  return render(
    <StockAnalysisDeepSelectionOverview
      themeBreakoutCount={0}
      themeLeaderPreviewItems={[]}
      themeBreakoutUnsupported={false}
      themeBreakoutBlockerLabel={null}
      themeBreakoutBlockerText={null}
      sectorHeavyweightPreview={preview}
      sectorHeavyweightRows={preview.rows}
      heavyweightTrends={buildHeavyweightTrendIndex(trends)}
      strategyPayload={null}
      setDetailSelection={() => {}}
    />,
  );
}

describe("StockAnalysisDeepSelectionOverview heavyweight trends", () => {
  it("renders all three heavyweight stocks per sector card", () => {
    renderOverview(trendPayload);

    const card = screen.getByTestId("sector-heavyweight-card-801001");
    expect(within(card).getByTestId("sector-heavyweight-row-801001-000001.SZ")).toBeInTheDocument();
    expect(within(card).getByTestId("sector-heavyweight-row-801001-000002.SZ")).toBeInTheDocument();
    expect(within(card).getByTestId("sector-heavyweight-row-801001-000003.SZ")).toBeInTheDocument();
  });

  it("draws a sparkline only for stocks with a plottable series and tones it by direction", () => {
    renderOverview(trendPayload);

    const up = within(screen.getByTestId("sector-heavyweight-row-801001-000001.SZ"));
    const upSpark = up.getByTestId("sector-heavyweight-sparkline");
    expect(upSpark).toHaveAttribute("data-tone", "positive");
    expect(up.getByText("+20.0%")).toBeInTheDocument();

    const down = within(screen.getByTestId("sector-heavyweight-row-801001-000002.SZ"));
    expect(down.getByTestId("sector-heavyweight-sparkline")).toHaveAttribute(
      "data-tone",
      "negative",
    );
    expect(down.getByText("-10.0%")).toBeInTheDocument();

    expect(screen.getAllByTestId("sector-heavyweight-sparkline")).toHaveLength(2);
  });

  it("degrades quietly when a stock has no series: no sparkline, reason in the row title", () => {
    renderOverview(trendPayload);

    const row = screen.getByTestId("sector-heavyweight-row-801001-000003.SZ");
    expect(within(row).queryByTestId("sector-heavyweight-sparkline")).not.toBeInTheDocument();
    expect(row).toHaveAttribute("title", expect.stringContaining("无可交易收盘价"));
    // the row itself still renders its snapshot metrics
    expect(row).toHaveTextContent("伽马");
    expect(screen.getByTestId("sector-heavyweight-card-801001")).toBeInTheDocument();
  });

  it("renders the card without sparklines when the trend request has not resolved", () => {
    renderOverview(null);

    expect(screen.getByTestId("sector-heavyweight-row-801001-000001.SZ")).toBeInTheDocument();
    expect(screen.queryAllByTestId("sector-heavyweight-sparkline")).toHaveLength(0);
  });
});
