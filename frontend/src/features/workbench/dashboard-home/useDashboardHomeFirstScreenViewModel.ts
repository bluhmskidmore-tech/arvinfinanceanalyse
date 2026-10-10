import { useCallback, useMemo, useState } from "react";
import { useSearchParams } from "react-router-dom";

import { sanitizeMetricCopy } from "./lib/sanitizeMetricCopy";
import { useDashboardSnapshotBoundary } from "../pages/useDashboardSnapshotBoundary";
import {
  mapToHomeFirstScreenView,
  type MapToHomeFirstScreenViewInput,
} from "./dashboardHomeFirstScreenView";
import { applyOperatingRevenueCandidate } from "./dashboardHomeSnapshotAdapter";
import { useHomeOperatingRevenueCandidate } from "./useHomeOperatingRevenueCandidate";
import { useMockHomeFirstScreenView } from "./useMockHomeFirstScreenView";

export type DashboardHomeFirstScreenModel = ReturnType<typeof useDashboardHomeFirstScreenViewModel>;
export type DashboardHomeSnapshotBoundary = DashboardHomeFirstScreenModel["snapshotBoundary"];

export function useDashboardHomeFirstScreenViewModel() {
  const [searchParams, setSearchParams] = useSearchParams();
  const reportDate = searchParams.get("report_date")?.trim() ?? "";
  const setReportDate = useCallback(
    (date: string) => {
      const nextSearchParams = new URLSearchParams(searchParams);
      const normalizedDate = date.trim();
      if (normalizedDate) {
        nextSearchParams.set("report_date", normalizedDate);
      } else {
        nextSearchParams.delete("report_date");
      }
      setSearchParams(nextSearchParams, { replace: true });
    },
    [searchParams, setSearchParams],
  );
  const [toolbarSearch, setToolbarSearch] = useState("");
  const [allowPartial, setAllowPartial] = useState(false);

  const snapshotBoundary = useDashboardSnapshotBoundary({
    reportDate,
    // Explicit dates show available same-date domains; latest still requires a complete snapshot.
    allowPartial: allowPartial || Boolean(reportDate),
  });

  const {
    dataClient,
    adapterOutput,
    snapshotResult,
    snapshotMeta,
    reportDateDataWarning,
    snapshotQuery,
  } = snapshotBoundary;
  // real 模式不允许任何 mock UI 可达路径：useMockFallback 只看数据源模式，
  // 不再挂接 isLiveDataFallback 之类的运行时回退信号。
  const useMockFallback = dataClient.mode !== "real";
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

  const operatingRevenueCandidate = useHomeOperatingRevenueCandidate(
    dataClient,
    effectiveReportDate,
    { enabled: !useMockFallback && Boolean(effectiveReportDate) },
  );
  const productCategoryHeadline = useMemo(
    () =>
      applyOperatingRevenueCandidate(
        adapterOutput.productCategoryHeadline,
        operatingRevenueCandidate,
      ),
    [adapterOutput.productCategoryHeadline, operatingRevenueCandidate],
  );

  const firstScreenInput = useMemo<MapToHomeFirstScreenViewInput>(
    () => ({
      reportDate: effectiveReportDate,
      useMockFallback,
      requestedReportDate,
      domainsEffectiveDate: adapterOutput.domainsEffectiveDate,
      domainsMissing: adapterOutput.domainsMissing,
      productCategoryHeadline,
      snapshotMode: snapshotResult?.mode,
      verdict: adapterOutput.verdict,
      metrics: sanitizedMetrics,
      attribution: adapterOutput.attribution.vm,
      bondHeadline: null,
      portfolio: null,
      snapshotMeta,
      alertCount,
      snapshotUnavailable,
      snapshotErrorDetail:
        snapshotQuery.error instanceof Error
          ? snapshotQuery.error.message
          : null,
      snapshotStale,
      snapshotLoading,
      staleWarning: reportDateDataWarning,
    }),
    [
      alertCount,
      adapterOutput.attribution.vm,
      adapterOutput.domainsEffectiveDate,
      adapterOutput.domainsMissing,
      productCategoryHeadline,
      adapterOutput.verdict,
      effectiveReportDate,
      requestedReportDate,
      reportDateDataWarning,
      sanitizedMetrics,
      snapshotMeta,
      snapshotResult?.mode,
      snapshotQuery.error,
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
