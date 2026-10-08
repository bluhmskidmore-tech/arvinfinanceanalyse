import type { EChartsOption } from "../../../lib/echarts";
import type { Numeric } from "../../../api/contracts";
import { bondNumericRaw } from "../adapters/bondAnalyticsAdapter";
import type {
  CreditSpreadAnalysisResponse,
  ConcentrationMetrics,
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
    },
    tooltip: { trigger: "axis" },
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
    },
    tooltip: {
      trigger: "axis",
      axisPointer: { type: "shadow" },
      formatter: (params: unknown) => {
        const list = Array.isArray(params) ? params : [params];
        const p = list[0] as { name?: string; value?: number | null };
        const value = typeof p.value === "number" ? `${p.value}%` : EM_DASH;
        const content = document.createElement("div");
        content.append(p.name ?? "", document.createElement("br"), `${yAxisName}：${value}`);
        return content;
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
        const content = document.createElement("div");
        content.append(d.name, document.createElement("br"), `市值：${formatYi(d.marketValueRaw)}`, document.createElement("br"), `权重：${d.weight.display}`);
        return content;
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
