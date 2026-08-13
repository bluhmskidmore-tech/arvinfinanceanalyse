import type {
  ApiEnvelope,
  CashflowProjectionPayload,
  DV01RiskPayload,
  ResultMeta,
  RiskTensorHistoryPayload,
  RiskTensorPayload,
  RiskTensorScalar,
  YieldCurveTermStructurePayload,
} from "../../../api/contracts";
import {
  formatYieldCurveDateSummary,
  summarizeYieldCurveDates,
} from "../../../lib/yieldCurveDateSummary";

import { bondNumericDisplay, bondNumericRawOrNull } from "../../bond-analytics/adapters/bondAnalyticsAdapter";
import { EM_DASH } from "../../../utils/format";
import type {
  ModuleHomeDetailChart,
} from "./moduleHomeModel";

const RISK_YUAN_PER_WAN = 10_000;
const RISK_YUAN_PER_YI = 100_000_000;

const RISK_KRD_FIELDS = [
  { key: "krd_1y", label: "KRD 1Y" },
  { key: "krd_3y", label: "KRD 3Y" },
  { key: "krd_5y", label: "KRD 5Y" },
  { key: "krd_7y", label: "KRD 7Y" },
  { key: "krd_10y", label: "KRD 10Y" },
  { key: "krd_30y", label: "KRD 30Y" },
] as const satisfies ReadonlyArray<{ key: keyof RiskTensorPayload; label: string }>;

function riskTensorRaw(value: RiskTensorScalar | null | undefined): number | null {
  return bondNumericRawOrNull(value);
}

export function buildRiskKrdChart(tensor: RiskTensorPayload): ModuleHomeDetailChart | undefined {
  const categories: string[] = [];
  const values: number[] = [];

  for (const field of RISK_KRD_FIELDS) {
    const raw = riskTensorRaw(tensor[field.key] as RiskTensorScalar | null | undefined);
    if (raw === null) {
      continue;
    }
    categories.push(field.label);
    values.push(Math.abs(raw) / RISK_YUAN_PER_WAN);
  }

  if (categories.length < 2) {
    return undefined;
  }

  return {
    title: "KRD 分布",
    unit: "万元",
    orientation: "horizontal",
    categories,
    values,
  };
}

/* ────────────────────────────────────────────────────────────────
   风险总览 v6 视图层（曜石卡 / 走势 / 涨跌胶囊 / 证据链）
   只读 governed 字段并做单位换算（元→万元 ÷1e4、元→亿元 ÷1e8、
   小数→% ×100），与 moduleHomeModel 风险段同一条换算规则；
   不在前端补算指标定义，缺失一律显式呈现。
   ──────────────────────────────────────────────────────────────── */

type RiskV6Scalar = RiskTensorScalar | null | undefined;

/** 元 → 万元/亿元，保留正负号（负缺口/空头方向有业务含义）。 */
function formatYuanAs(raw: number, divisor: number): string {
  return (raw / divisor).toLocaleString("zh-CN", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  });
}

function wanText(value: RiskV6Scalar): string | null {
  const raw = riskTensorRaw(value);
  return raw === null ? null : formatYuanAs(raw, RISK_YUAN_PER_WAN);
}

function yiText(value: RiskV6Scalar): string | null {
  const raw = riskTensorRaw(value);
  return raw === null ? null : formatYuanAs(raw, RISK_YUAN_PER_YI);
}

/** 小数 → 百分数文本（×100），decimals 由调用方按字段口径指定。 */
function percentText(value: RiskV6Scalar, decimals: number): string | null {
  const raw = riskTensorRaw(value);
  if (raw === null) {
    return null;
  }
  return (raw * 100).toFixed(decimals);
}

/* ── 24 期走势（Catmull-Rom → cubic 贝塞尔，与原型同款平滑） ────── */

export type RiskV6Sparkline = {
  linePath: string;
  areaPath: string;
  endX: number;
  endY: number;
};

const SPARK_WIDTH = 96;
const SPARK_HEIGHT = 30;
const SPARK_PAD_X = 3;
const SPARK_PAD_TOP = 5;
const SPARK_PAD_BOTTOM = 5;

function round1(value: number): number {
  return Math.round(value * 10) / 10;
}

/** Catmull-Rom（端点重复）转三次贝塞尔路径；点数 <2 时返回 null。 */
function smoothClosedPath(points: ReadonlyArray<{ x: number; y: number }>): string | null {
  if (points.length < 2) {
    return null;
  }
  let d = `M ${round1(points[0].x)},${round1(points[0].y)}`;
  for (let i = 0; i < points.length - 1; i += 1) {
    const p0 = points[Math.max(0, i - 1)];
    const p1 = points[i];
    const p2 = points[i + 1];
    const p3 = points[Math.min(points.length - 1, i + 2)];
    const c1x = p1.x + (p2.x - p0.x) / 6;
    const c1y = p1.y + (p2.y - p0.y) / 6;
    const c2x = p2.x - (p3.x - p1.x) / 6;
    const c2y = p2.y - (p3.y - p1.y) / 6;
    d += ` C ${round1(c1x)},${round1(c1y)} ${round1(c2x)},${round1(c2y)} ${round1(p2.x)},${round1(p2.y)}`;
  }
  return d;
}

/**
 * 24 期序列 → SVG viewBox 96x30 走势几何。
 * 线性归一化到 min/max；全相等（平线）时画中线。
 */
export function buildRiskV6Sparkline(values: readonly number[]): RiskV6Sparkline | null {
  const clean = values.filter((value) => Number.isFinite(value));
  if (clean.length < 2) {
    return null;
  }
  const min = Math.min(...clean);
  const max = Math.max(...clean);
  const span = max - min;
  const stepX = (SPARK_WIDTH - SPARK_PAD_X * 2) / (clean.length - 1);
  const points = clean.map((value, index) => ({
    x: SPARK_PAD_X + index * stepX,
    y:
      span === 0
        ? SPARK_HEIGHT / 2
        : SPARK_PAD_TOP +
          ((max - value) / span) * (SPARK_HEIGHT - SPARK_PAD_TOP - SPARK_PAD_BOTTOM),
  }));
  const linePath = smoothClosedPath(points);
  if (linePath === null) {
    return null;
  }
  const first = points[0];
  const last = points[points.length - 1];
  return {
    linePath,
    areaPath: `${linePath} L ${round1(last.x)},${SPARK_HEIGHT} L ${round1(first.x)},${SPARK_HEIGHT} Z`,
    endX: round1(last.x),
    endY: round1(last.y),
  };
}

/* ── 涨跌胶囊（本期 − 上一报告期，两个治理值的展示算术） ────────── */

export type RiskV6DeltaChip = {
  text: string;
  direction: "up" | "down" | "flat";
};

export type RiskV6DeltaFormat = "percent" | "absolute" | "pp" | "yi";

export function buildRiskV6DeltaChip(
  current: number | null,
  previous: number | null,
  format: RiskV6DeltaFormat,
  decimals = 2,
): RiskV6DeltaChip | null {
  if (current === null || previous === null || !Number.isFinite(current) || !Number.isFinite(previous)) {
    return null;
  }
  const delta = current - previous;
  const direction = delta > 0 ? "up" : delta < 0 ? "down" : "flat";
  const arrow = direction === "up" ? "▲" : direction === "down" ? "▼" : "·";
  let body: string;
  if (format === "percent") {
    if (previous === 0) {
      return null;
    }
    body = `${Math.abs((delta / Math.abs(previous)) * 100).toFixed(1)}%`;
  } else if (format === "pp") {
    body = `${Math.abs(delta * 100).toFixed(decimals)}pp`;
  } else if (format === "yi") {
    body = `${formatYuanAs(Math.abs(delta), RISK_YUAN_PER_YI)} 亿元`;
  } else {
    body = Math.abs(delta).toFixed(decimals);
  }
  return { text: `${arrow} ${body}`, direction };
}

/* ── 历史序列取数 ──────────────────────────────────────────────── */

