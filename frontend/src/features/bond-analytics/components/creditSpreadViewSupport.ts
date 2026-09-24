import type { EChartsOption } from "../../../lib/echarts";
import type { Numeric } from "../../../api/contracts";
import { bondNumericRaw } from "../adapters/bondAnalyticsAdapter";
import type {
  CreditSpreadAnalysisResponse,
  ConcentrationMetrics,
  CreditSpreadBondDetailRow,
  CreditSpreadMigrationResponse,
} from "../types";
import { designTokens, nocturneTokens, tabularNumsStyle } from "../../../theme/designSystem";
import { EM_DASH } from "../../../utils/format";
import { formatWan, formatYi, formatBp } from "../utils/formatters";

const dt = designTokens;
/* ECharts canvas 不消费 CSS 变量：图表取色统一走 Nocturne 常量组（与页面 scope 同源）。 */
const nct = nocturneTokens.color;

export const spreadColumns = [
  { title: "情景", dataIndex: "scenario_name", key: "scenario_name" },
  {
    title: "利差变动 (bp)",
    dataIndex: "spread_change_bp",
    key: "spread_change_bp",
    render: (v: Numeric) => v.display,
    onCell: () => ({ style: tabularNumsStyle }),
  },
  {
    title: "总影响",
    dataIndex: "pnl_impact",
    key: "pnl_impact",
    render: formatWan,
    onCell: () => ({ style: tabularNumsStyle }),
  },
  {
    title: "OCI影响",
    dataIndex: "oci_impact",
    key: "oci_impact",
    render: formatWan,
    onCell: () => ({ style: tabularNumsStyle }),
  },
  {
    title: "TPL影响",
    dataIndex: "tpl_impact",
    key: "tpl_impact",
    render: formatWan,
    onCell: () => ({ style: tabularNumsStyle }),
  },
];

export const migrationColumns = [
  { title: "情景", dataIndex: "scenario_name", key: "scenario_name" },
  { title: "原评级", dataIndex: "from_rating", key: "from_rating" },
  { title: "目标评级", dataIndex: "to_rating", key: "to_rating" },
  {
    title: "涉及债券",
    dataIndex: "affected_bonds",
    key: "affected_bonds",
    /* 缺失 ≠ 0：client 对字段缺失透传 null，这里渲染 —，不显示假「0 只」。 */
    render: (v: number | null) => (v === null || v === undefined ? EM_DASH : v),
    onCell: () => ({ style: tabularNumsStyle }),
  },
  {
    title: "涉及市值",
    dataIndex: "affected_market_value",
    key: "affected_market_value",
    render: formatYi,
    onCell: () => ({ style: tabularNumsStyle }),
  },
  {
    title: "损益影响",
    dataIndex: "pnl_impact",
    key: "pnl_impact",
    render: formatWan,
    onCell: () => ({ style: tabularNumsStyle }),
  },
];

export const issuerConcentrationColumns = [
  { title: "名称", dataIndex: "name", key: "name" },
  {
    title: "权重",
    dataIndex: "weight",
    key: "weight",
    onCell: () => ({ style: tabularNumsStyle }),
  },
  {
    title: "市值",
    dataIndex: "market_value",
    key: "market_value",
    render: formatYi,
    onCell: () => ({ style: tabularNumsStyle }),
  },
];

export const spreadDetailColumns = [
  { title: "债券代码", dataIndex: "instrument_code", key: "instrument_code" },
  { title: "债券名称", dataIndex: "instrument_name", key: "instrument_name" },
  { title: "评级", dataIndex: "rating", key: "rating" },
  { title: "期限桶", dataIndex: "tenor_bucket", key: "tenor_bucket" },
  {
    title: "YTM",
    dataIndex: "ytm",
    key: "ytm",
    render: (value: string) => formatPctPoint(value),
    onCell: () => ({ style: tabularNumsStyle }),
  },
  {
    title: "国债基准",
    dataIndex: "benchmark_yield",
    key: "benchmark_yield",
    render: (value: string) => formatPctPoint(value),
    onCell: () => ({ style: tabularNumsStyle }),
  },
  {
    title: "利差",
    dataIndex: "credit_spread",
    key: "credit_spread",
    render: (value: string) => formatBp(value),
    onCell: () => ({ style: tabularNumsStyle }),
  },
  {
    title: "市值",
    dataIndex: "market_value",
    key: "market_value",
    render: formatYi,
    onCell: () => ({ style: tabularNumsStyle }),
  },
];

