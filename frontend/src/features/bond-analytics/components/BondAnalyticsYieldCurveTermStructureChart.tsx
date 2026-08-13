import { useMemo } from "react";
import { useQuery } from "@tanstack/react-query";
import { Alert, Card, Spin } from "antd";

import { useApiClient } from "../../../api/client";
import type { ApiEnvelope, YieldCurveTermStructurePayload } from "../../../api/contracts";
import { apiQueryKeys } from "../../../api/queryKeys";
import { BaseChart } from "../../../components/charts/BaseChart";
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
    <Card
      size="small"
      title="即期曲线期限结构 (1Y–30Y，正式)"
      data-testid="bond-analytics-yield-curve-term-structure"
    >
      <div className={styles.subtitle}>
        <span>{dateLabel}</span>
        {stale ? <span> 数据可能非当日。</span> : null}
      </div>
      {warnings.length > 0 ? (
        <div className={styles.warningStack}>
          {warnings.map((w) => (
            <Alert key={w} type="warning" showIcon message={w} className={styles.warningItem} />
          ))}
        </div>
      ) : null}
      {q.isError ? (
        <Alert
          type="warning"
          showIcon
          message="期限结构未就绪"
          description={q.error instanceof Error ? q.error.message : "加载失败"}
        />
      ) : q.isPending ? (
        <div className={styles.spinWrap}>
          <Spin />
        </div>
      ) : option && (q.data?.result.curves.length ?? 0) > 0 ? (
        <div className={styles.chart}>
          <BaseChart option={option} height={280} />
        </div>
      ) : (
        <div className={styles.empty}>暂无正式曲线截面（或全部期限缺失）</div>
      )}
    </Card>
  );
}
