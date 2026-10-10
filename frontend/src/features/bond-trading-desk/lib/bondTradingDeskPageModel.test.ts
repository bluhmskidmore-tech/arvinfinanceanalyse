import { describe, expect, it } from "vitest";

import type { BondPositionItem, BondTopHoldingItem, CreditSpreadDetailBondRow, Numeric } from "../../../api/contracts";
import { EM_DASH } from "../../../pageModel";
import { formatRawAsNumeric } from "../../../utils/format";
import {
  buildBondTradingDeskComposeResult,
  buildBondTradingDeskPageModel,
  buildBondTradingDeskPath,
  codesMatch,
  formatComposeMetaNote,
  resolveBondSnapshot,
} from "./bondTradingDeskPageModel";

const yuan = (raw: number) => formatRawAsNumeric({ raw, unit: "yuan", sign_aware: false });
const pct = (raw: number) => formatRawAsNumeric({ raw, unit: "pct", sign_aware: false });
const years = (raw: number) => formatRawAsNumeric({ raw, unit: "years", sign_aware: false });

/** 重仓券契约：ytm 为 governed Numeric，display 已是百分点文案。 */
const ytmNumeric = (display: string, raw = 0.0245): Numeric => ({
  raw,
  unit: "pct",
  display,
  precision: 2,
  sign_aware: true,
});

const weightNumeric = (display: string, raw = 0.035): Numeric => ({
  raw,
  unit: "ratio",
  display,
  precision: 4,
  sign_aware: false,
});

function tileValue(
  model: ReturnType<typeof buildBondTradingDeskPageModel>,
  key: string,
): string {
  return model.metricTiles.find((tile) => tile.key === key)?.value ?? "";
}

function positionItem(overrides: Partial<BondPositionItem> = {}): BondPositionItem {
  return {
    bond_code: "149001.SZ",
    credit_name: "测试券",
    sub_type: "公司债",
    asset_class: "credit",
    market_value: "120000000",
    face_value: "100000000",
    valuation_net_price: "102.3",
    yield_rate: "0.0310",
    ...overrides,
  };
}

function spreadRow(overrides: Partial<CreditSpreadDetailBondRow> = {}): CreditSpreadDetailBondRow {
  return {
    instrument_code: "149003.IB",
    instrument_name: "利差样例",
    rating: "AA+",
    tenor_bucket: "3Y",
    ytm: "3.10000000",
    benchmark_yield: "2.10",
    credit_spread: "110bp",
    spread_duration: "2.0",
    spread_dv01: "1200",
    market_value: "5.00",
    weight: "0.05088252",
    ...overrides,
  };
}

function topHolding(overrides: Partial<BondTopHoldingItem> = {}): BondTopHoldingItem {
  return {
    instrument_code: "230210.IB",
    instrument_name: "23国开10",
    issuer_name: "国开行",
    rating: "AAA",
    asset_class: "rate",
    market_value: yuan(1_200_000_000),
    face_value: yuan(1_000_000_000),
    ytm: ytmNumeric("2.45%"),
    modified_duration: years(4.2),
    weight: weightNumeric("3.50%", 0.035),
    ...overrides,
  };
}

