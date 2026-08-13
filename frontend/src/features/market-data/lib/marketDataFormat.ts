import { pctOrDash } from "../../../pageModel";

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
  const sign = numericValue > 0 ? "+" : "";
  return `${sign}${numericValue.toFixed(2)}${suffix}`;
}

/** 展示用百分比格式化（两位小数，缺失显示 EM_DASH；非正式口径）。 */
export function formatPct(value: number | null | undefined): string {
  return pctOrDash(value, 2);
}
