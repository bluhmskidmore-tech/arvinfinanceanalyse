/**
 * 金融展示：避免 Number 浮点参与金额/利率处理。
 * 后端返回 Decimal string，展示层用 BigInt 做十进制 half-up 舍入。
 */

import { EM_DASH } from "../../../utils/format";

const GROUP = /\B(?=(\d{3})+(?!\d))/g;

function groupInt(s: string): string {
  return s.replace(GROUP, ",");
}

function splitDecimalString(v: string): { sign: 1 | -1; intPart: string; fracPart: string } {
  const s = (v || "").trim();
  const sign: 1 | -1 = s.startsWith("-") ? -1 : 1;
  const raw = s.startsWith("-") ? s.slice(1) : s;
  const [i, f] = raw.split(".");
  return { sign, intPart: (i && i.length > 0 ? i : "0").replace(/^0+(?=\d)/, ""), fracPart: f || "" };
}

function decimalToIntegerAndScale(v: string): { value: bigint; scale: number } {
  const { sign, intPart, fracPart } = splitDecimalString(v);
  const digits = `${intPart}${fracPart}`.replace(/^0+(?=\d)/, "");
  const value = BigInt(digits.length > 0 ? digits : "0");
  return { value: sign === -1 ? -value : value, scale: fracPart.length };
}

function pow10(scale: number): bigint {
  return 10n ** BigInt(Math.max(0, scale));
}

function divideRoundHalfUp(numerator: bigint, denominator: bigint): bigint {
  const negative = numerator < 0n;
  const abs = negative ? -numerator : numerator;
  const quotient = abs / denominator;
  const remainder = abs % denominator;
  const rounded = remainder * 2n >= denominator ? quotient + 1n : quotient;
  return negative ? -rounded : rounded;
}

export function decimalToScaledBigInt(v: string, scale: number): bigint {
  const { sign, intPart, fracPart } = splitDecimalString(v);
  const frac = fracPart.padEnd(scale, "0").slice(0, scale);
  const digits = `${intPart}${frac}`.replace(/^0+(?=\d)/, "");
  const bi = BigInt(digits.length > 0 ? digits : "0");
  return sign === -1 ? -bi : bi;
}

export function scaledBigIntToDecimalString(x: bigint, scale: number, decimals: number): string {
  const sign = x < 0n ? "-" : "";
  const abs = x < 0n ? -x : x;
  const s = abs.toString().padStart(scale + 1, "0");
  const intRaw = s.slice(0, s.length - scale) || "0";
  const fracRaw = scale > 0 ? s.slice(s.length - scale) : "";
  const frac = (fracRaw || "").slice(0, Math.max(0, decimals)).padEnd(decimals, "0");
  return decimals > 0 ? `${sign}${groupInt(intRaw)}.${frac}` : `${sign}${groupInt(intRaw)}`;
}

/** 元→亿元裸数（"1.15"，含千分位，不带单位）：单位收进表格列头时用。 */
export function formatAmountYiNumber(
  amountYuan: string | null | undefined,
  decimals: number = 2,
): string {
  if (!amountYuan) return EM_DASH;
  const { value, scale } = decimalToIntegerAndScale(amountYuan);
  const yiScaled = divideRoundHalfUp(value * pow10(decimals), 100000000n * pow10(scale));
  return scaledBigIntToDecimalString(yiScaled, decimals, decimals);
}

export function formatAmountYi(amountYuan: string | null | undefined, decimals: number = 2): string {
  if (!amountYuan) return EM_DASH;
  return `${formatAmountYiNumber(amountYuan, decimals)} 亿元`;
}

export function formatAmountWanYi(
  amountYuan: string | null | undefined,
  decimals: number = 2,
): string {
  if (!amountYuan) return EM_DASH;
  const { value, scale } = decimalToIntegerAndScale(amountYuan);
  const wanYiScaled = divideRoundHalfUp(value * pow10(decimals), 1000000000000n * pow10(scale));
  const s = scaledBigIntToDecimalString(wanYiScaled, decimals, decimals);
  return `${s} 万亿元`;
}

/** 金额 ≥1 万亿（1e12 元）切万亿单位，否则亿元：只给 KPI 大数读数用。 */
export function formatAmountYiAuto(amountYuan: string | null | undefined): string {
  if (!amountYuan) return EM_DASH;
  const { value, scale } = decimalToIntegerAndScale(amountYuan);
  const abs = value < 0n ? -value : value;
  return abs >= 1000000000000n * pow10(scale)
    ? formatAmountWanYi(amountYuan)
    : formatAmountYi(amountYuan);
}

export function formatAmountWan(amountYuan: string | null | undefined, decimals: number = 2): string {
  if (!amountYuan) return EM_DASH;
  const { value, scale } = decimalToIntegerAndScale(amountYuan);
  const wanScaled = divideRoundHalfUp(value * pow10(decimals), 10000n * pow10(scale));
  const s = scaledBigIntToDecimalString(wanScaled, decimals, decimals);
  return `${s} 万元`;
}

/** 利率小数（如 0.0255）→ 百分比展示（2.55%） */
export function formatRatePercent(rateDecimal: string | null | undefined, decimals: number = 2): string {
  if (!rateDecimal) return EM_DASH;
  const { value, scale } = decimalToIntegerAndScale(rateDecimal);
  const pctScaled = divideRoundHalfUp(value * 100n * pow10(decimals), pow10(scale));
  const s = scaledBigIntToDecimalString(pctScaled, decimals, decimals);
  return `${s}%`;
}

/** 已是百分数的字符串（如 "84.48287107"）→ 定精度展示（84.48%）；后端原始精度不直出。 */
export function formatPercentValue(percent: string | null | undefined, decimals: number = 2): string {
  if (!percent) return EM_DASH;
  const { value, scale } = decimalToIntegerAndScale(percent);
  const scaled = divideRoundHalfUp(value * pow10(decimals), pow10(scale));
  const s = scaledBigIntToDecimalString(scaled, decimals, decimals);
  return `${s}%`;
}
