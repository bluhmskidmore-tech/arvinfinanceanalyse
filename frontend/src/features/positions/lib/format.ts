/**
 * BigInt-based precise formatting for financial amounts and rates.
 * Never use parseFloat for amount calculations.
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

function decimalToScaledBigInt(v: string, scale: number): bigint {
  const { sign, intPart, fracPart } = splitDecimalString(v);
  const frac = fracPart.padEnd(scale, "0").slice(0, scale);
  const digits = `${intPart}${frac}`.replace(/^0+(?=\d)/, "");
  const bi = BigInt(digits.length > 0 ? digits : "0");
  return sign === -1 ? -bi : bi;
}

function scaledBigIntToDecimalString(x: bigint, scale: number, decimals: number): string {
  const sign = x < 0n ? "-" : "";
  const abs = x < 0n ? -x : x;
  const s = abs.toString().padStart(scale + 1, "0");
  const intRaw = s.slice(0, s.length - scale) || "0";
  const fracRaw = scale > 0 ? s.slice(s.length - scale) : "";
  const frac = (fracRaw || "").slice(0, Math.max(0, decimals)).padEnd(decimals, "0");
  return decimals > 0 ? `${sign}${groupInt(intRaw)}.${frac}` : `${sign}${groupInt(intRaw)}`;
}

/** 元 → 亿元 */
export function formatAmountYi(amountYuan: string | null | undefined, decimals = 2): string {
  if (!amountYuan) return "—";
  const scaled = decimalToScaledBigInt(amountYuan, 4);
  const yiScaled = (scaled * BigInt(10 ** decimals)) / 1000000000000n;
  return `${scaledBigIntToDecimalString(yiScaled, decimals, decimals)} 亿元`;
}

/** 元 → 万元 */
export function formatAmountWan(amountYuan: string | null | undefined, decimals = 2): string {
  if (!amountYuan) return "—";
  const scaled = decimalToScaledBigInt(amountYuan, 4);
  const wanScaled = (scaled * BigInt(10 ** decimals)) / 100000000n;
  return `${scaledBigIntToDecimalString(wanScaled, decimals, decimals)} 万元`;
}

/** 小数利率 → 百分比 (0.0255 → "2.55%") */
export function formatRatePercent(rateDecimal: string | null | undefined, decimals = 2): string {
  if (!rateDecimal) return "—";
  const scaled = decimalToScaledBigInt(rateDecimal, 6);
  const pctScaled = (scaled * 100n * BigInt(10 ** decimals)) / 1000000n;
  return `${scaledBigIntToDecimalString(pctScaled, decimals, decimals)}%`;
}