type RiskV6HistoryField =
  | "regulatory_dv01"
  | "portfolio_dv01"
  | "portfolio_modified_duration"
  | "portfolio_convexity"
  | "cs01"
  | "issuer_concentration_hhi"
  | "issuer_top5_weight"
  | "liquidity_gap_30d";

function historySeries(
  history: RiskTensorHistoryPayload | undefined,
  field: RiskV6HistoryField,
): number[] {
  if (!history) {
    return [];
  }
  return history.points
    .map((point) => bondNumericRawOrNull(point[field]))
    .filter((value): value is number => value !== null && Number.isFinite(value));
}

function seriesLastTwo(series: readonly number[]): { current: number | null; previous: number | null } {
  return {
    current: series.length > 0 ? series[series.length - 1] : null,
    previous: series.length > 1 ? series[series.length - 2] : null,
  };
}

/* ── 曜石 KPI 卡 ×8 ────────────────────────────────────────────── */

export type RiskV6KpiCard = {
  key: string;
  label: string;
  /** 大数字部分（EM_DASH 表示缺失，页面显式呈现待接入）。 */
  amount: string;
  /** 跟在数字后的小字单位（万元/亿元/%），无单位时为 null。 */
  unit: string | null;
  /** 红色语义卡（30D 流动性缺口为负时）。 */
  alert: boolean;
  valuePresent: boolean;
  sparkline: RiskV6Sparkline | null;
  delta: RiskV6DeltaChip | null;
  caption: string;
};

type KpiBuildArgs = {
  key: string;
  label: string;
  amount: string | null;
  unit: string | null;
  caption: string;
  alert?: boolean;
  series: number[];
  deltaFormat: RiskV6DeltaFormat;
  deltaDecimals?: number;
};

function buildKpiCard(args: KpiBuildArgs): RiskV6KpiCard {
  const valuePresent = args.amount !== null;
  const { current, previous } = seriesLastTwo(args.series);
  return {
    key: args.key,
    label: args.label,
    amount: args.amount ?? EM_DASH,
    unit: valuePresent ? args.unit : null,
    alert: args.alert ?? false,
    valuePresent,
    sparkline: buildRiskV6Sparkline(args.series),
    delta: buildRiskV6DeltaChip(current, previous, args.deltaFormat, args.deltaDecimals),
    caption: valuePresent ? args.caption : "待接入",
  };
}

export function buildRiskV6KpiCards(
  tensor: RiskTensorPayload | undefined,
  history: RiskTensorHistoryPayload | undefined,
): RiskV6KpiCard[] {
  if (!tensor) {
    return [];
  }
  const gap30Raw = riskTensorRaw(tensor.liquidity_gap_30d);
  const gap90Yi = yiText(tensor.liquidity_gap_90d);
  return [
    buildKpiCard({
      key: "regulatory-dv01",
      label: "监管 DV01",
      amount: wanText(tensor.regulatory_dv01),
      unit: "万元",
      caption: "范围：全部正式行",
      series: historySeries(history, "regulatory_dv01"),
      deltaFormat: "percent",
    }),
    buildKpiCard({
      key: "portfolio-dv01",
      label: "估值 DV01",
      amount: wanText(tensor.portfolio_dv01),
      unit: "万元",
      caption: "同值属口径预期",
      series: historySeries(history, "portfolio_dv01"),
      deltaFormat: "percent",
    }),
    buildKpiCard({
      key: "modified-duration",
      label: "修正久期",
      amount: riskTensorRaw(tensor.portfolio_modified_duration) === null ? null : bondNumericDisplay(tensor.portfolio_modified_duration),
      unit: null,
      caption: "市值加权",
      series: historySeries(history, "portfolio_modified_duration"),
      deltaFormat: "absolute",
      deltaDecimals: 2,
    }),
    buildKpiCard({
      key: "convexity",
      label: "组合凸度",
      amount: riskTensorRaw(tensor.portfolio_convexity) === null ? null : bondNumericDisplay(tensor.portfolio_convexity),
      unit: null,
      caption: "张量直读",
      series: historySeries(history, "portfolio_convexity"),
      deltaFormat: "absolute",
      deltaDecimals: 2,
    }),
    buildKpiCard({
      key: "cs01",
      label: "CS01 信用利差",
      amount: wanText(tensor.cs01),
      unit: "万元",
      caption: "每 bp 利差",
      series: historySeries(history, "cs01"),
      deltaFormat: "percent",
    }),
    buildKpiCard({
      key: "issuer-hhi",
      label: "发行人 HHI",
      amount: percentText(tensor.issuer_concentration_hhi, 2),
      unit: "%",
      caption: "发行人集中度指数",
      series: historySeries(history, "issuer_concentration_hhi"),
      deltaFormat: "pp",
      deltaDecimals: 2,
    }),
    buildKpiCard({
      key: "issuer-top5",
      label: "前五大权重",
      amount: percentText(tensor.issuer_top5_weight, 1),
      unit: "%",
      caption: "发行人口径",
      series: historySeries(history, "issuer_top5_weight"),
      deltaFormat: "pp",
      deltaDecimals: 1,
    }),
    buildKpiCard({
      key: "liquidity-gap-30d",
      label: "30D 流动性缺口",
      amount: yiText(tensor.liquidity_gap_30d),
      unit: "亿元",
      caption: gap90Yi !== null ? `90D 缺口 ${gap90Yi} 亿` : "90D 缺口待接入",
      alert: gap30Raw !== null && gap30Raw < 0,
      series: historySeries(history, "liquidity_gap_30d"),
      deltaFormat: "yi",
    }),
  ];
}

/* ── 01 Hero 模型 ──────────────────────────────────────────────── */

export type RiskV6Hero = {
  /** 监管 DV01（万元），缺失为 null。 */
  dv01Wan: string | null;
  /** 监管 DV01 折合亿元 / bp。 */
  dv01Yi: string | null;
  peakKrdBucket: string | null;
  peakKrdWan: string | null;
  duration: string | null;
  convexity: string | null;
  totalMarketValueYi: string | null;
  bondCount: number | null;
};

export function buildRiskV6Hero(tensor: RiskTensorPayload | undefined): RiskV6Hero {
  if (!tensor) {
    return {
      dv01Wan: null,
      dv01Yi: null,
      peakKrdBucket: null,
      peakKrdWan: null,
      duration: null,
      convexity: null,
      totalMarketValueYi: null,
      bondCount: null,
    };
  }
  const regRaw = riskTensorRaw(tensor.regulatory_dv01);
  let peakKrdBucket: string | null = null;
  let peakKrdWan: string | null = null;
  let peakAbs = -1;
  for (const field of RISK_KRD_FIELDS) {
    const raw = riskTensorRaw(tensor[field.key] as RiskV6Scalar);
    if (raw === null) {
      continue;
    }
    if (Math.abs(raw) > peakAbs) {
      peakAbs = Math.abs(raw);
      peakKrdBucket = field.label.replace("KRD ", "");
      peakKrdWan = formatYuanAs(raw, RISK_YUAN_PER_WAN);
    }
  }
  return {
    dv01Wan: regRaw === null ? null : formatYuanAs(regRaw, RISK_YUAN_PER_WAN),
    dv01Yi: regRaw === null ? null : formatYuanAs(regRaw, RISK_YUAN_PER_YI),
    peakKrdBucket,
    peakKrdWan,
    duration: riskTensorRaw(tensor.portfolio_modified_duration) === null ? null : bondNumericDisplay(tensor.portfolio_modified_duration),
    convexity: riskTensorRaw(tensor.portfolio_convexity) === null ? null : bondNumericDisplay(tensor.portfolio_convexity),
    totalMarketValueYi: yiText(tensor.total_market_value),
    bondCount: typeof tensor.bond_count === "number" ? tensor.bond_count : null,
  };
}

/* ── 02 风险截面摘要 ───────────────────────────────────────────── */

export type RiskV6Brief = {
  key: string;
  title: string;
  body: string;
  note: string;
};

