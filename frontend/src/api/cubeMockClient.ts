/**
 * Cube demo/mock client slice.
 * Loaded only from mock composition paths (mockApiClient.ts); keeps mock
 * payloads out of the real-mode bundle that imports cubeClient.ts.
 */
import { buildMockMeta } from "../mocks/mockApiEnvelope";
import type { CubeClientMethods } from "./cubeClient";
import type { CubeQueryRequest } from "./contracts";

const delay = async () => new Promise((resolve) => setTimeout(resolve, 40));

export function createMockCubeClient(): CubeClientMethods {
  return {
    async getCubeDimensions(factTable: string) {
      await delay();
      const dimensionMap: Record<string, string[]> = {
        bond_analytics: [
          "asset_class_std",
          "accounting_class",
          "tenor_bucket",
          "rating",
          "bond_type",
          "issuer_name",
          "industry_name",
          "portfolio_name",
          "cost_center",
        ],
        pnl: ["invest_type_std", "accounting_basis", "portfolio_name", "cost_center"],
        balance: [
          "asset_class",
          "invest_type_std",
          "accounting_basis",
          "position_scope",
          "bond_type",
          "rating",
        ],
        product_category: ["category_id", "category_name", "side", "view"],
      };
      const fieldMap: Record<string, string[]> = {
        bond_analytics: ["market_value", "duration"],
        pnl: ["total_pnl"],
        balance: ["market_value", "amortized_cost", "accrued_interest"],
        product_category: ["business_net_income"],
      };
      return {
        fact_table: factTable,
        dimensions: dimensionMap[factTable] ?? [],
        measures: ["sum", "avg", "count", "min", "max"],
        measure_fields: fieldMap[factTable] ?? [],
      };
    },
    async executeCubeQuery(request: CubeQueryRequest) {
      await delay();
      return {
        report_date: request.report_date,
        fact_table: request.fact_table,
        measures: request.measures,
        dimensions: request.dimensions ?? [],
        rows: [],
        total_rows: 0,
        drill_paths: [],
        result_meta: {
          ...buildMockMeta("cube.query"),
          basis: "formal",
          formal_use_allowed: true,
        },
      };
    },
  };
}
