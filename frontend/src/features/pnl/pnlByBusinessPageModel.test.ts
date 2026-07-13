import { describe, expect, it } from "vitest";

import type {
  PnlByBusinessAnalysisRow,
  PnlByBusinessMonthlyBucket,
  PnlByBusinessPayload,
  PnlByBusinessYtdPayload,
  ResultMeta,
} from "../../api/contracts";
import {
  buildPnlByBusinessMonthlyAdjustmentBridge,
  buildPnlByBusinessSelectedDrilldownModel,
  buildPnlByBusinessPageModel,
  buildPnlByBusinessSelectionModel,
  formatAvgBalanceYi,
  isParentZqtzBusinessRow,
  resolvePnlByBusinessActiveMonthlyBucket,
  VIEW_MODE_BUSINESS_QUESTIONS,
} from "./pnlByBusinessPageModel";

function meta(partial: Partial<ResultMeta> = {}): ResultMeta {
  return {
    trace_id: "tr_pnl_business_model",
    basis: "formal",
    result_kind: "pnl.by-business",
    formal_use_allowed: true,
    source_version: "sv_pnl_business_model",
    vendor_version: "vv_pnl_business_model",
    rule_version: "rv_pnl_business_model",
    cache_version: "cv_pnl_business_model",
    quality_flag: "ok",
    vendor_status: "ok",
    fallback_mode: "none",
    scenario_flag: false,
    as_of_date: "2026-04-30",
    generated_at: "2026-05-01T09:00:00Z",
    evidence_rows: 12,
    ...partial,
  };
}

function ytdPayload(partial: Partial<PnlByBusinessYtdPayload> = {}): PnlByBusinessYtdPayload {
  return {
    year: 2026,
    period_type: "yearly",
    period_label: "2026 年累计",
    period_start_date: "2026-01-01",
    period_end_date: "2026-04-30",
    total_pnl: "5000000",
    source_tables: ["pnl_ytd"],
    items: [
      {
        row_key: "asset_zqtz_parent_a",
        sort_order: 1,
        business_type: "债券投资",
        interest_income: "1000000",
        fair_value_change: "0",
        capital_gain: "0",
        manual_adjustment: "0",
        total_pnl: "1000000",
        avg_balance: "100000000",
        current_balance: "100000000",
        balance_yield_pct: null,
        annualized_yield_pct: null,
        ftp_rate_pct: "1.60",
        ftp_cost: "100000",
        ftp_net_pnl: "900000",
        ftp_net_annualized_yield_pct: "2.7375",
        source_kind: "zqtz",
        source_note: "父级",
        proportion: "0.2",
        assets_count: 2,
      },
      {
        row_key: "asset_zqtz_parent_b",
        sort_order: 2,
        business_type: "非底层投资资产",
        interest_income: "3000000",
        fair_value_change: "0",
        capital_gain: "0",
        manual_adjustment: "0",
        total_pnl: "3000000",
        avg_balance: "200000000",
        current_balance: "200000000",
        balance_yield_pct: null,
        annualized_yield_pct: null,
        ftp_rate_pct: "1.60",
        ftp_cost: "200000",
        ftp_net_pnl: "2800000",
        ftp_net_annualized_yield_pct: "5.11",
        source_kind: "zqtz",
        source_note: "父级",
        proportion: "0.6",
        assets_count: 3,
      },
      {
        row_key: "asset_zqtz_parent_b_detail_1",
        sort_order: 3,
        business_type: "其中：证券业资管",
        interest_income: "9000000",
        fair_value_change: "0",
        capital_gain: "0",
        manual_adjustment: "0",
        total_pnl: "9000000",
        avg_balance: "200000000",
        current_balance: "200000000",
        balance_yield_pct: null,
        annualized_yield_pct: null,
        ftp_rate_pct: "1.60",
        ftp_cost: null,
        ftp_net_pnl: null,
        ftp_net_annualized_yield_pct: null,
        source_kind: "zqtz",
        source_note: "其中项",
        proportion: "0.9",
        assets_count: 99,
      },
    ],
    ...partial,
  };
}

function monthlyBucket(partial: Partial<PnlByBusinessMonthlyBucket> = {}): PnlByBusinessMonthlyBucket {
  return {
    month_key: "2026-04",
    period_start_date: "2026-04-01",
    period_end_date: "2026-04-30",
    calendar_days: 30,
    summary: {
      interest_income: "0",
      fair_value_change: "0",
      capital_gain: "0",
      manual_adjustment: "0",
      total_pnl: "-2500000",
      avg_balance: "100000000",
      current_balance: "120000000",
      annualized_yield_pct: "-1.25",
      ftp_rate_pct: "1.60",
      ftp_cost: null,
      ftp_net_pnl: null,
      ftp_net_annualized_yield_pct: null,
      asset_count: 4,
    },
    items: [
      {
        row_key: "asset_zqtz_month_a",
        sort_order: 1,
        business_type: "月度债券",
        interest_income: "0",
        fair_value_change: "0",
        capital_gain: "0",
        manual_adjustment: "0",
        total_pnl: "-2500000",
        avg_balance: "100000000",
        current_balance: "120000000",
        annualized_yield_pct: "-1.25",
        ftp_rate_pct: "1.60",
        ftp_cost: null,
        ftp_net_pnl: null,
        ftp_net_annualized_yield_pct: null,
        proportion: "1",
        asset_count: 4,
      },
    ],
    ...partial,
  };
}

