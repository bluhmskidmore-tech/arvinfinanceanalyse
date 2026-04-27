import ReactECharts, { type EChartsOption } from "../../lib/echarts";

export type AccountingBasisStackedSharePoint = {
  monthLabel: string;
  AC: number;
  OCI: number;
  TPL: number;
  acValueYi?: number;
  ociValueYi?: number;
  tplValueYi?: number;
  totalValueYi?: number;
};

const basisSeries = [
  { key: "AC", name: "AC", color: "#10284a" },
  { key: "OCI", name: "OCI", color: "#33689a" },
  { key: "TPL", name: "TPL", color: "#d8d8d8" },
] as const;

function formatPct(value: number) {
  return `${value.toFixed(2)}%`;
}

function formatYi(value: number | undefined) {
  return value === undefined || Number.isNaN(value) ? "-" : `${value.toFixed(2)} 亿`;
}

function dataIndexFromTooltip(params: unknown) {
  const first = Array.isArray(params) ? params[0] : params;
  if (!first || typeof first !== "object" || !("dataIndex" in first)) {
    return 0;
  }
  const dataIndex = Number((first as { dataIndex?: unknown }).dataIndex);
  return Number.isFinite(dataIndex) ? dataIndex : 0;
}

function labelValue(params: unknown) {
  if (!params || typeof params !== "object" || !("value" in params)) {
    return 0;
  }
  const value = Number((params as { value?: unknown }).value);
  return Number.isFinite(value) ? value : 0;
}

function buildOption(rows: AccountingBasisStackedSharePoint[], title: string): EChartsOption {
  const series = basisSeries.map((seriesItem) => ({
    name: seriesItem.name,
    type: "bar" as const,
    stack: "accounting-basis-share",
    barWidth: 46,
    data: rows.map((row) => row[seriesItem.key]),
    itemStyle: { color: seriesItem.color },
    label: {
      show: true,
      position: "inside" as const,
      color: seriesItem.key === "TPL" ? "#334155" : "#ffffff",
      fontSize: 12,
      fontWeight: 600,
      formatter: (params: unknown) => {
        const value = labelValue(params);
        return value >= 7 ? formatPct(value) : "";
      },
    },
  }));

  return {
    title: {
      text: title,
      left: 0,
      top: 0,
      textStyle: { fontSize: 16, fontWeight: 700, color: "#2f3744" },
    },
    legend: {
      bottom: 0,
      data: basisSeries.map((item) => item.name),
      itemWidth: 28,
      itemHeight: 10,
    },
    tooltip: {
      trigger: "axis",
      axisPointer: { type: "shadow" },
      formatter: (params: unknown) => {
        const row = rows[dataIndexFromTooltip(params)];
        if (!row) return "";
        return [
          row.monthLabel,
          `AC: ${formatPct(row.AC)} / ${formatYi(row.acValueYi)}`,
          `OCI: ${formatPct(row.OCI)} / ${formatYi(row.ociValueYi)}`,
          `TPL: ${formatPct(row.TPL)} / ${formatYi(row.tplValueYi)}`,
          `合计: ${formatYi(row.totalValueYi)}`,
        ].join("<br/>");
      },
    },
    grid: { left: 36, right: 24, top: 54, bottom: 72 },
    xAxis: {
      type: "category",
      data: rows.map((row) => row.monthLabel),
      axisTick: { alignWithLabel: true },
      axisLabel: { fontSize: 12, color: "#555", interval: 0 },
    },
    yAxis: {
      type: "value",
      max: 100,
      axisLabel: { formatter: (value: number) => `${value.toFixed(0)}%` },
      splitLine: { lineStyle: { color: "#eceff3" } },
    },
    series,
  };
}

type AccountingBasisStackedShareChartProps = {
  rows: AccountingBasisStackedSharePoint[];
  title: string;
  height?: number;
};

export default function AccountingBasisStackedShareChart({
  rows,
  title,
  height = 390,
}: AccountingBasisStackedShareChartProps) {
  return (
    <ReactECharts
      option={buildOption(rows, title)}
      style={{ height, width: "100%" }}
      notMerge
      lazyUpdate
    />
  );
}