const CONCENTRATION_KEYS = [
  "concentration_by_issuer",
  "concentration_by_industry",
  "concentration_by_rating",
  "concentration_by_tenor",
] as const satisfies readonly (keyof Pick<
  CreditSpreadMigrationResponse,
  | "concentration_by_issuer"
  | "concentration_by_industry"
  | "concentration_by_rating"
  | "concentration_by_tenor"
>)[];

export function hasAnyConcentrationField(data: CreditSpreadMigrationResponse): boolean {
  return CONCENTRATION_KEYS.some((k) => data[k] != null);
}

/** X 轴期限桶（与后端 tenor_bucket 对齐后映射到此顺序） */
const CREDIT_DIST_TENOR_LABELS = ["1Y", "2Y", "3Y", "5Y", "7Y", "10Y", "20Y", "30Y"] as const;

/** Y 轴评级桶 */
const CREDIT_DIST_RATING_LABELS = ["AAA", "AA+", "AA", "AA-", "A+", "其他"] as const;

const PRIMARY_RATING_SET = new Set<string>(CREDIT_DIST_RATING_LABELS.filter((r) => r !== "其他"));

function mapTenorBucketToXIndex(raw: string | undefined): number | null {
  if (raw == null || String(raw).trim() === "") return null;
  const t = String(raw).trim().toUpperCase();
  const table: Record<string, number> = {
    "1M": 0,
    "3M": 0,
    "6M": 0,
    "9M": 0,
    "1Y": 0,
    "2Y": 1,
    "3Y": 2,
    "4Y": 2,
    "5Y": 3,
    "6Y": 3,
    "7Y": 4,
    "10Y": 5,
    "15Y": 5,
    "20Y": 6,
    "30Y": 7,
  };
  const idx = table[t];
  return idx === undefined ? null : idx;
}

function mapRatingToBucket(raw: string | undefined): string | null {
  if (raw == null || String(raw).trim() === "") return null;
  const up = String(raw).trim().toUpperCase();
  if (PRIMARY_RATING_SET.has(up)) return up;
  return "其他";
}

/** 将 bond 明细按评级×期限累加市值，再按信用债总市值换算占比（仅展示层聚合） */
export function buildRatingTenorHeatmapData(
  bondDetails: CreditSpreadBondDetailRow[],
  creditMarketValueField: Numeric | string,
): { seriesData: [number, number, number][]; maxPct: number } | null {
  const denom = bondNumericRaw(creditMarketValueField);
  if (denom === null || denom <= 0) return null;

  const sums = new Map<string, number>();
  let anyMapped = false;
  for (const row of bondDetails) {
    const yKey = mapRatingToBucket(row.rating);
    const xi = mapTenorBucketToXIndex(row.tenor_bucket);
    if (yKey == null || xi == null) continue;
    const mv = bondNumericRaw(row.market_value);
    if (mv === null || mv <= 0) continue;
    anyMapped = true;
    const key = `${yKey}|${xi}`;
    sums.set(key, (sums.get(key) ?? 0) + mv);
  }
  if (!anyMapped) return null;

  const seriesData: [number, number, number][] = [];
  let maxPct = 0;
  for (let yi = 0; yi < CREDIT_DIST_RATING_LABELS.length; yi++) {
    const rating = CREDIT_DIST_RATING_LABELS[yi];
    for (let xi = 0; xi < CREDIT_DIST_TENOR_LABELS.length; xi++) {
      const v = sums.get(`${rating}|${xi}`) ?? 0;
      const pct = (v / denom) * 100;
      if (pct > maxPct) maxPct = pct;
      seriesData.push([xi, yi, Number(pct.toFixed(4))]);
    }
  }
  if (maxPct <= 0) return null;
  return { seriesData, maxPct };
}

function formatPctPoint(value: string | null | undefined): string {
  const num = parseFloat(String(value ?? ""));
  if (!Number.isFinite(num)) return EM_DASH;
  return `${num.toFixed(2)}%`;
}

