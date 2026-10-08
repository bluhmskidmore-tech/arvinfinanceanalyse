/**
 * Runtime guards for the shared governed Numeric primitive.
 *
 * Paired with the TypeScript declaration in ``./contracts.ts`` and the backend
 * pydantic mirror ``backend/app/schemas/common_numeric.py``.
 */
import Decimal from "decimal.js";
import type { Numeric, NumericUnit } from "./contracts";
import { formatRawAsNumeric } from "../utils/format";

// Full-string plain decimal only: no exponent, no leading/trailing whitespace,
// no bare "."/"-", no explicit "+" prefix, and at least one integer digit.
const DECIMAL_STRING_PATTERN = /^-?\d+(\.\d+)?$/;

const NUMERIC_UNITS: ReadonlySet<NumericUnit> = new Set<NumericUnit>([
  "yuan",
  "pct",
  "bp",
  "ratio",
  "years",
  "count",
  "dv01",
  "yi",
]);

/**
 * Narrow an unknown value to ``Numeric``. Pure structural check with no
 * coercion or default-filling: a value that is "almost Numeric" fails.
 */
export function isNumeric(value: unknown): value is Numeric {
  if (value === null || value === undefined) {
    return false;
  }
  if (typeof value !== "object") {
    return false;
  }
  const obj = value as Record<string, unknown>;

  if (!("raw" in obj) || !("unit" in obj) || !("display" in obj) || !("precision" in obj) || !("sign_aware" in obj)) {
    return false;
  }

  const raw = obj.raw;
  if (raw !== null && typeof raw !== "number") {
    return false;
  }
  if (typeof raw === "number" && !Number.isFinite(raw)) {
    return false;
  }

  if ("raw_text" in obj && obj.raw_text !== null && obj.raw_text !== undefined) {
    if (typeof obj.raw_text !== "string") {
      return false;
    }
    if (!DECIMAL_STRING_PATTERN.test(obj.raw_text)) {
      return false;
    }
    if (raw === null) {
      return false;
    }
  }

  if (typeof obj.unit !== "string" || !NUMERIC_UNITS.has(obj.unit as NumericUnit)) {
    return false;
  }

  if (typeof obj.display !== "string") {
    return false;
  }

  if (typeof obj.precision !== "number" || !Number.isInteger(obj.precision) || obj.precision < 0) {
    return false;
  }

  if (typeof obj.sign_aware !== "boolean") {
    return false;
  }

  return true;
}

/**
 * Parse an unknown value into ``Numeric`` or throw. Use at trust boundaries
 * (mock payloads, API responses) when you want loud failures.
 */
export function parseNumeric(value: unknown): Numeric {
  if (!isNumeric(value)) {
    throw new Error(
      `invalid Numeric: ${describeShape(value)}`,
    );
  }
  return value;
}

/**
 * Lenient version of ``parseNumeric`` for optional fields; returns ``null``
 * instead of throwing when the shape is wrong.
 */
export function parseNumericOrNull(value: unknown): Numeric | null {
  return isNumeric(value) ? value : null;
}

/**
 * Normalize an unknown backend value (governed ``Numeric``, plain number, or
 * numeric string) into ``Numeric``. Already-valid ``Numeric`` is preserved
 * exactly as received. Plain decimal strings are trimmed at this normalization
 * boundary; the compatibility ``raw`` remains approximate while ``raw_text``
 * preserves the authoritative decimal text. Everything else is coerced via
 * ``formatRawAsNumeric``.
 */
export function normalizeNumeric(
  value: unknown,
  unit: NumericUnit,
  signAware: boolean,
  precision?: number,
): Numeric {
  const parsed = parseNumericOrNull(value);
  if (parsed) {
    return parsed;
  }
  const normalizedInput = typeof value === "string" ? value.trim() : value;
  return formatRawAsNumeric({
    raw: numericChartNumberOrNull(normalizedInput),
    raw_text: numericExactTextOrNull(normalizedInput),
    unit,
    sign_aware: signAware,
    precision,
  });
}

export function numericExactTextOrNull(value: unknown): string | null {
  const parsed = parseNumericOrNull(value);
  if (parsed) {
    return parsed.raw_text && DECIMAL_STRING_PATTERN.test(parsed.raw_text) ? parsed.raw_text : null;
  }
  if (value === null || value === undefined || value === "") {
    return null;
  }
  if (typeof value !== "string") {
    return null;
  }
  return DECIMAL_STRING_PATTERN.test(value) ? value : null;
}

export function numericDecimalOrNull(value: unknown): Decimal | null {
  const exactText = numericExactTextOrNull(value);
  if (exactText !== null) {
    return exactDecimalFromText(exactText);
  }
  return null;
}

export function numericChartNumberOrNull(value: unknown): number | null {
  const decimal = numericDecimalOrNull(value);
  if (decimal !== null) {
    const chartNumber = decimal.toNumber();
    return Number.isFinite(chartNumber) ? chartNumber : null;
  }
  const parsed = parseNumericOrNull(value);
  if (parsed) {
    return parsed.raw !== null && Number.isFinite(parsed.raw) ? parsed.raw : null;
  }
  return typeof value === "number" && Number.isFinite(value) ? value : null;
}

function describeShape(value: unknown): string {
  if (value === null) return "null";
  if (value === undefined) return "undefined";
  if (typeof value !== "object") return typeof value;
  try {
    return JSON.stringify(value).slice(0, 200);
  } catch {
    return "[unserializable object]";
  }
}

const DECIMAL_CONSTRUCTOR_CACHE = new Map<number, typeof Decimal>();

function exactDecimalFromText(value: string): Decimal {
  const precision = Math.max(64, countDecimalDigits(value) + 16);
  let DecimalCtor = DECIMAL_CONSTRUCTOR_CACHE.get(precision);
  if (!DecimalCtor) {
    DecimalCtor = Decimal.clone({ precision });
    DECIMAL_CONSTRUCTOR_CACHE.set(precision, DecimalCtor);
  }
  return new DecimalCtor(value);
}

function countDecimalDigits(value: string): number {
  return value.replace("-", "").replace(".", "").length;
}
