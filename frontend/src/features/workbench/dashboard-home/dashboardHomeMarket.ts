import type { ChoiceMacroLatestPoint } from "../../../api/contracts";
import {
  formatChoiceMacroDelta,
  formatChoiceMacroValue,
} from "../../../utils/choiceMacroFormat";

const MARKET_TICKER_PRIORITY: ReadonlyArray<{
  ids: readonly string[];
  label: string;
}> = [
  { ids: ["CA.CN_GOV_10Y", "E1000180", "EMM00166466"], label: "10年国债" },
  { ids: ["CA.DR007", "M002", "EMM00167613"], label: "DR007" },
  { ids: ["EM1", "CA.CN_US_SPREAD"], label: "1Y-10Y利差" },
  { ids: ["CA.US_GOV_10Y", "EMG00001310", "E1003238"], label: "美债10Y" },
  { ids: ["CA.USDCNY", "EMM00058124"], label: "人民币汇率" },
  { ids: ["CA.BRENT"], label: "原油 Brent" },
  { ids: ["CA.CSI300"], label: "沪深300" },
  { ids: ["CN_CREDIT_AAA_1Y", "S0059650", "EMM00166655"], label: "信用利差 中短票AAA" },
];

export type HomeMarketTicker = {
  id: string;
  label: string;
  value: string;
  delta: string;
  deltaTone: "up" | "down" | "flat" | "muted";
  sparkline: readonly number[];
};

function changeTone(value: number | null | undefined): HomeMarketTicker["deltaTone"] {
  if (value == null || Number.isNaN(value)) {
    return "flat";
  }
  if (value > 0) {
    return "up";
  }
  if (value < 0) {
    return "down";
  }
  return "flat";
}

function sparklineFromPoint(point: ChoiceMacroLatestPoint): readonly number[] {
  const base = point.value_numeric;
  const change = point.latest_change ?? 0;
  return Array.from({ length: 8 }, (_, index) => {
    const t = index / 7;
    return base - change * (1 - t) + Math.sin(index * 0.9) * Math.abs(change) * 0.15;
  });
}

function pickMarketPoints(points: readonly ChoiceMacroLatestPoint[]): ChoiceMacroLatestPoint[] {
  const candidates = points.filter((point) => (point.refresh_tier ?? "stable") !== "isolated");
  const selected: ChoiceMacroLatestPoint[] = [];
  const seen = new Set<string>();

  for (const item of MARKET_TICKER_PRIORITY) {
    const match = item.ids
      .map((id) => candidates.find((point) => point.series_id === id))
      .find((point): point is ChoiceMacroLatestPoint => Boolean(point));
    if (match && !seen.has(match.series_id)) {
      selected.push({ ...match, series_name: item.label });
      seen.add(match.series_id);
    }
  }

  for (const point of candidates) {
    if (seen.has(point.series_id)) {
      continue;
    }
    selected.push(point);
    seen.add(point.series_id);
    if (selected.length >= MARKET_TICKER_PRIORITY.length) {
      break;
    }
  }

  return selected.slice(0, MARKET_TICKER_PRIORITY.length);
}

export function mapMarketTape(
  points: readonly ChoiceMacroLatestPoint[] | null | undefined,
): HomeMarketTicker[] {
  return pickMarketPoints(points ?? []).map((point) => {
    const label =
      MARKET_TICKER_PRIORITY.find((item) => item.ids.includes(point.series_id))?.label ??
      point.series_name ??
      point.series_id;
    return {
      id: point.series_id,
      label,
      value: formatChoiceMacroValue(point, { spaceBeforeUnit: false, emptyDisplay: "—" }),
      delta: formatChoiceMacroDelta(point, { spaceBeforeUnit: false, emptyDisplay: "—" }),
      deltaTone: changeTone(point.latest_change),
      sparkline: sparklineFromPoint(point),
    };
  });
}
