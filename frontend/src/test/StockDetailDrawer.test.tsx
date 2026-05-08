import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { AppProviders } from "../app/providers";
import { createApiClient } from "../api/client";
import { buildMockApiEnvelope } from "../mocks/mockApiEnvelope";
import { StockDetailDrawer } from "../features/stock-analysis/components/StockDetailDrawer";

vi.mock("../components/charts/BaseChart", () => ({
  BaseChart: function MockBaseChart() {
    return <div data-testid="stock-detail-chart-canvas-stub" />;
  },
}));

function buildStockDetailEnvelope(overrides: { factor?: { pe: number | null } } = {}) {
  return buildMockApiEnvelope(
    "market_data.livermore.stock_detail",
    {
      basis: "analytical",
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
      }),
    );
    expect(screen.getByTestId("stock-detail-market-events-banner")).toHaveTextContent("未按本股过滤");
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

    expect(await screen.findByTestId("stock-detail-market-events-empty")).toHaveTextContent("暂无市场事件数据");
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
});
