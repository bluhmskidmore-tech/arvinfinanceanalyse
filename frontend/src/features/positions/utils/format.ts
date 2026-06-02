/**
 * 金融展示：避免 Number 浮点参与金额/利率处理。
 * 后端返回 Decimal string，展示层用 BigInt 做十进制 half-up 舍入。
 */

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

export function formatAmountYi(amountYuan: string | null | undefined, decimals: number = 2): string {
  if (!amountYuan) return "-";
  const { value, scale } = decimalToIntegerAndScale(amountYuan);
  const yiScaled = divideRoundHalfUp(value * pow10(decimals), 100000000n * pow10(scale));
  const s = scaledBigIntToDecimalString(yiScaled, decimals, decimals);
  return `${s} 亿元`;
}

export function formatAmountWan(amountYuan: string | null | undefined, decimals: number = 2): string {
  if (!amountYuan) return "-";
  const { value, scale } = decimalToIntegerAndScale(amountYuan);
  const wanScaled = divideRoundHalfUp(value * pow10(decimals), 10000n * pow10(scale));
  const s = scaledBigIntToDecimalString(wanScaled, decimals, decimals);
  return `${s} 万元`;
}

/** 利率小数（如 0.0255）→ 百分比展示（2.55%） */
export function formatRatePercent(rateDecimal: string | null | undefined, decimals: number = 2): string {
  if (!rateDecimal) return "-";
  const { value, scale } = decimalToIntegerAndScale(rateDecimal);
  const pctScaled = divideRoundHalfUp(value * 100n * pow10(decimals), pow10(scale));
  const s = scaledBigIntToDecimalString(pctScaled, decimals, decimals);
  return `${s}%`;
}
