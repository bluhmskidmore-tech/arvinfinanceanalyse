import { useMemo } from "react";
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

  const bondRiskQuery = useQuery({
    queryKey: ["module-home", "bond-risk", client.mode, bondReportDate],
    queryFn: () => client.getBondDashboardRiskIndicators(bondReportDate),
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

  // 归因瀑布数据（规模/利率/交叉分解）；纯展示增强，不参与决策 readiness gate。
  const pnlVolumeRateQuery = useQuery({
    queryKey: ["module-home", "pnl-volume-rate", client.mode, bondReportDate],
    queryFn: () => client.getVolumeRateAttribution({ reportDate: bondReportDate }),
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

  // fromBondHomeSummary 的派生投影随源 query 一起在此重建；
  // 返回对象只有底层 query 结果变化才更新引用，供页面 useMemo 直接依赖 queries 本身。
  return useMemo(
    () => ({
      balanceDates: balanceDatesQuery,
      balanceOverview: balanceOverviewQuery,
      bondDates: bondDatesQuery,
      bondHeadline: fromBondHomeSummary<BondDashboardHeadlinePayload>(
        bondHomeSummaryQuery,
        (summary) => summary.headline,
      ),
      bondRisk: bondRiskQuery,
      bondAssetType: fromBondHomeSummary<AssetStructurePayload>(
        bondHomeSummaryQuery,
        (summary) => summary.asset_type,
      ),
      bondAssetRating: fromBondHomeSummary<AssetStructurePayload>(
        bondHomeSummaryQuery,
        (summary) => summary.asset_rating,
      ),
      bondMaturity: fromBondHomeSummary<MaturityStructurePayload>(
        bondHomeSummaryQuery,
        (summary) => summary.maturity,
      ),
      bondIndustry: fromBondHomeSummary<IndustryDistPayload>(
        bondHomeSummaryQuery,
        (summary) => summary.industry,
      ),
      bondYield: fromBondHomeSummary<YieldDistributionPayload>(
        bondHomeSummaryQuery,
        (summary) => summary.yield_distribution,
      ),
      bondPortfolioComparison: fromBondHomeSummary<PortfolioComparisonPayload>(
        bondHomeSummaryQuery,
        (summary) => summary.portfolio_comparison,
      ),
      bondSpread: fromBondHomeSummary<SpreadAnalysisPayload>(
        bondHomeSummaryQuery,
        (summary) => summary.spread,
      ),
      bondBusinessType: fromBondHomeSummary<BondBusinessTypeMetricsPayload["result"]>(
        bondHomeSummaryQuery,
        (summary) => summary.business_type,
      ) as UseQueryResult<BondBusinessTypeMetricsPayload>,
      balanceBasis: balanceBasisQuery,
      pnlSummary: pnlSummaryQuery,
      pnlVolumeRate: pnlVolumeRateQuery,
      riskDates: riskDatesQuery,
    }),
    [
      balanceDatesQuery,
      balanceOverviewQuery,
      bondDatesQuery,
      bondHomeSummaryQuery,
      bondRiskQuery,
      balanceBasisQuery,
      pnlSummaryQuery,
      pnlVolumeRateQuery,
      riskDatesQuery,
    ],
  );
}
