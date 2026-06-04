import { useMemo, useState } from "react";

import { sanitizeMetricCopy } from "../../executive-dashboard/lib/sanitizeMetricCopy";
import { useDashboardSnapshotBoundary } from "../pages/useDashboardSnapshotBoundary";
import {
  mapToHomeFirstScreenView,
  type MapToHomeFirstScreenViewInput,
} from "./dashboardHomeFirstScreenView";

export type DashboardHomeFirstScreenModel = ReturnType<typeof useDashboardHomeFirstScreenViewModel>;
export type DashboardHomeSnapshotBoundary = DashboardHomeFirstScreenModel["snapshotBoundary"];

export function useDashboardHomeFirstScreenViewModel() {
  const [reportDate, setReportDate] = useState("");
  const [toolbarSearch, setToolbarSearch] = useState("");
  const [allowPartial, setAllowPartial] = useState(false);

  const snapshotBoundary = useDashboardSnapshotBoundary({
    reportDate,
    allowPartial,
  });

  const {
    dataClient,
    isLiveDataFallback,
    adapterOutput,
    snapshotResult,
    snapshotMeta,
    initialEffectiveReportDate,
    reportDateDataWarning,
    snapshotQuery,
  } = snapshotBoundary;
  const useMockFallback = dataClient.mode !== "real" || isLiveDataFallback;
  const requestedReportDate = reportDate.trim();
  const snapshotReportDate = snapshotResult?.report_date?.trim() || "";
  const effectiveReportDate =
    snapshotReportDate || initialEffectiveReportDate || requestedReportDate;
  const snapshotUnavailable =
    dataClient.mode === "real" && snapshotQuery.isError && !snapshotResult;
  const snapshotStale =
    dataClient.mode === "real" && Boolean(reportDateDataWarning) && Boolean(snapshotResult);

  const sanitizedMetrics = useMemo(
    () =>
      (adapterOutput.overview.vm?.metrics ?? []).map((metric) => sanitizeMetricCopy(metric)),
    [adapterOutput.overview.vm?.metrics],
  );

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
      bondHeadline: null,
      portfolio: null,
      snapshotMeta,
      alertCount,
      snapshotUnavailable,
      snapshotStale,
    }),
    [
      alertCount,
      adapterOutput.attribution.vm,
      adapterOutput.verdict,
      effectiveReportDate,
      sanitizedMetrics,
      snapshotMeta,
      snapshotStale,
      snapshotUnavailable,
      useMockFallback,
    ],
  );
  const view = useMemo(() => mapToHomeFirstScreenView(firstScreenInput), [firstScreenInput]);

  return {
    view,
    reportDate,
    setReportDate,
    toolbarSearch,
    setToolbarSearch,
    allowPartial,
    setAllowPartial,
    refreshSnapshot: snapshotBoundary.refreshSnapshot,
    snapshotQuery,
    effectiveReportDate,
    snapshotBoundary,
  };
}