describe("bondTradingDeskPageModel", () => {
  it("builds deep link path with bond_code and report_date", () => {
    expect(buildBondTradingDeskPath("230210.IB", "2026-04-30")).toBe(
      "/bond-trading-desk?bond_code=230210.IB&report_date=2026-04-30",
    );
  });

  it("prefers top holdings row when bond_code matches instrument_code", () => {
    const snapshot = resolveBondSnapshot({
      bondCode: "230210.ib",
      topHoldings: [
        {
          instrument_code: "230210.IB",
          instrument_name: "23国开10",
          issuer_name: "国开行",
          rating: "AAA",
          asset_class: "rate",
          market_value: yuan(1_200_000_000),
          face_value: yuan(1_000_000_000),
          ytm: pct(2.45),
          modified_duration: years(4.2),
          weight: pct(3.5),
        },
      ],
      positions: [],
      creditSpreadRows: [],
    });

    expect(snapshot?.coverageSource).toBe("top_holdings");
    expect(snapshot?.bondName).toBe("23国开10");
    expect(codesMatch("230210.IB", "230210.ib")).toBe(true);
  });

  it("falls back to positions list when not in top holdings", () => {
    const snapshot = resolveBondSnapshot({
      bondCode: "149001.SZ",
      topHoldings: [],
      positions: [
        {
          bond_code: "149001.SZ",
          credit_name: "测试券",
          sub_type: "公司债",
          asset_class: "credit",
          market_value: "120000000",
          face_value: "100000000",
          valuation_net_price: "102.3",
          yield_rate: "0.0310",
        },
      ],
      creditSpreadRows: [],
    });

    expect(snapshot?.coverageSource).toBe("positions");
    expect(snapshot?.valuationNetPrice).toBe("102.3");
  });

  it("merges credit spread fields when spread row exists", () => {
    const snapshot = resolveBondSnapshot({
      bondCode: "149002.IB",
      topHoldings: [
        {
          instrument_code: "149002.IB",
          instrument_name: "信用样例",
          issuer_name: "主体A",
          rating: "AA+",
          asset_class: "credit",
          market_value: yuan(500_000_000),
          face_value: yuan(500_000_000),
          ytm: pct(3.2),
          modified_duration: years(2.1),
          weight: pct(1.2),
        },
      ],
      positions: [],
      creditSpreadRows: [
        {
          instrument_code: "149002.IB",
          instrument_name: "信用样例",
          rating: "AA+",
          tenor_bucket: "3Y",
          ytm: "3.20",
          benchmark_yield: "2.10",
          credit_spread: "110bp",
          spread_duration: "2.0",
          spread_dv01: "1200",
          market_value: "5.00",
          weight: "1.20",
        },
      ],
    });

    expect(snapshot?.creditSpread).toBe("110bp");
    expect(snapshot?.coverageNote).toContain("利差字段");
  });

  it("appends quality notes from result_meta to compose source detail", () => {
    expect(
      formatComposeMetaNote({
        trace_id: "tr",
        basis: "formal",
        result_kind: "positions.bonds.list",
        formal_use_allowed: false,
        source_version: "sv",
        vendor_version: "vv",
        rule_version: "rv",
        cache_version: "cv",
        quality_flag: "warning",
        vendor_status: "ok",
        fallback_mode: "latest_snapshot",
        scenario_flag: false,
        generated_at: "2026-04-30T00:00:00Z",
      }),
    ).toContain("quality=warning");
  });

  it("marks partial compose when one source fails", () => {
    const composed = buildBondTradingDeskComposeResult({
      bondCode: "230210.IB",
      reportDate: "2026-04-30",
      topHoldings: [
        {
          instrument_code: "230210.IB",
          instrument_name: "23国开10",
          issuer_name: "国开行",
          rating: "AAA",
          asset_class: "rate",
          market_value: yuan(1_200_000_000),
          face_value: yuan(1_000_000_000),
          ytm: pct(2.45),
          modified_duration: years(4.2),
          weight: pct(3.5),
        },
      ],
      positions: [],
      creditSpreadRows: [],
      positionChanges: [],
      sourceSettled: {
        topHoldings: { status: "fulfilled", value: {} },
        positions: { status: "rejected", reason: new Error("positions down") },
        creditSpread: { status: "fulfilled", value: {} },
        positionChanges: { status: "fulfilled", value: {} },
      },
    });

    expect(composed.partialFailure).toBe(true);
    expect(composed.sourceStatuses.find((item) => item.key === "positions")?.status).toBe("failed");
    expect(composed.model.snapshot?.bondName).toBe("23国开10");
  });

  it("builds empty conclusion when bond not found in lookup scope", () => {
    const model = buildBondTradingDeskPageModel({
      bondCode: "999999.IB",
      reportDate: "2026-04-30",
      topHoldings: [],
      positions: [],
      creditSpreadRows: [],
      positionChanges: [],
    });

    expect(model.snapshot).toBeNull();
    expect(model.conclusion.title).toBe("未在当前查找范围命中");
    expect(model.gapSections[0]?.status).toBe("not_in_portfolio");
  });

  it("locks unmatched metric tiles to the shared EM_DASH placeholder", () => {
    const model = buildBondTradingDeskPageModel({
      bondCode: "999999.IB",
      reportDate: "2026-04-30",
      topHoldings: [],
      positions: [],
      creditSpreadRows: [],
      positionChanges: [],
    });

    expect(model.metricTiles.map((tile) => [tile.key, tile.label, tile.value, tile.caption])).toEqual([
      ["market_value", "市值", EM_DASH, ""],
      ["weight", "组合权重", EM_DASH, ""],
      ["ytm", "YTM", EM_DASH, ""],
      ["duration", "修正久期", EM_DASH, ""],
      ["credit_spread", "信用利差", EM_DASH, ""],
      ["net_price", "估值净价", EM_DASH, ""],
    ]);
  });

  it("formats top-holdings Numeric ytm via the governed display path", () => {
    const model = buildBondTradingDeskPageModel({
      bondCode: "230210.IB",
      reportDate: "2026-04-30",
      topHoldings: [topHolding()],
      positions: [],
      creditSpreadRows: [],
      positionChanges: [],
    });

    expect(model.snapshot?.coverageSource).toBe("top_holdings");
    expect(tileValue(model, "ytm")).toBe("2.45%");
    expect(tileValue(model, "weight")).toBe("3.50%");
  });

  it("formats positions yield_rate decimal string as percent points", () => {
    const model = buildBondTradingDeskPageModel({
      bondCode: "149001.SZ",
      reportDate: "2026-04-30",
      topHoldings: [],
      positions: [positionItem({ yield_rate: "0.0310" })],
      creditSpreadRows: [],
      positionChanges: [],
    });

    expect(model.snapshot?.coverageSource).toBe("positions");
    expect(tileValue(model, "ytm")).toBe("3.10%");
  });

  it("formats credit-spread ytm percent-point string without rescaling", () => {
    const model = buildBondTradingDeskPageModel({
      bondCode: "149003.IB",
      reportDate: "2026-04-30",
      topHoldings: [],
      positions: [],
      creditSpreadRows: [spreadRow({ ytm: "3.10000000", weight: "0.05088252" })],
      positionChanges: [],
    });

    expect(model.snapshot?.coverageSource).toBe("credit_spread");
    expect(tileValue(model, "ytm")).toBe("3.10%");
    expect(tileValue(model, "weight")).toBe("5.09%");
  });

  it("fills missing position weight from credit-spread ratio string", () => {
    const model = buildBondTradingDeskPageModel({
      bondCode: "149001.SZ",
      reportDate: "2026-04-30",
      topHoldings: [],
      positions: [positionItem({ bond_code: "149001.SZ", yield_rate: "0.0310" })],
      creditSpreadRows: [spreadRow({ instrument_code: "149001.SZ", weight: "0.05088252" })],
      positionChanges: [],
    });

    expect(model.snapshot?.coverageSource).toBe("positions");
    expect(tileValue(model, "ytm")).toBe("3.10%");
    expect(tileValue(model, "weight")).toBe("5.09%");
  });

  it("renders null or empty ytm and weight as EM_DASH", () => {
    const nullModel = buildBondTradingDeskPageModel({
      bondCode: "149001.SZ",
      reportDate: "2026-04-30",
      topHoldings: [],
      positions: [positionItem({ yield_rate: null })],
      creditSpreadRows: [],
      positionChanges: [],
    });
    expect(tileValue(nullModel, "ytm")).toBe(EM_DASH);
    expect(tileValue(nullModel, "weight")).toBe(EM_DASH);

    const emptyModel = buildBondTradingDeskPageModel({
      bondCode: "149001.SZ",
      reportDate: "2026-04-30",
      topHoldings: [],
      positions: [positionItem({ yield_rate: "" })],
      creditSpreadRows: [],
      positionChanges: [],
    });
    expect(tileValue(emptyModel, "ytm")).toBe(EM_DASH);
  });

  it("puts the scaled position YTM into the conclusion sentence", () => {
    const model = buildBondTradingDeskPageModel({
      bondCode: "149001.SZ",
      reportDate: "2026-04-30",
      topHoldings: [],
      positions: [positionItem({ credit_name: "测试券", yield_rate: "0.0310" })],
      creditSpreadRows: [],
      positionChanges: [],
    });

    expect(model.conclusion.body).toContain("YTM 3.10%");
    expect(model.conclusion.body).not.toContain("YTM 0.03%");
  });
});
