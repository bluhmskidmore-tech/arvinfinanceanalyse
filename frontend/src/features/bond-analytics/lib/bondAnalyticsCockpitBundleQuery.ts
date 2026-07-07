import { useQuery, type UseQueryResult } from "@tanstack/react-query";

import { useApiClient } from "../../../api/client";
import type {
  ApiEnvelope,
  BondDashboardBundlePayload,
  BondDashboardBundleSectionEnvelopeMap,
  BondDashboardBundleSectionId,
} from "../../../api/contracts";
import { apiQueryKeys } from "../../../api/queryKeys";

export const BOND_ANALYTICS_COCKPIT_YIELD_CURVE_TYPES = "treasury,cdb";
export const BOND_ANALYTICS_COCKPIT_DV01_TOP_N = 1;
export const BOND_ANALYTICS_COCKPIT_DV01_SHOCK_BPS = "1";
export const BOND_ANALYTICS_COCKPIT_BUNDLE_INDUSTRY_TOP_N = 10;
export const BOND_ANALYTICS_COCKPIT_BUNDLE_ANALYTICS_TOP_N = 10;
export const BOND_ANALYTICS_COCKPIT_BUNDLE_SECTIONS = [
  "headline-kpis",
  "maturity-structure",
  "top-holdings",
  "portfolio-headlines",
  "asset-structure",
  "risk-indicators",
  "industry-distribution",
  "dv01-risk-ac",
  "dv01-risk-oci",
  "dv01-risk-tpl",
  "dv01-risk-all",
  "yield-curve-term-structure",
] as const satisfies readonly BondDashboardBundleSectionId[];

export type BundleSectionQuery<TSection extends BondDashboardBundleSectionId> = {
  data: BondDashboardBundleSectionEnvelopeMap[TSection] | undefined;
  error: Error | null;
  isError: boolean;
  isPending: boolean;
  isLoading: boolean;
};

export function bundleSectionQuery<TSection extends BondDashboardBundleSectionId>(
  bundleQ: UseQueryResult<ApiEnvelope<BondDashboardBundlePayload>, Error>,
  section: TSection,
): BundleSectionQuery<TSection> {
  const status = bundleQ.data?.result.section_statuses?.[section];
  const sectionFailed = status?.status === "error";
  const data = bundleQ.data?.result.sections[section] as
    | BondDashboardBundleSectionEnvelopeMap[TSection]
    | undefined;
  return {
    data: sectionFailed ? undefined : data,
    error: sectionFailed
      ? new Error(status?.message ?? `${section} section failed`)
      : bundleQ.error ?? null,
    isError: bundleQ.isError || sectionFailed,
    isPending: bundleQ.isPending,
    isLoading: bundleQ.isLoading,
  };
}

export function useBondAnalyticsCockpitBundleQuery(reportDate: string) {
  const client = useApiClient();

  return useQuery({
    queryKey: apiQueryKeys.bondDashboardBundle(
      client.mode,
      reportDate,
      BOND_ANALYTICS_COCKPIT_BUNDLE_SECTIONS,
      BOND_ANALYTICS_COCKPIT_BUNDLE_INDUSTRY_TOP_N,
    ),
    queryFn: () =>
      client.fetchBondDashboardBundle(reportDate, BOND_ANALYTICS_COCKPIT_BUNDLE_SECTIONS, {
        industryTopN: BOND_ANALYTICS_COCKPIT_BUNDLE_INDUSTRY_TOP_N,
        analyticsTopN: BOND_ANALYTICS_COCKPIT_BUNDLE_ANALYTICS_TOP_N,
        dv01TopN: BOND_ANALYTICS_COCKPIT_DV01_TOP_N,
        dv01ShockBps: BOND_ANALYTICS_COCKPIT_DV01_SHOCK_BPS,
        curveTypes: BOND_ANALYTICS_COCKPIT_YIELD_CURVE_TYPES,
      }),
    enabled: Boolean(reportDate),
    retry: false,
    staleTime: 60_000,
  });
}
