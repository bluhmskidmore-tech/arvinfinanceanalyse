import { describe, expect, it } from "vitest";

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
          yield_rate: "3.1",
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
});
