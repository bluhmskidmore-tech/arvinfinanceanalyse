/**
 * Cashflow projection demo/mock client slice.
 * Loaded only from mock composition paths (mockApiClient.ts); keeps mock
 * payloads out of the real-mode bundle that imports cashflowClient.ts.
 */
import { buildMockApiEnvelope } from "../mocks/mockApiEnvelope";
import { formatRawAsNumeric } from "../utils/format";
import type { CashflowClientMethods } from "./cashflowClient";

type Delay = () => Promise<void>;

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
