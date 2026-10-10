import { useQuery } from "@tanstack/react-query";

import type { ApiClient } from "../../../api/client";
import type { BondDashboardBundleSectionId } from "../../../api/contracts";
import { apiQueryKeys } from "../../../api/queryKeys";

export function useBondDashboardBundleQuery(
  client: ApiClient,
  reportDate: string | null,
  sections: readonly BondDashboardBundleSectionId[],
  opts: { enabled?: boolean; industryTopN?: number } = {},
) {
  const rd = reportDate?.trim() ?? "";
  const industryTopN = opts.industryTopN ?? 10;

  return useQuery({
    queryKey: apiQueryKeys.bondDashboardBundle(client.mode, rd, sections, industryTopN),
    queryFn: () => client.fetchBondDashboardBundle(rd, sections, { industryTopN }),
    enabled: opts.enabled ?? Boolean(rd),
  });
}
