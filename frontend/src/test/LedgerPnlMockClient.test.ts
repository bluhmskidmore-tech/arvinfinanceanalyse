import { describe, expect, it, vi } from "vitest";

import { createApiClient } from "../api/client";
import type {
  LedgerMoneyValue,
  LedgerPnlAnalysisPayload,
  LedgerPnlDataPayload,
  LedgerPnlSummaryPayload,
  ResultMeta,
} from "../api/contracts";

const REPORT_DATE = "2025-12-31";
const TABLES_USED = [
  "qdb_gl_ledger_reconciliation_workbook",
  "qdb_gl_average_balance_workbook",
];
const CURRENCY_BASIS_NOTE = "CNX=综本；CNY=人民币账";

const EXPECTED = {
  CNX: {
    summary: {
      sourceVersion: "sv_mock_ledger_v2",
      headline: {
        assets: "1250000000",
        liabilities: "980000000",
        netAssets: "270000000",
        corePnl: "3520000",
        allPnl: "4180000",
      },
      byCurrency: [{ currency: "CNX", totalPnl: "4180000" }],
      byAccount: [
        { code: "514100", name: "利息收入", totalPnl: "2120000", count: 18 },
        { code: "516100", name: "公允价值变动损益", totalPnl: "880000", count: 9 },
        { code: "517100", name: "投资收益", totalPnl: "520000", count: 6 },
        { code: "519900", name: "其他损益", totalPnl: "660000", count: 4 },
      ],
    },
    data: {
      items: [
        {
          code: "514100",
          name: "利息收入",
          currency: "CNX",
          beginning: "101200000",
          ending: "106500000",
          monthlyPnl: "2120000",
          dailyAverage: "104100000",
          days: 31,
        },
        {
          code: "516100",
          name: "公允价值变动损益",
          currency: "CNX",
          beginning: "10000000",
          ending: "11200000",
          monthlyPnl: "880000",
          dailyAverage: "10600000",
          days: 31,
        },
        {
          code: "517100",
          name: "投资收益",
          currency: "CNX",
          beginning: "22000000",
          ending: "23500000",
          monthlyPnl: "520000",
          dailyAverage: "22800000",
          days: 31,
        },
        {
          code: "519900",
          name: "其他损益",
          currency: "CNX",
          beginning: "4000000",
          ending: "4500000",
          monthlyPnl: "660000",
          dailyAverage: "4250000",
          days: 31,
        },
      ],
      summary: { cnx: "4180000", cny: "0", total: "4180000", count: 4 },
    },
  },
  CNY: {
    summary: {
      sourceVersion: "sv_mock_ledger_v2",
      headline: {
        assets: "1120000000",
        liabilities: "870000000",
        netAssets: "250000000",
        corePnl: "3000000",
        allPnl: "3400000",
      },
      byCurrency: [{ currency: "CNY", totalPnl: "3400000" }],
      byAccount: [
        { code: "514100", name: "利息收入", totalPnl: "1900000", count: 15 },
        { code: "516100", name: "公允价值变动损益", totalPnl: "700000", count: 7 },
        { code: "517100", name: "投资收益", totalPnl: "400000", count: 4 },
        { code: "519900", name: "其他损益", totalPnl: "400000", count: 3 },
      ],
    },
    data: {
      items: [
        {
          code: "514100",
          name: "利息收入",
          currency: "CNY",
          beginning: "92000000",
          ending: "96500000",
          monthlyPnl: "1900000",
          dailyAverage: "94200000",
          days: 31,
        },
        {
          code: "516100",
          name: "公允价值变动损益",
          currency: "CNY",
          beginning: "8000000",
          ending: "8700000",
          monthlyPnl: "700000",
          dailyAverage: "8350000",
          days: 31,
        },
        {
          code: "517100",
          name: "投资收益",
          currency: "CNY",
          beginning: "18000000",
          ending: "18800000",
          monthlyPnl: "400000",
          dailyAverage: "18400000",
          days: 31,
        },
        {
          code: "519900",
          name: "其他损益",
          currency: "CNY",
          beginning: "3000000",
          ending: "3400000",
          monthlyPnl: "400000",
          dailyAverage: "3200000",
          days: 31,
        },
      ],
      summary: { cnx: "0", cny: "3400000", total: "3400000", count: 4 },
    },
  },
} as const;

type LedgerBasis = keyof typeof EXPECTED;

function yuan(value: LedgerMoneyValue) {
  return value.yuan;
}

function summaryView(payload: LedgerPnlSummaryPayload) {
  return {
    sourceVersion: payload.source_version,
    headline: {
      assets: yuan(payload.ledger_total_assets),
      liabilities: yuan(payload.ledger_total_liabilities),
      netAssets: yuan(payload.ledger_net_assets),
      corePnl: yuan(payload.ledger_monthly_pnl_core),
      allPnl: yuan(payload.ledger_monthly_pnl_all),
    },
    byCurrency: payload.by_currency.map((row) => ({
      currency: row.currency,
      totalPnl: yuan(row.total_pnl),
    })),
    byAccount: payload.by_account.map((row) => ({
      code: row.account_code,
      name: row.account_name,
      totalPnl: yuan(row.total_pnl),
      count: row.count,
    })),
  };
}

