// 共享格式化层（单文件双轨，2026-08-12 登记）：
// - 治理 API（"Governed Numeric helpers" 分节起）：EM_DASH / formatYi / formatWan /
//   formatPercent / formatBp / formatNumeric / formatRawAsNumeric 及
//   *AsYiPlain / *AsWanPlain 系列（万元系 2026-08-13 增补，与亿元系对称）。
//   缺省值语义：null/undefined/NaN 一律显示 EM_DASH（"—"）；真零显示 "0.00"，
//   与缺失必须不同形；空串输入不得经 Number("") 变 0。语义由 format.test.ts 固化。
// - legacy fmt* 双轨（fmtYi/fmtBp/fmtPct/fmtChange/fmtRate/fmtCount）：
//   legacy 待收敛，新代码禁用。仅存量组件消费；迁移按页面逐个收口，不做批量替换。
import Decimal from "decimal.js";

const zhNumberFormat = new Intl.NumberFormat("zh-CN");

export function fmtYi(v: number): string {
  return `${zhNumberFormat.format(v)} 亿`;
}

export function fmtBp(v: number): string {
  return `${v.toFixed(1)} bp`;
}

export function fmtPct(v: number): string {
  return `${v.toFixed(2)}%`;
}

export function fmtChange(v: number): string {
  return v > 0 ? `+${zhNumberFormat.format(v)}` : zhNumberFormat.format(v);
}

export function fmtRate(v: number): string {
  return `${v.toFixed(2)}%`;
}

export function fmtCount(v: number, unit = "项"): string {
  return `${v} ${unit}`;
}

// ---- Governed Numeric helpers (Wave 1.3) ---------------------------------
// These coexist with the legacy `fmt*` helpers above; the legacy helpers
// remain for existing component consumers and are not deprecated yet.
//
// New adapter / selector code MUST use these Numeric-returning or
// null-tolerant helpers instead of the legacy `fmt*` ones.

import type { Numeric, NumericUnit } from "../api/contracts";

/**
 * Canonical missing-value placeholder (DESIGN.md §6).
 * All tables/metrics must render missing values as this em dash;
 * do not use "-" or "--" variants.
 */
export const EM_DASH = "—";

const NULL_DISPLAY = EM_DASH;

function signPrefix(raw: number | Decimal, signed: boolean): string {
  if (!signed) return "";
  const nonnegative = Decimal.isDecimal(raw) ? !raw.isNegative() || raw.isZero() : raw >= 0;
  return nonnegative ? "+" : "";
}

/**
 * Fixed-precision decimal string with zh-CN thousands grouping, aligned with
 * the ``*AsYiPlain``/``*AsWanPlain`` family below so 亿/万 displays never
 * disagree on grouping within the same file (see format.ts 千分位 note).
 */
function formatDecimalZh(value: Decimal.Value, precision: number, grouped = true): string {
  const [integer, fraction] = new Decimal(value).toFixed(precision, Decimal.ROUND_HALF_UP).split(".");
  const whole = grouped ? integer.replace(/\B(?=(\d{3})+(?!\d))/g, ",") : integer;
  return fraction === undefined ? whole : `${whole}.${fraction}`;
}

