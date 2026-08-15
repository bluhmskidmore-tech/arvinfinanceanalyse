import { useMemo } from "react";
import { useQuery } from "@tanstack/react-query";
import { Spin, Table } from "antd";
import type { TableColumnsType } from "antd";

import { useApiClient } from "../../../api/client";
import type { RatingStatItem, RatingStatsResponse } from "../../../api/contracts";
import { type EChartsOption } from "../../../lib/echarts";
import { BaseChart } from "../../../components/charts/BaseChart";
import { nocturneTokens } from "../../../theme/designSystem";
import { EM_DASH } from "../../../utils/format";
import { POSITIONS_QUERY_STALE_TIME_MS } from "../model/positionsPageModel";
import { formatAmountYiNumber, formatPercentValue, formatRatePercent } from "../utils/format";

/*
 * Nocturne 深色系列色板（canvas 读不到 CSS 变量，走 designSystem.ts 的 TS 镜像；
 * 组合工作台 PortfolioStructureChart 同款先例）。表格图例色点的 CSS 类
 * （PositionsBondsSections.css 的 positions-bonds-dist__dot--*）按同序引用
 * --dh-api-* / --nct-* 变量，两侧必须保持同序同色。
 */
const SERIES_PALETTE = [
  nocturneTokens.color.blue,
  nocturneTokens.color.green,
  nocturneTokens.color.amber,
  nocturneTokens.color.accent400,
  nocturneTokens.color.inkSoft,
  nocturneTokens.color.accent300,
] as const;

/** 违约与 B 档及以下是风险警戒语义，固定去饱和红，不参与色板轮换。 */
const NEGATIVE_COLOR = nocturneTokens.color.red;

/** 未评级/未知档不伪装成任何评级档位，走中性灰（bond-dashboard 同制度）。 */
const UNRATED_COLOR = nocturneTokens.color.inkMuted;

/*
 * 评级色阶对齐 bond-dashboard CreditRatingBlocks：高评级沿 accent 冷色阶
 * 渐进（AAA 最深），AA- 中性过渡；A 档进入琥珀警戒。评级恶化是警戒语义
 * （琥珀/红），不占用涨跌绿/红。索引指向 SERIES_PALETTE。
 */
const RATING_PALETTE_INDEX: Record<string, number> = {
  AAA: 0, // blue
  "AA+": 3, // accent400
  AA: 5, // accent300
  "AA-": 4, // inkSoft（中性过渡）
  "A+": 2, // amber
  A: 2,
  "A-": 2,
};

type PaletteKey = "neg" | "unrated" | `p${number}`;

function ratingPaletteKey(rating: string): PaletteKey {
  const raw = rating.trim();
  if (raw === "未评级" || raw === "") {
    return "unrated";
  }
  const key = raw.toUpperCase();
  if (raw === "违约" || /^[BCD]/.test(key)) {
    return "neg";
  }
  const idx = RATING_PALETTE_INDEX[key];
  if (idx != null) {
    return `p${idx}`;
  }
  // 未登记的 A 系变体按琥珀警戒兜底，其余未知档位走中性灰。
  return key.includes("A") ? "p2" : "unrated";
}

function paletteColor(key: PaletteKey): string {
  if (key === "neg") {
    return NEGATIVE_COLOR;
  }
  if (key === "unrated") {
    return UNRATED_COLOR;
  }
  return SERIES_PALETTE[Number(key.slice(1)) % SERIES_PALETTE.length];
}

type RatingRow = RatingStatItem & { key: string; paletteKey: PaletteKey };

