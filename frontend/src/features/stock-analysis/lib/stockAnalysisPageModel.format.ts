// Numeric formatting primitives shared by the stock-analysis page model.
import type { StockCandidateRawField } from "./stockAnalysisPageModel.types";

export function formatNumber(value: number | null | undefined, digits = 2) {
  if (value == null || !Number.isFinite(value)) {
    return "待补";
  }
  return value.toFixed(digits);
}

export function formatPercent(value: number | null | undefined, digits = 2) {
  if (value == null || !Number.isFinite(value)) {
    return "待补";
  }
  return `${value.toFixed(digits)}%`;
}

export function formatRatioAsPercent(value: number | null | undefined, digits = 0) {
  if (value == null || !Number.isFinite(value)) {
    return "待补";
  }
  return `${(value * 100).toFixed(digits)}%`;
}

/**
 * 数值来源的原始字段：`value` 保持原有展示字符串，`numeric` 保留后端原值供下游计算，
 * 避免"格式化成字符串 → 再正则反解析"的精度与单位丢失。
 */
export function numericRawField(
  key: string,
  label: string,
  raw: number | null | undefined,
  value: string,
): StockCandidateRawField {
  return {
    key,
    label,
    value,
    numeric: raw != null && Number.isFinite(raw) ? raw : null,
  };
}

export function finiteCount(value: unknown): number {
  return typeof value === "number" && Number.isFinite(value) ? value : 0;
}