export function formatPercentile(value: string | null | undefined): string {
  const num = parseFloat(String(value ?? ""));
  if (!Number.isFinite(num)) return EM_DASH;
  return `${num.toFixed(1)}%`;
}

export function formatBpOrDash(value: string | null | undefined): string {
  return value == null ? EM_DASH : formatBp(value);
}

export function spreadTermStructureOption(
  points: CreditSpreadAnalysisResponse["spread_term_structure"],
): EChartsOption | null {
  if (!points.length) return null;
  return {
    grid: {
      left: dt.space[9],
      right: dt.space[4],
      top: dt.space[6],
      bottom: dt.space[6] + dt.space[1],
      containLabel: false,
    },
    tooltip: { trigger: "axis" },
    legend: { top: 0, textStyle: { fontSize: dt.fontSize[11], color: nct.inkMuted } },
    xAxis: {
      type: "category",
      data: points.map((point) => point.tenor_bucket),
      axisLabel: { color: nct.inkMuted, fontSize: dt.fontSize[11] },
      axisLine: { lineStyle: { color: nct.lineSoft } },
    },
    yAxis: {
      type: "value",
      axisLabel: { color: nct.inkMuted, fontSize: dt.fontSize[11], formatter: "{value} bp" },
      splitLine: { lineStyle: { color: nct.lineSoft, type: "dashed", opacity: 0.35 } },
    },
    series: [
      {
        name: "平均",
        type: "line",
        smooth: true,
        data: points.map((point) => Number(point.avg_spread_bps)),
        itemStyle: { color: nct.blue },
        lineStyle: { width: 2 },
      },
      {
        name: "最小",
        type: "line",
        data: points.map((point) => Number(point.min_spread_bps)),
        itemStyle: { color: nct.green },
        lineStyle: { type: "dashed" },
      },
      {
        name: "最大",
        type: "line",
        data: points.map((point) => Number(point.max_spread_bps)),
        itemStyle: { color: nct.amber },
        lineStyle: { type: "dashed" },
      },
    ],
  };
}

export function concentrationBarOption(
  metrics: ConcentrationMetrics | undefined,
  color: string,
  yAxisName: string,
): EChartsOption | null {
  const items = metrics?.top_items;
  if (!items?.length) return null;
  const names = items.map((it) => it.name);
  const pcts = items.map((it) => {
    const w = bondNumericRaw(it.weight);
    return w === null ? null : Number((w * 100).toFixed(4));
  });
  return {
    grid: {
      left: dt.space[9],
      right: dt.space[3],
      top: dt.space[6] + dt.space[1],
      bottom: names.some((n) => n.length > 6) ? dt.space[9] + dt.space[1] : dt.space[4] + dt.space[5],
      containLabel: false,
    },
    tooltip: {
      trigger: "axis",
      axisPointer: { type: "shadow" },
      formatter: (params: unknown) => {
        const list = Array.isArray(params) ? params : [params];
        const p = list[0] as { name?: string; value?: number | null };
        const value = typeof p.value === "number" ? `${p.value}%` : EM_DASH;
        return `${p.name ?? ""}<br/>${yAxisName}：${value}`;
      },
    },
    xAxis: {
      type: "category",
      data: names,
      axisLabel: {
        color: nct.inkMuted,
        fontSize: dt.fontSize[11],
        interval: 0,
        rotate: names.length > 5 ? 28 : 0,
      },
      axisLine: { lineStyle: { color: nct.lineSoft } },
    },
    yAxis: {
      type: "value",
      name: yAxisName,
      nameTextStyle: { color: nct.inkMuted, fontSize: dt.fontSize[11] },
      axisLabel: { color: nct.inkMuted, fontSize: dt.fontSize[11], formatter: "{value}%" },
      splitLine: { lineStyle: { color: nct.lineSoft, type: "dashed", opacity: 0.35 } },
    },
    series: [
      {
        type: "bar",
        name: yAxisName,
        barMaxWidth: 40,
        itemStyle: { color },
        data: pcts,
      },
    ],
  };
}

