import { pctOrDash } from "../../../pageModel";
import { EM_DASH, formatWan, formatYi } from "../../../utils/format";

/**
 * 联动与情景区展示用符号数格式化（非正式损益口径）。
 * 空值文案为“不可用”且透传非数字字符串、支持 " bp" 等后缀，
 * 与 pageModel `signedFixedOrDash` 的 EM_DASH 语义不同，保留本地实现。
 */
export function formatSignedNumber(value: number | string | null | undefined, suffix = "") {
  if (value == null || value === "") {
    return "不可用";
  }
  const numericValue = typeof value === "number" ? value : Number.parseFloat(String(value));
  if (Number.isNaN(numericValue)) {
    return String(value);
  }
  const fixed = numericValue.toFixed(2);
  // toFixed 会把 (-0.005, 0] 区间格式化成 "-0.00"：格式化后为零的值不得带符号。
  if (Number(fixed) === 0) {
    return `0.00${suffix}`;
  }
  const sign = numericValue > 0 ? "+" : "";
  return `${sign}${fixed}${suffix}`;
}

/** 展示用百分比格式化（两位小数，缺失显示 EM_DASH；非正式口径）。 */
export function formatPct(value: number | null | undefined): string {
  return pctOrDash(value, 2);
}

/** 后端 generated_at 为 UTC ISO 串：转本地时区分钟级显示；无法解析原样透传，空值 EM_DASH。 */
export function formatGeneratedAtLocal(value: string | null | undefined): string {
  if (!value) {
    return EM_DASH;
  }
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) {
    return value;
  }
  const pad = (n: number) => String(n).padStart(2, "0");
  return `${parsed.getFullYear()}-${pad(parsed.getMonth() + 1)}-${pad(parsed.getDate())} ${pad(
    parsed.getHours(),
  )}:${pad(parsed.getMinutes())}`;
}

// ---- 宏观/外汇序列紧凑表展示口径 -------------------------------------------
// 共享层 utils/choiceMacroFormat 被 workbench ticker、利率 KPI/资金面表等跨页复用，
// 其「% 变动 ×100 显示 bp」的利率语义不能全局改动；紧凑表（宏观主题卡、外汇卡）
// 序列横跨增速/金额/价格等口径，需要本地口径：
// - 亿元/亿 单位且 |值|≥1e4 时换算为「万亿」两位小数（原值由调用方收进 title）；
// - 其余数值走 zh-CN 千分位（最多两位小数）；
// - % 序列变动按「百分点」显示（+0.8pct），bp 仅用于 unit 为 bp 的利差类序列；
// - 变动格式化后为零的一律不带符号（消除 "-0"/"+0"）。

/**
 * 展示用序列名：优先后端清洗短名 `display_name`，缺失/空白回退原始 `series_name`。
 * 仅用于展示；分组分类、排序、去重等业务逻辑必须继续使用 series_id / series_name。
 */
export function seriesDisplayName(point: {
  display_name?: string | null;
  series_name: string;
}): string {
  const display = point.display_name?.trim();
  return display || point.series_name;
}

const MARKET_SERIES_UNITLESS_UNITS = new Set(["index", "x"]);
const zhCompactNumber = new Intl.NumberFormat("zh-CN", { maximumFractionDigits: 2 });
const zhFixed2Number = new Intl.NumberFormat("zh-CN", {
  minimumFractionDigits: 2,
  maximumFractionDigits: 2,
});
const zhBpFineNumber = new Intl.NumberFormat("zh-CN", { maximumFractionDigits: 1 });
const zhBpCoarseNumber = new Intl.NumberFormat("zh-CN", { maximumFractionDigits: 0 });
/** 1 万亿 = 1e4 亿。 */
const YI_PER_WANYI = 10_000;

export type MarketSeriesDisplayPoint = {
  unit?: string | null;
  value_numeric: number | null;
  latest_change?: number | null;
};

function normalizeMarketSeriesUnit(unit: string | null | undefined): string {
  const trimmed = unit?.trim() ?? "";
  if (!trimmed || trimmed.toLowerCase() === "unknown") {
    return "";
  }
  if (MARKET_SERIES_UNITLESS_UNITS.has(trimmed.toLowerCase())) {
    return "";
  }
  return trimmed;
}

