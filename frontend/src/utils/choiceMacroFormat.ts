import type { ChoiceMacroLatestPoint } from "../api/contracts";

type ChoiceMacroFormatOptions = {
  spaceBeforeUnit?: boolean;
  emptyDisplay?: string;
};

function normalizeUnit(point: ChoiceMacroLatestPoint): string {
  const unit = point.unit?.trim() ?? "";
  if (!unit || unit.toLowerCase() === "unknown") {
    return "";
  }
  return unit;
}

function formatNumber(value: number, digits = 2): string {
  const fixed = value.toFixed(digits);
  return digits > 0 ? fixed.replace(/\.?0+$/, "") : fixed;
}

function formatBp(value: number, options: ChoiceMacroFormatOptions): string {
  const digits = Math.abs(value) < 1 ? 1 : 0;
  const suffix = options.spaceBeforeUnit === false ? "bp" : " bp";
  return `${formatNumber(value, digits)}${suffix}`;
}

export function formatChoiceMacroValue(
  point: ChoiceMacroLatestPoint,
  options: ChoiceMacroFormatOptions = {},
): string {
  const unit = normalizeUnit(point);
  if (unit === "%") {
    return `${formatNumber(point.value_numeric)}%`;
  }
  if (unit.toLowerCase() === "bp") {
    return formatBp(point.value_numeric, options);
  }
  if (!unit) {
    return formatNumber(point.value_numeric);
  }
  const joiner = options.spaceBeforeUnit === false ? "" : " ";
  return `${formatNumber(point.value_numeric)}${joiner}${unit}`;
}

export function formatChoiceMacroDelta(
  point: ChoiceMacroLatestPoint,
  options: ChoiceMacroFormatOptions = {},
): string {
  if (point.latest_change == null) {
    return options.emptyDisplay ?? "--";
  }

  const unit = normalizeUnit(point);
  if (unit === "%") {
    const deltaBp = point.latest_change * 100;
    const sign = deltaBp > 0 ? "+" : "";
    return `${sign}${formatBp(deltaBp, options)}`;
  }
  if (unit.toLowerCase() === "bp") {
    const sign = point.latest_change > 0 ? "+" : "";
    return `${sign}${formatBp(point.latest_change, options)}`;
  }
  if (!unit) {
    const sign = point.latest_change > 0 ? "+" : "";
    return `${sign}${formatNumber(point.latest_change)}`;
  }

  const sign = point.latest_change > 0 ? "+" : "";
  const joiner = options.spaceBeforeUnit === false ? "" : " ";
  return `${sign}${formatNumber(point.latest_change)}${joiner}${unit}`;
}
