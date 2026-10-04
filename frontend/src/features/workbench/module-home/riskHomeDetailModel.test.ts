import { describe, expect, it } from "vitest";

import type { CashflowProjectionPayload, RiskTensorPayload, RiskTensorScalar } from "../../../api/contracts";
import { EM_DASH, formatRawAsNumeric } from "../../../utils/format";
import {
  buildCashflowDetailSections,
  buildRiskTensorDetailSections,
  riskTensorPendingOrWan,
  riskTensorWanWithUnit,
  riskTensorYiWithUnit,
} from "./riskHomeDetailModel";

type AccountingTensor = RiskTensorPayload & Partial<Record<
  "ac_dv01" | "oci_dv01" | "tpl_dv01" | "other_dv01",
  RiskTensorScalar | null
>>;

function tensor(overrides: Partial<AccountingTensor> = {}): AccountingTensor {
  return {
    report_date: "2026-02-28",
    regulatory_dv01: "0", portfolio_dv01: "0", rate_risk_dv01: "0", cs01: "0",
    krd_1y: "0", krd_3y: "0", krd_5y: "0", krd_7y: "0", krd_10y: "0", krd_30y: "0",
    portfolio_convexity: "0", portfolio_modified_duration: "0",
    issuer_concentration_hhi: "0", issuer_top5_weight: "0",
    liquidity_gap_30d: "0", liquidity_gap_90d: "0", liquidity_gap_30d_ratio: "0",
    asset_cashflow_30d: "0", asset_cashflow_90d: "0",
    liability_cashflow_30d: "0", liability_cashflow_90d: "0",
    total_market_value: "0", rate_risk_market_value: "0", rate_risk_modified_duration: "0",
    duration_excluded_market_value: "0", duration_excluded_count: 0,
    bond_count: 0, quality_flag: "ok", warnings: [],
    ...overrides,
  };
}

describe("risk home detail model", () => {
  it("preserves section and field order while retaining observed zero values", () => {
    const sections = buildRiskTensorDetailSections(tensor());
    expect(sections.map((section) => section.key)).toEqual([
      "rate-sensitivity", "krd-detail", "concentration", "liquidity-detail",
    ]);
    expect(sections[0].rows.map((row) => row.key)).toEqual([
      "regulatory_dv01", "portfolio_dv01", "rate_risk_dv01", "cs01", "portfolio_convexity",
    ]);
    expect(sections[1].rows.map((row) => row.key)).toEqual([
      "krd_1y", "krd_3y", "krd_5y", "krd_7y", "krd_10y", "krd_30y",
    ]);
    expect(sections[3].rows.map((row) => row.key)).toEqual([
      "liquidity_gap_30d", "liquidity_gap_90d", "liquidity_gap_30d_ratio",
      "asset_cashflow_30d", "asset_cashflow_90d", "liability_cashflow_30d", "liability_cashflow_90d",
    ]);
    expect(sections.map((section) => section.defaultExpanded)).toEqual([true, false, false, false]);
    expect(sections[0].rows[0].value).toBe("0.00 万元/bp");
    expect(sections.every((section) => section.rows.every((row) => row.tradeDate === "2026-02-28"))).toBe(true);
  });

  it("hides null fields and only zero accounting splits without hiding other zero readings", () => {
    const sections = buildRiskTensorDetailSections(tensor({
      regulatory_dv01: null,
      ac_dv01: "0", oci_dv01: null, tpl_dv01: "-10000", other_dv01: "",
    }));
    expect(sections.map((section) => section.key)).toEqual([
      "rate-sensitivity", "accounting-dv01", "krd-detail", "concentration", "liquidity-detail",
    ]);
    expect(sections[0].rows.map((row) => row.key)).not.toContain("regulatory_dv01");
    expect(sections[1].rows.map((row) => [row.key, row.value])).toEqual([
      ["tpl_dv01", "-1.00 万元/bp"], ["other_dv01", EM_DASH],
    ]);
  });

  it("retains signed unit displays and the existing missing-versus-pending distinction", () => {
    expect(riskTensorWanWithUnit("-1234567.89")).toBe("-123.46 万元/bp");
    expect(riskTensorYiWithUnit("-123456789")).toBe("-1.23 亿元");
    expect(riskTensorWanWithUnit(null)).toBe(EM_DASH);
    expect(riskTensorPendingOrWan(null)).toBe("待接入");
    expect(riskTensorPendingOrWan("0")).toBe("0.00 万元/bp");
  });

  it("keeps cashflow forecast order and limits monthly rows to the first six supplied buckets", () => {
    const zero = formatRawAsNumeric({ raw: 0, unit: "yuan", sign_aware: true });
    const cashflow: CashflowProjectionPayload = {
      report_date: "2026-02-28",
      duration_gap: zero, asset_duration: zero, liability_duration: zero, equity_duration: zero,
      rate_sensitivity_1bp: zero, reinvestment_risk_12m: zero,
      monthly_buckets: Array.from({ length: 7 }, (_, index) => ({
        year_month: `2026-${String(index + 3).padStart(2, "0")}`,
        asset_inflow: zero, liability_outflow: zero, net_cashflow: zero, cumulative_net: zero,
      })),
      top_maturing_assets_12m: [], warnings: [], computed_at: "2026-02-28T00:00:00Z",
    };
    const sections = buildCashflowDetailSections(cashflow);
    expect(sections.map((section) => section.key)).toEqual(["cashflow-forecast", "monthly-buckets"]);
    expect(sections[0].rows.map((row) => row.key)).toEqual([
      "duration_gap", "asset_duration", "liability_duration", "equity_duration",
      "rate_sensitivity_1bp", "reinvestment_risk_12m",
    ]);
    expect(sections[1].rows).toHaveLength(12);
    expect(sections[1].rows[0]).toMatchObject({ key: "bucket-2026-03", tradeDate: "2026-03" });
    expect(sections[1].rows[11]).toMatchObject({ key: "bucket-cum-2026-08", tradeDate: "2026-08" });
    expect(sections[1].rows.some((row) => row.tradeDate === "2026-09")).toBe(false);
  });
});
