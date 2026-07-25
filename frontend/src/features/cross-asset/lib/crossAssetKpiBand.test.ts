import { describe, expect, it } from "vitest";

import type { ResolvedCrossAssetKpi } from "./crossAssetKpiModel";
import { buildKpiBandItems, KPI_BAND_SLOTS, KPI_BAND_SPARK_LENGTH } from "./crossAssetKpiBand";

function kpiFixture(overrides: Partial<ResolvedCrossAssetKpi> & { key: string }): ResolvedCrossAssetKpi {
  return {
    label: overrides.key,
    format: "percent",
    tag: "测试",
    resolvedSeriesId: "E1000180",
    sourceKind: "choice",
    vendorName: null,
    tradeDate: "2026-03-05",
    unit: "%",
    valueLabel: "1.88%",
    changeLabel: "+1.2bp",
    changeTone: "positive",
    sparkline: [1.9, 1.88],
    ...overrides,
  };
}

function itemByKey(kpis: ResolvedCrossAssetKpi[], key: string) {
  const item = buildKpiBandItems(kpis).find((entry) => entry.key === key);
  expect(item).toBeDefined();
  return item!;
}

describe("crossAssetKpiBand", () => {
  it("固定输出 6 卡槽位与顺序", () => {
    const items = buildKpiBandItems([]);
    expect(items.map((item) => item.key)).toEqual(KPI_BAND_SLOTS.map((slot) => slot.key));
    expect(items.map((item) => item.label)).toEqual([
      "10Y国债收益率",
      "DR007",
      "沪深300指数",
      "布油(ICE)",
      "USD·CNY",
      "中美10Y利差",
    ]);
  });

  it("10Y国债收益率：下行=利好，上行=利空", () => {
    expect(itemByKey([kpiFixture({ key: "cn_gov_10y", changeLabel: "-1.2bp" })], "cn_gov_10y")).toMatchObject({
      impact: "bullish",
      impactLabel: "利好",
    });
    expect(itemByKey([kpiFixture({ key: "cn_gov_10y", changeLabel: "+1.2bp" })], "cn_gov_10y")).toMatchObject({
      impact: "bearish",
      impactLabel: "利空",
    });
  });

  it("DR007：下行=利好，上行=利空", () => {
    expect(itemByKey([kpiFixture({ key: "money_market_7d", changeLabel: "-3.0bp" })], "money_market_7d").impact).toBe(
      "bullish",
    );
    expect(itemByKey([kpiFixture({ key: "money_market_7d", changeLabel: "+2.0bp" })], "money_market_7d").impact).toBe(
      "bearish",
    );
  });

  it("沪深300指数与 USD·CNY：任意方向恒中性", () => {
    expect(itemByKey([kpiFixture({ key: "csi300", changeLabel: "+12.3点" })], "csi300").impact).toBe("neutral");
    expect(itemByKey([kpiFixture({ key: "csi300", changeLabel: "-8.1点" })], "csi300").impact).toBe("neutral");
    expect(itemByKey([kpiFixture({ key: "usdcny", changeLabel: "+0.0012" })], "usdcny").impact).toBe("neutral");
    expect(itemByKey([kpiFixture({ key: "usdcny", changeLabel: "-0.0300" })], "usdcny").impact).toBe("neutral");
  });

  it("布油：上行=利空，下行=利好", () => {
    expect(itemByKey([kpiFixture({ key: "brent", changeLabel: "+0.85" })], "brent").impact).toBe("bearish");
    expect(itemByKey([kpiFixture({ key: "brent", changeLabel: "-0.85" })], "brent").impact).toBe("bullish");
  });

  it("中美10Y利差：上行(收窄)=利好，下行(走阔)=利空", () => {
    expect(
      itemByKey([kpiFixture({ key: "gov_spread", label: "中美10Y利差", changeLabel: "+2.5bp" })], "gov_spread"),
    ).toMatchObject({ impact: "bullish", impactLabel: "利好" });
    expect(
      itemByKey([kpiFixture({ key: "gov_spread", label: "中美10Y利差", changeLabel: "-2.5bp" })], "gov_spread"),
    ).toMatchObject({ impact: "bearish", impactLabel: "利空" });
  });

  it("无变动（—/无符号）归为中性", () => {
    expect(itemByKey([kpiFixture({ key: "cn_gov_10y", changeLabel: "—" })], "cn_gov_10y").impact).toBe("neutral");
    expect(itemByKey([kpiFixture({ key: "gov_spread", changeLabel: "0.0bp" })], "gov_spread").impact).toBe("neutral");
  });

  it("sparkline 只取最近 20 点", () => {
    const sparkline = Array.from({ length: 25 }, (_, index) => index);
    const item = itemByKey([kpiFixture({ key: "cn_gov_10y", sparkline })], "cn_gov_10y");
    expect(item.spark).toHaveLength(KPI_BAND_SPARK_LENGTH);
    expect(item.spark).toEqual(sparkline.slice(-KPI_BAND_SPARK_LENGTH));
    expect(KPI_BAND_SPARK_LENGTH).toBe(20);
  });

  it("sparkline 不足 20 点时原样保留", () => {
    const item = itemByKey([kpiFixture({ key: "brent", sparkline: [80, 81, 82] })], "brent");
    expect(item.spark).toEqual([80, 81, 82]);
  });

  it("null/undefined/空数组输入降级为 6 张占位卡", () => {
    for (const input of [null, undefined, []]) {
      const items = buildKpiBandItems(input);
      expect(items).toHaveLength(6);
      for (const item of items) {
        expect(item).toMatchObject({
          valueLabel: "—",
          unit: "",
          changeLabel: "—",
          impact: "neutral",
          impactLabel: "中性",
          sourceLabel: "待接入",
          dateLabel: "—",
          spark: [],
        });
      }
    }
  });

  it("缺数据 KPI（— 标签、null 日期、missing 来源）null 安全", () => {
    const item = itemByKey(
      [
        kpiFixture({
          key: "gov_spread",
          label: "中美10Y利差",
          sourceKind: "missing",
          resolvedSeriesId: "gov_spread:missing",
          tradeDate: null,
          unit: null,
          valueLabel: "—",
          changeLabel: "—",
          changeTone: "default",
          sparkline: [],
        }),
      ],
      "gov_spread",
    );
    expect(item).toMatchObject({
      valueLabel: "—",
      unit: "",
      changeLabel: "—",
      impact: "neutral",
      sourceLabel: "待接入",
      dateLabel: "—",
      spark: [],
    });
  });

  it("日期格式化为 MM-DD", () => {
    expect(itemByKey([kpiFixture({ key: "cn_gov_10y", tradeDate: "2026-03-05" })], "cn_gov_10y").dateLabel).toBe(
      "03-05",
    );
    expect(itemByKey([kpiFixture({ key: "cn_gov_10y", tradeDate: "2026-12-31" })], "cn_gov_10y").dateLabel).toBe(
      "12-31",
    );
    expect(itemByKey([kpiFixture({ key: "cn_gov_10y", tradeDate: null })], "cn_gov_10y").dateLabel).toBe("—");
  });

  it("valueLabel 拆分为数值与单位", () => {
    expect(itemByKey([kpiFixture({ key: "cn_gov_10y", valueLabel: "1.88%" })], "cn_gov_10y")).toMatchObject({
      valueLabel: "1.88",
      unit: "%",
    });
    expect(
      itemByKey([kpiFixture({ key: "gov_spread", valueLabel: "45bp", format: "bp", unit: "bp" })], "gov_spread"),
    ).toMatchObject({ valueLabel: "45", unit: "bp" });
    expect(
      itemByKey(
        [kpiFixture({ key: "csi300", valueLabel: "4102.3点", format: "index", unit: "point", changeLabel: "+1.2点" })],
        "csi300",
      ),
    ).toMatchObject({ valueLabel: "4102.3", unit: "点" });
    expect(
      itemByKey([kpiFixture({ key: "usdcny", valueLabel: "7.1234", format: "fx", unit: null })], "usdcny"),
    ).toMatchObject({ valueLabel: "7.1234", unit: "" });
  });

  it("来源标签按槽位与实际 sourceKind 修正", () => {
    expect(itemByKey([kpiFixture({ key: "cn_gov_10y", sourceKind: "choice" })], "cn_gov_10y").sourceLabel).toBe(
      "中债估值",
    );
    expect(itemByKey([kpiFixture({ key: "cn_gov_10y", sourceKind: "public" })], "cn_gov_10y").sourceLabel).toBe(
      "公共补充",
    );
    expect(
      itemByKey([kpiFixture({ key: "money_market_7d", sourceKind: "public", resolvedSeriesId: "CA.DR007" })], "money_market_7d")
        .sourceLabel,
    ).toBe("公共补充");
    expect(itemByKey([kpiFixture({ key: "money_market_7d", sourceKind: "choice" })], "money_market_7d").sourceLabel).toBe(
      "Choice",
    );
    expect(
      itemByKey([kpiFixture({ key: "gov_spread", label: "中美10Y利差", sourceKind: "derived" })], "gov_spread").sourceLabel,
    ).toBe("中债+UST");
    expect(
      itemByKey([kpiFixture({ key: "gov_spread", label: "国开-国债10Y", sourceKind: "derived" })], "gov_spread").sourceLabel,
    ).toBe("中债口径");
  });
});