function isYiScaleUnit(unit: string): boolean {
  return unit === "亿元" || unit === "亿";
}

function formatBpMagnitude(value: number): string {
  return Math.abs(value) < 1 ? zhBpFineNumber.format(value) : zhBpCoarseNumber.format(value);
}

/**
 * 紧凑表「最新」列：返回数值与单位两段。%/bp/无单位并入数值段（与
 * choiceMacroFormat 同形），亿元级大数换算为「万亿」，其余千分位。
 */
export function formatMarketSeriesValueParts(point: MarketSeriesDisplayPoint): {
  value: string;
  unit: string;
} {
  const unit = normalizeMarketSeriesUnit(point.unit);
  const value = point.value_numeric;
  if (value == null || !Number.isFinite(value)) {
    return { value: EM_DASH, unit };
  }
  if (unit === "%") {
    return { value: `${zhCompactNumber.format(value)}%`, unit: "" };
  }
  if (unit.toLowerCase() === "bp") {
    return { value: `${formatBpMagnitude(value)} bp`, unit: "" };
  }
  if (!unit) {
    return { value: zhCompactNumber.format(value), unit: "" };
  }
  if (isYiScaleUnit(unit) && Math.abs(value) >= YI_PER_WANYI) {
    return { value: zhFixed2Number.format(value / YI_PER_WANYI), unit: `万${unit}` };
  }
  return { value: zhCompactNumber.format(value), unit };
}

/**
 * 紧凑表「变动」列：先按 |变动| 格式化数值体，格式化结果为零则不带符号。
 * % 序列显示百分点（pct），bp 序列保持 bp，亿元级大变动换算「万亿」。
 */
export function formatMarketSeriesDelta(
  point: MarketSeriesDisplayPoint,
  options: { emptyDisplay?: string } = {},
): string {
  const change = point.latest_change;
  if (point.value_numeric == null || !Number.isFinite(point.value_numeric) || change == null || !Number.isFinite(change)) {
    return options.emptyDisplay ?? EM_DASH;
  }
  const unit = normalizeMarketSeriesUnit(point.unit);
  const abs = Math.abs(change);
  let body: string;
  if (unit === "%") {
    body = `${zhCompactNumber.format(abs)}pct`;
  } else if (unit.toLowerCase() === "bp") {
    body = `${formatBpMagnitude(abs)} bp`;
  } else if (!unit) {
    body = zhCompactNumber.format(abs);
  } else if (isYiScaleUnit(unit) && abs >= YI_PER_WANYI) {
    body = `${zhFixed2Number.format(abs / YI_PER_WANYI)} 万${unit}`;
  } else {
    body = `${zhCompactNumber.format(abs)} ${unit}`;
  }
  const magnitude = Number.parseFloat(body.replace(/,/g, ""));
  if (!Number.isFinite(magnitude) || magnitude === 0) {
    return body;
  }
  return `${change < 0 ? "-" : "+"}${body}`;
}

/**
 * 金额（元）联动展示：|值|≥1e8 按亿、≥1e4 按万缩写，其余保留两位小数；
 * 空值“不可用”、非数字字符串透传，与 `formatSignedNumber` 同语义。原值由调用方收进 title。
 */
export function formatSignedCompactAmount(value: number | string | null | undefined): string {
  if (value == null || value === "") {
    return "不可用";
  }
  const numericValue = typeof value === "number" ? value : Number.parseFloat(String(value));
  if (Number.isNaN(numericValue)) {
    return String(value);
  }
  const abs = Math.abs(numericValue);
  if (abs >= 1e8) {
    return formatYi(numericValue, true);
  }
  if (abs >= 1e4) {
    return formatWan(numericValue, true);
  }
  const fixed = numericValue.toFixed(2);
  if (Number(fixed) === 0) {
    return "0.00";
  }
  const sign = numericValue > 0 ? "+" : "";
  return `${sign}${fixed}`;
}