function dataView(payload: LedgerPnlDataPayload) {
  return {
    items: payload.items.map((row) => ({
      code: row.account_code,
      name: row.account_name,
      currency: row.currency,
      beginning: yuan(row.beginning_balance),
      ending: yuan(row.ending_balance),
      monthlyPnl: yuan(row.monthly_pnl),
      dailyAverage: yuan(row.daily_avg_balance),
      days: row.days_in_period,
    })),
    summary: {
      cnx: yuan(payload.summary.total_pnl_cnx),
      cny: yuan(payload.summary.total_pnl_cny),
      total: yuan(payload.summary.total_pnl),
      count: payload.summary.count,
    },
  };
}

function expectLedgerMeta(
  meta: ResultMeta,
  basis: LedgerBasis,
  reportDate = REPORT_DATE,
) {
  expect(meta.rule_version).toBe("rv_ledger_pnl_v2");
  expect(meta.cache_version).toBe("cv_ledger_pnl_v2");
  expect(meta.tables_used).toEqual(TABLES_USED);
  expect(meta.filters_applied).toEqual({
    report_date: reportDate,
    currency: basis,
    currency_basis: basis,
    currency_basis_note: CURRENCY_BASIS_NOTE,
  });
}

function expectAnalysisMeta(
  meta: ResultMeta,
  basis: LedgerBasis,
  reportDate = REPORT_DATE,
) {
  expect(meta.result_kind).toBe("ledger_pnl.analysis");
  expect(meta.basis).toBe("ledger");
  expect(meta.formal_use_allowed).toBe(false);
  expect(meta.rule_version).toBe("rv_ledger_pnl_analysis_v1");
  expect(meta.cache_version).toBe("cv_ledger_pnl_analysis_v1");
  expect(meta.tables_used).toEqual(TABLES_USED);
  expect(meta.filters_applied).toEqual({
    report_date: reportDate,
    currency: basis,
    currency_basis: basis,
    currency_basis_note: CURRENCY_BASIS_NOTE,
  });
}

function expectAnalysisTieOut(payload: LedgerPnlAnalysisPayload) {
  const coreMoney = payload.conclusion.core_pnl;
  const otherMoney = payload.conclusion.other_5_pnl;
  const allMoney = payload.conclusion.all_pnl;
  const bridgeTotal = payload.pnl_bridge.total;
  const bridgeResidual = payload.pnl_bridge.residual;
  const positiveTotal = payload.contributors.positive_total;
  const negativeTotal = payload.contributors.negative_total;
  const netTotal = payload.contributors.net_total;
  if (
    !coreMoney ||
    !otherMoney ||
    !allMoney ||
    !bridgeTotal ||
    !bridgeResidual ||
    !positiveTotal ||
    !negativeTotal ||
    !netTotal
  ) {
    throw new Error("ready mock analysis must provide every analytical amount");
  }
  const core = Number(coreMoney.yuan);
  const other = Number(otherMoney.yuan);
  const total = Number(bridgeTotal.yuan);
  expect(core + other).toBe(total);
  expect(Number(allMoney.yuan)).toBe(total);
  expect(Number(bridgeResidual.yuan)).toBe(0);
  expect(payload.basis_comparison).toHaveLength(6);
  for (const row of payload.basis_comparison) {
    expect(row.availability).toEqual({ CNX: "ready", CNY: "ready" });
    expect(row.evidence_rows.CNX).toBeGreaterThan(0);
    expect(row.evidence_rows.CNY).toBeGreaterThan(0);
    if (!row.cnx || !row.cny || !row.cnx_minus_cny) {
      throw new Error(`ready basis row ${row.metric_key} must provide every amount`);
    }
    expect(Number(row.cnx.yuan) - Number(row.cny.yuan)).toBe(Number(row.cnx_minus_cny.yuan));
  }
  expect(Number(positiveTotal.yuan) + Number(negativeTotal.yuan)).toBe(Number(netTotal.yuan));
  expect(payload.contributors.top_positive.map((row) => row.rank)).toEqual(
    payload.contributors.top_positive.map((_, index) => index + 1),
  );
  expect(payload.contributors.top_negative.map((row) => row.rank)).toEqual(
    payload.contributors.top_negative.map((_, index) => index + 1),
  );
}

