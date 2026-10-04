import { createElement } from "react";
import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import type {
  ProductCategoryAttributionPayload,
  ProductCategoryAttributionRow,
  ProductCategoryPnlPayload,
  ProductCategoryPnlRow,
} from "../../../api/contracts";
import { ProductCategoryOperatingAnalysisPanel } from "./ProductCategoryOperatingPanels";
import {
  selectProductCategoryDecisionFocusSurface,
  selectProductCategoryOperatingAnalysisSurface,
  selectProductCategoryOperatingActionBacktestSurface,
  selectProductCategoryRootCauseSurface,
} from "./productCategoryPnlPageModel";

function syntheticRow(
  categoryId: string,
  overrides: Partial<ProductCategoryPnlRow> = {},
): ProductCategoryPnlRow {
  return {
    category_id: categoryId,
    category_name: categoryId,
    side: "asset",
    level: 0,
    view: "monthly",
    report_date: "2026-02-28",
    baseline_ftp_rate_pct: "1.75",
    cnx_scale: "10000000000",
    cny_scale: "10000000000",
    foreign_scale: "0",
    cnx_cash: "0",
    cny_cash: "0",
    foreign_cash: "0",
    cny_ftp: "0",
    foreign_ftp: "0",
    cny_net: "0",
    foreign_net: "0",
    business_net_income: "100000000",
    weighted_yield: "3.00",
    is_total: false,
    children: [],
    ...overrides,
  };
}

function syntheticAttributionRow(
  categoryId: string,
  delta = "100000000",
): ProductCategoryAttributionRow {
  return {
    category_id: categoryId,
    category_name: categoryId,
    side: "asset",
    level: 0,
    state: "complete",
    current: null,
    prior: null,
    effects: {
      day_effect: "0",
      scale_effect: "0",
      rate_effect: "0",
      ftp_effect: "0",
      direct_effect: "0",
      unexplained_effect: delta,
      explained_effect: "0",
      delta_business_net_income: delta,
      closure_error: "0",
    },
  };
}

function syntheticAttribution(
  overrides: Partial<ProductCategoryAttributionPayload> = {},
): ProductCategoryAttributionPayload {
  return {
    report_date: "2026-02-28",
    compare: "mom",
    current_report_date: "2026-02-28",
    prior_report_date: "2026-01-31",
    state: "complete",
    reason: null,
    rows: [syntheticAttributionRow("repo_assets")],
    totals: null,
    ...overrides,
  };
}

const detailRows = [
  syntheticRow("repo_assets"),
  syntheticRow("bond_ac", {
    cnx_scale: "30000000000",
    weighted_yield: "2.00",
  }),
];
// The backend intentionally exposes this overlapping summary as a childless,
// non-total row. Those flags cannot make it an independent product.
const overlappingSummary = syntheticRow("interest_earning_assets", {
  cnx_scale: "40000000000",
  weighted_yield: "0.50",
  business_net_income: "200000000",
});

function syntheticMonthlyPayload(reportDate: string): ProductCategoryPnlPayload {
  const emptySpread = {
    all_currency_asset_yield_pct: null,
    all_currency_liability_yield_pct: null,
    all_currency_spread_pct: null,
    cny_asset_yield_pct: null,
    cny_liability_yield_pct: null,
    cny_spread_pct: null,
  };
  return {
    report_date: reportDate,
    view: "monthly",
    available_views: ["monthly", "ytd"],
    scenario_rate_pct: null,
    rows: detailRows.map((row) => ({ ...row, report_date: reportDate })),
    asset_total: syntheticRow("asset_total", {
      report_date: reportDate,
      business_net_income: "200000000",
      is_total: true,
    }),
    liability_total: syntheticRow("liability_total", {
      report_date: reportDate,
      side: "liability",
      business_net_income: "0",
      is_total: true,
    }),
    grand_total: syntheticRow("grand_total", {
      report_date: reportDate,
      side: "all",
      business_net_income: "200000000",
      is_total: true,
    }),
    interest_spread: emptySpread,
    interest_earning_spread: emptySpread,
    liability_cost_decomposition: {
      liability_yield_pct: null,
      liability_yield_ex_cln_pct: null,
      cln_yield_pct: null,
      cln_drag_bp: null,
      cln_scale: null,
    },
  };
}

