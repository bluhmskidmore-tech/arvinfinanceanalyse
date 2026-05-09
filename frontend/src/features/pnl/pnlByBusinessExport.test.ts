import { describe, expect, it } from "vitest";

import type { PnlByBusinessYtdItem } from "../../api/contracts";

import { buildPnlByBusinessWorkbook } from "./pnlByBusinessExport";

const minimalYtdRow = (patch: Partial<PnlByBusinessYtdItem> = {}): PnlByBusinessYtdItem => ({
  row_key: "rk_test",
  sort_order: 1,
  business_type: "测试业务种类",
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

describe("buildPnlByBusinessWorkbook", () => {
  it("导出说明与工作表命名包含 YTD 主表明细", () => {
    const wb = buildPnlByBusinessWorkbook({
      viewMode: "ytd",
      reportDate: "2025-12-31",
      year: 2025,
      periodStart: "2025-01-01",
      periodEnd: "2025-12-31",
      periodLabel: "2025 年累计",
      ytdRows: [minimalYtdRow()],
      adbAvgByBusinessType: new Map([["测试业务种类", 1_000_000_000]]),
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
    expect(wb.SheetNames).toContain("导出说明");
    expect(wb.SheetNames).toContain("YTD年累计明细");
  });

  it("formal 视图包含 Formal 单日工作表", () => {
    const wb = buildPnlByBusinessWorkbook({
      viewMode: "formal",
      reportDate: "2025-12-31",
      year: 2025,
      ytdRows: [],
      adbAvgByBusinessType: new Map(),
      formalRows: [
        {
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
        },
      ],
      months: [],
      adjustments: [],
      adjustmentEvents: [],
      bondBucketRows: [],
      bondBucketMonthlyRows: [],
      negativeFtpRows: [],
      analysisDimension: undefined,
      analysisRows: [],
    });
    expect(wb.SheetNames).toContain("Formal单日明细");
  });
});