describe("Ledger PnL mock client accounting bases", () => {
  it.each(["CNX", "CNY"] as const)("returns an internally consistent static %s fixture", async (basis) => {
    const client = createApiClient({ mode: "mock" });

    const [summary, data] = await Promise.all([
      client.getLedgerPnlSummary(REPORT_DATE, basis),
      client.getLedgerPnlData(REPORT_DATE, basis),
    ]);

    expect(summary.result.report_date).toBe(REPORT_DATE);
    expect(data.result.report_date).toBe(REPORT_DATE);
    expect(summaryView(summary.result)).toEqual(EXPECTED[basis].summary);
    expect(dataView(data.result)).toEqual(EXPECTED[basis].data);
    expectLedgerMeta(summary.result_meta, basis);
    expectLedgerMeta(data.result_meta, basis);

    const headlineTotal = Number(summary.result.ledger_monthly_pnl_all.yuan);
    expect(summary.result.by_currency.reduce((total, row) => total + Number(row.total_pnl.yuan), 0)).toBe(
      headlineTotal,
    );
    expect(summary.result.by_account.reduce((total, row) => total + Number(row.total_pnl.yuan), 0)).toBe(
      headlineTotal,
    );
    expect(data.result.items.reduce((total, row) => total + Number(row.monthly_pnl.yuan), 0)).toBe(
      Number(data.result.summary.total_pnl.yuan),
    );
    expect(data.result.summary.count).toBe(data.result.items.length);
  });

  it.each(["CNX", "CNY"] as const)("returns a candidate analysis fixture that ties out for %s", async (basis) => {
    const client = createApiClient({ mode: "mock" });

    const analysis = await client.getLedgerPnlAnalysis(REPORT_DATE, basis);

    expect(analysis.result.report_date).toBe(REPORT_DATE);
    expect(analysis.result.source_version).toBe(EXPECTED[basis].summary.sourceVersion);
    expect(analysis.result_meta.source_version).toBe(EXPECTED[basis].summary.sourceVersion);
    expect(analysis.result.currency_basis).toBe(basis);
    expect(analysis.result.basis_availability).toEqual({ CNX: "ready", CNY: "ready" });
    expect(analysis.result.analysis_status).toBe("ready");
    expect(analysis.result.metric_status).toBe("candidate");
    expect(analysis.result_meta.evidence_rows).toBe(basis === "CNX" ? 37 : 29);
    expectAnalysisMeta(analysis.result_meta, basis);
    expectAnalysisTieOut(analysis.result);
    expect(analysis.result.contributors.top_positive[0]).toMatchObject({
      rank: 1,
      account_code: "514100",
      account_name: "利息收入",
    });
  });

  it.each([
    [
      "2025-12-31",
      "CNX",
      {
        sourceVersion: "sv_mock_ledger_v2",
        corePnl: "3520000",
        otherPnl: "660000",
        allPnl: "4180000",
        evidenceRows: 37,
        daysInPeriod: 31,
        periodStatus: "available",
      },
    ],
    [
      "2025-12-31",
      "CNY",
      {
        sourceVersion: "sv_mock_ledger_v2",
        corePnl: "3000000",
        otherPnl: "400000",
        allPnl: "3400000",
        evidenceRows: 29,
        daysInPeriod: 31,
        periodStatus: "available",
      },
    ],
    [
      "2025-11-30",
      "CNX",
      {
        sourceVersion: "sv_mock_ledger_analysis_v1_previous",
        corePnl: "3100000",
        otherPnl: "600000",
        allPnl: "3700000",
        evidenceRows: 32,
        daysInPeriod: 30,
        periodStatus: "no_previous_period",
      },
    ],
    [
      "2025-11-30",
      "CNY",
      {
        sourceVersion: "sv_mock_ledger_analysis_v1_previous",
        corePnl: "2800000",
        otherPnl: "350000",
        allPnl: "3150000",
        evidenceRows: 27,
        daysInPeriod: 30,
        periodStatus: "no_previous_period",
      },
    ],
  ] as const)("uses one %s static snapshot across all %s endpoints", async (reportDate, basis, expected) => {
    const client = createApiClient({ mode: "mock" });

    const [summary, data, analysis] = await Promise.all([
      client.getLedgerPnlSummary(reportDate, basis),
      client.getLedgerPnlData(reportDate, basis),
      client.getLedgerPnlAnalysis(reportDate, basis),
    ]);

    expect(summary.result.report_date).toBe(reportDate);
    expect(data.result.report_date).toBe(reportDate);
    expect(analysis.result).toMatchObject({
      report_date: reportDate,
      source_version: expected.sourceVersion,
      currency_basis: basis,
      analysis_status: "ready",
      conclusion: {
        core_pnl: expect.objectContaining({ yuan: expected.corePnl }),
        other_5_pnl: expect.objectContaining({ yuan: expected.otherPnl }),
        all_pnl: expect.objectContaining({ yuan: expected.allPnl }),
      },
      period_comparison: {
        status: expected.periodStatus,
      },
    });
    expect(summary.result.source_version).toBe(expected.sourceVersion);
    expect(summary.result.ledger_monthly_pnl_core.yuan).toBe(expected.corePnl);
    expect(summary.result.ledger_monthly_pnl_all.yuan).toBe(expected.allPnl);
    expect(data.result.summary.total_pnl.yuan).toBe(expected.allPnl);
    expect(data.result.summary.count).toBe(data.result.items.length);
    expect(data.result.items.every((row) => row.days_in_period === expected.daysInPeriod)).toBe(true);
    expect(
      data.result.items.reduce((total, row) => total + Number(row.monthly_pnl.yuan), 0),
    ).toBe(Number(expected.allPnl));

    const comparisonKey = basis === "CNX" ? "cnx" : "cny";
    const allPnlComparison = analysis.result.basis_comparison.find((row) => row.metric_key === "all_pnl");
    expect(allPnlComparison?.[comparisonKey]?.yuan).toBe(expected.allPnl);
    expect(analysis.result_meta.evidence_rows).toBe(allPnlComparison?.evidence_rows[basis]);

    for (const meta of [summary.result_meta, data.result_meta, analysis.result_meta]) {
      expect(meta).toMatchObject({
        source_version: expected.sourceVersion,
        quality_flag: "ok",
        requested_report_date: reportDate,
        resolved_report_date: reportDate,
        as_of_date: reportDate,
      });
    }
    expect(summary.result_meta.evidence_rows).toBe(expected.evidenceRows);
    expect(data.result_meta.evidence_rows).toBe(4);
    expect(analysis.result_meta.evidence_rows).toBe(expected.evidenceRows);
    expectLedgerMeta(summary.result_meta, basis, reportDate);
    expectLedgerMeta(data.result_meta, basis, reportDate);
    expectAnalysisMeta(analysis.result_meta, basis, reportDate);
    expectAnalysisTieOut(analysis.result);
  });

  it.each(["CNX", "CNY"] as const)(
    "returns explicit no_data instead of relabeling a %s fixture for an unknown date",
    async (basis) => {
      const client = createApiClient({ mode: "mock" });

      const [summary, data, analysis] = await Promise.all([
        client.getLedgerPnlSummary("2024-10-31", basis),
        client.getLedgerPnlData("2024-10-31", basis),
        client.getLedgerPnlAnalysis("2024-10-31", basis),
      ]);

      expect(summary.result).toMatchObject({
        report_date: "2024-10-31",
        source_version: "sv_mock_ledger_no_data",
        ledger_total_assets: expect.objectContaining({ yuan: "0" }),
        ledger_total_liabilities: expect.objectContaining({ yuan: "0" }),
        ledger_net_assets: expect.objectContaining({ yuan: "0" }),
        ledger_monthly_pnl_core: expect.objectContaining({ yuan: "0" }),
        ledger_monthly_pnl_all: expect.objectContaining({ yuan: "0" }),
        by_currency: [],
        by_account: [],
      });
      expect(data.result).toMatchObject({
        report_date: "2024-10-31",
        items: [],
        summary: {
          total_pnl_cnx: expect.objectContaining({ yuan: "0" }),
          total_pnl_cny: expect.objectContaining({ yuan: "0" }),
          total_pnl: expect.objectContaining({ yuan: "0" }),
          count: 0,
        },
      });

      expect(analysis.result).toMatchObject({
        report_date: "2024-10-31",
        source_version: "sv_mock_ledger_no_data",
        currency_basis: basis,
        basis_availability: { CNX: "no_data", CNY: "no_data" },
        analysis_status: "no_data",
        conclusion: {
          direction: "unavailable",
          other_effect: "unavailable",
          core_pnl: null,
          other_5_pnl: null,
          all_pnl: null,
        },
        contributors: {
          positive_total: null,
          negative_total: null,
          net_total: null,
          top_positive: [],
          top_negative: [],
        },
        period_comparison: {
          status: "current_basis_no_data",
          previous_report_date: null,
          previous_source_version: null,
          rows: [],
        },
      });
      expect(analysis.result.basis_comparison).toHaveLength(6);
      expect(
        analysis.result.basis_comparison.every(
          (row) =>
            row.cnx === null &&
            row.cny === null &&
            row.cnx_minus_cny === null &&
            row.availability.CNX === "no_data" &&
            row.availability.CNY === "no_data" &&
            row.evidence_rows.CNX === 0 &&
            row.evidence_rows.CNY === 0,
        ),
      ).toBe(true);
      for (const meta of [summary.result_meta, data.result_meta, analysis.result_meta]) {
        expect(meta).toMatchObject({
          quality_flag: "warning",
          source_version: "sv_mock_ledger_no_data",
          evidence_rows: 0,
          requested_report_date: "2024-10-31",
          resolved_report_date: "2024-10-31",
          as_of_date: "2024-10-31",
        });
      }
      expectLedgerMeta(summary.result_meta, basis, "2024-10-31");
      expectLedgerMeta(data.result_meta, basis, "2024-10-31");
      expectAnalysisMeta(analysis.result_meta, basis, "2024-10-31");
    },
  );

  it("normalizes omitted direct mock calls to CNX without adding CNY", async () => {
    const client = createApiClient({ mode: "mock" });

    const [defaultSummary, explicitSummary, defaultData, explicitData, defaultAnalysis, explicitAnalysis] = await Promise.all([
      client.getLedgerPnlSummary(REPORT_DATE),
      client.getLedgerPnlSummary(REPORT_DATE, "CNX"),
      client.getLedgerPnlData(REPORT_DATE),
      client.getLedgerPnlData(REPORT_DATE, "CNX"),
      client.getLedgerPnlAnalysis(REPORT_DATE),
      client.getLedgerPnlAnalysis(REPORT_DATE, "CNX"),
    ]);

    expect(defaultSummary.result).toEqual(explicitSummary.result);
    expect(defaultData.result).toEqual(explicitData.result);
    expect(defaultAnalysis.result).toEqual(explicitAnalysis.result);
    expect(defaultSummary.result.by_currency.map((row) => row.currency)).toEqual(["CNX"]);
    expect(defaultData.result.items.every((row) => row.currency === "CNX")).toBe(true);
    expectLedgerMeta(defaultSummary.result_meta, "CNX");
    expectLedgerMeta(defaultData.result_meta, "CNX");
    expectAnalysisMeta(defaultAnalysis.result_meta, "CNX");
  });

  it.each(["ALL", "USD", "cny", " CNX ", "", " "])(
    "rejects non-canonical direct mock basis %j",
    async (basis) => {
      const client = createApiClient({ mode: "mock" });

      await expect(client.getLedgerPnlSummary(REPORT_DATE, basis)).rejects.toThrow(/Expected CNX or CNY/);
      await expect(client.getLedgerPnlData(REPORT_DATE, basis)).rejects.toThrow(/Expected CNX or CNY/);
      await expect(client.getLedgerPnlAnalysis(REPORT_DATE, basis)).rejects.toThrow(/Expected CNX or CNY/);
    },
  );

  it("aligns dates metadata with the governed ledger source", async () => {
    const client = createApiClient({ mode: "mock" });

    const dates = await client.getLedgerPnlDates();

    expect(dates.result_meta.rule_version).toBe("rv_ledger_pnl_v2");
    expect(dates.result_meta.cache_version).toBe("cv_ledger_pnl_v2");
    expect(dates.result_meta.tables_used).toEqual(TABLES_USED);
    expect(dates.result_meta.filters_applied).toEqual({});
  });

  it("returns the exact audited account detail fixture without daily-average fields", async () => {
    const client = createApiClient({ mode: "mock" });

    const detail = await client.getLedgerPnlAccountDetail(
      "2026-06-30",
      "55000000001",
      "CNX",
    );

    expect(detail.result).toMatchObject({
      report_date: "2026-06-30",
      source_version: "sv_product_category_4490cb62d9f5",
      currency_basis: "CNX",
      analysis_status: "ready",
      metric_status: "candidate",
      account: {
        account_code: "55000000001",
        account_name: "当期所得税",
      },
      period_comparison: {
        status: "available",
        previous_report_date: "2026-05-31",
        previous_source_version: "sv_product_category_3353b116b9a6",
        current_monthly_pnl: { yuan: "-566796492.18", yi: "-5.67" },
        previous_monthly_pnl: { yuan: "0", yi: "0.00" },
        change: { yuan: "-566796492.18", yi: "-5.67" },
        current_evidence_rows: 1,
        previous_evidence_rows: 1,
      },
    });
    expect(detail.result.canonical_evidence_rows).toHaveLength(4);
    expect(detail.result.canonical_evidence_rows[0]).not.toHaveProperty("daily_avg_balance");
    expect(detail.result_meta).toMatchObject({
      result_kind: "ledger_pnl.account_detail",
      basis: "ledger",
      formal_use_allowed: false,
      evidence_rows: 1,
      filters_applied: {
        report_date: "2026-06-30",
        account_code: "55000000001",
        currency: "CNX",
        currency_basis: "CNX",
        currency_basis_note: CURRENCY_BASIS_NOTE,
      },
    });
  });

  it.each([
    {
      code: "514100",
      name: "利息收入",
      cnx: {
        current: { yuan: "2120000", yi: "0.02" },
        previous: { yuan: "1900000", yi: "0.02" },
        change: { yuan: "220000", yi: "0.00" },
      },
      cny: {
        current: { yuan: "1900000", yi: "0.02" },
        previous: { yuan: "1750000", yi: "0.02" },
        change: { yuan: "150000", yi: "0.00" },
      },
      currentDifference: { yuan: "220000", yi: "0.00" },
      previousDifference: { yuan: "150000", yi: "0.00" },
    },
    {
      code: "516100",
      name: "公允价值变动损益",
      cnx: {
        current: { yuan: "880000", yi: "0.01" },
        previous: { yuan: "750000", yi: "0.01" },
        change: { yuan: "130000", yi: "0.00" },
      },
      cny: {
        current: { yuan: "700000", yi: "0.01" },
        previous: { yuan: "650000", yi: "0.01" },
        change: { yuan: "50000", yi: "0.00" },
      },
      currentDifference: { yuan: "180000", yi: "0.00" },
      previousDifference: { yuan: "100000", yi: "0.00" },
    },
    {
      code: "517100",
      name: "投资收益",
      cnx: {
        current: { yuan: "520000", yi: "0.01" },
        previous: { yuan: "450000", yi: "0.00" },
        change: { yuan: "70000", yi: "0.00" },
      },
      cny: {
        current: { yuan: "400000", yi: "0.00" },
        previous: { yuan: "400000", yi: "0.00" },
        change: { yuan: "0", yi: "0.00" },
      },
      currentDifference: { yuan: "120000", yi: "0.00" },
      previousDifference: { yuan: "50000", yi: "0.00" },
    },
    {
      code: "519900",
      name: "其他损益",
      cnx: {
        current: { yuan: "660000", yi: "0.01" },
        previous: { yuan: "600000", yi: "0.01" },
        change: { yuan: "60000", yi: "0.00" },
      },
      cny: {
        current: { yuan: "400000", yi: "0.00" },
        previous: { yuan: "350000", yi: "0.00" },
        change: { yuan: "50000", yi: "0.00" },
      },
      currentDifference: { yuan: "260000", yi: "0.00" },
      previousDifference: { yuan: "250000", yi: "0.00" },
    },
  ])(
    "returns frozen 2025-12 account detail for Top contributor $code",
    async ({ code, name, cnx: expectedCnx, cny: expectedCny, currentDifference, previousDifference }) => {
      const client = createApiClient({ mode: "mock" });

      const cnx = await client.getLedgerPnlAccountDetail(REPORT_DATE, code, "CNX");
      const cny = await client.getLedgerPnlAccountDetail(REPORT_DATE, code, "CNY");

      expect(cnx.result).toMatchObject({
        report_date: REPORT_DATE,
        source_version: "sv_mock_ledger_v2",
        currency_basis: "CNX",
        analysis_status: "ready",
        account: { account_code: code, account_name: name },
        period_comparison: {
          status: "available",
          previous_report_date: "2025-11-30",
          previous_source_version: "sv_mock_ledger_analysis_v1_previous",
          current_monthly_pnl: expectedCnx.current,
          previous_monthly_pnl: expectedCnx.previous,
          change: expectedCnx.change,
          current_evidence_rows: 1,
          previous_evidence_rows: 1,
        },
      });
      expect(cny.result).toMatchObject({
        currency_basis: "CNY",
        analysis_status: "ready",
        account: { account_code: code, account_name: name },
        period_comparison: {
          current_monthly_pnl: expectedCny.current,
          previous_monthly_pnl: expectedCny.previous,
          change: expectedCny.change,
        },
      });
      for (const detail of [cnx, cny]) {
        expect(detail.result.basis_comparison.current.cnx_minus_cny).toEqual(currentDifference);
        expect(detail.result.basis_comparison.previous?.cnx_minus_cny).toEqual(previousDifference);
        expect(detail.result.canonical_evidence_rows).toHaveLength(4);
        expect(detail.result.canonical_evidence_rows.every(
          (row) => !("daily_avg_balance" in row),
        )).toBe(true);
        expect(detail.result_meta.evidence_rows).toBe(1);
      }
    },
  );

  it("returns the audited positive contributor change and explicit no_data for other account codes", async () => {
    const client = createApiClient({ mode: "mock" });

    const positive = await client.getLedgerPnlAccountDetail(
      "2026-06-30",
      "51603030006",
      "CNY",
    );
    const missing = await client.getLedgerPnlAccountDetail(
      "2026-06-30",
      "59999999999",
      "CNX",
    );

    expect(positive.result.period_comparison).toMatchObject({
      current_monthly_pnl: { yuan: "337860000", yi: "3.38" },
      previous_monthly_pnl: { yuan: "216270000", yi: "2.16" },
      change: { yuan: "121590000", yi: "1.22" },
    });
    expect(missing.result).toMatchObject({
      report_date: "2026-06-30",
      currency_basis: "CNX",
      analysis_status: "no_data",
      account: { account_code: "59999999999", account_name: null },
      period_comparison: {
        status: "current_account_no_data",
        previous_report_date: "2026-05-31",
        previous_source_version: "sv_product_category_3353b116b9a6",
        current_monthly_pnl: null,
        previous_monthly_pnl: null,
        change: null,
        current_evidence_rows: 0,
        previous_evidence_rows: 0,
      },
      canonical_evidence_rows: [],
    });
    expect(missing.result.basis_comparison.previous).toEqual({
      report_date: "2026-05-31",
      source_version: "sv_product_category_3353b116b9a6",
      cnx: null,
      cny: null,
      cnx_minus_cny: null,
      availability: { CNX: "no_data", CNY: "no_data" },
      evidence_rows: { CNX: 0, CNY: 0 },
    });
    expect(missing.result_meta.evidence_rows).toBe(0);
  });

  it("routes the real account detail read with encoded account and trimmed currency", async () => {
    const fetchImpl = vi.fn(async () =>
      new Response(JSON.stringify({ result_meta: {}, result: {} }), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }),
    ) as unknown as typeof fetch;
    const client = createApiClient({
      mode: "real",
      baseUrl: "http://backend.local",
      fetchImpl,
    });

    await client.getLedgerPnlAccountDetail("2026 06/30", "55 000/1", " CNY ");

    expect(fetchImpl).toHaveBeenCalledWith(
      "http://backend.local/api/ledger-pnl/account-detail?date=2026+06%2F30&account_code=55+000%2F1&currency=CNY",
      expect.objectContaining({ headers: expect.objectContaining({ Accept: "application/json" }) }),
    );
  });

  it("routes the real analysis read with encoded date and trimmed currency", async () => {
    const fetchImpl = vi.fn(async () =>
      new Response(JSON.stringify({ result_meta: {}, result: {} }), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }),
    ) as unknown as typeof fetch;
    const client = createApiClient({
      mode: "real",
      baseUrl: "http://backend.local",
      fetchImpl,
    });

    await client.getLedgerPnlAnalysis("2026 06/30", " CNX ");

    expect(fetchImpl).toHaveBeenCalledWith(
      "http://backend.local/api/ledger-pnl/analysis?date=2026+06%2F30&currency=CNX",
      expect.objectContaining({ headers: expect.objectContaining({ Accept: "application/json" }) }),
    );
  });

  it("omits the optional currency from the real analysis request", async () => {
    const fetchImpl = vi.fn(async () =>
      new Response(JSON.stringify({ result_meta: {}, result: {} }), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }),
    ) as unknown as typeof fetch;
    const client = createApiClient({
      mode: "real",
      baseUrl: "http://backend.local",
      fetchImpl,
    });

    await client.getLedgerPnlAnalysis(REPORT_DATE);

    expect(fetchImpl).toHaveBeenCalledWith(
      `http://backend.local/api/ledger-pnl/analysis?date=${REPORT_DATE}`,
      expect.objectContaining({ headers: expect.objectContaining({ Accept: "application/json" }) }),
    );
  });

  it("returns the complete synthetic 202606 candidate contract without eager lineage", async () => {
    const client = createApiClient({ mode: "mock" });

    const response = await client.getLedgerPnlCandidateFinancialIndicators("202606");

    expect(response.result).toMatchObject({
      report_month: "202606",
      report_date: "2026-06-30",
      currency: "CNX",
      basis: "ledger",
      metric_status: "candidate",
      formal_use_allowed: false,
      calculation_status: "warning",
      source_alignment: "not_applicable",
      requested_metric_id: null,
      include_lineage: false,
      summary: {
        metric_total: 186,
        metric_evaluated: 186,
        metric_returned: 186,
        ok_count: 134,
        warning_count: 33,
        manual_default_count: 19,
        error_count: 0,
        validation_total: 12,
        validation_evaluated: 12,
        validation_passed: 12,
        validation_warning_failed: 0,
        validation_error_failed: 0,
      },
    });
    expect(response.result.metrics).toHaveLength(186);
    expect(response.result.metrics.some((metric) => metric.metric_id.startsWith("candidate.metric."))).toBe(false);
    expect(response.result.metrics.map((metric) => metric.metric_id)).toEqual(
      expect.arrayContaining([
        "income.interest.net",
        "income.noninterest.total",
        "income.operating.mother_bank",
        "balance.deposit.corporate.total::point",
        "balance.deposit.retail.total::point",
        "balance.loan.corporate.total::point",
        "balance.loan.retail.total::point",
        "income.fee.company.investment_banking",
      ]),
    );
    expect(response.result.metrics.every((metric) => metric.lineage.length === 0)).toBe(true);
    expect(response.result.metrics.find(
      (metric) => metric.metric_id === "income.noninterest.total",
    )).toMatchObject({
      status: "warning",
      reasons: ["Synthetic demo dependency status propagated from rule topology."],
    });
    expect(response.result.sources).toEqual(
      expect.arrayContaining([
        expect.objectContaining({ source_kind: "ledger", locked_sha256: null, locked_hash_match: null }),
        expect.objectContaining({ source_kind: "daily", locked_sha256: null, locked_hash_match: null }),
      ]),
    );
    expect(response.result.sources.find((source) => source.source_kind === "ledger")).toMatchObject({
      file_name: "synthetic-ledger-202606.xlsx",
      sheets: ["DEMO-LEDGER"],
      periods: [
        {
          evidence_id: "ledger",
          start: "2026-06-01",
          end: "2026-06-30",
          source_cell: "DEMO:ledger:PERIOD",
        },
      ],
    });
    expect(response.result.sources.find((source) => source.source_kind === "daily")).toMatchObject({
      file_name: "synthetic-daily-202606.xlsx",
      sheets: ["DEMO-DAILY"],
      periods: [
        expect.objectContaining({ evidence_id: "daily_ytd", source_cell: "DEMO:daily_ytd:PERIOD" }),
        expect.objectContaining({ evidence_id: "daily_month", source_cell: "DEMO:daily_month:PERIOD" }),
        expect.objectContaining({ evidence_id: "microloan_ytd", source_cell: "DEMO:microloan_ytd:PERIOD" }),
        expect.objectContaining({ evidence_id: "microloan_month", source_cell: "DEMO:microloan_month:PERIOD" }),
        expect.objectContaining({ evidence_id: "microloan_ledger", source_cell: "DEMO:microloan_ledger:PERIOD" }),
      ],
    });
    expect(response.result.metrics.filter((metric) => metric.status === "manual_default").map(
      (metric) => metric.metric_id,
    )).toEqual([
      "input.adjustment.noninterest.r010",
      "input.adjustment.noninterest.r019",
      "input.adjustment.noninterest.r023",
      "input.adjustment.noninterest.r031",
      "input.adjustment.noninterest.r035",
      "input.adjustment.noninterest.r047",
      "input.adjustment.noninterest.r053",
      "input.adjustment.noninterest.r068",
      "input.adjustment.noninterest.r076",
      "input.adjustment.noninterest.r084",
      "input.adjustment.noninterest.r087",
      "input.adjustment.noninterest.r091",
      "input.adjustment.noninterest.r096",
      "input.adjustment.noninterest.r099",
      "input.adjustment.noninterest.r102",
      "input.adjustment.noninterest.r105",
      "input.adjustment.noninterest.r112",
      "input.adjustment.noninterest.r116",
      "input.adjustment.noninterest.r120",
    ]);
    expect(response.result_meta.requested_report_date).toBe("202606");
    expect(response.result_meta).toMatchObject({
      basis: "ledger",
      result_kind: "ledger_pnl.candidate_financial_indicators",
      formal_use_allowed: false,
      amount_currency_basis: "CNX",
      cache_key: response.result.idempotency_key,
      quality_flag: "warning",
      filters_applied: {
        report_month: "202606",
        include_lineage: false,
        metric_id: null,
      },
      evidence_rows: 186,
    });
    expect(response.result.validations).toHaveLength(12);
    expect(response.result.validations.every((validation) => validation.passed)).toBe(true);
    expect(response.result.gaps.map((gap) => gap.gap_id)).toEqual([
      "synthetic.source_unlocked",
      "synthetic.manual_defaults",
    ]);
    expect(response.result.promotion_readiness.evidence_pack.evidence_pack_key).toBe(
      "18c9c7e2f7652e7db1914559af42a40cced3b6fff312a9aa6450bfc5635604ec",
    );
  });

  it("returns only the requested candidate metric with lineage on demand", async () => {
    const client = createApiClient({ mode: "mock" });
    const baseResponse = await client.getLedgerPnlCandidateFinancialIndicators("202606");

    const response = await client.getLedgerPnlCandidateFinancialIndicators("202606", {
      includeLineage: true,
      metricId: "income.interest.net",
    });

    expect(response.result).toMatchObject({
      requested_metric_id: "income.interest.net",
      include_lineage: true,
      summary: { metric_total: 186, metric_evaluated: 186, metric_returned: 1 },
    });
    expect(response.result.metrics).toHaveLength(1);
    expect(response.result.metrics[0]).toMatchObject({
      metric_id: "income.interest.net",
      value: "184.6771",
    });
    expect(response.result.metrics[0].lineage).toEqual([
      expect.objectContaining({
        lineage_type: "metric",
        metric_id: "income.interest.loan.total",
        metric_value_yi: expect.any(String),
      }),
      expect.objectContaining({
        lineage_type: "metric",
        metric_id: "expense.interest.deposit.total",
        weight: "-1",
      }),
      expect.objectContaining({
        lineage_type: "metric",
        metric_id: "income.interest.investment",
      }),
      expect.objectContaining({
        lineage_type: "metric",
        metric_id: "income.interest.interbank_net",
      }),
    ]);
    expect(response.result.idempotency_key).not.toBe(baseResponse.result.idempotency_key);
    expect(response.result_meta.cache_key).toBe(response.result.idempotency_key);
  });

  it("keeps account drilldown synthetic while preserving governed metric ids", async () => {
    const client = createApiClient({ mode: "mock" });

    const response = await client.getLedgerPnlCandidateFinancialIndicators("202606", {
      includeLineage: true,
      metricId: "balance.deposit.corporate.total::point",
    });
    const accountLineage = response.result.metrics[0].lineage.filter(
      (row) => row.lineage_type === "account",
    );

    expect(accountLineage.length).toBeGreaterThan(0);
    expect(accountLineage).toEqual(expect.arrayContaining([
      expect.objectContaining({
        code: expect.stringMatching(/^99\d+$/),
        raw_yuan: expect.any(String),
        evidence_refs: [expect.stringMatching(/^DEMO:/)],
      }),
    ]));
  });

  it("rejects an unknown candidate metric id instead of returning an empty evaluated result", async () => {
    const client = createApiClient({ mode: "mock" });

    await expect(client.getLedgerPnlCandidateFinancialIndicators("202606", {
      metricId: "unknown.metric",
    })).rejects.toThrow("Unknown candidate financial indicator metric_id: unknown.metric");
  });

  it("rejects invalid months and unknown metrics before the no-data branch", async () => {
    const client = createApiClient({ mode: "mock" });

    await expect(client.getLedgerPnlCandidateFinancialIndicators("   ")).rejects.toThrow(
      "Invalid candidate financial indicator report_month",
    );
    await expect(client.getLedgerPnlCandidateFinancialIndicators("202613")).rejects.toThrow(
      "Invalid candidate financial indicator report_month",
    );
    await expect(client.getLedgerPnlCandidateFinancialIndicators("202607", {
      metricId: "unknown.metric",
    })).rejects.toThrow("Unknown candidate financial indicator metric_id: unknown.metric");
  });

  it("uses a stable request-specific idempotency key for no-data and lineage filters", async () => {
    const client = createApiClient({ mode: "mock" });

    const july = await client.getLedgerPnlCandidateFinancialIndicators("202607");
    const julyAgain = await client.getLedgerPnlCandidateFinancialIndicators("202607");
    const julyLineage = await client.getLedgerPnlCandidateFinancialIndicators("202607", {
      includeLineage: true,
      metricId: "income.interest.net",
    });

    expect(july.result.idempotency_key).toBe(julyAgain.result.idempotency_key);
    expect(july.result.idempotency_key).not.toBe(julyLineage.result.idempotency_key);
    expect(july.result.sources).toEqual([
      expect.objectContaining({ source_kind: "ledger", exists: false }),
      expect.objectContaining({ source_kind: "daily", exists: false }),
    ]);
    expect(july.result_meta.evidence_rows).toBe(0);
  });

  it("does not rename the frozen 202603 formal contract for unregistered months", async () => {
    const client = createApiClient({ mode: "mock" });

    const registered = await client.getLedgerPnlFormalFinancialIndicators("202603");
    const missing = await client.getLedgerPnlFormalFinancialIndicators("202606");

    expect(registered.result).toMatchObject({
      report_month: "202603",
      report_date: "2026-03-31",
      sample_status: "contract_fixture",
    });
    expect(missing.result).toMatchObject({
      report_month: "202606",
      report_date: "2026-06-30",
      sample_status: "missing_contract",
      formal_use_allowed: false,
      metrics: [],
    });
  });

  it("routes candidate financial indicator filters to the domain endpoint", async () => {
    const fetchImpl = vi.fn(async () =>
      new Response(JSON.stringify({ result_meta: {}, result: {} }), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }),
    ) as unknown as typeof fetch;
    const client = createApiClient({
      mode: "real",
      baseUrl: "http://backend.local",
      fetchImpl,
    });

    await client.getLedgerPnlCandidateFinancialIndicators(" 202606 ", {
      includeLineage: true,
      metricId: " income.interest.net ",
    });

    expect(fetchImpl).toHaveBeenCalledWith(
      "http://backend.local/api/ledger-pnl/candidate-financial-indicators?report_month=202606&include_lineage=true&metric_id=income.interest.net",
      expect.objectContaining({ headers: expect.objectContaining({ Accept: "application/json" }) }),
    );
  });
});
