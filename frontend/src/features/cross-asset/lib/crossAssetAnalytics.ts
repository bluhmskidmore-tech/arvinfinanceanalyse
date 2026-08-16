/**
 * Cross-asset analytics module.
 *
 * Provides pure computation functions for:
 * - Rolling pairwise Pearson correlation (NxN heatmap)
 * - Market regime identification from environment scores and sparkline direction
 * - Historical percentile within a sparkline window
 * - Momentum scoreboard (1d/5d/20d returns with acceleration)
 *
 * All functions are pure and stateless; no side effects.
 */

import { designTokens } from "../../../theme/designSystem";
import { EM_DASH } from "../../../utils/format";
import {
  isAssetLevelKpiKey,
  type CrossAssetDatedValue,
  type ResolvedCrossAssetKpi,
  type CrossAssetKpiFormat,
} from "./crossAssetKpiModel";

/**
 * Cross-asset analytics presentation palette.
 * Token-equal colors resolve through designTokens; non-equal hex stay verbatim.
 */
const CA_PALETTE = {
  riskOn: "#16a34a",
  riskOnBg: "#f0fdf4",
  riskOff: designTokens.color.danger[600],
  riskOffBg: designTokens.color.danger[50],
  stagflation: "#ea580c",
  stagflationBg: "#fff7ed",
  deflation: designTokens.color.info[600],
  deflationBg: designTokens.color.info[50],
  liquidity: designTokens.color.primary[600],
  liquidityBg: designTokens.color.primary[50],
  mixed: designTokens.color.cockpit.ink600,
  mixedBg: designTokens.color.cockpit.surface20,
  percentileExtremeLow: designTokens.color.info[600],
  percentileLow: designTokens.color.info[400],
  percentileMid: designTokens.color.cockpit.ink600,
  percentileHigh: "#f59e0b",
  percentileExtremeHigh: designTokens.color.danger[500],
  erpCheap: "#16a34a",
  erpCheapBg: "#f0fdf4",
  erpExpensive: designTokens.color.danger[600],
  erpExpensiveBg: designTokens.color.danger[50],
  erpNeutral: designTokens.color.warning[500],
  erpNeutralBg: "#fffbeb",
  erpUnavailable: designTokens.color.cockpit.ink600,
  erpUnavailableBg: designTokens.color.cockpit.surface20,
  waterfallUp: designTokens.color.danger[600],
  waterfallDown: "#16a34a",
  waterfallTotalNeutral: designTokens.color.cockpit.ink600,
  waterfallFactorNeutral: designTokens.color.cockpit.ink450,
} as const;

/* ================================================================
 *  1. Asset Correlation Matrix
 * ================================================================ */

export type CorrelationCell = {
  rowKey: string;
  colKey: string;
  value: number | null; // Pearson r, or null if insufficient overlap
};

export type CorrelationMatrix = {
  keys: string[];
  labels: string[];
  cells: CorrelationCell[][];
};

/**
 * Pearson correlation coefficient between two numeric arrays of equal length.
 * Returns null if length < 3 or all values are identical.
 */
function pearsonR(xs: number[], ys: number[]): number | null {
  const n = xs.length;
  if (n < 3) return null;

  let sumX = 0;
  let sumY = 0;
  for (let i = 0; i < n; i++) {
    sumX += xs[i];
    sumY += ys[i];
  }
  const meanX = sumX / n;
  const meanY = sumY / n;

  let covXY = 0;
  let varX = 0;
  let varY = 0;
  for (let i = 0; i < n; i++) {
    const dx = xs[i] - meanX;
    const dy = ys[i] - meanY;
    covXY += dx * dy;
    varX += dx * dx;
    varY += dy * dy;
  }

  if (varX === 0 || varY === 0) return null;
  return covXY / Math.sqrt(varX * varY);
}

/**
 * Build an NxN correlation matrix from date-bearing KPI observations.
 * Only includes KPIs that have at least 5 unique dated observations.
 * Each pair is aligned by common trade_date and requires at least 5 overlaps.
 * Undated sparkline arrays are presentation-only and must not be positionally paired.
 */
