import { useMemo } from "react";
import { useQuery } from "@tanstack/react-query";
import { Card, Spin } from "antd";

import { useApiClient } from "../../../api/client";
import ReactECharts from "../../../lib/echarts";
import { designTokens } from "../../../theme/designSystem";
import { buildBondAnalyticsOverviewRateChartOption } from "../lib/bondAnalyticsRateChartOption";
import { bondAnalyticsQueryKeyRoot } from "../lib/bondAnalyticsQueryKeys";

const dt = designTokens;

export function BondAnalyticsOverviewRateChart() {
  const client = useApiClient();
  const q = useQuery({
    queryKey: [...bondAnalyticsQueryKeyRoot, "choice-macro-latest", client.mode],
    queryFn: () => client.getChoiceMacroLatest(),
    retry: false,
    staleTime: 60_000,
  });

  const option = useMemo(
    () => buildBondAnalyticsOverviewRateChartOption(q.data?.result.series ?? []),
    [q.data?.result.series],
  );

  return (
    <Card
      size="small"
      title="曲线走势（交易日序列）"
      data-testid="bond-analytics-overview-rate-chart"
      styles={{ body: { paddingBlock: dt.space[2] } }}
    >
      <div
        style={{
          fontSize: dt.fontSize[11],
          color: dt.color.neutral[600],
          marginBottom: dt.space[2],
          lineHeight: dt.lineHeight.normal,
        }}
      >
        横轴为交易日，纵轴为各期限/品种收益率读数；非完整 1Y–30Y 即期曲线截面。
      </div>
      {q.isPending ? (
        <div style={{ display: "flex", justifyContent: "center", padding: dt.space[6] }}>
          <Spin />
        </div>
      ) : option ? (
        <ReactECharts option={option} style={{ height: 280, width: "100%" }} opts={{ renderer: "canvas" }} />
      ) : (
        <div
          style={{
            border: `1px dashed ${dt.color.primary[200]}`,
            borderRadius: dt.radius.md,
            padding: dt.space[5],
            textAlign: "center",
            color: dt.color.neutral[500],
            fontSize: dt.fontSize[13],
          }}
        >
          暂无可用的利率时间序列
        </div>
      )}
    </Card>
  );
}
