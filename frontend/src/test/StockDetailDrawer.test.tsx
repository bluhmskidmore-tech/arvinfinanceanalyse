import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { AppProviders } from "../app/providers";
import { createApiClient } from "../api/client";
import type { ApiEnvelope, LivermoreCandidateHistoryRow, LivermoreStockDetailPayload } from "../api/contracts";
import { buildMockApiEnvelope } from "../mocks/mockApiEnvelope";
import { StockDetailDrawer } from "../features/stock-analysis/components/StockDetailDrawer";

vi.mock("../components/charts/BaseChart", () => ({
  BaseChart: function MockBaseChart() {
    return <div data-testid="stock-detail-chart-canvas-stub" />;
  },
}));

function buildStockDetailEnvelope(overrides: { factor?: { pe: number | null } } = {}): ApiEnvelope<LivermoreStockDetailPayload> {
  return buildMockApiEnvelope(
    "market_data.livermore.stock_detail",
    {
      basis: "analytical",
      state: "ok",
      stock_code: "000001.SZ",
      requested_as_of_date: "2026-04-29",
      as_of_date: "2026-04-29",
      lookback: 60,
      candles: [
        {
          trade_date: "2026-04-26",
          open_value: 10,
          high_value: 10.5,
          low_value: 9.9,
          close_value: 10.3,
          volume: 1e6,
          amount: 1e7,
        },
      ],
      factor: {
        as_of_date: "2026-04-29",
        pe: overrides.factor?.pe ?? 9.7,
        pb: 1.2,
        roe: 0.1,
        dividend_yield: 0.015,
      },
    },
    {
      basis: "analytical",
      source_version: "sv_test",
      rule_version: "rv_test",
      quality_flag: "ok",
      vendor_status: "ok",
    },
  );
}

function buildCandidateHistoryEnvelope(items: LivermoreCandidateHistoryRow[]) {
  return buildMockApiEnvelope(
    "market_data.livermore.candidate_history",
    {
      stock_code: "000001.SZ",
      snapshot_from: null,
      snapshot_to: null,
      limit: 10,
      items,
    },
    {
      basis: "analytical",
      source_version: "sv_hist_test",
      vendor_version: "vv_hist_test",
      rule_version: "rv_livermore_candidate_history_v1",
      cache_version: "cv_livermore_candidate_history_v1",
      quality_flag: "ok",
      vendor_status: "ok",
    },
  );
}

