import { describe, expect, it } from "vitest";

import { buildMockProductCategoryPnlEnvelope } from "../../../mocks/productCategoryPnl";
import {
  buildProductCategoryDiagnosticsSurface,
  selectProductCategoryScenarioSensitivitySurface,
} from "./productCategoryPnlPageModel";

const baseline = buildMockProductCategoryPnlEnvelope({
  reportDate: "2026-08-31",
  view: "monthly",
}).result;

describe("product-category net-income signs", () => {
  it("preserves liability income signs and colors in diagnostics and the loss watchlist", () => {
    const row = {
      ...baseline.rows.find((item) => item.category_id === "credit_linked_notes")!,
      cnx_scale: "-3000000000",
      cny_net: "-125000000",
      foreign_net: "25000000",
      business_net_income: "-100000000",
    };
    const surface = buildProductCategoryDiagnosticsSurface({ rows: [row] });

    expect(surface.matrixRows[0]).toMatchObject({
      scaleLabel: "30.00 亿元",
      cnyNetLabel: "-1.25 亿元",
      cnyNetTone: "negative",
      foreignNetLabel: "0.25 亿元",
      foreignNetTone: "positive",
      businessNetIncomeLabel: "-1.00 亿元",
      businessNetIncomeTone: "negative",
    });
    expect(surface.negativeWatchlistRows[0]?.lossLabel).toBe("-1.00 亿元");
  });

  it("keeps negative foreign liability income negative while total income is positive", () => {
    const row = {
      ...baseline.rows.find((item) => item.category_id === "interbank_borrowings")!,
      cny_net: "15000000",
      foreign_net: "-5000000",
      business_net_income: "10000000",
    };
    const surface = buildProductCategoryDiagnosticsSurface({ rows: [row] });

    expect(surface.matrixRows[0]).toMatchObject({
      cnyNetLabel: "0.15 亿元",
      cnyNetTone: "positive",
      foreignNetLabel: "-0.05 亿元",
      foreignNetTone: "negative",
      businessNetIncomeLabel: "0.10 亿元",
      businessNetIncomeTone: "positive",
    });
    expect(surface.negativeWatchlistRows).toEqual([]);
  });

  it("does not turn a scenario liability loss into positive net income", () => {
    const scenario = {
      ...baseline,
      scenario_rate_pct: "2.00",
      liability_total: {
        ...baseline.liability_total,
        business_net_income: "-123456789",
      },
    };

    const surface = selectProductCategoryScenarioSensitivitySurface({
      baseline,
      scenarios: [scenario],
    });

    expect(surface.rows[0]?.liabilityNetIncomeLabel).toBe("-1.23");
  });
});