export function buildRiskV6Briefs(tensor: RiskTensorPayload | undefined): RiskV6Brief[] {
  if (!tensor) {
    return [
      { key: "duration", title: "久期与 DV01", body: "风险张量暂未返回。", note: "直接展示 risk tensor 字段，不以前端计算监管 DV01。" },
      { key: "credit", title: "信用与集中度", body: "集中度需要进入下钻页核验。", note: "首页只提供摘要状态。" },
      { key: "cashflow", title: "现金流压力", body: "风险张量暂未返回。", note: "现金流压力以 /cashflow-projection 正式展示为准。" },
    ];
  }
  const dv01 = wanText(tensor.portfolio_dv01);
  const duration = riskTensorRaw(tensor.portfolio_modified_duration) === null ? null : bondNumericDisplay(tensor.portfolio_modified_duration);
  const convexity = riskTensorRaw(tensor.portfolio_convexity) === null ? null : bondNumericDisplay(tensor.portfolio_convexity);
  const cs01 = wanText(tensor.cs01);
  const top5 = percentText(tensor.issuer_top5_weight, 1);
  const hhi = percentText(tensor.issuer_concentration_hhi, 2);
  const gap30 = yiText(tensor.liquidity_gap_30d);
  const gap90 = yiText(tensor.liquidity_gap_90d);
  return [
    {
      key: "duration",
      title: "久期与 DV01",
      body:
        dv01 !== null && duration !== null && convexity !== null
          ? `DV01 ${dv01} 万元，修正久期 ${duration}，凸度 ${convexity}。`
          : "张量字段缺失，逐项核对后再引用。",
      note: "直接展示 risk tensor 字段，不以前端计算监管 DV01。",
    },
    {
      key: "credit",
      title: "信用与集中度",
      body:
        cs01 !== null && top5 !== null && hhi !== null
          ? `CS01 ${cs01} 万元，前五大权重 ${top5}%，HHI ${hhi}%。`
          : "集中度字段缺失，进入下钻页核验。",
      note: "首页只提供摘要状态。",
    },
    {
      key: "cashflow",
      title: "现金流压力",
      body:
        gap30 !== null && gap90 !== null
          ? `30D 缺口 ${gap30} 亿元，90D 缺口 ${gap90} 亿元。`
          : "现金流窗口字段缺失。",
      note: "现金流压力以 /cashflow-projection 正式展示为准。",
    },
  ];
}

/* ── 03 KRD 分布条形 ───────────────────────────────────────────── */

export type RiskV6KrdBar = {
  bucket: string;
  wanText: string;
  widthPct: number;
  hot: boolean;
};

export function buildRiskV6KrdBars(tensor: RiskTensorPayload | undefined): RiskV6KrdBar[] {
  if (!tensor) {
    return [];
  }
  const rows: Array<{ bucket: string; raw: number }> = [];
  for (const field of RISK_KRD_FIELDS) {
    const raw = riskTensorRaw(tensor[field.key] as RiskV6Scalar);
    if (raw === null) {
      continue;
    }
    rows.push({ bucket: field.label.replace("KRD ", ""), raw });
  }
  if (rows.length === 0) {
    return [];
  }
  const maxAbs = Math.max(...rows.map((row) => Math.abs(row.raw)), 1e-9);
  return rows.map((row) => ({
    bucket: row.bucket,
    wanText: formatYuanAs(row.raw, RISK_YUAN_PER_WAN),
    widthPct: Math.max(3, (Math.abs(row.raw) / maxAbs) * 100),
    hot: Math.abs(row.raw) === maxAbs,
  }));
}

/* ── 03 收益率曲线（治理规则读数，缺失期限不插值、不补点） ──────── */

export type RiskV6CurveTone = "ink" | "amber" | "acc";

export type RiskV6CurveSeries = {
  curveType: string;
  label: string;
  tone: RiskV6CurveTone;
  points: Array<{ tenor: string; x: number; y: number }>;
  linePath: string | null;
  areaPath: string | null;
  endLabel: { x: number; y: number; text: string } | null;
};

export type RiskV6YieldCurveChart = {
  dateLabel: string;
  series: RiskV6CurveSeries[];
  yTicks: Array<{ text: string; y: number }>;
  xLabels: Array<{ tenor: string; x: number }>;
  resolvedDate: string | null;
  ruleVersion: string | null;
};

const CURVE_ORDER: ReadonlyArray<{ type: string; label: string; tone: RiskV6CurveTone }> = [
  { type: "treasury", label: "国债", tone: "ink" },
  { type: "cdb", label: "国开", tone: "amber" },
  { type: "aaa_credit", label: "AAA 信用", tone: "acc" },
];

const CURVE_CANONICAL_TENORS = ["1Y", "2Y", "3Y", "5Y", "7Y", "10Y", "20Y", "30Y"] as const;

const CURVE_X_LEFT = 36;
const CURVE_X_RIGHT = 348;
const CURVE_Y_TOP = 30;
const CURVE_Y_BOTTOM = 156;
const CURVE_AREA_BASELINE = 168;
const CURVE_TICK_STEP = 0.5;

/** yield_pct 为 governed Numeric（unit pct，raw 为小数比率）；图上按 % 取值。 */
function yieldPctRaw(point: { yield_pct: RiskTensorScalar | null }): number | null {
  const raw = riskTensorRaw(point.yield_pct as RiskV6Scalar);
  return raw === null ? null : raw * 100;
}

export function buildRiskV6YieldCurveChart(
  payload: YieldCurveTermStructurePayload | undefined,
): RiskV6YieldCurveChart | null {
  if (!payload || payload.curves.length === 0) {
    return null;
  }
  const byType = new Map(payload.curves.map((curve) => [curve.curve_type, curve]));
  const ordered = CURVE_ORDER.filter((entry) => byType.has(entry.type));
  if (ordered.length === 0) {
    return null;
  }
  const dateSummary = summarizeYieldCurveDates(payload.curves);

  const tenorSet = new Set<string>();
  for (const entry of ordered) {
    for (const point of byType.get(entry.type)?.points ?? []) {
      tenorSet.add(point.tenor);
    }
  }
  const tenors = CURVE_CANONICAL_TENORS.filter((tenor) => tenorSet.has(tenor));
  if (tenors.length < 2) {
    return null;
  }
  const tenorX = new Map<string, number>();
  const tenorOrder = new Map<string, number>();
  tenors.forEach((tenor, index) => {
    tenorX.set(tenor, CURVE_X_LEFT + (index * (CURVE_X_RIGHT - CURVE_X_LEFT)) / (tenors.length - 1));
    tenorOrder.set(tenor, index);
  });

  const pctValues: number[] = [];
  for (const entry of ordered) {
    for (const point of byType.get(entry.type)?.points ?? []) {
      const pct = yieldPctRaw(point);
      if (pct !== null && tenorX.has(point.tenor)) {
        pctValues.push(pct);
      }
    }
  }
  if (pctValues.length < 2) {
    return null;
  }
  const lo = Math.floor(Math.min(...pctValues) / CURVE_TICK_STEP) * CURVE_TICK_STEP;
  const hi = Math.max(
    Math.ceil(Math.max(...pctValues) / CURVE_TICK_STEP) * CURVE_TICK_STEP,
    lo + CURVE_TICK_STEP,
  );
  const yOf = (pct: number) =>
    CURVE_Y_BOTTOM - ((pct - lo) / (hi - lo)) * (CURVE_Y_BOTTOM - CURVE_Y_TOP);

  const yTicks: Array<{ text: string; y: number }> = [];
  for (let tick = lo; tick <= hi + 1e-9; tick += CURVE_TICK_STEP) {
    yTicks.push({ text: tick.toFixed(1), y: yOf(tick) });
  }

  const series: RiskV6CurveSeries[] = ordered.map((entry, seriesIndex) => {
    const curve = byType.get(entry.type);
    const points: Array<{ tenor: string; x: number; y: number; pct: number }> = [];
    for (const point of curve?.points ?? []) {
      const pct = yieldPctRaw(point);
      const x = tenorX.get(point.tenor);
      if (pct === null || x === undefined) {
        continue;
      }
      points.push({ tenor: point.tenor, x, y: yOf(pct), pct });
    }
    points.sort((a, b) => a.x - b.x);

    // 缺失期限不插值：连续可用点成段，断点另起 M。
    const segments: Array<Array<{ tenor: string; x: number; y: number; pct: number }>> = [];
    let current: Array<{ tenor: string; x: number; y: number; pct: number }> = [];
    for (const point of points) {
      const prev = current[current.length - 1];
      if (prev !== undefined && (tenorOrder.get(point.tenor) ?? 0) - (tenorOrder.get(prev.tenor) ?? 0) > 1) {
        segments.push(current);
        current = [];
      }
      current.push(point);
    }
    if (current.length > 0) {
      segments.push(current);
    }
    const segmentPaths = segments
      .map((segment) => smoothClosedPath(segment))
      .filter((path): path is string => path !== null);
    const linePath = segmentPaths.length > 0 ? segmentPaths.join(" ") : null;

    let areaPath: string | null = null;
    if (seriesIndex === 0 && segments.length === 1 && linePath !== null && points.length >= 2) {
      const first = points[0];
      const last = points[points.length - 1];
      areaPath = `${linePath} L ${round1(last.x)},${CURVE_AREA_BASELINE} L ${round1(first.x)},${CURVE_AREA_BASELINE} Z`;
    }

    const lastPoint = points.length > 0 ? points[points.length - 1] : null;
    const endLabel =
      lastPoint === null
        ? null
        : {
            x: round1(lastPoint.x + 6),
            y: round1(lastPoint.y),
            text: lastPoint.pct.toFixed(2),
          };

    return {
      curveType: entry.type,
      label: entry.label,
      tone: entry.tone,
      points,
      linePath,
      areaPath,
      endLabel,
    };
  });

  return {
    series,
    yTicks,
    xLabels: tenors.map((tenor) => ({ tenor, x: round1(tenorX.get(tenor) ?? 0) })),
    resolvedDate: dateSummary.sharedResolvedDate,
    dateLabel: formatYieldCurveDateSummary(dateSummary),
    ruleVersion: ordered.map((entry) => byType.get(entry.type)?.rule_version).find((version) => Boolean(version)) ?? null,
  };
}

