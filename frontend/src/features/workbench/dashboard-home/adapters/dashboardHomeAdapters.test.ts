import { describe, expect, it } from "vitest";

import type {
  AssetStructurePayload,
  BondPortfolioHeadlinesPayload,
  CockpitWarningsPayload,
  ChoiceNewsEvent,
  DailyChangesResult,
  PortfolioComparisonPayload,
  ProductCategoryMonthlyHeadlinePayload,
  ProductCategoryYtdHeadlinePayload,
  YieldDistributionPayload,
} from "../../../../api/contracts";
import { buildHomeAttributionTabs } from "./buildHomeAttributionTabs";
import { buildHomeBondNewsModel } from "./buildHomeBondNewsModel";
import { buildHomeResearchCalendarModel } from "./buildHomeResearchCalendarModel";
import { mapAssetStructureToHomeAssetBars } from "./mapAssetStructureToHomeAssetBars";
import {
  mapCockpitWarningsToRiskCards,
  mapCockpitWarningsToWatchlist,
} from "./mapCockpitWarningsToHomeRisk";
import { mapHomeSummaryDistributions } from "./mapHomeSummaryDistributions";
import { mapHomeRiskRadar } from "./mapHomeRiskRadar";
import { mapPortfolioComparisonToExposureRows } from "./mapPortfolioComparisonToExposureRows";
import { buildRiskRadarFromRiskItems } from "./riskRadarFromRiskItems";

function numeric(raw: number, display: string, unit: "yuan" | "pct" | "bp" | "ratio" | "dv01" | "yi" = "yuan") {
  return {
    raw,
    unit,
    display,
    precision: 2,
    sign_aware: false,
  };
}

function newsEvent(
  partial: Partial<ChoiceNewsEvent> &
    Pick<ChoiceNewsEvent, "event_key" | "received_at" | "topic_code" | "payload_text">,
): ChoiceNewsEvent {
  return {
    group_id: "tushare_news",
    content_type: "news",
    serial_id: 1,
    request_id: 1,
    error_code: 0,
    error_msg: "",
    item_index: 0,
    payload_json: null,
    ...partial,
  };
}

