import { describe, expect, it } from "vitest";

import type { PnlByBusinessYtdItem, ProductCategoryPnlRow } from "../../api/contracts";
import {
  type AssessmentIndicator2025,
  type CenterPnlMapping2025,
  buildTeamPerformanceViewModel,
} from "./teamPerformancePageModel";

function assessmentIndicator(
  partial: Partial<AssessmentIndicator2025> &
    Pick<
      AssessmentIndicator2025,
      | "centerId"
      | "centerName"
      | "indicatorCategory"
      | "metric"
      | "target"
      | "weight"
      | "scoringText"
      | "actual"
      | "progress"
      | "sourceRow"
    >,
): AssessmentIndicator2025 {
  return {
    centerId: partial.centerId,
    centerName: partial.centerName,
    indicatorCategory: partial.indicatorCategory,
    metric: partial.metric,
    target: partial.target,
    weight: partial.weight,
    scoringText: partial.scoringText,
    actual: partial.actual,
    progress: partial.progress,
    score: partial.score ?? null,
    sourceRow: partial.sourceRow,
    blockLabel: partial.blockLabel,
  };
}

function byBusinessRow(
  partial: Partial<PnlByBusinessYtdItem> & Pick<PnlByBusinessYtdItem, "row_key" | "business_type">,
): PnlByBusinessYtdItem {
  return {
    row_key: partial.row_key,
    sort_order: partial.sort_order ?? 1,
    business_type: partial.business_type,
    interest_income: partial.interest_income ?? "0",
    fair_value_change: partial.fair_value_change ?? "0",
    capital_gain: partial.capital_gain ?? "0",
    manual_adjustment: partial.manual_adjustment ?? "0",
    total_pnl: partial.total_pnl ?? "0",
    current_balance: partial.current_balance ?? "0",
    balance_yield_pct: partial.balance_yield_pct ?? null,
    source_kind: partial.source_kind ?? null,
    source_note: partial.source_note ?? null,
    proportion: partial.proportion ?? null,
    assets_count: partial.assets_count ?? 0,
  };
}

function productRow(
  partial: Partial<ProductCategoryPnlRow> &
    Pick<ProductCategoryPnlRow, "category_id" | "category_name" | "level" | "is_total">,
): ProductCategoryPnlRow {
  return {
    category_id: partial.category_id,
    category_name: partial.category_name,
    side: partial.side ?? "asset",
    level: partial.level,
    view: partial.view ?? "ytd",
    report_date: partial.report_date ?? "2025-12-31",
    baseline_ftp_rate_pct: partial.baseline_ftp_rate_pct ?? "0",
    cnx_scale: partial.cnx_scale ?? "0",
    cny_scale: partial.cny_scale ?? "0",
    foreign_scale: partial.foreign_scale ?? "0",
    cnx_cash: partial.cnx_cash ?? "0",
    cny_cash: partial.cny_cash ?? "0",
    foreign_cash: partial.foreign_cash ?? "0",
    cny_ftp: partial.cny_ftp ?? "0",
    foreign_ftp: partial.foreign_ftp ?? "0",
    cny_net: partial.cny_net ?? "0",
    foreign_net: partial.foreign_net ?? "0",
    business_net_income: partial.business_net_income ?? "0",
    weighted_yield: partial.weighted_yield ?? null,
    is_total: partial.is_total,
    children: partial.children ?? [],
    scenario_rate_pct: partial.scenario_rate_pct ?? null,
  };
}

