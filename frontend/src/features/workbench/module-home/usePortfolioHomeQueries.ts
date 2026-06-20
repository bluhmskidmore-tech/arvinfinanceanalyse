import { useQuery } from "@tanstack/react-query";
import type { UseQueryResult } from "@tanstack/react-query";

import { useApiClient } from "../../../api/client";
import type {
  ApiEnvelope,
  AssetStructurePayload,
  BondBusinessTypeMetricsPayload,
  BondDashboardHeadlinePayload,
  BondDashboardHomeSummaryPayload,
  IndustryDistPayload,
  MaturityStructurePayload,
  PortfolioComparisonPayload,
  SpreadAnalysisPayload,
  YieldDistributionPayload,
} from "../../../api/contracts";
import type { ModuleHomeSourceQueries } from "./moduleHomeModel";

function fromBondHomeSummary<T>(
  query: UseQueryResult<ApiEnvelope<BondDashboardHomeSummaryPayload>>,
  pick: (summary: BondDashboardHomeSummaryPayload) => T,
): UseQueryResult<ApiEnvelope<T>> {
  const data = query.data
    ? {
        ...query.data,
        result: pick(query.data.result),
      }
    : undefined;
  return {
    ...query,
    data,
  } as UseQueryResult<ApiEnvelope<T>>;
}

export function usePortfolioHomeQueries(): ModuleHomeSourceQueries {
  const client = useApiClient();

  const balanceDatesQuery = useQuery({
    queryKey: ["module-home", "balance-dates", client.mode],
    queryFn: () => client.getBalanceAnalysisDates(),
    retry: false,
    staleTime: 60_000,
  });
  const balanceReportDate = balanceDatesQuery.data?.result.report_dates[0] ?? "";

  const balanceOverviewQuery = useQuery({
    queryKey: ["module-home", "balance-overview", client.mode, balanceReportDate],
    queryFn: () =>
      client.getBalanceAnalysisOverview({
        reportDate: balanceReportDate,
        positionScope: "all",
        currencyBasis: "CNY",
      }),
    enabled: Boolean(balanceReportDate),
    retry: false,
    staleTime: 60_000,
  });

  const bondDatesQuery = useQuery({
    queryKey: ["module-home", "bond-dates", client.mode],
    queryFn: () => client.getBondDashboardDates(),
    retry: false,
    staleTime: 60_000,
  });
  const bondReportDate = bondDatesQuery.data?.result.report_dates[0] ?? "";

  const bondHomeSummaryQuery = useQuery({
    queryKey: ["module-home", "bond-home-summary", client.mode, bondReportDate],
    queryFn: () => client.getBondDashboardHomeSummary(bondReportDate),
    enabled: Boolean(bondReportDate),
    retry: false,
    staleTime: 60_000,
  });

  const bondHeadlineQuery = fromBondHomeSummary<BondDashboardHeadlinePayload>(
    bondHomeSummaryQuery,
    (summary) => summary.headline,
  );
  const bondRiskQuery = useQuery({
    queryKey: ["module-home", "bond-risk", client.mode, bondReportDate],
    queryFn: () => client.getBondDashboardRiskIndicators(bondReportDate),
    enabled: Boolean(bondReportDate),
    retry: false,
    staleTime: 60_000,
  });
  const bondAssetTypeQuery = fromBondHomeSummary<AssetStructurePayload>(
    bondHomeSummaryQuery,
    (summary) => summary.asset_type,
  );
  const bondAssetRatingQuery = fromBondHomeSummary<AssetStructurePayload>(
    bondHomeSummaryQuery,
    (summary) => summary.asset_rating,
  );
  const bondMaturityQuery = fromBondHomeSummary<MaturityStructurePayload>(
    bondHomeSummaryQuery,
    (summary) => summary.maturity,
  );
  const bondIndustryQuery = fromBondHomeSummary<IndustryDistPayload>(
    bondHomeSummaryQuery,
    (summary) => summary.industry,
  );
  const bondYieldQuery = fromBondHomeSummary<YieldDistributionPayload>(
    bondHomeSummaryQuery,
    (summary) => summary.yield_distribution,
  );
  const bondPortfolioComparisonQuery = fromBondHomeSummary<PortfolioComparisonPayload>(
    bondHomeSummaryQuery,
    (summary) => summary.portfolio_comparison,
  );
  const bondSpreadQuery = fromBondHomeSummary<SpreadAnalysisPayload>(
    bondHomeSummaryQuery,
    (summary) => summary.spread,
  );
  const bondBusinessTypeQuery = fromBondHomeSummary<BondBusinessTypeMetricsPayload["result"]>(
    bondHomeSummaryQuery,
    (summary) => summary.business_type,
  ) as UseQueryResult<BondBusinessTypeMetricsPayload>;

  const balanceBasisQuery = useQuery({
    queryKey: ["module-home", "balance-basis", client.mode, balanceReportDate],
    queryFn: () =>
      client.getBalanceAnalysisSummaryByBasis({
        reportDate: balanceReportDate,
        positionScope: "all",
        currencyBasis: "CNY",
      }),
    enabled: Boolean(balanceReportDate),
    retry: false,
    staleTime: 60_000,
  });

  const pnlSummaryQuery = useQuery({
    queryKey: ["module-home", "pnl-summary", client.mode, bondReportDate],
    queryFn: () => client.getPnlAttributionAnalysisSummary(bondReportDate),
    enabled: Boolean(bondReportDate),
    retry: false,
    staleTime: 60_000,
  });

  const riskDatesQuery = useQuery({
    queryKey: ["module-home", "portfolio-risk-dates", client.mode],
    queryFn: () => client.getRiskTensorDates(),
    retry: false,
    staleTime: 60_000,
  });

  return {
    balanceDates: balanceDatesQuery,
    balanceOverview: balanceOverviewQuery,
    bondDates: bondDatesQuery,
    bondHeadline: bondHeadlineQuery,
    bondRisk: bondRiskQuery,
    bondAssetType: bondAssetTypeQuery,
    bondAssetRating: bondAssetRatingQuery,
    bondMaturity: bondMaturityQuery,
    bondIndustry: bondIndustryQuery,
    bondYield: bondYieldQuery,
    bondPortfolioComparison: bondPortfolioComparisonQuery,
    bondSpread: bondSpreadQuery,
    bondBusinessType: bondBusinessTypeQuery,
    balanceBasis: balanceBasisQuery,
    pnlSummary: pnlSummaryQuery,
    riskDates: riskDatesQuery,
  };
}
