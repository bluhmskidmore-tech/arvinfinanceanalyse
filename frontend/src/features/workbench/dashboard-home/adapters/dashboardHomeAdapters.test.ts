import { describe, expect, it } from "vitest";

import type {
  AssetStructurePayload,
  BondPortfolioHeadlinesPayload,
  CockpitWarningsPayload,
  DailyChangesResult,
  PortfolioComparisonPayload,
  ProductCategoryMonthlyHeadlinePayload,
  ProductCategoryYtdHeadlinePayload,
} from "../../../../api/contracts";
import { buildHomeAttributionTabs } from "./buildHomeAttributionTabs";
import { buildHomeResearchCalendarModel } from "./buildHomeResearchCalendarModel";
import { mapAssetStructureToHomeAssetBars } from "./mapAssetStructureToHomeAssetBars";
import {
  mapCockpitWarningsToRiskCards,
  mapCockpitWarningsToWatchlist,
} from "./mapCockpitWarningsToHomeRisk";
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
