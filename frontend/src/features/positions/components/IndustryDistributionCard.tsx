import { useMemo } from "react";
import { useQuery } from "@tanstack/react-query";
import { Spin, Table } from "antd";
import type { TableColumnsType } from "antd";

import { useApiClient } from "../../../api/client";
import type { IndustryStatItem } from "../../../api/contracts";
import ReactECharts, { type EChartsOption } from "../../../lib/echarts";
import { nocturneTokens } from "../../../theme/designSystem";
import { EM_DASH } from "../../../utils/format";
import { POSITIONS_QUERY_STALE_TIME_MS } from "../model/positionsPageModel";
import { formatAmountYi, formatPercentValue, formatRatePercent } from "../utils/format";

/*
 * Nocturne 深色系列色板（canvas 读不到 CSS 变量，走 designSystem.ts 的 TS 镜像）。
 * 与 RatingDistributionCard 及 PositionsBondsSections.css 的
 * positions-bonds-dist__dot--p* 类保持同序同色。
 */
const SERIES_PALETTE = [
  nocturneTokens.color.blue,
  nocturneTokens.color.green,
  nocturneTokens.color.amber,
  nocturneTokens.color.accent400,
  nocturneTokens.color.inkSoft,
  nocturneTokens.color.accent300,
] as const;

function industryPaletteIndex(index: number): number {
  return index % SERIES_PALETTE.length;
}

type IndustryRow = IndustryStatItem & { key: string; paletteIndex: number };

const INDUSTRY_COLUMNS: TableColumnsType<IndustryRow> = [
  {
    title: "行业",
    dataIndex: "industry",
    render: (text: string, record: IndustryRow) => (
      <span className="positions-bonds-dist__legend">
        <span
          className={`positions-bonds-dist__dot positions-bonds-dist__dot--p${record.paletteIndex}`}
        />
        <span className="positions-bonds-dist__legend-label">{text}</span>
      </span>
    ),
  },
  {
    title: "日均",
    dataIndex: "avg_daily_balance",
    align: "right",
    className: "positions-view__num-cell",
    render: (v: string) => formatAmountYi(v),
  },
  {
    title: "占比",
    dataIndex: "percentage",
    align: "right",
    className: "positions-view__num-cell",
    render: (v: string) => formatPercentValue(v),
  },
  {
    title: "只数",
    dataIndex: "bond_count",
    align: "right",
    className: "positions-view__num-cell",
    render: (v: number | null | undefined) => (v != null ? `${v}` : EM_DASH),
  },
  {
    title: "收益率",
    dataIndex: "weighted_rate",
    align: "right",
    className: "positions-view__num-cell",
    render: (v: string | null) => formatRatePercent(v),
  },
];

type Props = {
  startDate: string | null;
  endDate: string | null;
  subType?: string | null;
};

export default function IndustryDistributionCard({ startDate, endDate, subType }: Props) {
  const client = useApiClient();

  /* queryKey/queryFn 与质量面板完全一致（返回整只信封），同参数只发一次请求。 */
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
      return client.getPositionsStatsIndustry({
        startDate,
        endDate,
        subType: subType ?? null,
        topN: 10,
      });
    },
    enabled: Boolean(startDate && endDate),
    staleTime: POSITIONS_QUERY_STALE_TIME_MS,
    retry: false,
  });

  const data = query.data?.result;
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
    const colors = items.map((_, idx) => SERIES_PALETTE[industryPaletteIndex(idx)]);

    return {
      grid: { left: 72, right: 16, top: 16, bottom: 16 },
      tooltip: {
        trigger: "axis",
        axisPointer: { type: "shadow" },
        backgroundColor: nocturneTokens.color.panel2,
        borderColor: nocturneTokens.color.line,
        borderWidth: 1,
        textStyle: { color: nocturneTokens.color.ink, fontSize: 11 },
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
        axisLabel: {
          formatter: "{value}%",
          color: nocturneTokens.color.inkMuted,
          fontSize: 11,
        },
        splitLine: {
          lineStyle: { type: "dashed", color: nocturneTokens.color.lineSoft },
        },
      },
      yAxis: {
        type: "category",
        data: names,
        axisLabel: { fontSize: 11, color: nocturneTokens.color.inkMuted },
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

  const rows = useMemo<IndustryRow[]>(
    () =>
      (data?.items ?? []).slice(0, 5).map((row, idx) => ({
        key: row.industry,
        ...row,
        paletteIndex: industryPaletteIndex(idx),
      })),
    [data?.items],
  );

  return (
    <section className="positions-view__panel">
      <div className="positions-view__panel-head">
        <h3 className="positions-view__panel-title">行业分布</h3>
        <span className="positions-view__panel-hint">
          {data?.num_days != null ? `${data.num_days} 天` : EM_DASH} / 前十
        </span>
      </div>
      {!startDate || !endDate ? (
        <p className="positions-view__table-state">请先选择可用报告日</p>
      ) : query.isLoading ? (
        <div className="positions-view__table-state positions-view__table-state--loading">
          <Spin />
        </div>
      ) : query.isError ? (
        <p className="positions-view__table-state">行业分布暂不可用</p>
      ) : data && data.items.length > 0 ? (
        <>
          {chartOption ? (
            <ReactECharts
              option={chartOption}
              className="positions-bonds-dist__chart positions-bonds-dist__chart--industry"
              notMerge
              lazyUpdate
            />
          ) : null}
          <Table
            size="small"
            className="positions-view__table"
            pagination={false}
            scroll={{ x: "max-content" }}
            dataSource={rows}
            columns={INDUSTRY_COLUMNS}
          />
        </>
      ) : (
        <p className="positions-view__table-state">暂无数据</p>
      )}
    </section>
  );
}
