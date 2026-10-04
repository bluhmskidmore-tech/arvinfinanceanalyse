import type {
  LedgerPnlCandidateFinancialIndicatorsEnvelope,
  LedgerPnlCandidateFinancialIndicatorsPayload,
} from "./contracts";
import type { PnlCoreClientMethods } from "./pnlCoreClient";
import { requestJson } from "./transport";

type FetchLike = typeof fetch;

export type CandidateFinancialIndicatorsClientMethods = Pick<
  PnlCoreClientMethods,
  "getLedgerPnlCandidateFinancialIndicators"
>;

type CandidateFinancialIndicatorsClientFactoryOptions = {
  fetchImpl: FetchLike;
  baseUrl: string;
};

let mockClientPromise: Promise<CandidateFinancialIndicatorsClientMethods> | null = null;

const delay = async () => new Promise<void>((resolve) => setTimeout(resolve, 40));

export function createRealCandidateFinancialIndicatorsClient({
  fetchImpl,
  baseUrl,
}: CandidateFinancialIndicatorsClientFactoryOptions): CandidateFinancialIndicatorsClientMethods {
  return {
    getLedgerPnlCandidateFinancialIndicators: (reportMonth, options = {}) => {
      const params = new URLSearchParams({
        report_month: reportMonth.trim(),
      });
      if (options.includeLineage) {
        params.set("include_lineage", "true");
      }
      if (options.metricId?.trim()) {
        params.set("metric_id", options.metricId.trim());
      }
      return requestJson<LedgerPnlCandidateFinancialIndicatorsPayload>(
        fetchImpl,
        baseUrl,
        `/api/ledger-pnl/candidate-financial-indicators?${params.toString()}`,
      ) as Promise<LedgerPnlCandidateFinancialIndicatorsEnvelope>;
    },
  };
}

async function loadMockClient(): Promise<CandidateFinancialIndicatorsClientMethods> {
  if (!mockClientPromise) {
    mockClientPromise = import("../mocks/pnlCoreMockClient").then(({ createDemoPnlCoreClient }) => {
      const client = createDemoPnlCoreClient(delay);
      return {
        getLedgerPnlCandidateFinancialIndicators:
          client.getLedgerPnlCandidateFinancialIndicators,
      };
    });
  }
  return mockClientPromise;
}

export function createMockCandidateFinancialIndicatorsClient(): CandidateFinancialIndicatorsClientMethods {
  return {
    async getLedgerPnlCandidateFinancialIndicators(...args) {
      const client = await loadMockClient();
      return client.getLedgerPnlCandidateFinancialIndicators(...args);
    },
  };
}