function formalPayload(partial: Partial<PnlByBusinessPayload> = {}): PnlByBusinessPayload {
  return {
    report_date: "2026-04-30",
    source_tables: ["formal_pnl"],
    summary: {
      business_count: 2,
      total_pnl: "7000000",
      total_scale_amount: "1000000000",
      traced_pnl_row_count: 8,
      untraced_pnl_row_count: 1,
    },
    rows: [
      {
        report_date: "2026-04-30",
        business_type_primary: "业务 A",
        business_type: "业务 A",
        currency_basis: "CNY",
        interest_income_514: "0",
        fair_value_change_516: "0",
        capital_gain_517: "0",
        manual_adjustment: "0",
        total_pnl: "1000000",
        scale_amount: "100000000",
        yield_pct: null,
        pnl_row_count: 1,
        balance_row_count: 1,
      },
      {
        report_date: "2026-04-30",
        business_type_primary: "业务 B",
        business_type: "业务 B",
        currency_basis: "CNY",
        interest_income_514: "0",
        fair_value_change_516: "0",
        capital_gain_517: "0",
        manual_adjustment: "0",
        total_pnl: "6000000",
        scale_amount: "200000000",
        yield_pct: null,
        pnl_row_count: 7,
        balance_row_count: 1,
      },
    ],
    ...partial,
  };
}

