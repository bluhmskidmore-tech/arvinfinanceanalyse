import { useMemo } from "react";
import { useQuery } from "@tanstack/react-query";
import { Alert } from "antd";

import { useApiClient } from "../../../api/client";
import type { ApiEnvelope, YieldCurveTermStructurePayload } from "../../../api/contracts";
import { apiQueryKeys } from "../../../api/queryKeys";
import { ChartCard } from "../../../components/charts/ChartCard";
import {
  formatYieldCurveDateSummary,
  summarizeYieldCurveDates,
} from "../../../lib/yieldCurveDateSummary";
import {
  BOND_ANALYTICS_COCKPIT_YIELD_CURVE_TYPES,
  type BundleSectionQuery,
} from "../lib/bondAnalyticsCockpitBundleQuery";
import { buildYieldCurveTermStructureChartOption } from "../lib/yieldCurveTermStructureChartOption";
import styles from "./BondAnalyticsYieldCurveTermStructureChart.module.css";

export type BondAnalyticsYieldCurveTermStructureChartProps = {
  reportDate: string;
  bundledYieldCurveQuery?: BundleSectionQuery<"yield-curve-term-structure">;
};

export function BondAnalyticsYieldCurveTermStructureChart({
  reportDate,
  bundledYieldCurveQuery,
}: BondAnalyticsYieldCurveTermStructureChartProps) {
  const client = useApiClient();
  const hasBundledYieldCurveQuery = bundledYieldCurveQuery !== undefined;
  const directYieldCurveQ = useQuery<ApiEnvelope<YieldCurveTermStructurePayload>, Error>({
    queryKey: apiQueryKeys.bondAnalyticsYieldCurveTermStructure(
      client.mode,
      reportDate,
      BOND_ANALYTICS_COCKPIT_YIELD_CURVE_TYPES,
    ),
    queryFn: () =>
      client.getBondAnalyticsYieldCurveTermStructure(reportDate, {
        curveTypes: BOND_ANALYTICS_COCKPIT_YIELD_CURVE_TYPES,
      }),
    enabled: !hasBundledYieldCurveQuery && Boolean(reportDate),
    retry: false,
    staleTime: 60_000,
  });
  const q = bundledYieldCurveQuery ?? directYieldCurveQ;

  const option = useMemo(
    () => buildYieldCurveTermStructureChartOption(q.data?.result.curves ?? []),
    [q.data?.result.curves],
  );

  const dateSummary = useMemo(
    () => summarizeYieldCurveDates(q.data?.result.curves ?? []),
    [q.data?.result.curves],
  );
  const dateLabel = formatYieldCurveDateSummary(dateSummary);
  const meta = q.data?.result_meta;
  const warnings = q.data?.result.warnings ?? [];
  const stale =
    meta?.vendor_status === "vendor_stale" || meta?.fallback_mode === "latest_snapshot";


  return (
    <ChartCard
      title="即期曲线期限结构"
      question="1Y–30Y，正式"
      asOf={dateLabel}
      height={280}
      option={q.isPending || q.isError ? null : option}
      state={q.isPending ? "loading" : q.isError ? "error" : stale ? "stale" : undefined}
      errorMessage={q.error instanceof Error ? q.error.message : "期限结构加载失败"}
      emptyMessage="暂无正式曲线截面（或全部期限缺失）"
      testId="bond-analytics-yield-curve-term-structure"
    >
      {warnings.length > 0 ? (
        <div className={styles.warningStack}>
          {warnings.map((w) => (
            <Alert key={w} type="warning" showIcon message={w} className={styles.warningItem} />
          ))}
        </div>
      ) : null}
    </ChartCard>
  );
}
