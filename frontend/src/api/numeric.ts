/**
 * Runtime guards for the shared governed Numeric primitive.
 *
 * Paired with the TypeScript declaration in ``./contracts.ts`` and the backend
 * pydantic mirror ``backend/app/schemas/common_numeric.py``.
 */
import type { Numeric, NumericUnit } from "./contracts";
import { formatRawAsNumeric } from "../utils/format";

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
 * numeric string) into ``Numeric``. Already-valid ``Numeric`` passes through
 * unchanged; anything else is coerced via ``formatRawAsNumeric``.
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
  return formatRawAsNumeric({
    raw: decimalRaw(value),
    unit,
    sign_aware: signAware,
    precision,
  });
}

function decimalRaw(value: unknown): number | null {
  const parsed = parseNumericOrNull(value);
  if (parsed) {
    return parsed.raw;
  }
  if (value === null || value === undefined || value === "") {
    return null;
  }
  const raw = typeof value === "number" ? value : Number.parseFloat(String(value));
  return Number.isFinite(raw) ? raw : null;
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
