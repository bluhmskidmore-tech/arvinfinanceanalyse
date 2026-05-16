import { describe, expect, it } from "vitest";
import writeExcelFile from "write-excel-file/browser";

import type {
  PnlByBusinessAnalysisRow,
  PnlByBusinessManualAdjustmentPayload,
  PnlByBusinessMonthlyBucket,
  PnlByBusinessRow,
  PnlByBusinessYtdItem,
} from "../../api/contracts";

import { buildPnlByBusinessSheets } from "./pnlByBusinessExport";

const minimalYtdRow = (patch: Partial<PnlByBusinessYtdItem> = {}): PnlByBusinessYtdItem => ({
  row_key: "rk_test",
  sort_order: 1,
  business_type: "政策性金融债",
  interest_income: "100000",
  fair_value_change: "0",
  capital_gain: "0",
  manual_adjustment: "0",
  total_pnl: "100000",
  current_balance: "1000000000",
  balance_yield_pct: null,
  proportion: "0.1",
  assets_count: 3,
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
  ...patch,
});

const minimalMonthlyBucket = (): PnlByBusinessMonthlyBucket => ({
  month_key: "2025-12",
  period_start_date: "2025-12-01",
  period_end_date: "2025-12-31",
  calendar_days: 31,
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

describe("buildPnlByBusinessSheets", () => {
  it("builds monthly report sheets without YTD-only analysis tabs", () => {
    const sheets = buildPnlByBusinessSheets({
      viewMode: "monthly",
      reportDate: "2025-12-31",
      year: 2025,
      ytdRows: [minimalYtdRow()],
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

    expect(sheets.map((sheet) => sheet.sheet)).toEqual(["导出说明", "月报业务种类", "月报其中项明细"]);
    expect(sheets[0]?.data).toEqual(expect.arrayContaining([expect.arrayContaining(["月报(ZQTZ)"])]));
    expect(sheets[1]?.data).toEqual(expect.arrayContaining([expect.arrayContaining(["政策性金融债"])]));
    expect(sheets[1]?.data).not.toEqual(expect.arrayContaining([expect.arrayContaining(["其中：本币专户（成本法）"])]));
    expect(sheets[2]?.data).toEqual(expect.arrayContaining([expect.arrayContaining(["其中：本币专户（成本法）"])]));
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
    });

    expect(sheets.map((sheet) => sheet.sheet)).toEqual([
      "导出说明",
      "YTD年累计明细",
      "YTD其中项明细",
      "月度业务种类",
      "月度其中项明细",
      "手工调整当前",
      "手工调整事件",
      "债券四类",
      "四类债券月度",
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
    expect(sheets[2]?.data).toEqual(expect.arrayContaining([expect.arrayContaining(["其中：本币专户（成本法）"])]));

    const blob = await writeExcelFile(sheets).toBlob();
    expect(blob.size).toBeGreaterThan(1000);
  });

  it("builds a formal detail sheet with the writer sheet contract", () => {
    const sheets = buildPnlByBusinessSheets({
      viewMode: "formal",
      reportDate: "2025-12-31",
      year: 2025,
      ytdRows: [],
      adbAvgByBusinessType: new Map(),
      formalRows: [minimalFormalRow()],
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
});