/* ── 03 现金流双轨 + 缺口胶囊 ──────────────────────────────────── */

export type RiskV6CashflowRow = {
  key: string;
  window: "30D" | "90D";
  label: string;
  kind: "asset" | "liability";
  yiText: string;
  widthPct: number;
};

export type RiskV6GapChip = {
  key: string;
  label: string;
  text: string;
  tone: "alert" | "dim";
};

export type RiskV6CashflowTrack = {
  rows: RiskV6CashflowRow[];
  chips: RiskV6GapChip[];
};

export function buildRiskV6CashflowTrack(tensor: RiskTensorPayload | undefined): RiskV6CashflowTrack | null {
  if (!tensor) {
    return null;
  }
  const legs: Array<{ key: string; window: "30D" | "90D"; label: string; kind: "asset" | "liability"; raw: number }> = [];
  const push = (key: string, window: "30D" | "90D", label: string, kind: "asset" | "liability", value: RiskV6Scalar) => {
    const raw = riskTensorRaw(value);
    if (raw !== null) {
      legs.push({ key, window, label, kind, raw });
    }
  };
  push("asset-30d", "30D", "资产流入", "asset", tensor.asset_cashflow_30d);
  push("liability-30d", "30D", "负债流出", "liability", tensor.liability_cashflow_30d);
  push("asset-90d", "90D", "资产流入", "asset", tensor.asset_cashflow_90d);
  push("liability-90d", "90D", "负债流出", "liability", tensor.liability_cashflow_90d);
  if (legs.length === 0) {
    return null;
  }
  const maxAbs = Math.max(...legs.map((leg) => Math.abs(leg.raw)), 1e-9);
  const rows: RiskV6CashflowRow[] = legs.map((leg) => ({
    key: leg.key,
    window: leg.window,
    label: leg.label,
    kind: leg.kind,
    yiText: formatYuanAs(leg.raw, RISK_YUAN_PER_YI),
    widthPct: Math.max(3, (Math.abs(leg.raw) / maxAbs) * 100),
  }));

  const chips: RiskV6GapChip[] = [];
  const gap30Raw = riskTensorRaw(tensor.liquidity_gap_30d);
  const gap90Raw = riskTensorRaw(tensor.liquidity_gap_90d);
  const gapRatioRaw = riskTensorRaw(tensor.liquidity_gap_30d_ratio);
  if (gap30Raw !== null) {
    chips.push({
      key: "gap-30d",
      label: "30D 净缺口",
      text: `${formatYuanAs(gap30Raw, RISK_YUAN_PER_YI)} 亿`,
      tone: gap30Raw < 0 ? "alert" : "dim",
    });
  }
  if (gap90Raw !== null) {
    chips.push({
      key: "gap-90d",
      label: "90D 净缺口",
      text: `${formatYuanAs(gap90Raw, RISK_YUAN_PER_YI)} 亿`,
      tone: gap90Raw < 0 ? "alert" : "dim",
    });
  }
  if (gapRatioRaw !== null) {
    chips.push({
      key: "gap-ratio",
      label: "30D 缺口率",
      text: `${(gapRatioRaw * 100).toFixed(2)}%`,
      tone: "dim",
    });
  }
  return { rows, chips };
}

/* OCI / TPL bond-analysis evidence stays page-local and independently stateful. */
export type RiskBondEvidenceAccountingClass = "OCI" | "TPL";
export type RiskBondEvidenceState =
  | "loading"
  | "ready"
  | "review"
  | "empty"
  | "error"
  | "blocked";
export type RiskBondMetricKey =
  | "total-face-value"
  | "total-market-value"
  | "modified-duration"
  | "total-dv01"
  | "position-count";
export type RiskBondEvidenceMetric = {
  key: RiskBondMetricKey;
  label: string;
  value: string;
  unit: "亿元" | "年" | "万元/bp" | "只";
};
export type RiskBondComparisonReadout = {
  state: "ready" | "review" | "unavailable";
  absoluteText: string;
  percentText: string;
  basisDate: string | null;
};
export type RiskBondMetricComparison = {
  mom: RiskBondComparisonReadout;
  yoy: RiskBondComparisonReadout;
};
export type RiskBondComparisons = Record<
  RiskBondMetricKey,
  RiskBondMetricComparison
>;
export type RiskBondTrendPoint = {
  reportDate: string;
  slotIndex: number;
  value: number;
  x: number;
  y: number;
};
export type RiskBondTrend = {
  state: "ready" | "review" | "unavailable";
  dates: string[];
  values: Array<number | null>;
  unit: "万元/bp";
  linePaths: string[];
  points: RiskBondTrendPoint[];
  sparkline: RiskV6Sparkline | null;
  notices: string[];
};
export type RiskBondComparisonDateSlot = {
  reportDate: string;
  available: boolean;
};
export type RiskBondComparisonPlan = {
  enabled: boolean;
  currentDate: string;
  momDate: string | null;
  yoyDate: string | null;
  momAvailable: boolean;
  yoyAvailable: boolean;
  trendDates: RiskBondComparisonDateSlot[];
  requestDates: string[];
  missingDates: string[];
  basisText: string;
  disabledReason: string | null;
};
export type RiskBondHistoryObservation = {
  reportDate: string;
  envelope?: ApiEnvelope<DV01RiskPayload>;
  error?: unknown;
  isLoading?: boolean;
};
export type RiskBondEvidenceCard = {
  key: "bond-oci" | "bond-tpl";
  accountingClass: RiskBondEvidenceAccountingClass;
  title: string;
  state: RiskBondEvidenceState;
  statusLabel: string;
  reportDate: string | null;
  metrics: RiskBondEvidenceMetric[];
  notices: string[];
  comparisons: RiskBondComparisons;
  comparisonBasisText: string;
  trend: RiskBondTrend | null;
};
export type RiskBondEvidenceInput = {
  accountingClass: RiskBondEvidenceAccountingClass;
  reportDate: string;
  envelope?: ApiEnvelope<DV01RiskPayload>;
  isLoading?: boolean;
  error?: unknown;
  comparisonPlan?: RiskBondComparisonPlan;
  history?: readonly RiskBondHistoryObservation[];
};

