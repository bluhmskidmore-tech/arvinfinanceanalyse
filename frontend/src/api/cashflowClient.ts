/**
 * Cashflow projection client slice.
 * Imported by client.ts for ApiClient composition.
 * Demo/mock factory lives in cashflowMockClient.ts so mock payloads stay out
 * of the real-mode bundle.
 */
import type { ApiEnvelope, CashflowProjectionPayload } from "./contracts";

export type CashflowClientMethods = {
  getCashflowProjection: (reportDate: string) => Promise<ApiEnvelope<CashflowProjectionPayload>>;
};

type FetchLike = typeof fetch;

type RequestJson = <T>(
  fetchImpl: FetchLike,
  baseUrl: string,
  path: string,
) => Promise<ApiEnvelope<T>>;

export type CashflowClientFactoryOptions = {
  fetchImpl: FetchLike;
  baseUrl: string;
  requestJson: RequestJson;
};

export function createRealCashflowClient(
  options: CashflowClientFactoryOptions,
): CashflowClientMethods {
  const { fetchImpl, baseUrl, requestJson } = options;

  return {
    getCashflowProjection: (reportDate: string) =>
      requestJson<CashflowProjectionPayload>(
        fetchImpl,
        baseUrl,
        `/api/cashflow-projection?report_date=${encodeURIComponent(reportDate)}`,
      ),
  };
}