export function buildCorrelationMatrix(kpis: ResolvedCrossAssetKpi[]): CorrelationMatrix {
  const minimumObservations = 5;
  const eligible = kpis
    .map((kpi) => ({ kpi, points: normalizeDatedValues(kpi.sparklinePoints) }))
    .filter(({ kpi, points }) => isAssetLevelKpiKey(kpi.key) && points.length >= minimumObservations);
  const keys = eligible.map(({ kpi }) => kpi.key);
  const labels = eligible.map(({ kpi }) => kpi.label);

  const cells: CorrelationCell[][] = eligible.map(({ kpi: rowKpi, points: rowPoints }, ri) => {
    return eligible.map(({ kpi: colKpi, points: colPoints }, ci) => {
      if (ri === ci) {
        return { rowKey: rowKpi.key, colKey: colKpi.key, value: 1 };
      }
      const colByDate = new Map(colPoints.map((point) => [point.tradeDate, point.value]));
      const aligned = rowPoints
        .filter((point) => colByDate.has(point.tradeDate))
        .map((point) => ({ x: point.value, y: colByDate.get(point.tradeDate)! }));
      const value =
        aligned.length >= minimumObservations
          ? pearsonR(
              aligned.map((point) => point.x),
              aligned.map((point) => point.y),
            )
          : null;
      return { rowKey: rowKpi.key, colKey: colKpi.key, value };
    });
  });

  return { keys, labels, cells };
}

function normalizeDatedValues(points: CrossAssetDatedValue[] | undefined): CrossAssetDatedValue[] {
  const byDate = new Map<string, number>();
  for (const point of points ?? []) {
    if (!point.tradeDate || !Number.isFinite(point.value)) {
      continue;
    }
    byDate.set(point.tradeDate, point.value);
  }
  return [...byDate.entries()]
    .sort(([leftDate], [rightDate]) => leftDate.localeCompare(rightDate))
    .map(([tradeDate, value]) => ({ tradeDate, value }));
}

/**
 * Map a correlation value [-1, 1] to an RGBA color string.
 *   -1 → deep red/loss
 *   0  → neutral/grey
 *   +1 → deep green/profit
 */
export function correlationColor(r: number | null): string {
  if (r == null) return "rgba(100, 116, 139, 0.12)";
  const clamped = Math.max(-1, Math.min(1, r));
  if (clamped >= 0) {
    const t = clamped;
    // green channel ramp
    return `rgba(34, 139, 34, ${(0.1 + t * 0.65).toFixed(2)})`;
  }
  const t = -clamped;
  return `rgba(220, 53, 69, ${(0.1 + t * 0.65).toFixed(2)})`;
}

/**
 * Format a correlation value for display.
 */
export function formatCorrelation(r: number | null): string {
  if (r == null) return EM_DASH;
  return r.toFixed(2);
}

/* ================================================================
 *  2. Market Regime Identification
 * ================================================================ */

export type MarketRegime =
  | "risk_on"
  | "risk_off"
  | "stagflation"
  | "deflation_trade"
  | "liquidity_driven"
  | "mixed";

export type MarketRegimeInfo = {
  regime: MarketRegime;
  label: string;
  description: string;
  color: string;
  bgColor: string;
  icon: string; // emoji or symbol
};

const REGIME_META: Record<MarketRegime, Omit<MarketRegimeInfo, "regime">> = {
  risk_on: {
    label: "Risk-On",
    description: "风险偏好回暖：权益上行 + 利率上行/持平 + 流动性中性偏松",
    color: CA_PALETTE.riskOn,
    bgColor: CA_PALETTE.riskOnBg,
    icon: "🟢",
  },
  risk_off: {
    label: "Risk-Off",
    description: "避险模式：权益走弱 + 利率下行 + 资金面宽松",
    color: CA_PALETTE.riskOff,
    bgColor: CA_PALETTE.riskOffBg,
    icon: "🔴",
  },
  stagflation: {
    label: "滞胀交易",
    description: "增长放缓叠加通胀压力：商品走强 + 权益走弱 + 利率上行",
    color: CA_PALETTE.stagflation,
    bgColor: CA_PALETTE.stagflationBg,
    icon: "🟠",
  },
  deflation_trade: {
    label: "通缩交易",
    description: "通缩预期主导：商品走弱 + 利率下行 + 权益承压",
    color: CA_PALETTE.deflation,
    bgColor: CA_PALETTE.deflationBg,
    icon: "🔵",
  },
  liquidity_driven: {
    label: "流动性驱动",
    description: "宽松流动性主导：资金面偏松 + 股债同涨 + 利率下行",
    color: CA_PALETTE.liquidity,
    bgColor: CA_PALETTE.liquidityBg,
    icon: "🟣",
  },
  mixed: {
    label: "信号分化",
    description: "各资产信号冲突，无法归入单一体制",
    color: CA_PALETTE.mixed,
    bgColor: CA_PALETTE.mixedBg,
    icon: "⚪",
  },
};

