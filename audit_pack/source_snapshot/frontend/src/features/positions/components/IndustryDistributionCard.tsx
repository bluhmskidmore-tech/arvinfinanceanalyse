import { useMemo } from "react";
import { useQuery } from "@tanstack/react-query";
import { Card, Spin, Table, Typography } from "antd";

import { useApiClient } from "../../../api/client";
import ReactECharts, { type EChartsOption } from "../../../lib/echarts";
import { formatAmountYi, formatRatePercent } from "../utils/format";

const INDUSTRY_COLORS = [
  "#3b82f6",
  "#8b5cf6",
  "#ec4899",
  "#14b8a6",
  "#f59e0b",
  "#22c55e",
  "#ef4444",
  "#6366f1",
  "#84cc16",
  "#f97316",
];

type Props = {
  startDate: string | null;
  endDate: string | null;
  subType?: string | null;
};

export default function IndustryDistributionCard({ startDate, endDate, subType }: Props) {
  const client = useApiClient();

  const query = useQuery({
    queryKey: [
      "positions",
      "stats-industry",
      client.mode,
      startDate,
      endDate,
      subType ?? "",
    ],
    queryFn: async () => {
      if (!startDate || !endDate) {
        throw new Error("missing range");
      }
      const envelope = await client.getPositionsStatsIndustry({
        startDate,
        endDate,
        subType: subType ?? null,
        topN: 10,
      });
      return envelope.result;
    },
    enabled: Boolean(startDate && endDate),
    retry: false,
  });

  const data = query.data;
  const chartOption = useMemo((): EChartsOption | null => {
    if (!data?.items?.length) {
      return null;
    }
    const items = [...data.items].slice(0, 10);
    const names = items.map((it) =>
      it.industry.length > 6 ? `${it.industry.slice(0, 6)}…` : it.industry,
    );
    const fullNames = items.map((it) => it.industry);
    const values = items.map((it) => parseFloat(it.percentage));
    const colors = items.map((_, idx) => INDUSTRY_COLORS[idx % INDUSTRY_COLORS.length]);

    return {
      grid: { left: 72, right: 16, top: 16, bottom: 16 },
      tooltip: {
        trigger: "axis",
        axisPointer: { type: "shadow" },
        formatter: (params: unknown) => {
          const list = Array.isArray(params) ? params : [params];
          const first = list[0] as { dataIndex?: number; value?: number } | undefined;
          const idx = first?.dataIndex ?? 0;
          const name = fullNames[idx] ?? "";
          const v = first?.value;
          return `${name}<br/>占比：${typeof v === "number" ? v.toFixed(2) : v}%`;
        },
      },
      xAxis: {
        type: "value",
        axisLabel: { formatter: "{value}%" },
      },
      yAxis: {
        type: "category",
        data: names,
        axisLabel: { fontSize: 11 },
      },
      series: [
        {
          type: "bar",
          data: values.map((v, i) => ({ value: v, itemStyle: { color: colors[i] } })),
          barMaxWidth: 22,
        },
      ],
    };
  }, [data]);

  return (
    <Card
      size="small"
      title="行业分布"
      extra={
        <Typography.Text type="secondary">
          {data?.num_days != null ? `${data.num_days} 天` : "—"} · 前十
        </Typography.Text>
      }
    >
      {query.isLoading ? (
        <div style={{ textAlign: "center", padding: 24 }}>
          <Spin />
        </div>
      ) : data && data.items.length > 0 ? (
        <>
          {chartOption ? (
            <ReactECharts option={chartOption} style={{ height: 260 }} notMerge lazyUpdate />
          ) : null}
          <Table
            size="small"
            pagination={false}
            dataSource={data.items.slice(0, 5).map((row, idx) => ({
              key: row.industry,
              ...row,
              color: INDUSTRY_COLORS[idx % INDUSTRY_COLORS.length],
            }))}
            columns={[
              {
                title: "行业",
                dataIndex: "industry",
                render: (text: string, record: { color: string }) => (
                  <span style={{ display: "flex", alignItems: "center", gap: 8 }}>
                    <span
                      style={{
                        width: 10,
                        height: 10,
                        borderRadius: 999,
                        background: record.color,
                        flexShrink: 0,
                      }}
                    />
                    <span style={{ fontWeight: 500 }}>{text}</span>
                  </span>
                ),
              },
              {
                title: "日均(亿)",
                dataIndex: "avg_daily_balance",
                align: "right",
                render: (v: string) => formatAmountYi(v),
              },
              {
                title: "占比",
                dataIndex: "percentage",
                align: "right",
                render: (v: string) => `${v}%`,
              },
              {
                title: "收益率",
                dataIndex: "weighted_rate",
                align: "right",
                render: (v: string | null) => formatRatePercent(v),
              },
            ]}
          />
        </>
      ) : (
        <Typography.Text type="secondary">暂无数据</Typography.Text>
      )}
    </Card>
  );
}
