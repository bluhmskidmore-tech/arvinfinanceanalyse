import type {
  ApiEnvelope,
  BalanceMovementDatesPayload,
  BalanceMovementPayload,
  BalanceMovementRefreshPayload,
} from "./contracts";
import { buildMockApiEnvelope } from "../mocks/mockApiEnvelope";

type FetchLike = typeof fetch;

export type BalanceMovementClientMethods = {
  getBalanceMovementDates: (
    currencyBasis?: string,
  ) => Promise<ApiEnvelope<BalanceMovementDatesPayload>>;
  getBalanceMovementAnalysis: (options: {
    reportDate: string;
    currencyBasis?: string;
  }) => Promise<ApiEnvelope<BalanceMovementPayload>>;
  refreshBalanceMovementAnalysis: (options: {
    reportDate: string;
    currencyBasis?: string;
  }) => Promise<BalanceMovementRefreshPayload>;
};

export function createMockBalanceMovementClient(): BalanceMovementClientMethods {
  return {
    async getBalanceMovementDates(currencyBasis = "CNX") {
      return buildMockApiEnvelope("balance-analysis.movement.dates", {
        report_dates: ["2026-02-28"],
        currency_basis: currencyBasis,
      });
    },
    async getBalanceMovementAnalysis({ reportDate, currencyBasis = "CNX" }) {
      const reportMonth = reportDate.slice(0, 7);
      const currentRows: BalanceMovementPayload["rows"] = [
        {
          report_date: reportDate,
          report_month: reportMonth,
          currency_basis: currencyBasis,
          sort_order: 1,
          basis_bucket: "AC",
          previous_balance: "139214376198.90",
          current_balance: "142543803312.70",
          previous_balance_pct: "43.114646",
          current_balance_pct: "42.439753",
          balance_change: "3329427113.80",
          change_pct: "2.391581",
          contribution_pct: "25.6509",
          zqtz_amount: "142543803312.70",
          gl_amount: "142543803312.70",
          reconciliation_diff: "0",
          reconciliation_status: "matched",
          source_version: "sv_mock",
          rule_version: "rv_accounting_asset_movement_v2",
        },
        {
          report_date: reportDate,
          report_month: reportMonth,
          currency_basis: currencyBasis,
          sort_order: 2,
          basis_bucket: "OCI",
          previous_balance: "101294750662.96",
          current_balance: "105781745231.25",
          previous_balance_pct: "31.370951",
          current_balance_pct: "31.494537",
          balance_change: "4486994568.29",
          change_pct: "4.429644",
          contribution_pct: "34.5682",
          zqtz_amount: "105781745231.25",
          gl_amount: "105781745231.25",
          reconciliation_diff: "0",
          reconciliation_status: "matched",
          source_version: "sv_mock",
          rule_version: "rv_accounting_asset_movement_v2",
        },
        {
          report_date: reportDate,
          report_month: reportMonth,
          currency_basis: currencyBasis,
          sort_order: 3,
          basis_bucket: "TPL",
          previous_balance: "82384340890.05",
          current_balance: "87547760746.55",
          previous_balance_pct: "25.514403",
          current_balance_pct: "26.065709",
          balance_change: "5163419856.50",
          change_pct: "6.267476",
          contribution_pct: "39.7809",
          zqtz_amount: "87547760746.55",
          gl_amount: "87547760746.55",
          reconciliation_diff: "0",
          reconciliation_status: "matched",
          source_version: "sv_mock",
          rule_version: "rv_accounting_asset_movement_v2",
        },
      ];
      const previousRows: BalanceMovementPayload["rows"] = [
        {
          report_date: "2026-01-31",
          report_month: "2026-01",
          currency_basis: currencyBasis,
          sort_order: 1,
          basis_bucket: "AC",
          previous_balance: "133290012435.54",
          current_balance: "139214376198.90",
          previous_balance_pct: "43.18",
          current_balance_pct: "43.11",
          balance_change: "5924363763.36",
          change_pct: "4.44",
          contribution_pct: "40.98",
          zqtz_amount: "139214376198.90",
          gl_amount: "139214376198.90",
          reconciliation_diff: "0",
          reconciliation_status: "matched",
          source_version: "sv_mock",
          rule_version: "rv_accounting_asset_movement_v2",
        },
        {
          report_date: "2026-01-31",
          report_month: "2026-01",
          currency_basis: currencyBasis,
          sort_order: 2,
          basis_bucket: "OCI",
          previous_balance: "98220500620.00",
          current_balance: "101294750662.96",
          previous_balance_pct: "31.84",
          current_balance_pct: "31.37",
          balance_change: "3074250042.96",
          change_pct: "3.13",
          contribution_pct: "21.27",
          zqtz_amount: "101294750662.96",
          gl_amount: "101294750662.96",
          reconciliation_diff: "0",
          reconciliation_status: "matched",
          source_version: "sv_mock",
          rule_version: "rv_accounting_asset_movement_v2",
        },
        {
          report_date: "2026-01-31",
          report_month: "2026-01",
          currency_basis: currencyBasis,
          sort_order: 3,
          basis_bucket: "TPL",
          previous_balance: "76928560422.80",
          current_balance: "82384340890.18",
          previous_balance_pct: "24.98",
          current_balance_pct: "25.51",
          balance_change: "5455780467.38",
          change_pct: "7.09",
          contribution_pct: "37.75",
          zqtz_amount: "82384340890.05",
          gl_amount: "82384340890.05",
          reconciliation_diff: "0",
          reconciliation_status: "matched",
          source_version: "sv_mock",
          rule_version: "rv_accounting_asset_movement_v2",
        },
      ];

      return buildMockApiEnvelope(
        "balance-analysis.movement.detail",
        {
          report_date: reportDate,
          currency_basis: currencyBasis,
          accounting_controls: ["141%", "142%", "143%", "1440101%"],
          excluded_controls: ["144020%"],
          summary: {
            previous_balance_total: "322893467751.91",
            current_balance_total: "335873309290.50",
            balance_change_total: "12979841538.59",
            zqtz_amount_total: "335873309290.50",
            reconciliation_diff_total: "0",
            matched_bucket_count: 3,
            bucket_count: 3,
          },
          trend_months: [
            {
              report_date: reportDate,
              report_month: reportMonth,
              current_balance_total: "335873309290.50",
              balance_change_total: "12979841538.59",
              rows: currentRows,
            },
            {
              report_date: "2026-01-31",
              report_month: "2026-01",
              current_balance_total: "322893467752.04",
              balance_change_total: "14454898913.70",
              rows: previousRows,
            },
          ],
          rows: currentRows,
        },
        { quality_flag: "ok" },
      );
    },
    async refreshBalanceMovementAnalysis({ reportDate, currencyBasis = "CNX" }) {
      return {
        status: "completed",
        cache_key: "accounting_asset_movement.monthly",
        report_date: reportDate,
        currency_basis: currencyBasis,
        row_count: 3,
        source_version: "sv_mock",
        rule_version: "rv_accounting_asset_movement_v2",
      };
    },
  };
}

