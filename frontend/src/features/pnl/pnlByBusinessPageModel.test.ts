import { describe, expect, it } from "vitest";

import type {
  PnlByBusinessMonthlyBucket,
  PnlByBusinessPayload,
  PnlByBusinessYtdPayload,
  ResultMeta,
} from "../../api/contracts";
import {
  buildPnlByBusinessPageModel,
  buildPnlByBusinessSelectionModel,
  formatAvgBalanceYi,
  isParentZqtzBusinessRow,
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
        current_balance: "100000000",
        balance_yield_pct: null,
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
        current_balance: "200000000",
        balance_yield_pct: null,
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
        current_balance: "200000000",
        balance_yield_pct: null,
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

function formalPayload(): PnlByBusinessPayload {
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
  };
}

describe("pnlByBusinessPageModel", () => {
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
      ["月报累计损益", "500 万元", "2026 年累计", "positive"],
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
});