export function ratingTenorHeatmapOption(seriesData: [number, number, number][], maxPct: number): EChartsOption {
  const vmax = Math.max(maxPct, 1e-6);
  return {
    tooltip: {
      position: "top",
      formatter: (raw: unknown) => {
        const p = raw as { value?: [number, number, number] | number };
        const val = Array.isArray(p.value) ? p.value : [];
        const xi = Number(val[0]);
        const yi = Number(val[1]);
        const v = Number(val[2]);
        const tenor = CREDIT_DIST_TENOR_LABELS[xi] ?? "";
        const rating = CREDIT_DIST_RATING_LABELS[yi] ?? "";
        return `${rating} × ${tenor}<br/>市值占比：${Number.isFinite(v) ? v.toFixed(2) : EM_DASH}%`;
      },
    },
    grid: {
      left: dt.space[9] + dt.space[2],
      right: dt.space[6],
      top: dt.space[4],
      bottom: dt.space[9] + dt.space[2],
      containLabel: true,
    },
    xAxis: {
      type: "category",
      data: [...CREDIT_DIST_TENOR_LABELS],
      splitArea: { show: true },
      axisLabel: { color: nct.inkMuted, fontSize: dt.fontSize[11] },
      axisLine: { lineStyle: { color: nct.lineSoft } },
    },
    yAxis: {
      type: "category",
      data: [...CREDIT_DIST_RATING_LABELS],
      splitArea: { show: true },
      axisLabel: { color: nct.inkMuted, fontSize: dt.fontSize[11] },
      axisLine: { lineStyle: { color: nct.lineSoft } },
    },
    visualMap: {
      min: 0,
      max: vmax,
      calculable: true,
      orient: "horizontal",
      left: "center",
      bottom: dt.space[1],
      itemWidth: dt.space[3],
      itemHeight: 120,
      inRange: { color: [nct.accent300, nct.blue] },
      textStyle: { fontSize: dt.fontSize[11], color: nct.inkMuted },
      formatter: (min, _max) => `${Number(min).toFixed(1)}%`,
    },
    series: [
      {
        type: "heatmap",
        data: seriesData,
        label: {
          show: true,
          fontSize: dt.fontSize[11],
          color: nct.inkSoft,
          formatter: (params: unknown) => {
            const raw = (params as { value?: unknown }).value;
            const tuple = Array.isArray(raw) ? raw : [];
            const v = Number(tuple[2]);
            if (!Number.isFinite(v) || v === 0) return "";
            return v < 0.05 ? "" : `${v.toFixed(1)}%`;
          },
        },
        emphasis: {
          itemStyle: { shadowBlur: dt.space[2], shadowColor: nct.lineSoft },
        },
      },
    ],
  };
}

const ISSUER_SLICE_COLORS = [nct.blue, nct.amber, nct.green, nct.red, nct.inkMuted];

export function buildIssuerConcentrationPieOption(metrics: ConcentrationMetrics): EChartsOption {
  const pieData = metrics.top_items.map((it, idx) => ({
    name: it.name,
    value: bondNumericRaw(it.market_value) ?? undefined,
    marketValueRaw: it.market_value,
    weight: it.weight,
    itemStyle: { color: ISSUER_SLICE_COLORS[idx % ISSUER_SLICE_COLORS.length] },
  }));

  return {
    tooltip: {
      trigger: "item" as const,
      formatter: (params: unknown) => {
        const d = (params as { data?: unknown }).data as
          | { name: string; marketValueRaw: Numeric; weight: Numeric }
          | undefined;
        if (!d || typeof d !== "object") return "";
        return `${d.name}<br/>市值：${formatYi(d.marketValueRaw)}<br/>权重：${d.weight.display}`;
      },
    },
    graphic: {
      elements: [
        {
          type: "text" as const,
          left: "center",
          top: "center",
          style: {
            text: "发行人集中度",
            fill: nct.ink,
            fontSize: dt.fontSize[14],
            fontWeight: 500,
          },
        },
      ],
    },
    series: [
      {
        type: "pie" as const,
        radius: ["42%", "68%"],
        center: ["50%", "50%"],
        avoidLabelOverlap: true,
        label: {
          show: true,
          formatter: "{b}: {d}%",
        },
        data: pieData,
      },
    ],
  };
}

export function normalizeClientError(message: string): string {
  const match = message.match(/\((\d{3})\)\s*$/);
  if (match?.[1]) {
    return `HTTP ${match[1]}`;
  }
  return message;
}
