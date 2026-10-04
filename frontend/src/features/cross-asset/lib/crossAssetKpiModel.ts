import type { ChoiceMacroLatestPoint } from "../../../api/contracts";
import { EM_DASH, fixedOrDash, pctOrDash, signedFixedOrDash } from "../../../pageModel";

/** KPI 来源标注：预计算利差序列未下发时写入既有来源位。 */
export const PRECOMPUTED_SPREAD_MISSING_NOTE = "后端预计算序列缺失";

export type CrossAssetKpiFormat = "percent" | "bp" | "index" | "fx" | "plain";

/** 与 `config/choice_macro_catalog.json` 对齐；`CA.*` 为治理后的 Tushare/公共补充源。 */
export type CrossAssetSingleSlot = {
  kind: "single";
  key: string;
  label: string;
  format: CrossAssetKpiFormat;
  tag: string;
  displayUnit?: string;
  candidateSeriesIds: readonly string[];
};

export type CrossAssetSpreadSlot = {
  kind: "spread";
  key: string;
  /** 中美10Y 利差（仅消费后端预计算 bp 序列） */
  labelCnUs: string;
  tag: string;
  /**
   * 后端预计算中美10Y利差(bp)。
   * `EM1` 为 Choice 目录核心序列；`CA.CN_US_SPREAD` 为工作台 ticker 同口径公共补充预计算序列。
   * 缺失时 KPI 显示 EM_DASH，禁止前端用两条收益率相减重算。
   */
  precomputedCnUsBpIds: readonly string[];
};

export type CrossAssetKpiSlot = CrossAssetSingleSlot | CrossAssetSpreadSlot;

/** Zero-centered scores are evidence, not asset levels: no return, vol, correlation, or base-100 transforms. */
export function isAssetLevelKpiKey(key: string): boolean {
  return key !== "financial_conditions";
}

export const CROSS_ASSET_KPI_SLOTS: CrossAssetKpiSlot[] = [
  {
    kind: "single",
    key: "cn_gov_10y",
    label: "10Y国债",
    format: "percent",
    tag: "利率锚",
    candidateSeriesIds: ["E1000180", "EMM00166466", "CA.CN_GOV_10Y"],
  },
  {
    kind: "single",
    key: "us_gov_10y",
    label: "10Y美债",
    format: "percent",
    tag: "外部约束",
    candidateSeriesIds: ["E1003238", "EMG00001310", "CA.US_GOV_10Y"],
  },
  {
    kind: "spread",
    key: "gov_spread",
    labelCnUs: "中美10Y利差",
    tag: "利差",
    precomputedCnUsBpIds: ["EM1", "CA.CN_US_SPREAD"],
  },
  {
    kind: "single",
    key: "money_market_7d",
    label: "银拆(7D)",
    format: "percent",
    tag: "流动性",
    candidateSeriesIds: ["EMM00167613", "CA.DR007"],
  },
  {
    kind: "single",
    key: "financial_conditions",
    label: "金融条件指数",
    format: "plain",
    tag: "风险情绪",
    displayUnit: "z-score",
    candidateSeriesIds: ["EMM01843735"],
  },
  {
    kind: "single",
    key: "csi300",
    label: "沪深300指数",
    format: "index",
    tag: "权益风险偏好",
    displayUnit: "point",
    candidateSeriesIds: ["CA.CSI300"],
  },
  {
    kind: "single",
    key: "csi300_pe",
    label: "沪深300市盈率",
    format: "plain",
    tag: "估值",
    candidateSeriesIds: ["CA.CSI300_PE"],
  },
  {
    kind: "single",
    key: "mega_cap_weight",
    label: "沪深300前十大权重",
    format: "percent",
    tag: "大市值权重",
    candidateSeriesIds: ["CA.MEGA_CAP_WEIGHT"],
  },
  {
    kind: "single",
    key: "mega_cap_top5_weight",
    label: "沪深300前五大权重",
    format: "percent",
    tag: "大市值权重",
    candidateSeriesIds: ["CA.MEGA_CAP_TOP5_WEIGHT"],
  },
  {
    kind: "single",
    key: "brent",
    label: "布油",
    format: "plain",
    tag: "通胀预期",
    candidateSeriesIds: ["CA.BRENT"],
  },
  {
    kind: "single",
    key: "steel",
    label: "钢",
    format: "plain",
    tag: "内需",
    candidateSeriesIds: ["CA.STEEL"],
  },
  {
    kind: "single",
    key: "copper",
    label: "铜主力期货",
    format: "plain",
    tag: "有色",
    candidateSeriesIds: ["CA.COPPER"],
  },
  {
    kind: "single",
    key: "aluminum",
    label: "铝主力期货",
    format: "plain",
    tag: "有色",
    candidateSeriesIds: ["CA.ALUMINUM"],
  },
  {
    kind: "single",
    key: "usdcny",
    label: "USD/CNY",
    format: "fx",
    tag: "汇率",
    candidateSeriesIds: ["EMM00058124", "CA.USDCNY"],
  },
];

