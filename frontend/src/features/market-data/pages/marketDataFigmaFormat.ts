import type { ChoiceMacroLatestPoint } from "../../../api/contracts";
import {
  formatChoiceMacroDelta,
  formatChoiceMacroValue,
} from "../../../utils/choiceMacroFormat";

function trimFixed(value: number, digits: number): string {
  return value.toFixed(digits).replace(/\.?0+$/, "");
}

function normalizedUnit(point: ChoiceMacroLatestPoint): string {
  return point.unit?.trim() ?? "";
}

function isFxFixing(point: ChoiceMacroLatestPoint): boolean {
  return point.series_id === "EMM00058124" || normalizedUnit(point) === "CNY/USD";
}

export function formatMarketDataFigmaValue(point: ChoiceMacroLatestPoint): string {
  const unit = normalizedUnit(point);
  if (isFxFixing(point)) {
    return unit ? `${point.value_numeric.toFixed(4)} ${unit}` : point.value_numeric.toFixed(4);
  }
  return formatChoiceMacroValue(point);
}

export function formatMarketDataFigmaDelta(
  point: ChoiceMacroLatestPoint,
  emptyDisplay = "—",
): string {
  if (point.latest_change == null) {
    return emptyDisplay;
  }

  const unit = normalizedUnit(point);
  if (isFxFixing(point)) {
    const sign = point.latest_change > 0 ? "+" : "";
    const formatted = `${sign}${point.latest_change.toFixed(4)}`;
    return unit ? `${formatted} ${unit}` : formatted;
  }
  if (unit === "%") {
    const deltaBp = point.latest_change * 100;
    const sign = deltaBp > 0 ? "+" : "";
    return `${sign}${trimFixed(deltaBp, 1)}bp`;
  }
  if (unit.toLowerCase() === "bp") {
    const sign = point.latest_change > 0 ? "+" : "";
    return `${sign}${trimFixed(point.latest_change, 1)}bp`;
  }
  return formatChoiceMacroDelta(point, {
    emptyDisplay,
  });
}
