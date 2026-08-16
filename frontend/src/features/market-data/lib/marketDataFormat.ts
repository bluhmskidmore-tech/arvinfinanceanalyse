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
  const sign = numericValue > 0 ? "+" : "";
  return `${sign}${numericValue.toFixed(2)}${suffix}`;
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
  const sign = numericValue > 0 ? "+" : "";
  return `${sign}${numericValue.toFixed(2)}`;
}
