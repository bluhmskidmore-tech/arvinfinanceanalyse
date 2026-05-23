import { useEffect, useMemo, useState } from "react";
import { useQuery, type UseQueryResult } from "@tanstack/react-query";

import { createApiClient, useApiClient, type ApiClient } from "../../../api/client";
import { adaptDashboard } from "../../executive-dashboard/adapters/executiveDashboardAdapter";
import { isNetworkUnavailableError } from "./dashboardPageHelpers";

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
  adapterOutput: ReturnType<typeof adaptDashboard>;
  snapshotResult: HomeSnapshotEnvelope["result"] | undefined;
  overviewMeta: ReturnType<typeof adaptDashboard>["overview"]["meta"];
  attributionMeta: ReturnType<typeof adaptDashboard>["attribution"]["meta"];
  initialEffectiveReportDate: string;
  supplementalReportDate: string | undefined;
  refreshSnapshot: () => Promise<unknown>;
};

export function useDashboardSnapshotBoundary({
  reportDate,
  allowPartial,
}: UseDashboardSnapshotBoundaryOptions): DashboardSnapshotBoundaryResult {
  const sourceClient = useApiClient();
  const fallbackClient = useMemo(() => createApiClient({ mode: "mock" }), []);
  const [forceMockFallback, setForceMockFallback] = useState(false);
  const dataClient = forceMockFallback ? fallbackClient : sourceClient;
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

  const isSnapshotNetworkFallback =
    sourceClient.mode === "real" &&
    snapshotQuery.isError &&
    isNetworkUnavailableError(snapshotQuery.error);
  const isLiveDataFallback =
    sourceClient.mode === "real" && (forceMockFallback || isSnapshotNetworkFallback);

  useEffect(() => {
    if (
      sourceClient.mode === "real" &&
      !forceMockFallback &&
      snapshotQuery.isError &&
      isNetworkUnavailableError(snapshotQuery.error)
    ) {
      setForceMockFallback(true);
    }
  }, [
    forceMockFallback,
    snapshotQuery.error,
    snapshotQuery.isError,
    sourceClient.mode,
  ]);

  const { overviewEnv, attributionEnv } = useMemo(() => {
    const env = snapshotQuery.data;
    if (!env) {
      return { overviewEnv: undefined, attributionEnv: undefined };
    }
    return {
      overviewEnv: {
        result_meta: env.result_meta,
        result: env.result.overview,
      },
      attributionEnv: {
        result_meta: env.result_meta,
        result: env.result.attribution,
      },
    };
  }, [snapshotQuery.data]);

  const adapterOutput = useMemo(
    () =>
      adaptDashboard({
        overviewEnv,
        attributionEnv,
        overviewLoading: snapshotQuery.isLoading,
        overviewError: snapshotQuery.isError,
        attributionLoading: snapshotQuery.isLoading,
        attributionError: snapshotQuery.isError,
        verdictPayload: snapshotQuery.data?.result.verdict ?? null,
        snapshotFetchErrorDetail:
          snapshotQuery.error instanceof Error ? snapshotQuery.error.message : undefined,
        domainsEffectiveDate: snapshotQuery.data?.result.domains_effective_date ?? {},
        productCategoryYtd: snapshotQuery.data?.result.product_category_ytd ?? null,
        productCategoryMonthly: snapshotQuery.data?.result.product_category_monthly ?? null,
      }),
    [
      overviewEnv,
      attributionEnv,
      snapshotQuery.isLoading,
      snapshotQuery.isError,
      snapshotQuery.error,
      snapshotQuery.data?.result.verdict,
      snapshotQuery.data?.result.domains_effective_date,
      snapshotQuery.data?.result.product_category_ytd,
      snapshotQuery.data?.result.product_category_monthly,
    ],
  );

  const snapshotResult = snapshotQuery.data?.result;
  const overviewMeta = adapterOutput.overview.meta;
  const attributionMeta = adapterOutput.attribution.meta;
  const initialEffectiveReportDate = snapshotResult?.report_date?.trim() || reportDate.trim();
  const supplementalReportDate = initialEffectiveReportDate || undefined;

  const refreshSnapshot = async () => {
    if (isLiveDataFallback) {
      setForceMockFallback(false);
      return;
    }
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
    initialEffectiveReportDate,
    supplementalReportDate,
    refreshSnapshot,
  };
}
