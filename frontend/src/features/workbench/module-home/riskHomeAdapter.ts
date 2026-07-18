import type {
  CashflowProjectionPayload,
  ResultMeta,
  RiskTensorHistoryPayload,
  RiskTensorPayload,
  RiskTensorScalar,
  YieldCurveTermStructurePayload,
} from "../../../api/contracts";
import { bondNumericDisplay, bondNumericRawOrNull } from "../../bond-analytics/adapters/bondAnalyticsAdapter";
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
  /** 大数字部分（"-" 表示缺失，页面显式呈现待接入）。 */
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
    amount: args.amount ?? "-",
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
    resolvedDate: ordered.map((entry) => byType.get(entry.type)?.trade_date_resolved).find((date) => Boolean(date)) ?? payload.report_date ?? null,
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