export type ResolvedCrossAssetKpi = {
  key: string;
  label: string;
  format: CrossAssetKpiFormat;
  tag: string;
  /** 单序列时为该 id；利差为预计算序列 id，缺失为 `gov_spread:missing` */
  resolvedSeriesId: string;
  sourceKind: "choice" | "public" | "derived" | "missing";
  vendorName?: string | null;
  tradeDate: string | null;
  unit: string | null;
  qualityFlag?: ChoiceMacroLatestPoint["quality_flag"];
  refreshTier?: ChoiceMacroLatestPoint["refresh_tier"];
  valueLabel: string;
  changeLabel: string;
  changeTone: "positive" | "negative" | "warning" | "default";
  sparkline: number[];
  /**
   * Date-bearing observations used by pairwise analytics.
   * Optional for compatibility with presentation-only fixtures; correlation
   * calculations must treat a missing value as unavailable, never positional.
   */
  sparklinePoints?: CrossAssetDatedValue[];
  /** 缺预计算序列等缺口说明，写入既有来源/说明标注位。 */
  missingNote?: string;
};

export type CrossAssetDatedValue = {
  tradeDate: string;
  value: number;
};

function pickPoint(
  byId: Map<string, ChoiceMacroLatestPoint>,
  candidates: readonly string[],
): ChoiceMacroLatestPoint | undefined {
  const ranked = candidates
    .map((id, priority) => {
      const point = byId.get(id);
      return point ? { point, priority } : null;
    })
    .filter((item): item is { point: ChoiceMacroLatestPoint; priority: number } => Boolean(item));
  const usable = ranked.filter((item) => item.point.quality_flag !== "stale");
  const pool = usable.length ? usable : ranked;
  return [...pool].sort((left, right) => {
    const dateOrder = right.point.trade_date.localeCompare(left.point.trade_date);
    return dateOrder || left.priority - right.priority;
  })[0]?.point;
}

function sourceKindFromSeriesId(seriesId: string): ResolvedCrossAssetKpi["sourceKind"] {
  if (seriesId.endsWith(":missing")) {
    return "missing";
  }
  if (seriesId.includes(":")) {
    return "derived";
  }
  if (/^(E100|EMM|EMG|EMI|EM\d)/.test(seriesId)) {
    return "choice";
  }
  if (seriesId.startsWith("CA.")) {
    return "public";
  }
  return "missing";
}

function sparklinePointsFromPoint(point: ChoiceMacroLatestPoint | undefined): CrossAssetDatedValue[] {
  if (!point?.recent_points?.length) {
    return [];
  }
  const sorted = [...point.recent_points].sort((a, b) => a.trade_date.localeCompare(b.trade_date));
  return sorted.map((p) => ({ tradeDate: p.trade_date, value: p.value_numeric }));
}

function spreadLatestChange(sparkline: number[]): number | null {
  if (sparkline.length < 2) {
    return null;
  }
  return sparkline[sparkline.length - 1] - sparkline[sparkline.length - 2];
}

