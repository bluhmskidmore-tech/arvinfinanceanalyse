/**
 * Formal, Ledger, and Bridge P&L client slice.
 * Imported by client.ts for ApiClient composition.
 */
import { buildMockApiEnvelope } from "../mocks/mockApiEnvelope";
import {
  buildMockLedgerPnlCandidateFinancialIndicators,
  buildMockLedgerPnlCandidateFinancialIndicatorComponentDetail,
  buildMockLedgerPnlCandidateFinancialIndicatorPeriodComparison,
  buildMockLedgerPnlFormalIndicatorRuleChecks,
  getMockLedgerPnlFormalFinancialIndicators,
  getMockLedgerPnlAccountDetail,
  getMockLedgerPnlSnapshot,
  MOCK_LEDGER_PNL_ACCOUNT_DETAIL_CACHE_VERSION,
  MOCK_LEDGER_PNL_ACCOUNT_DETAIL_RULE_VERSION,
  MOCK_LEDGER_PNL_ANALYSIS_CACHE_VERSION,
  MOCK_LEDGER_PNL_ANALYSIS_RULE_VERSION,
  MOCK_LEDGER_PNL_CACHE_VERSION,
  MOCK_LEDGER_PNL_CANDIDATE_CAPTURE_META,
  MOCK_LEDGER_PNL_CURRENCY_BASIS_NOTE,
  MOCK_LEDGER_PNL_DEFAULT_CURRENCY_BASIS,
  MOCK_LEDGER_PNL_RULE_VERSION,
  MOCK_LEDGER_PNL_TABLES_USED,
  mockLedgerPnlDates,
  mockLedgerPnlSummaryByBasis,
  type MockLedgerPnlCurrencyBasis,
} from "../mocks/ledgerPnlMocks";
import { formatRawAsNumeric } from "../utils/format";
import type {
  ApiEnvelope,
  FormalPnlRefreshPayload,
  LedgerPnlAccountDetailPayload,
  LedgerPnlDataPayload,
  LedgerPnlDatesPayload,
  LedgerPnlAnalysisPayload,
  LedgerPnlCandidateFinancialIndicatorsPayload,
  LedgerPnlCandidateFinancialIndicatorsEnvelope,
  LedgerPnlCandidateFinancialIndicatorComponentDetail,
  LedgerPnlCandidateFinancialIndicatorComponentMetricId,
  LedgerPnlCandidateFinancialIndicatorPeriodComparison,
  LedgerPnlCandidateFinancialIndicatorRevalidationReceipt,
  LedgerPnlCandidateFinancialIndicatorRevalidationRequest,
  LedgerPnlFormalFinancialIndicatorContractPayload,
  LedgerPnlFormalIndicatorRuleChecksPayload,
  LedgerPnlSummaryPayload,
  NumericUnit,
  PnlBasis,
  PnlBridgePayload,
  PnlDataPayload,
  PnlDatesPayload,
  PnlOverviewPayload,
  QdbGlMonthlyAnalysisDatesPayload,
  QdbGlMonthlyAnalysisWorkbookPayload,
} from "./contracts";