function unavailableRiskBondReadout(): RiskBondComparisonReadout {
  return {
    state: "unavailable",
    absoluteText: EM_DASH,
    percentText: EM_DASH,
    basisDate: null,
  };
}

function emptyRiskBondComparisons(): RiskBondComparisons {
  const empty = (): RiskBondMetricComparison => ({
    mom: unavailableRiskBondReadout(),
    yoy: unavailableRiskBondReadout(),
  });
  return {
    "total-face-value": empty(),
    "total-market-value": empty(),
    "modified-duration": empty(),
    "total-dv01": empty(),
    "position-count": empty(),
  };
}

type RiskBondCalendarDate = {
  year: number;
  month: number;
  day: number;
};

function riskBondDaysInMonth(year: number, month: number): number {
  if (month === 2) {
    const leap = year % 4 === 0 && (year % 100 !== 0 || year % 400 === 0);
    return leap ? 29 : 28;
  }
  return [4, 6, 9, 11].includes(month) ? 30 : 31;
}

function parseRiskBondCalendarDate(value: string): RiskBondCalendarDate | null {
  const match = /^(\d{4})-(\d{2})-(\d{2})$/.exec(value.trim());
  if (!match) return null;
  const year = Number(match[1]);
  const month = Number(match[2]);
  const day = Number(match[3]);
  if (
    year < 1900 ||
    month < 1 ||
    month > 12 ||
    day < 1 ||
    day > riskBondDaysInMonth(year, month)
  ) {
    return null;
  }
  return { year, month, day };
}

function riskBondMonthEnd(
  date: Pick<RiskBondCalendarDate, "year" | "month">,
  offsetMonths: number,
): string {
  const monthIndex = date.year * 12 + date.month - 1 + offsetMonths;
  const year = Math.floor(monthIndex / 12);
  const month = ((monthIndex % 12) + 12) % 12 + 1;
  const day = riskBondDaysInMonth(year, month);
  return [
    String(year).padStart(4, "0"),
    String(month).padStart(2, "0"),
    String(day).padStart(2, "0"),
  ].join("-");
}

export function buildRiskBondComparisonPlan(
  reportDate: string,
  availableDates: readonly string[],
  trendMonths = 6,
): RiskBondComparisonPlan {
  const currentDate = reportDate.trim();
  const current = parseRiskBondCalendarDate(currentDate);
  const available = new Set(availableDates.map((date) => date.trim()));
  const exactMonthEnd =
    current !== null &&
    current.day === riskBondDaysInMonth(current.year, current.month);
  const disabledReason = !exactMonthEnd
    ? "当前报告日不是精确自然月末。"
    : !available.has(currentDate)
      ? "可用日期未包含当前报告日。"
      : null;
  if (!current || disabledReason) {
    return {
      enabled: false,
      currentDate,
      momDate: null,
      yoyDate: null,
      momAvailable: false,
      yoyAvailable: false,
      trendDates: [],
      requestDates: [],
      missingDates: [],
      basisText:
        "系统口径快照比较未启用：" +
        (disabledReason ?? "当前报告日无效。"),
      disabledReason: disabledReason ?? "当前报告日无效。",
    };
  }

  const months =
    Number.isInteger(trendMonths) && trendMonths > 0 ? trendMonths : 6;
  const momDate = riskBondMonthEnd(current, -1);
  const yoyDate = riskBondMonthEnd(current, -12);
  const trendDates = Array.from({ length: months }, (_, index) => {
    const slotDate = riskBondMonthEnd(current, index - months + 1);
    return { reportDate: slotDate, available: available.has(slotDate) };
  });
  const momAvailable = available.has(momDate);
  const yoyAvailable = available.has(yoyDate);
  const requestDates = Array.from(
    new Set([
      ...trendDates
        .filter((slot) => slot.available && slot.reportDate !== currentDate)
        .map((slot) => slot.reportDate),
      ...(momAvailable ? [momDate] : []),
      ...(yoyAvailable ? [yoyDate] : []),
    ]),
  ).sort((left, right) => left.localeCompare(right));
  const missingDates = Array.from(
    new Set([
      ...trendDates
        .filter((slot) => !slot.available)
        .map((slot) => slot.reportDate),
      ...(!momAvailable ? [momDate] : []),
      ...(!yoyAvailable ? [yoyDate] : []),
    ]),
  ).sort((left, right) => left.localeCompare(right));

  return {
    enabled: true,
    currentDate,
    momDate,
    yoyDate,
    momAvailable,
    yoyAvailable,
    trendDates,
    requestDates,
    missingDates,
    basisText:
      "系统口径快照比较：环比 " +
      momDate +
      "；同比 " +
      yoyDate +
      "；趋势为近 " +
      months +
      " 个精确自然月末。缺失日期不以邻近日期替代。",
    disabledReason: null,
  };
}

function riskBondSummary(
  accountingClass: RiskBondEvidenceAccountingClass,
  state: RiskBondEvidenceState,
  statusLabel: string,
  reportDate: string | null,
  notices: string[],
  metrics: RiskBondEvidenceMetric[] = [],
  derived?: {
    comparisons: RiskBondComparisons;
    comparisonBasisText: string;
    trend: RiskBondTrend | null;
  },
): RiskBondEvidenceCard {
  return {
    key: accountingClass === "OCI" ? "bond-oci" : "bond-tpl",
    accountingClass,
    title:
      accountingClass === "OCI"
        ? "OCI 债券（系统正式口径）"
        : "TPL 债券（系统全量口径）",
    state,
    statusLabel,
    reportDate,
    metrics,
    notices,
    comparisons: derived?.comparisons ?? emptyRiskBondComparisons(),
    comparisonBasisText:
      derived?.comparisonBasisText ?? "系统口径快照比较未启用。",
    trend: derived?.trend ?? null,
  };
}

function riskBondUnitsValid(payload: DV01RiskPayload): boolean {
  return (
    payload.total_face_value.unit === "yuan" &&
    payload.total_market_value.unit === "yuan" &&
    payload.face_weighted_modified_duration.unit === "ratio" &&
    payload.total_dv01.unit === "dv01"
  );
}

function riskBondDecimal(raw: number): string {
  return raw.toLocaleString("zh-CN", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  });
}

type RiskBondSnapshot = {
  reportDate: string;
  values: Record<RiskBondMetricKey, number>;
  review: boolean;
  notices: string[];
};

