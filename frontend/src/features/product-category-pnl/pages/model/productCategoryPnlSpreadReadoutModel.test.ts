import { describe, expect, it } from "vitest";

import { EM_DASH } from "../../../../utils/format";
import {
  readProductCategoryLiabilityCostDecomposition,
  selectProductCategorySpreadReadoutSurface,
  type ProductCategorySpreadReadoutSurface,
} from "./productCategoryPnlSpreadReadoutModel";

function percent(raw: string) {
  return { raw, display: `${Number(raw).toFixed(2)}%`, unit: "percent" as const };
}

function bp(raw: string) {
  return { raw, display: `${Number(raw).toFixed(1)} bp`, unit: "bp" as const };
}

function spreadSection(input: {
  asset: string;
  liability: string;
  spread: string;
}) {
  return {
    all_currency_asset_yield_pct: percent(input.asset),
    all_currency_liability_yield_pct: percent(input.liability),
    all_currency_spread_pct: percent(input.spread),
    cny_asset_yield_pct: null,
    cny_liability_yield_pct: null,
    cny_spread_pct: null,
  };
}

/** 2026-07-31 / ytd 的已核定口径（CONTRACT.md 报告口径基准）。 */
const YTD_PAYLOAD = {
  interest_earning_spread: spreadSection({
    asset: "2.36",
    liability: "1.58",
    spread: "0.78",
  }),
  interest_spread: spreadSection({
    asset: "2.51",
    liability: "1.58",
    spread: "0.93",
  }),
};

/** 2026-07-31 / monthly 的已核定口径。 */
const MONTHLY_PAYLOAD = {
  interest_earning_spread: spreadSection({
    asset: "2.29",
    liability: "1.53",
    spread: "0.76",
  }),
  interest_spread: spreadSection({
    asset: "2.17",
    liability: "1.53",
    spread: "0.64",
  }),
};

function metricValue(
  surface: ProductCategorySpreadReadoutSurface,
  key: string,
): string {
  const metric = surface.metrics.find((item) => item.key === key);
  if (!metric) {
    throw new Error(`missing spread readout metric: ${key}`);
  }
  return metric.value;
}

function liabilityMetricValue(
  surface: ProductCategorySpreadReadoutSurface,
  key: string,
): string {
  if (surface.liability.state === "unavailable") {
    throw new Error("expected available liability cost decomposition");
  }
  const metric = surface.liability.metrics.find((item) => item.key === key);
  if (!metric) {
    throw new Error(`missing liability readout metric: ${key}`);
  }
  return metric.value;
}

