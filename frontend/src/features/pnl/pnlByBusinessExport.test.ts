import { describe, expect, it } from "vitest";
import writeExcelFile from "write-excel-file/browser";

import type {
  PnlByBusinessAnalysisRow,
  PnlByBusinessManualAdjustmentPayload,
  PnlByBusinessMonthlyBucket,
  PnlByBusinessRow,
  PnlByBusinessYtdItem,
  PnlByBusinessYtdSummary,
} from "../../api/contracts";
import type { PnlByBusinessSummary } from "../../api/pnlByBusinessContracts";

import { buildPnlByBusinessSheets } from "./pnlByBusinessExport";
import { buildNegativeFtpList } from "./pnlByBusinessPageModel";

const minimalYtdRow = (patch: Partial<PnlByBusinessYtdItem> = {}): PnlByBusinessYtdItem => ({
  row_key: "rk_test",
  sort_order: 1,
  business_type: "政策性金融债",
  interest_income: "100000",
  fair_value_change: "0",
  capital_gain: "0",
  manual_adjustment: "0",
  total_pnl: "100000",
  avg_balance: "1000000000",
  current_balance: "1000000000",
  annualized_yield_pct: "9.876543",
  ftp_rate_pct: "1.600000",
  ftp_cost: "12345.67",
  ftp_net_pnl: "76543.21",
  ftp_net_annualized_yield_pct: "8.765432",
  balance_yield_pct: null,
  proportion: "0.1",
  assets_count: 3,
  ...patch,
});

const minimalYtdSummary = (
  patch: Partial<PnlByBusinessYtdSummary> = {},
): PnlByBusinessYtdSummary => ({
  interest_income: "910000",
  fair_value_change: "820000",
  capital_gain: "730000",
  manual_adjustment: "640000",
  total_pnl: "550000",
  avg_balance: "4600000000",
  current_balance: "3700000000",
  annualized_yield_pct: "12.34",
  ftp_rate_pct: "1.6",
  ftp_cost: "280000",
  ftp_net_pnl: "190000",
  ftp_net_annualized_yield_pct: "4.56",
  proportion: "1",
  assets_count: 91,
  ...patch,
});

const minimalFormalRow = (patch: Partial<PnlByBusinessRow> = {}): PnlByBusinessRow => ({
  report_date: "2025-12-31",
  business_type_primary: "政策性金融债",
  business_type: "政策性金融债",
  currency_basis: "CNY",
  interest_income_514: "50000",
  fair_value_change_516: "0",
  capital_gain_517: "0",
  manual_adjustment: "0",
  total_pnl: "50000",
  scale_amount: "1000000000",
  yield_pct: "5",
  pnl_row_count: 10,
  balance_row_count: 5,
  ...patch,
});

const minimalFormalSummary = (patch: Partial<PnlByBusinessSummary> = {}): PnlByBusinessSummary => ({
  business_count: 1,
  total_pnl: "50000",
  total_scale_amount: "1000000000",
  interest_income_514: "50000",
  fair_value_change_516: "0",
  capital_gain_517: "0",
  manual_adjustment: "0",
  pnl_row_count: 10,
  traced_pnl_row_count: 10,
  untraced_pnl_row_count: 0,
  ...patch,
});

const minimalAdjustment = (
  patch: Partial<PnlByBusinessManualAdjustmentPayload> = {},
): PnlByBusinessManualAdjustmentPayload => ({
  adjustment_id: "adj_test",
  event_type: "edited",
  created_at: "2026-04-12T08:30:00Z",
  stream: "pnl_by_business_adjustments",
  report_date: "2025-12-31",
  row_key: "rk_test",
  business_type: "政策性金融债",
  operator: "DELTA",
  approval_status: "approved",
  manual_adjustment: "2500",
  reason: "复核后补录",
  created_by: "reviewer_test",
  approved_by: "approver_test",
  ...patch,
});

