import { describe, expect, it } from "vitest";

import { buildProductCategoryMockYuanPayload, buildMockProductCategoryPnlEnvelope } from "./productCategoryPnl";
import type { ProductCategoryPnlRow } from "../api/contracts";

const YI = 100_000_000;

function minimalRow(overrides: Partial<ProductCategoryPnlRow> & Pick<ProductCategoryPnlRow, "category_id">): ProductCategoryPnlRow {
  const { category_id, ...rest } = overrides;
  return {
    category_name: "x",
    side: "asset",
    level: 0,
    view: "monthly",
    report_date: "2026-02-28",
    baseline_ftp_rate_pct: "1",
    cnx_scale: "0",
    cny_scale: "0",
    foreign_scale: "0",
    cnx_cash: "0",
    cny_cash: "0",
    foreign_cash: "0",
    cny_ftp: "0",
    foreign_ftp: "0",
    cny_net: "0",
    foreign_net: "0",
    business_net_income: "1.5",
    weighted_yield: null,
    is_total: true,
    children: [],
    ...rest,
    category_id,
  };
}

describe("productCategoryPnl mock", () => {
  it("converts 亿元-scale numeric fields to yuan strings in buildProductCategoryMockYuanPayload", () => {
    const asset = minimalRow({ category_id: "asset_total", is_total: true, business_net_income: "2" });
    const liab = minimalRow({ category_id: "liability_total", side: "liability", is_total: true, business_net_income: "1" });
    const grand = minimalRow({ category_id: "grand_total", side: "all", is_total: true, business_net_income: "3" });
    const out = buildProductCategoryMockYuanPayload({
      rows: [],
      assetTotal: asset,
      liabilityTotal: liab,
      grandTotal: grand,
    });
    expect(out.assetTotal.business_net_income).toBe(String(2 * YI));
    expect(out.liabilityTotal.business_net_income).toBe(String(1 * YI));
    expect(out.grandTotal.business_net_income).toBe(String(3 * YI));
  });

  it("buildMockProductCategoryPnlEnvelope returns mock meta and yi-scale totals like the workbench product-category page", () => {
    const env = buildMockProductCategoryPnlEnvelope({
      reportDate: "2026-02-28",
      view: "monthly",
    });
    expect(env.result_meta.result_kind).toBe("product_category_pnl.detail");
    expect(env.result_meta.trace_id).toBe("mock_product_category_pnl.detail");
    const yi = (v: string) => Number(v) / YI;
    expect(yi(String(env.result.grand_total.business_net_income))).toBeCloseTo(2.85, 5);
  });
});
