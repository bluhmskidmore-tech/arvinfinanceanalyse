import { useMemo } from "react";
import { useQuery, type UseQueryResult } from "@tanstack/react-query";

import type { ApiClient } from "../../../api/client";
import { apiQueryKeys } from "../../../api/queryKeys";
import { addDaysToIsoDate, todayIsoDate } from "../pages/dashboardPageHelpers";

const HOME_MACRO_RELEASE_FORWARD_DAYS = 45;

export type UseDashboardHomeMacroReleaseContextQueryOptions = {
  dataClient: ApiClient;
  enabled?: boolean;
  historyLimit?: number;
  getTodayIsoDate?: () => string;
};

export type DashboardHomeMacroReleaseContextQueryResult = {
  windowStartDate: string;
  windowEndDate: string;
  macroReleaseContextQuery: UseQueryResult<
    Awaited<ReturnType<ApiClient["getHomeMacroReleaseContext"]>>,
    Error
  >;
};

export function useDashboardHomeMacroReleaseContextQuery({
  dataClient,
  enabled = true,
  historyLimit = 8,
  getTodayIsoDate = todayIsoDate,
}: UseDashboardHomeMacroReleaseContextQueryOptions): DashboardHomeMacroReleaseContextQueryResult {
  const windowStartDate = getTodayIsoDate();
  const windowEndDate = useMemo(
    () => addDaysToIsoDate(windowStartDate, HOME_MACRO_RELEASE_FORWARD_DAYS),
    [windowStartDate],
  );
  const macroReleaseContextQuery = useQuery({
    queryKey: apiQueryKeys.homeMacroReleaseContext(
      dataClient.mode,
      windowStartDate,
      windowEndDate,
      historyLimit,
    ),
    queryFn: () =>
      dataClient.getHomeMacroReleaseContext({
        startDate: windowStartDate,
        endDate: windowEndDate,
        historyLimit,
      }),
    enabled,
    retry: false,
    staleTime: 60_000,
  });

  return {
    windowStartDate,
    windowEndDate,
    macroReleaseContextQuery,
  };
}
