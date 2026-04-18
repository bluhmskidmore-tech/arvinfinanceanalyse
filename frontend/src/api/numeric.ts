/**
 * Runtime guards for the shared governed Numeric primitive.
 *
 * Paired with the TypeScript declaration in ``./contracts.ts`` and the backend
 * pydantic mirror ``backend/app/schemas/common_numeric.py``.
 */
import type { Numeric, NumericUnit } from "./contracts";

const NUMERIC_UNITS: ReadonlySet<NumericUnit> = new Set<NumericUnit>([
  "yuan",
  "pct",
  "bp",
  "ratio",
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
