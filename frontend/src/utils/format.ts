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

const NULL_DISPLAY = "—";

function signPrefix(raw: number, signed: boolean): string {
  if (!signed) return "";
  return raw >= 0 ? "+" : "";
}

/**
 * Null-tolerant yuan-in-yi formatter.
 * Converts ``raw`` (yuan) to a "XX.XX 亿" display string with optional leading ``+``.
 */
export function formatYi(raw: number | null | undefined, signed: boolean): string {
  if (raw === null || raw === undefined) return NULL_DISPLAY;
  const yi = raw / 100_000_000;
  return `${signPrefix(yi, signed)}${yi.toFixed(2)} 亿`;
}

/**
 * Null-tolerant ratio-as-percent formatter. ``raw`` is a decimal ratio
 * (e.g. 0.0255 → "+2.55%").
 */
export function formatPercent(raw: number | null | undefined, signed: boolean): string {
  if (raw === null || raw === undefined) return NULL_DISPLAY;
  const pct = raw * 100;
  return `${signPrefix(pct, signed)}${pct.toFixed(2)}%`;
}

/**
 * Null-tolerant basis-point formatter. ``raw`` is already in bp.
 */
export function formatBp(raw: number | null | undefined, signed: boolean): string {
  if (raw === null || raw === undefined) return NULL_DISPLAY;
  return `${signPrefix(raw, signed)}${raw.toFixed(1)} bp`;
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
}): Numeric {
  const { raw, unit, sign_aware } = opts;
  const rawNorm = raw === undefined || raw === null ? null : raw;

  let display: string;
  let precision: number;

  if (rawNorm === null) {
    display = NULL_DISPLAY;
    precision = opts.precision ?? defaultPrecisionForUnit(unit);
  } else if (unit === "yuan") {
    display = formatYi(rawNorm, sign_aware);
    precision = opts.precision ?? 2;
  } else if (unit === "yi") {
    display = `${signPrefix(rawNorm, sign_aware)}${rawNorm.toFixed(opts.precision ?? 2)} 亿`;
    precision = opts.precision ?? 2;
  } else if (unit === "pct") {
    display = formatPercentRaw(rawNorm, sign_aware, opts.precision ?? 2);
    precision = opts.precision ?? 2;
  } else if (unit === "bp") {
    display = `${signPrefix(rawNorm, sign_aware)}${rawNorm.toFixed(opts.precision ?? 1)} bp`;
    precision = opts.precision ?? 1;
  } else if (unit === "ratio") {
    display = `${signPrefix(rawNorm, sign_aware)}${rawNorm.toFixed(opts.precision ?? 2)}`;
    precision = opts.precision ?? 2;
  } else if (unit === "count") {
    display = zhNumberFormat.format(rawNorm);
    precision = 0;
  } else if (unit === "dv01") {
    display = zhNumberFormat.format(Math.round(rawNorm));
    precision = 0;
  } else {
    // unreachable given NumericUnit Literal; fall back defensively
    display = String(rawNorm);
    precision = opts.precision ?? 2;
  }

  return {
    raw: rawNorm,
    unit,
    display,
    precision,
    sign_aware,
  };
}

function formatPercentRaw(raw: number, signed: boolean, precision: number): string {
  // Note: ``formatPercent(raw, signed)`` uses fixed precision 2; this helper
  // lets ``formatRawAsNumeric`` honor caller-specified precision without
  // changing the public ``formatPercent`` signature.
  const pct = raw * 100;
  return `${signPrefix(pct, signed)}${pct.toFixed(precision)}%`;
}

function defaultPrecisionForUnit(unit: NumericUnit): number {
  if (unit === "count" || unit === "dv01") return 0;
  if (unit === "bp") return 1;
  return 2;
}
