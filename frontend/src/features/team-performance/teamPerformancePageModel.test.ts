import { describe, expect, it } from "vitest";

import type {
  PnlByBusinessMonthlyItem,
  PnlByBusinessMonthlyPayload,
  PnlByBusinessYtdItem,
  ProductCategoryPnlRow,
} from "../../api/contracts";
import {
  type AssessmentIndicator2025,
  type CenterPnlMapping2025,
  Q1_CENTER_CALIBER_RULES,
  buildTeamPerformanceQ1CaliberModel,
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

  it("splits Q1 interbank and FX rows by currency fields and keeps derivatives out of FX", () => {
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
          category_name: "衍生品",
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
          business_type: "其中：结构化融资（券商）",
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
          business_type: "其中：结构化融资（券商）",
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
          business_type: "其中：结构化融资（券商）",
          total_pnl: "30000000",
          source_note: "ZQTZSHOW 其中项：instrument_code prefix=J4",
        }),
      ],
      byBusinessMonthly: byBusinessMonthlyPayload([
        monthlyBusinessItem({
          row_key: "asset_zqtz_detail_structured_finance_broker",
          business_type: "其中：结构化融资（券商）",
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
      rowName: "其中：结构化融资（券商）",
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