type SparkDir = "rising" | "falling" | "flat";

function sparkDirection(sparkline: number[], format: CrossAssetKpiFormat, lookback = 5): SparkDir {
  if (sparkline.length < 2) return "flat";
  const start = Math.max(0, sparkline.length - lookback);
  const slice = sparkline.slice(start);
  const first = slice[0];
  const last = slice[slice.length - 1];
  const change = last - first;
  const absChange = Math.abs(change);

  let significant = false;
  switch (format) {
    case "percent":
      significant = absChange > 0.03;
      break;
    case "bp":
      significant = absChange > 3;
      break;
    case "fx":
      significant = absChange > 0.005;
      break;
    case "plain":
    case "index":
    default:
      significant = first > 0 ? absChange / first > 0.005 : false;
      break;
  }
  if (!significant) return "flat";
  return change > 0 ? "rising" : "falling";
}

/**
 * Determine the current market regime based on KPI sparkline directions.
 */
export function identifyMarketRegime(kpis: ResolvedCrossAssetKpi[]): MarketRegimeInfo {
  const byKey = new Map(kpis.map((k) => [k.key, k]));

  function dir(key: string): SparkDir {
    const kpi = byKey.get(key);
    if (!kpi || kpi.sparkline.length < 2) return "flat";
    return sparkDirection(kpi.sparkline, kpi.format);
  }

  const bondDir = dir("cn_gov_10y"); // yield: rising = rates up
  const equityDir = dir("csi300");
  const moneyDir = dir("money_market_7d"); // rising = tightening
  const brentDir = dir("brent");
  const steelDir = dir("steel");

  // Liquidity driven: money rates falling + bond yield falling + equity rising
  if (moneyDir === "falling" && bondDir === "falling" && equityDir === "rising") {
    return { regime: "liquidity_driven", ...REGIME_META.liquidity_driven };
  }

  // Risk-on: equity rising + bond yield not falling significantly
  if (equityDir === "rising" && bondDir !== "falling") {
    return { regime: "risk_on", ...REGIME_META.risk_on };
  }

  // Risk-off: equity falling + bond yield falling (flight to quality)
  if (equityDir === "falling" && bondDir === "falling") {
    return { regime: "risk_off", ...REGIME_META.risk_off };
  }

  // Stagflation: commodities rising + equity falling + yield rising
  if ((brentDir === "rising" || steelDir === "rising") && equityDir === "falling" && bondDir === "rising") {
    return { regime: "stagflation", ...REGIME_META.stagflation };
  }

  // Deflation trade: commodities falling + yield falling
  if ((brentDir === "falling" || steelDir === "falling") && bondDir === "falling") {
    return { regime: "deflation_trade", ...REGIME_META.deflation_trade };
  }

  return { regime: "mixed", ...REGIME_META.mixed };
}

/* ================================================================
 *  3. Historical Percentile
 * ================================================================ */

export type PercentileInfo = {
  percentile: number; // 0–100
  label: string; // e.g. "72th"
  zone: "low" | "mid" | "high" | "extreme_low" | "extreme_high";
};

/**
 * Compute the percentile of the last value within the sparkline window.
 * Returns null if insufficient data.
 */
export function computeSparklinePercentile(sparkline: number[]): PercentileInfo | null {
  if (sparkline.length < 3) return null;
  const current = sparkline[sparkline.length - 1];
  const sorted = [...sparkline].sort((a, b) => a - b);
  // Count how many values are strictly less than current
  const below = sorted.filter((v) => v < current).length;
  const pct = Math.round((below / (sorted.length - 1)) * 100);
  const clamped = Math.max(0, Math.min(100, pct));

  let zone: PercentileInfo["zone"];
  if (clamped <= 10) zone = "extreme_low";
  else if (clamped <= 30) zone = "low";
  else if (clamped >= 90) zone = "extreme_high";
  else if (clamped >= 70) zone = "high";
  else zone = "mid";

  // 分位标签用百分数形态（"21%"），避免英文序数词在窄 chip 内折行（§7 语域）。
  return { percentile: clamped, label: `${clamped}%`, zone };
}

