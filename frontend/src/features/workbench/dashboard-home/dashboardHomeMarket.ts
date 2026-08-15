import type { ChoiceMacroLatestPoint } from "../../../api/contracts";
import {
  formatChoiceMacroDelta,
  formatChoiceMacroValue,
  formatChoiceMacroValueParts,
} from "../../../utils/choiceMacroFormat";
import { sparklineFromChoicePoint } from "../module-home/marketHomeRowEnrichment";

import { EM_DASH } from "../../../utils/format";
/**
 * 行情快讯行的展示口径说明（悬浮 title），补齐同页与报告日正式链路的口径互注。
 * EM1/CA.CN_US_SPREAD 为预计算「中美10年利差」序列（后端 series_name
 * 「中美国债利差(10Y)」，与外壳 ticker、债券分析宏观条同一映射）；此前误标
 * 「1Y-10Y利差」，数据集内并无 1Y-10Y 期限利差序列被顶掉。
 */
const MARKET_TICKER_PRIORITY: ReadonlyArray<{
  ids: readonly string[];
  label: string;
  title?: string;
}> = [
  {
    ids: ["CA.CN_GOV_10Y", "E1000180", "EMM00166466"],
    label: "10年国债",
    title: "实时行情快讯源（中债10Y 收益率），与国债收益率卡的报告日正式链路口径不同",
  },
  { ids: ["M002", "CA.DR007"], label: "DR007" },
  {
    ids: ["EM1", "CA.CN_US_SPREAD"],
    label: "中美10年利差",
    title: "中美10年利差 = 中债10Y − 美债10Y（bp，预计算序列）",
  },
  { ids: ["CA.US_GOV_10Y", "EMG00001310", "E1003238"], label: "美债10Y" },
  { ids: ["CA.USDCNY", "EMM00058124"], label: "人民币汇率" },
  { ids: ["CA.BRENT"], label: "原油 Brent" },
  { ids: ["CA.CSI300"], label: "沪深300" },
  { ids: ["CN_CREDIT_AAA_1Y", "S0059650", "EMM00166655"], label: "信用利差 中短票AAA" },
];

export type HomeMarketTicker = {
  id: string;
  label: string;
  /** 行级口径说明（悬浮 title），仅对需要口径互注的行下发。 */
  title?: string;
  value: string;
  delta: string;
  /** 变动完整串（含单位/±0 原文）；可见 delta 被简化时由 title 全量披露。 */
  deltaTitle?: string;
  deltaTone: "up" | "down" | "flat" | "muted";
  sparkline: readonly number[];
  tradeDate?: string;
  valueNumeric?: number;
  unit?: string;
  qualityFlag?: ChoiceMacroLatestPoint["quality_flag"];
  vendorName?: string | null;
  policyNote?: string | null;
  sourceVersion?: string;
};

function changeTone(value: number | null | undefined): HomeMarketTicker["deltaTone"] {
  if (value == null || Number.isNaN(value)) {
    return "flat";
  }
  if (value > 0) {
    return "up";
  }
  if (value < 0) {
    return "down";
  }
  return "flat";
}

const FLAT_DELTA_DISPLAY = "持平";

/** 格式化后为 ±0 的变动（如 "+0CNY/USD"）视为零变动，避免噪声符号与涨跌误着色。 */
function isZeroDeltaDisplay(delta: string): boolean {
  const numeric = delta.match(/-?\d+(?:\.\d+)?/);
  return numeric != null && Number.parseFloat(numeric[0]) === 0;
}

/**
 * 变动列展示（与外壳 ticker 同规则）：
 * - 文本单位（非 %/bp）已完整出现在数值列，变动值不重复单位串；
 * - 格式化后为 ±0 的变动显示「持平」并归中性色；
 * - 完整原文一律收进 deltaTitle 供行级 title 披露。
 */
function buildTickerDelta(
  point: ChoiceMacroLatestPoint,
): Pick<HomeMarketTicker, "delta" | "deltaTitle" | "deltaTone"> {
  const fullDelta = formatChoiceMacroDelta(point, {
    spaceBeforeUnit: false,
    emptyDisplay: EM_DASH,
  });
  if (point.latest_change == null) {
    return { delta: fullDelta, deltaTone: "flat" };
  }

  const { unit } = formatChoiceMacroValueParts(point, { spaceBeforeUnit: false });
  const delta = unit
    ? formatChoiceMacroDelta({ ...point, unit: "" }, { spaceBeforeUnit: false, emptyDisplay: EM_DASH })
    : fullDelta;

  if (isZeroDeltaDisplay(delta)) {
    return { delta: FLAT_DELTA_DISPLAY, deltaTitle: fullDelta, deltaTone: "flat" };
  }

  return {
    delta,
    deltaTitle: unit ? fullDelta : undefined,
    deltaTone: changeTone(point.latest_change),
  };
}

function pickMarketPoints(points: readonly ChoiceMacroLatestPoint[]): ChoiceMacroLatestPoint[] {
  const candidates = points.filter((point) => (point.refresh_tier ?? "stable") !== "isolated");
  const selected: ChoiceMacroLatestPoint[] = [];
  const seen = new Set<string>();

  for (const item of MARKET_TICKER_PRIORITY) {
    const match = item.ids
      .map((id) => candidates.find((point) => point.series_id === id))
      .find((point): point is ChoiceMacroLatestPoint => Boolean(point));
    if (match && !seen.has(match.series_id)) {
      selected.push({ ...match, series_name: item.label });
      seen.add(match.series_id);
    }
  }

  for (const point of candidates) {
    if (seen.has(point.series_id)) {
      continue;
    }
    selected.push(point);
    seen.add(point.series_id);
    if (selected.length >= MARKET_TICKER_PRIORITY.length) {
      break;
    }
  }

  return selected.slice(0, MARKET_TICKER_PRIORITY.length);
}

function mapMarketPoint(point: ChoiceMacroLatestPoint): HomeMarketTicker {
  const spec = MARKET_TICKER_PRIORITY.find((item) => item.ids.includes(point.series_id));
  const label = spec?.label ?? point.series_name ?? point.series_id;
  return {
    id: point.series_id,
    label,
    title: spec?.title,
    value: formatChoiceMacroValue(point, { spaceBeforeUnit: false, emptyDisplay: EM_DASH }),
    ...buildTickerDelta(point),
    sparkline: sparklineFromChoicePoint(point) ?? [],
    tradeDate: point.trade_date,
    valueNumeric: point.value_numeric,
    unit: point.unit,
    qualityFlag: point.quality_flag,
    vendorName: point.vendor_name,
    policyNote: point.policy_note,
    sourceVersion: point.source_version,
  };
}

export function mapMarketTape(
  points: readonly ChoiceMacroLatestPoint[] | null | undefined,
): HomeMarketTicker[] {
  return pickMarketPoints(points ?? []).map(mapMarketPoint);
}

export function mapMarketSeries(
  points: readonly ChoiceMacroLatestPoint[] | null | undefined,
): HomeMarketTicker[] {
  return (points ?? [])
    .filter((point) => (point.refresh_tier ?? "stable") !== "isolated")
    .map(mapMarketPoint);
}
