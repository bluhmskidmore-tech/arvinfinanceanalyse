import { describe, expect, it } from "vitest";

import type {
  ProductCategoryAttributionEffects,
  ProductCategoryAttributionPayload,
  ProductCategoryPnlPayload,
  ProductCategoryPnlRow,
} from "../../../api/contracts";
import { EM_DASH } from "../../../utils/format";

import { selectProductCategoryScenarioExplanation } from "./productCategoryPnlPageModel";

const CATEGORY_ID = "synthetic_asset";

function row(income: string): ProductCategoryPnlRow {
  return {
    category_id: CATEGORY_ID,
    category_name: "合成资产",
    side: "asset",
    level: 0,
    view: "monthly",
    report_date: "2026-02-28",
    baseline_ftp_rate_pct: "1.75",
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
    business_net_income: income,
    weighted_yield: null,
    is_total: false,
    children: [],
  };
}

function pnl(income: string, scenarioRate: string | null): ProductCategoryPnlPayload {
  const detail = row(income);
  const spread = {
    all_currency_asset_yield_pct: null,
    all_currency_liability_yield_pct: null,
    all_currency_spread_pct: null,
    cny_asset_yield_pct: null,
    cny_liability_yield_pct: null,
    cny_spread_pct: null,
  };
  return {
    report_date: detail.report_date,
    view: detail.view,
    available_views: [detail.view],
    scenario_rate_pct: scenarioRate,
    rows: [detail],
    asset_total: { ...detail, category_id: "asset_total", is_total: true },
    liability_total: {
      ...detail,
      category_id: "liability_total",
      side: "liability",
      business_net_income: "0",
      is_total: true,
    },
    grand_total: { ...detail, category_id: "grand_total", is_total: true },
    interest_spread: spread,
    interest_earning_spread: spread,
    liability_cost_decomposition: {
      liability_yield_pct: null,
      liability_yield_ex_cln_pct: null,
      cln_yield_pct: null,
      cln_drag_bp: null,
      cln_scale: null,
    },
  };
}

function attribution(
  overrides: Partial<Record<keyof ProductCategoryAttributionEffects, string | number | null | undefined>>,
  state: "complete" | "partial" = "complete",
): ProductCategoryAttributionPayload {
  // Deliberately allow missing runtime fields to verify the display boundary.
  const effects = {
    day_effect: "0",
    scale_effect: "0",
    rate_effect: "0",
    ftp_effect: "0",
    direct_effect: "0",
    unexplained_effect: "0",
    explained_effect: "0",
    delta_business_net_income: "0",
    closure_error: "0",
    ...overrides,
  } as ProductCategoryAttributionEffects;
  return {
    report_date: "2026-02-28",
    compare: "mom",
    current_report_date: "2026-02-28",
    prior_report_date: "2026-01-31",
    state: "complete",
    reason: null,
    rows: [{
      category_id: CATEGORY_ID,
      category_name: "合成资产",
      side: "asset",
      level: 0,
      state,
      current: null,
      prior: null,
      effects,
    }],
    totals: null,
  };
}

function explain(
  formalAttribution: ProductCategoryAttributionPayload,
  scenarioIncome = "400000000",
) {
  return selectProductCategoryScenarioExplanation({
    categoryId: CATEGORY_ID,
    baseline: pnl("500000000", null),
    scenarios: [pnl(scenarioIncome, "2.00")],
    attribution: formalAttribution,
  });
}