export function createRealBalanceMovementClient(options: {
  fetchImpl: FetchLike;
  baseUrl: string;
}): BalanceMovementClientMethods {
  const { fetchImpl, baseUrl } = options;
  return {
    getBalanceMovementDates: (currencyBasis = "CNX") =>
      requestJson<BalanceMovementDatesPayload>(
        fetchImpl,
        baseUrl,
        `/ui/balance-movement-analysis/dates?currency_basis=${encodeURIComponent(currencyBasis)}`,
      ),
    getBalanceMovementAnalysis: ({ reportDate, currencyBasis = "CNX" }) =>
      requestJson<BalanceMovementPayload>(
        fetchImpl,
        baseUrl,
        `/ui/balance-movement-analysis?report_date=${encodeURIComponent(reportDate)}&currency_basis=${encodeURIComponent(currencyBasis)}`,
      ),
    refreshBalanceMovementAnalysis: ({ reportDate, currencyBasis = "CNX" }) =>
      requestActionJson<BalanceMovementRefreshPayload>(
        fetchImpl,
        baseUrl,
        `/ui/balance-movement-analysis/refresh?report_date=${encodeURIComponent(reportDate)}&currency_basis=${encodeURIComponent(currencyBasis)}`,
      ),
  };
}

async function requestJson<T>(fetchImpl: FetchLike, baseUrl: string, path: string) {
  const response = await fetchImpl(`${baseUrl}${path}`, {
    headers: { Accept: "application/json" },
  });
  if (!response.ok) {
    throw new Error(`Request failed: ${path} (${response.status})`);
  }
  return (await response.json()) as ApiEnvelope<T>;
}

async function requestActionJson<T>(fetchImpl: FetchLike, baseUrl: string, path: string) {
  const response = await fetchImpl(`${baseUrl}${path}`, {
    method: "POST",
    headers: { Accept: "application/json" },
  });
  if (!response.ok) {
    throw new Error(`Request failed: ${path} (${response.status})`);
  }
  return (await response.json()) as T;
}
