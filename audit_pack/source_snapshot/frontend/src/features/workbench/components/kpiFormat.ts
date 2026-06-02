import type { KpiCardProps } from "./KpiCard";

export type KpiTone = NonNullable<KpiCardProps["tone"]>;

/** 解析卡片上常见的数值字符串（逗号、括号负数、破折号空值）。 */
export function parseDisplayNumber(value: string): number | null {
  const raw = value.trim();
  if (!raw || raw === "—" || raw === "-" || raw === "不可用") {
    return null;
  }
  let s = raw.replace(/,/g, "").replace(/，/g, "");
  let sign = 1;
  if (s.startsWith("(") && s.endsWith(")")) {
    sign = -1;
    s = s.slice(1, -1).trim();
  }
  const n = Number.parseFloat(s);
  if (!Number.isFinite(n)) {
    return null;
  }
  return sign * n;
}

export function toneFromSignedNumber(n: number | null): KpiTone {
  if (n == null || n === 0) {
    return "default";
  }
  return n > 0 ? "positive" : "negative";
}

export function toneFromSignedDisplayString(value: string): KpiTone {
  return toneFromSignedNumber(parseDisplayNumber(value));
}

/** 将 0–1 或 0–100 比例格式化为百分比展示（不含则按原样返回）。 */
export function formatRatioAsPercent(valueStr: string | undefined | null, emptyDisplay = "—"): string {
  if (valueStr === undefined || valueStr === null || valueStr === "") {
    return emptyDisplay;
  }
  const str = String(valueStr);
  if (str.includes("%")) {
    return str;
  }
  const n = Number.parseFloat(str.replace(/,/g, ""));
  if (!Number.isFinite(n)) {
    return str;
  }
  if (n >= 0 && n <= 1) {
    return `${(n * 100).toFixed(1)}%`;
  }
  if (n > 1 && n <= 100) {
    return `${n.toFixed(1)}%`;
  }
  return str;
}

export function pnlSurfaceQualityToTone(flag: string): KpiTone {
  if (flag === "warning") {
    return "warning";
  }
  if (flag === "error") {
    return "error";
  }
  return "default";
}

export type LimitTone = "ok" | "near" | "breach";

export function limitTone(value: number | null, limit: number): LimitTone {
  if (value === null || limit <= 0) {
    return "ok";
  }
  const ratio = value / limit;
  if (ratio >= 1) {
    return "breach";
  }
  if (ratio > 0.8) {
    return "near";
  }
  return "ok";
}

export function limitToneToKpi(l: LimitTone): KpiTone {
  if (l === "breach") {
    return "error";
  }
  if (l === "near") {
    return "warning";
  }
  return "default";
}
