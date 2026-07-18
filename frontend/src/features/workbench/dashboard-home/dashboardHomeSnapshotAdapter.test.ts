import { describe, expect, it } from "vitest";

import { createApiClient } from "../../../api/client";
import type { Numeric } from "../../../api/contracts";
import { adaptHomeSnapshotForFirstScreen } from "./dashboardHomeSnapshotAdapter";

function numeric(raw: number, display: string): Numeric {
  return {
    raw,
    display,
    unit: "yuan",
    precision: 2,
    sign_aware: true,
  };
}

describe("adaptHomeSnapshotForFirstScreen product-category contract", () => {
  it("passes through backend display values and governed missing domains without recalculation", async () => {
    const base = await createApiClient({ mode: "mock" }).getHomeSnapshot();
    const snapshot = {
      ...base,
      result: {
        ...base.result,
        domains_missing: ["attribution"],
        product_category_ytd: {
          view: "ytd" as const,
          summary_pnl: numeric(1_230_000_000, "+12.30 亿元"),
          summary_pnl_detail: "后端年度汇总口径",
          operating_income: numeric(920_000_000, "+9.20 亿元"),
          operating_income_detail: "后端营业收入口径",
          intermediate_business_income: numeric(310_000_000, "+3.10 亿元"),
          intermediate_business_income_detail: "后端中间业务口径",
        },
        product_category_monthly: {
          view: "monthly" as const,
          monthly_income: numeric(120_000_000, "+1.20 亿元"),
          monthly_income_detail: "后端月度口径",
        },
      },
    };

    const output = adaptHomeSnapshotForFirstScreen({
      snapshot,
      isLoading: false,
      isError: false,
    }) as ReturnType<typeof adaptHomeSnapshotForFirstScreen> & {
      domainsMissing: readonly string[];
      productCategoryHeadline: {
        state: string;
        metrics: ReadonlyArray<{ id: string; label: string; value: string; detail: string }>;
      };
    };

    expect(output.domainsMissing).toEqual(["attribution"]);
    expect(output.productCategoryHeadline).toEqual({
      state: "ready",
      metrics: [
        {
          id: "ytd-summary-pnl",
          label: "年度汇总损益",
          value: "+12.30 亿元",
          detail: "后端年度汇总口径",
        },
        {
          id: "ytd-operating-income",
          label: "年度营业收入",
          value: "+9.20 亿元",
          detail: "后端营业收入口径",
        },
        {
          id: "ytd-intermediate-business-income",
          label: "年度中间业务收入",
          value: "+3.10 亿元",
          detail: "后端中间业务口径",
        },
        {
          id: "monthly-income",
          label: "本月收入",
          value: "+1.20 亿元",
          detail: "后端月度口径",
        },
      ],
    });
  });

  it("exposes an explicit empty product-category state when the snapshot has no headline", async () => {
    const base = await createApiClient({ mode: "mock" }).getHomeSnapshot();
    const snapshot = {
      ...base,
      result: {
        ...base.result,
        product_category_ytd: null,
        product_category_monthly: null,
      },
    };

    const output = adaptHomeSnapshotForFirstScreen({
      snapshot,
      isLoading: false,
      isError: false,
    }) as ReturnType<typeof adaptHomeSnapshotForFirstScreen> & {
      productCategoryHeadline: { state: string; metrics: readonly unknown[] };
    };

    expect(output.productCategoryHeadline).toEqual({ state: "empty", metrics: [] });
  });
  it("marks product-category data partial when a required block or governed value is missing", async () => {
    const base = await createApiClient({ mode: "mock" }).getHomeSnapshot();
    const completeYtd = {
      view: "ytd" as const,
      summary_pnl: numeric(1_230_000_000, "+12.30 亿元"),
      summary_pnl_detail: "后端年度汇总口径",
      operating_income: numeric(920_000_000, "+9.20 亿元"),
      operating_income_detail: "后端营业收入口径",
      intermediate_business_income: numeric(310_000_000, "+3.10 亿元"),
      intermediate_business_income_detail: "后端中间业务口径",
    };
    const completeMonthly = {
      view: "monthly" as const,
      monthly_income: numeric(120_000_000, "+1.20 亿元"),
      monthly_income_detail: "后端月度口径",
    };

    const missingMonthly = adaptHomeSnapshotForFirstScreen({
      snapshot: {
        ...base,
        result: {
          ...base.result,
          product_category_ytd: completeYtd,
          product_category_monthly: null,
        },
      },
      isLoading: false,
      isError: false,
    });
    expect(missingMonthly.productCategoryHeadline.state).toBe("partial");
    expect(missingMonthly.productCategoryHeadline.metrics).toHaveLength(4);
    expect(
      missingMonthly.productCategoryHeadline.metrics.find((metric) => metric.id === "monthly-income"),
    ).toEqual(expect.objectContaining({ value: "—" }));

    const missingIntermediate = adaptHomeSnapshotForFirstScreen({
      snapshot: {
        ...base,
        result: {
          ...base.result,
          product_category_ytd: {
            ...completeYtd,
            intermediate_business_income: {
              ...completeYtd.intermediate_business_income,
              raw: null,
              display: "0.00 亿元",
            },
          },
          product_category_monthly: completeMonthly,
        },
      },
      isLoading: false,
      isError: false,
    });
    expect(missingIntermediate.productCategoryHeadline.state).toBe("partial");
    expect(
      missingIntermediate.productCategoryHeadline.metrics.find(
        (metric) => metric.id === "ytd-intermediate-business-income",
      ),
    ).toEqual(expect.objectContaining({ value: "—" }));
  });
});

describe("adaptHomeSnapshotForFirstScreen fallback semantics", () => {
  it("does not relabel a complete fallback product block as stale", async () => {
    const base = await createApiClient({ mode: "mock" }).getHomeSnapshot();
    const snapshot = {
      ...base,
      result_meta: {
        ...base.result_meta,
        fallback_mode: "latest_snapshot" as const,
      },
      result: {
        ...base.result,
        product_category_ytd: {
          view: "ytd" as const,
          summary_pnl: numeric(1_230_000_000, "+12.30 亿元"),
          summary_pnl_detail: "年度汇总口径",
          operating_income: numeric(920_000_000, "+9.20 亿元"),
          operating_income_detail: "营业收入口径",
          intermediate_business_income: numeric(310_000_000, "+3.10 亿元"),
          intermediate_business_income_detail: "中间业务口径",
        },
        product_category_monthly: {
          view: "monthly" as const,
          monthly_income: numeric(120_000_000, "+1.20 亿元"),
          monthly_income_detail: "月度口径",
        },
      },
    };

    const output = adaptHomeSnapshotForFirstScreen({
      snapshot,
      isLoading: false,
      isError: false,
    });

    expect(output.productCategoryHeadline.state).toBe("ready");
  });
});