function toneForChange(
  format: CrossAssetKpiFormat,
  delta: number | null | undefined,
): ResolvedCrossAssetKpi["changeTone"] {
  if (delta == null || Number.isNaN(delta)) {
    return "default";
  }
  if (format === "bp") {
    if (delta > 0.05) {
      return "negative";
    }
    if (delta < -0.05) {
      return "positive";
    }
    return "warning";
  }
  if (delta > 0) {
    return format === "percent" || format === "index" || format === "fx" || format === "plain"
      ? "positive"
      : "default";
  }
  if (delta < 0) {
    return format === "percent" || format === "index" || format === "fx" || format === "plain"
      ? "negative"
      : "default";
  }
  return "default";
}

function changeLabelForSlot(
  format: CrossAssetKpiFormat,
  delta: number | null | undefined,
): string {
  if (delta == null || Number.isNaN(delta)) {
    return EM_DASH;
  }
  if (format === "percent") {
    // 收益率日变动以 bp 展示；delta 与 delta*100 同号，"+" 边界（严格正）不变。
    return `${signedFixedOrDash(delta * 100, 1)}bp`;
  }
  if (format === "bp") {
    return `${signedFixedOrDash(delta, 1)}bp`;
  }
  if (format === "index") {
    const sign = delta > 0 ? "+" : "";
    return `${sign}${delta.toLocaleString("zh-CN", { maximumFractionDigits: 2 })}点`;
  }
  if (format === "plain") {
    const sign = delta > 0 ? "+" : "";
    return `${sign}${delta.toLocaleString("zh-CN", { maximumFractionDigits: 2 })}`;
  }
  if (format === "fx") {
    return signedFixedOrDash(delta, 4);
  }
  return String(delta);
}

function valueLabelForSlot(
  format: CrossAssetKpiFormat,
  value: number | undefined,
): string {
  if (value == null || Number.isNaN(value)) {
    return EM_DASH;
  }
  if (format === "percent") {
    return pctOrDash(value, 2);
  }
  if (format === "bp") {
    return `${value.toFixed(0)}bp`;
  }
  if (format === "fx") {
    return fixedOrDash(value, 4);
  }
  if (format === "index") {
    return `${value.toFixed(1)}点`;
  }
  return value.toLocaleString("zh-CN", { maximumFractionDigits: 2 });
}

function missingSpreadKpi(slot: CrossAssetSpreadSlot): ResolvedCrossAssetKpi {
  return {
    key: slot.key,
    label: slot.labelCnUs,
    format: "bp",
    tag: slot.tag,
    resolvedSeriesId: `${slot.key}:missing`,
    sourceKind: "missing",
    vendorName: null,
    tradeDate: null,
    unit: null,
    valueLabel: EM_DASH,
    changeLabel: EM_DASH,
    changeTone: "default",
    sparkline: [],
    sparklinePoints: [],
    missingNote: PRECOMPUTED_SPREAD_MISSING_NOTE,
  };
}

function resolveSpreadSlot(
  slot: CrossAssetSpreadSlot,
  byId: Map<string, ChoiceMacroLatestPoint>,
): ResolvedCrossAssetKpi {
  const preBp = pickPoint(byId, slot.precomputedCnUsBpIds);
  if (!preBp) {
    return missingSpreadKpi(slot);
  }
  const sparklinePoints = sparklinePointsFromPoint(preBp);
  const sparkline = sparklinePoints.map((point) => point.value);
  const delta = spreadLatestChange(sparkline);
  return {
    key: slot.key,
    label: slot.labelCnUs,
    format: "bp",
    tag: slot.tag,
    resolvedSeriesId: preBp.series_id,
    sourceKind: sourceKindFromSeriesId(preBp.series_id),
    vendorName: preBp.vendor_name,
    tradeDate: preBp.trade_date,
    unit: preBp.unit,
    valueLabel: valueLabelForSlot("bp", preBp.value_numeric),
    changeLabel: changeLabelForSlot("bp", delta),
    changeTone: toneForChange("bp", delta),
    sparkline,
    sparklinePoints,
  };
}

