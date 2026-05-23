import { useMemo } from "react";
import { useQuery, type UseQueryResult } from "@tanstack/react-query";

import { type ApiClient } from "../../../api/client";
import { addDaysToIsoDate, todayIsoDate } from "./dashboardPageHelpers";

const DASHBOARD_KEY_CALENDAR_LOOKBACK_DAYS = 7;
const DASHBOARD_KEY_CALENDAR_FORWARD_DAYS = 14;

export type UseDashboardResearchCalendarQueryOptions = {
  dataClient: ApiClient;
  getTodayIsoDate?: () => string;
};

export type DashboardResearchCalendarQueryResult = {
  calendarStartDate: string;
  calendarEndDate: string;
  researchCalendarQuery: UseQueryResult<
    Awaited<ReturnType<ApiClient["getResearchCalendarEvents"]>>,
    Error
  >;
};

export function useDashboardResearchCalendarQuery({
  dataClient,
  getTodayIsoDate = todayIsoDate,
}: UseDashboardResearchCalendarQueryOptions): DashboardResearchCalendarQueryResult {
  const calendarAnchorDate = getTodayIsoDate();
  const calendarStartDate = useMemo(
    () => addDaysToIsoDate(calendarAnchorDate, -DASHBOARD_KEY_CALENDAR_LOOKBACK_DAYS),
    [calendarAnchorDate],
  );
  const calendarEndDate = useMemo(
    () => addDaysToIsoDate(calendarAnchorDate, DASHBOARD_KEY_CALENDAR_FORWARD_DAYS),
    [calendarAnchorDate],
  );

  const researchCalendarQuery = useQuery({
    queryKey: ["research-calendar", dataClient.mode, calendarStartDate, calendarEndDate],
    queryFn: () =>
      dataClient.getResearchCalendarEvents({
        startDate: calendarStartDate,
        endDate: calendarEndDate,
      }),
    retry: false,
  });

  return {
    calendarStartDate,
    calendarEndDate,
    researchCalendarQuery,
  };
}