const RATING_COLUMNS: TableColumnsType<RatingRow> = [
  {
    title: "评级",
    dataIndex: "rating",
    render: (text: string, record: RatingRow) => (
      <span className="positions-bonds-dist__legend">
        <span
          className={`positions-bonds-dist__dot positions-bonds-dist__dot--${record.paletteKey}`}
        />
        <span className="positions-bonds-dist__legend-label">{text}</span>
      </span>
    ),
  },
  {
    title: "日均(亿元)",
    dataIndex: "avg_daily_balance",
    align: "right",
    className: "positions-view__num-cell",
    render: (v: string) => formatAmountYiNumber(v),
  },
  {
    title: "占比",
    dataIndex: "percentage",
    align: "right",
    className: "positions-view__num-cell",
    render: (v: string) => formatPercentValue(v),
  },
  {
    /* bond_count 是区间内 bond-days 累计（AAA 可达 22 万+），不是组合持券只数。 */
    title: <span title="区间内逐日持仓记录累计">笔数(区间)</span>,
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

export default function RatingDistributionCard({ startDate, endDate, subType }: Props) {
  const client = useApiClient();

  /* queryKey/queryFn 与质量面板完全一致（返回整只信封），同参数只发一次请求。 */
  const query = useQuery({
    queryKey: ["positions", "stats-rating", client.mode, startDate, endDate, subType ?? ""],
    queryFn: async () => {
      if (!startDate || !endDate) {
        throw new Error("missing range");
      }
      return client.getPositionsStatsRating({
        startDate,
        endDate,
        subType: subType ?? null,
      });
    },
    enabled: Boolean(startDate && endDate),
    staleTime: POSITIONS_QUERY_STALE_TIME_MS,
    retry: false,
  });

  const data: RatingStatsResponse | undefined = query.data?.result;

  const rows = useMemo<RatingRow[]>(
    () =>
      (data?.items ?? []).map((row) => ({
        key: row.rating,
        ...row,
        paletteKey: ratingPaletteKey(row.rating),
      })),
    [data?.items],
  );

  const chartOption = useMemo((): EChartsOption | null => {
    if (!rows.length) {
      return null;
    }
    /* 占比 <1% 的薄片不出引导标签（挤成一摞小字是版式噪音），明细看下表。 */
    const pieData = rows.map((it) => {
      const value = parseFloat(it.percentage);
      const showLabel = Number.isFinite(value) && value >= 1;
      return {
        name: it.rating,
        value,
        itemStyle: { color: paletteColor(it.paletteKey) },
        label: { show: showLabel },
        labelLine: { show: showLabel },
      };
    });
    return {
      tooltip: {
        trigger: "item",
        formatter: "{b}: {c}% ({d}%)",
        backgroundColor: nocturneTokens.color.panel2,
        borderColor: nocturneTokens.color.line,
        borderWidth: 1,
        textStyle: { color: nocturneTokens.color.ink, fontSize: 11 },
      },
      series: [
        {
          type: "pie",
          radius: ["42%", "72%"],
          avoidLabelOverlap: true,
          data: pieData,
          label: {
            formatter: "{b} {d}%",
            color: nocturneTokens.color.inkSoft,
            fontSize: 11,
          },
          labelLine: {
            lineStyle: { color: nocturneTokens.color.line },
          },
        },
      ],
    };
  }, [rows]);

  return (
    <section className="positions-view__panel">
      <div className="positions-view__panel-head">
        <h3 className="positions-view__panel-title">评级收益率</h3>
        <span className="positions-view__panel-hint">
          {data?.num_days != null ? `${data.num_days} 天` : EM_DASH} / 利率债默认 AAA
        </span>
      </div>
      {!startDate || !endDate ? (
        <p className="positions-view__table-state">请先选择可用报告日</p>
      ) : query.isLoading ? (
        <div className="positions-view__table-state positions-view__table-state--loading">
          <Spin />
        </div>
      ) : query.isError ? (
        <p className="positions-view__table-state">评级分布暂不可用</p>
      ) : data && data.items.length > 0 ? (
        <>
          {chartOption ? <BaseChart option={chartOption} height={190} /> : null}
          <Table
            size="small"
            className="positions-view__table"
            pagination={false}
            scroll={{ x: "max-content" }}
            dataSource={rows}
            columns={RATING_COLUMNS}
          />
        </>
      ) : (
        <p className="positions-view__table-state">暂无数据</p>
      )}
    </section>
  );
}
