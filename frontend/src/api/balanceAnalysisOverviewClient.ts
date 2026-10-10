import type {
  BalanceAnalysisClientFactoryOptions,
  BalanceAnalysisClientMethods,
} from "./balanceAnalysisClient";
import type { BalanceAnalysisOverviewPayload } from "./contracts";

/** Shared live endpoint without loading the balance domain's demo fixtures. */
export function createRealBalanceAnalysisOverviewClient({
  fetchImpl,
  baseUrl,
  requestJson,
}: Pick<BalanceAnalysisClientFactoryOptions, "fetchImpl" | "baseUrl" | "requestJson">): Pick<
  BalanceAnalysisClientMethods,
  "getBalanceAnalysisOverview"
> {
  return {
    getBalanceAnalysisOverview: ({ reportDate, positionScope, currencyBasis, generation }) => {
      const params = new URLSearchParams({
        report_date: reportDate,
        position_scope: positionScope,
        currency_basis: currencyBasis,
      });
      if (generation) {
        params.set("generation", generation);
      }
      return requestJson<BalanceAnalysisOverviewPayload>(
        fetchImpl,
        baseUrl,
        `/ui/balance-analysis/overview?${params.toString()}`,
      );
    },
  };
}
