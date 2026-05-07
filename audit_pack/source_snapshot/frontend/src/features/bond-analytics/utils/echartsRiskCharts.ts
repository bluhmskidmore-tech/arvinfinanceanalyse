import type { EChartsOption } from "echarts";
import type { Numeric } from "../../../api/contracts";
import { designTokens } from "../../../theme/designSystem";
import { bondNumericRaw } from "../adapters/bondAnalyticsAdapter";
import type { AssetClassRiskSummary, KRDBucket } from "../types";
import { formatWan, formatYi } from "./formatters";

export const ECHARTS_RISK_TEXT = designTokens.color.neutral[700];
export const ECHARTS_RISK_GRID_LINE = designTokens.color.neutral[200];

const ASSET_CLASS_SLICE_COLORS: Record<string, string> = {
  rate: designTokens.color.info[500],
  credit: designTokens.color.warning[400],
  other: designTokens.color.neutral[500],
};

function hexToRgbTriple(hex: string): readonly [number, number, number] {
  const n = hex.replace("#", "");
  return [
    Number.parseInt(n.slice(0, 2), 16),
    Number.parseInt(n.slice(2, 4), 16),
    Number.parseInt(n.slice(4, 6), 16),
  ];
}

function lerpByte(a: number, b: number, t: number) {
  return Math.round(a + (b - a) * t);
}

const DV01_GRADIENT_LO = hexToRgbTriple(designTokens.color.primary[200]);
const DV01_GRADIENT_HI = hexToRgbTriple(designTokens.color.primary[700]);

/** 浅蓝 → 深蓝，按 DV01 数值在分桶内的相对大小着色。 */
function dv01GradientColor(dv01: number, min: number, max: number): string {
  const lo = DV01_GRADIENT_LO;
  const hi = DV01_GRADIENT_HI;
  let t = max > min ? (dv01 - min) / (max - min) : 0.5;
  t = Math.max(0, Math.min(1, t));
  const r = lerpByte(lo[0], hi[0], t);
  const g = lerpByte(lo[1], hi[1], t);
  const b = lerpByte(lo[2], hi[2], t);
  return `#${[r, g, b].map((x) => x.toString(16).padStart(2, "0")).join("")}`;
}

export function buildKrdDv01BarOption(buckets: KRDBucket[]): EChartsOption | null {
  if (!buckets.length) return null;
  const dv01Values = buckets.map((b) => {
    const n = bondNumericRaw(b.dv01);
    return Number.isFinite(n) ? n : 0;
  });
  const min = Math.min(...dv01Values);
  const max = Math.max(...dv01Values);
  return {
    backgroundColor: "transparent",
    textStyle: { color: ECHARTS_RISK_TEXT },
    grid: { left: 52, right: 24, top: 28, bottom: 32, containLabel: true },
    tooltip: {
      trigger: "axis",
      axisPointer: { type: "shadow" },
      formatter: (params: unknown) => {
        const arr = Array.isArray(params) ? params : [params];
        const p = arr[0] as { dataIndex?: number };
        const idx = typeof p.dataIndex === "number" ? p.dataIndex : 0;
        const b = buckets[idx];
        if (!b) return "";
        return `${b.tenor}<br/>DV01：${formatWan(b.dv01)}`;
      },
    },
    xAxis: {
      type: "category",
      data: buckets.map((b) => b.tenor),
      axisLabel: { color: ECHARTS_RISK_TEXT, fontSize: 11 },
      axisLine: { lineStyle: { color: ECHARTS_RISK_GRID_LINE } },
      axisTick: { alignWithLabel: true },
    },
    yAxis: {
      type: "value",
      name: "DV01",
      nameTextStyle: { color: ECHARTS_RISK_TEXT, fontSize: 11 },
      axisLabel: { color: ECHARTS_RISK_TEXT, fontSize: 11 },
      splitLine: { lineStyle: { color: ECHARTS_RISK_GRID_LINE, type: "dashed" } },
    },
    series: [
      {
        type: "bar",
        barMaxWidth: 48,
        data: buckets.map((b, i) => {
          const v = dv01Values[i];
          return {
            value: v,
            itemStyle: { color: dv01GradientColor(v, min, max) },
          };
        }),
      },
    ],
  };
}

export function buildAssetClassMarketValuePieOption(rows: AssetClassRiskSummary[]): EChartsOption | null {
  if (!rows.length) return null;
  const data = rows.map((row) => ({
    name: row.asset_class,
    value: bondNumericRaw(row.market_value) || 0,
    marketValueRaw: row.market_value,
    weight: row.weight,
    itemStyle: {
      color:
        ASSET_CLASS_SLICE_COLORS[row.asset_class.trim().toLowerCase()] ??
        designTokens.color.neutral[400],
    },
  }));
  return {
    backgroundColor: "transparent",
    textStyle: { color: ECHARTS_RISK_TEXT },
    tooltip: {
      trigger: "item",
      formatter: (p: unknown) => {
        const d = (p as { data?: unknown }).data as
          | { name: string; marketValueRaw: Numeric; weight: Numeric }
          | undefined;
        if (!d || typeof d !== "object") return "";
        return `${d.name}<br/>市值：${formatYi(d.marketValueRaw)}<br/>权重：${d.weight.display}`;
      },
    },
    series: [
      {
        type: "pie",
        radius: ["40%", "65%"],
        center: ["50%", "52%"],
        avoidLabelOverlap: true,
        label: { color: ECHARTS_RISK_TEXT, formatter: "{b}: {d}%" },
        data,
      },
    ],
  };
}