describe("dashboard-home adapter helpers", () => {
  it("maps asset structure percentages and merges the tail bucket", () => {
    const payload: AssetStructurePayload = {
      report_date: "2026-04-30",
      group_by: "bond_type",
      total_market_value: numeric(50_000_000_000, "500.00 yi"),
      items: [
        { category: "gov", total_market_value: numeric(20_000_000_000, "200.00 yi"), bond_count: 10, percentage: numeric(0.4, "40%", "pct") },
        { category: "policy", total_market_value: numeric(15_000_000_000, "150.00 yi"), bond_count: 8, percentage: numeric(0.3, "30%", "pct") },
        { category: "credit", total_market_value: numeric(10_000_000_000, "100.00 yi"), bond_count: 6, percentage: numeric(0.2, "20%", "pct") },
        { category: "ncd", total_market_value: numeric(3_000_000_000, "30.00 yi"), bond_count: 2, percentage: numeric(0.06, "6%", "pct") },
        { category: "abs", total_market_value: numeric(2_000_000_000, "20.00 yi"), bond_count: 1, percentage: numeric(0.04, "4%", "pct") },
      ],
    };

    const { bars, hasData } = mapAssetStructureToHomeAssetBars(payload, "2026-04-30", 3);

    expect(hasData).toBe(true);
    expect(bars).toHaveLength(4);
    expect(bars[0]?.label).toBe("gov");
    expect(bars[0]?.pct).toBe(40);
    expect(bars[3]?.pct).toBeCloseTo(10, 1);
  });

  it("maps home summary distributions without inventing missing percentages", () => {
    const assetPayload: AssetStructurePayload = {
      report_date: "2026-04-30",
      group_by: "bond_type",
      total_market_value: numeric(20_000_000_000, "200.00 yi"),
      items: [
        {
          category: "credit",
          total_market_value: numeric(12_000_000_000, "120.00 yi"),
          bond_count: 4,
          percentage: numeric(0.6, "60%", "pct"),
        },
      ],
    };
    const yieldPayload: YieldDistributionPayload = {
      report_date: "2026-04-30",
      weighted_ytm: numeric(0.028, "2.80%", "pct"),
      items: [
        {
          yield_bucket: "2.5%-3.0%",
          total_market_value: numeric(12_000_000_000, "120.00 yi"),
          bond_count: 4,
        },
      ],
    };

    const sections = mapHomeSummaryDistributions({
      report_date: "2026-04-30",
      asset_type: assetPayload,
      yield_distribution: yieldPayload,
    });

    const assetSection = sections.find((section) => section.key === "asset_type");
    const yieldSection = sections.find((section) => section.key === "yield_distribution");

    expect(assetSection?.rows[0]).toMatchObject({
      label: "credit",
      valueRaw: 12_000_000_000,
      valueDisplay: "120.00 yi",
      percentageRaw: 0.6,
      percentageDisplay: "60%",
      count: 4,
    });
    expect(yieldSection?.rows[0]).toMatchObject({
      label: "2.5%-3.0%",
      valueDisplay: "120.00 yi",
      percentageRaw: null,
      count: 4,
    });
  });

  it("builds attribution tabs from daily changes and product-category headlines", () => {
    const ytd: ProductCategoryYtdHeadlinePayload = {
      view: "ytd",
      summary_pnl: numeric(-100, "-100 wan"),
      summary_pnl_detail: "YTD detail",
      operating_income: numeric(0, "0"),
      operating_income_detail: "",
      intermediate_business_income: numeric(0, "0"),
      intermediate_business_income_detail: "",
    };
    const monthly: ProductCategoryMonthlyHeadlinePayload = {
      view: "monthly",
      monthly_income: numeric(50, "+50 wan"),
      monthly_income_detail: "monthly detail",
    };
    const dailyChanges: DailyChangesResult = {
      report_date: "2026-04-30",
      periods: [
        { period: "day", bond_investments_change: numeric(0, "0"), interbank_assets_change: numeric(0, "0"), interbank_liabilities_change: numeric(0, "0"), net_change: numeric(1, "+1 wan") },
        { period: "week", bond_investments_change: numeric(0, "0"), interbank_assets_change: numeric(0, "0"), interbank_liabilities_change: numeric(0, "0"), net_change: numeric(2, "+2 wan") },
        { period: "month", bond_investments_change: numeric(0, "0"), interbank_assets_change: numeric(0, "0"), interbank_liabilities_change: numeric(0, "0"), net_change: numeric(3, "+3 wan") },
      ],
    };

    const tabs = buildHomeAttributionTabs({
      reportDate: "2026-04-30",
      attribution: { title: "attr", total: numeric(-10, "-10 wan"), segments: [] },
      dailyChanges,
      productCategoryYtd: ytd,
      productCategoryMonthly: monthly,
    });

    expect(tabs.find((tab) => tab.id === "day")?.change).toBe("+1 wan");
    expect(tabs.find((tab) => tab.id === "month")?.pnl).toBe("+50 wan");
    expect(tabs.find((tab) => tab.id === "ytd")?.pnl).toBe("-100 wan");
  });

  it("maps portfolio comparison rows with computed weights", () => {
    const payload: PortfolioComparisonPayload = {
      report_date: "2026-04-30",
      items: [
        { portfolio_name: "book-a", total_market_value: numeric(30_000_000_000, "300.00 yi"), weighted_ytm: numeric(0.03, "3%", "pct"), weighted_duration: numeric(4.2, "4.20", "ratio"), total_dv01: numeric(1_000_000, "100.00 wan", "dv01"), bond_count: 12 },
        { portfolio_name: "book-b", total_market_value: numeric(10_000_000_000, "100.00 yi"), weighted_ytm: numeric(0.025, "2.5%", "pct"), weighted_duration: numeric(3.1, "3.10", "ratio"), total_dv01: numeric(500_000, "50.00 wan", "dv01"), bond_count: 6 },
      ],
    };

    const { rows, hasData } = mapPortfolioComparisonToExposureRows(payload, "2026-04-30");

    expect(hasData).toBe(true);
    expect(rows[0]?.weight).toBe("75.00%");
    expect(rows[1]?.dailyPnl).toBe("—");
  });

  it("keeps risk radar pending until enough usable risk items exist", () => {
    const { radar, usesMock } = buildRiskRadarFromRiskItems(
      [{ id: "dv01", label: "duration risk", value: "50", hint: "", level: 50, status: "landed", tone: "warning" }],
      false,
    );

    expect(usesMock).toBe(false);
    expect(radar.pending).toBe(true);
  });

  it("derives risk radar dimensions from portfolio headlines", () => {
    const portfolio: BondPortfolioHeadlinesPayload = {
      report_date: "2026-04-30",
      total_market_value: numeric(1, "1 yi", "yi"),
      weighted_ytm: numeric(0.03, "3%", "pct"),
      weighted_duration: numeric(4.5, "4.50", "ratio"),
      weighted_coupon: numeric(0.03, "3%", "pct"),
      total_dv01: numeric(150_000_000, "15,000.00 wan", "dv01"),
      bond_count: 100,
      credit_weight: numeric(0.35, "35%", "pct"),
      issuer_hhi: numeric(0.1, "0.10", "ratio"),
      issuer_top5_weight: numeric(0.45, "45%", "pct"),
      by_asset_class: [],
      warnings: [],
      computed_at: "2026-04-30T00:00:00Z",
    };

    const radar = mapHomeRiskRadar(portfolio, "2026-04-30");

    expect(radar.placeholder).toBe(false);
    expect(radar.dimensions.length).toBeGreaterThanOrEqual(3);
  });

  it("builds research calendar states", () => {
    const empty = buildHomeResearchCalendarModel({
      events: [],
      isLoading: false,
      isError: false,
      startDate: "2026-04-23",
      endDate: "2026-05-14",
    });
    const ready = buildHomeResearchCalendarModel({
      events: [
        { id: "high", date: "2026-04-24", title: "high", kind: "supply", severity: "high" },
        { id: "low", date: "2026-04-25", title: "low", kind: "auction", severity: "low" },
        { id: "mid", date: "2026-04-26", title: "mid", kind: "supply", severity: "medium" },
      ],
      isLoading: false,
      isError: false,
      startDate: "2026-04-23",
      endDate: "2026-05-14",
    });

    expect(empty.status).toBe("empty");
    expect(ready.status).toBe("ready");
    expect(ready.items.map((item) => item.id)).toEqual(["high", "mid"]);
  });

  it("explains bond news source returns that do not pass the bond filter", () => {
    const model = buildHomeBondNewsModel({
      todayIsoDate: "2026-06-01",
      events: [
        newsEvent({
          event_key: "broad-equity",
          received_at: "2026-06-01T12:00:00+08:00",
          topic_code: "tushare.news.sina",
          payload_text: "A股市场成交额放大，科技板块走强。",
        }),
        newsEvent({
          event_key: "commodity",
          received_at: "2026-06-01T11:50:00+08:00",
          topic_code: "tushare.major_news",
          payload_text: "国际油价震荡上行。",
        }),
      ],
    });

    expect(model.holdingHits).toHaveLength(0);
    expect(model.marketNews).toHaveLength(0);
    expect(model.creditAndIssuanceNews).toHaveLength(0);
    expect(model.asOfLabel).toBe("已查询至 06-01 12:00");
    expect(model.statusLabel).toBe("来源状态：未命中债券相关内容");
    expect(model.holdingMessage).toBe("持仓命中：已查询 2 条新闻，未命中当前持仓或发行人。");
    expect(model.marketMessage).toBe("债券市场：已查询 2 条新闻，未筛出债券市场相关内容。");
    expect(model.creditMessage).toBe("发行/评级：已查询 2 条新闻，未筛出债券发行或评级内容。");
  });

  it("maps cockpit warnings to watchlist and risk counts", () => {
    const payload: CockpitWarningsPayload = {
      report_date: "2026-04-30",
      watch_items: [{ id: "w1", label: "liability cost", level: "warning", detail: "detail" }],
      alert_events: [{ id: "a1", severity: "high", title: "alert", occurred_at: "2026-04-30", detail: "detail" }],
    };

    const watchlist = mapCockpitWarningsToWatchlist(payload, "2026-04-30");
    const riskCards = mapCockpitWarningsToRiskCards(payload, "2026-04-30");

    expect(watchlist.hasData).toBe(true);
    expect(riskCards.cards.find((card) => card.id === "high")?.count).toBe(1);
  });
});
