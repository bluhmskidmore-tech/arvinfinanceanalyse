/**
 * Formal, Ledger, and Bridge P&L client slice.
 * Imported by client.ts for ApiClient composition.
 */
import { buildMockApiEnvelope } from "../mocks/mockApiEnvelope";
import {
  mockLedgerPnlData,
  mockLedgerPnlDates,
  mockLedgerPnlFormalFinancialIndicators,
  mockLedgerPnlSummary,
} from "../mocks/ledgerPnlMocks";
import { formatRawAsNumeric } from "../utils/format";
import type {
  ApiEnvelope,
  FormalPnlRefreshPayload,
  LedgerPnlDataPayload,
  LedgerPnlDatesPayload,
  LedgerPnlFormalFinancialIndicatorContractPayload,
  LedgerPnlSummaryPayload,
  NumericUnit,
  PnlBasis,
  PnlBridgePayload,
  PnlDataPayload,
  PnlDatesPayload,
  PnlOverviewPayload,
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
  getLedgerPnlFormalFinancialIndicators: (
    reportMonth: string,
  ) => Promise<ApiEnvelope<LedgerPnlFormalFinancialIndicatorContractPayload>>;
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
        source_version: mockLedgerPnlSummary.source_version,
        rule_version: "rv_ledger_pnl_v1",
        cache_version: "cv_ledger_pnl_v1",
        tables_used: ["qdb_general_ledger_workbook"],
        evidence_rows: mockLedgerPnlDates.dates.length,
      });
    },
    async getLedgerPnlData(reportDate: string, currency) {
      await delay();
      return buildMockApiEnvelope(
        "ledger_pnl.data",
        {
          ...mockLedgerPnlData,
          report_date: reportDate,
          items: currency
            ? mockLedgerPnlData.items.filter((item) => item.currency === currency)
            : mockLedgerPnlData.items,
        },
        {
          basis: "ledger",
          formal_use_allowed: false,
          source_version: mockLedgerPnlSummary.source_version,
          rule_version: "rv_ledger_pnl_v1",
          cache_version: "cv_ledger_pnl_v1",
          requested_report_date: reportDate,
          resolved_report_date: reportDate,
          as_of_date: reportDate,
          date_basis: "ledger_report_date",
          filters_applied: { report_date: reportDate, currency: currency ?? "ALL" },
          tables_used: ["qdb_general_ledger_workbook"],
          evidence_rows: currency
            ? mockLedgerPnlData.items.filter((item) => item.currency === currency).length
            : mockLedgerPnlData.items.length,
        },
      );
    },
    async getLedgerPnlSummary(reportDate: string, currency) {
      await delay();
      const filteredCurrencyRows = currency
        ? mockLedgerPnlSummary.by_currency.filter((item) => item.currency === currency)
        : mockLedgerPnlSummary.by_currency;
      const filteredAccountRows = currency
        ? mockLedgerPnlData.items.reduce(
            (total, item) => total + (item.currency === currency ? 1 : 0),
            0,
          )
        : mockLedgerPnlSummary.by_account.reduce((total, item) => total + item.count, 0);
      return buildMockApiEnvelope(
        "ledger_pnl.summary",
        {
          ...mockLedgerPnlSummary,
          report_date: reportDate,
          by_currency: filteredCurrencyRows,
        },
        {
          basis: "ledger",
          formal_use_allowed: false,
          source_version: mockLedgerPnlSummary.source_version,
          rule_version: "rv_ledger_pnl_v1",
          cache_version: "cv_ledger_pnl_v1",
          requested_report_date: reportDate,
          resolved_report_date: reportDate,
          as_of_date: reportDate,
          date_basis: "ledger_report_date",
          filters_applied: { report_date: reportDate, currency: currency ?? "ALL" },
          tables_used: ["qdb_general_ledger_workbook"],
          evidence_rows: filteredAccountRows,
        },
      );
    },
    async getLedgerPnlFormalFinancialIndicators(reportMonth: string) {
      await delay();
      const normalizedReportMonth = reportMonth.trim() || mockLedgerPnlFormalFinancialIndicators.report_month;
      return buildMockApiEnvelope(
        "ledger_pnl.formal_financial_indicator_source_contract",
        {
          ...mockLedgerPnlFormalFinancialIndicators,
          report_month: normalizedReportMonth,
        },
        {
          basis: "ledger",
          formal_use_allowed: false,
          source_version: mockLedgerPnlFormalFinancialIndicators.source_version,
          rule_version: mockLedgerPnlFormalFinancialIndicators.rule_version,
          cache_version: "cv_ledger_pnl_financial_indicator_contract_v1",
          quality_flag: "warning",
          as_of_date: mockLedgerPnlFormalFinancialIndicators.report_date,
          date_basis: "report_month_end",
          evidence_rows: mockLedgerPnlFormalFinancialIndicators.metrics.length,
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