describe("teamPerformancePageModel", () => {
  it("sums workbook scores while preserving pending-score flags", () => {
    const indicators: AssessmentIndicator2025[] = [
      assessmentIndicator({
        centerId: "demo-center",
        centerName: "示例中心",
        indicatorCategory: "效益类",
        metric: "指标一",
        target: "目标一",
        weight: 10,
        scoringText: "线性打分",
        actual: "已完成",
        progress: "100%",
        score: 9,
        sourceRow: 1,
      }),
      assessmentIndicator({
        centerId: "demo-center",
        centerName: "示例中心",
        indicatorCategory: "规模类",
        metric: "指标二",
        target: "目标二",
        weight: 5,
        scoringText: "待补分",
        actual: "待确认",
        progress: "待确认",
        score: null,
        sourceRow: 2,
      }),
    ];

    const viewModel = buildTeamPerformanceViewModel({ indicators });

    expect(viewModel.totalWorkbookScore).toBe(9);
    expect(viewModel.centers).toHaveLength(1);
    expect(viewModel.centers[0]).toMatchObject({
      weightTotal: 15,
      workbookScore: 9,
      hasPendingScore: true,
    });
  });

  it("builds mapped pnl and scale totals from by-business and product-category evidence", () => {
    const viewModel = buildTeamPerformanceViewModel({
      byBusinessItems: [
        byBusinessRow({
          row_key: "asset_zqtz_detail_structured_finance_broker",
          business_type: "其中：结构化融资（券商）",
          total_pnl: "3500000",
          current_balance: "800000000",
        }),
        byBusinessRow({
          row_key: "asset_zqtz_nonfinancial_enterprise_bond",
          business_type: "非金融企业债券",
          total_pnl: "2600000",
          current_balance: "650000000",
        }),
      ],
      productCategoryRows: [
        productRow({
          category_id: "intermediate_business_income",
          category_name: "中间业务收入",
          level: 1,
          is_total: false,
          business_net_income: "1800000",
        }),
      ],
    });

    const productAndMarketCenter = viewModel.centers.find(
      (center) => center.centerId === "product-market",
    );
    const customerBusinessCenter = viewModel.centers.find(
      (center) => center.centerId === "customer-business",
    );

    expect(productAndMarketCenter).toMatchObject({
      mappedPnlTotalYuan: 5300000,
      mappedScaleTotalYuan: 800000000,
    });
    expect(customerBusinessCenter).toMatchObject({
      mappedPnlTotalYuan: 4400000,
      mappedScaleTotalYuan: 650000000,
    });
  });

  it("does not double count duplicate mapping rows inside a center", () => {
    const indicators: AssessmentIndicator2025[] = [
      assessmentIndicator({
        centerId: "dedupe-center",
        centerName: "去重中心",
        indicatorCategory: "效益类",
        metric: "示例指标",
        target: "示例目标",
        weight: 10,
        scoringText: "线性打分",
        actual: "已完成",
        progress: "100%",
        score: 10,
        sourceRow: 1,
      }),
    ];
    const mappings: CenterPnlMapping2025[] = [
      {
        centerId: "dedupe-center",
        endpoint: "product-category-ytd",
        rowId: "intermediate_business_income",
        pnlField: "business_net_income",
        confidence: "high",
      },
      {
        centerId: "dedupe-center",
        endpoint: "product-category-ytd",
        rowId: "intermediate_business_income",
        pnlField: "business_net_income",
        confidence: "high",
      },
    ];

    const viewModel = buildTeamPerformanceViewModel({
      indicators,
      mappings,
      productCategoryRows: [
        productRow({
          category_id: "intermediate_business_income",
          category_name: "中间业务收入",
          level: 1,
          is_total: false,
          business_net_income: "2000000",
        }),
      ],
    });

    expect(viewModel.centers[0]).toMatchObject({
      mappedPnlTotalYuan: 2000000,
    });
    expect(viewModel.centers[0].evidenceRows).toHaveLength(1);
  });

  it("surfaces unmapped metrics in center coverage warnings", () => {
    const viewModel = buildTeamPerformanceViewModel();

    const productAndMarketCenter = viewModel.centers.find(
      (center) => center.centerId === "product-market",
    );
    const interbankCenter = viewModel.centers.find(
      (center) => center.centerId === "interbank-finance",
    );
    const jinanCenter = viewModel.centers.find(
      (center) => center.centerId === "jinan-branch",
    );

    expect(productAndMarketCenter?.coverageWarnings.join(" ")).toContain("金融债发行规模");
    expect(interbankCenter?.coverageWarnings.join(" ")).toContain("同业银团贷款中间业务收入");
    expect(jinanCenter).toMatchObject({
      mappingStatus: "挂钩引用",
    });
  });
});
