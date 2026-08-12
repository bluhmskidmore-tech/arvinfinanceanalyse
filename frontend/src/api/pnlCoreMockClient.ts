/**
 * Demo/mock Formal+Ledger+Bridge PnL client.
 * Loaded only via mockApiClient / tests — keep out of real-mode client.ts imports.
 */
import { buildMockApiEnvelope } from "../mocks/mockApiEnvelope";
import type { MockLedgerPnlCurrencyBasis } from "../mocks/ledgerPnlMocks";
import { formatRawAsNumeric } from "../utils/format";
import type {
  LedgerPnlCandidateFinancialIndicatorsEnvelope,
  LedgerPnlCandidateFinancialIndicatorsPayload,
  NumericUnit,
} from "./contracts";
import type { PnlCoreClientMethods } from "./pnlCoreClient";

type Delay = () => Promise<void>;

// Heavy demo fixtures (incl. a ~266KB JSON) stay out of the real-mode bundle:
// the demo client loads them on demand instead of via a top-level import.
type LedgerPnlMocksModule = typeof import("../mocks/ledgerPnlMocks");
let ledgerPnlMocksPromise: Promise<LedgerPnlMocksModule> | null = null;

function loadLedgerPnlMocks(): Promise<LedgerPnlMocksModule> {
  ledgerPnlMocksPromise ??= import("../mocks/ledgerPnlMocks");
  return ledgerPnlMocksPromise;
}

function normalizeMockLedgerPnlCurrencyBasis(
  mocks: LedgerPnlMocksModule,
  currency?: string,
): MockLedgerPnlCurrencyBasis {
  const normalized = currency === undefined
    ? mocks.MOCK_LEDGER_PNL_DEFAULT_CURRENCY_BASIS
    : currency;
  if (normalized !== "CNX" && normalized !== "CNY") {
    throw new Error(`Unsupported ledger currency basis: ${JSON.stringify(currency)}. Expected CNX or CNY.`);
  }
  return normalized;
}

function buildMockCandidateFinancialIndicatorsEnvelope(
  mocks: LedgerPnlMocksModule,
  payload: LedgerPnlCandidateFinancialIndicatorsPayload,
): LedgerPnlCandidateFinancialIndicatorsEnvelope {
  const qualityFlag = payload.calculation_status === "ready"
    ? "ok"
    : payload.calculation_status === "error"
      ? "error"
      : "warning";
  return {
    result_meta: {
      ...mocks.MOCK_LEDGER_PNL_CANDIDATE_CAPTURE_META,
      basis: "ledger",
      result_kind: "ledger_pnl.candidate_financial_indicators",
      formal_use_allowed: false,
      amount_currency_basis: "CNX",
      trace_id: `mock_candidate_financial_indicators_${payload.report_month}_${payload.idempotency_key.slice(0, 12)}`,
      source_version: payload.source_version,
      rule_version: payload.rule_version,
      cache_key: payload.idempotency_key,
      quality_flag: qualityFlag,
      requested_report_date: payload.report_month,
      resolved_report_date: payload.report_date,
      as_of_date: payload.report_date,
      filters_applied: {
        report_month: payload.report_month,
        include_lineage: payload.include_lineage,
        metric_id: payload.requested_metric_id,
      },
      tables_used: payload.calculation_status === "no_data"
        ? []
        : Array.from(new Set(payload.sources.flatMap((source) => source.sheets))),
      evidence_rows: payload.calculation_status === "no_data"
        ? 0
        : mocks.MOCK_LEDGER_PNL_CANDIDATE_CAPTURE_META.evidence_rows,
    },
    result: payload,
  };
}