export type PnlCoreClientMethods = {
  getFormalPnlDates: (basis?: PnlBasis) => Promise<ApiEnvelope<PnlDatesPayload>>;
  getFormalPnlData: (date: string, basis?: PnlBasis) => Promise<ApiEnvelope<PnlDataPayload>>;
  getFormalPnlOverview: (
    reportDate: string,
    basis?: PnlBasis,
  ) => Promise<ApiEnvelope<PnlOverviewPayload>>;
  getLedgerPnlDates: () => Promise<ApiEnvelope<LedgerPnlDatesPayload>>;
  getLedgerPnlData: (
    reportDate: string,
    currency?: string,
  ) => Promise<ApiEnvelope<LedgerPnlDataPayload>>;
  getLedgerPnlSummary: (
    reportDate: string,
    currency?: string,
  ) => Promise<ApiEnvelope<LedgerPnlSummaryPayload>>;
  getLedgerPnlAnalysis: (
    reportDate: string,
    currency?: string,
  ) => Promise<ApiEnvelope<LedgerPnlAnalysisPayload>>;
  getLedgerPnlAccountDetail: (
    reportDate: string,
    accountCode: string,
    currency?: string,
  ) => Promise<ApiEnvelope<LedgerPnlAccountDetailPayload>>;
  getLedgerPnlFormalFinancialIndicators: (
    reportMonth: string,
  ) => Promise<ApiEnvelope<LedgerPnlFormalFinancialIndicatorContractPayload>>;
  getLedgerPnlCandidateFinancialIndicators: (
    reportMonth: string,
    options?: { includeLineage?: boolean; metricId?: string },
  ) => Promise<LedgerPnlCandidateFinancialIndicatorsEnvelope>;
  getLedgerPnlCandidateFinancialIndicatorPeriodComparison: (
    reportMonth: string,
    options?: { signal?: AbortSignal },
  ) => Promise<LedgerPnlCandidateFinancialIndicatorPeriodComparison>;
  getLedgerPnlCandidateFinancialIndicatorComponentDetail: (
    reportMonth: string,
    metricId: LedgerPnlCandidateFinancialIndicatorComponentMetricId,
    parentIdempotencyKey: string,
    options?: { signal?: AbortSignal },
  ) => Promise<LedgerPnlCandidateFinancialIndicatorComponentDetail>;
  revalidateLedgerPnlCandidateFinancialIndicators: (
    reportMonth: string,
    request: LedgerPnlCandidateFinancialIndicatorRevalidationRequest,
  ) => Promise<LedgerPnlCandidateFinancialIndicatorRevalidationReceipt>;
  getLedgerPnlFormalIndicatorRuleChecks: (
    reportMonth: string,
  ) => Promise<ApiEnvelope<LedgerPnlFormalIndicatorRuleChecksPayload>>;
  getLedgerPnlMonthlyAnalysisDates: () => Promise<ApiEnvelope<QdbGlMonthlyAnalysisDatesPayload>>;
  getLedgerPnlMonthlyAnalysisWorkbook: (options: {
    reportMonth: string;
  }) => Promise<ApiEnvelope<QdbGlMonthlyAnalysisWorkbookPayload>>;
  getPnlBridge: (reportDate: string) => Promise<ApiEnvelope<PnlBridgePayload>>;
  refreshFormalPnl: (reportDate?: string) => Promise<FormalPnlRefreshPayload>;
  getFormalPnlImportStatus: (runId?: string) => Promise<FormalPnlRefreshPayload>;
};

type FetchLike = typeof fetch;
type Delay = () => Promise<void>;

type RequestJson = <T>(
  fetchImpl: FetchLike,
  baseUrl: string,
  path: string,
) => Promise<ApiEnvelope<T>>;

type RequestActionJson = <T>(
  fetchImpl: FetchLike,
  baseUrl: string,
  path: string,
  init?: RequestInit,
) => Promise<T>;

export type PnlCoreClientFactoryOptions = {
  fetchImpl: FetchLike;
  baseUrl: string;
  requestJson: RequestJson;
  requestActionJson: RequestActionJson;
};

function buildPnlBasisQuerySegment(basis?: PnlBasis) {
  return basis && basis !== "formal" ? `&basis=${encodeURIComponent(basis)}` : "";
}

function normalizeMockLedgerPnlCurrencyBasis(currency?: string): MockLedgerPnlCurrencyBasis {
  const normalized = currency === undefined
    ? MOCK_LEDGER_PNL_DEFAULT_CURRENCY_BASIS
    : currency;
  if (normalized !== "CNX" && normalized !== "CNY") {
    throw new Error(`Unsupported ledger currency basis: ${JSON.stringify(currency)}. Expected CNX or CNY.`);
  }
  return normalized;
}