const minimalMonthlyBucket = (): PnlByBusinessMonthlyBucket => ({
  month_key: "2025-12",
  period_start_date: "2025-12-01",
  period_end_date: "2025-12-31",
  calendar_days: 31,
  coverage_days: 1,
  expected_days: 31,
  sample_filled: true,
  sample_fill_method: "observed_days_scaled_to_calendar",
  source_total_pnl: "150000",
  classified_parent_total_pnl: "100000",
  unallocated_pnl: "50000",
  unallocated_abs_pnl: "90000",
  unallocated_row_count: 2,
  reconciliation_delta: "0",
  unallocated_breakdown: [minimalUnallocatedBreakdownRow],
  unallocated_items: minimalUnallocatedItems,
  unallocated_evidence_complete: true,
  summary: {
    interest_income: "100000",
    fair_value_change: "0",
    capital_gain: "0",
    manual_adjustment: "0",
    total_pnl: "100000",
    avg_balance: "1000000000",
    current_balance: "1000000000",
    annualized_yield_pct: "1.2",
    ftp_rate_pct: "1.6",
    ftp_cost: "1000",
    ftp_net_pnl: "99000",
    ftp_net_annualized_yield_pct: "1.1",
    asset_count: 3,
  },
  items: [
    {
      ...minimalYtdRow(),
      avg_balance: "1000000000",
      annualized_yield_pct: "1.2",
      ftp_rate_pct: "1.6",
      ftp_cost: "1000",
      ftp_net_pnl: "99000",
      ftp_net_annualized_yield_pct: "1.1",
      asset_count: 3,
      source_note: "ZQTZ_ASSET_BOND_ROWS",
    },
    {
      ...minimalYtdRow({
        row_key: "asset_zqtz_detail_local_currency_special_account_cost",
        business_type: "其中：本币专户（成本法）",
        total_pnl: "50000",
      }),
      avg_balance: "500000000",
      current_balance: "500000000",
      annualized_yield_pct: "1.1",
      ftp_rate_pct: "1.6",
      ftp_cost: "1000",
      ftp_net_pnl: "49000",
      ftp_net_annualized_yield_pct: "0.9",
      asset_count: 1,
      source_note: "ZQTZSHOW 其中项：J0 剔除市值法清单后的成本法专户",
    },
  ],
});

const minimalAnalysisRow = (patch: Partial<PnlByBusinessAnalysisRow> = {}): PnlByBusinessAnalysisRow => ({
  dimension_key: "rate_bond",
  dimension_label: "利率债",
  interest_income: "100000",
  fair_value_change: "0",
  capital_gain: "0",
  manual_adjustment: "0",
  total_pnl: "100000",
  avg_balance: "1000000000",
  current_balance: "1000000000",
  annualized_yield_pct: "1.2",
  ftp_rate_pct: "1.6",
  ftp_cost: "1000",
  ftp_net_pnl: "99000",
  ftp_net_annualized_yield_pct: "1.1",
  asset_count: 3,
  ...patch,
});

const minimalUnallocatedBreakdownRow = {
  reason_code: "no_business_rule_match" as const,
  source_kind: "formal_fi",
  invest_type_std: "A",
  accounting_basis: "FVOCI",
  portfolio_name: "Unmapped Desk",
  cost_center: "CC-UNMAPPED",
  pnl_row_count: 2,
  total_pnl: "50000",
  abs_pnl: "90000",
  sample_instrument_codes: ["UNALLOCATED-A", "UNALLOCATED-A-NEG"],
};

const minimalUnallocatedItems = [
  {
    report_date: "2025-12-31",
    reason_code: "no_business_rule_match" as const,
    source_kind: "formal_fi",
    instrument_code: "UNALLOCATED-A",
    portfolio_name: "Unmapped Desk",
    cost_center: "CC-UNMAPPED",
    invest_type_std: "A",
    accounting_basis: "FVOCI",
    currency_basis: "CNY",
    interest_income_514: "70000",
    fair_value_change_516: "0",
    capital_gain_517: "0",
    manual_adjustment: "0",
    total_pnl: "70000",
    abs_pnl: "70000",
  },
  {
    report_date: "2025-12-31",
    reason_code: "no_business_rule_match" as const,
    source_kind: "formal_fi",
    instrument_code: "UNALLOCATED-A-NEG",
    portfolio_name: "Unmapped Desk",
    cost_center: "CC-UNMAPPED",
    invest_type_std: "A",
    accounting_basis: "FVOCI",
    currency_basis: "CNY",
    interest_income_514: "-20000",
    fair_value_change_516: "0",
    capital_gain_517: "0",
    manual_adjustment: "0",
    total_pnl: "-20000",
    abs_pnl: "20000",
  },
];