/**
 * Map a percentile zone to a color for the gauge bar.
 */
export function percentileZoneColor(zone: PercentileInfo["zone"]): string {
  switch (zone) {
    case "extreme_low":
      return CA_PALETTE.percentileExtremeLow;
    case "low":
      return CA_PALETTE.percentileLow;
    case "mid":
      return CA_PALETTE.percentileMid;
    case "high":
      return CA_PALETTE.percentileHigh;
    case "extreme_high":
      return CA_PALETTE.percentileExtremeHigh;
  }
}

/* ================================================================
 *  4. Momentum Scoreboard
 * ================================================================ */

export type MomentumRow = {
  key: string;
  label: string;
  tag: string;
  current: number | null;
  chg1d: number | null;
  chg5d: number | null;
  chg20d: number | null;
  direction: "up" | "down" | "flat";
  acceleration: "accelerating" | "decelerating" | "steady";
};

function pctChange(arr: number[], lookback: number): number | null {
  if (arr.length <= lookback) return null;
  const from = arr[arr.length - 1 - lookback];
  const to = arr[arr.length - 1];
  if (from === 0) return null;
  return ((to - from) / Math.abs(from)) * 100;
}

export function buildMomentumScoreboard(kpis: ResolvedCrossAssetKpi[]): MomentumRow[] {
  return kpis
    .filter((k) => isAssetLevelKpiKey(k.key) && k.sparkline.length >= 2)
    .map((k) => {
      const chg1d = pctChange(k.sparkline, 1);
      const chg5d = pctChange(k.sparkline, Math.min(5, k.sparkline.length - 1));
      const chg20d = pctChange(k.sparkline, Math.min(20, k.sparkline.length - 1));

      let direction: MomentumRow["direction"] = "flat";
      if (chg1d != null) {
        if (chg1d > 0.001) direction = "up";
        else if (chg1d < -0.001) direction = "down";
      }

      // Acceleration: compare short-term momentum to longer-term
      let acceleration: MomentumRow["acceleration"] = "steady";
      if (chg1d != null && chg5d != null) {
        const avgDaily5d = chg5d / Math.min(5, k.sparkline.length - 1);
        if (Math.abs(chg1d) > Math.abs(avgDaily5d) * 1.3) acceleration = "accelerating";
        else if (Math.abs(chg1d) < Math.abs(avgDaily5d) * 0.5) acceleration = "decelerating";
      }

      return {
        key: k.key,
        label: k.label,
        tag: k.tag,
        current: k.sparkline[k.sparkline.length - 1] ?? null,
        chg1d,
        chg5d,
        chg20d,
        direction,
        acceleration,
      };
    });
}

/* ================================================================
 *  5. Trend Chart Group Filter
 * ================================================================ */

export type TrendGroupKey = "all" | "rates" | "equity" | "commodity_fx";

export type TrendGroup = {
  key: TrendGroupKey;
  label: string;
  /** KPI keys that belong to this group */
  kpiKeys: string[];
};

export const TREND_GROUPS: TrendGroup[] = [
  {
    key: "all",
    label: "全部",
    kpiKeys: [], // empty means show all
  },
  {
    key: "rates",
    label: "利率",
    kpiKeys: ["cn_gov_10y", "us_gov_10y", "gov_spread", "money_market_7d"],
  },
  {
    key: "equity",
    label: "权益",
    kpiKeys: ["csi300", "csi300_pe", "mega_cap_weight", "mega_cap_top5_weight"],
  },
  {
    key: "commodity_fx",
    label: "商品+汇率",
    kpiKeys: ["brent", "steel", "usdcny"],
  },
];

/**
 * Filter KPI labels for the trend chart based on group selection.
 * Returns the set of *labels* to show (matching line.name in the ECharts option).
 */
export function trendGroupLabels(
  group: TrendGroupKey,
  kpis: ResolvedCrossAssetKpi[],
): Set<string> | null {
  if (group === "all") return null; // null = show all
  const target = TREND_GROUPS.find((g) => g.key === group);
  if (!target) return null;
  const byKey = new Map(kpis.map((k) => [k.key, k]));
  const labels = new Set<string>();
  for (const key of target.kpiKeys) {
    const kpi = byKey.get(key);
    if (kpi) labels.add(kpi.label);
  }
  return labels;
}