export function createDemoPnlCoreClient(delay: Delay): PnlCoreClientMethods {
  return {
    async getFormalPnlDates(basis = "formal") {
      await delay();
      return buildMockApiEnvelope(
        "pnl.dates",
        {
          report_dates: [],
          formal_fi_report_dates: [],
          nonstd_bridge_report_dates: [],
        },
        { basis, formal_use_allowed: basis === "formal" },
      );
    },
    async getFormalPnlData(date: string, basis = "formal") {
      await delay();
      return buildMockApiEnvelope(
        "pnl.data",
        {
          report_date: date,
          formal_fi_rows: [],
          nonstd_bridge_rows: [],
        },
        { basis, formal_use_allowed: basis === "formal" },
      );
    },
    async getFormalPnlOverview(reportDate: string, basis = "formal") {
      await delay();
      return buildMockApiEnvelope(
        "pnl.overview",
        {
          report_date: reportDate,
          formal_fi_row_count: 0,
          nonstd_bridge_row_count: 0,
          interest_income_514: "0.00",
          fair_value_change_516: "0.00",
          capital_gain_517: "0.00",
          manual_adjustment: "0.00",
          total_pnl: "0.00",
        },
        { basis, formal_use_allowed: basis === "formal" },
      );
    },
    async getLedgerPnlDates() {
      const mocks = await loadLedgerPnlMocks();
      await delay();
      return buildMockApiEnvelope("ledger_pnl.dates", mocks.mockLedgerPnlDates, {
        basis: "ledger",
        formal_use_allowed: false,
        source_version: mocks.mockLedgerPnlSummaryByBasis.CNX.source_version,
        rule_version: mocks.MOCK_LEDGER_PNL_RULE_VERSION,
        cache_version: mocks.MOCK_LEDGER_PNL_CACHE_VERSION,
        filters_applied: {},
        tables_used: mocks.MOCK_LEDGER_PNL_TABLES_USED,
        evidence_rows: mocks.mockLedgerPnlDates.dates.length,
      });
    },
    async getLedgerPnlData(reportDate: string, currency?: string) {
      const mocks = await loadLedgerPnlMocks();
      const currencyBasis = normalizeMockLedgerPnlCurrencyBasis(mocks, currency);
      await delay();
      const snapshot = mocks.getMockLedgerPnlSnapshot(reportDate, currencyBasis);
      return buildMockApiEnvelope(
        "ledger_pnl.data",
        snapshot.data,
        {
          basis: "ledger",
          formal_use_allowed: false,
          source_version: snapshot.source_version,
          rule_version: mocks.MOCK_LEDGER_PNL_RULE_VERSION,
          cache_version: mocks.MOCK_LEDGER_PNL_CACHE_VERSION,
          quality_flag: snapshot.quality_flag,
          requested_report_date: reportDate,
          resolved_report_date: reportDate,
          as_of_date: reportDate,
          date_basis: "ledger_report_date",
          filters_applied: {
            report_date: reportDate,
            currency: currencyBasis,
            currency_basis: currencyBasis,
            currency_basis_note: mocks.MOCK_LEDGER_PNL_CURRENCY_BASIS_NOTE,
          },
          tables_used: mocks.MOCK_LEDGER_PNL_TABLES_USED,
          evidence_rows: snapshot.evidence_rows.data,
        },
      );
    },
    async getLedgerPnlSummary(reportDate: string, currency?: string) {
      const mocks = await loadLedgerPnlMocks();
      const currencyBasis = normalizeMockLedgerPnlCurrencyBasis(mocks, currency);
      await delay();
      const snapshot = mocks.getMockLedgerPnlSnapshot(reportDate, currencyBasis);
      return buildMockApiEnvelope(
        "ledger_pnl.summary",
        snapshot.summary,
        {
          basis: "ledger",
          formal_use_allowed: false,
          source_version: snapshot.source_version,
          rule_version: mocks.MOCK_LEDGER_PNL_RULE_VERSION,
          cache_version: mocks.MOCK_LEDGER_PNL_CACHE_VERSION,
          quality_flag: snapshot.quality_flag,
          requested_report_date: reportDate,
          resolved_report_date: reportDate,
          as_of_date: reportDate,
          date_basis: "ledger_report_date",
          filters_applied: {
            report_date: reportDate,
            currency: currencyBasis,
            currency_basis: currencyBasis,
            currency_basis_note: mocks.MOCK_LEDGER_PNL_CURRENCY_BASIS_NOTE,
          },
          tables_used: mocks.MOCK_LEDGER_PNL_TABLES_USED,
          evidence_rows: snapshot.evidence_rows.summary,
        },
      );
    },
    async getLedgerPnlAnalysis(reportDate: string, currency?: string) {
      const mocks = await loadLedgerPnlMocks();
      const currencyBasis = normalizeMockLedgerPnlCurrencyBasis(mocks, currency);
      await delay();
      const snapshot = mocks.getMockLedgerPnlSnapshot(reportDate, currencyBasis);
      const payload = snapshot.analysis;
      const evidenceRows = payload.basis_comparison
        .find((row) => row.metric_key === "all_pnl")
        ?.evidence_rows[currencyBasis] ?? 0;
      return buildMockApiEnvelope(
        "ledger_pnl.analysis",
        payload,
        {
          basis: "ledger",
          formal_use_allowed: false,
          source_version: payload.source_version,
          rule_version: mocks.MOCK_LEDGER_PNL_ANALYSIS_RULE_VERSION,
          cache_version: mocks.MOCK_LEDGER_PNL_ANALYSIS_CACHE_VERSION,
          quality_flag: snapshot.quality_flag,
          requested_report_date: reportDate,
          resolved_report_date: reportDate,
          as_of_date: reportDate,
          date_basis: "ledger_report_date",
          filters_applied: {
            report_date: reportDate,
            currency: currencyBasis,
            currency_basis: currencyBasis,
            currency_basis_note: mocks.MOCK_LEDGER_PNL_CURRENCY_BASIS_NOTE,
          },
          tables_used: mocks.MOCK_LEDGER_PNL_TABLES_USED,
          evidence_rows: evidenceRows,
        },
      );
    },
    async getLedgerPnlAccountDetail(
      reportDate: string,
      accountCode: string,
      currency?: string,
    ) {
      const mocks = await loadLedgerPnlMocks();
      const currencyBasis = normalizeMockLedgerPnlCurrencyBasis(mocks, currency);
      await delay();
      const payload = mocks.getMockLedgerPnlAccountDetail(
        reportDate,
        accountCode,
        currencyBasis,
      );
      const evidenceRows = payload.basis_comparison.current.evidence_rows[currencyBasis];
      return buildMockApiEnvelope(
        "ledger_pnl.account_detail",
        payload,
        {
          basis: "ledger",
          formal_use_allowed: false,
          source_version: payload.source_version,
          rule_version: mocks.MOCK_LEDGER_PNL_ACCOUNT_DETAIL_RULE_VERSION,
          cache_version: mocks.MOCK_LEDGER_PNL_ACCOUNT_DETAIL_CACHE_VERSION,
          quality_flag: payload.analysis_status === "ready" ? "ok" : "warning",
          requested_report_date: reportDate,
          resolved_report_date: reportDate,
          as_of_date: reportDate,
          date_basis: "ledger_report_date",
          filters_applied: {
            report_date: reportDate,
            account_code: accountCode.trim(),
            currency: currencyBasis,
            currency_basis: currencyBasis,
            currency_basis_note: mocks.MOCK_LEDGER_PNL_CURRENCY_BASIS_NOTE,
          },
          tables_used: mocks.MOCK_LEDGER_PNL_TABLES_USED,
          evidence_rows: evidenceRows,
        },
      );
    },
    async getLedgerPnlFormalFinancialIndicators(reportMonth: string) {
      const mocks = await loadLedgerPnlMocks();
      await delay();
      const payload = mocks.getMockLedgerPnlFormalFinancialIndicators(reportMonth);
      return buildMockApiEnvelope(
        "ledger_pnl.formal_financial_indicator_source_contract",
        payload,
        {
          basis: "ledger",
          formal_use_allowed: false,
          source_version: payload.source_version,
          rule_version: payload.rule_version,
          cache_version: "cv_ledger_pnl_financial_indicator_contract_v1",
          quality_flag: "warning",
          as_of_date: payload.report_date,
          date_basis: "report_month_end",
          evidence_rows: payload.metrics.length,
        },
      );
    },
    async getLedgerPnlFinancialIndicatorSummary(reportMonth: string, currency?: string) {
      const mocks = await loadLedgerPnlMocks();
      await delay();
      const currencyBasis = normalizeMockLedgerPnlCurrencyBasis(mocks, currency);
      const payload = mocks.buildMockLedgerPnlFinancialIndicatorSummary(
        reportMonth,
        currencyBasis,
      );
      return buildMockApiEnvelope(
        "ledger_pnl.financial_indicator_summary",
        payload,
        {
          basis: "ledger",
          formal_use_allowed: false,
          source_version: payload.source_files[0]?.source_version ?? "sv_ledger_pnl_mock",
          rule_version: mocks.MOCK_LEDGER_PNL_INDICATOR_SUMMARY_RULE_VERSION,
          cache_version: mocks.MOCK_LEDGER_PNL_INDICATOR_SUMMARY_CACHE_VERSION,
          quality_flag: payload.data_status === "ready" ? "ok" : "warning",
          date_basis: "ledger_report_month",
          filters_applied: {
            report_month: payload.report_month,
            currency: currencyBasis,
            currency_basis: currencyBasis,
            currency_basis_note: mocks.MOCK_LEDGER_PNL_CURRENCY_BASIS_NOTE,
          },
          tables_used: ["qdb_gl_ledger_reconciliation_workbook"],
          evidence_rows: payload.data_status === "ready" ? payload.coverage.row_computed : 0,
        },
      );
    },
    async getLedgerPnlCandidateFinancialIndicators(reportMonth, options = {}) {
      const mocks = await loadLedgerPnlMocks();
      await delay();
      const payload = await mocks.buildMockLedgerPnlCandidateFinancialIndicators(reportMonth, options);
      return buildMockCandidateFinancialIndicatorsEnvelope(mocks, payload);
    },
    async getLedgerPnlCandidateFinancialIndicatorPeriodComparison(reportMonth) {
      const mocks = await loadLedgerPnlMocks();
      await delay();
      return mocks.buildMockLedgerPnlCandidateFinancialIndicatorPeriodComparison(reportMonth);
    },
    async getLedgerPnlCandidateFinancialIndicatorComponentDetail(
      reportMonth,
      metricId,
      parentIdempotencyKey,
    ) {
      const mocks = await loadLedgerPnlMocks();
      await delay();
      return mocks.buildMockLedgerPnlCandidateFinancialIndicatorComponentDetail(
        reportMonth,
        metricId,
        parentIdempotencyKey,
      );
    },
    async revalidateLedgerPnlCandidateFinancialIndicators() {
      await delay();
      throw new Error("Candidate revalidation dry-run requires the real API client.");
    },
    async getLedgerPnlFormalIndicatorRuleChecks(reportMonth: string) {
      const mocks = await loadLedgerPnlMocks();
      await delay();
      const payload = mocks.buildMockLedgerPnlFormalIndicatorRuleChecks(reportMonth);
      const evidenceRows =
        payload.ratio_recomputation.length +
        payload.additivity_checks.length +
        payload.arrangement_rules.length;
      return buildMockApiEnvelope("ledger_pnl.formal_financial_indicator_rule_checks", payload, {
        basis: "ledger",
        formal_use_allowed: false,
        source_version: payload.source_version,
        rule_version: payload.rule_version,
        cache_version: "cv_ledger_pnl_financial_indicator_rule_checks_v1",
        quality_flag: payload.sample_status === "missing_contract" ? "warning" : "ok",
        as_of_date: payload.report_date,
        date_basis: "report_month_end",
        evidence_rows: evidenceRows,
      });
    },
    async getLedgerPnlMonthlyAnalysisDates() {
      await delay();
      return buildMockApiEnvelope(
        "qdb-gl-monthly-analysis.dates",
        { report_months: [] },
        {
          basis: "analytical",
          formal_use_allowed: false,
          source_version: "sv_qdb_gl_mock",
          rule_version: "rv_qdb_gl_monthly_analysis_v1",
          cache_version: "cv_qdb_gl_monthly_analysis_v1",
        },
      );
    },
    async getLedgerPnlMonthlyAnalysisWorkbook({ reportMonth }) {
      await delay();
      return buildMockApiEnvelope(
        "qdb-gl-monthly-analysis.workbook",
        { report_month: reportMonth, sheets: [] },
        {
          basis: "analytical",
          formal_use_allowed: false,
          source_version: "sv_qdb_gl_mock",
          rule_version: "rv_qdb_gl_monthly_analysis_v1",
          cache_version: "cv_qdb_gl_monthly_analysis_v1",
        },
      );
    },
    async getPnlBridge(reportDate: string) {
      await delay();
      const z = (unit: NumericUnit, sign_aware: boolean) =>
        formatRawAsNumeric({ raw: 0, unit, sign_aware });
      return buildMockApiEnvelope(
        "pnl.bridge",
        {
          report_date: reportDate,
          rows: [],
          summary: {
            row_count: 0,
            ok_count: 0,
            warning_count: 0,
            error_count: 0,
            total_beginning_dirty_mv: z("yuan", false),
            total_ending_dirty_mv: z("yuan", false),
            total_carry: z("yuan", true),
            total_roll_down: z("yuan", true),
            total_treasury_curve: z("yuan", true),
            total_credit_spread: z("yuan", true),
            total_fx_translation: z("yuan", true),
            total_realized_trading: z("yuan", true),
            total_unrealized_fv: z("yuan", true),
            total_manual_adjustment: z("yuan", true),
            total_explained_pnl: z("yuan", true),
            total_actual_pnl: z("yuan", true),
            total_residual: z("yuan", true),
            quality_flag: "ok",
          },
          warnings: [],
        },
        { basis: "formal", formal_use_allowed: true },
      );
    },
    async refreshFormalPnl(reportDate?: string) {
      await delay();
      return {
        status: "queued",
        run_id: "pnl_materialize:mock-run",
        job_name: "pnl_materialize",
        trigger_mode: "async",
        cache_key: "pnl:phase2:materialize:formal",
        report_date: reportDate ?? "2026-02-28",
      };
    },
    async getFormalPnlImportStatus(runId?: string) {
      await delay();
      return {
        status: runId ? "completed" : "idle",
        run_id: runId ?? "pnl_materialize:mock-run",
        job_name: "pnl_materialize",
        trigger_mode: runId ? "terminal" : "idle",
        cache_key: "pnl:phase2:materialize:formal",
        report_date: "2026-02-28",
        source_version: "sv_mock_dashboard_v2",
      };
    },
  };
}
