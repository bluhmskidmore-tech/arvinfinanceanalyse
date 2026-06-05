import { useEffect, useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";

import { apiQueryKeys } from "../../../api/queryKeys";
import { sanitizeMetricCopy } from "../../executive-dashboard/lib/sanitizeMetricCopy";
import {
  mapToHomeFirstScreenView,
  type MapToHomeFirstScreenViewInput,
} from "./dashboardHomeFirstScreenView";
import type { DashboardHomeFirstScreenHydration } from "./dashboardHomeFirstScreenTypes";
import type { DashboardHomeSnapshotBoundary } from "./useDashboardHomeFirstScreenViewModel";

export function useDashboardHomeSupplementalHydration(
  snapshotBoundary: DashboardHomeSnapshotBoundary,
): DashboardHomeFirstScreenHydration {
  const [supplementalDataReportDate, setSupplementalDataReportDate] = useState<string | null>(null);

  const {
    dataClient,
    snapshotQuery,
    isLiveDataFallback,
    adapterOutput,
    snapshotResult,
    snapshotMeta,
    initialEffectiveReportDate,
    supplementalReportDate,
    reportDateDataWarning,
  } = snapshotBoundary;

  const useMockFallback = dataClient.mode !== "real" || isLiveDataFallback;
  const snapshotReportDate = snapshotResult?.report_date?.trim() || "";
  const hasInitialEffectiveReportDate = Boolean(initialEffectiveReportDate);
  const hasDeferredSupplementalData =
    hasInitialEffectiveReportDate &&
    supplementalDataReportDate === initialEffectiveReportDate;
  const hasSupplementalReportDate = Boolean(supplementalReportDate);
  const hasDeferredSupplementalReportDate =
    hasDeferredSupplementalData && hasSupplementalReportDate;

  useEffect(() => {
    setSupplementalDataReportDate(null);
    if (!initialEffectiveReportDate) {
      return;
    }

    setSupplementalDataReportDate(initialEffectiveReportDate);
  }, [initialEffectiveReportDate]);

  const bondHeadlineQuery = useQuery({
    queryKey: apiQueryKeys.bondDashboardHeadline(dataClient.mode, supplementalReportDate),
    queryFn: () => dataClient.getBondDashboardHeadlineKpis(supplementalReportDate ?? ""),
    retry: false,
    staleTime: 60_000,
    enabled: hasDeferredSupplementalReportDate,
  });

  const portfolioHeadlinesQuery = useQuery({
    queryKey: apiQueryKeys.bondAnalyticsPortfolioHeadlines(dataClient.mode, supplementalReportDate),
    queryFn: () => dataClient.getBondAnalyticsPortfolioHeadlines(supplementalReportDate ?? ""),
    retry: false,
    staleTime: 60_000,
    enabled: hasDeferredSupplementalReportDate,
  });

  const sanitizedMetrics = useMemo(
    () =>
      (adapterOutput.overview.vm?.metrics ?? []).map((metric) => sanitizeMetricCopy(metric)),
    [adapterOutput.overview.vm?.metrics],
  );
  const effectiveReportDate = snapshotReportDate || initialEffectiveReportDate;
  const snapshotUnavailable =
    dataClient.mode === "real" && snapshotQuery.isError && !snapshotResult;
  const snapshotStale =
    dataClient.mode === "real" && Boolean(reportDateDataWarning) && Boolean(snapshotResult);

  const alertCount = useMemo(() => {
    if (useMockFallback) {
      return 3;
    }
    const missing = snapshotResult?.domains_missing?.length ?? 0;
    return missing > 0 ? missing : adapterOutput.verdict?.tone === "warning" ? 1 : 0;
  }, [adapterOutput.verdict?.tone, snapshotResult?.domains_missing?.length, useMockFallback]);

  const firstScreenInput = useMemo<MapToHomeFirstScreenViewInput>(
    () => ({
      reportDate: effectiveReportDate,
      useMockFallback,
      verdict: adapterOutput.verdict,
      metrics: sanitizedMetrics,
      attribution: adapterOutput.attribution.vm,
      bondHeadline: bondHeadlineQuery.data?.result ?? null,
      portfolio: portfolioHeadlinesQuery.data?.result ?? null,
      snapshotMeta,
      alertCount,
      snapshotUnavailable,
      snapshotStale,
    }),
    [
      adapterOutput.attribution.vm,
      adapterOutput.verdict,
      alertCount,
      bondHeadlineQuery.data?.result,
      effectiveReportDate,
      portfolioHeadlinesQuery.data?.result,
      sanitizedMetrics,
      snapshotMeta,
      snapshotStale,
      snapshotUnavailable,
      useMockFallback,
    ],
  );

  const view = useMemo(() => mapToHomeFirstScreenView(firstScreenInput), [firstScreenInput]);

  return useMemo(
    () => ({
      reportDate: view.reportDate,
      headerStatus: view.headerStatus,
      decisionRail: view.decisionRail,
      terminalKpis: view.terminalKpis,
      keyRiskStrip: view.keyRiskStrip,
    }),
    [
      view.decisionRail,
      view.headerStatus,
      view.keyRiskStrip,
      view.reportDate,
      view.terminalKpis,
    ],
  );
}