describe("product operating analysis regression", () => {
  it("keeps the overlapping interest-earning summary out of profit contribution", () => {
    const surface = selectProductCategoryOperatingAnalysisSurface({
      rows: [...detailRows, overlappingSummary],
      grandTotal: { business_net_income: "200000000" },
    });

    expect(surface.contribution.profitRows.map((row) => row.categoryId)).toEqual([
      "repo_assets",
      "bond_ac",
    ]);
    expect(surface.contribution.grandTotalLabel).toBe("2.00");
    expect(surface.contribution.profitRows[0]?.contributionPct).toBe(50);
  });

  it("computes quadrant benchmarks and operating actions from independent products", () => {
    const surface = selectProductCategoryOperatingAnalysisSurface({
      rows: [...detailRows, overlappingSummary],
    });

    expect(surface.quadrant.scaleBenchmark).toBe(200);
    expect(surface.quadrant.yieldBenchmark).toBe(2.5);
    expect(surface.quadrant.rows.map((row) => row.categoryId)).toEqual([
      "bond_ac",
      "repo_assets",
    ]);
    expect(surface.actionQueue.rows).toEqual([
      expect.objectContaining({
        categoryId: "bond_ac",
        actionKind: "reprice_or_improve",
      }),
      expect.objectContaining({
        categoryId: "repo_assets",
        actionKind: "selective_growth",
      }),
    ]);
  });

  it("does not rank the overlapping summary as a movement or root-cause product", () => {
    const attribution = syntheticAttribution({
      rows: [
        syntheticAttributionRow("interest_earning_assets", "900000000"),
        syntheticAttributionRow("repo_assets"),
      ],
    });
    const surface = selectProductCategoryOperatingAnalysisSurface({
      rows: [...detailRows, overlappingSummary],
      attribution,
    });
    const rootCause = selectProductCategoryRootCauseSurface({
      rows: [...detailRows, overlappingSummary],
      attribution,
    });

    expect(surface.movement.rows.map((row) => row.categoryId)).toEqual([
      "repo_assets",
    ]);
    expect(rootCause.headline?.categoryId).toBe("repo_assets");
    expect(surface.actionQueue.rows[0]).toMatchObject({
      categoryId: "repo_assets",
      actionKind: "review_attribution",
    });
    expect(surface.actionQueue.rows.map((row) => row.categoryId)).not.toContain(
      "interest_earning_assets",
    );
  });

  it("chooses the independent product as the root-cause headline even when summary movement is larger", () => {
    const rootCause = selectProductCategoryRootCauseSurface({
      rows: [...detailRows, overlappingSummary],
      attribution: syntheticAttribution({
        rows: [
          syntheticAttributionRow("interest_earning_assets", "900000000"),
          syntheticAttributionRow("repo_assets"),
        ],
      }),
    });

    expect(rootCause.headline?.categoryId).toBe("repo_assets");
    expect(rootCause.headline?.delta).toBe(1);
  });

  it.each([
    { compare: "yoy" as const, state: "complete" as const },
    { compare: "mom" as const, state: "incomplete" as const },
  ])("rejects $compare/$state attribution for monthly operating actions", (input) => {
    const surface = selectProductCategoryOperatingAnalysisSurface({
      rows: detailRows,
      attribution: syntheticAttribution(input),
    });

    expect(surface.movement.rows).toEqual([]);
    expect(surface.movement.emptyCopy).toBe("当前缺少可用的月度经营差异归因。");
    expect(surface.actionQueue.rows.map((row) => row.actionKind)).not.toContain(
      "review_attribution",
    );
  });

  it("retains complete monthly attribution for operating movement and review", () => {
    const surface = selectProductCategoryOperatingAnalysisSurface({
      rows: detailRows,
      attribution: syntheticAttribution(),
    });

    expect(surface.movement.rows[0]).toMatchObject({
      categoryId: "repo_assets",
      delta: 1,
      leadingDriverKey: "unexplained_effect",
    });
    expect(surface.actionQueue.rows[0]).toMatchObject({
      categoryId: "repo_assets",
      actionKind: "review_attribution",
    });
  });

  it.each([
    { categoryId: "interest_earning_assets", children: [] },
    { categoryId: "bond_investment", children: ["bond_ac"] },
  ])("keeps $categoryId out of monthly decision-focus leaders", (summary) => {
    const rows = [
      ...detailRows,
      syntheticRow(summary.categoryId, { children: summary.children }),
    ];
    const attribution = syntheticAttribution({
      rows: [
        syntheticAttributionRow(summary.categoryId, "-900000000"),
        syntheticAttributionRow("repo_assets", "-100000000"),
      ],
    });
    const focus = selectProductCategoryDecisionFocusSurface({ rows, attribution });
    const rootCause = selectProductCategoryRootCauseSurface({ rows, attribution });
    const operating = selectProductCategoryOperatingAnalysisSurface({
      rows,
      attribution,
    });

    expect(
      focus.items
        .filter((item) => item.key.startsWith("largest_"))
        .map((item) => ({ key: item.key, categoryId: item.categoryId })),
    ).toEqual([
      { key: "largest_deterioration", categoryId: "repo_assets" },
      { key: "largest_unexplained", categoryId: "repo_assets" },
    ]);
    expect(rootCause.headline?.categoryId).toBe("repo_assets");
    expect(operating.movement.rows[0]?.categoryId).toBe("repo_assets");
  });

  it.each([
    { compare: "yoy" as const, state: "complete" as const },
    { compare: "mom" as const, state: "incomplete" as const },
  ])("omits monthly decision-focus attribution for $compare/$state", (input) => {
    const surface = selectProductCategoryDecisionFocusSurface({
      rows: detailRows,
      attribution: syntheticAttribution({
        ...input,
        rows: [syntheticAttributionRow("repo_assets", "-100000000")],
      }),
    });

    expect(surface.items.map((item) => item.key)).toEqual(["top_contributor"]);
    expect(surface.items[0]?.categoryId).toBe("repo_assets");
  });

  it.each(["missing", "yoy", "incomplete"] as const)(
    "leaves attribution-review backtests pending when next-month attribution is %s",
    (invalidNext) => {
      const attributionsByReportDate = new Map<
        string,
        ProductCategoryAttributionPayload | null
      >([["2026-02-28", syntheticAttribution()]]);
      if (invalidNext !== "missing") {
        attributionsByReportDate.set(
          "2026-03-31",
          syntheticAttribution({
            report_date: "2026-03-31",
            current_report_date: "2026-03-31",
            prior_report_date: "2026-02-28",
            compare: invalidNext === "yoy" ? "yoy" : "mom",
            state: invalidNext === "incomplete" ? "incomplete" : "complete",
          }),
        );
      }
      const surface = selectProductCategoryOperatingActionBacktestSurface({
        payloads: [
          syntheticMonthlyPayload("2026-02-28"),
          syntheticMonthlyPayload("2026-03-31"),
        ],
        attributionsByReportDate,
      });

      expect(
        surface.examples.find((row) => row.actionKind === "review_attribution"),
      ).toMatchObject({ outcomeLabel: "待判定", tone: "neutral" });
      expect(
        surface.actionRows.find((row) => row.actionKind === "review_attribution"),
      ).toMatchObject({ comparableCount: 0, hitCount: 0, hitRate: null });
    },
  );

  it("keeps valid monthly review outcomes evaluable when no unexplained movement remains", () => {
    const surface = selectProductCategoryOperatingActionBacktestSurface({
      payloads: [
        syntheticMonthlyPayload("2026-02-28"),
        syntheticMonthlyPayload("2026-03-31"),
      ],
      attributionsByReportDate: new Map([
        ["2026-02-28", syntheticAttribution()],
        [
          "2026-03-31",
          syntheticAttribution({
            report_date: "2026-03-31",
            current_report_date: "2026-03-31",
            prior_report_date: "2026-02-28",
            rows: [],
          }),
        ],
      ]),
    });

    expect(
      surface.examples.find((row) => row.actionKind === "review_attribution"),
    ).toMatchObject({ outcomeLabel: "命中", tone: "positive" });
    expect(
      surface.actionRows.find((row) => row.actionKind === "review_attribution"),
    ).toMatchObject({ comparableCount: 1, hitCount: 1, hitRate: 1 });
  });

  it("labels cumulative contribution and its unavailable monthly attribution clearly", () => {
    const surface = selectProductCategoryOperatingAnalysisSurface({
      rows: detailRows.map((row) => ({ ...row, view: "ytd" })),
    });
    render(
      createElement(ProductCategoryOperatingAnalysisPanel, {
        surface,
        view: "ytd",
      }),
    );

    expect(screen.getByText(/基于当前正式累计表/)).toBeInTheDocument();
    expect(screen.getByText(/月环比归因仅适用于月度视图/)).toBeInTheDocument();
  });
});
