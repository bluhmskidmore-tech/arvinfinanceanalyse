/**
 * Cashflow projection client slice.
 * Imported by client.ts for ApiClient composition.
 */
import { buildMockApiEnvelope } from "../mocks/mockApiEnvelope";
import { formatRawAsNumeric } from "../utils/format";
import type { ApiEnvelope, CashflowProjectionPayload } from "./contracts";

export type CashflowClientMethods = {
  getCashflowProjection: (reportDate: string) => Promise<ApiEnvelope<CashflowProjectionPayload>>;
};

type FetchLike = typeof fetch;
type Delay = () => Promise<void>;

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

export function createDemoCashflowClient(delay: Delay): CashflowClientMethods {
  return {
    async getCashflowProjection(reportDate: string) {
      await delay();
      return buildMockApiEnvelope(
        "cashflow_projection.overview",
        {
          report_date: reportDate,
          duration_gap: formatRawAsNumeric({ raw: 1.25, unit: "years", sign_aware: true }),
          asset_duration: formatRawAsNumeric({ raw: 3.8, unit: "years", sign_aware: false }),
          liability_duration: formatRawAsNumeric({ raw: 2.55, unit: "years", sign_aware: false }),
          equity_duration: formatRawAsNumeric({ raw: 5.2, unit: "years", sign_aware: true }),
          rate_sensitivity_1bp: formatRawAsNumeric({ raw: 125_000, unit: "yuan", sign_aware: true }),
          reinvestment_risk_12m: formatRawAsNumeric({ raw: 0.185, unit: "pct", sign_aware: false }),
          monthly_buckets: [],
          top_maturing_assets_12m: [],
          warnings: [],
          computed_at: new Date().toISOString(),
        },
        {
          basis: "analytical",
          formal_use_allowed: false,
          quality_flag: "warning",
          requested_report_date: reportDate,
          resolved_report_date: reportDate,
          as_of_date: reportDate,
          date_basis: "cashflow_projection_report_date",
          filters_applied: {
            report_date: reportDate,
            position_scope: "all",
            currency_basis: "CNY",
          },
          tables_used: ["fact_formal_zqtz_balance_daily", "fact_formal_tyw_balance_daily"],
          evidence_rows: 0,
        },
      );
    },
  };
}

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
