import { useMemo } from "react";
import { useQuery } from "@tanstack/react-query";
import { Alert, Card, Spin } from "antd";

import { useApiClient } from "../../../api/client";
import ReactECharts from "../../../lib/echarts";
import { bondAnalyticsQueryKeyRoot } from "../lib/bondAnalyticsQueryKeys";
import { buildYieldCurveTermStructureChartOption } from "../lib/yieldCurveTermStructureChartOption";
import styles from "./BondAnalyticsYieldCurveTermStructureChart.module.css";

export type BondAnalyticsYieldCurveTermStructureChartProps = {
  reportDate: string;
};

export function BondAnalyticsYieldCurveTermStructureChart({
  reportDate,
}: BondAnalyticsYieldCurveTermStructureChartProps) {
  const client = useApiClient();
  const q = useQuery({
    queryKey: [
      ...bondAnalyticsQueryKeyRoot,
      "yield-curve-term-structure",
      client.mode,
      reportDate,
    ],
    queryFn: () =>
      client.getBondAnalyticsYieldCurveTermStructure(reportDate, {
        curveTypes: "treasury,cdb",
      }),
    enabled: Boolean(reportDate),
    retry: false,
    staleTime: 60_000,
  });

  const option = useMemo(
    () => buildYieldCurveTermStructureChartOption(q.data?.result.curves ?? []),
    [q.data?.result.curves],
  );

  const meta = q.data?.result_meta;
  const warnings = q.data?.result.warnings ?? [];
  const stale =
    meta?.vendor_status === "vendor_stale" || meta?.fallback_mode === "latest_snapshot";
  const firstCurve = q.data?.result.curves[0];
  const resolved = firstCurve?.trade_date_resolved;
  const requested = firstCurve?.trade_date_requested;

  return (
    <Card
      size="small"
      title="即期曲线期限结构 (1Y–30Y，正式)"
      data-testid="bond-analytics-yield-curve-term-structure"
    >
      <div className={styles.subtitle}>
        {resolved && requested && resolved !== requested ? (
          <span>曲线交易日已回退为 {resolved}（请求日 {requested}）。</span>
        ) : resolved ? (
          <span>曲线交易日：{resolved}。</span>
        ) : (
          <span>曲线交易日：未解析。</span>
        )}
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
          <ReactECharts option={option} opts={{ renderer: "canvas" }} />
        </div>
      ) : (
        <div className={styles.empty}>暂无正式曲线截面（或全部期限缺失）</div>
      )}
    </Card>
  );
}
