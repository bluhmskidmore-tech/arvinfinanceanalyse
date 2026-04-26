import type { ChoiceMacroLatestPoint, ChoiceMacroRecentPoint } from "../../../api/contracts";

export type CrossAssetKpiFormat = "percent" | "bp" | "index" | "fx" | "plain";

/** 与 `config/choice_macro_catalog.json` 对齐；`CA.*` 为治理后的 Tushare/公共补充源。 */
export type CrossAssetSingleSlot = {
  kind: "single";
  key: string;
  label: string;
  format: CrossAssetKpiFormat;
  tag: string;
  candidateSeriesIds: readonly string[];
};

export type CrossAssetSpreadSlot = {
  kind: "spread";
  key: string;
  /** 中债10Y − 美债10Y（美债序列入库后自动启用） */
  labelCnUs: string;
  /** 目录暂无美债时的国内代理：国开10Y − 国债10Y */
  labelDomesticFallback: string;
  tag: string;
  /** 发布方直接给出的中美10Y利差(bp)，优先于两收益率相减 */
  precomputedCnUsBpIds: readonly string[];
  cnGov10yIds: readonly string[];
  usGov10yIds: readonly string[];
  cdb10yIds: readonly string[];
};

export type CrossAssetKpiSlot = CrossAssetSingleSlot | CrossAssetSpreadSlot;

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
    labelDomesticFallback: "国开-国债10Y",
    tag: "利差",
    precomputedCnUsBpIds: ["EM1"],
    cnGov10yIds: ["E1000180", "EMM00166466", "CA.CN_GOV_10Y"],
    usGov10yIds: ["E1003238", "EMG00001310", "CA.US_GOV_10Y"],
    cdb10yIds: ["EMM00166502"],
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
    candidateSeriesIds: ["EMM01843735", "CA.CSI300"],
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
  /** 单序列时为该 id；利差时为合成键 */
  resolvedSeriesId: string;
  sourceKind: "choice" | "public" | "derived" | "missing";
  vendorName?: string | null;
  tradeDate: string | null;
  valueLabel: string;
  changeLabel: string;
  changeTone: "positive" | "negative" | "warning" | "default";
  sparkline: number[];
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

function latestTradeDate(points: Array<ChoiceMacroLatestPoint | undefined>) {
  const dates = points
    .map((point) => point?.trade_date)
    .filter((tradeDate): tradeDate is string => Boolean(tradeDate));
  return dates.length > 0 ? dates.sort((left, right) => right.localeCompare(left))[0] : null;
}

function formatPercent(n: number) {
  return `${n.toFixed(2)}%`;
}

function formatBpFromNumber(n: number) {
  const sign = n > 0 ? "+" : "";
  return `${sign}${n.toFixed(1)}bp`;
}

function formatFx(n: number) {
  return n.toFixed(4);
}

function sparklineFromPoint(point: ChoiceMacroLatestPoint | undefined): number[] {
  if (!point?.recent_points?.length) {
    return [];
  }
  const sorted = [...point.recent_points].sort((a, b) => a.trade_date.localeCompare(b.trade_date));
  return sorted.map((p) => p.value_numeric);
}

function mergeRecentByDate(
  left: ChoiceMacroRecentPoint[],
  right: ChoiceMacroRecentPoint[],
): { dates: string[]; leftV: number[]; rightV: number[] } {
  const rm = new Map(right.map((p) => [p.trade_date, p.value_numeric]));
  const sorted = [...left].sort((a, b) => a.trade_date.localeCompare(b.trade_date));
  const dates: string[] = [];
  const leftV: number[] = [];
  const rightV: number[] = [];
  for (const p of sorted) {
    const rv = rm.get(p.trade_date);
    if (rv != null) {
      dates.push(p.trade_date);
      leftV.push(p.value_numeric);
      rightV.push(rv);
    }
  }
  return { dates, leftV, rightV };
}

/** 两收益率(%)之差 → bp */
function toSpreadBp(minuendPct: number, subtrahendPct: number) {
  return (minuendPct - subtrahendPct) * 100;
}

function spreadSparklineFromPoints(
  hi: ChoiceMacroLatestPoint | undefined,
  lo: ChoiceMacroLatestPoint | undefined,
): number[] {
  if (!hi?.recent_points?.length || !lo?.recent_points?.length) {
    return [];
  }
  const { leftV, rightV } = mergeRecentByDate(hi.recent_points, lo.recent_points);
  return leftV.map((lv, i) => toSpreadBp(lv, rightV[i]));
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
    return "—";
  }
  if (format === "percent") {
    const sign = delta > 0 ? "+" : "";
    const bp = delta * 100;
    return `${sign}${bp.toFixed(1)}bp`;
  }
  if (format === "bp") {
    return formatBpFromNumber(delta);
  }
  if (format === "index" || format === "plain") {
    const sign = delta > 0 ? "+" : "";
    return `${sign}${delta.toFixed(2)}%`;
  }
  if (format === "fx") {
    const sign = delta > 0 ? "+" : "";
    return `${sign}${delta.toFixed(4)}`;
  }
  return String(delta);
}

function valueLabelForSlot(
  format: CrossAssetKpiFormat,
  value: number | undefined,
): string {
  if (value == null || Number.isNaN(value)) {
    return "—";
  }
  if (format === "percent") {
    return formatPercent(value);
  }
  if (format === "bp") {
    return `${value.toFixed(0)}bp`;
  }
  if (format === "fx") {
    return formatFx(value);
  }
  if (format === "index") {
    return value.toFixed(1);
  }
  return value.toLocaleString("zh-CN", { maximumFractionDigits: 2 });
}