function validateRiskBondHistoryObservation(
  observation: RiskBondHistoryObservation | undefined,
  accountingClass: RiskBondEvidenceAccountingClass,
): { snapshot: RiskBondSnapshot | null; notices: string[] } {
  if (!observation) {
    return { snapshot: null, notices: ["历史月末快照未返回。"] };
  }
  const prefix = observation.reportDate + "：";
  if (!observation.envelope) {
    const detail = observation.isLoading
      ? "历史月末快照读取中。"
      : observation.error instanceof Error && observation.error.message.trim()
        ? "历史月末快照读取失败：" + observation.error.message.trim()
        : "历史月末快照未返回。";
    return { snapshot: null, notices: [prefix + detail] };
  }

  const { result_meta: meta, result: payload } = observation.envelope;
  const blocked: string[] = [];
  if (meta.basis !== "formal" || !meta.formal_use_allowed) {
    blocked.push("未通过 formal / formal_use_allowed 门禁");
  }
  if (meta.quality_flag === "error" || meta.quality_flag === "missing") {
    blocked.push("质量标记为 " + meta.quality_flag);
  }
  if (payload.report_date !== observation.reportDate) {
    blocked.push("载荷日期为 " + payload.report_date + "，不是精确目标日");
  }
  if (
    meta.resolved_report_date &&
    meta.resolved_report_date !== observation.reportDate
  ) {
    blocked.push("解析日期为 " + meta.resolved_report_date);
  }
  if (meta.fallback_mode !== "none") {
    blocked.push(
      "使用回退快照" +
        (meta.fallback_date ? "（" + meta.fallback_date + "）" : ""),
    );
  }
  if (payload.accounting_class.trim().toUpperCase() !== accountingClass) {
    blocked.push("会计分类为 " + payload.accounting_class);
  }
  if (!riskBondUnitsValid(payload)) {
    blocked.push("单位口径不一致");
  }
  if (!Number.isInteger(payload.position_count) || payload.position_count < 0) {
    blocked.push("持仓数无效");
  }

  const face = bondNumericRawOrNull(payload.total_face_value);
  const market = bondNumericRawOrNull(payload.total_market_value);
  const duration = bondNumericRawOrNull(
    payload.face_weighted_modified_duration,
  );
  const dv01 = bondNumericRawOrNull(payload.total_dv01);
  if ([face, market, duration, dv01].some((value) => value === null)) {
    blocked.push("存在空数值");
  }
  if (blocked.length > 0 || face === null || market === null || duration === null || dv01 === null) {
    return {
      snapshot: null,
      notices: [prefix + blocked.join("；") + "，该点已排除。"],
    };
  }

  const reviewNotices: string[] = [];
  if (observation.error !== undefined && observation.error !== null) {
    reviewNotices.push(prefix + "最新刷新失败，沿用缓存快照，比较待复核。");
  }
  if (meta.quality_flag === "warning" || meta.quality_flag === "stale") {
    reviewNotices.push(
      prefix + "质量标记为 " + meta.quality_flag + "，比较待复核。",
    );
  }
  if (meta.vendor_status !== "ok") {
    reviewNotices.push(
      prefix + "供应方状态为 " + meta.vendor_status + "，比较待复核。",
    );
  }
  reviewNotices.push(
    ...payload.warnings.map(
      (warning) => prefix + "警告：" + warning + "，比较待复核。",
    ),
  );
  return {
    snapshot: {
      reportDate: observation.reportDate,
      values: {
        "total-face-value": face,
        "total-market-value": market,
        "modified-duration": duration,
        "total-dv01": dv01,
        "position-count": payload.position_count,
      },
      review: reviewNotices.length > 0,
      notices: reviewNotices,
    },
    notices: reviewNotices,
  };
}

function riskBondSigned(raw: number, digits: number): string {
  const scale = 10 ** digits;
  const rounded = Math.round(raw * scale) / scale;
  const sign = rounded > 0 ? "+" : rounded < 0 ? "-" : "";
  return (
    sign +
    Math.abs(rounded).toLocaleString("zh-CN", {
      minimumFractionDigits: digits,
      maximumFractionDigits: digits,
    })
  );
}

function riskBondDeltaReadout(
  key: RiskBondMetricKey,
  current: number | null,
  previous: RiskBondSnapshot | null,
  review: boolean,
  basisDate: string | null,
): RiskBondComparisonReadout {
  if (current === null || !previous || !basisDate) {
    return {
      ...unavailableRiskBondReadout(),
      basisDate,
    };
  }
  const prior = previous.values[key];
  const delta = current - prior;
  let absoluteText: string;
  if (key === "total-face-value" || key === "total-market-value") {
    absoluteText = riskBondSigned(delta / RISK_YUAN_PER_YI, 2) + " 亿元";
  } else if (key === "modified-duration") {
    absoluteText = riskBondSigned(delta, 2) + " 年";
  } else if (key === "total-dv01") {
    absoluteText = riskBondSigned(delta / RISK_YUAN_PER_WAN, 2) + " 万元/bp";
  } else {
    absoluteText = riskBondSigned(delta, 0) + " 只";
  }
  const percentText =
    key === "modified-duration" || prior === 0
      ? EM_DASH
      : riskBondSigned((delta / Math.abs(prior)) * 100, 2) + "%";
  return {
    state: review || previous.review ? "review" : "ready",
    absoluteText,
    percentText,
    basisDate,
  };
}

function uniqueRiskBondNotices(notices: readonly string[]): string[] {
  return Array.from(new Set(notices.filter((notice) => notice.trim())));
}

function buildRiskBondGapTrendGeometry(
  dates: readonly string[],
  values: readonly (number | null)[],
): { linePaths: string[]; points: RiskBondTrendPoint[] } {
  const finiteValues = values.filter(
    (value): value is number => value !== null && Number.isFinite(value),
  );
  if (finiteValues.length === 0) {
    return { linePaths: [], points: [] };
  }
  const min = Math.min(...finiteValues);
  const max = Math.max(...finiteValues);
  const span = max - min;
  const usableWidth = SPARK_WIDTH - SPARK_PAD_X * 2;
  const usableHeight = SPARK_HEIGHT - SPARK_PAD_TOP - SPARK_PAD_BOTTOM;
  const pointAt = (value: number, slotIndex: number): RiskBondTrendPoint => ({
    reportDate: dates[slotIndex] ?? "",
    slotIndex,
    value,
    x: round1(
      values.length <= 1
        ? SPARK_WIDTH / 2
        : SPARK_PAD_X + (slotIndex / (values.length - 1)) * usableWidth,
    ),
    y: round1(
      span === 0
        ? SPARK_HEIGHT / 2
        : SPARK_PAD_TOP + ((max - value) / span) * usableHeight,
    ),
  });
  const points: RiskBondTrendPoint[] = [];
  const segments: RiskBondTrendPoint[][] = [];
  let activeSegment: RiskBondTrendPoint[] = [];
  values.forEach((value, slotIndex) => {
    if (value === null || !Number.isFinite(value)) {
      if (activeSegment.length > 0) segments.push(activeSegment);
      activeSegment = [];
      return;
    }
    const point = pointAt(value, slotIndex);
    points.push(point);
    activeSegment.push(point);
  });
  if (activeSegment.length > 0) segments.push(activeSegment);
  return {
    linePaths: segments
      .filter((segment) => segment.length >= 2)
      .map((segment) => smoothClosedPath(segment))
      .filter((path): path is string => path !== null),
    points,
  };
}

function summarizeRiskBondHistoryNotices(
  notices: readonly string[],
): string[] {
  const undated: string[] = [];
  const dated = new Map<string, string[]>();
  uniqueRiskBondNotices(notices).forEach((notice) => {
    const match = /^(\d{4}-\d{2}-\d{2})：(.*)$/.exec(notice);
    if (!match) {
      undated.push(notice);
      return;
    }
    const dates = dated.get(match[2]) ?? [];
    dates.push(match[1]);
    dated.set(match[2], dates);
  });
  const summarized = Array.from(dated.entries()).map(([detail, dates]) =>
    dates.length > 1
      ? dates.length + " 个历史月末均有同类提示：" + detail
      : dates[0] + "：" + detail,
  );
  return [...undated, ...summarized];
}

