import { buildMockMeta } from "../mocks/mockApiEnvelope";
import type {
  CubeDimensionsPayload,
  CubeQueryRequest,
  CubeQueryResult,
} from "./contracts";

export type CubeClientMethods = {
  getCubeDimensions: (factTable: string) => Promise<CubeDimensionsPayload>;
  executeCubeQuery: (request: CubeQueryRequest) => Promise<CubeQueryResult>;
};

type CubeClientFactoryOptions = {
  fetchImpl: typeof fetch;
  baseUrl: string;
};

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

export function createRealCubeClient({
  fetchImpl,
  baseUrl,
}: CubeClientFactoryOptions): CubeClientMethods {
  return {
    getCubeDimensions: async (factTable: string) => {
      const response = await fetchImpl(
        `${baseUrl}/api/cube/dimensions/${encodeURIComponent(factTable)}`,
        {
          headers: { Accept: "application/json" },
        },
      );
      if (!response.ok) {
        throw new Error(`Request failed: /api/cube/dimensions/${factTable} (${response.status})`);
      }
      return response.json() as Promise<CubeDimensionsPayload>;
    },
    executeCubeQuery: async (request: CubeQueryRequest) => {
      const response = await fetchImpl(`${baseUrl}/api/cube/query`, {
        method: "POST",
        headers: { "Content-Type": "application/json", Accept: "application/json" },
        body: JSON.stringify(request),
      });
      if (!response.ok) {
        const text = await response.text().catch(() => "");
        throw new Error(text || `Cube query failed (${response.status})`);
      }
      return response.json() as Promise<CubeQueryResult>;
    },
  };
}
