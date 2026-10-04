import { useMemo } from "react";
import { useQuery } from "@tanstack/react-query";
import type { UseQueryResult } from "@tanstack/react-query";

import { useApiClient } from "../../../api/client";
import { apiQueryKeys } from "../../../api/queryKeys";
import type {
  ApiEnvelope,
  AssetStructurePayload,
  BondBusinessTypeMetricsPayload,
  BondDashboardHeadlinePayload,
  BondDashboardHomeSummaryPayload,
  IndustryDistPayload,
  MaturityStructurePayload,
  PortfolioComparisonPayload,
  RiskIndicatorsPayload,
  SpreadAnalysisPayload,
  YieldDistributionPayload,
} from "../../../api/contracts";
import type { ModuleHomeSourceQueries } from "./moduleHomeModel";

function verifyBalancePublication<T extends { report_date: string }>(
  envelope: ApiEnvelope<T>,
  reportDate: string,
  generation: string | undefined,
  manifestSha256: string | undefined,
): ApiEnvelope<T> {
  const filters = envelope.result_meta.filters_applied;
  if (generation && (
    envelope.result.report_date !== reportDate ||
    filters?.generation !== generation ||
    filters?.manifest_sha256 !== manifestSha256 ||
    filters?.serving_mode !== "published"
  )) {
    throw new Error("资产负债发布快照的报告日或版本校验失败。");
  }
  return envelope;
}

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

export function usePortfolioHomeQueries() {
  const client = useApiClient();

  const balanceDatesQuery = useQuery({
    queryKey: apiQueryKeys.balanceAnalysisDates(client.mode),
    queryFn: () => client.getBalanceAnalysisDates(),
    retry: false,
    staleTime: 60_000,
  });
  const balancePublicationStatusQuery = useQuery({
    queryKey: ["balance-analysis", "publication-status", client.mode],
    queryFn: () => client.getBalanceAnalysisPublicationStatus(),
    retry: false,
  });
  const publicationStatus = balancePublicationStatusQuery.data;
  const publishedReportDate =
    balancePublicationStatusQuery.isSuccess && publicationStatus?.enabled && publicationStatus.available
      ? publicationStatus.report_dates[0]
      : undefined;
  const balanceReportDate = publishedReportDate ?? balanceDatesQuery.data?.result.report_dates[0] ?? "";
  const overviewGeneration =
    publicationStatus?.enabled && publicationStatus.available &&
    publicationStatus.report_dates.includes(balanceReportDate)
      ? publicationStatus.generation ?? undefined
      : undefined;
  const publicationManifest = overviewGeneration ? publicationStatus?.manifest_sha256 ?? undefined : undefined;
  const balanceOverviewServingMode = !balancePublicationStatusQuery.isSuccess
    ? "pending"
    : publicationStatus?.enabled
      ? overviewGeneration && publicationManifest ? "published" : "blocked"
      // The overview endpoint requires a pinned generation for this report date,
      // including when the publication service is disabled.
      : balanceReportDate === "2026-08-31" ? "blocked" : "legacy";
  const canReadOverview = balanceOverviewServingMode === "published" || balanceOverviewServingMode === "legacy";

  const balanceOverviewQuery = useQuery({
    queryKey: ["module-home", "balance-overview", client.mode, balanceReportDate, balanceOverviewServingMode, overviewGeneration, publicationManifest],
    queryFn: async () =>
      verifyBalancePublication(await client.getBalanceAnalysisOverview({
        reportDate: balanceReportDate,
        positionScope: "all",
        currencyBasis: "CNY",
        ...(overviewGeneration ? { generation: overviewGeneration } : {}),
      }), balanceReportDate, overviewGeneration, publicationManifest),
    enabled: Boolean(balanceReportDate) && canReadOverview,
    retry: false,
    staleTime: 60_000,
  });

  const bondDatesQuery = useQuery({
    queryKey: [client.mode, "bond-dashboard", "dates"],
    queryFn: () => client.getBondDashboardDates(),
    retry: false,
    staleTime: 60_000,
  });
  const bondReportDate = bondDatesQuery.data?.result.report_dates[0] ?? "";

  const bondHomeSummaryQuery = useQuery({
    queryKey: apiQueryKeys.bondDashboardHomeSummary(client.mode, bondReportDate),
    queryFn: () => client.getBondDashboardHomeSummary(bondReportDate),
    enabled: Boolean(bondReportDate),
    retry: false,
    staleTime: 60_000,
  });

  const balanceBasisQuery = useQuery({
    queryKey: ["module-home", "balance-basis", client.mode, balanceReportDate, balanceOverviewServingMode, overviewGeneration, publicationManifest],
    queryFn: async () =>
      verifyBalancePublication(await client.getBalanceAnalysisSummaryByBasis({
        reportDate: balanceReportDate,
        positionScope: "all",
        currencyBasis: "CNY",
        ...(overviewGeneration ? { generation: overviewGeneration } : {}),
      }), balanceReportDate, overviewGeneration, publicationManifest),
    enabled: Boolean(balanceReportDate) && canReadOverview,
    retry: false,
    staleTime: 60_000,
  });
  // A published pair is shown only once both envelopes prove the selected snapshot.
  // Withdrawing either side also withdraws its peer, including cached refetch results.
  const canDisplayBalance = canReadOverview && (balanceOverviewServingMode === "legacy" ||
    (balanceOverviewQuery.isSuccess && balanceBasisQuery.isSuccess));

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
  const queries = useMemo<ModuleHomeSourceQueries>(
    () => ({
      balanceDates: balanceDatesQuery,
      balancePublicationStatus: balancePublicationStatusQuery,
      balanceOverview: {
        ...balanceOverviewQuery,
        data: canDisplayBalance && balanceOverviewQuery.isSuccess ? balanceOverviewQuery.data : undefined,
      } as ModuleHomeSourceQueries["balanceOverview"],
      bondDates: bondDatesQuery,
      bondHeadline: fromBondHomeSummary<BondDashboardHeadlinePayload>(
        bondHomeSummaryQuery,
        (summary) => summary.headline,
      ),
      bondRisk: fromBondHomeSummary<RiskIndicatorsPayload>(
        bondHomeSummaryQuery,
        (summary) => summary.risk,
      ),
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
      balanceBasis: {
        ...balanceBasisQuery,
        data: canDisplayBalance && balanceBasisQuery.isSuccess ? balanceBasisQuery.data : undefined,
      } as ModuleHomeSourceQueries["balanceBasis"],
      pnlSummary: pnlSummaryQuery,
      pnlVolumeRate: pnlVolumeRateQuery,
      riskDates: riskDatesQuery,
    }),
    [
      balanceDatesQuery,
      balancePublicationStatusQuery,
      balanceOverviewQuery,
      canDisplayBalance,
      bondDatesQuery,
      bondHomeSummaryQuery,
      balanceBasisQuery,
      pnlSummaryQuery,
      pnlVolumeRateQuery,
      riskDatesQuery,
    ],
  );
  return { queries, balanceReportDate, balancePublicationStatusQuery, balanceOverviewServingMode };
}