describe("selectProductCategorySpreadReadoutSurface", () => {
  it("reads both spread calibers straight from the backend payload for the ytd view", () => {
    const surface = selectProductCategorySpreadReadoutSurface({
      payload: YTD_PAYLOAD,
      reportDate: "2026-07-31",
      selectedView: "ytd",
    });

    expect(surface.state).toBe("ready");
    expect(metricValue(surface, "interest_earning_asset_yield")).toBe("2.36%");
    expect(metricValue(surface, "liability_yield")).toBe("1.58%");
    expect(metricValue(surface, "interest_earning_spread")).toBe("78.0 bp");
    expect(metricValue(surface, "asset_yield_with_tpl")).toBe("2.51%");
    expect(metricValue(surface, "interest_spread_with_tpl")).toBe("93.0 bp");
    expect(surface.viewLabel).toBe("累计口径 · 截至 2026年07月");
    expect(surface.caliberNote).toContain("年初至今累计口径");
  });

  it("switches the readout and the caliber label with the monthly view", () => {
    const monthly = selectProductCategorySpreadReadoutSurface({
      payload: MONTHLY_PAYLOAD,
      reportDate: "2026-07-31",
      selectedView: "monthly",
    });
    const ytd = selectProductCategorySpreadReadoutSurface({
      payload: YTD_PAYLOAD,
      reportDate: "2026-07-31",
      selectedView: "ytd",
    });

    expect(metricValue(monthly, "interest_earning_spread")).toBe("76.0 bp");
    expect(metricValue(monthly, "interest_spread_with_tpl")).toBe("64.0 bp");
    expect(metricValue(monthly, "interest_earning_asset_yield")).toBe("2.29%");
    expect(monthly.viewLabel).toBe("单月口径 · 2026年07月");
    expect(monthly.caliberNote).toContain("单月");
    expect(monthly.viewLabel).not.toBe(ytd.viewLabel);
    expect(metricValue(monthly, "interest_earning_spread")).not.toBe(
      metricValue(ytd, "interest_earning_spread"),
    );
  });

  it("renders the CLN drag block when the backend returns liability_cost_decomposition", () => {
    const surface = selectProductCategorySpreadReadoutSurface({
      payload: {
        ...YTD_PAYLOAD,
        liability_cost_decomposition: {
          liability_yield_pct: percent("1.58"),
          liability_yield_ex_cln_pct: percent("1.57"),
          cln_yield_pct: percent("2.79"),
          cln_drag_bp: bp("1.4"),
          cln_scale: "-1947000000",
        },
      },
      reportDate: "2026-07-31",
      selectedView: "ytd",
    });

    expect(surface.liability.state).toBe("ready");
    expect(liabilityMetricValue(surface, "liability_yield_pct")).toBe("1.58%");
    expect(liabilityMetricValue(surface, "liability_yield_ex_cln_pct")).toBe(
      "1.57%",
    );
    expect(liabilityMetricValue(surface, "cln_drag_bp")).toBe("1.4 bp");
    expect(liabilityMetricValue(surface, "cln_yield_pct")).toBe("2.79%");
    if (surface.liability.state === "unavailable") {
      throw new Error("expected available liability cost decomposition");
    }
    expect(
      surface.liability.metrics.find((item) => item.key === "cln_yield_pct")
        ?.note,
    ).toBe("规模 19.47 亿元");
  });

  it("uses the authoritative backend BP display without JavaScript rerounding", () => {
    const surface = selectProductCategorySpreadReadoutSurface({
      payload: {
        ...YTD_PAYLOAD,
        liability_cost_decomposition: {
          liability_yield_pct: percent("1.58"),
          liability_yield_ex_cln_pct: percent("1.5655"),
          cln_yield_pct: percent("2.79"),
          cln_drag_bp: {
            raw: "1.45",
            display: "1.5 bp",
            unit: "bp",
          },
          cln_scale: "-1947000000",
        },
      },
      reportDate: "2026-07-31",
      selectedView: "ytd",
    });

    expect(liabilityMetricValue(surface, "cln_drag_bp")).toBe("1.5 bp");
  });

  it("describes a negative CLN impact as cost reduction instead of drag", () => {
    const surface = selectProductCategorySpreadReadoutSurface({
      payload: {
        ...YTD_PAYLOAD,
        liability_cost_decomposition: {
          liability_yield_pct: percent("1.57"),
          liability_yield_ex_cln_pct: percent("1.60"),
          cln_yield_pct: percent("0.50"),
          cln_drag_bp: bp("-3.0"),
          cln_scale: "-100000000",
        },
      },
      reportDate: "2026-07-31",
      selectedView: "ytd",
    });

    if (surface.liability.state === "unavailable") {
      throw new Error("expected available liability cost decomposition");
    }
    const drag = surface.liability.metrics.find(
      (item) => item.key === "cln_drag_bp",
    );
    expect(surface.liability.title).toBe("负债端 CLN 降本");
    expect(surface.liability.description).toContain("降低");
    expect(drag?.label).toBe("CLN 降本（bp）");
    expect(drag?.note).toContain("降低");
    expect(`${surface.liability.title}${surface.liability.description}${drag?.note}`).not.toContain(
      "拖累",
    );
  });

  it("degrades to a gap notice when liability_cost_decomposition is absent", () => {
    const surface = selectProductCategorySpreadReadoutSurface({
      payload: YTD_PAYLOAD,
      reportDate: "2026-07-31",
      selectedView: "ytd",
    });

    expect(surface.state).toBe("ready");
    expect(surface.liability).toEqual({
      state: "unavailable",
      title: "负债端 CLN 影响",
      description: "信用联结票据对负债端成本率的影响，后端直出",
      reason: "后端未返回负债成本拆解字段，CLN 影响暂不可用。",
      metrics: [],
    });
  });

  it("degrades when liability_cost_decomposition is present but fully null", () => {
    const surface = selectProductCategorySpreadReadoutSurface({
      payload: {
        ...YTD_PAYLOAD,
        liability_cost_decomposition: {
          liability_yield_pct: null,
          liability_yield_ex_cln_pct: null,
          cln_yield_pct: null,
          cln_drag_bp: null,
          cln_scale: null,
        },
      },
      reportDate: "2026-07-31",
      selectedView: "ytd",
    });

    expect(surface.liability.state).toBe("unavailable");
  });

  it("shows an em dash instead of zero for individually missing decomposition fields", () => {
    const surface = selectProductCategorySpreadReadoutSurface({
      payload: {
        ...YTD_PAYLOAD,
        liability_cost_decomposition: {
          liability_yield_pct: percent("1.58"),
          liability_yield_ex_cln_pct: null,
          cln_yield_pct: null,
          cln_drag_bp: null,
          cln_scale: null,
        },
      },
      reportDate: "2026-07-31",
      selectedView: "ytd",
    });

    expect(surface.liability.state).toBe("partial");
    expect(liabilityMetricValue(surface, "cln_drag_bp")).toBe(EM_DASH);
    expect(liabilityMetricValue(surface, "liability_yield_ex_cln_pct")).toBe(
      EM_DASH,
    );
    expect(liabilityMetricValue(surface, "cln_yield_pct")).toBe(EM_DASH);
    if (surface.liability.state === "unavailable") {
      throw new Error("expected available liability cost decomposition");
    }
    expect(
      surface.liability.metrics.find((item) => item.key === "cln_yield_pct")
        ?.note,
    ).toBe(`规模 ${EM_DASH}`);
    expect(surface.liability.reason).toContain("不完整");
  });

  it("marks the liability decomposition partial when only CLN scale is missing", () => {
    const surface = selectProductCategorySpreadReadoutSurface({
      payload: {
        ...YTD_PAYLOAD,
        liability_cost_decomposition: {
          liability_yield_pct: percent("1.58"),
          liability_yield_ex_cln_pct: percent("1.57"),
          cln_yield_pct: percent("2.79"),
          cln_drag_bp: bp("1.4"),
          cln_scale: null,
        },
      },
      reportDate: "2026-07-31",
      selectedView: "ytd",
    });

    expect(surface.liability.state).toBe("partial");
    expect(surface.liability.reason).toContain("不完整");
    expect(
      surface.liability.metrics.find((item) => item.key === "cln_yield_pct")
        ?.note,
    ).toBe(`规模 ${EM_DASH}`);
  });

  it("marks a partially populated spread response as partial", () => {
    const partialInterestEarning = {
      ...YTD_PAYLOAD.interest_earning_spread,
      all_currency_asset_yield_pct: null,
    };
    const surface = selectProductCategorySpreadReadoutSurface({
      payload: {
        ...YTD_PAYLOAD,
        interest_earning_spread: partialInterestEarning,
      },
      reportDate: "2026-07-31",
      selectedView: "ytd",
    });

    expect(surface.state).toBe("partial");
    expect(surface.reason).toContain("不完整");
    expect(metricValue(surface, "interest_earning_asset_yield")).toBe(EM_DASH);
  });

  it("degrades the whole readout when the backend returns no spread section", () => {
    const surface = selectProductCategorySpreadReadoutSurface({
      payload: { interest_spread: null, interest_earning_spread: null },
      reportDate: "2026-07-31",
      selectedView: "monthly",
    });

    expect(surface.state).toBe("unavailable");
    expect(surface.reason).toBe("后端未返回利差指标，主屏利差读数暂不可用。");
    surface.metrics.forEach((item) => {
      expect(item.value).toBe(EM_DASH);
      expect(item.available).toBe(false);
    });
  });

  it("ignores a malformed liability_cost_decomposition payload", () => {
    expect(
      readProductCategoryLiabilityCostDecomposition({
        liability_cost_decomposition: "unexpected",
      }),
    ).toBeNull();
    expect(readProductCategoryLiabilityCostDecomposition(null)).toBeNull();
    expect(readProductCategoryLiabilityCostDecomposition(undefined)).toBeNull();
  });
});