function buildMockCandidateFinancialIndicatorsEnvelope(
  payload: LedgerPnlCandidateFinancialIndicatorsPayload,
): LedgerPnlCandidateFinancialIndicatorsEnvelope {
  const qualityFlag = payload.calculation_status === "ready"
    ? "ok"
    : payload.calculation_status === "error"
      ? "error"
      : "warning";
  return {
    result_meta: {
      ...MOCK_LEDGER_PNL_CANDIDATE_CAPTURE_META,
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
        : MOCK_LEDGER_PNL_CANDIDATE_CAPTURE_META.evidence_rows,
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
      await delay();
      return buildMockApiEnvelope("ledger_pnl.dates", mockLedgerPnlDates, {
        basis: "ledger",
        formal_use_allowed: false,
        source_version: mockLedgerPnlSummaryByBasis.CNX.source_version,
        rule_version: MOCK_LEDGER_PNL_RULE_VERSION,
        cache_version: MOCK_LEDGER_PNL_CACHE_VERSION,
        filters_applied: {},
        tables_used: MOCK_LEDGER_PNL_TABLES_USED,
        evidence_rows: mockLedgerPnlDates.dates.length,
      });
    },
    async getLedgerPnlData(reportDate: string, currency?: string) {
      const currencyBasis = normalizeMockLedgerPnlCurrencyBasis(currency);
      await delay();
      const snapshot = getMockLedgerPnlSnapshot(reportDate, currencyBasis);
      return buildMockApiEnvelope(
        "ledger_pnl.data",
        snapshot.data,
        {
          basis: "ledger",
          formal_use_allowed: false,
          source_version: snapshot.source_version,
          rule_version: MOCK_LEDGER_PNL_RULE_VERSION,
          cache_version: MOCK_LEDGER_PNL_CACHE_VERSION,
          quality_flag: snapshot.quality_flag,
          requested_report_date: reportDate,
          resolved_report_date: reportDate,
          as_of_date: reportDate,
          date_basis: "ledger_report_date",
          filters_applied: {
            report_date: reportDate,
            currency: currencyBasis,
            currency_basis: currencyBasis,
            currency_basis_note: MOCK_LEDGER_PNL_CURRENCY_BASIS_NOTE,
          },
          tables_used: MOCK_LEDGER_PNL_TABLES_USED,
          evidence_rows: snapshot.evidence_rows.data,
        },
      );
    },
    async getLedgerPnlSummary(reportDate: string, currency?: string) {
      const currencyBasis = normalizeMockLedgerPnlCurrencyBasis(currency);
      await delay();
      const snapshot = getMockLedgerPnlSnapshot(reportDate, currencyBasis);
      return buildMockApiEnvelope(
        "ledger_pnl.summary",
        snapshot.summary,
        {
          basis: "ledger",
          formal_use_allowed: false,
          source_version: snapshot.source_version,
          rule_version: MOCK_LEDGER_PNL_RULE_VERSION,
          cache_version: MOCK_LEDGER_PNL_CACHE_VERSION,
          quality_flag: snapshot.quality_flag,
          requested_report_date: reportDate,
          resolved_report_date: reportDate,
          as_of_date: reportDate,
          date_basis: "ledger_report_date",
          filters_applied: {
            report_date: reportDate,
            currency: currencyBasis,
            currency_basis: currencyBasis,
            currency_basis_note: MOCK_LEDGER_PNL_CURRENCY_BASIS_NOTE,
          },
          tables_used: MOCK_LEDGER_PNL_TABLES_USED,
          evidence_rows: snapshot.evidence_rows.summary,
        },
      );
    },
    async getLedgerPnlAnalysis(reportDate: string, currency?: string) {
      const currencyBasis = normalizeMockLedgerPnlCurrencyBasis(currency);
      await delay();
      const snapshot = getMockLedgerPnlSnapshot(reportDate, currencyBasis);
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
          rule_version: MOCK_LEDGER_PNL_ANALYSIS_RULE_VERSION,
          cache_version: MOCK_LEDGER_PNL_ANALYSIS_CACHE_VERSION,
          quality_flag: snapshot.quality_flag,
          requested_report_date: reportDate,
          resolved_report_date: reportDate,
          as_of_date: reportDate,
          date_basis: "ledger_report_date",
          filters_applied: {
            report_date: reportDate,
            currency: currencyBasis,
            currency_basis: currencyBasis,
            currency_basis_note: MOCK_LEDGER_PNL_CURRENCY_BASIS_NOTE,
          },
          tables_used: MOCK_LEDGER_PNL_TABLES_USED,
          evidence_rows: evidenceRows,
        },
      );
    },
    async getLedgerPnlAccountDetail(
      reportDate: string,
      accountCode: string,
      currency?: string,
    ) {
      const currencyBasis = normalizeMockLedgerPnlCurrencyBasis(currency);
      await delay();
      const payload = getMockLedgerPnlAccountDetail(
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
          rule_version: MOCK_LEDGER_PNL_ACCOUNT_DETAIL_RULE_VERSION,
          cache_version: MOCK_LEDGER_PNL_ACCOUNT_DETAIL_CACHE_VERSION,
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
            currency_basis_note: MOCK_LEDGER_PNL_CURRENCY_BASIS_NOTE,
          },
          tables_used: MOCK_LEDGER_PNL_TABLES_USED,
          evidence_rows: evidenceRows,
        },
      );
    },
    async getLedgerPnlFormalFinancialIndicators(reportMonth: string) {
      await delay();
      const payload = getMockLedgerPnlFormalFinancialIndicators(reportMonth);
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
    async getLedgerPnlCandidateFinancialIndicators(reportMonth, options = {}) {
      await delay();
      const payload = await buildMockLedgerPnlCandidateFinancialIndicators(reportMonth, options);
      return buildMockCandidateFinancialIndicatorsEnvelope(payload);
    },
    async getLedgerPnlCandidateFinancialIndicatorPeriodComparison(reportMonth) {
      await delay();
      return buildMockLedgerPnlCandidateFinancialIndicatorPeriodComparison(reportMonth);
    },
    async getLedgerPnlCandidateFinancialIndicatorComponentDetail(
      reportMonth,
      metricId,
      parentIdempotencyKey,
    ) {
      await delay();
      return buildMockLedgerPnlCandidateFinancialIndicatorComponentDetail(
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
      await delay();
      const payload = buildMockLedgerPnlFormalIndicatorRuleChecks(reportMonth);
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

export function createRealPnlCoreClient(
  options: PnlCoreClientFactoryOptions,
): PnlCoreClientMethods {
  const { fetchImpl, baseUrl, requestJson, requestActionJson } = options;

  return {
    getFormalPnlDates: (basis = "formal") =>
      requestJson<PnlDatesPayload>(
        fetchImpl,
        baseUrl,
        `/api/pnl/dates${basis !== "formal" ? `?basis=${encodeURIComponent(basis)}` : ""}`,
      ),
    getFormalPnlData: (date: string, basis = "formal") =>
      requestJson<PnlDataPayload>(
        fetchImpl,
        baseUrl,
        `/api/pnl/data?date=${encodeURIComponent(date)}${buildPnlBasisQuerySegment(basis)}`,
      ),
    getFormalPnlOverview: (reportDate: string, basis = "formal") =>
      requestJson<PnlOverviewPayload>(
        fetchImpl,
        baseUrl,
        `/api/pnl/overview?report_date=${encodeURIComponent(reportDate)}${buildPnlBasisQuerySegment(basis)}`,
      ),
    getLedgerPnlDates: () =>
      requestJson<LedgerPnlDatesPayload>(fetchImpl, baseUrl, "/api/ledger-pnl/dates"),
    getLedgerPnlData: (reportDate: string, currency?: string) => {
      const params = new URLSearchParams({
        date: reportDate,
      });
      if (currency?.trim()) {
        params.set("currency", currency.trim());
      }
      return requestJson<LedgerPnlDataPayload>(
        fetchImpl,
        baseUrl,
        `/api/ledger-pnl/data?${params.toString()}`,
      );
    },
    getLedgerPnlSummary: (reportDate: string, currency?: string) => {
      const params = new URLSearchParams({
        date: reportDate,
      });
      if (currency?.trim()) {
        params.set("currency", currency.trim());
      }
      return requestJson<LedgerPnlSummaryPayload>(
        fetchImpl,
        baseUrl,
        `/api/ledger-pnl/summary?${params.toString()}`,
      );
    },
    getLedgerPnlAnalysis: (reportDate: string, currency?: string) => {
      const params = new URLSearchParams({
        date: reportDate,
      });
      if (currency?.trim()) {
        params.set("currency", currency.trim());
      }
      return requestJson<LedgerPnlAnalysisPayload>(
        fetchImpl,
        baseUrl,
        `/api/ledger-pnl/analysis?${params.toString()}`,
      );
    },
    getLedgerPnlAccountDetail: (
      reportDate: string,
      accountCode: string,
      currency?: string,
    ) => {
      const params = new URLSearchParams({
        date: reportDate,
        account_code: accountCode,
      });
      if (currency?.trim()) {
        params.set("currency", currency.trim());
      }
      return requestJson<LedgerPnlAccountDetailPayload>(
        fetchImpl,
        baseUrl,
        `/api/ledger-pnl/account-detail?${params.toString()}`,
      );
    },
    getLedgerPnlFormalFinancialIndicators: (reportMonth: string) => {
      const params = new URLSearchParams({
        report_month: reportMonth.trim(),
      });
      return requestJson<LedgerPnlFormalFinancialIndicatorContractPayload>(
        fetchImpl,
        baseUrl,
        `/api/ledger-pnl/formal-financial-indicators?${params.toString()}`,
      );
    },
    getLedgerPnlCandidateFinancialIndicators: (reportMonth, options = {}) => {
      const params = new URLSearchParams({
        report_month: reportMonth.trim(),
      });
      if (options.includeLineage) {
        params.set("include_lineage", "true");
      }
      if (options.metricId?.trim()) {
        params.set("metric_id", options.metricId.trim());
      }
      return requestJson<LedgerPnlCandidateFinancialIndicatorsPayload>(
        fetchImpl,
        baseUrl,
        `/api/ledger-pnl/candidate-financial-indicators?${params.toString()}`,
      ) as Promise<LedgerPnlCandidateFinancialIndicatorsEnvelope>;
    },
    getLedgerPnlCandidateFinancialIndicatorPeriodComparison: (reportMonth, options = {}) =>
      requestActionJson<LedgerPnlCandidateFinancialIndicatorPeriodComparison>(
        fetchImpl,
        baseUrl,
        `/api/ledger-pnl/candidate-financial-indicators/period-comparison?report_month=${encodeURIComponent(reportMonth.trim())}`,
        { signal: options.signal },
      ),
    getLedgerPnlCandidateFinancialIndicatorComponentDetail: (
      reportMonth,
      metricId,
      parentIdempotencyKey,
      options = {},
    ) => {
      const params = new URLSearchParams({
        report_month: reportMonth.trim(),
        metric_id: metricId.trim(),
        parent_idempotency_key: parentIdempotencyKey.trim(),
      });
      return requestActionJson<LedgerPnlCandidateFinancialIndicatorComponentDetail>(
        fetchImpl,
        baseUrl,
        `/api/ledger-pnl/candidate-financial-indicators/period-comparison/component-detail?${params.toString()}`,
        { signal: options.signal },
      );
    },
    revalidateLedgerPnlCandidateFinancialIndicators: (reportMonth, request) =>
      requestActionJson<LedgerPnlCandidateFinancialIndicatorRevalidationReceipt>(
        fetchImpl,
        baseUrl,
        `/api/ledger-pnl/candidate-financial-indicators/revalidate?report_month=${encodeURIComponent(reportMonth.trim())}`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(request),
        },
      ),
    getLedgerPnlFormalIndicatorRuleChecks: (reportMonth: string) => {
      const params = new URLSearchParams({
        report_month: reportMonth.trim(),
      });
      return requestJson<LedgerPnlFormalIndicatorRuleChecksPayload>(
        fetchImpl,
        baseUrl,
        `/api/ledger-pnl/formal-indicator-rule-checks?${params.toString()}`,
      );
    },
    getLedgerPnlMonthlyAnalysisDates: () =>
      requestJson<QdbGlMonthlyAnalysisDatesPayload>(
        fetchImpl,
        baseUrl,
        "/api/ledger-pnl/monthly-analysis/dates",
      ),
    getLedgerPnlMonthlyAnalysisWorkbook: ({ reportMonth }) =>
      requestJson<QdbGlMonthlyAnalysisWorkbookPayload>(
        fetchImpl,
        baseUrl,
        `/api/ledger-pnl/monthly-analysis/workbook?report_month=${encodeURIComponent(reportMonth.trim())}`,
      ),
    getPnlBridge: (reportDate: string) =>
      requestJson<PnlBridgePayload>(
        fetchImpl,
        baseUrl,
        `/api/pnl/bridge?report_date=${encodeURIComponent(reportDate)}`,
      ),
    refreshFormalPnl: (reportDate?: string) =>
      requestActionJson<FormalPnlRefreshPayload>(
        fetchImpl,
        baseUrl,
        reportDate
          ? `/api/data/refresh_pnl?report_date=${encodeURIComponent(reportDate)}`
          : "/api/data/refresh_pnl",
        {
          method: "POST",
        },
      ),
    getFormalPnlImportStatus: (runId?: string) =>
      requestActionJson<FormalPnlRefreshPayload>(
        fetchImpl,
        baseUrl,
        runId
          ? `/api/data/import_status/pnl?run_id=${encodeURIComponent(runId)}`
          : "/api/data/import_status/pnl",
      ),
  };
}