function resolveSingleSlot(slot: CrossAssetSingleSlot, byId: Map<string, ChoiceMacroLatestPoint>): ResolvedCrossAssetKpi {
  const point = pickPoint(byId, slot.candidateSeriesIds);
  const id = point?.series_id ?? slot.candidateSeriesIds[0] ?? slot.key;
  const delta = point?.latest_change ?? null;
  const label = slot.key === "money_market_7d" && point?.series_id === "CA.DR007" ? "DR007" : slot.label;
  const sparklinePoints = sparklinePointsFromPoint(point);
  return {
    key: slot.key,
    label,
    format: slot.format,
    tag: slot.tag,
    resolvedSeriesId: id,
    sourceKind: sourceKindFromSeriesId(id),
    vendorName: point?.vendor_name,
    tradeDate: point?.trade_date ?? null,
    unit: slot.displayUnit ?? point?.unit ?? null,
    qualityFlag: point?.quality_flag,
    refreshTier: point?.refresh_tier,
    valueLabel: valueLabelForSlot(slot.format, point?.value_numeric),
    changeLabel: changeLabelForSlot(slot.format, delta),
    changeTone: toneForChange(slot.format, delta),
    sparkline: sparklinePoints.map((sparklinePoint) => sparklinePoint.value),
    sparklinePoints,
  };
}

export function resolveCrossAssetKpis(series: ChoiceMacroLatestPoint[]): ResolvedCrossAssetKpi[] {
  const byId = new Map(series.map((p) => [p.series_id, p]));
  return CROSS_ASSET_KPI_SLOTS.map((slot) => {
    if (slot.kind === "spread") {
      return resolveSpreadSlot(slot, byId);
    }
    return resolveSingleSlot(slot, byId);
  });
}

export type CrossAssetTrendLine = { name: string; dates: string[]; values: number[] };

/** Same trade_date can appear more than once from upstream; keep last and enforce strictly increasing x. */
function dedupeDateSeries(dates: string[], values: number[]): Pick<CrossAssetTrendLine, "dates" | "values"> {
  const byDate = new Map<string, number>();
  for (let i = 0; i < dates.length; i += 1) {
    const d = dates[i];
    const v = values[i];
    if (typeof v !== "number" || Number.isNaN(v)) {
      continue;
    }
    byDate.set(d, v);
  }
  const order = [...byDate.keys()].sort((a, b) => a.localeCompare(b));
  return { dates: order, values: order.map((d) => byDate.get(d)!) };
}

export function maxCrossAssetHeadlineTradeDate(series: ChoiceMacroLatestPoint[]): string {
  const byId = new Map(series.map((p) => [p.series_id, p]));
  const dates: string[] = [];
  for (const slot of CROSS_ASSET_KPI_SLOTS) {
    if (slot.kind === "single") {
      const p = pickPoint(byId, slot.candidateSeriesIds);
      if (p) {
        dates.push(p.trade_date);
      }
      continue;
    }
    const preBp = pickPoint(byId, slot.precomputedCnUsBpIds);
    if (preBp) {
      dates.push(preBp.trade_date);
    }
  }
  if (dates.length === 0) {
    return "";
  }
  return dates.sort((a, b) => b.localeCompare(a))[0];
}

export function crossAssetTrendLines(series: ChoiceMacroLatestPoint[]): CrossAssetTrendLine[] {
  const byId = new Map(series.map((p) => [p.series_id, p]));
  const lines: CrossAssetTrendLine[] = [];

  for (const slot of CROSS_ASSET_KPI_SLOTS) {
    if (slot.kind === "single") {
      if (!isAssetLevelKpiKey(slot.key)) {
        continue;
      }
      const p = pickPoint(byId, slot.candidateSeriesIds);
      if (!p?.recent_points?.length) {
        continue;
      }
      const sorted = [...p.recent_points].sort((a, b) => a.trade_date.localeCompare(b.trade_date));
      lines.push({
        name: slot.label,
        ...dedupeDateSeries(
          sorted.map((x) => x.trade_date),
          sorted.map((x) => x.value_numeric),
        ),
      });
      continue;
    }

    const preBp = pickPoint(byId, slot.precomputedCnUsBpIds);
    if (!preBp?.recent_points?.length) {
      continue;
    }
    const sorted = [...preBp.recent_points].sort((a, b) => a.trade_date.localeCompare(b.trade_date));
    lines.push({
      name: slot.labelCnUs,
      ...dedupeDateSeries(
        sorted.map((x) => x.trade_date),
        sorted.map((x) => x.value_numeric),
      ),
    });
  }

  return lines;
}
