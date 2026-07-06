import { readFileSync } from "node:fs";
import { resolve } from "node:path";

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
  BaseChart: function MockBaseChart({ height }: { height?: number }) {
    return (
      <div data-height={height} data-testid="stock-detail-chart-canvas-stub" />
    );
  },
}));

const STOCK_DETAIL_DRAWER_CSS_PATH = resolve(
  process.cwd(),
  "src/features/stock-analysis/components/StockDetailDrawer.css",
);

function buildStockDetailEnvelope(
  overrides: {
    factor?: Partial<NonNullable<LivermoreStockDetailPayload["factor"]>>;
    payload?: Partial<
      Pick<LivermoreStockDetailPayload, "requested_as_of_date" | "as_of_date">
    >;
    candles?: LivermoreStockDetailPayload["candles"];
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
    overrides.payload && "as_of_date" in overrides.payload
      ? (overrides.payload.as_of_date ?? null)
      : "2026-04-29";

  const envelope = buildMockApiEnvelope<LivermoreStockDetailPayload>(
    "market_data.livermore.stock_detail",
    {
      basis: "analytical",
      state: "ok",
      stock_code: "000001.SZ",
      requested_as_of_date: requestedAsOfDate,
      as_of_date: asOfDate,
      lookback: 60,
      candles: overrides.candles ?? [
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
  it("keeps the stock detail drawer header compact before the decision summary", () => {
    const css = readFileSync(STOCK_DETAIL_DRAWER_CSS_PATH, "utf8");
    const compactStart = css.indexOf("Detail drawer compact header pass");
    const compactCss = css.slice(compactStart);

    expect(compactStart).toBeGreaterThan(-1);
    expect(compactCss).toMatch(
      /\.stock-detail-drawer__header\s*\{[\s\S]*?grid-template-columns:\s*minmax\(0,\s*1fr\)\s*auto[\s\S]*?gap:\s*8px[\s\S]*?padding:\s*10px 12px/,
    );
    expect(compactCss).toMatch(
      /\.stock-detail-drawer__strategy-ranks-label\s*\{[\s\S]*?display:\s*none/,
    );
    expect(compactCss).toMatch(
      /@media \(max-width:\s*720px\)[\s\S]*?\.stock-detail-drawer__header\s*\{[\s\S]*?grid-template-columns:\s*minmax\(0,\s*1fr\)\s*auto[\s\S]*?padding:\s*10px/,
    );
    expect(compactCss).toMatch(
      /@media \(max-width:\s*720px\)[\s\S]*?\.stock-detail-drawer__lookback\s*\.ant-typography\s*\{[\s\S]*?display:\s*none/,
    );
  });

  it("keeps audit and footer governance compact behind the stock review", () => {
    const css = readFileSync(STOCK_DETAIL_DRAWER_CSS_PATH, "utf8");
    const compactStart = css.indexOf("Detail drawer audit compact pass");
    const compactCss = css.slice(compactStart);

    expect(compactStart).toBeGreaterThan(-1);
    expect(compactCss).toMatch(
      /\.stock-detail-drawer__audit-details\s*>\s*summary\s*\{[\s\S]*?min-height:\s*36px[\s\S]*?padding:\s*8px 10px/,
    );
    expect(compactCss).toMatch(
      /\.stock-detail-drawer__footer-meta\s*\{[\s\S]*?min-height:\s*28px[\s\S]*?white-space:\s*nowrap/,
    );
    expect(compactCss).toMatch(
      /@media \(max-width:\s*720px\)[\s\S]*?\.stock-detail-drawer__audit-details\s*>\s*summary\s*\{[\s\S]*?align-items:\s*center[\s\S]*?flex-direction:\s*row/,
    );
  });

  it("fetches stock detail and shows chart + factor grid", async () => {
    const client = createApiClient({ mode: "mock" });
    const spy = vi
      .spyOn(client, "getLivermoreStockDetail")
      .mockResolvedValue(buildStockDetailEnvelope());
    const newsSpy = vi.spyOn(client, "getChoiceNewsEvents");

    render(
      <AppProviders client={client}>
        <StockDetailDrawer
          stockCode="000001.SZ"
          stockName="Alpha"
          asOfDate="2026-04-29"
          onClose={() => undefined}
        />
      </AppProviders>,
    );

    await waitFor(() => expect(spy).toHaveBeenCalled());

    expect(await screen.findByTestId("stock-detail-chart")).toBeInTheDocument();
    expect(screen.getByTestId("stock-detail-chart-canvas-stub")).toHaveAttribute(
      "data-height",
      "300",
    );
    expect(screen.getByTestId("stock-detail-factors")).toBeInTheDocument();
    expect(screen.getByTestId("stock-detail-factor-pe")).toHaveTextContent(
      "9.70",
    );
    const footerMeta = screen.getByTestId("stock-detail-footer-meta");
    expect(footerMeta).toHaveTextContent("数据口径 已确认");
    expect(footerMeta).toHaveTextContent("质量 正常");
    expect(footerMeta).toHaveTextContent("供数状态 正常");
    expect(footerMeta).not.toHaveTextContent("sv_test");
    expect(footerMeta).not.toHaveTextContent("rv_test");
    expect(footerMeta).not.toHaveTextContent("通道 正常");
    expect(footerMeta).not.toHaveTextContent("source_version");
    expect(footerMeta).not.toHaveTextContent("rule_version");
    expect(footerMeta).not.toHaveTextContent("quality_flag");
    expect(footerMeta).not.toHaveTextContent("vendor_status");
    const lineageDetail = screen.getByTestId("stock-detail-lineage-detail");
    expect(lineageDetail).toHaveTextContent(/来源版本\s*sv_test/);
    expect(lineageDetail).toHaveTextContent(/规则版本\s*rv_test/);
    await waitFor(() =>
      expect(newsSpy).toHaveBeenCalledWith({
        limit: 10,
        offset: 0,
        stockCode: "000001.SZ",
      }),
    );
    expect(
      screen.getByTestId("stock-detail-candidate-history"),
    ).toHaveTextContent("价格回报 · 快照累计");
    expect(
      screen.getByTestId("stock-detail-candidate-history"),
    ).not.toHaveTextContent("backfill");
    expect(
      screen.getByTestId("stock-detail-market-events-banner"),
    ).toHaveTextContent("市场事件 · 公告财报待补");
    expect(
      screen.getByTestId("stock-detail-market-events-banner"),
    ).not.toHaveTextContent("payload");
  });

  it("shows the resolved data date separately when a requested date falls back", async () => {
    const client = createApiClient({ mode: "mock" });
    const detailSpy = vi
      .spyOn(client, "getLivermoreStockDetail")
      .mockResolvedValue(
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
    vi.spyOn(client, "getLivermoreCandidateHistory").mockResolvedValue(
      buildCandidateHistoryEnvelope([]),
    );

    render(
      <AppProviders client={client}>
        <StockDetailDrawer
          stockCode="000001.SZ"
          stockName="Alpha"
          asOfDate="2026-05-08"
          onClose={() => undefined}
        />
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
    vi.spyOn(client, "getLivermoreStockDetail").mockResolvedValue(
      buildStockDetailEnvelope({ meta: null }),
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
        <StockDetailDrawer
          stockCode="000001.SZ"
          stockName="Alpha"
          asOfDate="2026-04-29"
          onClose={() => undefined}
        />
      </AppProviders>,
    );

    const footerMeta = await screen.findByTestId("stock-detail-footer-meta");
    expect(footerMeta).toHaveTextContent("数据口径 待确认");
    expect(footerMeta).toHaveTextContent("质量 待确认");
    expect(footerMeta).toHaveTextContent("供数状态 待确认");
    expect(footerMeta).not.toHaveTextContent("来源版本");
    expect(footerMeta).not.toHaveTextContent("规则版本");
    expect(footerMeta).not.toHaveTextContent("通道 待确认");
    const lineageDetail = screen.getByTestId("stock-detail-lineage-detail");
    expect(lineageDetail).toHaveTextContent(/来源版本\s*待确认/);
    expect(lineageDetail).toHaveTextContent(/规则版本\s*待确认/);
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
    const histSpy = vi
      .spyOn(client, "getLivermoreCandidateHistory")
      .mockResolvedValue(buildCandidateHistoryEnvelope([]));

    render(
      <AppProviders client={client}>
        <StockDetailDrawer
          stockCode="000001.SZ"
          stockName="Alpha"
          asOfDate="2026-05-08"
          onClose={() => undefined}
        />
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
    const histSpy = vi
      .spyOn(client, "getLivermoreCandidateHistory")
      .mockResolvedValue(buildCandidateHistoryEnvelope([]));

    render(
      <AppProviders client={client}>
        <StockDetailDrawer
          stockCode="000001.SZ"
          stockName="Alpha"
          asOfDate="2026-05-08"
          onClose={() => undefined}
        />
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
        <StockDetailDrawer
          stockCode="000001.SZ"
          stockName="Alpha"
          asOfDate="2026-04-29"
          onClose={() => undefined}
        />
      </AppProviders>,
    );

    const footerMeta = await screen.findByTestId("stock-detail-footer-meta");
    expect(footerMeta).toHaveTextContent("数据口径 已确认");
    expect(footerMeta).toHaveTextContent("质量 需复核");
    expect(footerMeta).toHaveTextContent("供数状态 供数陈旧");
    expect(footerMeta).not.toHaveTextContent("sv_live");
    expect(footerMeta).not.toHaveTextContent("rv_live");
    expect(footerMeta).not.toHaveTextContent("通道 供数陈旧");
    expect(footerMeta).not.toHaveTextContent("warning");
    expect(footerMeta).not.toHaveTextContent("vendor_stale");
    const lineageDetail = screen.getByTestId("stock-detail-lineage-detail");
    expect(lineageDetail).toHaveTextContent(/来源版本\s*sv_live/);
    expect(lineageDetail).toHaveTextContent(/规则版本\s*rv_live/);
  });

  it("does not expose unknown stock detail footer governance codes", async () => {
    const client = createApiClient({ mode: "mock" });
    vi.spyOn(client, "getLivermoreStockDetail").mockResolvedValue(
      buildStockDetailEnvelope({
        meta: {
          source_version: "sv_live",
          rule_version: "rv_live",
          quality_flag: "external_vendor_quality_state" as ApiQuality,
          vendor_status:
            "external_vendor_feed_pending" as ResultMeta["vendor_status"],
        },
      }),
    );

    render(
      <AppProviders client={client}>
        <StockDetailDrawer
          stockCode="000001.SZ"
          stockName="Alpha"
          asOfDate="2026-04-29"
          onClose={() => undefined}
        />
      </AppProviders>,
    );

    const footerMeta = await screen.findByTestId("stock-detail-footer-meta");
    expect(footerMeta).toHaveTextContent("待确认");
    expect(footerMeta).not.toHaveTextContent("external_vendor_quality_state");
    expect(footerMeta).not.toHaveTextContent("external_vendor_feed_pending");
    const lineageDetail = screen.getByTestId("stock-detail-lineage-detail");
    expect(lineageDetail).toHaveTextContent(/质量\s*待确认/);
    expect(lineageDetail).toHaveTextContent(/供数状态\s*待确认/);
    expect(lineageDetail).not.toHaveTextContent(
      "external_vendor_quality_state",
    );
    expect(lineageDetail).not.toHaveTextContent("external_vendor_feed_pending");
  });

  it("shows the review context that opened the drawer", async () => {
    const client = createApiClient({ mode: "mock" });
    vi.spyOn(client, "getLivermoreStockDetail").mockResolvedValue(
      buildStockDetailEnvelope(),
    );

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

  it("renders candidate review thesis when opened from the review queue", async () => {
    const client = createApiClient({ mode: "mock" });
    vi.spyOn(client, "getLivermoreStockDetail").mockResolvedValue(
      buildStockDetailEnvelope(),
    );

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
            reviewThesis: {
              whySelected: [
                "Alpha · AI · 距观察位 0.46%",
                "行业排名：行业排名第 1：AI",
              ],
              boundaries: ["新闻、公告、财报事件尚未进入候选卡。"],
              invalidation: ["收盘跌破 10EMA 20.60 后降级观察。"],
              nextActions: [
                "看 K 线确认价格与量能",
                "查公告/新闻确认边界",
                "确认失效条件后再继续观察",
              ],
            },
          }}
          onClose={() => undefined}
        />
      </AppProviders>,
    );

    const thesis = await screen.findByTestId("stock-detail-review-thesis");
    const brief = screen.getByTestId("stock-detail-decision-brief");
    const thesisDetails = screen.getByTestId("stock-detail-thesis-details");
    expect(brief).toHaveTextContent("为什么看");
    expect(brief).toHaveTextContent("Alpha · AI");
    expect(brief).toHaveTextContent("失效线");
    expect(brief).toHaveTextContent("10EMA");
    expect(brief).toHaveTextContent("边界");
    expect(brief).toHaveTextContent("新闻、公告、财报事件尚未进入候选卡");
    expect(brief).toHaveTextContent("下一步");
    expect(brief).toHaveTextContent("看 K 线确认价格与量能");
    expect(thesisDetails).not.toHaveAttribute("open");
    expect(thesis).toHaveTextContent("为什么入选");
    expect(thesis).toHaveTextContent("Alpha · AI");
    expect(thesis).toHaveTextContent("行业排名");
    expect(thesis).toHaveTextContent("主要边界");
    expect(thesis).toHaveTextContent("新闻、公告、财报事件尚未进入候选卡");
    expect(thesis).toHaveTextContent("失效条件");
    expect(thesis).toHaveTextContent("10EMA");
    expect(thesis).toHaveTextContent("下一步动作");
    expect(thesis).toHaveTextContent("看 K 线确认价格与量能");
    expect(thesis).not.toHaveTextContent("仅作观察与复核");
    expect(thesis).not.toHaveTextContent("source_table");
  });

  it("opens review candidates with a decision summary before secondary audit details", async () => {
    const client = createApiClient({ mode: "mock" });
    vi.spyOn(client, "getLivermoreStockDetail").mockResolvedValue(
      buildStockDetailEnvelope(),
    );
    vi.spyOn(client, "getChoiceNewsEvents").mockResolvedValue(
      buildMockApiEnvelope(
        "news.choice.latest",
        { total_rows: 0, limit: 10, offset: 0, events: [] },
        { basis: "analytical", result_kind: "news.choice.latest" },
      ),
    );
    vi.spyOn(client, "getLivermoreCandidateHistory").mockResolvedValue(
      buildCandidateHistoryEnvelope([]),
    );

    render(
      <AppProviders client={client}>
        <StockDetailDrawer
          stockCode="000001.SZ"
          stockName="Alpha"
          asOfDate="2026-04-29"
          reviewContext={{
            sourceLabel: "review queue",
            sectorName: "AI",
            reviewRank: 1,
            distanceToBreakoutPct: "MA20 0.46%",
            reviewThesis: {
              whySelected: [
                "Selected because rank #1 and MA20 distance is tight",
              ],
              boundaries: [
                "Boundary: announcement and news still need manual confirmation",
              ],
              invalidation: ["Downgrade if price closes below 10EMA"],
              nextActions: ["Open K-line review before continuing"],
            },
          }}
          onClose={() => undefined}
        />
      </AppProviders>,
    );

    await screen.findByTestId("stock-detail-chart");

    const summary = await screen.findByTestId("stock-detail-decision-summary");
    const brief = screen.getByTestId("stock-detail-decision-brief");
    expect(summary).toHaveTextContent("Selected because rank #1");
    expect(summary).toHaveTextContent(
      "Boundary: announcement and news still need manual confirmation",
    );
    expect(summary).toHaveTextContent("Downgrade if price closes below 10EMA");
    expect(summary).toHaveTextContent("Open K-line review before continuing");
    expect(brief).toHaveTextContent("为什么看");
    expect(brief).toHaveTextContent("失效线");
    expect(brief).toHaveTextContent("边界");
    expect(brief).toHaveTextContent("下一步");

    const chart = screen.getByTestId("stock-detail-chart");
    expect(
      summary.compareDocumentPosition(chart) & Node.DOCUMENT_POSITION_FOLLOWING,
    ).toBeTruthy();

    const auditDetails = screen.getByTestId("stock-detail-audit-details");
    expect(auditDetails).toContainElement(
      screen.getByTestId("stock-detail-lineage-detail"),
    );
    expect(auditDetails).toContainElement(
      screen.getByTestId("stock-detail-factors"),
    );
    expect(auditDetails).toContainElement(
      screen.getByTestId("stock-detail-candidate-history"),
    );
    expect(auditDetails).toContainElement(
      screen.getByTestId("stock-detail-market-events"),
    );
  });

  it("renders compact review checks for price, volume, invalidation, and boundary", async () => {
    const client = createApiClient({ mode: "mock" });
    vi.spyOn(client, "getLivermoreStockDetail").mockResolvedValue(
      buildStockDetailEnvelope({
        candles: [
          {
            trade_date: "2026-04-24",
            open_value: 9.8,
            high_value: 10.1,
            low_value: 9.7,
            close_value: 10,
            volume: 100,
            amount: 1_000,
          },
          {
            trade_date: "2026-04-25",
            open_value: 10,
            high_value: 10.8,
            low_value: 9.9,
            close_value: 10.5,
            volume: 100,
            amount: 1_050,
          },
          {
            trade_date: "2026-04-26",
            open_value: 10.6,
            high_value: 11.2,
            low_value: 10.5,
            close_value: 11,
            volume: 300,
            amount: 3_300,
          },
        ],
      }),
    );

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
            distanceToBreakoutPct: "MA20 0.46%",
            reviewThesis: {
              whySelected: ["Alpha · AI · 距观察位 MA20 0.46%"],
              boundaries: ["新闻、公告、财报事件尚未进入候选卡。"],
              invalidation: ["收盘跌破 10EMA 20.60 后降级观察。"],
              nextActions: ["看 K 线确认价格与量能"],
            },
          }}
          onClose={() => undefined}
        />
      </AppProviders>,
    );

    const confirmation = await screen.findByTestId(
      "stock-detail-review-checklist",
    );
    const primaryGrid = confirmation.querySelector(
      ".stock-detail-drawer__review-check-grid",
    );
    const moreChecks = within(confirmation).getByTestId(
      "stock-detail-review-check-more",
    );
    const moreGrid = moreChecks.querySelector(
      ".stock-detail-drawer__review-check-more-grid",
    );
    const timeline = within(confirmation).getByTestId(
      "stock-detail-event-boundary-timeline",
    );

    expect(primaryGrid?.children.length).toBe(2);
    expect(moreChecks).not.toHaveAttribute("open");
    expect(moreChecks).toContainElement(timeline);
    expect(moreGrid?.children.length).toBe(2);
    expect(confirmation).toHaveTextContent("复核核验");
    expect(confirmation).toHaveTextContent("价格");
    await waitFor(() => expect(confirmation).toHaveTextContent("11.00"));
    expect(confirmation).toHaveTextContent("较前日 +4.76%");
    expect(confirmation).toHaveTextContent("量能 3.0x");
    expect(confirmation).toHaveTextContent("观察位");
    expect(confirmation).toHaveTextContent("MA20 0.46%");
    expect(confirmation).toHaveTextContent("失效");
    expect(confirmation).toHaveTextContent("收盘跌破 10EMA 20.60 后降级观察。");
    expect(confirmation).toHaveTextContent("边界");
    expect(confirmation).toHaveTextContent(
      "新闻、公告、财报事件尚未进入候选卡。",
    );
    expect(confirmation).not.toHaveTextContent("source_table");
  });

  it("renders event boundary timeline near the candidate decision", async () => {
    const client = createApiClient({ mode: "mock" });
    vi.spyOn(client, "getLivermoreStockDetail").mockResolvedValue(
      buildStockDetailEnvelope(),
    );
    vi.spyOn(client, "getChoiceNewsEvents").mockResolvedValue(
      buildMockApiEnvelope(
        "news.choice.latest",
        {
          total_rows: 2,
          limit: 10,
          offset: 0,
          as_of_date: "2026-05-08",
          excluded_future_rows: 1,
          events: [
            {
              event_key: "e1",
              received_at: "2026-05-08T09:30:00Z",
              group_id: "g1",
              content_type: "announcement",
              serial_id: 1,
              request_id: 1,
              error_code: 0,
              error_msg: "",
              topic_code: "TOPIC_ONE",
              item_index: 0,
              payload_text: "Alpha signed a new supply contract",
              payload_json: null,
            },
            {
              event_key: "e2",
              received_at: "2026-05-08T10:15:00Z",
              group_id: "g1",
              content_type: "stocknews",
              serial_id: 2,
              request_id: 1,
              error_code: 0,
              error_msg: "",
              topic_code: "TOPIC_TWO",
              item_index: 0,
              payload_text: "Alpha intraday volume expanded",
              payload_json: null,
            },
          ],
        },
        { basis: "analytical", result_kind: "news.choice.latest" },
      ),
    );

    render(
      <AppProviders client={client}>
        <StockDetailDrawer
          stockCode="000001.SZ"
          stockName="Alpha"
          asOfDate="2026-04-29"
          reviewContext={{
            sourceLabel: "复核队列",
            reviewThesis: {
              whySelected: ["Alpha · AI"],
              boundaries: ["新闻、公告、财报事件尚未进入候选卡。"],
              invalidation: ["跌破 MA20 后降级观察。"],
              nextActions: ["查公告/新闻确认边界"],
            },
          }}
          onClose={() => undefined}
        />
      </AppProviders>,
    );

    const checklist = await screen.findByTestId(
      "stock-detail-review-checklist",
    );
    const timeline = within(checklist).getByTestId(
      "stock-detail-event-boundary-timeline",
    );
    expect(checklist).toHaveTextContent("复核核验");
    await waitFor(() => expect(checklist).toHaveTextContent("事件 2 条"));
    expect(checklist).toHaveTextContent("边界");
    expect(checklist).toHaveTextContent("新闻、公告、财报事件尚未进入候选卡。");
    expect(timeline).toHaveTextContent("公告事件");
    expect(timeline).toHaveTextContent("个股新闻事件");
    expect(timeline).toHaveTextContent("Alpha signed a new supply contract");
    expect(timeline).not.toHaveTextContent("TOPIC_ONE");
    expect(timeline).not.toHaveTextContent("source_table");
  });

  it("renders market event rows from getChoiceNewsEvents", async () => {
    const client = createApiClient({ mode: "mock" });
    vi.spyOn(client, "getLivermoreStockDetail").mockResolvedValue(
      buildStockDetailEnvelope(),
    );
    vi.spyOn(client, "getChoiceNewsEvents").mockResolvedValue(
      buildMockApiEnvelope(
        "news.choice.latest",
        {
          total_rows: 2,
          limit: 10,
          offset: 0,
          as_of_date: "2026-05-08",
          excluded_future_rows: 1,
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
        <StockDetailDrawer
          stockCode="000001.SZ"
          asOfDate="2026-04-29"
          onClose={() => undefined}
        />
      </AppProviders>,
    );

    const list = await screen.findByTestId("stock-detail-market-events-list");
    expect(screen.getByTestId("stock-detail-market-events-banner")).toHaveTextContent(
      "数据日期 2026-05-08",
    );
    expect(screen.getByTestId("stock-detail-market-events-banner")).toHaveTextContent(
      "已剔除未来 1 条",
    );
    expect(list.querySelectorAll("li")).toHaveLength(3);
    expect(screen.getAllByText("行业新闻")).toHaveLength(2);
    expect(screen.getByText("事件分类待确认")).toBeInTheDocument();
    expect(list).not.toHaveTextContent("TOPIC_ONE");
    expect(list).not.toHaveTextContent("TOPIC_TWO");
    expect(list).not.toHaveTextContent("externalVendorTopic");
    expect(list).not.toHaveTextContent("externalVendorNews");
    expect(
      within(list).getByText(/Brief headline about macro conditions/),
    ).toBeInTheDocument();
  });

  it("shows choice news error in isolation while chart and factors still render", async () => {
    const client = createApiClient({ mode: "mock" });
    vi.spyOn(client, "getLivermoreStockDetail").mockResolvedValue(
      buildStockDetailEnvelope(),
    );
    vi.spyOn(client, "getChoiceNewsEvents").mockRejectedValue(
      new Error(
        "Request failed: /ui/news/choice-events/latest because source_table choice_stock_news_event is missing.",
      ),
    );

    render(
      <AppProviders client={client}>
        <StockDetailDrawer
          stockCode="000001.SZ"
          asOfDate="2026-04-29"
          onClose={() => undefined}
        />
      </AppProviders>,
    );

    expect(await screen.findByTestId("stock-detail-chart")).toBeInTheDocument();
    expect(screen.getByTestId("stock-detail-factors")).toBeInTheDocument();
    const marketEventsError = await screen.findByTestId(
      "stock-detail-market-events-error",
    );
    expect(marketEventsError).toHaveTextContent("市场事件暂不可用");
    expect(marketEventsError).toHaveTextContent("个股复核数据不受影响");
    expect(marketEventsError).toHaveTextContent("数据源缺失");
    expect(marketEventsError).not.toHaveTextContent("Request failed");
    expect(marketEventsError).not.toHaveTextContent(
      "/ui/news/choice-events/latest",
    );
    expect(marketEventsError).not.toHaveTextContent("source_table");
    expect(marketEventsError).not.toHaveTextContent("choice_stock_news_event");
  });

  it("shows empty state when choice news returns no events", async () => {
    const client = createApiClient({ mode: "mock" });
    vi.spyOn(client, "getLivermoreStockDetail").mockResolvedValue(
      buildStockDetailEnvelope(),
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
        <StockDetailDrawer
          stockCode="000001.SZ"
          asOfDate="2026-04-29"
          onClose={() => undefined}
        />
      </AppProviders>,
    );

    const emptyState = await screen.findByTestId(
      "stock-detail-market-events-empty",
    );
    expect(emptyState).toHaveTextContent(
      "暂无与该股票代码匹配的市场事件，公告财报仍待补。",
    );
    expect(emptyState).not.toHaveTextContent("库表");
  });

  it("refetches when lookback segment changes", async () => {
    const user = userEvent.setup();
    const client = createApiClient({ mode: "mock" });
    const spy = vi
      .spyOn(client, "getLivermoreStockDetail")
      .mockResolvedValue(buildStockDetailEnvelope());

    render(
      <AppProviders client={client}>
        <StockDetailDrawer
          stockCode="000001.SZ"
          asOfDate="2026-04-29"
          onClose={() => undefined}
        />
      </AppProviders>,
    );

    await waitFor(() => expect(spy).toHaveBeenCalled());

    const firstCalls = spy.mock.calls.length;
    const seg = await screen.findByText("120");
    await user.click(seg);

    await waitFor(() =>
      expect(spy.mock.calls.length).toBeGreaterThan(firstCalls),
    );
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
          factor: {
            as_of_date: null,
            pe: null,
            pb: null,
            roe: null,
            dividend_yield: null,
          },
        },
        { basis: "analytical", quality_flag: "missing" },
      ),
    );

    render(
      <AppProviders client={client}>
        <StockDetailDrawer stockCode="000001.SZ" onClose={() => undefined} />
      </AppProviders>,
    );

    expect(
      await screen.findByTestId("stock-detail-factor-pe"),
    ).toHaveTextContent("待补");
  });

  it("shows 待补 instead of non-finite factor metrics", async () => {
    const client = createApiClient({ mode: "mock" });
    const detailSpy = vi
      .spyOn(client, "getLivermoreStockDetail")
      .mockResolvedValue(
        buildStockDetailEnvelope({
          factor: {
            pe: Number.POSITIVE_INFINITY,
            pb: Number.NEGATIVE_INFINITY,
            roe: Number.POSITIVE_INFINITY,
            dividend_yield: Number.NEGATIVE_INFINITY,
          },
        }),
      );
    vi.spyOn(client, "getLivermoreCandidateHistory").mockResolvedValue(
      buildCandidateHistoryEnvelope([]),
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
    expect(
      await screen.findByTestId("stock-detail-factor-pe"),
    ).toHaveTextContent("待补");
    expect(screen.getByTestId("stock-detail-factor-pb")).toHaveTextContent(
      "待补",
    );
    expect(screen.getByTestId("stock-detail-factor-roe")).toHaveTextContent(
      "待补",
    );
    expect(
      screen.getByTestId("stock-detail-factor-dividend"),
    ).toHaveTextContent("待补");
    expect(screen.getByTestId("stock-detail-factors")).not.toHaveTextContent(
      "Infinity",
    );
  });

  it("shows error state without breaking drawer chrome", async () => {
    const client = createApiClient({ mode: "mock" });
    vi.spyOn(client, "getLivermoreStockDetail").mockRejectedValue(
      new Error("network down"),
    );

    render(
      <AppProviders client={client}>
        <StockDetailDrawer stockCode="000001.SZ" onClose={() => undefined} />
      </AppProviders>,
    );

    expect(await screen.findByTestId("stock-detail-error")).toBeInTheDocument();
    expect(screen.getByTestId("stock-detail-error")).toHaveTextContent(
      "个股复核数据暂不可用",
    );
    expect(screen.getByTestId("stock-detail-error")).toHaveTextContent(
      "请稍后重试",
    );
    expect(screen.getByTestId("stock-detail-error")).not.toHaveTextContent(
      "network down",
    );
  });

  it("close button calls onClose", async () => {
    const user = userEvent.setup();
    const onClose = vi.fn();
    const client = createApiClient({ mode: "mock" });
    vi.spyOn(client, "getLivermoreStockDetail").mockResolvedValue(
      buildStockDetailEnvelope(),
    );

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
    const histSpy = vi
      .spyOn(client, "getLivermoreCandidateHistory")
      .mockResolvedValue(buildCandidateHistoryEnvelope(histItems));
    vi.spyOn(client, "getLivermoreStockDetail").mockResolvedValue(
      buildStockDetailEnvelope(),
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
        <StockDetailDrawer
          stockCode="000001.SZ"
          asOfDate="2026-04-29"
          onClose={() => undefined}
        />
      </AppProviders>,
    );

    await waitFor(() =>
      expect(histSpy).toHaveBeenCalledWith({
        stockCode: "000001.SZ",
        snapshotTo: "2026-04-29",
        limit: 10,
      }),
    );
    expect(
      await screen.findByTestId("stock-detail-candidate-history"),
    ).toBeInTheDocument();
    expect(screen.getByText("1.00%")).toBeInTheDocument();
    expect(screen.getByText("-2.00%")).toBeInTheDocument();
    expect(screen.getByText("8.00%")).toBeInTheDocument();
    const completeRow = screen.getByTestId(
      "stock-detail-candidate-history-row-2026-04-10-1",
    );
    expect(completeRow).toHaveTextContent("趋势突破");
    expect(completeRow).not.toHaveTextContent("livermore");
    expect(completeRow).toHaveTextContent("已成熟");
    expect(completeRow).not.toHaveTextContent("complete");
    const pendingRow = screen.getByTestId(
      "stock-detail-candidate-history-row-2026-04-03-2",
    );
    expect(pendingRow).toHaveTextContent("待成熟");
    expect(pendingRow).not.toHaveTextContent("pending");
    expect(within(pendingRow).getAllByText("—").length).toBeGreaterThanOrEqual(
      1,
    );
    const partialHaltRow = screen.getByTestId(
      "stock-detail-candidate-history-row-2026-03-27-3",
    );
    expect(partialHaltRow).toHaveTextContent("部分停牌");
    expect(partialHaltRow).not.toHaveTextContent("partial_halt");
    expect(partialHaltRow).toHaveClass(
      "stock-detail-drawer__history-row--halt",
    );
    const unknownStatusRow = screen.getByTestId(
      "stock-detail-candidate-history-row-2026-03-20-4",
    );
    expect(unknownStatusRow).toHaveTextContent("策略待确认");
    expect(unknownStatusRow).not.toHaveTextContent("experimental_signal");
    expect(unknownStatusRow).toHaveTextContent("状态待确认");
    expect(unknownStatusRow).not.toHaveTextContent("missing_forward_return");
    const sourceTableRow = screen.getByTestId(
      "stock-detail-candidate-history-row-2026-03-13-5",
    );
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
    const histSpy = vi
      .spyOn(client, "getLivermoreCandidateHistory")
      .mockResolvedValue(buildCandidateHistoryEnvelope(histItems));
    vi.spyOn(client, "getLivermoreStockDetail").mockResolvedValue(
      buildStockDetailEnvelope(),
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
        <StockDetailDrawer
          stockCode="000003.SZ"
          asOfDate="2026-04-29"
          onClose={() => undefined}
        />
      </AppProviders>,
    );

    await waitFor(() =>
      expect(histSpy).toHaveBeenCalledWith({
        stockCode: "000003.SZ",
        snapshotTo: "2026-04-29",
        limit: 10,
      }),
    );
    const row = await screen.findByTestId(
      "stock-detail-candidate-history-row-2026-04-10-1",
    );
    expect(row).not.toHaveTextContent("Infinity");
    expect(row).not.toHaveTextContent("NaN");
    expect(within(row).getAllByText("—").length).toBeGreaterThanOrEqual(3);
  });

  it("shows candidate history error without breaking chart or factors", async () => {
    const client = createApiClient({ mode: "mock" });
    vi.spyOn(client, "getLivermoreStockDetail").mockResolvedValue(
      buildStockDetailEnvelope(),
    );
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
        <StockDetailDrawer
          stockCode="000001.SZ"
          asOfDate="2026-04-29"
          onClose={() => undefined}
        />
      </AppProviders>,
    );

    expect(await screen.findByTestId("stock-detail-chart")).toBeInTheDocument();
    expect(screen.getByTestId("stock-detail-factors")).toBeInTheDocument();
    const candidateHistoryError = await screen.findByTestId(
      "stock-detail-candidate-history-error",
    );
    expect(candidateHistoryError).toHaveTextContent("入选历史暂不可用");
    expect(candidateHistoryError).toHaveTextContent("图表与因子仍可继续查看");
    expect(candidateHistoryError).toHaveTextContent("数据源缺失");
    expect(candidateHistoryError).not.toHaveTextContent("Request failed");
    expect(candidateHistoryError).not.toHaveTextContent(
      "/ui/market-data/livermore/candidate-history",
    );
    expect(candidateHistoryError).not.toHaveTextContent("source_table");
    expect(candidateHistoryError).not.toHaveTextContent(
      "choice_stock_candidate_history",
    );
  });

  it("shows empty state when candidate history has no rows", async () => {
    const client = createApiClient({ mode: "mock" });
    vi.spyOn(client, "getLivermoreCandidateHistory").mockResolvedValue(
      buildCandidateHistoryEnvelope([]),
    );
    vi.spyOn(client, "getLivermoreStockDetail").mockResolvedValue(
      buildStockDetailEnvelope(),
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
        <StockDetailDrawer
          stockCode="000001.SZ"
          asOfDate="2026-04-29"
          onClose={() => undefined}
        />
      </AppProviders>,
    );

    expect(
      await screen.findByTestId("stock-detail-candidate-history-empty"),
    ).toHaveTextContent("暂无入选快照记录");
  });
});
