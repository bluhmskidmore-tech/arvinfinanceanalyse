import { useMemo } from "react";
import { useQuery } from "@tanstack/react-query";
import { Card, Spin, Table, Typography } from "antd";

import { useApiClient } from "../../../api/client";
import type { RatingStatsResponse } from "../../../api/contracts";
import ReactECharts, { type EChartsOption } from "../../../lib/echarts";
import { formatAmountYi, formatRatePercent } from "../utils/format";

const RATING_COLORS: Record<string, string> = {
  AAA: "#22c55e",
  "AA+": "#84cc16",
  AA: "#eab308",
  "AA-": "#f97316",
  "A+": "#ef4444",
  A: "#dc2626",
  "A-": "#b91c1c",
  未评级: "#94a3b8",
};

function ratingColor(rating: string, index: number): string {
  if (RATING_COLORS[rating]) {
    return RATING_COLORS[rating];
  }
  const palette = ["#3b82f6", "#8b5cf6", "#ec4899", "#14b8a6", "#f59e0b"];
  return palette[index % palette.length];
}

type Props = {
  startDate: string | null;
  endDate: string | null;
  subType?: string | null;
};

export default function RatingDistributionCard({ startDate, endDate, subType }: Props) {
  const client = useApiClient();

  const query = useQuery({
    queryKey: ["positions", "stats-rating", client.mode, startDate, endDate, subType ?? ""],
    queryFn: async (): Promise<RatingStatsResponse> => {
      if (!startDate || !endDate) {
        throw new Error("missing range");
      }
      const envelope = await client.getPositionsStatsRating({
        startDate,
        endDate,
        subType: subType ?? null,
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
    const pieData = data.items.map((it, idx) => ({
      name: it.rating,
      value: parseFloat(it.percentage),
      itemStyle: { color: ratingColor(it.rating, idx) },
    }));
    return {
      tooltip: { trigger: "item", formatter: "{b}: {c}% ({d}%)" },
      series: [
        {
          type: "pie",
          radius: ["42%", "72%"],
          avoidLabelOverlap: true,
          data: pieData,
          label: {
            formatter: "{b} {d}%",
          },
        },
      ],
    };
  }, [data]);

  return (
    <Card
      size="small"
      title="评级分布"
      extra={
        <Typography.Text type="secondary">
          {data?.num_days != null ? `${data.num_days} 天` : "—"} · 利率债默认 AAA
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
            <ReactECharts option={chartOption} style={{ height: 220 }} notMerge lazyUpdate />
          ) : null}
          <Table
            size="small"
            pagination={false}
            dataSource={data.items.map((row, idx) => ({
              key: row.rating,
              ...row,
              dot: ratingColor(row.rating, idx),
            }))}
            columns={[
              {
                title: "评级",
                dataIndex: "rating",
                render: (text: string, record: { dot: string }) => (
                  <span style={{ display: "flex", alignItems: "center", gap: 8 }}>
                    <span
                      style={{
                        width: 10,
                        height: 10,
                        borderRadius: 999,
                        background: record.dot,
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