const EXACT_DECIMAL_TEXT_PATTERN = /^-?\d+(?:\.\d+)?$/;
// Amount helpers retain full finite exponent tokens; Numeric.raw_text stays plain decimal.
const AMOUNT_TOKEN_PATTERN = /^[+-]?(?:(?:\d+|\d{1,3}(?:,\d{3})+)(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?$/;

function decimalFromText(text: string): Decimal {
  const AmountDecimal = Decimal.clone({ precision: Math.max(64, text.length + 16) });
  return new AmountDecimal(text);
}

/** Full-token amounts only; grouped input must use complete thousands groups. */
function amountDecimalOrNull(raw: string | number | null | undefined): Decimal | null {
  if (raw === null || raw === undefined) return null;
  if (typeof raw === "number") return Number.isFinite(raw) ? new Decimal(raw) : null;
  const text = raw.trim();
  if (!AMOUNT_TOKEN_PATTERN.test(text)) return null;
  const amount = decimalFromText(text.replace(/,/g, ""));
  return amount.isFinite() && Number.isFinite(amount.toNumber()) ? amount : null;
}

/** Shared display-only scaling. The divisor expresses the existing unit convention. */
export function formatScaledAmount(
  raw: string | number | null | undefined, divisor: number, precision: number, grouped = true,
): string {
  const amount = amountDecimalOrNull(raw);
  return amount === null ? NULL_DISPLAY : formatDecimalZh(amount.div(divisor), precision, grouped);
}

/**
 * Null-tolerant yuan-in-yi formatter.
 * Converts ``raw`` (yuan) to a "XX.XX 亿" display string (zh-CN thousands
 * grouping) with optional leading ``+``.
 * ``null``/``undefined``/non-finite (``NaN``/``Infinity``) render as ``EM_DASH``.
 */
export function formatYi(raw: number | null | undefined, signed: boolean): string {
  if (raw === null || raw === undefined || !Number.isFinite(raw)) return NULL_DISPLAY;
  return `${signPrefix(raw, signed)}${formatScaledAmount(raw, 100_000_000, 2)} 亿`;
}

/**
 * Null-tolerant yuan-in-wan formatter（与 ``formatYi`` 对称的万元系入口）。
 * Converts ``raw`` (yuan) to a "XX.XX 万" display string (zh-CN thousands
 * grouping) with optional leading ``+``.
 * ``null``/``undefined``/非有限值 render as ``EM_DASH``.
 */
export function formatWan(raw: number | null | undefined, signed: boolean): string {
  if (raw === null || raw === undefined || !Number.isFinite(raw)) return NULL_DISPLAY;
  return `${signPrefix(raw, signed)}${formatScaledAmount(raw, 10_000, 2)} 万`;
}

/**
 * Null-tolerant ratio-as-percent formatter. ``raw`` is a decimal ratio
 * (e.g. 0.0255 → "+2.55%"). ``null``/``undefined``/非有限值 render as ``EM_DASH``.
 *
 * Tie rounding is half-up on the decimal the caller wrote, matching ``formatYi``
 * / ``formatWan`` and the feature-local decimal paths (positions, bond-dashboard).
 * ``Number.prototype.toFixed`` must not be used here: it rounds the exact binary
 * double, so an intended 0.015% rendered as 0.01% — measured 4823 of 20000 probed
 * ties landing one unit low.
 */
export function formatPercent(raw: number | null | undefined, signed: boolean): string {
  if (raw === null || raw === undefined || !Number.isFinite(raw)) return NULL_DISPLAY;
  const pct = new Decimal(raw).times(100);
  return `${signPrefix(raw, signed)}${pct.toFixed(2, Decimal.ROUND_HALF_UP)}%`;
}

/**
 * Null-tolerant basis-point formatter. ``raw`` is already in bp.
 * ``null``/``undefined``/非有限值 render as ``EM_DASH``.
 *
 * Tie rounding follows ``formatPercent`` (half-up on the written decimal);
 * ``toFixed`` rounded the binary double and rendered an intended 0.95 bp as 0.9 bp.
 */
export function formatBp(raw: number | null | undefined, signed: boolean): string {
  if (raw === null || raw === undefined || !Number.isFinite(raw)) return NULL_DISPLAY;
  const bp = new Decimal(raw);
  return `${signPrefix(raw, signed)}${bp.toFixed(1, Decimal.ROUND_HALF_UP)} bp`;
}

/**
 * Return the pre-baked display string on a ``Numeric``. Use this in components
 * so the render path never calls ``toFixed`` or ``/1e8`` locally.
 */
export function formatNumeric(n: Numeric): string {
  return n.display;
}

/**
 * Construct a ``Numeric`` from a raw value using standard unit-aware formatting.
 * Adapter-layer helper. Components must not call this directly.
 */
export function formatRawAsNumeric(opts: {
  raw: number | null | undefined;
  unit: NumericUnit;
  sign_aware: boolean;
  precision?: number;
  /** Authoritative accepted decimal text; raw remains approximate chart compatibility. */
  raw_text?: string | null;
}): Numeric {
  const { raw, unit, sign_aware } = opts;
  // NaN/Infinity 与 null/undefined 同视为缺失：display 走 EM_DASH，raw 归一为 null，
  // 避免非有限值泄漏进 Numeric.raw（JSON 序列化也无法表达 NaN/Infinity）。
  const rawNorm =
    raw === undefined || raw === null || !Number.isFinite(raw) ? null : raw;

  const rawText = rawNorm !== null && typeof opts.raw_text === "string" && EXACT_DECIMAL_TEXT_PATTERN.test(opts.raw_text)
    ? opts.raw_text : null;
  const exactDisplay = rawText === null ? null : decimalFromText(rawText);
  const displayRaw = exactDisplay ?? (rawNorm === null ? null : new Decimal(rawNorm));
  let display: string;
  let precision: number;

  if (rawNorm === null) {
    display = NULL_DISPLAY;
    precision = opts.precision ?? defaultPrecisionForUnit(unit);
  } else if (unit === "yuan") {
    display = `${signPrefix(displayRaw!, sign_aware)}${formatDecimalZh(displayRaw!.div(100_000_000), opts.precision ?? 2)} 亿`;
    precision = opts.precision ?? 2;
  } else if (unit === "yi") {
    display = `${signPrefix(displayRaw!, sign_aware)}${formatDecimalZh(displayRaw!, opts.precision ?? 2)} 亿`;
    precision = opts.precision ?? 2;
  } else if (unit === "pct") {
    display = `${signPrefix(displayRaw!, sign_aware)}${displayRaw!.times(100).toFixed(opts.precision ?? 2, Decimal.ROUND_HALF_UP)}%`;
    precision = opts.precision ?? 2;
  } else if (unit === "bp") {
    display = `${signPrefix(displayRaw!, sign_aware)}${displayRaw!.toFixed(opts.precision ?? 1, Decimal.ROUND_HALF_UP)} bp`;
    precision = opts.precision ?? 1;
  } else if (unit === "ratio") {
    display = `${signPrefix(displayRaw!, sign_aware)}${displayRaw!.toFixed(opts.precision ?? 2, Decimal.ROUND_HALF_UP)}`;
    precision = opts.precision ?? 2;
  } else if (unit === "years") {
    display = `${signPrefix(displayRaw!, sign_aware)}${displayRaw!.toFixed(opts.precision ?? 2, Decimal.ROUND_HALF_UP)}`;
    precision = opts.precision ?? 2;
  } else if (unit === "count") {
    // Exact integer counts must not lose digits; fractional counts retain legacy Intl behavior.
    display = exactDisplay?.isInteger() && !exactDisplay.isZero()
      ? formatDecimalZh(exactDisplay, 0) : zhNumberFormat.format(rawNorm);
    precision = 0;
  } else if (unit === "dv01") {
    display = formatDecimalZh(displayRaw!, 0);
    precision = 0;
  } else {
    // unreachable given NumericUnit Literal; fall back defensively
    display = String(rawNorm);
    precision = opts.precision ?? 2;
  }

  return {
    raw: rawNorm,
    ...(rawText === null ? {} : { raw_text: rawText }),
    unit,
    display,
    precision,
    sign_aware,
  };
}

function defaultPrecisionForUnit(unit: NumericUnit): number {
  if (unit === "count" || unit === "dv01") return 0;
  if (unit === "bp") return 1;
  return 2;
}

// ---- Formal balance sheet display (yuan / wan from API) -----------------------

const YUAN_PER_YI = 100_000_000;
const WAN_PER_YI = 10_000;

/**
 * 人民币元 → 亿元数值串（不含“亿”后缀），与 KpiCard 的 `unit="亿元"` 搭配。
 * `/ui/balance-analysis/overview`、summary、detail、basis_breakdown 的金额字段均为元。
 */
export function formatYuanAmountAsYiPlain(raw: string | number | null | undefined): string {
  return formatScaledAmount(raw, YUAN_PER_YI, 2);
}

const YUAN_PER_WAN = 10_000;

/**
 * 人民币元 → 万元数值串（不含“万”后缀），与 ``formatYuanAmountAsYiPlain`` 对称，
 * 供 KpiCard 等以 `unit="万元"` 展示的场景使用。
 */
export function formatYuanAmountAsWanPlain(raw: string | number | null | undefined): string {
  return formatScaledAmount(raw, YUAN_PER_WAN, 2);
}

/**
 * 万元 → 亿元数值串（不含“亿”后缀）。balance-analysis workbook 读模型中多数金额为万元（`_to_wanyuan`）。
 */
export function formatWanAmountAsYiPlain(raw: string | number | null | undefined): string {
  return formatScaledAmount(raw, WAN_PER_YI, 2);
}
