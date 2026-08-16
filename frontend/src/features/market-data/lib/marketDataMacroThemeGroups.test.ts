import { describe, expect, it } from "vitest";

import type { ChoiceMacroLatestPoint, MacroVendorSeries } from "../../../api/contracts";
import {
  canRenderMacroThemeChart,
  classifyMacroThemeGroup,
  groupMacroSeriesByTheme,
} from "./marketDataMacroThemeGroups";

const SOURCE_META = {
  source_version: "sv",
  vendor_version: "vv",
  quality_flag: "ok" as const,
};

function point(
  seriesId: string,
  seriesName: string,
  unit = "%",
): ChoiceMacroLatestPoint {
  return {
    series_id: seriesId,
    series_name: seriesName,
    trade_date: "2026-06-11",
    value_numeric: 1.5,
    latest_change: 0.01,
    unit,
    source_version: SOURCE_META.source_version,
    vendor_version: SOURCE_META.vendor_version,
    recent_points: [],
  };
}

describe("marketDataMacroThemeGroups", () => {
  const catalog: MacroVendorSeries[] = [
    {
      series_id: "M001",
      series_name: "DR007",
      vendor_name: "choice",
      vendor_version: "v1",
      frequency: "daily",
      unit: "%",
      theme: "rates",
      tags: ["rates", "liquidity"],
    },
    {
      series_id: "M002",
      series_name: "沪深300收盘",
      vendor_name: "choice",
      vendor_version: "v1",
      frequency: "daily",
      unit: "点",
      theme: "equity",
      tags: ["equity", "csi300"],
    },
  ];

  it("classifies by catalog tags first", () => {
    const catalogById = new Map(catalog.map((entry) => [entry.series_id, entry]));
    expect(classifyMacroThemeGroup(point("M001", "DR007"), catalogById)).toBe("rates");
    expect(classifyMacroThemeGroup(point("M002", "沪深300收盘", "点"), catalogById)).toBe("equity");
  });

  it("falls back to name heuristics when catalog is missing", () => {
    expect(classifyMacroThemeGroup(point("X1", "10年期国债到期收益率"))).toBe("rates");
    expect(classifyMacroThemeGroup(point("X2", "沪深300指数", "点"))).toBe("equity");
    expect(classifyMacroThemeGroup(point("X3", "布伦特原油", "USD/bbl"))).toBe("commodity");
  });

  it("does not classify mis-tagged fallback macro series as rates", () => {
    const misTaggedCatalog = new Map<string, MacroVendorSeries>([
      [
        "EMM00072301",
        {
          series_id: "EMM00072301",
          series_name: "CPI:当月同比",
          vendor_name: "choice",
          vendor_version: "v1",
          frequency: "monthly",
          unit: "%",
          theme: "macro_market",
          tags: ["choice", "macro", "market", "rates", "fx"],
        },
      ],
      [
        "EMM00087081",
        {
          series_id: "EMM00087081",
          series_name: "M0",
          vendor_name: "choice",
          vendor_version: "v1",
          frequency: "monthly",
          unit: "unknown",
          theme: "macro_market",
          tags: ["choice", "macro", "market", "rates", "fx"],
        },
      ],
      [
        "EMM01280574",
        {
          series_id: "EMM01280574",
          series_name: "人民币存款准备金率:大型存款类金融机构(月)",
          vendor_name: "choice",
          vendor_version: "v1",
          frequency: "monthly",
          unit: "%",
          theme: "money_liquidity",
          tags: ["choice", "macro", "liquidity", "money"],
        },
      ],
    ]);

    expect(classifyMacroThemeGroup(point("EMM00072301", "CPI:当月同比"), misTaggedCatalog)).toBe("inflation");
    expect(classifyMacroThemeGroup(point("EMM00087081", "M0"), misTaggedCatalog)).toBe("monetary");
    expect(
      classifyMacroThemeGroup(
        point("EMM01280574", "人民币存款准备金率:大型存款类金融机构(月)"),
        misTaggedCatalog,
      ),
    ).toBe("policy");
  });

  it("enables theme charts only when at least two series have recent points", () => {
    const recentPoint = { trade_date: "2026-06-10", value_numeric: 1.1, ...SOURCE_META };
    expect(
      canRenderMacroThemeChart([
        point("A", "DR007"),
        { ...point("B", "R007"), recent_points: [recentPoint, recentPoint] },
      ]),
    ).toBe(false);
    expect(
      canRenderMacroThemeChart([
        { ...point("A", "DR007"), recent_points: [recentPoint, recentPoint] },
        { ...point("B", "R007"), recent_points: [recentPoint, recentPoint] },
      ]),
    ).toBe(true);
  });

  it("groups series into ordered theme buckets and skips empty groups", () => {
    const grouped = groupMacroSeriesByTheme(
      [
        point("M001", "DR007"),
        point("M002", "沪深300收盘", "点"),
        point("M003", "1年期国债到期收益率"),
        point("M004", "CPI:当月同比"),
      ],
      catalog,
    );

    expect(grouped.map((bucket) => bucket.key)).toEqual(["rates", "inflation", "equity"]);
    expect(grouped[0]?.series).toHaveLength(2);
    expect(grouped[1]?.series).toHaveLength(1);
    expect(grouped[2]?.series).toHaveLength(1);
  });
});