describe("scenario explanation official delta regression", () => {
  it("uses the backend delta when direct effects reverse the four visible factors", () => {
    const explanation = explain(attribution({
      ftp_effect: "-100000000",
      direct_effect: "200000000",
      delta_business_net_income: "100000000",
    }));

    expect(explanation?.bridgeLabel).toContain("正式归因合计 +1.00 亿元；差异 -2.00 亿元");
    expect(explanation?.bridgeTone).toBe("warning");
    expect(explanation?.driverRows[0]).toEqual(expect.objectContaining({
      key: "direct_effect",
      label: "直接因素",
      valueLabel: "+2.00",
    }));
  });

  it("keeps day and direct effects visible without deriving the official total", () => {
    const explanation = explain(attribution({
      day_effect: "100000000",
      direct_effect: "200000000",
      delta_business_net_income: "300000000",
    }), "500000000");

    expect(explanation?.bridgeLabel).toContain("正式归因合计 +3.00 亿元；差异 -3.00 亿元");
    expect(explanation?.driverRows.map((driver) => driver.key)).toEqual([
      "direct_effect", "day_effect", "ftp_effect", "scale_effect", "rate_effect", "unexplained_effect",
    ]);
  });

  it.each([null, undefined, "", " ", "not-a-number", Number.NaN])(
    "does not reconstruct the official delta when it is unavailable (%s)",
    (delta) => {
      const explanation = explain(attribution({
        ftp_effect: "-100000000",
        delta_business_net_income: delta,
      }));

      expect(explanation?.bridgeLabel).toContain(`正式归因合计 ${EM_DASH} 亿元；差异 ${EM_DASH}`);
      expect(explanation?.bridgeConclusionLabel).toContain("暂不能做口径差异判断");
      expect(explanation?.bridgeTone).toBe("neutral");
    },
  );

  it("warns about a material backend closure error even when the two deltas agree", () => {
    const explanation = explain(attribution({
      ftp_effect: "-100000000",
      delta_business_net_income: "-100000000",
      closure_error: "2000000",
    }));

    expect(explanation?.bridgeLabel).toContain("差异 0.00 亿元");
    expect(explanation?.bridgeTone).toBe("warning");
    expect(explanation?.bridgeConclusionLabel).toContain("正式归因闭合误差 +0.02 亿元");
    expect(explanation?.bridgeConclusionLabel).not.toContain("合计接近");
  });

  it.each([null, undefined, "", " ", "not-a-number"])("does not claim comparability when the closure error is missing (%s)", (closureError) => {
    const explanation = explain(attribution({
      ftp_effect: "-100000000",
      delta_business_net_income: "-100000000",
      closure_error: closureError,
    }));

    expect(explanation?.bridgeConclusionLabel).toContain("闭合误差缺失");
    expect(explanation?.bridgeConclusionLabel).not.toContain("合计接近");
  });

  it.each([null, undefined, "", " ", "not-a-number"])("preserves an incomplete driver rather than treating it as zero (%s)", (dayEffect) => {
    const explanation = explain(attribution({
      ftp_effect: "-100000000",
      day_effect: dayEffect,
      delta_business_net_income: "-100000000",
    }));

    expect(explanation?.driverRows.find((driver) => driver.key === "day_effect")).toEqual(
      expect.objectContaining({ value: null, valueLabel: EM_DASH }),
    );
    expect(explanation?.bridgeConclusionLabel).toContain("驱动不完整");
    expect(explanation?.bridgeConclusionLabel).not.toContain("合计接近");
  });

  it("retains the partial attribution state when the backend delta is present", () => {
    const explanation = explain(attribution({
      ftp_effect: "-100000000",
      delta_business_net_income: "-100000000",
    }, "partial"));

    expect(explanation?.bridgeLabel).toContain("正式归因合计 -1.00 亿元");
    expect(explanation?.bridgeConclusionLabel).toContain("驱动不完整");
  });

  it("keeps a valid zero delta and closed six-factor attribution comparable", () => {
    const explanation = explain(attribution({}), "500000000");

    expect(explanation?.bridgeLabel).toContain("正式归因合计 0.00 亿元；差异 0.00 亿元");
    expect(explanation?.bridgeTone).toBe("neutral");
    expect(explanation?.bridgeConclusionLabel).toContain("合计接近");
  });

  it("does not compare a prior reporting month's attribution with the baseline", () => {
    const formalAttribution = attribution({ delta_business_net_income: "100000000" });
    formalAttribution.current_report_date = "2026-01-31";
    const explanation = explain(formalAttribution);

    expect(explanation?.driverRows).toEqual([]);
    expect(explanation?.bridgeLabel).toContain(`正式归因合计 ${EM_DASH} 亿元；差异 ${EM_DASH}`);
  });

  it("does not compare an incomplete attribution payload with the baseline", () => {
    const formalAttribution = attribution({ delta_business_net_income: "100000000" });
    formalAttribution.state = "incomplete";
    const explanation = explain(formalAttribution);

    expect(explanation?.driverRows).toEqual([]);
    expect(explanation?.bridgeLabel).toContain(`正式归因合计 ${EM_DASH} 亿元；差异 ${EM_DASH}`);
  });

  it("does not compare monthly attribution with a cumulative baseline", () => {
    const baseline = pnl("500000000", null);
    const scenario = pnl("400000000", "2.00");
    baseline.view = scenario.view = "ytd";
    baseline.rows[0].view = scenario.rows[0].view = "ytd";
    const explanation = selectProductCategoryScenarioExplanation({
      categoryId: CATEGORY_ID,
      baseline,
      scenarios: [scenario],
      attribution: attribution({ delta_business_net_income: "100000000" }),
    });

    expect(explanation?.driverRows).toEqual([]);
    expect(explanation?.bridgeLabel).toContain(`正式归因合计 ${EM_DASH} 亿元；差异 ${EM_DASH}`);
  });

  it.each([{ report_date: "2026-03-31" }, { view: "ytd" }])(
    "does not compare a scenario with a mismatched date or view (%s)",
    (overrides) => {
      const scenario = { ...pnl("400000000", "2.00"), ...overrides };
      scenario.rows[0].report_date = scenario.report_date;
      scenario.rows[0].view = scenario.view;
      const explanation = selectProductCategoryScenarioExplanation({
        categoryId: CATEGORY_ID,
        baseline: pnl("500000000", null),
        scenarios: [scenario],
        attribution: attribution({ delta_business_net_income: "100000000" }),
      });

      expect(explanation?.scenarioDeltaLabel).toBe(EM_DASH);
      expect(explanation?.bridgeLabel).toContain(`差异 ${EM_DASH}`);
      expect(explanation?.emptyCopy).toContain("可比较结果");
    },
  );
});
