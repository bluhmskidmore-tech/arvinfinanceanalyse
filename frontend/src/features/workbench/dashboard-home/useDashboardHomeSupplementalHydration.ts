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
import { useMockHomeFirstScreenView } from "./useMockHomeFirstScreenView";

type IdleWindow = Window & {
  requestIdleCallback?: (callback: () => void, options?: { timeout: number }) => number;
  cancelIdleCallback?: (handle: number) => void;
};

const FIRST_SCREEN_HYDRATION_IDLE_MIN_DELAY_MS = 600;
const FIRST_SCREEN_HYDRATION_IDLE_TIMEOUT_MS = 1_200;
const FIRST_SCREEN_HYDRATION_TIMEOUT_FALLBACK_MS = 900;

function useFirstScreenHydrationGate(reportDate: string | undefined, enabled: boolean) {
  const [readyReportDate, setReadyReportDate] = useState<string | null>(null);

  useEffect(() => {
    setReadyReportDate(null);
    if (!enabled || !reportDate) {
      return undefined;
    }

    let isActive = true;
    const idleWindow = window as IdleWindow;
    let idleHandle: number | null = null;
    let timeoutHandle: number | null = null;
    let delayHandle: number | null = null;
    const cancelScheduledWork = () => {
      if (idleHandle != null) {
        idleWindow.cancelIdleCallback?.(idleHandle);
        idleHandle = null;
      }
      if (timeoutHandle != null) {
        window.clearTimeout(timeoutHandle);
        timeoutHandle = null;
      }
      if (delayHandle != null) {
        window.clearTimeout(delayHandle);
        delayHandle = null;
      }
    };
    const markReady = () => {
      if (isActive) {
        cancelScheduledWork();
        setReadyReportDate(reportDate);
      }
    };
    const scheduleReady = () => {
      if (!isActive) {
        return;
      }
      if (idleWindow.requestIdleCallback) {
        idleHandle = idleWindow.requestIdleCallback(markReady, {
          timeout: FIRST_SCREEN_HYDRATION_IDLE_TIMEOUT_MS,
        });
        return;
      }
      timeoutHandle = window.setTimeout(markReady, FIRST_SCREEN_HYDRATION_TIMEOUT_FALLBACK_MS);
    };
    delayHandle = window.setTimeout(scheduleReady, FIRST_SCREEN_HYDRATION_IDLE_MIN_DELAY_MS);

    return () => {
      isActive = false;
      cancelScheduledWork();
    };
  }, [enabled, reportDate]);

  return readyReportDate === reportDate;
}

export function useDashboardHomeSupplementalHydration(
  snapshotBoundary: DashboardHomeSnapshotBoundary,
  options: { enabled: boolean } = { enabled: true },
): DashboardHomeFirstScreenHydration {
  const [supplementalDataReportDate, setSupplementalDataReportDate] = useState<string | null>(null);

  const {
    dataClient,
    snapshotQuery,
    isLiveDataFallback,
    adapterOutput,
    snapshotResult,
    snapshotMeta,
    supplementalReportDate,
    reportDateDataWarning,
  } = snapshotBoundary;

  const useMockFallback = dataClient.mode !== "real" || isLiveDataFallback;
  const mockFirstScreenView = useMockHomeFirstScreenView(useMockFallback);
  const snapshotReportDate = snapshotResult?.report_date?.trim() || "";
  const hasSupplementalReportDate = Boolean(supplementalReportDate);
  const hasDeferredSupplementalData =
    hasSupplementalReportDate &&
    supplementalDataReportDate === supplementalReportDate;
  const hasDeferredSupplementalReportDate =
    hasDeferredSupplementalData && hasSupplementalReportDate;
  const hasFirstScreenHydrationData = useFirstScreenHydrationGate(
    hasDeferredSupplementalReportDate ? supplementalReportDate : undefined,
    options.enabled,
  );

  useEffect(() => {
    setSupplementalDataReportDate(null);
    if (!supplementalReportDate) {
      return;
    }

    setSupplementalDataReportDate(supplementalReportDate);
  }, [supplementalReportDate]);

  const bondHeadlineQuery = useQuery({
    queryKey: apiQueryKeys.bondDashboardHeadline(dataClient.mode, supplementalReportDate),
    queryFn: () => dataClient.getBondDashboardHeadlineKpis(supplementalReportDate ?? ""),
    retry: false,
    staleTime: 60_000,
    enabled: !useMockFallback && hasDeferredSupplementalReportDate && hasFirstScreenHydrationData,
  });

  const portfolioHeadlinesQuery = useQuery({
    queryKey: apiQueryKeys.bondAnalyticsPortfolioHeadlines(dataClient.mode, supplementalReportDate),
    queryFn: () => dataClient.getBondAnalyticsPortfolioHeadlines(supplementalReportDate ?? ""),
    retry: false,
    staleTime: 60_000,
    enabled: !useMockFallback && hasDeferredSupplementalReportDate && hasFirstScreenHydrationData,
  });

  const sanitizedMetrics = useMemo(
    () =>
      (adapterOutput.overview.vm?.metrics ?? []).map((metric) => sanitizeMetricCopy(metric)),
    [adapterOutput.overview.vm?.metrics],
  );
  const effectiveReportDate = snapshotReportDate;
  const snapshotUnavailable =
    dataClient.mode === "real" && snapshotQuery.isError && !snapshotResult;
  const snapshotLoading =
    dataClient.mode === "real" && snapshotQuery.isFetching && !snapshotResult;
  const snapshotStale =
    dataClient.mode === "real" && Boolean(reportDateDataWarning) && Boolean(snapshotResult);

  // No governed alert feed is hydrated here. Data-quality gaps must not become
  // synthetic risk tasks or links to the decision queue.
  const alertCount = 0;

  const firstScreenInput = useMemo<MapToHomeFirstScreenViewInput>(
    () => ({
      reportDate: effectiveReportDate,
      useMockFallback,
      domainsEffectiveDate: adapterOutput.domainsEffectiveDate,
      domainsMissing: adapterOutput.domainsMissing,
      productCategoryHeadline: adapterOutput.productCategoryHeadline,
      snapshotMode: snapshotResult?.mode,
      verdict: adapterOutput.verdict,
      metrics: sanitizedMetrics,
      attribution: adapterOutput.attribution.vm,
      bondHeadline: bondHeadlineQuery.data?.result ?? null,
      portfolio: portfolioHeadlinesQuery.data?.result ?? null,
      snapshotMeta,
      alertCount,
      snapshotUnavailable,
      snapshotStale,
      snapshotLoading,
      staleWarning: reportDateDataWarning,
    }),
    [
      adapterOutput.attribution.vm,
      adapterOutput.domainsEffectiveDate,
      adapterOutput.domainsMissing,
      adapterOutput.productCategoryHeadline,
      adapterOutput.verdict,
      alertCount,
      bondHeadlineQuery.data?.result,
      effectiveReportDate,
      portfolioHeadlinesQuery.data?.result,
      reportDateDataWarning,
      sanitizedMetrics,
      snapshotMeta,
      snapshotResult?.mode,
      snapshotStale,
      snapshotLoading,
      snapshotUnavailable,
      useMockFallback,
    ],
  );

  const mappedView = useMemo(() => mapToHomeFirstScreenView(firstScreenInput), [firstScreenInput]);
  const view = useMockFallback && mockFirstScreenView ? mockFirstScreenView : mappedView;

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
