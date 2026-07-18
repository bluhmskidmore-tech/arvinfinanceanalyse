import { useMemo, useState } from "react";

import { sanitizeMetricCopy } from "../../executive-dashboard/lib/sanitizeMetricCopy";
import { useDashboardSnapshotBoundary } from "../pages/useDashboardSnapshotBoundary";
import {
  mapToHomeFirstScreenView,
  type MapToHomeFirstScreenViewInput,
} from "./dashboardHomeFirstScreenView";
import { useMockHomeFirstScreenView } from "./useMockHomeFirstScreenView";

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
    reportDateDataWarning,
    snapshotQuery,
  } = snapshotBoundary;
  const useMockFallback = dataClient.mode !== "real" || isLiveDataFallback;
  const requestedReportDate = reportDate.trim();
  const snapshotReportDate = snapshotResult?.report_date?.trim() || "";
  const effectiveReportDate = snapshotReportDate;
  const snapshotUnavailable =
    dataClient.mode === "real" && snapshotQuery.isError && !snapshotResult;
  const snapshotLoading =
    dataClient.mode === "real" && snapshotQuery.isFetching && !snapshotResult;
  const mockFirstScreenView = useMockHomeFirstScreenView(useMockFallback);
  const snapshotStale =
    dataClient.mode === "real" && Boolean(reportDateDataWarning) && Boolean(snapshotResult);

  const sanitizedMetrics = useMemo(
    () =>
      (adapterOutput.overview.vm?.metrics ?? []).map((metric) => sanitizeMetricCopy(metric)),
    [adapterOutput.overview.vm?.metrics],
  );

  // The homepage snapshot has no governed alert feed. Missing domains and a warning
  // verdict are data-quality signals, not counted risk tasks.
  const alertCount = 0;

  const firstScreenInput = useMemo<MapToHomeFirstScreenViewInput>(
    () => ({
      reportDate: effectiveReportDate,
      useMockFallback,
      requestedReportDate,
      domainsEffectiveDate: adapterOutput.domainsEffectiveDate,
      domainsMissing: adapterOutput.domainsMissing,
      productCategoryHeadline: adapterOutput.productCategoryHeadline,
      snapshotMode: snapshotResult?.mode,
      verdict: adapterOutput.verdict,
      metrics: sanitizedMetrics,
      attribution: adapterOutput.attribution.vm,
      bondHeadline: null,
      portfolio: null,
      snapshotMeta,
      alertCount,
      snapshotUnavailable,
      snapshotStale,
      snapshotLoading,
      staleWarning: reportDateDataWarning,
    }),
    [
      alertCount,
      adapterOutput.attribution.vm,
      adapterOutput.domainsEffectiveDate,
      adapterOutput.domainsMissing,
      adapterOutput.productCategoryHeadline,
      adapterOutput.verdict,
      effectiveReportDate,
      requestedReportDate,
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
