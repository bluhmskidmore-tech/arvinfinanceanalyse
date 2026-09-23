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

import { requestJson, type FetchLike } from "./transport";

const decimalPattern = /^[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?$/;

export type BalanceMovementClientMethods = {
  getBalanceMovementDates: (
    currencyBasis?: string,
    options?: { signal?: AbortSignal },
  ) => Promise<ApiEnvelope<BalanceMovementDatesPayload>>;
  getBalanceMovementAnalysis: (options: {
    reportDate: string;
    currencyBasis?: string;
    signal?: AbortSignal;
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
    getBalanceMovementDates: async (currencyBasis = "CNX", options) => {
      const path = `/ui/balance-movement-analysis/dates?currency_basis=${encodeURIComponent(currencyBasis)}`;
      const envelope = await requestJson<BalanceMovementDatesPayload>(
        fetchImpl,
        baseUrl,
        path,
        {
          ...options,
          keyFields: [
            { path: "report_dates", type: "array" },
            { path: "currency_basis", type: "string" },
          ],
        },
      );
      if (envelope.result.report_dates.some((date) => typeof date !== "string" || !date.trim())) {
        throw new Error(`Invalid ApiEnvelope from ${baseUrl}${path}: \`result.report_dates\` must contain non-empty strings`);
      }
      if (envelope.result.currency_basis !== currencyBasis) {
        throw new Error(`Invalid ApiEnvelope from ${baseUrl}${path}: \`result.currency_basis\` does not match requested currency_basis`);
      }
      return envelope;
    },
    getBalanceMovementAnalysis: async ({ reportDate, currencyBasis = "CNX", signal }) => {
      const path = `/ui/balance-movement-analysis?report_date=${encodeURIComponent(reportDate)}&currency_basis=${encodeURIComponent(currencyBasis)}`;
      const envelope = await requestJson<BalanceMovementPayload>(
        fetchImpl,
        baseUrl,
        path,
        {
          signal,
          keyFields: [
            { path: "report_date", type: "string" },
            { path: "currency_basis", type: "string" },
            { path: "rows", type: "array" },
            { path: "summary", type: "object" },
            { path: "summary.matched_bucket_count", type: "number" },
            { path: "summary.bucket_count", type: "number" },
            { path: "trend_months", type: "array" },
            { path: "business_trend_months", type: "array" },
            { path: "accounting_controls", type: "array" },
            { path: "excluded_controls", type: "array" },
          ],
        },
      );
      if (envelope.result.report_date !== reportDate) {
        throw new Error(`Invalid ApiEnvelope from ${baseUrl}${path}: \`result.report_date\` does not match requested report_date`);
      }
      if (envelope.result.currency_basis !== currencyBasis) {
        throw new Error(`Invalid ApiEnvelope from ${baseUrl}${path}: \`result.currency_basis\` does not match requested currency_basis`);
      }
      for (const field of [
        "previous_balance_total", "current_balance_total", "balance_change_total",
        "zqtz_amount_total", "reconciliation_diff_total",
      ] as const) {
        const value = envelope.result.summary[field];
        if (!((typeof value === "number" && Number.isFinite(value)) ||
          (typeof value === "string" && decimalPattern.test(value)))) {
          throw new Error(`Invalid ApiEnvelope from ${baseUrl}${path}: \`result.summary.${field}\` must be a decimal value`);
        }
      }
      if (!Number.isInteger(envelope.result.summary.matched_bucket_count) ||
          !Number.isInteger(envelope.result.summary.bucket_count)) {
        throw new Error(`Invalid ApiEnvelope from ${baseUrl}${path}: summary bucket counts must be integers`);
      }
      return envelope;
    },
    refreshBalanceMovementAnalysis: async ({ reportDate, currencyBasis = "CNX" }) => {
      const path = `/ui/balance-movement-analysis/refresh?report_date=${encodeURIComponent(reportDate)}&currency_basis=${encodeURIComponent(currencyBasis)}`;
      const response = await fetchImpl(`${baseUrl}${path}`, {
        method: "POST",
        headers: { Accept: "application/json" },
      });
      if (!response.ok) {
        throw new Error(`Request failed: ${path} (${response.status})`);
      }
      return (await response.json()) as BalanceMovementRefreshPayload;
    },
  };
}
