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
            zqtz_amount_total: "329135676882.45",
            reconciliation_diff_total: "-6737632408.05",
            matched_bucket_count: 0,
            bucket_count: 3,
          },
          rows: [
            {
              report_date: reportDate,
              report_month: reportDate.slice(0, 7),
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
              zqtz_amount: "140350006285.79",
              gl_amount: "142543803312.70",
              reconciliation_diff: "-2193797026.91",
              reconciliation_status: "mismatch",
              source_version: "sv_mock",
              rule_version: "rv_accounting_asset_movement_v2",
            },
            {
              report_date: reportDate,
              report_month: reportDate.slice(0, 7),
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
              zqtz_amount: "101248585598.69",
              gl_amount: "105781745231.25",
              reconciliation_diff: "-4533159632.56",
              reconciliation_status: "mismatch",
              source_version: "sv_mock",
              rule_version: "rv_accounting_asset_movement_v2",
            },
            {
              report_date: reportDate,
              report_month: reportDate.slice(0, 7),
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
              zqtz_amount: "87537084997.96",
              gl_amount: "87547760746.55",
              reconciliation_diff: "-10675748.59",
              reconciliation_status: "mismatch",
              source_version: "sv_mock",
              rule_version: "rv_accounting_asset_movement_v2",
            },
          ],
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