function resolveSpreadSlot(
  slot: CrossAssetSpreadSlot,
  byId: Map<string, ChoiceMacroLatestPoint>,
): ResolvedCrossAssetKpi {
  const preBp = pickPoint(byId, slot.precomputedCnUsBpIds);
  if (preBp) {
    const sparkline = sparklineFromPoint(preBp);
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
      valueLabel: valueLabelForSlot("bp", preBp.value_numeric),
      changeLabel: changeLabelForSlot("bp", delta),
      changeTone: toneForChange("bp", delta),
      sparkline,
    };
  }

  const cn = pickPoint(byId, slot.cnGov10yIds);
  const us = pickPoint(byId, slot.usGov10yIds);
  const cdb = pickPoint(byId, slot.cdb10yIds);

  let label = slot.labelDomesticFallback;
  let hi: ChoiceMacroLatestPoint | undefined;
  let lo: ChoiceMacroLatestPoint | undefined;
  let resolvedId = `${slot.key}:domestic`;

  if (cn && us) {
    label = slot.labelCnUs;
    hi = cn;
    lo = us;
    resolvedId = `${slot.key}:cn_us`;
  } else if (cdb && cn) {
    label = slot.labelDomesticFallback;
    hi = cdb;
    lo = cn;
    resolvedId = `${slot.key}:cdb_gov`;
  }

  if (!hi || !lo) {
    return {
      key: slot.key,
      label: slot.labelCnUs,
      format: "bp",
      tag: slot.tag,
      resolvedSeriesId: `${slot.key}:missing`,
      sourceKind: "missing",
      vendorName: null,
      tradeDate: null,
      valueLabel: "—",
      changeLabel: "—",
      changeTone: "default",
      sparkline: [],
    };
  }

  const vBp = toSpreadBp(hi.value_numeric, lo.value_numeric);
  const sparkline = spreadSparklineFromPoints(hi, lo);
  const delta = spreadLatestChange(sparkline);

  return {
    key: slot.key,
    label,
    format: "bp",
    tag: slot.tag,
    resolvedSeriesId: resolvedId,
    sourceKind: sourceKindFromSeriesId(resolvedId),
    vendorName: null,
    tradeDate: latestTradeDate([hi, lo]),
    valueLabel: valueLabelForSlot("bp", vBp),
    changeLabel: changeLabelForSlot("bp", delta),
    changeTone: toneForChange("bp", delta),
    sparkline,
  };
}

function resolveSingleSlot(slot: CrossAssetSingleSlot, byId: Map<string, ChoiceMacroLatestPoint>): ResolvedCrossAssetKpi {
  const point = pickPoint(byId, slot.candidateSeriesIds);
  const id = point?.series_id ?? slot.candidateSeriesIds[0] ?? slot.key;
  const delta = point?.latest_change ?? null;
  let label = slot.key === "money_market_7d" && point?.series_id === "CA.DR007" ? "DR007" : slot.label;
  let tag = slot.tag;
  if (slot.key === "financial_conditions" && point?.series_id === "CA.CSI300") {
    label = "沪深300指数";
    tag = "权益风险偏好";
  }
  return {
    key: slot.key,
    label,
    format: slot.format,
    tag,
    resolvedSeriesId: id,
    sourceKind: sourceKindFromSeriesId(id),
    vendorName: point?.vendor_name,
    tradeDate: point?.trade_date ?? null,
    valueLabel: valueLabelForSlot(slot.format, point?.value_numeric),
    changeLabel: changeLabelForSlot(slot.format, delta),
    changeTone: toneForChange(slot.format, delta),
    sparkline: sparklineFromPoint(point),
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
      continue;
    }
    const cn = pickPoint(byId, slot.cnGov10yIds);
    const us = pickPoint(byId, slot.usGov10yIds);
    const cdb = pickPoint(byId, slot.cdb10yIds);
    if (cn && us) {
      dates.push(cn.trade_date, us.trade_date);
    } else if (cdb && cn) {
      dates.push(cdb.trade_date, cn.trade_date);
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
    if (preBp?.recent_points?.length) {
      const sorted = [...preBp.recent_points].sort((a, b) => a.trade_date.localeCompare(b.trade_date));
      lines.push({
        name: slot.labelCnUs,
        ...dedupeDateSeries(
          sorted.map((x) => x.trade_date),
          sorted.map((x) => x.value_numeric),
        ),
      });
      continue;
    }

    const cn = pickPoint(byId, slot.cnGov10yIds);
    const us = pickPoint(byId, slot.usGov10yIds);
    const cdb = pickPoint(byId, slot.cdb10yIds);
    let hi: ChoiceMacroLatestPoint | undefined;
    let lo: ChoiceMacroLatestPoint | undefined;
    let name = slot.labelDomesticFallback;
    if (cn && us) {
      hi = cn;
      lo = us;
      name = slot.labelCnUs;
    } else if (cdb && cn) {
      hi = cdb;
      lo = cn;
      name = slot.labelDomesticFallback;
    }
    if (!hi?.recent_points?.length || !lo?.recent_points?.length) {
      continue;
    }
    const { dates, leftV, rightV } = mergeRecentByDate(hi.recent_points, lo.recent_points);
    if (dates.length === 0) {
      continue;
    }
    lines.push({
      name,
      ...dedupeDateSeries(
        dates,
        leftV.map((lv, i) => toSpreadBp(lv, rightV[i])),
      ),
    });
  }

  return lines;
}