describe("StockDetailDrawer", () => {
  it("fetches stock detail and shows chart + factor grid", async () => {
    const client = createApiClient({ mode: "mock" });
    const spy = vi.spyOn(client, "getLivermoreStockDetail").mockResolvedValue(buildStockDetailEnvelope());
    const newsSpy = vi.spyOn(client, "getChoiceNewsEvents");

    render(
      <AppProviders client={client}>
        <StockDetailDrawer stockCode="000001.SZ" stockName="Alpha" asOfDate="2026-04-29" onClose={() => undefined} />
      </AppProviders>,
    );

    await waitFor(() => expect(spy).toHaveBeenCalled());

    expect(await screen.findByTestId("stock-detail-chart")).toBeInTheDocument();
    expect(screen.getByTestId("stock-detail-factors")).toBeInTheDocument();
    expect(screen.getByTestId("stock-detail-factor-pe")).toHaveTextContent("9.70");
    expect(screen.getByTestId("stock-detail-footer-meta")).toHaveTextContent("sv_test");
    await waitFor(() =>
      expect(newsSpy).toHaveBeenCalledWith({
        limit: 10,
        offset: 0,
        stockCode: "000001.SZ",
      }),
    );
    expect(screen.getByTestId("stock-detail-market-events-banner")).toHaveTextContent("按股票代码匹配");
  });

  it("shows the review context that opened the drawer", async () => {
    const client = createApiClient({ mode: "mock" });
    vi.spyOn(client, "getLivermoreStockDetail").mockResolvedValue(buildStockDetailEnvelope());

    render(
      <AppProviders client={client}>
        <StockDetailDrawer
          stockCode="000001.SZ"
          stockName="Alpha"
          asOfDate="2026-04-29"
          reviewContext={{
            sourceLabel: "复核队列",
            sectorName: "AI",
            reviewRank: 1,
            distanceToBreakoutPct: "0.46%",
          }}
          onClose={() => undefined}
        />
      </AppProviders>,
    );

    const context = await screen.findByTestId("stock-detail-review-context");
    expect(context).toHaveTextContent("复核队列");
    expect(context).toHaveTextContent("#1");
    expect(context).toHaveTextContent("AI");
    expect(context).toHaveTextContent("距观察位 0.46%");
  });

  it("renders market event rows from getChoiceNewsEvents", async () => {
    const client = createApiClient({ mode: "mock" });
    vi.spyOn(client, "getLivermoreStockDetail").mockResolvedValue(buildStockDetailEnvelope());
    vi.spyOn(client, "getChoiceNewsEvents").mockResolvedValue(
      buildMockApiEnvelope(
        "news.choice.latest",
        {
          total_rows: 2,
          limit: 10,
          offset: 0,
          events: [
            {
              event_key: "e1",
              received_at: "2026-05-08T09:30:00Z",
              group_id: "g1",
              content_type: "sectornews",
              serial_id: 1,
              request_id: 1,
              error_code: 0,
              error_msg: "",
              topic_code: "TOPIC_ONE",
              item_index: 0,
              payload_text: "Brief headline about macro conditions".repeat(3),
              payload_json: null,
            },
            {
              event_key: "e2",
              received_at: "2026-05-08T10:15:00Z",
              group_id: "g1",
              content_type: "sectornews",
              serial_id: 2,
              request_id: 1,
              error_code: 0,
              error_msg: "",
              topic_code: "TOPIC_TWO",
              item_index: 0,
              payload_text: "Second row body text",
              payload_json: null,
            },
          ],
        },
        { basis: "analytical", result_kind: "news.choice.latest" },
      ),
    );

    render(
      <AppProviders client={client}>
        <StockDetailDrawer stockCode="000001.SZ" asOfDate="2026-04-29" onClose={() => undefined} />
      </AppProviders>,
    );

    const list = await screen.findByTestId("stock-detail-market-events-list");
    expect(list.querySelectorAll("li")).toHaveLength(2);
    expect(screen.getByText("TOPIC_ONE")).toBeInTheDocument();
    expect(screen.getByText("TOPIC_TWO")).toBeInTheDocument();
    expect(screen.getByText(/Brief headline about macro conditions/)).toBeInTheDocument();
  });

  it("shows choice news error in isolation while chart and factors still render", async () => {
    const client = createApiClient({ mode: "mock" });
    vi.spyOn(client, "getLivermoreStockDetail").mockResolvedValue(buildStockDetailEnvelope());
    vi.spyOn(client, "getChoiceNewsEvents").mockRejectedValue(new Error("news feed unavailable"));

    render(
      <AppProviders client={client}>
        <StockDetailDrawer stockCode="000001.SZ" asOfDate="2026-04-29" onClose={() => undefined} />
      </AppProviders>,
    );

    expect(await screen.findByTestId("stock-detail-chart")).toBeInTheDocument();
    expect(screen.getByTestId("stock-detail-factors")).toBeInTheDocument();
    expect(await screen.findByTestId("stock-detail-market-events-error")).toHaveTextContent("news feed unavailable");
  });

  it("shows empty state when choice news returns no events", async () => {
    const client = createApiClient({ mode: "mock" });
    vi.spyOn(client, "getLivermoreStockDetail").mockResolvedValue(buildStockDetailEnvelope());
    vi.spyOn(client, "getChoiceNewsEvents").mockResolvedValue(
      buildMockApiEnvelope(
        "news.choice.latest",
        { total_rows: 0, limit: 10, offset: 0, events: [] },
        { basis: "analytical", result_kind: "news.choice.latest" },
      ),
    );

    render(
      <AppProviders client={client}>
        <StockDetailDrawer stockCode="000001.SZ" asOfDate="2026-04-29" onClose={() => undefined} />
      </AppProviders>,
    );

    expect(await screen.findByTestId("stock-detail-market-events-empty")).toHaveTextContent(
      "暂无与该股票代码匹配的市场事件",
    );
  });

  it("refetches when lookback segment changes", async () => {
    const user = userEvent.setup();
    const client = createApiClient({ mode: "mock" });
    const spy = vi.spyOn(client, "getLivermoreStockDetail").mockResolvedValue(buildStockDetailEnvelope());

    render(
      <AppProviders client={client}>
        <StockDetailDrawer stockCode="000001.SZ" asOfDate="2026-04-29" onClose={() => undefined} />
      </AppProviders>,
    );

    await waitFor(() => expect(spy).toHaveBeenCalled());

    const firstCalls = spy.mock.calls.length;
    const seg = await screen.findByText("120");
    await user.click(seg);

    await waitFor(() => expect(spy.mock.calls.length).toBeGreaterThan(firstCalls));
    const lastArg = spy.mock.calls[spy.mock.calls.length - 1]?.[0];
    expect(lastArg?.lookback).toBe(120);
  });

  it("shows 待补 for missing factor fields", async () => {
    const client = createApiClient({ mode: "mock" });
    vi.spyOn(client, "getLivermoreStockDetail").mockResolvedValue(
      buildMockApiEnvelope(
        "market_data.livermore.stock_detail",
        {
          basis: "analytical",
          state: "missing",
          stock_code: "000001.SZ",
          requested_as_of_date: null,
          as_of_date: "2026-04-29",
          lookback: 60,
          candles: [
            {
              trade_date: "2026-04-26",
              open_value: 10,
              high_value: 10,
              low_value: 10,
              close_value: 10,
              volume: 0,
              amount: 0,
            },
          ],
          factor: { as_of_date: null, pe: null, pb: null, roe: null, dividend_yield: null },
        },
        { basis: "analytical", quality_flag: "missing" },
      ),
    );

    render(
      <AppProviders client={client}>
        <StockDetailDrawer stockCode="000001.SZ" onClose={() => undefined} />
      </AppProviders>,
    );

    expect(await screen.findByTestId("stock-detail-factor-pe")).toHaveTextContent("待补");
  });

  it("shows error state without breaking drawer chrome", async () => {
    const client = createApiClient({ mode: "mock" });
    vi.spyOn(client, "getLivermoreStockDetail").mockRejectedValue(new Error("network down"));

    render(
      <AppProviders client={client}>
        <StockDetailDrawer stockCode="000001.SZ" onClose={() => undefined} />
      </AppProviders>,
    );

    expect(await screen.findByTestId("stock-detail-error")).toBeInTheDocument();
    expect(screen.getByTestId("stock-detail-error")).toHaveTextContent("network down");
  });

  it("close button calls onClose", async () => {
    const user = userEvent.setup();
    const onClose = vi.fn();
    const client = createApiClient({ mode: "mock" });
    vi.spyOn(client, "getLivermoreStockDetail").mockResolvedValue(buildStockDetailEnvelope());

    render(
      <AppProviders client={client}>
        <StockDetailDrawer stockCode="000001.SZ" onClose={onClose} />
      </AppProviders>,
    );

    await screen.findByTestId("stock-detail-chart");
    await user.click(screen.getByRole("button", { name: "关闭抽屉" }));
    expect(onClose).toHaveBeenCalled();
  });

  it("fetches candidate history and renders table with returns and data_status", async () => {
    const client = createApiClient({ mode: "mock" });
    const histItems: LivermoreCandidateHistoryRow[] = [
      {
        snapshot_as_of_date: "2026-04-10",
        stock_code: "000001.SZ",
        stock_name: "H1",
        candidate_rank: 1,
        sector_code: null,
        sector_name: null,
        selection_close: 10.5,
        forward_trade_date_1d: "2026-04-11",
        forward_trade_date_5d: "2026-04-16",
        forward_trade_date_20d: "2026-05-15",
        return_1d: 0.01,
        return_5d: -0.02,
        return_20d: 0.08,
        data_status: "complete",
      },
      {
        snapshot_as_of_date: "2026-04-03",
        stock_code: "000001.SZ",
        stock_name: "H2",
        candidate_rank: 2,
        selection_close: 10.4,
        forward_trade_date_1d: "2026-04-04",
        forward_trade_date_5d: null,
        forward_trade_date_20d: null,
        return_1d: 0.009,
        return_5d: null,
        return_20d: null,
        data_status: "pending",
      },
    ];
    const histSpy = vi.spyOn(client, "getLivermoreCandidateHistory").mockResolvedValue(buildCandidateHistoryEnvelope(histItems));
    vi.spyOn(client, "getLivermoreStockDetail").mockResolvedValue(buildStockDetailEnvelope());
    vi.spyOn(client, "getChoiceNewsEvents").mockResolvedValue(
      buildMockApiEnvelope(
        "news.choice.latest",
        { total_rows: 0, limit: 10, offset: 0, events: [] },
        { basis: "analytical", result_kind: "news.choice.latest" },
      ),
    );

    render(
      <AppProviders client={client}>
        <StockDetailDrawer stockCode="000001.SZ" asOfDate="2026-04-29" onClose={() => undefined} />
      </AppProviders>,
    );

    await waitFor(() =>
      expect(histSpy).toHaveBeenCalledWith({
        stockCode: "000001.SZ",
        limit: 10,
      }),
    );
    expect(await screen.findByTestId("stock-detail-candidate-history")).toBeInTheDocument();
    expect(screen.getByText("1.00%")).toBeInTheDocument();
    expect(screen.getByText("-2.00%")).toBeInTheDocument();
    expect(screen.getByText("8.00%")).toBeInTheDocument();
    const pendingRow = screen.getByTestId("stock-detail-candidate-history-row-2026-04-03-2");
    expect(pendingRow).toHaveTextContent("pending");
    expect(within(pendingRow).getAllByText("—").length).toBeGreaterThanOrEqual(1);
  });

  it("shows candidate history error without breaking chart or factors", async () => {
    const client = createApiClient({ mode: "mock" });
    vi.spyOn(client, "getLivermoreStockDetail").mockResolvedValue(buildStockDetailEnvelope());
    vi.spyOn(client, "getLivermoreCandidateHistory").mockRejectedValue(new Error("candidate history down"));
    vi.spyOn(client, "getChoiceNewsEvents").mockResolvedValue(
      buildMockApiEnvelope(
        "news.choice.latest",
        { total_rows: 0, limit: 10, offset: 0, events: [] },
        { basis: "analytical", result_kind: "news.choice.latest" },
      ),
    );

    render(
      <AppProviders client={client}>
        <StockDetailDrawer stockCode="000001.SZ" asOfDate="2026-04-29" onClose={() => undefined} />
      </AppProviders>,
    );

    expect(await screen.findByTestId("stock-detail-chart")).toBeInTheDocument();
    expect(screen.getByTestId("stock-detail-factors")).toBeInTheDocument();
    expect(await screen.findByTestId("stock-detail-candidate-history-error")).toHaveTextContent("candidate history down");
  });

  it("shows empty state when candidate history has no rows", async () => {
    const client = createApiClient({ mode: "mock" });
    vi.spyOn(client, "getLivermoreCandidateHistory").mockResolvedValue(buildCandidateHistoryEnvelope([]));
    vi.spyOn(client, "getLivermoreStockDetail").mockResolvedValue(buildStockDetailEnvelope());
    vi.spyOn(client, "getChoiceNewsEvents").mockResolvedValue(
      buildMockApiEnvelope(
        "news.choice.latest",
        { total_rows: 0, limit: 10, offset: 0, events: [] },
        { basis: "analytical", result_kind: "news.choice.latest" },
      ),
    );

    render(
      <AppProviders client={client}>
        <StockDetailDrawer stockCode="000001.SZ" asOfDate="2026-04-29" onClose={() => undefined} />
      </AppProviders>,
    );

    expect(await screen.findByTestId("stock-detail-candidate-history-empty")).toHaveTextContent("暂无入选快照记录");
  });
});