describe("buildPnlByBusinessSheets", () => {
  it.each(["monthly", "bond_bucket_monthly"] as const)("uses each month's evidence for %s analysis rows", (dimension) => {
    const month = minimalMonthlyBucket();
    const rows = ["2026-07", "2026-08", "2026-09", "2026-10"].map((key) => minimalAnalysisRow({
      dimension_key: dimension === "monthly" ? `${key}-31` : `${key}::rate_bond`,
      dimension_label: `${key} 利率债`,
    }));
    const sheets = buildPnlByBusinessSheets({
      viewMode: "ytd", reportDate: "2026-10-31", year: 2026,
      ytdRows: [], adbAvgByBusinessType: new Map(), formalRows: [],
      months: [
        { ...month, month_key: "2026-07", coverage_days: 31, expected_days: 31, sample_filled: false },
        { ...month, month_key: "2026-08", coverage_days: 30, expected_days: 31, sample_filled: true },
        { ...month, month_key: "2026-10", coverage_days: 31, expected_days: 31, balance_quality_issues: [{
          issue_id: "oct-source", report_date: "2026-10-02", status: "pending", reason: "十月来源待核实",
          source_file: "source.xls", source_version: "v1",
        }] },
      ],
      adjustments: [], adjustmentEvents: [], bondBucketRows: [],
      bondBucketMonthlyRows: rows, bondBucketMonthlyQuality: { coverage_days: 242, expected_days: 243 },
      negativeFtpRows: [], analysisRows: rows, analysisDimension: dimension,
      analysisQuality: { coverage_days: 242, expected_days: 243 },
    });
    for (const name of ["投资资产四类月度", "多维下钻"]) {
      const sheet = sheets.find((item) => item.sheet === name)!;
      const notes = sheet.data.slice(3).map((row) => String(row.at(-1)));
      expect(notes[0]).toContain("31/31 天");
      expect(notes[0]).not.toMatch(/待核对|样本填充|十月来源/);
      expect(notes[1]).toContain("30/31 天");
      expect(notes[1]).toContain("待核对");
      expect(notes[1]).toContain("样本填充");
      expect(notes[2]).toContain("2026-09 本月覆盖未返回");
      expect(notes[3]).toContain("2026-10-02 十月来源待核实");
      expect(notes.every((note) => !note.includes("242/243"))).toBe(true);
    }
  });

  it("retains endpoint coverage beside exported values even without source issues", () => {
    const month = { ...minimalMonthlyBucket(), coverage_days: 30, expected_days: 31, sample_filled: false };
    const sheets = buildPnlByBusinessSheets({
      viewMode: "ytd", reportDate: "2025-12-31", year: 2025,
      ytdRows: [minimalYtdRow(), minimalYtdRow({ row_key: "asset_detail_test", business_type: "其中：测试" })],
      ytdSummary: minimalYtdSummary(), ytdQuality: { coverage_days: 364, expected_days: 365 },
      adbAvgByBusinessType: new Map(), formalRows: [], months: [month],
      adjustments: [], adjustmentEvents: [], bondBucketRows: [minimalAnalysisRow()],
      bondBucketQuality: { coverage_days: 365, expected_days: 365, sample_filled: true },
      bondBucketMonthlyRows: [minimalAnalysisRow({ dimension_key: `${month.month_key}::rate_bond` })],
      bondBucketMonthlyQuality: { coverage_days: 364, expected_days: 365 },
      negativeFtpRows: [minimalAnalysisRow({ ftp_net_pnl: "-1000" })],
      negativeFtpQuality: { coverage_days: 364, expected_days: 365 },
      analysisRows: [minimalAnalysisRow()], analysisDimension: "portfolio",
      analysisQuality: { coverage_days: 364, expected_days: 365 }, balanceQualityIssues: [],
    });
    for (const name of ["月度业务种类", "月度其中项明细"]) {
      const sheet = sheets.find((item) => item.sheet === name)!;
      expect(sheet.data.at(-1)?.at(-1)).toContain("30/31 天");
      expect(sheet.data.at(-1)?.at(-1)).toContain("观测日均");
      expect(sheet.data.at(-1)?.at(-1)).toContain("待核对");
    }
    expect(sheets.find((item) => item.sheet === "投资资产四类月度")?.data.at(-1)?.at(-1)).toContain("30/31 天");
    for (const name of ["YTD年累计明细", "YTD其中项明细", "负FTP资产清单", "多维下钻"]) {
      const sheet = sheets.find((item) => item.sheet === name)!;
      expect(sheet.data.at(-1)?.at(-1)).toContain("364/365 天");
      expect(sheet.data.at(-1)?.at(-1)).toContain("待核对");
    }
    const complete = sheets.find((item) => item.sheet === "投资资产四类")!;
    expect(complete.data.at(-1)?.at(-1)).toContain("365/365 天；样本填充");
    expect(complete.data.at(-1)?.at(-1)).not.toContain("观测日均");
    const ytd = sheets.find((item) => item.sheet === "YTD年累计明细")!;
    expect(ytd.data[1]?.[7]).toBe(9.876543);
    expect(JSON.stringify(sheets[0]?.data)).toContain("30/31 天");
    expect(JSON.stringify(sheets[0]?.data)).toContain("364/365 天");
  });

  it("uses the backend YTD summary for the parent total instead of summing child rows", () => {
    const sheets = buildPnlByBusinessSheets({
      viewMode: "ytd",
      reportDate: "2025-12-31",
      year: 2025,
      periodStart: "2025-01-01",
      periodEnd: "2025-12-31",
      periodLabel: "2025 YTD",
      balanceQualityIssues: [{
        issue_id: "source-date", report_date: "2025-11-20", status: "pending",
        reason: "源表日期与文件名不一致。", source_file: "source.xls", source_version: "sv_test",
      }],
      ytdRows: [minimalYtdRow()],
      ytdSummary: minimalYtdSummary(),
      adbAvgByBusinessType: new Map(),
      formalRows: [],
      months: [],
      adjustments: [],
      adjustmentEvents: [],
      bondBucketRows: [],
      bondBucketMonthlyRows: [],
      negativeFtpRows: [],
      analysisRows: [],
    });

    const totalRow = sheets[1]?.data.at(-1);
    expect(sheets[0]?.data).toContainEqual([
      "余额来源待核实", "2025-11-20", "源表日期与文件名不一致。",
      "受影响期间的日均、年化收益率和 FTP 为暂列值，取得正确源表后重算。",
    ]);
    expect(totalRow?.slice(1, 12)).toEqual([
      46,
      91,
      82,
      73,
      64,
      55,
      12.34,
      19,
      4.56,
      1,
      91,
    ]);
  });

  it("does not fabricate a YTD parent total when the backend summary is missing", () => {
    const sheets = buildPnlByBusinessSheets({
      viewMode: "ytd",
      reportDate: "2025-12-31",
      year: 2025,
      periodStart: "2025-01-01",
      periodEnd: "2025-12-31",
      periodLabel: "2025 YTD",
      ytdRows: [minimalYtdRow()],
      adbAvgByBusinessType: new Map(),
      formalRows: [],
      months: [],
      adjustments: [],
      adjustmentEvents: [],
      bondBucketRows: [],
      bondBucketMonthlyRows: [],
      negativeFtpRows: [],
      analysisRows: [],
    });

    expect(sheets[1]?.data).toHaveLength(2);
  });

  it("builds monthly report sheets without YTD-only analysis tabs", () => {
    const sheets = buildPnlByBusinessSheets({
      viewMode: "monthly",
      reportDate: "2025-12-31",
      year: 2025,
      ytdRows: [minimalYtdRow({ avg_balance: "0", annualized_yield_pct: null, ftp_net_pnl: null, ftp_net_annualized_yield_pct: null })],
      adbAvgByBusinessType: new Map([["政策性金融债", 1_000_000_000]]),
      formalRows: [minimalFormalRow()],
      months: [minimalMonthlyBucket()],
      adjustments: [minimalAdjustment()],
      adjustmentEvents: [minimalAdjustment({ event_type: "created" })],
      bondBucketRows: [minimalAnalysisRow()],
      bondBucketMonthlyRows: [minimalAnalysisRow()],
      negativeFtpRows: [minimalAnalysisRow({ ftp_net_pnl: "-1000" })],
      analysisDimension: "monthly",
      analysisRows: [minimalAnalysisRow()],
    });

    expect(sheets.map((sheet) => sheet.sheet)).toEqual([
      "导出说明",
      "月报业务种类",
      "月报未分类汇总",
      "月报未分类明细",
      "月报其中项明细",
    ]);
    expect(sheets[0]?.data).toEqual(expect.arrayContaining([expect.arrayContaining(["月报(ZQTZ)"])]));
    expect(sheets[1]?.data).toEqual(expect.arrayContaining([expect.arrayContaining(["政策性金融债"])]));
    expect(sheets[1]?.data).not.toEqual(expect.arrayContaining([expect.arrayContaining(["其中：本币专户（成本法）"])]));
    expect(sheets.find((sheet) => sheet.sheet === "月报未分类汇总")?.data).toEqual(
      expect.arrayContaining([expect.arrayContaining(["2025-12", 5, 9])]),
    );
    expect(sheets.find((sheet) => sheet.sheet === "月报未分类明细")?.data).toEqual(
      expect.arrayContaining([expect.arrayContaining(["2025-12", "UNALLOCATED-A-NEG", -2, 2])]),
    );
    expect(sheets.find((sheet) => sheet.sheet === "月报其中项明细")?.data).toEqual(
      expect.arrayContaining([expect.arrayContaining(["其中：本币专户（成本法）"])]),
    );
    const monthlyDetailFirstRow = sheets.find((sheet) => sheet.sheet === "月报其中项明细")?.data[0];
    expect(monthlyDetailFirstRow?.some((cell) => typeof cell === "string" && cell.includes("重叠"))).toBe(true);
  });

  it("preserves uncomputed FTP assets separately from the ten largest calculated losses", () => {
    const rows = [
      ...Array.from({ length: 12 }, (_, i) => minimalAnalysisRow({ dimension_key: `loss-${i}`, ftp_net_pnl: String(-i - 1) })),
      minimalAnalysisRow({ dimension_key: "zero", ftp_net_pnl: "0" }),
      minimalAnalysisRow({ dimension_key: "unknown", dimension_label: "未计算资产", total_pnl: "-12345.67", ftp_net_pnl: null }),
    ];
    const list = buildNegativeFtpList(rows);
    expect(list.calculatedCount).toBe(13);
    expect(list.negativeCount).toBe(12);
    expect(list.topRows).toHaveLength(10);
    expect(list.topRows[0].dimension_key).toBe("loss-11");
    expect(list.topRows[9].dimension_key).toBe("loss-2");
    expect(list.unavailableRows.map((row) => row.dimension_key)).toEqual(["unknown"]);
    const sheets = buildPnlByBusinessSheets({
      viewMode: "ytd", reportDate: "2025-12-31", year: 2025, ytdRows: [], adbAvgByBusinessType: new Map(),
      formalRows: [], months: [], adjustments: [], adjustmentEvents: [], bondBucketRows: [], bondBucketMonthlyRows: [],
      negativeFtpRows: rows, analysisRows: [],
    });
    const unknown = sheets.find((sheet) => sheet.sheet === "FTP未计算资产")!;
    expect(unknown.data).toEqual(expect.arrayContaining([expect.arrayContaining(["未计算资产"])]));
    expect(JSON.stringify(unknown.data)).toContain("未计算 1 笔");
    const negative = sheets.find((sheet) => sheet.sheet === "负FTP资产清单")!;
    expect(JSON.stringify(negative.data)).not.toContain("未计算资产");
    expect(JSON.stringify(negative.data)).toContain("负收益 12 笔");
  });

  it("builds writer-compatible YTD sheets with stable names and localized values", async () => {
    const sheets = buildPnlByBusinessSheets({
      viewMode: "ytd",
      reportDate: "2025-12-31",
      year: 2025,
      periodStart: "2025-01-01",
      periodEnd: "2025-12-31",
      periodLabel: "2025 YTD",
      ytdRows: [
        minimalYtdRow(),
        minimalYtdRow({
          row_key: "asset_zqtz_detail_local_currency_special_account_cost",
          business_type: "其中：本币专户（成本法）",
          source_note: "ZQTZSHOW 其中项：J0 剔除市值法清单后的成本法专户",
        }),
      ],
      adbAvgByBusinessType: new Map([["政策性金融债", 1_000_000_000]]),
      formalRows: [],
      months: [minimalMonthlyBucket()],
      adjustments: [minimalAdjustment()],
      adjustmentEvents: [minimalAdjustment({ event_type: "created" })],
      bondBucketRows: [minimalAnalysisRow()],
      bondBucketMonthlyRows: [minimalAnalysisRow({ dimension_key: "2025-12::rate_bond", dimension_label: "2025-12 利率债" })],
      negativeFtpRows: [minimalAnalysisRow({ dimension_key: "240001.IB", dimension_label: "240001.IB 负FTP资产", ftp_net_pnl: "-1000" })],
      analysisDimension: "monthly",
      analysisRows: [minimalAnalysisRow({ dimension_key: "2025-12-31", dimension_label: "2025-12-31" })],
      selectedBusinessLabel: "政策性金融债",
      unallocatedBreakdown: [minimalUnallocatedBreakdownRow],
      unallocatedItems: minimalUnallocatedItems,
    });

    expect(sheets.map((sheet) => sheet.sheet)).toEqual([
      "导出说明",
      "YTD年累计明细",
      "YTD未分类汇总",
      "YTD未分类明细",
      "YTD其中项明细",
      "月度业务种类",
      "月度未分类汇总",
      "月度未分类明细",
      "月度其中项明细",
      "手工调整当前",
      "手工调整事件",
      "投资资产四类",
      "投资资产四类月度",
      "负FTP资产清单",
      "多维下钻",
    ]);
    expect(sheets[0]?.data).toEqual(
      expect.arrayContaining([expect.arrayContaining(["2025-12-31"])]),
    );
    expect(sheets[1]?.data).toEqual(
      expect.arrayContaining([expect.arrayContaining(["政策性金融债"])]),
    );
    expect(sheets[1]?.data).toEqual(expect.arrayContaining([expect.arrayContaining([10])]));
    expect(sheets[1]?.data).not.toEqual(expect.arrayContaining([expect.arrayContaining(["其中：本币专户（成本法）"])]));
    expect(sheets.find((sheet) => sheet.sheet === "YTD其中项明细")?.data).toEqual(
      expect.arrayContaining([expect.arrayContaining(["其中：本币专户（成本法）"])]),
    );
    const unallocatedSummary = sheets.find((sheet) => sheet.sheet === "YTD未分类汇总");
    expect(unallocatedSummary?.data).toEqual(expect.arrayContaining([expect.arrayContaining([5, 9])]));
    const unallocatedItems = sheets.find((sheet) => sheet.sheet === "YTD未分类明细");
    expect(unallocatedItems?.data).toEqual(expect.arrayContaining([expect.arrayContaining(["UNALLOCATED-A", 7, 7])]));
    expect(unallocatedItems?.data).toEqual(expect.arrayContaining([expect.arrayContaining(["UNALLOCATED-A-NEG", -2, 2])]));
    const monthlyDetailFirstRow = sheets.find((sheet) => sheet.sheet === "月度其中项明细")?.data[0];
    expect(monthlyDetailFirstRow?.some((cell) => typeof cell === "string" && cell.includes("重叠"))).toBe(true);

    const blob = await writeExcelFile(sheets).toBlob();
    expect(blob.size).toBeGreaterThan(1000);
  });

  it("prefixes the YTD detail sheet with an overlap warning row", () => {
    const sheets = buildPnlByBusinessSheets({
      viewMode: "ytd",
      reportDate: "2025-12-31",
      year: 2025,
      periodStart: "2025-01-01",
      periodEnd: "2025-12-31",
      periodLabel: "2025 YTD",
      ytdRows: [
        minimalYtdRow(),
        minimalYtdRow({
          row_key: "asset_zqtz_detail_local_currency_special_account_cost",
          business_type: "其中：本币专户（成本法）",
          source_note: "ZQTZSHOW 其中项：J0 剔除市值法清单后的成本法专户",
        }),
      ],
      adbAvgByBusinessType: new Map(),
      formalRows: [],
      months: [],
      adjustments: [],
      adjustmentEvents: [],
      bondBucketRows: [],
      bondBucketMonthlyRows: [],
      negativeFtpRows: [],
      analysisDimension: undefined,
      analysisRows: [],
    });

    const detailSheet = sheets.find((sheet) => sheet.sheet === "YTD其中项明细");
    const firstRow = detailSheet?.data[0];

    expect(firstRow?.some((cell) => typeof cell === "string" && cell.includes("重叠"))).toBe(true);
  });

  it("exports true-zero ADB as zero while leaving denominator metrics unavailable", () => {
    const sheets = buildPnlByBusinessSheets({
      viewMode: "ytd",
      reportDate: "2025-12-31",
      year: 2025,
      periodStart: "2025-01-01",
      periodEnd: "2025-12-31",
      periodLabel: "2025 YTD",
      ytdRows: [
        minimalYtdRow({
          avg_balance: "0",
          annualized_yield_pct: null,
          ftp_cost: null,
          ftp_net_pnl: null,
          ftp_net_annualized_yield_pct: null,
        }),
      ],
      ytdSummary: minimalYtdSummary({
        avg_balance: "0",
        annualized_yield_pct: null,
        ftp_cost: null,
        ftp_net_pnl: null,
        ftp_net_annualized_yield_pct: null,
      }),
      adbAvgByBusinessType: new Map([["政策性金融债", 0]]),
      formalRows: [],
      months: [],
      adjustments: [],
      adjustmentEvents: [],
      bondBucketRows: [],
      bondBucketMonthlyRows: [],
      negativeFtpRows: [],
      analysisDimension: undefined,
      analysisRows: [],
      selectedBusinessLabel: "政策性金融债",
    });

    const ytdSheet = sheets.find((sheet) => sheet.sheet === "YTD年累计明细");

    const businessRow = ytdSheet?.data[1];
    const footerRow = ytdSheet?.data[2];

    expect(businessRow?.[0]).toBe("政策性金融债");
    expect(businessRow?.[1]).toBe(0);
    expect(businessRow?.[7]).toBeNull();
    expect(businessRow?.[8]).toBeNull();
    expect(businessRow?.[9]).toBeNull();
    expect(footerRow?.[0]).toBe("父级汇总");
    expect(footerRow?.[1]).toBe(0);
    expect(footerRow?.[7]).toBeNull();
    expect(footerRow?.[8]).toBeNull();
    expect(footerRow?.[9]).toBeNull();
  });

  it("exports YTD annualized yield and FTP fields from backend fields", () => {
    const businessType = minimalYtdRow().business_type;
    const sheets = buildPnlByBusinessSheets({
      viewMode: "ytd",
      reportDate: "2025-12-31",
      year: 2025,
      periodStart: "2025-01-01",
      periodEnd: "2025-12-31",
      periodLabel: "2025 YTD",
      ytdRows: [
        minimalYtdRow({
          total_pnl: "100000",
          avg_balance: "1000000000",
          annualized_yield_pct: "9.876543",
          ftp_net_pnl: "76543.21",
          ftp_net_annualized_yield_pct: "8.765432",
        }),
      ],
      adbAvgByBusinessType: new Map([[businessType, 100_000_000]]),
      formalRows: [],
      months: [],
      adjustments: [],
      adjustmentEvents: [],
      bondBucketRows: [],
      bondBucketMonthlyRows: [],
      negativeFtpRows: [],
      analysisDimension: undefined,
      analysisRows: [],
      selectedBusinessLabel: businessType,
    });

    const ytdSheet = sheets[1];
    const businessRow = ytdSheet?.data[1];

    expect(businessRow?.[7]).toBe(9.876543);
    expect(businessRow?.[8]).toBe(7.654321);
    expect(businessRow?.[9]).toBe(8.765432);
  });

  it("builds a formal detail sheet with the writer sheet contract", () => {
    const sheets = buildPnlByBusinessSheets({
      viewMode: "formal",
      reportDate: "2025-12-31",
      year: 2025,
      ytdRows: [],
      adbAvgByBusinessType: new Map(),
      formalRows: [minimalFormalRow()],
      formalSummary: minimalFormalSummary(),
      months: [],
      adjustments: [],
      adjustmentEvents: [],
      bondBucketRows: [],
      bondBucketMonthlyRows: [],
      negativeFtpRows: [],
      analysisDimension: undefined,
      analysisRows: [],
    });

    expect(sheets.map((sheet) => sheet.sheet)).toEqual(["导出说明", "Primary对账明细"]);
    expect(sheets[1]?.data).toEqual(
      expect.arrayContaining([expect.arrayContaining(["政策性金融债"])]),
    );
  });

  it("uses the backend formal summary for the total row instead of summing rows with a bad value", () => {
    const sheets = buildPnlByBusinessSheets({
      viewMode: "formal",
      reportDate: "2025-12-31",
      year: 2025,
      ytdRows: [],
      adbAvgByBusinessType: new Map(),
      formalRows: [
        minimalFormalRow(),
        // 解析失败行：interest_income_514 非数值，若前端逐行累加会被 ?? 0 静默吞掉。
        minimalFormalRow({
          business_type_primary: "非标债权",
          interest_income_514: "not-a-number",
          total_pnl: "not-a-number",
          scale_amount: "not-a-number",
        }),
      ],
      formalSummary: minimalFormalSummary({
        total_pnl: "999999",
        total_scale_amount: "2000000000",
        interest_income_514: "888888",
        pnl_row_count: 20,
      }),
      months: [],
      adjustments: [],
      adjustmentEvents: [],
      bondBucketRows: [],
      bondBucketMonthlyRows: [],
      negativeFtpRows: [],
      analysisDimension: undefined,
      analysisRows: [],
    });

    const formalSheet = sheets.find((sheet) => sheet.sheet === "Primary对账明细");
    const totalRow = formalSheet?.data.at(-1);

    expect(totalRow?.[0]).toBe("全表合计");
    expect(totalRow?.[2]).toBe(20); // total_scale_amount 2,000,000,000 元 -> 20 亿元
    expect(totalRow?.[3]).toBe(88.8888); // interest_income_514 888,888 元 -> 万元
    expect(totalRow?.[7]).toBe(99.9999); // total_pnl 999,999 元 -> 万元
    expect(totalRow?.[9]).toBe(20); // pnl_row_count 直读 summary，不受解析失败行影响
  });

  it("annotates the formal total row as unavailable instead of silently omitting it when the backend summary is missing", () => {
    const sheets = buildPnlByBusinessSheets({
      viewMode: "formal",
      reportDate: "2025-12-31",
      year: 2025,
      ytdRows: [],
      adbAvgByBusinessType: new Map(),
      formalRows: [minimalFormalRow()],
      formalSummary: undefined,
      months: [],
      adjustments: [],
      adjustmentEvents: [],
      bondBucketRows: [],
      bondBucketMonthlyRows: [],
      negativeFtpRows: [],
      analysisDimension: undefined,
      analysisRows: [],
    });

    const formalSheet = sheets.find((sheet) => sheet.sheet === "Primary对账明细");
    const totalRow = formalSheet?.data.at(-1);

    expect(totalRow?.[0]).toContain("不可用");
    expect(totalRow?.slice(1)).toEqual([null, null, null, null, null, null, null, null, null]);
  });
});
