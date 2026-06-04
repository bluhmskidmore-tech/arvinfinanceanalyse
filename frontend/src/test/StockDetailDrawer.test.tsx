import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { AppProviders } from "../app/providers";
import { createApiClient } from "../api/client";
import type {
  ApiEnvelope,
  ApiQuality,
  LivermoreCandidateHistoryRow,
  LivermoreStockDetailPayload,
  ResultMeta,
} from "../api/contracts";
import { buildMockApiEnvelope } from "../mocks/mockApiEnvelope";
import { StockDetailDrawer } from "../features/stock-analysis/components/StockDetailDrawer";

vi.mock("../components/charts/BaseChart", () => ({
  BaseChart: function MockBaseChart() {
    return <div data-testid="stock-detail-chart-canvas-stub" />;
  },
}));

function buildStockDetailEnvelope(
  overrides: {
    factor?: Partial<NonNullable<LivermoreStockDetailPayload["factor"]>>;
    payload?: Partial<Pick<LivermoreStockDetailPayload, "requested_as_of_date" | "as_of_date">>;
    meta?: {
      source_version?: string;
      rule_version?: string;
      quality_flag?: ApiQuality;
      vendor_status?: ResultMeta["vendor_status"];
    } | null;
  } = {},
): ApiEnvelope<LivermoreStockDetailPayload> {
  const requestedAsOfDate: LivermoreStockDetailPayload["requested_as_of_date"] =
    overrides.payload && "requested_as_of_date" in overrides.payload
      ? (overrides.payload.requested_as_of_date ?? null)
      : "2026-04-29";
  const asOfDate: LivermoreStockDetailPayload["as_of_date"] =
    overrides.payload && "as_of_date" in overrides.payload ? (overrides.payload.as_of_date ?? null) : "2026-04-29";

  const envelope = buildMockApiEnvelope<LivermoreStockDetailPayload>(
    "market_data.livermore.stock_detail",
    {
      basis: "analytical",
      state: "ok",
      stock_code: "000001.SZ",
      requested_as_of_date: requestedAsOfDate,
      as_of_date: asOfDate,
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
        pb: overrides.factor?.pb ?? 1.2,
        roe: overrides.factor?.roe ?? 0.1,
        dividend_yield: overrides.factor?.dividend_yield ?? 0.015,
      },
    },
    {
      basis: "analytical",
      source_version: overrides.meta?.source_version ?? "sv_test",
      rule_version: overrides.meta?.rule_version ?? "rv_test",
      quality_flag: overrides.meta?.quality_flag ?? "ok",
      vendor_status: overrides.meta?.vendor_status ?? "ok",
    },
  );
  if (overrides.meta === null) {
    const responseWithoutMeta = { result: envelope.result };
    return responseWithoutMeta as ApiEnvelope<LivermoreStockDetailPayload>;
  }
  return envelope;
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
    const footerMeta = screen.getByTestId("stock-detail-footer-meta");
    expect(footerMeta).toHaveTextContent("来源版本 sv_test");
    expect(footerMeta).toHaveTextContent("规则版本 rv_test");
    expect(footerMeta).toHaveTextContent("质量 正常");
    expect(footerMeta).toHaveTextContent("通道 正常");
    expect(footerMeta).not.toHaveTextContent("source_version");
    expect(footerMeta).not.toHaveTextContent("rule_version");
    expect(footerMeta).not.toHaveTextContent("quality_flag");
    expect(footerMeta).not.toHaveTextContent("vendor_status");
    await waitFor(() =>
      expect(newsSpy).toHaveBeenCalledWith({
        limit: 10,
        offset: 0,
        stockCode: "000001.SZ",
      }),
    );
    expect(screen.getByTestId("stock-detail-candidate-history")).toHaveTextContent("价格回报 · 快照累计");
    expect(screen.getByTestId("stock-detail-candidate-history")).not.toHaveTextContent("backfill");
    expect(screen.getByTestId("stock-detail-market-events-banner")).toHaveTextContent("市场事件 · 公告财报待补");
    expect(screen.getByTestId("stock-detail-market-events-banner")).not.toHaveTextContent("payload");
  });

  it("shows the resolved data date separately when a requested date falls back", async () => {
    const client = createApiClient({ mode: "mock" });
    const detailSpy = vi.spyOn(client, "getLivermoreStockDetail").mockResolvedValue(
      buildStockDetailEnvelope({
        payload: {
          requested_as_of_date: "2026-05-08",
          as_of_date: "2026-04-29",
        },
      }),
    );
    vi.spyOn(client, "getChoiceNewsEvents").mockResolvedValue(
      buildMockApiEnvelope(
        "news.choice.latest",
        { total_rows: 0, limit: 10, offset: 0, events: [] },
        { basis: "analytical", result_kind: "news.choice.latest" },
      ),
    );
    vi.spyOn(client, "getLivermoreCandidateHistory").mockResolvedValue(buildCandidateHistoryEnvelope([]));

    render(
      <AppProviders client={client}>
        <StockDetailDrawer stockCode="000001.SZ" stockName="Alpha" asOfDate="2026-05-08" onClose={() => undefined} />
      </AppProviders>,
    );

    await waitFor(() =>
      expect(detailSpy).toHaveBeenCalledWith({
        stockCode: "000001.SZ",
        asOfDate: "2026-05-08",
        lookback: 60,
      }),
    );
    await screen.findByTestId("stock-detail-footer-meta");
    expect(screen.getByText("截至日 2026-04-29")).toBeInTheDocument();
    expect(screen.getByText("请求日期 2026-05-08")).toBeInTheDocument();
    expect(screen.queryByText("截至日 2026-05-08")).not.toBeInTheDocument();
  });

  it("keeps stock detail lineage visible as pending when result metadata is missing", async () => {
    const client = createApiClient({ mode: "mock" });
    vi.spyOn(client, "getLivermoreStockDetail").mockResolvedValue(buildStockDetailEnvelope({ meta: null }));
    vi.spyOn(client, "getChoiceNewsEvents").mockResolvedValue(
      buildMockApiEnvelope(
        "news.choice.latest",
        { total_rows: 0, limit: 10, offset: 0, events: [] },
        { basis: "analytical", result_kind: "news.choice.latest" },
      ),
    );

    render(
      <AppProviders client={client}>
        <StockDetailDrawer stockCode="000001.SZ" stockName="Alpha" asOfDate="2026-04-29" onClose={() => undefined} />
      </AppProviders>,
    );

    const footerMeta = await screen.findByTestId("stock-detail-footer-meta");
    expect(footerMeta).toHaveTextContent("来源版本 待确认");
    expect(footerMeta).toHaveTextContent("规则版本 待确认");
    expect(footerMeta).toHaveTextContent("质量 待确认");
    expect(footerMeta).toHaveTextContent("通道 待确认");
  });

  it("does not show the requested date as the stock detail data date when no data date is resolved", async () => {
    const client = createApiClient({ mode: "mock" });
    vi.spyOn(client, "getLivermoreStockDetail").mockResolvedValue(
      buildStockDetailEnvelope({
        payload: {
          requested_as_of_date: "2026-05-08",
          as_of_date: null,
        },
      }),
    );
    vi.spyOn(client, "getChoiceNewsEvents").mockResolvedValue(
      buildMockApiEnvelope(
        "news.choice.latest",
        { total_rows: 0, limit: 10, offset: 0, events: [] },
        { basis: "analytical", result_kind: "news.choice.latest" },
      ),
    );
    const histSpy = vi.spyOn(client, "getLivermoreCandidateHistory").mockResolvedValue(buildCandidateHistoryEnvelope([]));

    render(
      <AppProviders client={client}>
        <StockDetailDrawer stockCode="000001.SZ" stockName="Alpha" asOfDate="2026-05-08" onClose={() => undefined} />
      </AppProviders>,
    );

    await screen.findByTestId("stock-detail-footer-meta");
    expect(screen.getByText("截至日 日期待补")).toBeInTheDocument();
    expect(screen.getByText("请求日期 2026-05-08")).toBeInTheDocument();
    expect(screen.queryByText("截至日 2026-05-08")).not.toBeInTheDocument();
    expect(histSpy).not.toHaveBeenCalled();
  });

  it("fetches candidate history with the resolved detail date when a requested date falls back", async () => {
    const client = createApiClient({ mode: "mock" });
    vi.spyOn(client, "getLivermoreStockDetail").mockResolvedValue(
      buildStockDetailEnvelope({
        payload: {
          requested_as_of_date: "2026-05-08",
          as_of_date: "2026-04-29",
        },
      }),
    );
    vi.spyOn(client, "getChoiceNewsEvents").mockResolvedValue(
      buildMockApiEnvelope(
        "news.choice.latest",
        { total_rows: 0, limit: 10, offset: 0, events: [] },
        { basis: "analytical", result_kind: "news.choice.latest" },
      ),
    );
    const histSpy = vi.spyOn(client, "getLivermoreCandidateHistory").mockResolvedValue(buildCandidateHistoryEnvelope([]));

    render(
      <AppProviders client={client}>
        <StockDetailDrawer stockCode="000001.SZ" stockName="Alpha" asOfDate="2026-05-08" onClose={() => undefined} />
      </AppProviders>,
    );

    await waitFor(() =>
      expect(histSpy).toHaveBeenCalledWith({
        stockCode: "000001.SZ",
        snapshotTo: "2026-04-29",
        limit: 10,
      }),
    );
    expect(histSpy).not.toHaveBeenCalledWith({
      stockCode: "000001.SZ",
      snapshotTo: "2026-05-08",
      limit: 10,
    });
  });

  it("localizes stock detail footer governance statuses", async () => {
    const client = createApiClient({ mode: "mock" });
    vi.spyOn(client, "getLivermoreStockDetail").mockResolvedValue(
      buildStockDetailEnvelope({
        meta: {
          source_version: "sv_live",
          rule_version: "rv_live",
          quality_flag: "warning",
          vendor_status: "vendor_stale",
        },
      }),
    );

    render(
      <AppProviders client={client}>
        <StockDetailDrawer stockCode="000001.SZ" stockName="Alpha" asOfDate="2026-04-29" onClose={() => undefined} />
      </AppProviders>,
    );

    const footerMeta = await screen.findByTestId("stock-detail-footer-meta");
    expect(footerMeta).toHaveTextContent("来源版本 sv_live");
    expect(footerMeta).toHaveTextContent("规则版本 rv_live");
    expect(footerMeta).toHaveTextContent("质量 需复核");
    expect(footerMeta).toHaveTextContent("通道 供数陈旧");
    expect(footerMeta).not.toHaveTextContent("warning");
    expect(footerMeta).not.toHaveTextContent("vendor_stale");
  });

  it("does not expose unknown stock detail footer governance codes", async () => {
    const client = createApiClient({ mode: "mock" });
    vi.spyOn(client, "getLivermoreStockDetail").mockResolvedValue(
      buildStockDetailEnvelope({
        meta: {
          source_version: "sv_live",
          rule_version: "rv_live",
          quality_flag: "external_vendor_quality_state" as ApiQuality,
          vendor_status: "external_vendor_feed_pending" as ResultMeta["vendor_status"],
        },
      }),
    );

    render(
      <AppProviders client={client}>
        <StockDetailDrawer stockCode="000001.SZ" stockName="Alpha" asOfDate="2026-04-29" onClose={() => undefined} />
      </AppProviders>,
    );

    const footerMeta = await screen.findByTestId("stock-detail-footer-meta");
    expect(footerMeta).toHaveTextContent("待确认");
    expect(footerMeta).not.toHaveTextContent("external_vendor_quality_state");
    expect(footerMeta).not.toHaveTextContent("external_vendor_feed_pending");
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
            {
              event_key: "e3",
              received_at: "2026-05-08T10:45:00Z",
              group_id: "g1",
              content_type: "externalVendorNews",
              serial_id: 3,
              request_id: 1,
              error_code: 0,
              error_msg: "",
              topic_code: "externalVendorTopic",
              item_index: 0,
              payload_text: "Third row body text",
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
    expect(list.querySelectorAll("li")).toHaveLength(3);
    expect(screen.getAllByText("行业新闻")).toHaveLength(2);
    expect(screen.getByText("事件分类待确认")).toBeInTheDocument();
    expect(list).not.toHaveTextContent("TOPIC_ONE");
    expect(list).not.toHaveTextContent("TOPIC_TWO");
    expect(list).not.toHaveTextContent("externalVendorTopic");
    expect(list).not.toHaveTextContent("externalVendorNews");
    expect(screen.getByText(/Brief headline about macro conditions/)).toBeInTheDocument();
  });

  it("shows choice news error in isolation while chart and factors still render", async () => {
    const client = createApiClient({ mode: "mock" });
    vi.spyOn(client, "getLivermoreStockDetail").mockResolvedValue(buildStockDetailEnvelope());
    vi.spyOn(client, "getChoiceNewsEvents").mockRejectedValue(
      new Error(
        "Request failed: /ui/news/choice-events/latest because source_table choice_stock_news_event is missing.",
      ),
    );

    render(
      <AppProviders client={client}>
        <StockDetailDrawer stockCode="000001.SZ" asOfDate="2026-04-29" onClose={() => undefined} />
      </AppProviders>,
    );

    expect(await screen.findByTestId("stock-detail-chart")).toBeInTheDocument();
    expect(screen.getByTestId("stock-detail-factors")).toBeInTheDocument();
    const marketEventsError = await screen.findByTestId("stock-detail-market-events-error");
    expect(marketEventsError).toHaveTextContent("市场事件暂不可用");
    expect(marketEventsError).toHaveTextContent("个股复核数据不受影响");
    expect(marketEventsError).toHaveTextContent("源表缺失");
    expect(marketEventsError).not.toHaveTextContent("Request failed");
    expect(marketEventsError).not.toHaveTextContent("/ui/news/choice-events/latest");
    expect(marketEventsError).not.toHaveTextContent("source_table");
    expect(marketEventsError).not.toHaveTextContent("choice_stock_news_event");
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

  it("shows 待补 instead of non-finite factor metrics", async () => {
    const client = createApiClient({ mode: "mock" });
    const detailSpy = vi.spyOn(client, "getLivermoreStockDetail").mockResolvedValue(
      buildStockDetailEnvelope({
        factor: {
          pe: Number.POSITIVE_INFINITY,
          pb: Number.NEGATIVE_INFINITY,
          roe: Number.POSITIVE_INFINITY,
          dividend_yield: Number.NEGATIVE_INFINITY,
        },
      }),
    );
    vi.spyOn(client, "getLivermoreCandidateHistory").mockResolvedValue(buildCandidateHistoryEnvelope([]));
    vi.spyOn(client, "getChoiceNewsEvents").mockResolvedValue(
      buildMockApiEnvelope(
        "news.choice.latest",
        { total_rows: 0, limit: 10, offset: 0, events: [] },
        { basis: "analytical", result_kind: "news.choice.latest" },
      ),
    );

    render(
      <AppProviders client={client}>
        <StockDetailDrawer stockCode="000002.SZ" onClose={() => undefined} />
      </AppProviders>,
    );

    await waitFor(() =>
      expect(detailSpy).toHaveBeenCalledWith({
        stockCode: "000002.SZ",
        asOfDate: undefined,
        lookback: 60,
      }),
    );
    expect(await screen.findByTestId("stock-detail-factor-pe")).toHaveTextContent("待补");
    expect(screen.getByTestId("stock-detail-factor-pb")).toHaveTextContent("待补");
    expect(screen.getByTestId("stock-detail-factor-roe")).toHaveTextContent("待补");
    expect(screen.getByTestId("stock-detail-factor-dividend")).toHaveTextContent("待补");
    expect(screen.getByTestId("stock-detail-factors")).not.toHaveTextContent("Infinity");
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
    expect(screen.getByTestId("stock-detail-error")).toHaveTextContent("个股复核数据暂不可用");
    expect(screen.getByTestId("stock-detail-error")).toHaveTextContent("请稍后重试");
    expect(screen.getByTestId("stock-detail-error")).not.toHaveTextContent("network down");
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

  it("fetches candidate history and renders table with returns and localized data status", async () => {
    const client = createApiClient({ mode: "mock" });
    const histItems: LivermoreCandidateHistoryRow[] = [
      {
        snapshot_as_of_date: "2026-04-10",
        stock_code: "000001.SZ",
        stock_name: "H1",
        signal_kind: "livermore",
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
      {
        snapshot_as_of_date: "2026-03-27",
        stock_code: "000001.SZ",
        stock_name: "H3",
        candidate_rank: 3,
        selection_close: 10.1,
        forward_trade_date_1d: "2026-03-30",
        forward_trade_date_5d: null,
        forward_trade_date_20d: null,
        return_1d: null,
        return_5d: null,
        return_20d: null,
        data_status: " partial_halt ",
      },
      {
        snapshot_as_of_date: "2026-03-20",
        stock_code: "000001.SZ",
        stock_name: "H4",
        signal_kind: "experimental_signal",
        candidate_rank: 4,
        selection_close: 9.9,
        forward_trade_date_1d: null,
        forward_trade_date_5d: null,
        forward_trade_date_20d: null,
        return_1d: null,
        return_5d: null,
        return_20d: null,
        data_status: "missing_forward_return",
      },
      {
        snapshot_as_of_date: "2026-03-13",
        stock_code: "000001.SZ",
        stock_name: "H5",
        signal_kind: "sourceTableAlphaSignal",
        candidate_rank: 5,
        sector_code: null,
        sector_name: null,
        selection_close: 9.8,
        forward_trade_date_1d: null,
        forward_trade_date_5d: null,
        forward_trade_date_20d: null,
        return_1d: null,
        return_5d: null,
        return_20d: null,
        data_status: "complete",
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
        snapshotTo: "2026-04-29",
        limit: 10,
      }),
    );
    expect(await screen.findByTestId("stock-detail-candidate-history")).toBeInTheDocument();
    expect(screen.getByText("1.00%")).toBeInTheDocument();
    expect(screen.getByText("-2.00%")).toBeInTheDocument();
    expect(screen.getByText("8.00%")).toBeInTheDocument();
    const completeRow = screen.getByTestId("stock-detail-candidate-history-row-2026-04-10-1");
    expect(completeRow).toHaveTextContent("趋势突破");
    expect(completeRow).not.toHaveTextContent("livermore");
    expect(completeRow).toHaveTextContent("已成熟");
    expect(completeRow).not.toHaveTextContent("complete");
    const pendingRow = screen.getByTestId("stock-detail-candidate-history-row-2026-04-03-2");
    expect(pendingRow).toHaveTextContent("待成熟");
    expect(pendingRow).not.toHaveTextContent("pending");
    expect(within(pendingRow).getAllByText("—").length).toBeGreaterThanOrEqual(1);
    const partialHaltRow = screen.getByTestId("stock-detail-candidate-history-row-2026-03-27-3");
    expect(partialHaltRow).toHaveTextContent("部分停牌");
    expect(partialHaltRow).not.toHaveTextContent("partial_halt");
    expect(partialHaltRow).toHaveClass("stock-detail-drawer__history-row--halt");
    const unknownStatusRow = screen.getByTestId("stock-detail-candidate-history-row-2026-03-20-4");
    expect(unknownStatusRow).toHaveTextContent("策略待确认");
    expect(unknownStatusRow).not.toHaveTextContent("experimental_signal");
    expect(unknownStatusRow).toHaveTextContent("状态待确认");
    expect(unknownStatusRow).not.toHaveTextContent("missing_forward_return");
    const sourceTableRow = screen.getByTestId("stock-detail-candidate-history-row-2026-03-13-5");
    expect(sourceTableRow).toHaveTextContent("策略待确认");
    expect(sourceTableRow).not.toHaveTextContent("sourceTableAlphaSignal");
  });

  it("shows dashes instead of non-finite candidate history returns", async () => {
    const client = createApiClient({ mode: "mock" });
    const histItems: LivermoreCandidateHistoryRow[] = [
      {
        snapshot_as_of_date: "2026-04-10",
        stock_code: "000001.SZ",
        stock_name: "H1",
        signal_kind: "livermore",
        candidate_rank: 1,
        sector_code: null,
        sector_name: null,
        selection_close: 10.5,
        forward_trade_date_1d: "2026-04-11",
        forward_trade_date_5d: "2026-04-16",
        forward_trade_date_20d: "2026-05-15",
        return_1d: Number.POSITIVE_INFINITY,
        return_5d: Number.NEGATIVE_INFINITY,
        return_20d: Number.NaN,
        data_status: "complete",
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
        <StockDetailDrawer stockCode="000003.SZ" asOfDate="2026-04-29" onClose={() => undefined} />
      </AppProviders>,
    );

    await waitFor(() =>
      expect(histSpy).toHaveBeenCalledWith({
        stockCode: "000003.SZ",
        snapshotTo: "2026-04-29",
        limit: 10,
      }),
    );
    const row = await screen.findByTestId("stock-detail-candidate-history-row-2026-04-10-1");
    expect(row).not.toHaveTextContent("Infinity");
    expect(row).not.toHaveTextContent("NaN");
    expect(within(row).getAllByText("—").length).toBeGreaterThanOrEqual(3);
  });

  it("shows candidate history error without breaking chart or factors", async () => {
    const client = createApiClient({ mode: "mock" });
    vi.spyOn(client, "getLivermoreStockDetail").mockResolvedValue(buildStockDetailEnvelope());
    vi.spyOn(client, "getLivermoreCandidateHistory").mockRejectedValue(
      new Error(
        "Request failed: /ui/market-data/livermore/candidate-history because source_table choice_stock_candidate_history is missing.",
      ),
    );
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
    const candidateHistoryError = await screen.findByTestId("stock-detail-candidate-history-error");
    expect(candidateHistoryError).toHaveTextContent("入选历史暂不可用");
    expect(candidateHistoryError).toHaveTextContent("图表与因子仍可继续查看");
    expect(candidateHistoryError).toHaveTextContent("源表缺失");
    expect(candidateHistoryError).not.toHaveTextContent("Request failed");
    expect(candidateHistoryError).not.toHaveTextContent("/ui/market-data/livermore/candidate-history");
    expect(candidateHistoryError).not.toHaveTextContent("source_table");
    expect(candidateHistoryError).not.toHaveTextContent("choice_stock_candidate_history");
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