describe("pnlByBusinessPageModel", () => {
  it("builds the monthly manual-adjustment and FTP bridge from governed API fields", () => {
    const baseItem = monthlyBucket().items[0]!;
    const bridge = buildPnlByBusinessMonthlyAdjustmentBridge(
      monthlyBucket({
        month_key: "2026-06",
        items: [
          {
            ...baseItem,
            row_key: "asset_zqtz_interbank_cd",
            business_type: "同业存单",
            interest_income: "31055463.02",
            fair_value_change: "-10004409.07",
            capital_gain: "0.00",
            manual_adjustment: "37018504.54",
            total_pnl: "58069558.49",
            ftp_cost: "66499950.66",
            ftp_net_pnl: "-8430392.17",
          },
        ],
      }),
    );

    expect(bridge?.row.business_type).toBe("同业存单");
    expect(bridge?.adjustedParentRowCount).toBe(1);
    expect(bridge?.preAdjustmentPnl).toBeCloseTo(21_051_053.95, 2);
    expect(bridge?.row.manual_adjustment).toBe("37018504.54");
    expect(bridge?.row.ftp_cost).toBe("66499950.66");
    expect(bridge?.row.ftp_net_pnl).toBe("-8430392.17");
    expect(bridge?.pnlReconciliationDelta).toBeCloseTo(0, 2);
    expect(bridge?.ftpReconciliationDelta).toBeCloseTo(0, 2);
    expect(bridge?.pnlReconciled).toBe(true);
    expect(bridge?.ftpReconciled).toBe(true);
    expect(buildPnlByBusinessMonthlyAdjustmentBridge(monthlyBucket())).toBeUndefined();
  });

  it("resolves the displayed monthly bucket once so fallback evidence uses the same report date", () => {
    const may = monthlyBucket({ month_key: "2026-05", period_end_date: "2026-05-31" });
    const june = monthlyBucket({ month_key: "2026-06", period_end_date: "2026-06-30" });

    expect(resolvePnlByBusinessActiveMonthlyBucket([june, may], "2026-05-31", "2026-05-31")).toBe(may);
    expect(resolvePnlByBusinessActiveMonthlyBucket([may, june], "2026-07-31", "2026-07-31")).toBe(june);
    expect(resolvePnlByBusinessActiveMonthlyBucket([june, may], "2026-07-31", "2026-07-31")).toBe(june);
    expect(resolvePnlByBusinessActiveMonthlyBucket([june, may], "2026-07-31", "2026-05-31")).toBe(may);
    expect(resolvePnlByBusinessActiveMonthlyBucket([may, june], "2026-04-30", "2026-04-30")).toBeUndefined();
  });

  it("uses the approved monthly adjustment count instead of hard-coding zero", () => {
    const model = buildPnlByBusinessPageModel({
      viewMode: "monthly",
      selectedReportDate: "2026-06-30",
      selectedYear: 2026,
      selectedBusinessKey: null,
      datesState: { isLoading: false, isError: false },
      monthlyState: { isLoading: false, isError: false },
      ytdState: { isLoading: false, isError: false },
      formalState: { isLoading: false, isError: false },
      monthlyResult: {
        year: 2026,
        as_of_date: "2026-06-30",
        source_tables: ["monthly"],
        months: [monthlyBucket({ month_key: "2026-06" })],
      },
      monthlyMeta: meta({ as_of_date: "2026-06-30" }),
      manualAdjustmentCount: 1,
    });

    expect(model.insight.manualAdjustmentCount).toBe(1);
  });

  it("ranks selected business instrument drilldown without dropping null or zero numeric fields", () => {
    const row = (partial: Partial<PnlByBusinessAnalysisRow>): PnlByBusinessAnalysisRow => ({
      dimension_key: "fallback",
      dimension_label: "fallback",
      interest_income: "0",
      fair_value_change: "0",
      capital_gain: "0",
      manual_adjustment: "0",
      total_pnl: "0",
      avg_balance: "0",
      current_balance: "0",
      annualized_yield_pct: null,
      ftp_rate_pct: "1.600000",
      ftp_cost: null,
      ftp_net_pnl: null,
      ftp_net_annualized_yield_pct: null,
      asset_count: 1,
      ...partial,
    });

    const model = buildPnlByBusinessSelectedDrilldownModel([
      row({
        dimension_key: "bond_positive",
        dimension_label: "240001.IB 贡献券",
        total_pnl: "200000",
        ftp_net_pnl: "10000",
      }),
      row({
        dimension_key: "bond_zero",
        dimension_label: "240002.IB 零损益券",
        total_pnl: "0",
        ftp_net_pnl: null,
      }),
      row({
        dimension_key: "bond_drag",
        dimension_label: "240003.IB 拖累券",
        total_pnl: "-300000",
        ftp_net_pnl: "-80000",
      }),
      row({
        dimension_key: "bond_small_drag",
        dimension_label: "240004.IB 小拖累券",
        total_pnl: "-100000",
        ftp_net_pnl: "-20000",
      }),
    ]);

    expect(model.topContributionRows.map((item) => item.dimension_label)).toEqual([
      "240001.IB 贡献券",
      "240002.IB 零损益券",
      "240004.IB 小拖累券",
    ]);
    expect(model.topDragRows.map((item) => item.dimension_label)).toEqual([
      "240003.IB 拖累券",
      "240004.IB 小拖累券",
    ]);
    expect(model.negativeFtpRows.map((item) => item.dimension_label)).toEqual([
      "240003.IB 拖累券",
      "240004.IB 小拖累券",
    ]);
  });

  it("keeps zero average balance present and filters ZQTZ parent rows without changing totals", () => {
    expect(formatAvgBalanceYi(0)).toBe("0.00");
    expect(formatAvgBalanceYi("abc")).toBe("日均缺失");

    const payload = ytdPayload();
    expect(payload.items.map(isParentZqtzBusinessRow)).toEqual([true, true, false]);

    const selection = buildPnlByBusinessSelectionModel({
      ytdResult: payload,
      selectedBusinessKey: null,
    });

    expect(selection.ytdRows).toHaveLength(3);
    expect(selection.parentYtdRows.map((row) => row.row_key)).toEqual([
      "asset_zqtz_parent_a",
      "asset_zqtz_parent_b",
    ]);
    expect(selection.defaultBusinessRow?.row_key).toBe("asset_zqtz_parent_b");
    expect(selection.selectedBusinessRow?.row_key).toBe("asset_zqtz_parent_b");
  });

  it("builds status strip and YTD KPI view model from existing payload fields", () => {
    const model = buildPnlByBusinessPageModel({
      viewMode: "ytd",
      selectedReportDate: "2026-04-30",
      selectedYear: 2026,
      selectedBusinessKey: null,
      datesState: { isLoading: false, isError: false },
      monthlyState: { isLoading: false, isError: false },
      ytdState: { isLoading: false, isError: false },
      formalState: { isLoading: false, isError: false },
      ytdResult: ytdPayload(),
      ytdMeta: meta({
        quality_flag: "warning",
        vendor_status: "vendor_stale",
        fallback_mode: "latest_snapshot",
      }),
    });

    expect(model.loading).toBe(false);
    expect(model.error).toBe(false);
    expect(model.empty).toBe(false);
    expect(model.activeDataStatus).toBe("预警");
    expect(model.statusStrip).toMatchObject({
      viewModeLabel: "年累计 YTD",
      asOfDate: "2026-04-30",
      fallbackMode: "最新快照降级",
      vendorStatus: "供应商陈旧",
      evidenceRows: "12 行",
      traceId: "tr_pnl_business_model",
    });
    expect(model.ytdAssetCount).toBe(5);
    expect(model.summaryCards.map((card) => [card.label, card.value, card.detail, card.tone])).toEqual([
      ["年累计损益", "500 万元", "2026 年累计", "positive"],
      ["业务种类", "2", "5 个父级归类命中", undefined],
      ["最大损益业务", "非底层投资资产", "300 万元", "positive"],
      ["最大占比", "60.00%", "非底层投资资产", undefined],
    ]);
    expect(model.hero.businessQuestion).toBe(VIEW_MODE_BUSINESS_QUESTIONS.ytd);
    expect(model.hero.conclusionTitle).toContain("500 万元");
    expect(model.hero.requestedReportDate).toBe("2026-04-30");
    expect(model.hero.asOfDate).toBe("2026-04-30");
    expect(model.hero.reportDateNote).toContain("fallback 快照");
    expect(model.stateSurfaces.map((surface) => surface.key)).toEqual(
      expect.arrayContaining(["warning", "fallback-date", "vendor-stale"]),
    );
  });

  it("builds hero date alignment note and quality error/missing state surfaces", () => {
    const alignedModel = buildPnlByBusinessPageModel({
      viewMode: "monthly",
      selectedReportDate: "2026-04-30",
      selectedYear: 2026,
      selectedBusinessKey: null,
      datesState: { isLoading: false, isError: false },
      monthlyState: { isLoading: false, isError: false },
      ytdState: { isLoading: false, isError: false },
      formalState: { isLoading: false, isError: false },
      monthlyResult: {
        year: 2026,
        as_of_date: "2026-04-30",
        source_tables: ["monthly"],
        months: [monthlyBucket()],
      },
      monthlyMeta: meta({ quality_flag: "ok", as_of_date: "2026-04-30", fallback_mode: "none" }),
    });

    expect(alignedModel.hero.reportDateNote).toContain("与请求日一致");

    const errorModel = buildPnlByBusinessPageModel({
      viewMode: "formal",
      selectedReportDate: "2026-04-30",
      selectedYear: 2026,
      selectedBusinessKey: null,
      datesState: { isLoading: false, isError: false },
      monthlyState: { isLoading: false, isError: false },
      ytdState: { isLoading: false, isError: false },
      formalState: { isLoading: false, isError: false },
      formalResult: formalPayload(),
      formalMeta: meta({ quality_flag: "error" }),
    });

    expect(errorModel.stateSurfaces.map((surface) => surface.key)).toEqual(
      expect.arrayContaining(["quality-error"]),
    );

    const missingModel = buildPnlByBusinessPageModel({
      viewMode: "formal",
      selectedReportDate: "2026-04-30",
      selectedYear: 2026,
      selectedBusinessKey: null,
      datesState: { isLoading: false, isError: false },
      monthlyState: { isLoading: false, isError: false },
      ytdState: { isLoading: false, isError: false },
      formalState: { isLoading: false, isError: false },
      formalResult: formalPayload(),
      formalMeta: meta({ quality_flag: "missing" }),
    });

    expect(missingModel.stateSurfaces.map((surface) => surface.key)).toEqual(
      expect.arrayContaining(["quality-missing"]),
    );
  });

  it("does not infer as_of and surfaces YTD coverage and unallocated reconciliation warnings", () => {
    const model = buildPnlByBusinessPageModel({
      viewMode: "ytd",
      selectedReportDate: "2026-06-30",
      selectedYear: 2026,
      selectedBusinessKey: null,
      datesState: { isLoading: false, isError: false },
      monthlyState: { isLoading: false, isError: false },
      ytdState: { isLoading: false, isError: false },
      formalState: { isLoading: false, isError: false },
      ytdResult: ytdPayload({
        period_end_date: "2026-05-31",
        coverage_days: 152,
        expected_days: 181,
        sample_filled: true,
        sample_fill_method: "observed_days_scaled_to_calendar",
        classified_parent_total_pnl: "4198915256.99",
        unallocated_pnl: "64295.80",
        unallocated_row_count: 400,
        reconciliation_delta: "0",
      }),
      ytdMeta: meta({
        basis: "analytical",
        formal_use_allowed: false,
        as_of_date: null,
        requested_report_date: "2026-06-30",
        resolved_report_date: null,
      }),
    });

    expect(model.hero.asOfDate).toBe("待返回");
    expect(model.statusStrip.asOfDate).toBe("待返回");
    expect(model.stateSurfaces.map((surface) => surface.key)).toContain("definition-pending");
    const coverage = model.stateSurfaces.find((surface) => surface.key === "coverage-partial");
    expect(coverage?.description).toContain("152/181");
    expect(coverage?.description).toContain("observed_days_scaled_to_calendar");
    const unallocated = model.stateSurfaces.find((surface) => surface.key === "unallocated");
    expect(unallocated?.description).toContain("400");
    expect(unallocated?.description).toContain("6.43 万元");
  });

  it("builds monthly and formal KPI models and preserves loading/error/empty states", () => {
    const monthlyModel = buildPnlByBusinessPageModel({
      viewMode: "monthly",
      selectedReportDate: "2026-04-30",
      selectedYear: 2026,
      selectedBusinessKey: null,
      datesState: { isLoading: false, isError: false },
      monthlyState: { isLoading: false, isError: false },
      ytdState: { isLoading: false, isError: false },
      formalState: { isLoading: false, isError: false },
      monthlyResult: {
        year: 2026,
        as_of_date: "2026-04-30",
        source_tables: ["monthly"],
        months: [monthlyBucket()],
      },
      monthlyMeta: meta({ quality_flag: "ok" }),
    });

    expect(monthlyModel.activeDataStatus).toBe("正常");
    expect(monthlyModel.topMonthlyRow?.business_type).toBe("月度债券");
    expect(monthlyModel.summaryCards.map((card) => [card.label, card.value, card.tone])).toEqual([
      ["月报合计损益", "-250 万元", "negative"],
      ["业务种类", "1", undefined],
      ["最大损益业务", "月度债券", "negative"],
      ["月报收益率", "-1.25%", "negative"],
    ]);

    const formalModel = buildPnlByBusinessPageModel({
      viewMode: "formal",
      selectedReportDate: "2026-04-30",
      selectedYear: 2026,
      selectedBusinessKey: null,
      datesState: { isLoading: false, isError: false },
      monthlyState: { isLoading: false, isError: false },
      ytdState: { isLoading: false, isError: false },
      formalState: { isLoading: false, isError: false },
      formalResult: formalPayload(),
      formalMeta: meta({ quality_flag: "stale" }),
    });

    expect(formalModel.activeDataStatus).toBe("陈旧");
    expect(formalModel.topFormalRow?.business_type_primary).toBe("业务 B");
    expect(formalModel.summaryCards.map((card) => [card.label, card.value, card.detail])).toEqual([
      ["报表日合计损益", "700 万元", "2026-04-30 · formal"],
      ["业务种类行数", "2", "已追溯损益行 8"],
      ["最大损益（行）", "业务 B", "600 万元"],
      ["未追溯 PnL 行", "1", "与余额 join 未命中时计数"],
    ]);

    const loadingModel = buildPnlByBusinessPageModel({
      viewMode: "monthly",
      selectedReportDate: "2026-04-30",
      selectedYear: 2026,
      selectedBusinessKey: null,
      datesState: { isLoading: false, isError: false },
      monthlyState: { isLoading: true, isError: false },
      ytdState: { isLoading: false, isError: false },
      formalState: { isLoading: false, isError: false },
    });
    expect(loadingModel.loading).toBe(true);
    expect(loadingModel.activeDataStatus).toBe("读取中");

    const emptyModel = buildPnlByBusinessPageModel({
      viewMode: "formal",
      selectedReportDate: "2026-04-30",
      selectedYear: 2026,
      selectedBusinessKey: null,
      datesState: { isLoading: false, isError: false },
      monthlyState: { isLoading: false, isError: false },
      ytdState: { isLoading: false, isError: false },
      formalState: { isLoading: false, isError: false },
    });
    expect(emptyModel.empty).toBe(true);
    expect(emptyModel.activeDataStatus).toBe("无数据");
    expect(emptyModel.stateSurfaces).toEqual([]);
  });

  it("keeps monthly top contribution separate from the largest drag row", () => {
    const model = buildPnlByBusinessPageModel({
      viewMode: "monthly",
      selectedReportDate: "2026-04-30",
      selectedYear: 2026,
      selectedBusinessKey: null,
      datesState: { isLoading: false, isError: false },
      monthlyState: { isLoading: false, isError: false },
      ytdState: { isLoading: false, isError: false },
      formalState: { isLoading: false, isError: false },
      monthlyResult: {
        year: 2026,
        as_of_date: "2026-04-30",
        source_tables: ["monthly"],
        months: [
          monthlyBucket({
            summary: {
              ...monthlyBucket().summary,
              total_pnl: "7000000",
              ftp_net_pnl: "5000000",
            },
            items: [
              {
                ...monthlyBucket().items[0]!,
                row_key: "asset_zqtz_month_gain",
                business_type: "monthly_gain",
                total_pnl: "7000000",
                proportion: "0.7",
              },
              {
                ...monthlyBucket().items[0]!,
                row_key: "asset_zqtz_month_drag",
                business_type: "monthly_drag",
                total_pnl: "-1000000",
                proportion: "-0.1",
              },
            ],
          }),
        ],
      },
      monthlyMeta: meta({ quality_flag: "ok" }),
    });

    expect(model.insight).toMatchObject({
      confidenceLabel: "可分析",
      topContributionLabel: "monthly_gain",
      topContributionDisplay: "700 万元",
      topDragLabel: "monthly_drag",
      topDragDisplay: "-100 万元",
      ftpAvailable: true,
    });
  });

  it("surfaces mock mode and monthly hero conclusion without changing KPI values", () => {
    const monthlyModel = buildPnlByBusinessPageModel({
      viewMode: "monthly",
      selectedReportDate: "2026-04-30",
      selectedYear: 2026,
      selectedBusinessKey: null,
      clientMode: "mock",
      datesState: { isLoading: false, isError: false },
      monthlyState: { isLoading: false, isError: false },
      ytdState: { isLoading: false, isError: false },
      formalState: { isLoading: false, isError: false },
      monthlyResult: {
        year: 2026,
        as_of_date: "2026-04-30",
        source_tables: ["monthly"],
        months: [monthlyBucket()],
      },
      monthlyMeta: meta({ quality_flag: "ok" }),
    });

    expect(monthlyModel.hero.businessQuestion).toBe(VIEW_MODE_BUSINESS_QUESTIONS.monthly);
    expect(monthlyModel.hero.conclusionTitle).toContain("-250 万元");
    expect(monthlyModel.stateSurfaces[0]).toMatchObject({
      key: "mock-mode",
      variant: "mock",
    });
    expect(monthlyModel.summaryCards[0]?.value).toBe("-250 万元");
  });

  it("builds analysis insight from parent YTD rows and marks missing ADB", () => {
    const payload = ytdPayload({
      items: [
        ...ytdPayload().items,
        {
          row_key: "asset_zqtz_parent_loss",
          sort_order: 4,
          business_type: "拖累业务",
          interest_income: "-500000",
          fair_value_change: "0",
          capital_gain: "0",
          manual_adjustment: "0",
          total_pnl: "-500000",
          avg_balance: "10000000",
          current_balance: "10000000",
          balance_yield_pct: null,
          annualized_yield_pct: null,
          ftp_rate_pct: "1.60",
          ftp_cost: null,
          ftp_net_pnl: null,
          ftp_net_annualized_yield_pct: null,
          source_kind: "zqtz",
          source_note: "父级",
          proportion: "-0.1",
          assets_count: 1,
        },
      ],
    });

    const model = buildPnlByBusinessPageModel({
      viewMode: "ytd",
      selectedReportDate: "2026-04-30",
      selectedYear: 2026,
      selectedBusinessKey: null,
      manualAdjustmentCount: 2,
      adbAvgByBusinessType: new Map([["债券投资", 100_000_000]]),
      datesState: { isLoading: false, isError: false },
      monthlyState: { isLoading: false, isError: false },
      ytdState: { isLoading: false, isError: false },
      formalState: { isLoading: false, isError: false },
      ytdResult: payload,
      ytdMeta: meta({ quality_flag: "ok" }),
    });

    expect(model.insight).toMatchObject({
      confidenceLabel: "缺日均",
      topContributionLabel: "非底层投资资产",
      topDragLabel: "拖累业务",
      topShareLabel: "非底层投资资产",
      manualAdjustmentCount: 2,
      missingAdbCount: 2,
      ftpAvailable: false,
      formalUntracedCount: 0,
      formalUntracedValueDisplay: "未读取",
      formalUntracedDisplay: "切到 primary 对账查看；不与月报/YTD 混加",
    });
    expect(model.insight.totalPnlDisplay).toBe("500 万元");
    expect(model.insight.recommendedDrilldown).toMatchObject({
      targetBusinessLabel: "非底层投资资产",
      priorityLabel: "补日均",
      dimensionLabel: "日均映射",
      actionLabel: "先补齐 ADB 再判断 FTP 后收益",
      evidenceLabel: "缺日均 2 项",
    });
  });

  it("does not mark YTD ADB missing when parent rows resolve from rollup children", () => {
    const model = buildPnlByBusinessPageModel({
      viewMode: "ytd",
      selectedReportDate: "2026-04-30",
      selectedYear: 2026,
      selectedBusinessKey: null,
      adbAvgByBusinessType: new Map([
        ["债券投资", 100_000_000],
        ["信托计划", 25_000_000],
        ["证券业资管计划", 75_000_000],
      ]),
      datesState: { isLoading: false, isError: false },
      monthlyState: { isLoading: false, isError: false },
      ytdState: { isLoading: false, isError: false },
      formalState: { isLoading: false, isError: false },
      ytdResult: ytdPayload(),
      ytdMeta: meta({ quality_flag: "ok" }),
    });

    expect(model.insight).toMatchObject({
      confidenceLabel: "可分析",
      missingAdbCount: 0,
      ftpAvailable: true,
      formalUntracedValueDisplay: "未读取",
      formalUntracedDisplay: "切到 primary 对账查看；不与月报/YTD 混加",
    });
    expect(model.insight.recommendedDrilldown).toMatchObject({
      targetBusinessLabel: "非底层投资资产",
      priorityLabel: "FTP 后仍有效",
      dimensionLabel: "证券级下钻",
      actionLabel: "看 Top 贡献券、Top 拖累券、FTP 后为负",
      evidenceLabel: "ADB 已覆盖",
    });
  });

  it("uses YTD daily averages without reporting missing ADB when supplemental comparison is unavailable", () => {
    const model = buildPnlByBusinessPageModel({
      viewMode: "ytd",
      selectedReportDate: "2026-04-30",
      selectedYear: 2026,
      selectedBusinessKey: null,
      adbAvgByBusinessType: new Map([
        ["债券投资", 100_000_000],
        ["非底层投资资产", 200_000_000],
      ]),
      adbEvidenceStatus: "ytd_fallback",
      datesState: { isLoading: false, isError: false },
      monthlyState: { isLoading: false, isError: false },
      ytdState: { isLoading: false, isError: false },
      formalState: { isLoading: false, isError: false },
      ytdResult: ytdPayload(),
      ytdMeta: meta({ quality_flag: "ok" }),
    });

    expect(model.insight).toMatchObject({
      confidenceLabel: "预警/降级",
      missingAdbCount: 0,
      zeroAdbCount: 0,
      missingFtpFieldCount: 0,
      ftpAvailable: true,
      adbEvidenceStatus: "ytd_fallback",
    });
    expect(model.insight.nextStep).toContain("ADB 补充复核不可用");
    expect(model.insight.recommendedDrilldown).toMatchObject({
      priorityLabel: "预警/降级",
      dimensionLabel: "ADB 补充复核",
      evidenceLabel: "YTD 日均回退",
    });
  });

  it("does not mark FTP as analyzable when an active YTD row lacks FTP fields", () => {
    const basePayload = ytdPayload();
    const model = buildPnlByBusinessPageModel({
      viewMode: "ytd",
      selectedReportDate: "2026-04-30",
      selectedYear: 2026,
      selectedBusinessKey: null,
      adbAvgByBusinessType: new Map([
        ["债券投资", 100_000_000],
        ["非底层投资资产", 200_000_000],
      ]),
      datesState: { isLoading: false, isError: false },
      monthlyState: { isLoading: false, isError: false },
      ytdState: { isLoading: false, isError: false },
      formalState: { isLoading: false, isError: false },
      ytdResult: ytdPayload({
        items: basePayload.items.map((row) =>
          row.row_key === "asset_zqtz_parent_a" ? { ...row, ftp_cost: null, ftp_net_pnl: null } : row,
        ),
      }),
      ytdMeta: meta({ quality_flag: "ok" }),
    });

    expect(model.insight).toMatchObject({
      confidenceLabel: "预警/降级",
      missingAdbCount: 0,
      zeroAdbCount: 0,
      missingFtpFieldCount: 1,
      ftpAvailable: false,
    });
    expect(model.insight.recommendedDrilldown).toMatchObject({
      priorityLabel: "FTP 字段待核对",
      evidenceLabel: "FTP 字段缺失 1 项",
    });
  });

  it("marks a YTD zero denominator as pending confirmation when ADB comparison is unavailable", () => {
    const model = buildPnlByBusinessPageModel({
      viewMode: "ytd",
      selectedReportDate: "2026-04-30",
      selectedYear: 2026,
      selectedBusinessKey: null,
      adbAvgByBusinessType: new Map([
        ["债券投资", 100_000_000],
        ["非底层投资资产", 0],
      ]),
      adbEvidenceStatus: "ytd_fallback",
      datesState: { isLoading: false, isError: false },
      monthlyState: { isLoading: false, isError: false },
      ytdState: { isLoading: false, isError: false },
      formalState: { isLoading: false, isError: false },
      ytdResult: ytdPayload(),
      ytdMeta: meta({ quality_flag: "ok" }),
    });

    expect(model.insight).toMatchObject({
      confidenceLabel: "日均为0",
      missingAdbCount: 0,
      zeroAdbCount: 1,
      ftpAvailable: false,
      adbEvidenceStatus: "ytd_fallback",
    });
    expect(model.insight.recommendedDrilldown).toMatchObject({
      evidenceLabel: "YTD 日均为0 1 项（待复核）",
    });
  });

  it("counts true-zero ADB as covered but zero-denominator limited", () => {
    const model = buildPnlByBusinessPageModel({
      viewMode: "ytd",
      selectedReportDate: "2026-04-30",
      selectedYear: 2026,
      selectedBusinessKey: null,
      adbAvgByBusinessType: new Map([
        ["债券投资", 100_000_000],
        ["信托计划", 0],
        ["证券业资管计划", 0],
      ]),
      datesState: { isLoading: false, isError: false },
      monthlyState: { isLoading: false, isError: false },
      ytdState: { isLoading: false, isError: false },
      formalState: { isLoading: false, isError: false },
      ytdResult: ytdPayload(),
      ytdMeta: meta({ quality_flag: "ok" }),
    });

    expect(model.insight).toMatchObject({
      confidenceLabel: "日均为0",
      missingAdbCount: 0,
      zeroAdbCount: 1,
      ftpAvailable: false,
    });
    expect(model.insight.recommendedDrilldown).toMatchObject({
      priorityLabel: "日均为0",
      dimensionLabel: "日均分母",
      evidenceLabel: "日均为0 1 项",
    });
  });

  it("does not block YTD FTP analysis on zero-activity parent rows without ADB", () => {
    const model = buildPnlByBusinessPageModel({
      viewMode: "ytd",
      selectedReportDate: "2026-04-30",
      selectedYear: 2026,
      selectedBusinessKey: null,
      adbAvgByBusinessType: new Map([
        ["债券投资", 100_000_000],
        ["信托计划", 25_000_000],
        ["证券业资管计划", 75_000_000],
      ]),
      datesState: { isLoading: false, isError: false },
      monthlyState: { isLoading: false, isError: false },
      ytdState: { isLoading: false, isError: false },
      formalState: { isLoading: false, isError: false },
      ytdResult: ytdPayload({
        items: [
          ...ytdPayload().items,
          {
            row_key: "asset_zqtz_parent_zero",
            sort_order: 4,
            business_type: "央行票据",
            interest_income: "0",
            fair_value_change: "0",
            capital_gain: "0",
            manual_adjustment: "0",
            total_pnl: "0",
            avg_balance: "0",
            current_balance: "0",
            balance_yield_pct: null,
            annualized_yield_pct: null,
            ftp_rate_pct: "1.60",
            ftp_cost: null,
            ftp_net_pnl: null,
            ftp_net_annualized_yield_pct: null,
            source_kind: "zqtz",
            source_note: "父级",
            proportion: "0",
            assets_count: 0,
          },
        ],
      }),
      ytdMeta: meta({ quality_flag: "ok" }),
    });

    expect(model.insight).toMatchObject({
      confidenceLabel: "可分析",
      missingAdbCount: 0,
      ftpAvailable: true,
      formalUntracedValueDisplay: "未读取",
      formalUntracedDisplay: "切到 primary 对账查看；不与月报/YTD 混加",
    });
    expect(model.insight.recommendedDrilldown.evidenceLabel).toBe("ADB 已覆盖");
  });

  it("surfaces formal reconciliation insight without promoting it to YTD analysis", () => {
    const model = buildPnlByBusinessPageModel({
      viewMode: "formal",
      selectedReportDate: "2026-04-30",
      selectedYear: 2026,
      selectedBusinessKey: null,
      datesState: { isLoading: false, isError: false },
      monthlyState: { isLoading: false, isError: false },
      ytdState: { isLoading: false, isError: false },
      formalState: { isLoading: false, isError: false },
      formalResult: formalPayload({
        summary: {
          ...formalPayload().summary,
          business_count: 4,
          untraced_pnl_row_count: 5,
        },
        rows: [
          ...formalPayload().rows,
          {
            report_date: "2026-04-30",
            business_type_primary: "T",
            business_type: "T",
            currency_basis: "CNY",
            interest_income_514: "1",
            fair_value_change_516: "0",
            capital_gain_517: "0",
            manual_adjustment: "0",
            total_pnl: "1",
            scale_amount: "0",
            yield_pct: null,
            pnl_row_count: 3,
            balance_row_count: 0,
          },
          {
            report_date: "2026-04-30",
            business_type_primary: "A",
            business_type: "A",
            currency_basis: "CNY",
            interest_income_514: "1",
            fair_value_change_516: "0",
            capital_gain_517: "0",
            manual_adjustment: "0",
            total_pnl: "1",
            scale_amount: "0",
            yield_pct: null,
            pnl_row_count: 2,
            balance_row_count: 0,
          },
        ],
      }),
      formalMeta: meta({ quality_flag: "warning" }),
    });

    expect(model.insight).toMatchObject({
      confidenceLabel: "预警/降级",
      topContributionLabel: "业务 B",
      topDragLabel: "无拖累",
      topShareLabel: "仅对账",
      ftpAvailable: false,
      missingAdbCount: 0,
      formalUntracedCount: 5,
      formalUntracedValueDisplay: "5 条未追溯",
      formalUntracedDisplay: "T 3 条 / A 2 条",
    });
    expect(model.insight.nextStep).toContain("对账证据");
    expect(model.insight.nextStep).toContain("T 3 条 / A 2 条");
    expect(model.insight.formalTriageDisplay).toContain("无余额/无持仓排查");
    expect(model.insight.formalTriageDisplay).toContain("cost_center 已授权放宽");
  });

  it("uses formal untraced balance evidence breakdown when returned", () => {
    const model = buildPnlByBusinessPageModel({
      viewMode: "formal",
      selectedReportDate: "2026-04-30",
      selectedYear: 2026,
      monthlyResult: undefined,
      ytdResult: undefined,
      selectedBusinessKey: null,
      formalState: { isLoading: false, isError: false },
      datesState: { isLoading: false, isError: false },
      monthlyState: { isLoading: false, isError: false },
      ytdState: { isLoading: false, isError: false },
      formalResult: formalPayload({
        summary: {
          ...formalPayload().summary,
          untraced_pnl_row_count: 4,
          untraced_breakdown: [
            {
              reason_code: "position_absent_before_maturity",
              invest_type_std: "A",
              pnl_row_count: 2,
              total_pnl: "3000000",
              abs_pnl: "3000000",
              interest_income_514: "3000000",
              fair_value_change_516: "0",
              capital_gain_517: "0",
              manual_adjustment: "0",
            },
            {
              reason_code: "matured_before_or_on_report_date",
              invest_type_std: "T",
              pnl_row_count: 1,
              total_pnl: "-500000",
              abs_pnl: "500000",
              interest_income_514: "0",
              fair_value_change_516: "-500000",
              capital_gain_517: "0",
              manual_adjustment: "0",
            },
            {
              reason_code: "never_seen_in_zqtz_asset_balance",
              invest_type_std: "H",
              pnl_row_count: 1,
              total_pnl: "10000",
              abs_pnl: "10000",
              interest_income_514: "10000",
              fair_value_change_516: "0",
              capital_gain_517: "0",
              manual_adjustment: "0",
            },
            {
              reason_code: "same_day_balance_multiple_primary_types",
              invest_type_std: "A",
              pnl_row_count: 1,
              total_pnl: "1000000",
              abs_pnl: "1000000",
              interest_income_514: "1000000",
              fair_value_change_516: "0",
              capital_gain_517: "0",
              manual_adjustment: "0",
            },
          ],
        },
      }),
      formalMeta: meta({ quality_flag: "warning" }),
      monthlyMeta: meta(),
      ytdMeta: meta(),
    });

    expect(model.insight.formalTriageDisplay).toContain("未到期但报表日无持仓 · A 2 条");
    expect(model.insight.formalTriageDisplay).toContain("到期后无持仓 · T 1 条");
    expect(model.insight.formalTriageDisplay).toContain("同日余额多业务分类 · A 1 条");
    expect(model.insight.formalTriageDisplay).toContain("不作为业务贡献结论");
  });
});
