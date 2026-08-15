import { describe, expect, it } from "vitest";

import type { ChoiceMacroLatestPoint } from "../../../api/contracts";
import { mapMarketSeries, mapMarketTape } from "./dashboardHomeMarket";

function point(
  overrides: Partial<ChoiceMacroLatestPoint> = {},
): ChoiceMacroLatestPoint {
  return {
    series_id: "CA.DR007",
    series_name: "DR007",
    trade_date: "2026-07-29",
    value_numeric: 1.42,
    unit: "%",
    latest_change: 0.02,
    source_version: "sv1",
    vendor_version: "vv1",
    vendor_name: "public_repo_rate_query",
    refresh_tier: "stable",
    quality_flag: "ok",
    policy_note:
      "public fallback headline lane via repo_rate_query FDR007; not the exact Choice weighted interbank lending 7D series",
    recent_points: [],
    ...overrides,
  };
}

describe("mapMarketTape", () => {
  it("uses sorted real recent_points for sparkline values", () => {
    const rows = mapMarketTape([
      point({
        recent_points: [
          {
            trade_date: "2026-07-29",
            value_numeric: 1.42,
            source_version: "sv1",
            vendor_version: "vv1",
            quality_flag: "ok",
          },
          {
            trade_date: "2026-07-27",
            value_numeric: 1.38,
            source_version: "sv1",
            vendor_version: "vv1",
            quality_flag: "ok",
          },
          {
            trade_date: "2026-07-28",
            value_numeric: 1.4,
            source_version: "sv1",
            vendor_version: "vv1",
            quality_flag: "ok",
          },
        ],
      }),
    ]);

    expect(rows[0]?.sparkline).toEqual([1.38, 1.4, 1.42]);
    expect(rows[0]).toMatchObject({
      id: "CA.DR007",
      tradeDate: "2026-07-29",
      valueNumeric: 1.42,
      unit: "%",
      qualityFlag: "ok",
      vendorName: "public_repo_rate_query",
    });
  });

  it("falls back to two real endpoints when only latest_change exists", () => {
    const rows = mapMarketTape([
      point({
        value_numeric: 1.42,
        latest_change: 0.02,
        recent_points: [],
      }),
    ]);

    expect(rows[0]?.sparkline).toEqual([1.4, 1.42]);
  });

  it("does not fabricate a sparkline without history or change", () => {
    const rows = mapMarketTape([
      point({
        latest_change: null,
        recent_points: [],
      }),
    ]);

    expect(rows[0]?.sparkline).toEqual([]);
  });

  it("does not relabel SHIBOR aliases as DR007 or R007", () => {
    const rows = mapMarketTape([
      point({
        series_id: "EMM00167613",
        series_name: "SHIBOR 3M",
        value_numeric: 1.42,
      }),
      point({
        series_id: "EMM00167614",
        series_name: "SHIBOR 6M",
        value_numeric: 1.47,
      }),
    ]);

    expect(rows.map((row) => row.label)).toEqual(["SHIBOR 3M", "SHIBOR 6M"]);
    expect(rows.some((row) => row.label === "DR007")).toBe(false);
    expect(rows.some((row) => row.label === "R007")).toBe(false);
  });

  it("keeps exact M002 in the deterministic DR007 priority lane", () => {
    const rows = mapMarketTape([
      point({
        series_id: "M002",
        series_name: "银行间质押式回购 7D",
      }),
    ]);

    expect(rows[0]).toMatchObject({
      id: "M002",
      label: "DR007",
    });
  });

  it("labels EM1 as the CN-US 10Y spread with the two-leg basis in the title", () => {
    const rows = mapMarketTape([
      point({
        series_id: "EM1",
        series_name: "中美国债利差(10Y)",
        value_numeric: -296.59,
        unit: "bp",
        latest_change: 1.8,
      }),
    ]);

    expect(rows[0]).toMatchObject({
      id: "EM1",
      label: "中美10年利差",
      title: "中美10年利差 = 中债10Y − 美债10Y（bp，预计算序列）",
    });
    expect(rows[0]?.label).not.toContain("1Y-10Y");
  });

  it("annotates the 10Y CGB tape row as the realtime feed lane", () => {
    const rows = mapMarketTape([
      point({
        series_id: "E1000180",
        series_name: "中债国债到期收益率:10年",
        value_numeric: 1.7141,
      }),
    ]);

    expect(rows[0]?.label).toBe("10年国债");
    expect(rows[0]?.title).toContain("实时行情快讯源");
    expect(rows[0]?.title).toContain("报告日正式链路");
  });

  it("shows 持平 for a zero-formatted delta and keeps the raw string in deltaTitle", () => {
    const rows = mapMarketTape([
      point({
        series_id: "EMM00058124",
        series_name: "中间价:美元兑人民币",
        value_numeric: 6.79,
        unit: "CNY/USD",
        latest_change: 0.0016,
      }),
    ]);

    expect(rows[0]).toMatchObject({
      id: "EMM00058124",
      label: "人民币汇率",
      value: "6.79CNY/USD",
      delta: "持平",
      deltaTone: "flat",
      deltaTitle: "+0CNY/USD",
    });
  });

  it("drops the textual unit from a non-zero delta and discloses the full string in deltaTitle", () => {
    const rows = mapMarketTape([
      point({
        series_id: "EMM00058124",
        series_name: "中间价:美元兑人民币",
        value_numeric: 6.82,
        unit: "CNY/USD",
        latest_change: 0.03,
      }),
    ]);

    expect(rows[0]).toMatchObject({
      value: "6.82CNY/USD",
      delta: "+0.03",
      deltaTone: "up",
      deltaTitle: "+0.03CNY/USD",
    });
  });

  it("keeps the full stable series for context panels without changing the compact tape", () => {
    const points = [
      ...Array.from({ length: 8 }, (_, index) =>
        point({
          series_id: `TEST.${index + 1}`,
          series_name: `测试序列 ${index + 1}`,
        }),
      ),
      point({
        series_id: "EMM00166502",
        series_name: "10年国开债",
      }),
      point({
        series_id: "TEST.ISOLATED",
        series_name: "隔离序列",
        refresh_tier: "isolated",
      }),
    ];

    expect(mapMarketTape(points)).toHaveLength(8);
    expect(mapMarketTape(points).some((row) => row.id === "EMM00166502")).toBe(
      false,
    );
    expect(mapMarketSeries(points).map((row) => row.id)).toContain(
      "EMM00166502",
    );
    expect(mapMarketSeries(points).some((row) => row.id === "TEST.ISOLATED")).toBe(
      false,
    );
  });
});
