/**
 * Balance movement client slice.
 * Imported by client.ts for ApiClient composition.
 * Mock factory lives in balanceMovementMockClient.ts so the large inline mock
 * payload stays out of the real-mode bundle.
 */
import type {
  ApiEnvelope,
  BalanceMovementDatesPayload,
  BalanceMovementPayload,
  BalanceMovementRefreshPayload,
} from "./contracts";

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
