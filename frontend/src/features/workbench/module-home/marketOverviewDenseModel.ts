import type { ChoiceMacroLatestPoint } from "../../../api/contracts";
import { EM_DASH } from "../../../utils/format";

export type DenseTapeTone = "up" | "down" | "warn" | "ok" | "muted";

export function compactNumber(value: number) {
  const maximumFractionDigits = Math.abs(value) < 10 ? 4 : 2;
  return value.toLocaleString("zh-CN", {
    maximumFractionDigits,
    minimumFractionDigits: 0,
  });
}

export const DENSE_UNIT_LABELS: Record<string, string> = {
  index: "指数",
  point: "点",
};

export function normalizeDenseUnit(unit: string | null | undefined) {
  const normalized = unit?.trim() ?? "";
  if (!normalized || normalized.toLowerCase() === "unknown") return "";
  return DENSE_UNIT_LABELS[normalized.toLowerCase()] ?? normalized;
}

export function denseUnitSuffix(unit: string | null | undefined) {
  const normalized = normalizeDenseUnit(unit);
  if (!normalized) return "";
  return /^(?:%|‰|bp|bps)$/i.test(normalized) ? normalized : ` ${normalized}`;
}

export function formatDenseValue(value: number | null, unit: string) {
  if (value == null || !Number.isFinite(value)) return EM_DASH;
  return `${compactNumber(value)}${denseUnitSuffix(unit)}`;
}

export function directionTone(value: number | null | undefined): DenseTapeTone {
  if (value == null || !Number.isFinite(value) || value === 0) return "muted";
  return value > 0 ? "up" : "down";
}

export function rateDirectionTone(value: number | null | undefined): DenseTapeTone {
  if (value == null || !Number.isFinite(value) || value === 0) return "muted";
  return value > 0 ? "warn" : "muted";
}

export function normalizeTapeDelta(delta: string) {
  if (delta === "无前值") return "未返回";
  if (/^[+-]?0(?:\.0+)?(?:%|bp|bps)?$/i.test(delta.trim())) return "持平";
  return delta;
}

export function formatSignedPointValue(point: ChoiceMacroLatestPoint) {
  if (!Number.isFinite(point.value_numeric)) return null;
  const sign = point.value_numeric > 0 ? "+" : "";
  return `${sign}${compactNumber(point.value_numeric)}${denseUnitSuffix(point.unit)}`;
}

const FRIENDLY_NEWS_TOPIC_LABELS: Readonly<Record<string, string>> = {
  "major news": "主要新闻",
  sina: "新浪",
  "tushare.major_news": "主要新闻",
  tushare_major: "主要新闻",
  "tushare.news.sina": "新浪",
  tushare_news: "新浪",
};

const RESEARCH_REPORT_TOPIC_PATTERN = /^tushare\.research_report(?:[._-]|$)/i;

export function formatDenseNewsTopicLabel(value: string) {
  const rawValue = value.trim() || "未分类";
  const friendly = FRIENDLY_NEWS_TOPIC_LABELS[rawValue.toLowerCase()];
  if (friendly) return friendly;
  if (RESEARCH_REPORT_TOPIC_PATTERN.test(rawValue)) return "研究报告";
  return rawValue;
}
