import { EM_DASH } from "../../../utils/format";

/** 联动与情景区展示用符号数格式化（非正式损益口径）。 */
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
  if (value == null || Number.isNaN(value)) {
    return EM_DASH;
  }
  return `${value.toFixed(2)}%`;
}
