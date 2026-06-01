import { apiQueryKeys } from "../../../api/queryKeys";

export function dashboardBondHeadlineQueryKey(mode: string, reportDate: string) {
  return apiQueryKeys.bondDashboardHeadline(mode, reportDate);
}