function buildRiskBondDerivedEvidence(
  plan: RiskBondComparisonPlan | undefined,
  history: readonly RiskBondHistoryObservation[],
  accountingClass: RiskBondEvidenceAccountingClass,
  currentValues: Record<RiskBondMetricKey, number | null>,
  currentReview: boolean,
): {
  comparisons: RiskBondComparisons;
  comparisonBasisText: string;
  trend: RiskBondTrend | null;
  notices: string[];
} {
  if (!plan?.enabled) {
    return {
      comparisons: emptyRiskBondComparisons(),
      comparisonBasisText:
        plan?.basisText ?? "系统口径快照比较未启用。",
      trend: null,
      notices: [],
    };
  }

  const observations = new Map(
    history.map((observation) => [observation.reportDate, observation]),
  );
  const validated = new Map<
    string,
    ReturnType<typeof validateRiskBondHistoryObservation>
  >();
  const getValidated = (reportDate: string) => {
    const cached = validated.get(reportDate);
    if (cached) return cached;
    const result = validateRiskBondHistoryObservation(
      observations.get(reportDate) ?? { reportDate },
      accountingClass,
    );
    validated.set(reportDate, result);
    return result;
  };

  const comparisonNotices: string[] = [];
  const periodSnapshot = (
    reportDate: string | null,
    available: boolean,
    label: string,
  ): RiskBondSnapshot | null => {
    if (!reportDate || !available) {
      if (reportDate) {
        comparisonNotices.push(
          label + "缺少精确月末 " + reportDate + "，不使用邻近日期。",
        );
      }
      return null;
    }
    const result = getValidated(reportDate);
    comparisonNotices.push(...result.notices);
    return result.snapshot;
  };
  const mom = periodSnapshot(plan.momDate, plan.momAvailable, "环比");
  const yoy = periodSnapshot(plan.yoyDate, plan.yoyAvailable, "同比");
  const comparisons = emptyRiskBondComparisons();
  (Object.keys(comparisons) as RiskBondMetricKey[]).forEach((key) => {
    comparisons[key] = {
      mom: riskBondDeltaReadout(
        key,
        currentValues[key],
        mom,
        currentReview,
        plan.momDate,
      ),
      yoy: riskBondDeltaReadout(
        key,
        currentValues[key],
        yoy,
        currentReview,
        plan.yoyDate,
      ),
    };
  });

  const trendNotices: string[] = [];
  let trendReview = currentReview;
  const trendValues = plan.trendDates.map((slot): number | null => {
    if (slot.reportDate === plan.currentDate) {
      const currentDv01 = currentValues["total-dv01"];
      return currentDv01 === null
        ? null
        : currentDv01 / RISK_YUAN_PER_WAN;
    }
    if (!slot.available) {
      trendNotices.push(
        "趋势缺少精确月末 " + slot.reportDate + "，不跨缺口连线。",
      );
      return null;
    }
    const result = getValidated(slot.reportDate);
    trendNotices.push(...result.notices);
    if (!result.snapshot) return null;
    trendReview = trendReview || result.snapshot.review;
    return result.snapshot.values["total-dv01"] / RISK_YUAN_PER_WAN;
  });
  const hasCompleteSixPoints =
    plan.trendDates.length === 6 &&
    trendValues.every((value) => value !== null);
  const numericTrendValues = hasCompleteSixPoints
    ? (trendValues as number[])
    : [];
  const trendDates = plan.trendDates.map((slot) => slot.reportDate);
  const geometry = buildRiskBondGapTrendGeometry(trendDates, trendValues);
  const canDisplayTrend = geometry.points.length >= 2;
  const trend: RiskBondTrend = {
    state: !canDisplayTrend
      ? "unavailable"
      : trendReview || !hasCompleteSixPoints
        ? "review"
        : "ready",
    dates: trendDates,
    values: trendValues,
    unit: "万元/bp",
    linePaths: geometry.linePaths,
    points: geometry.points,
    sparkline: hasCompleteSixPoints
      ? buildRiskV6Sparkline(numericTrendValues)
      : null,
    notices: uniqueRiskBondNotices(trendNotices),
  };

  return {
    comparisons,
    comparisonBasisText: plan.basisText,
    trend,
    notices: summarizeRiskBondHistoryNotices([
      ...comparisonNotices,
      ...trendNotices,
    ]),
  };
}

/**
 * Maps one accounting-class response without combining OCI and TPL state.
 * Values are display conversions only; no duration or DV01 formula is recalculated here.
 */
export function buildRiskBondDv01Summary(
  input: RiskBondEvidenceInput,
): RiskBondEvidenceCard {
  const {
    accountingClass,
    reportDate,
    envelope,
    isLoading = false,
    error,
    comparisonPlan,
    history = [],
  } = input;
  const errorMessage =
    error instanceof Error && error.message.trim()
      ? error.message.trim()
      : null;
  if (!reportDate.trim()) {
    return riskBondSummary(accountingClass, "blocked", "报告日待接入", null, [
      "风险报告日未返回，债券分析辅助证据未发起读取。",
    ]);
  }
  if (error !== undefined && error !== null && !envelope) {
    const detail = errorMessage
      ? "读取失败：" + errorMessage
      : "读取失败，请单独复核该会计分类。";
    return riskBondSummary(
      accountingClass,
      "error",
      "读取失败",
      reportDate,
      [detail],
    );
  }
  if (!envelope) {
    return riskBondSummary(
      accountingClass,
      isLoading ? "loading" : "error",
      isLoading ? "读取中" : "未返回",
      reportDate,
      [isLoading ? "正在读取债券分析辅助证据。" : "接口未返回该分类证据。"],
    );
  }

  const { result_meta: meta, result: payload } = envelope;
  const blocked: string[] = [];
  const fallbackDateMatches =
    meta.fallback_mode !== "none" &&
    meta.fallback_date === payload.report_date;
  if (meta.basis !== "formal" || !meta.formal_use_allowed) {
    blocked.push("结果未通过 formal / formal_use_allowed 门禁，不展示数值。");
  }
  if (meta.quality_flag === "error" || meta.quality_flag === "missing") {
    blocked.push("质量标记为 " + meta.quality_flag + "，不展示数值。");
  }
  if (payload.accounting_class.trim().toUpperCase() !== accountingClass) {
    blocked.push(
      "返回分类为 " +
        (payload.accounting_class || "空") +
        "，与请求分类 " +
        accountingClass +
        " 不一致。",
    );
  }
  if (payload.report_date !== reportDate && !fallbackDateMatches) {
    blocked.push(
      "返回报告日 " +
        (payload.report_date || "空") +
        " 与请求报告日 " +
        reportDate +
        " 不一致。",
    );
  }
  if (!riskBondUnitsValid(payload)) {
    blocked.push("返回单位与亿元、年、万元/bp 展示口径不一致。");
  }
  if (!Number.isInteger(payload.position_count) || payload.position_count < 0) {
    blocked.push("持仓数无效，不展示数值。");
  }
  if (blocked.length > 0) {
    return riskBondSummary(
      accountingClass,
      "blocked",
      "口径校验未通过",
      payload.report_date || null,
      blocked,
    );
  }

  const review: string[] = [];
  review.push(
    accountingClass === "OCI"
      ? "630 手工表的同名金额列与系统字段定义不一致：本次手工“账面金额”数值对应含息公允价值，“市值”数值对应系统面值。本卡展示系统正式的面值、不含应计的公允价值和面值基数 DV01，不按手工同名列直接比较。"
      : "630 手工表的 TPL 范围为交易账簿债券、银行账簿债券和市值型基金；当前接口仅返回全量 TPL 会计分类，缺少市值型基金正式清单及穿透久期/DV01，因此不可用本卡替代 630 小计。",
  );
  if (error !== undefined && error !== null) {
    review.push(
      errorMessage
        ? "最新刷新失败：" + errorMessage + "；当前展示上次成功结果。"
        : "最新刷新失败，当前展示上次成功结果。",
    );
  }
  if (meta.quality_flag === "warning" || meta.quality_flag === "stale") {
    review.push("质量标记为 " + meta.quality_flag + "，结论待复核。");
  }
  if (meta.vendor_status !== "ok") {
    review.push("供应方状态为 " + meta.vendor_status + "，结论待复核。");
  }
  if (meta.fallback_mode !== "none") {
    review.push(
      "使用回退快照" +
        (meta.fallback_date ? "（" + meta.fallback_date + "）" : "") +
        "，结论待复核。",
    );
  }
  if (
    meta.resolved_report_date &&
    meta.resolved_report_date !== reportDate
  ) {
    review.push(
      "解析报告日 " +
        meta.resolved_report_date +
        " 与请求报告日不一致，系统口径快照比较已禁用。",
    );
  }
  review.push(...payload.warnings.map((warning) => "警告：" + warning));

  if (payload.position_count === 0) {
    return riskBondSummary(
      accountingClass,
      "empty",
      "暂无数据",
      payload.report_date,
      [
        "该报告日无持仓，不将空载荷中的零值展示为真实风险数值。",
        ...review,
      ],
    );
  }

  const face = bondNumericRawOrNull(payload.total_face_value);
  const market = bondNumericRawOrNull(payload.total_market_value);
  const duration = bondNumericRawOrNull(
    payload.face_weighted_modified_duration,
  );
  const dv01 = bondNumericRawOrNull(payload.total_dv01);
  if ([face, market, duration, dv01].some((value) => value === null)) {
    review.push("部分数值为空，缺失项以 — 展示，结论待复核。");
  }
  const metrics: RiskBondEvidenceMetric[] = [
    {
      key: "total-face-value",
      label: "总面值（DV01 基数）",
      value: face === null ? EM_DASH : formatYuanAs(face, RISK_YUAN_PER_YI),
      unit: "亿元",
    },
    {
      key: "total-market-value",
      label: "公允价值（不含应计）",
      value: market === null ? EM_DASH : formatYuanAs(market, RISK_YUAN_PER_YI),
      unit: "亿元",
    },
    {
      key: "modified-duration",
      label: "面值加权修正久期",
      value: duration === null ? EM_DASH : riskBondDecimal(duration),
      unit: "年",
    },
    {
      key: "total-dv01",
      label: "正式 DV01（面值基数）",
      value: dv01 === null ? EM_DASH : formatYuanAs(dv01, RISK_YUAN_PER_WAN),
      unit: "万元/bp",
    },
    {
      key: "position-count",
      label: "持仓数",
      value: payload.position_count.toLocaleString("zh-CN"),
      unit: "只",
    },
  ];
  const currentComparisonDisabled =
    comparisonPlan !== undefined &&
    (comparisonPlan.currentDate !== reportDate ||
      payload.report_date !== reportDate ||
      meta.fallback_mode !== "none" ||
      (meta.resolved_report_date !== undefined &&
        meta.resolved_report_date !== null &&
        meta.resolved_report_date !== reportDate));
  const derived = currentComparisonDisabled
    ? {
        comparisons: emptyRiskBondComparisons(),
        comparisonBasisText:
          "系统口径快照比较未启用：当前快照为回退或日期与请求月末不一致。",
        trend: null,
        notices: [],
      }
    : buildRiskBondDerivedEvidence(
        comparisonPlan,
        history,
        accountingClass,
        {
          "total-face-value": face,
          "total-market-value": market,
          "modified-duration": duration,
          "total-dv01": dv01,
          "position-count": payload.position_count,
        },
        review.length > 0,
      );
  return riskBondSummary(
    accountingClass,
    review.length > 0 ? "review" : "ready",
    review.length > 0 ? "待复核" : "可读取",
    payload.report_date,
    uniqueRiskBondNotices([...review, ...derived.notices]),
    metrics,
    derived,
  );
}

