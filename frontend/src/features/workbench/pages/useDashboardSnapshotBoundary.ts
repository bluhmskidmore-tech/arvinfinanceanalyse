import { useMemo, useRef } from "react";
import { useQuery, type UseQueryResult } from "@tanstack/react-query";

import { useApiClient, type ApiClient } from "../../../api/clientContext";
import {
  adaptHomeSnapshotForFirstScreen,
  type HomeSnapshotAdapterOutput,
} from "../dashboard-home/dashboardHomeSnapshotAdapter";

type HomeSnapshotEnvelope = Awaited<ReturnType<ApiClient["getHomeSnapshot"]>>;

export type UseDashboardSnapshotBoundaryOptions = {
  reportDate: string;
  allowPartial: boolean;
};

export type DashboardSnapshotBoundaryResult = {
  dataClient: ApiClient;
  displayMode: ApiClient["mode"];
  snapshotQuery: UseQueryResult<HomeSnapshotEnvelope, Error>;
  isLiveDataFallback: boolean;
  adapterOutput: HomeSnapshotAdapterOutput;
  snapshotResult: HomeSnapshotEnvelope["result"] | undefined;
  overviewMeta: HomeSnapshotAdapterOutput["overview"]["meta"];
  attributionMeta: HomeSnapshotAdapterOutput["attribution"]["meta"];
  snapshotMeta: HomeSnapshotEnvelope["result_meta"] | null;
  initialEffectiveReportDate: string;
  supplementalReportDate: string | undefined;
  reportDateDataWarning: string | null;
  refreshSnapshot: () => Promise<unknown>;
};

const REPORT_DATE_STALE_WARNING = "新报告日数据获取失败，当前展示上一版本数据";
const LIVE_SOURCE_UNAVAILABLE_WARNING = "实时数据源当前不可用，未展示本地模拟数据";

export function useDashboardSnapshotBoundary({
  reportDate,
  allowPartial,
}: UseDashboardSnapshotBoundaryOptions): DashboardSnapshotBoundaryResult {
  const sourceClient = useApiClient();
  const dataClient = sourceClient;
  const displayMode = sourceClient.mode;
  const requestedDateLabel = reportDate || "latest";

  const snapshotQuery = useQuery<HomeSnapshotEnvelope, Error>({
    queryKey: ["home-snapshot", dataClient.mode, requestedDateLabel, allowPartial],
    queryFn: () =>
      dataClient.getHomeSnapshot({
        reportDate: reportDate || undefined,
        allowPartial,
      }),
    retry: false,
  });

  const isLiveDataFallback = false;
  const lastSuccessfulSnapshotRef = useRef<HomeSnapshotEnvelope | null>(null);
  if (snapshotQuery.data) {
    lastSuccessfulSnapshotRef.current = snapshotQuery.data;
  }

  const displayedSnapshot =
    snapshotQuery.data ?? (snapshotQuery.isError ? lastSuccessfulSnapshotRef.current : null);
  const reportDateDataWarning =
    snapshotQuery.isError && lastSuccessfulSnapshotRef.current
      ? REPORT_DATE_STALE_WARNING
      : snapshotQuery.isError && dataClient.mode === "real"
        ? LIVE_SOURCE_UNAVAILABLE_WARNING
      : null;

  const adapterOutput = useMemo(
    () =>
      adaptHomeSnapshotForFirstScreen({
        snapshot: displayedSnapshot,
        isLoading: snapshotQuery.isLoading,
        isError: snapshotQuery.isError && !displayedSnapshot,
        snapshotFetchErrorDetail:
          snapshotQuery.isError && !displayedSnapshot && snapshotQuery.error instanceof Error
            ? snapshotQuery.error.message
            : undefined,
      }),
    [
      snapshotQuery.isLoading,
      snapshotQuery.isError,
      snapshotQuery.error,
      displayedSnapshot,
    ],
  );

  const snapshotResult = displayedSnapshot?.result;
  const overviewMeta = adapterOutput.overview.meta;
  const attributionMeta = adapterOutput.attribution.meta;
  const snapshotMeta = displayedSnapshot?.result_meta ?? null;
  const requestedReportDate = reportDate.trim();
  const snapshotReportDate = snapshotResult?.report_date?.trim() || "";
  const activeSnapshotReportDate = snapshotQuery.data?.result.report_date?.trim() || "";
  const reportDateSnapshotPending =
    Boolean(requestedReportDate) &&
    snapshotQuery.isFetching &&
    activeSnapshotReportDate !== requestedReportDate;
  const initialEffectiveReportDate = reportDateSnapshotPending
    ? ""
    : snapshotReportDate || (snapshotResult ? requestedReportDate : "");
  const supplementalReportDate = initialEffectiveReportDate || undefined;

  const refreshSnapshot = async () => {
    return snapshotQuery.refetch();
  };

  return {
    dataClient,
    displayMode,
    snapshotQuery,
    isLiveDataFallback,
    adapterOutput,
    snapshotResult,
    overviewMeta,
    attributionMeta,
    snapshotMeta,
    initialEffectiveReportDate,
    supplementalReportDate,
    reportDateDataWarning,
    refreshSnapshot,
  };
}