/* ================================================================
 *  6. Volatility Clustering Alert
 * ================================================================ */

export type VolatilityAlert = {
  triggered: boolean;
  clusterCount: number; // how many assets have elevated vol
  totalAssets: number;
  /** Per-asset volatility details */
  assets: VolatilityAssetDetail[];
  severity: "normal" | "elevated" | "critical";
  headline: string;
};

export type VolatilityAssetDetail = {
  key: string;
  label: string;
  rollingStdDev: number;
  /** Ratio of recent vol to full-window vol: > 1.5 = elevated */
  volRatio: number;
  isElevated: boolean;
};

/**
 * Compute rolling standard deviation over the last `window` points.
 */
function rollingStdDev(values: number[], window: number): number {
  if (values.length < window) return 0;
  const slice = values.slice(-window);
  const mean = slice.reduce((s, v) => s + v, 0) / slice.length;
  const variance = slice.reduce((s, v) => s + (v - mean) ** 2, 0) / slice.length;
  return Math.sqrt(variance);
}

/**
 * Detect volatility clustering: when multiple assets simultaneously
 * show elevated volatility (recent window >> full window), it signals
 * systemic risk buildup.
 */
export function detectVolatilityClustering(
  kpis: ResolvedCrossAssetKpi[],
  recentWindow = 5,
  elevationThreshold = 1.5,
): VolatilityAlert {
  const eligible = kpis.filter((k) => isAssetLevelKpiKey(k.key) && k.sparkline.length >= 8);
  const assets: VolatilityAssetDetail[] = eligible.map((k) => {
    const fullVol = rollingStdDev(k.sparkline, k.sparkline.length);
    const recentVol = rollingStdDev(k.sparkline, recentWindow);
    const ratio = fullVol > 0 ? recentVol / fullVol : 0;
    return {
      key: k.key,
      label: k.label,
      rollingStdDev: recentVol,
      volRatio: ratio,
      isElevated: ratio > elevationThreshold,
    };
  });

  const elevatedCount = assets.filter((a) => a.isElevated).length;
  const total = assets.length;
  const clusterRatio = total > 0 ? elevatedCount / total : 0;

  let severity: VolatilityAlert["severity"] = "normal";
  let headline = "各资产波动率正常，暂无聚类信号。";

  if (clusterRatio >= 0.5) {
    severity = "critical";
    headline = `⚠️ 波动率聚类警告：${elevatedCount}/${total} 个资产近期波动率显著放大，注意系统性风险。`;
  } else if (elevatedCount >= 2) {
    severity = "elevated";
    headline = `${elevatedCount}/${total} 个资产波动率偏高，关注是否扩散。`;
  }

  return {
    triggered: severity !== "normal",
    clusterCount: elevatedCount,
    totalAssets: total,
    assets,
    severity,
    headline,
  };
}

/* ================================================================
 *  7. Equity-Bond Risk Premium (ERP)
 * ================================================================ */

export type EquityBondERP = {
  available: boolean;
  /** Earnings yield = 1/PE × 100 (%) */
  earningsYieldPct: number | null;
  /** Bond yield in % */
  bondYieldPct: number | null;
  /** ERP = earnings yield - bond yield (percentage points) */
  erpPct: number | null;
  /** Interpretation */
  verdict: "equity_cheap" | "equity_expensive" | "neutral" | "unavailable";
  verdictLabel: string;
  verdictDescription: string;
  verdictColor: string;
  verdictBg: string;
};

/**
 * Compute equity-bond risk premium from CSI300 PE and 10Y gov yield.
 * ERP = (1/PE × 100) − 10Y_yield
 * ERP > 3% → equity relatively cheap
 * ERP < 1% → equity relatively expensive
 */