/* ── 03 字段级明细表 ───────────────────────────────────────────── */

export type RiskV6TableRow = {
  key: string;
  label: string;
  value: string;
  date: string;
  tone?: "ok" | "watch";
};

export type RiskV6DetailTable = {
  key: string;
  title: string;
  rows: RiskV6TableRow[];
};

export function buildRiskV6DetailTables(
  tensor: RiskTensorPayload | undefined,
  cashflow: CashflowProjectionPayload | undefined,
): RiskV6DetailTable[] {
  const portfolioRows: RiskV6TableRow[] = [];
  const creditRows: RiskV6TableRow[] = [];
  if (!tensor) {
    return [
      { key: "portfolio-duration", title: "组合与久期", rows: portfolioRows },
      { key: "credit-concentration", title: "信用与集中度", rows: creditRows },
    ];
  }
  const date = tensor.report_date;
  const push = (rows: RiskV6TableRow[], key: string, label: string, value: string | null) => {
    if (value !== null) {
      rows.push({ key, label, value, date });
    }
  };

  const totalMv = yiText(tensor.total_market_value);
  push(portfolioRows, "total-market-value", "组合总市值", totalMv === null ? null : `${totalMv} 亿元`);
  push(portfolioRows, "bond-count", "持仓只数", typeof tensor.bond_count === "number" ? tensor.bond_count.toLocaleString("zh-CN") : null);
  push(portfolioRows, "modified-duration", "修正久期", riskTensorRaw(tensor.portfolio_modified_duration) === null ? null : bondNumericDisplay(tensor.portfolio_modified_duration));
  push(portfolioRows, "convexity", "组合凸度", riskTensorRaw(tensor.portfolio_convexity) === null ? null : bondNumericDisplay(tensor.portfolio_convexity));
  const portfolioDv01 = wanText(tensor.portfolio_dv01);
  push(portfolioRows, "portfolio-dv01", "组合 DV01", portfolioDv01 === null ? null : `${portfolioDv01} 万元`);
  const regulatoryDv01 = wanText(tensor.regulatory_dv01);
  push(portfolioRows, "regulatory-dv01", "监管口径 DV01", regulatoryDv01 === null ? null : `${regulatoryDv01} 万元`);
  const rateRiskDv01 = wanText(tensor.rate_risk_dv01);
  push(portfolioRows, "rate-risk-dv01", "利率风险口径 DV01", rateRiskDv01 === null ? null : `${rateRiskDv01} 万元`);
  const rateRiskMv = yiText(tensor.rate_risk_market_value);
  push(portfolioRows, "rate-risk-mv", "利率风险口径市值", rateRiskMv === null ? null : `${rateRiskMv} 亿元`);
  const excludedMv = yiText(tensor.duration_excluded_market_value);
  if (typeof tensor.duration_excluded_count === "number" && excludedMv !== null) {
    portfolioRows.push({
      key: "duration-excluded",
      label: "久期剔除项",
      value: `${tensor.duration_excluded_count.toLocaleString("zh-CN")} 只 · ${excludedMv} 亿元`,
      date,
    });
  }

  const cs01 = wanText(tensor.cs01);
  push(creditRows, "cs01", "CS01", cs01 === null ? null : `${cs01} 万元`);
  const top5 = percentText(tensor.issuer_top5_weight, 1);
  push(creditRows, "issuer-top5", "前五大发行人权重", top5 === null ? null : `${top5}%`);
  const hhi = percentText(tensor.issuer_concentration_hhi, 2);
  push(creditRows, "issuer-hhi", "发行人集中度 HHI", hhi === null ? null : `${hhi}%`);

  // 久期缺口 / 12M 再投资风险来自现金流服务（独立于张量链路）。
  creditRows.push({
    key: "duration-gap",
    label: "久期缺口",
    value: cashflow ? bondNumericDisplay(cashflow.duration_gap) : "待接入",
    date: cashflow?.report_date ?? date,
    tone: cashflow ? "ok" : "watch",
  });
  creditRows.push({
    key: "reinvestment-risk-12m",
    label: "12M 再投资风险",
    value: cashflow ? bondNumericDisplay(cashflow.reinvestment_risk_12m) : "待接入",
    date: cashflow?.report_date ?? date,
    tone: cashflow ? "ok" : "watch",
  });

  return [
    { key: "portfolio-duration", title: "组合与久期", rows: portfolioRows },
    { key: "credit-concentration", title: "信用与集中度", rows: creditRows },
  ];
}

/* ── 04 血缘版本链 ─────────────────────────────────────────────── */

export type RiskV6LineageRow = {
  key: string;
  label: string;
  value: string;
};

export function buildRiskV6LineageRows(meta: ResultMeta | undefined): RiskV6LineageRow[] {
  if (!meta) {
    return [];
  }
  const rows: RiskV6LineageRow[] = [];
  const push = (key: string, label: string, value: string | null | undefined) => {
    if (value) {
      rows.push({ key, label, value });
    }
  };
  push("source", "SOURCE", meta.source_version);
  push("rule", "RULE", meta.rule_version);
  push("cache", "CACHE", meta.cache_version);
  push("trace", "TRACE", meta.trace_id);
  push("resolved", "RESOLVED", meta.resolved_report_date);
  push("quality", "QUALITY", meta.quality_flag);
  if (meta.fallback_mode && meta.fallback_mode !== "none") {
    push("fallback", "FALLBACK", `${meta.fallback_mode}${meta.fallback_date ? ` · ${meta.fallback_date}` : ""}`);
  }
  return rows;
}
