import { describe, expect, it } from "vitest";

import type {
  PnlByBusinessMonthlyItem,
  PnlByBusinessMonthlyPayload,
  PnlByBusinessYtdItem,
  ProductCategoryPnlRow,
  ResultMeta,
  TeamPerformanceAssessmentIndicator,
  TeamPerformanceAssessmentWorkbookPayload,
} from "../../api/contracts";
import { buildMockTeamPerformanceAssessmentWorkbookPayload } from "../../mocks/teamPerformanceMockClient";
import { EM_DASH } from "../../pageModel";
import {
  type AssessmentIndicator2025,
  type CenterPnlMapping2025,
  type TeamPerformanceQ1CaliberRule,
  Q1_CENTER_CALIBER_RULES,
  buildTeamPerformanceQ1CaliberModel,
  buildTeamPerformanceViewModel,
  formatRatePct,
  formatScore,
  formatWanFromYuan,
  formatYiFromYuan,
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

/** 模拟后端 `_build_center_summaries`：把 camelCase 底稿行转成后端下发的 workbook payload。 */
function workbookFromIndicators(
  indicators: AssessmentIndicator2025[],
  mappings: CenterPnlMapping2025[] = [],
): TeamPerformanceAssessmentWorkbookPayload {
  const toBackendIndicator = (
    item: AssessmentIndicator2025,
  ): TeamPerformanceAssessmentIndicator => ({
    center_id: item.centerId,
    center_name: item.centerName,
    indicator_category: item.indicatorCategory,
    metric: item.metric,
    target: item.target,
    weight: item.weight,
    scoring_text: item.scoringText,
    actual: item.actual,
    progress: item.progress,
    score: item.score,
    source_row: item.sourceRow,
    block_label: item.blockLabel ?? null,
  });
  const centerIds: string[] = [];
  for (const item of indicators) {
    if (!centerIds.includes(item.centerId)) {
      centerIds.push(item.centerId);
    }
  }
  const centers = centerIds.map((centerId) => {
    const centerIndicators = indicators.filter((item) => item.centerId === centerId);
    const weightTotal = centerIndicators.reduce((sum, item) => sum + item.weight, 0);
    const workbookScore = centerIndicators.reduce((sum, item) => sum + (item.score ?? 0), 0);
    return {
      center_id: centerId,
      center_name: centerIndicators[0].centerName,
      weight_total: weightTotal,
      workbook_score: workbookScore,
      has_pending_score: centerIndicators.some((item) => item.score === null),
      score_rate: weightTotal > 0 ? workbookScore / weightTotal : null,
      indicators: centerIndicators.map(toBackendIndicator),
    };
  });
  return {
    assessment_year: 2025,
    caliber_label: "静态底稿·非正式口径（后端下发）",
    caliber_note: "测试用底稿。",
    source_label: "测试用底稿。",
    centers,
    mappings: mappings.map((mapping) => ({
      center_id: mapping.centerId,
      endpoint: mapping.endpoint,
      row_id: mapping.rowId,
      pnl_field: mapping.pnlField ?? null,
      scale_field: mapping.scaleField ?? null,
      confidence: mapping.confidence,
      note: mapping.note ?? null,
      additive: mapping.additive ?? null,
    })),
    total_workbook_score: centers.reduce((sum, center) => sum + center.workbook_score, 0),
    total_center_count: centers.length,
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
    avg_balance: partial.avg_balance ?? "0",
    current_balance: partial.current_balance ?? "0",
    balance_yield_pct: partial.balance_yield_pct ?? null,
    annualized_yield_pct: partial.annualized_yield_pct ?? null,
    ftp_rate_pct: partial.ftp_rate_pct ?? "1.60",
    ftp_cost: partial.ftp_cost ?? null,
    ftp_net_pnl: partial.ftp_net_pnl ?? null,
    ftp_net_annualized_yield_pct: partial.ftp_net_annualized_yield_pct ?? null,
    source_kind: partial.source_kind ?? null,
    source_note: partial.source_note ?? null,
    proportion: partial.proportion ?? null,
    assets_count: partial.assets_count ?? 0,
  };
}

function monthlyBusinessItem(
  partial: Partial<PnlByBusinessMonthlyItem> &
    Pick<PnlByBusinessMonthlyItem, "row_key" | "business_type">,
): PnlByBusinessMonthlyItem {
  return {
    row_key: partial.row_key,
    sort_order: partial.sort_order ?? 1,
    business_type: partial.business_type,
    interest_income: partial.interest_income ?? "0",
    fair_value_change: partial.fair_value_change ?? "0",
    capital_gain: partial.capital_gain ?? "0",
    manual_adjustment: partial.manual_adjustment ?? "0",
    total_pnl: partial.total_pnl ?? "0",
    avg_balance: partial.avg_balance ?? "0",
    current_balance: partial.current_balance ?? "0",
    annualized_yield_pct: partial.annualized_yield_pct ?? null,
    ftp_rate_pct: partial.ftp_rate_pct ?? "1.60",
    ftp_cost: partial.ftp_cost ?? "0",
    ftp_net_pnl: partial.ftp_net_pnl ?? "0",
    ftp_net_annualized_yield_pct: partial.ftp_net_annualized_yield_pct ?? null,
    proportion: partial.proportion ?? null,
    asset_count: partial.asset_count ?? 0,
    source_note: partial.source_note ?? null,
  };
}

function byBusinessMonthlyPayload(items: PnlByBusinessMonthlyItem[]): PnlByBusinessMonthlyPayload {
  return {
    year: 2026,
    as_of_date: "2026-03-31",
    source_tables: ["fact_formal_pnl_fi", "fact_formal_zqtz_balance_daily"],
    management_change: null,
    months: [
      {
        month_key: "2026-03",
        period_start_date: "2026-03-01",
        period_end_date: "2026-03-31",
        calendar_days: 31,
        summary: {
          interest_income: "0",
          fair_value_change: "0",
          capital_gain: "0",
          manual_adjustment: "0",
          total_pnl: "0",
          avg_balance: "0",
          current_balance: "0",
          annualized_yield_pct: null,
          ftp_rate_pct: "1.60",
          ftp_cost: "0",
          ftp_net_pnl: "0",
          ftp_net_annualized_yield_pct: null,
          asset_count: 0,
        },
        items,
      },
    ],
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
  it("consumes backend-aggregated workbook scores while preserving pending-score flags", () => {
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

    const viewModel = buildTeamPerformanceViewModel({
      workbook: workbookFromIndicators(indicators),
    });

    expect(viewModel.totalWorkbookScore).toBe(9);
    expect(viewModel.centers).toHaveLength(1);
    expect(viewModel.centers[0]).toMatchObject({
      weightTotal: 15,
      workbookScore: 9,
      hasPendingScore: true,
      scoreRate: 9 / 15,
    });
  });

  it("returns an empty pending model when the backend workbook is not loaded", () => {
    const viewModel = buildTeamPerformanceViewModel();

    expect(viewModel.centers).toHaveLength(0);
    expect(viewModel.totalWorkbookScore).toBe(0);
    expect(viewModel.totalCenterCount).toBe(0);
    expect(viewModel.warnings.join(" ")).toContain("考核底稿尚未从后端加载");
  });

  it("builds mapped pnl and scale totals from by-business and product-category evidence", () => {
    const viewModel = buildTeamPerformanceViewModel({
      workbook: buildMockTeamPerformanceAssessmentWorkbookPayload(),
      byBusinessItems: [
        byBusinessRow({
          row_key: "asset_zqtz_detail_structured_finance_broker",
          business_type: "其中：结构化产业基金（产业基金部分）",
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
      workbook: workbookFromIndicators(indicators, mappings),
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

  it("excludes linked non-additive evidence from the mapped-team candidate count", () => {
    const indicators: AssessmentIndicator2025[] = [
      assessmentIndicator({
        centerId: "reference-center",
        centerName: "挂钩中心",
        indicatorCategory: "效益类",
        metric: "挂钩参考收入",
        target: "参考正式读模型，不并入中心归因",
        weight: 10,
        scoringText: "参考口径",
        actual: "挂钩引用",
        progress: "挂钩引用",
        score: 10,
        sourceRow: 1,
      }),
    ];
    const mappings: CenterPnlMapping2025[] = [
      {
        centerId: "reference-center",
        endpoint: "product-category-ytd",
        rowId: "intermediate_business_income",
        pnlField: "business_net_income",
        confidence: "linked",
        additive: false,
      },
    ];

    const viewModel = buildTeamPerformanceViewModel({
      workbook: workbookFromIndicators(indicators, mappings),
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

    expect(viewModel.mappedCenterCount).toBe(0);
    expect(viewModel.visibleEvidenceStatus).toBe("暂无正式映射证据");
    expect(viewModel.centers[0]).toMatchObject({
      mappingStatus: "挂钩引用",
      mappedPnlTotalYuan: null,
      mappedScaleTotalYuan: null,
    });
    expect(viewModel.centers[0].evidenceRows).toHaveLength(1);
  });

  it("surfaces unmapped metrics in center coverage warnings", () => {
    const viewModel = buildTeamPerformanceViewModel({
      workbook: buildMockTeamPerformanceAssessmentWorkbookPayload(),
    });

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

  it("keeps Q1 self-investment and bond-trading business boundaries separate", () => {
    const model = buildTeamPerformanceQ1CaliberModel();
    const selfInvestment = model.centers.find((center) => center.centerId === "self-investment");
    const bondTrading = model.centers.find((center) => center.centerId === "bond-trading");

    expect(
      selfInvestment?.rules
        .filter((rule) => rule.allocation === "include")
        .map((rule) => rule.businessLabel),
    ).toEqual([
      "公募基金",
      "企业债",
      "中期票据",
      "商业银行债",
      "资产支持证券",
      "人民币资管产品",
      "非银行金融债",
      "次级债券",
      "债权投资",
      "短期融资券",
    ]);
    expect(
      selfInvestment?.rules
        .filter((rule) => rule.allocation === "include")
        .map((rule) => rule.rowId),
    ).not.toEqual(
      expect.arrayContaining([
        "asset_zqtz_policy_financial_bond",
        "asset_zqtz_interbank_cd",
        "asset_zqtz_local_government_bond",
        "asset_zqtz_treasury_bond",
        "asset_zqtz_railway_bond",
      ]),
    );
    expect(
      bondTrading?.rules
        .filter((rule) => rule.allocation === "include")
        .map((rule) => rule.businessLabel),
    ).toEqual(["政策性金融债", "同业存单", "地方政府债券", "国债", "铁道债"]);
  });

  it("splits Q1 interbank and FX rows by currency fields and keeps aggregate FX derivative evidence pending", () => {
    const model = buildTeamPerformanceQ1CaliberModel({
      productCategoryRows: [
        productRow({
          category_id: "interbank_lending_assets",
          category_name: "拆放同业",
          level: 0,
          is_total: false,
          cny_net: "10000000",
          foreign_net: "7000000",
        }),
        productRow({
          category_id: "bond_investment",
          category_name: "债券投资",
          level: 0,
          is_total: false,
          foreign_net: "11000000",
        }),
        productRow({
          category_id: "interbank_borrowings",
          category_name: "同业拆入",
          level: 0,
          is_total: false,
          cny_net: "4000000",
          foreign_net: "-2000000",
        }),
        productRow({
          category_id: "derivatives",
          category_name: "汇兑损益及衍生",
          level: 0,
          is_total: false,
          business_net_income: "-5000000",
        }),
      ],
    });

    const interbank = model.centers.find((center) => center.centerId === "interbank-finance");
    const fx = model.centers.find((center) => center.centerId === "fx-derivatives");
    const customer = model.centers.find((center) => center.centerId === "customer-business");

    expect(interbank?.rules.find((rule) => rule.rowId === "interbank_lending_assets")).toMatchObject({
      amountField: "cny_net",
      amountYuan: 10000000,
    });
    expect(fx?.rules.find((rule) => rule.rowId === "interbank_lending_assets")).toMatchObject({
      amountField: "foreign_net",
      amountYuan: 7000000,
    });
    expect(fx?.rules.some((rule) => rule.rowId === "derivatives")).toBe(false);
    expect(customer?.rules.find((rule) => rule.rowId === "derivatives")).toMatchObject({
      allocation: "reference",
      evidenceStatus: "split-needed",
      rowName: "汇兑损益及衍生",
      amountYuan: -5000000,
    });
  });

  it("subtracts structured financing from Q1 self-investment RMB asset management", () => {
    const model = buildTeamPerformanceQ1CaliberModel({
      byBusinessItems: [
        byBusinessRow({
          row_key: "asset_zqtz_public_fund",
          business_type: "公募基金",
          total_pnl: "100000000",
        }),
        byBusinessRow({
          row_key: "asset_zqtz_detail_securities_asset_management_plan",
          business_type: "证券业资管计划",
          total_pnl: "1000000000",
        }),
        byBusinessRow({
          row_key: "asset_zqtz_detail_structured_finance_broker",
          business_type: "其中：结构化产业基金（产业基金部分）",
          total_pnl: "250000000",
        }),
      ],
      byBusinessMonthly: byBusinessMonthlyPayload([
        monthlyBusinessItem({
          row_key: "asset_zqtz_public_fund",
          business_type: "公募基金",
          total_pnl: "100000000",
          ftp_cost: "20000000",
          ftp_net_pnl: "80000000",
        }),
        monthlyBusinessItem({
          row_key: "asset_zqtz_detail_securities_asset_management_plan",
          business_type: "证券业资管计划",
          total_pnl: "1000000000",
          ftp_cost: "150000000",
          ftp_net_pnl: "850000000",
        }),
        monthlyBusinessItem({
          row_key: "asset_zqtz_detail_structured_finance_broker",
          business_type: "其中：结构化产业基金（产业基金部分）",
          total_pnl: "250000000",
          ftp_cost: "80000000",
          ftp_net_pnl: "170000000",
        }),
      ]),
    });

    const selfInvestment = model.centers.find((center) => center.centerId === "self-investment");
    const productMarket = model.centers.find((center) => center.centerId === "product-market");

    expect(selfInvestment?.includedTotalYuan).toBe(760000000);
    expect(productMarket?.includedTotalYuan).toBe(170000000);
    expect(
      selfInvestment?.rules.find(
        (rule) => rule.rowId === "asset_zqtz_detail_structured_finance_broker",
      ),
    ).toMatchObject({
      allocation: "subtract",
      amountField: "ftp_net_pnl",
      sourceEndpoint: "by-business-monthly",
      contributionYuan: -170000000,
    });
  });

  it("uses J4 asset evidence as the Q1 product-market industry fund caliber", () => {
    const model = buildTeamPerformanceQ1CaliberModel({
      byBusinessItems: [
        byBusinessRow({
          row_key: "asset_zqtz_detail_structured_finance_broker",
          business_type: "其中：结构化产业基金（产业基金部分）",
          total_pnl: "30000000",
          source_note: "ZQTZSHOW 其中项：instrument_code prefix=J4",
        }),
      ],
      byBusinessMonthly: byBusinessMonthlyPayload([
        monthlyBusinessItem({
          row_key: "asset_zqtz_detail_structured_finance_broker",
          business_type: "其中：结构化产业基金（产业基金部分）",
          total_pnl: "30000000",
          ftp_cost: "5000000",
          ftp_net_pnl: "25000000",
          source_note: "ZQTZSHOW 其中项：instrument_code prefix=J4",
        }),
      ]),
    });

    const productMarket = model.centers.find((center) => center.centerId === "product-market");

    expect(productMarket?.pendingRuleCount).toBe(0);
    expect(productMarket?.rules).toHaveLength(1);
    expect(productMarket?.rules[0]).toMatchObject({
      businessLabel: "产业基金",
      rowId: "asset_zqtz_detail_structured_finance_broker",
      rowName: "其中：结构化产业基金（产业基金部分）",
      allocation: "include",
      evidenceStatus: "direct",
      amountField: "ftp_net_pnl",
      sourceEndpoint: "by-business-monthly",
      amountYuan: 25000000,
      contributionYuan: 25000000,
    });
    expect(productMarket?.rules[0].note).toContain("J4");
  });

  it("counts each Q1 aggregate source row only once inside a center", () => {
    const model = buildTeamPerformanceQ1CaliberModel({
      byBusinessItems: [
        byBusinessRow({
          row_key: "asset_zqtz_nonfinancial_enterprise_bond",
          business_type: "非金融企业债券",
          total_pnl: "300000000",
        }),
      ],
      byBusinessMonthly: byBusinessMonthlyPayload([
        monthlyBusinessItem({
          row_key: "asset_zqtz_nonfinancial_enterprise_bond",
          business_type: "非金融企业债券",
          total_pnl: "300000000",
          ftp_cost: "60000000",
          ftp_net_pnl: "240000000",
        }),
      ]),
    });

    const selfInvestment = model.centers.find((center) => center.centerId === "self-investment");
    const nonfinancialRules = selfInvestment?.rules.filter(
      (rule) => rule.rowId === "asset_zqtz_nonfinancial_enterprise_bond",
    );

    expect(selfInvestment?.includedTotalYuan).toBe(240000000);
    expect(nonfinancialRules?.map((rule) => rule.contributionYuan)).toEqual([
      240000000,
      null,
      null,
    ]);
    expect(nonfinancialRules?.[1].note).toContain("前序子项计入汇总");
  });

  it("uses FTP-net monthly business evidence instead of raw Q1 total_pnl", () => {
    const model = buildTeamPerformanceQ1CaliberModel({
      byBusinessItems: [
        byBusinessRow({
          row_key: "asset_zqtz_public_fund",
          business_type: "公募基金",
          total_pnl: "100000000",
        }),
      ],
      byBusinessMonthly: byBusinessMonthlyPayload([
        monthlyBusinessItem({
          row_key: "asset_zqtz_public_fund",
          business_type: "公募基金",
          total_pnl: "100000000",
          ftp_cost: "30000000",
          ftp_net_pnl: "70000000",
        }),
      ]),
    });

    const publicFund = model.centers
      .find((center) => center.centerId === "self-investment")
      ?.rules.find((rule) => rule.rowId === "asset_zqtz_public_fund");

    expect(publicFund).toMatchObject({
      sourceEndpoint: "by-business-monthly",
      amountField: "ftp_net_pnl",
      amountYuan: 70000000,
      contributionYuan: 70000000,
    });
    expect(buildMockTeamPerformanceAssessmentWorkbookPayload().mappings.find(
      (mapping) => mapping.row_id === "asset_zqtz_detail_structured_finance_broker",
    )?.note).toContain("结构化产业基金（产业基金部分）");
  });

  it("does not silently fall back to raw total_pnl when FTP-net monthly evidence is missing", () => {
    const model = buildTeamPerformanceQ1CaliberModel({
      byBusinessItems: [
        byBusinessRow({
          row_key: "asset_zqtz_public_fund",
          business_type: "公募基金",
          total_pnl: "100000000",
        }),
      ],
    });

    const publicFund = model.centers
      .find((center) => center.centerId === "self-investment")
      ?.rules.find((rule) => rule.rowId === "asset_zqtz_public_fund");

    expect(publicFund).toMatchObject({
      sourceEndpoint: "by-business-monthly",
      amountField: "ftp_net_pnl",
      amountYuan: null,
      contributionYuan: null,
    });
  });

  it("does not encode Excel prediction rows as Q1 actual caliber rules", () => {
    const labels = Q1_CENTER_CALIBER_RULES.map((rule) => rule.businessLabel);

    expect(labels).not.toEqual(expect.arrayContaining(["营收", "线性外推合计", "全年预测"]));
  });
});

describe("Q1 evidence completeness", () => {
  const rule: TeamPerformanceQ1CaliberRule = {
    centerId: "synthetic-center",
    centerName: "合成测试中心",
    businessLabel: "合成测试业务",
    sourceEndpoint: "by-business-monthly",
    rowId: "synthetic-row",
    amountField: "ftp_net_pnl",
    allocation: "include",
    evidenceStatus: "direct",
  };
  const meta: ResultMeta = {
    // Both live and precomputed monthly envelopes use this analytical contract.
    trace_id: "synthetic-q1", basis: "analytical", result_kind: "pnl.by_business_monthly",
    formal_use_allowed: false, source_version: "synthetic", vendor_version: "synthetic",
    rule_version: "synthetic", cache_version: "synthetic", quality_flag: "ok",
    vendor_status: "ok", fallback_mode: "none", scenario_flag: false,
    generated_at: "2026-04-01T00:00:00Z",
  };
  function monthly(values: Array<string | null | undefined>): PnlByBusinessMonthlyPayload {
    const template = byBusinessMonthlyPayload([]);
    return {
      ...template,
      months: values.map((value, index) => {
        const monthKey = `2026-0${index + 1}`;
        const days = index === 1 ? 28 : 31;
        return {
          ...template.months[0], month_key: monthKey,
          period_start_date: `${monthKey}-01`, period_end_date: `${monthKey}-${days}`,
          calendar_days: days, coverage_days: days, expected_days: days, sample_filled: false,
          items: value === undefined ? [] : [{
            ...monthlyBusinessItem({ row_key: rule.rowId!, business_type: rule.businessLabel }),
            ftp_net_pnl: value,
          }],
        };
      }),
    };
  }
  function model(payload: PnlByBusinessMonthlyPayload | null, rules = [rule]) {
    return buildTeamPerformanceQ1CaliberModel({ rules, byBusinessMonthly: payload, byBusinessMeta: meta });
  }

  it("distinguishes a null February from real zero without changing the known subtotal", () => {
    const partial = model(monthly(["100", null, "300"]));
    const zero = model(monthly(["100", "0", "300"]));
    expect(partial.centers[0]).toMatchObject({ includedTotalYuan: 400, coverageStatus: "partial" });
    expect(partial.centers[0].rules[0]).toMatchObject({ amountYuan: 400, coverageStatus: "partial" });
    expect(partial.centers[0].rules[0].coverageWarnings.join(" ")).toContain("2026-02 FTP后净损益不可用");
    expect(zero.centers[0]).toMatchObject({ includedTotalYuan: 400, coverageStatus: "complete" });
  });

  it.each(["duplicate month", "duplicate row", "extra month"] as const)(
    "retains original amount aggregation for %s while flagging ambiguous quarter coverage", (kind) => {
      const payload = monthly(["100", "200", "300"]);
      if (kind === "duplicate month") payload.months.push(payload.months[1]);
      if (kind === "duplicate row") payload.months[0].items.push(payload.months[0].items[0]);
      if (kind === "extra month") payload.months.push({ ...payload.months[2], month_key: "2026-04" });
      const result = model(payload).centers[0];
      expect(result.includedTotalYuan).toBe(kind === "duplicate month" ? 800 : kind === "duplicate row" ? 700 : 900);
      expect(result.coverageStatus).toBe("partial");
      expect(result.coverageWarnings.join(" ")).toContain(kind === "extra month" ? "季度外月份：2026-04" : "重复");
    },
  );

  it("preserves source-order floating point addition when months are reordered", () => {
    const payload = monthly(["10000000000000000", "1", "-10000000000000000"]);
    // In source order, cancellation happens before the final +1. Sorting would lose it.
    payload.months = [payload.months[0], payload.months[2], payload.months[1]];
    expect(model(payload).centers[0]).toMatchObject({ includedTotalYuan: 1, coverageStatus: "complete" });
  });

  it.each([
    ["healthy", ["100", "200", "300"], 600, "complete"],
    ["valid zeros", ["0", "0", "0"], 0, "complete"],
    ["all null", [null, null, null], null, "unavailable"],
    ["missing row", ["100", undefined, "300"], 400, "partial"],
    ["nonfinite", ["100", "NaN", "300"], 400, "partial"],
    ["infinite", ["100", "Infinity", "300"], 400, "partial"],
    ["empty", ["100", "", "300"], 400, "partial"],
  ] as const)("preserves %s semantics", (_name, values, amount, coverageStatus) => {
    const result = model(monthly([...values])).centers[0];
    expect(result).toMatchObject({ includedTotalYuan: amount, coverageStatus });
    expect(result.rules[0]).toMatchObject({ amountYuan: amount, coverageStatus });
  });

  it("names missing January and February for March-only evidence", () => {
    const payload = monthly(["100", "200", "300"]);
    payload.months = payload.months.slice(2);
    const result = model(payload).centers[0];
    expect(result).toMatchObject({ includedTotalYuan: 300, coverageStatus: "partial" });
    expect(result.rules[0].coverageWarnings.join(" ")).toContain("缺少月份：2026-01、2026-02");
  });

  it("treats an omitted FTP field as unavailable rather than zero", () => {
    const payload = monthly(["100", "200", "300"]);
    delete (payload.months[1].items[0] as Partial<PnlByBusinessMonthlyItem>).ftp_net_pnl;
    expect(model(payload).centers[0]).toMatchObject({ includedTotalYuan: 400, coverageStatus: "partial" });
  });

  it("keeps day coverage, sample fill, truncated periods and pending balance issues visible", () => {
    const payload = monthly(["100", "200", "300"]);
    Object.assign(payload.months[1], {
      coverage_days: 10, sample_filled: true, sample_fill_method: "observed_days_scaled_to_calendar",
      period_end_date: "2026-02-20",
      balance_quality_issues: [{ issue_id: "synthetic", report_date: "2026-02-10", status: "pending",
        reason: "合成余额缺口", source_file: "synthetic", source_version: "synthetic" }],
    });
    const result = model(payload).centers[0];
    expect(result).toMatchObject({ includedTotalYuan: 600, coverageStatus: "partial" });
    const warnings = result.rules[0].coverageWarnings.join(" ");
    expect(warnings).toContain("10/28");
    expect(warnings).toContain("observed_days_scaled_to_calendar");
    expect(warnings).toContain("2026-02-20");
    expect(warnings).toContain("合成余额缺口");
  });

  it("reports unknown completeness when legacy payload omits day coverage", () => {
    const payload = monthly(["100", "200", "300"]);
    delete payload.months[1].coverage_days;
    const result = model(payload).centers[0];
    expect(result).toMatchObject({ includedTotalYuan: 600, coverageStatus: "unknown" });
    expect(result.rules[0].coverageWarnings.join(" ")).toContain("2026-02 缺少日覆盖信息");
  });

  it("does not claim completeness when day coverage is null or invalid", () => {
    const payload = monthly(["100", "200", "300"]);
    Object.assign(payload.months[1], { coverage_days: null, expected_days: null });
    expect(model(payload).centers[0]).toMatchObject({ includedTotalYuan: 600, coverageStatus: "unknown" });
    Object.assign(payload.months[1], { coverage_days: 0, expected_days: 0 });
    expect(model(payload).centers[0].coverageStatus).toBe("unknown");
  });

  it("keeps complete product-currency zero and flags source-date or metadata gaps", () => {
    const productRule: TeamPerformanceQ1CaliberRule = { ...rule, sourceEndpoint: "product-category-ytd", amountField: "foreign_net" };
    const row = productRow({ category_id: rule.rowId!, category_name: "合成产品", level: 1, is_total: false,
      report_date: "2026-03-31", view: "ytd", foreign_net: "0" });
    const args = { rules: [productRule], productCategoryRows: [row], productCategoryMeta: meta };
    expect(buildTeamPerformanceQ1CaliberModel(args).centers[0]).toMatchObject({ includedTotalYuan: 0, coverageStatus: "complete" });
    expect(buildTeamPerformanceQ1CaliberModel({ ...args, productCategoryMeta: null }).centers[0].coverageStatus).toBe("unknown");
    row.report_date = "2025-12-31";
    expect(buildTeamPerformanceQ1CaliberModel(args).centers[0].coverageStatus).toBe("partial");
  });

  it("does not let a missing subtract component look like a complete center total", () => {
    const result = model(monthly(["100", "200", "300"]), [rule, {
      ...rule, businessLabel: "待扣除项", rowId: "missing-subtract", allocation: "subtract",
    }]).centers[0];
    expect(result).toMatchObject({ includedTotalYuan: 600, coverageStatus: "partial" });
  });

  it("preserves deduplication and excludes reference and excluded rows from total coverage", () => {
    const result = model(monthly(["100", "200", "300"]), [rule, { ...rule },
      { ...rule, rowId: "reference", allocation: "reference" },
      { ...rule, rowId: "excluded", evidenceStatus: "excluded" },
    ]).centers[0];
    expect(result).toMatchObject({ includedTotalYuan: 600, coverageStatus: "complete" });
    expect(result.rules.map((row) => row.contributionYuan)).toEqual([600, null, null, null]);
  });

  it("discloses Q1 result quality separately and never fills an unavailable payload", () => {
    const result = buildTeamPerformanceQ1CaliberModel({ rules: [rule], byBusinessMonthly: null,
      byBusinessMeta: { ...meta, quality_flag: "stale", fallback_mode: "latest_snapshot" } });
    expect(result.centers[0]).toMatchObject({ includedTotalYuan: null, coverageStatus: "unavailable" });
    expect(result.warnings.join(" ")).toContain("Q1业务种类月度损益 quality_flag=stale");
    expect(result.warnings.join(" ")).toContain("fallback_mode=latest_snapshot");
  });
});

// 锁定本页格式化器的 zh-CN locale 语义（千分位 + 去尾零）与缺失值占位：
// 这是它们不能替换为共享 `fixedOrDash`/`pctOrDash`（toFixed，恒定小数位）的原因。
describe("teamPerformancePageModel display formatters", () => {
  it("formats wan/yi amounts with zh-CN grouping and trimmed trailing zeros", () => {
    expect(formatWanFromYuan(123_456_789)).toBe("12,345.68 万元");
    expect(formatWanFromYuan(5_300_000)).toBe("530 万元");
    expect(formatYiFromYuan(123_456_789)).toBe("1.23 亿元");
    expect(formatYiFromYuan(800_000_000)).toBe("8 亿元");
  });

  it("renders missing amounts and rates as a bare em dash without unit suffix", () => {
    expect(formatWanFromYuan(null)).toBe(EM_DASH);
    expect(formatYiFromYuan(null)).toBe(EM_DASH);
    expect(formatRatePct(null)).toBe(EM_DASH);
  });

  it("formats score rate as trimmed percentage and pending score with its own placeholder", () => {
    expect(formatRatePct(0.6)).toBe("60%");
    expect(formatRatePct(0.8567)).toBe("85.67%");
    expect(formatScore(9)).toBe("9 分");
    expect(formatScore(null)).toBe("待补分");
  });
});