export function computeEquityBondERP(kpis: ResolvedCrossAssetKpi[]): EquityBondERP {
  const byKey = new Map(kpis.map((k) => [k.key, k]));
  const peKpi = byKey.get("csi300_pe");
  const bondKpi = byKey.get("cn_gov_10y");

  const unavailable: EquityBondERP = {
    available: false,
    earningsYieldPct: null,
    bondYieldPct: null,
    erpPct: null,
    verdict: "unavailable",
    verdictLabel: "数据不足",
    verdictDescription: "缺少沪深300市盈率或10Y国债数据，无法计算股债性价比。",
    verdictColor: CA_PALETTE.erpUnavailable,
    verdictBg: CA_PALETTE.erpUnavailableBg,
  };

  if (!peKpi || !bondKpi) return unavailable;

  const pe = peKpi.sparkline.length > 0 ? peKpi.sparkline[peKpi.sparkline.length - 1] : null;
  const bondYield = bondKpi.sparkline.length > 0 ? bondKpi.sparkline[bondKpi.sparkline.length - 1] : null;

  if (pe == null || pe <= 0 || bondYield == null) return unavailable;

  const earningsYield = (1 / pe) * 100;
  const erp = earningsYield - bondYield;

  let verdict: EquityBondERP["verdict"];
  let verdictLabel: string;
  let verdictDescription: string;
  let verdictColor: string;
  let verdictBg: string;

  if (erp > 3) {
    verdict = "equity_cheap";
    verdictLabel = "股票偏便宜";
    verdictDescription = `ERP ${erp.toFixed(2)}% > 3%：盈利收益率显著高于无风险利率，股票相对债券有吸引力。`;
    verdictColor = CA_PALETTE.erpCheap;
    verdictBg = CA_PALETTE.erpCheapBg;
  } else if (erp < 1) {
    verdict = "equity_expensive";
    verdictLabel = "股票偏贵";
    verdictDescription = `ERP ${erp.toFixed(2)}% < 1%：盈利收益率接近无风险利率，股票估值偏高。`;
    verdictColor = CA_PALETTE.erpExpensive;
    verdictBg = CA_PALETTE.erpExpensiveBg;
  } else {
    verdict = "neutral";
    verdictLabel = "中性区间";
    verdictDescription = `ERP ${erp.toFixed(2)}%：盈利收益率适度高于无风险利率，股债性价比中性。`;
    verdictColor = CA_PALETTE.erpNeutral;
    verdictBg = CA_PALETTE.erpNeutralBg;
  }

  return {
    available: true,
    earningsYieldPct: earningsYield,
    bondYieldPct: bondYield,
    erpPct: erp,
    verdict,
    verdictLabel,
    verdictDescription,
    verdictColor,
    verdictBg,
  };
}

/* ================================================================
 *  8. Driver Attribution Waterfall
 * ================================================================ */

export type WaterfallBar = {
  key: string;
  label: string;
  value: number;
  cumulative: number;
  /** "factor" for individual bars, "total" for composite */
  kind: "factor" | "total";
  color: string;
};

type CompositeContribution = {
  component?: string;
  signed_contribution?: number;
};

const CONTRIBUTION_LABELS: Record<string, { key: string; label: string }> = {
  liquidity: { key: "liquidity", label: "流动性" },
  rate: { key: "rate", label: "海外利率" },
  rate_direction: { key: "rate", label: "海外利率" },
  growth: { key: "growth", label: "增长预期" },
  inflation: { key: "inflation", label: "通胀扰动" },
};

function waterfallColor(value: number, kind: "factor" | "total") {
  if (value > 0.05) return CA_PALETTE.waterfallUp;
  if (value < -0.05) return CA_PALETTE.waterfallDown;
  return kind === "total"
    ? CA_PALETTE.waterfallTotalNeutral
    : CA_PALETTE.waterfallFactorNeutral;
}

/**
 * Build waterfall chart data from backend-provided composite contributions.
 */
export function buildDriverWaterfall(env: {
  composite_contributions?: CompositeContribution[];
  composite_score?: number;
}): WaterfallBar[] {
  const bars: WaterfallBar[] = [];
  let cumulative = 0;

  for (const contribution of env.composite_contributions ?? []) {
    const value = contribution.signed_contribution;
    if (typeof value !== "number" || !Number.isFinite(value)) continue;
    const component = String(contribution.component ?? "").trim();
    const labelConfig = CONTRIBUTION_LABELS[component] ?? { key: component || `factor-${bars.length + 1}`, label: component || "因子" };
    cumulative += value;
    bars.push({
      key: labelConfig.key,
      label: labelConfig.label,
      value,
      cumulative,
      kind: "factor",
      color: waterfallColor(value, "factor"),
    });
  }

  if (typeof env.composite_score === "number" && Number.isFinite(env.composite_score)) {
    bars.push({
      key: "composite",
      label: "综合",
      value: env.composite_score,
      cumulative: env.composite_score,
      kind: "total",
      color: waterfallColor(env.composite_score, "total"),
    });
  }

  return bars;
}
