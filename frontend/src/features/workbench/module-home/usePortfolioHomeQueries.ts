import { useQuery } from "@tanstack/react-query";

import { useApiClient } from "../../../api/client";
import type { ModuleHomeSourceQueries } from "./moduleHomeModel";

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

  const bondHeadlineQuery = useQuery({
    queryKey: ["module-home", "bond-headline", client.mode, bondReportDate],
    queryFn: () => client.getBondDashboardHeadlineKpis(bondReportDate),
    enabled: Boolean(bondReportDate),
    retry: false,
    staleTime: 60_000,
  });

  const bondRiskQuery = useQuery({
    queryKey: ["module-home", "bond-risk", client.mode, bondReportDate],
    queryFn: () => client.getBondDashboardRiskIndicators(bondReportDate),
    enabled: Boolean(bondReportDate),
    retry: false,
    staleTime: 60_000,
  });

  const bondAssetTypeQuery = useQuery({
    queryKey: ["module-home", "bond-asset-type", client.mode, bondReportDate],
    queryFn: () => client.getBondDashboardAssetStructure(bondReportDate, "bond_type"),
    enabled: Boolean(bondReportDate),
    retry: false,
    staleTime: 60_000,
  });

  const bondAssetRatingQuery = useQuery({
    queryKey: ["module-home", "bond-asset-rating", client.mode, bondReportDate],
    queryFn: () => client.getBondDashboardAssetStructure(bondReportDate, "rating"),
    enabled: Boolean(bondReportDate),
    retry: false,
    staleTime: 60_000,
  });

  const bondMaturityQuery = useQuery({
    queryKey: ["module-home", "bond-maturity", client.mode, bondReportDate],
    queryFn: () => client.getBondDashboardMaturityStructure(bondReportDate),
    enabled: Boolean(bondReportDate),
    retry: false,
    staleTime: 60_000,
  });

  const bondIndustryQuery = useQuery({
    queryKey: ["module-home", "bond-industry", client.mode, bondReportDate],
    queryFn: () => client.getBondDashboardIndustryDistribution(bondReportDate),
    enabled: Boolean(bondReportDate),
    retry: false,
    staleTime: 60_000,
  });

  const bondYieldQuery = useQuery({
    queryKey: ["module-home", "bond-yield", client.mode, bondReportDate],
    queryFn: () => client.getBondDashboardYieldDistribution(bondReportDate),
    enabled: Boolean(bondReportDate),
    retry: false,
    staleTime: 60_000,
  });

  const bondPortfolioComparisonQuery = useQuery({
    queryKey: ["module-home", "bond-portfolio-comparison", client.mode, bondReportDate],
    queryFn: () => client.getBondDashboardPortfolioComparison(bondReportDate),
    enabled: Boolean(bondReportDate),
    retry: false,
    staleTime: 60_000,
  });

  const bondSpreadQuery = useQuery({
    queryKey: ["module-home", "bond-spread", client.mode, bondReportDate],
    queryFn: () => client.getBondDashboardSpreadAnalysis(bondReportDate),
    enabled: Boolean(bondReportDate),
    retry: false,
    staleTime: 60_000,
  });

  const bondBusinessTypeQuery = useQuery({
    queryKey: ["module-home", "bond-business-type", client.mode, bondReportDate],
    queryFn: () => client.getBondBusinessTypeMetrics({ reportDate: bondReportDate }),
    enabled: Boolean(bondReportDate),
    retry: false,
    staleTime: 60_000,
  });

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
  };
}
