import type { CockpitWarningsPayload } from "../../../../api/contracts";
import type { HomeRiskCard, HomeWatchItem } from "../dashboardHomeView";

const LIABILITY_BASIS_NOTE =
  "负债预警（Phase 3 边界 · analytical basis，非正式口径）";

function isSameReportDate(expected: string, actual: string | null | undefined): boolean {
  return Boolean(expected && actual && expected.trim() === actual.trim());
}

export function mapCockpitWarningsToWatchlist(
  payload: CockpitWarningsPayload | null | undefined,
  reportDate: string,
): { items: readonly HomeWatchItem[]; hasData: boolean; basisNote: string | null } {
  if (!payload || !isSameReportDate(reportDate, payload.report_date)) {
    return { items: [], hasData: false, basisNote: null };
  }

  const items: HomeWatchItem[] = payload.watch_items.map((item) => ({
    id: item.id,
    label: item.label?.trim() || "—",
    count: item.level === "warning" ? "预警" : "关注",
  }));

  return {
    items,
    hasData: items.length > 0,
    basisNote: items.length > 0 ? LIABILITY_BASIS_NOTE : null,
  };
}

export function mapCockpitWarningsToRiskCards(
  payload: CockpitWarningsPayload | null | undefined,
  reportDate: string,
): { cards: readonly HomeRiskCard[]; hasData: boolean } {
  if (!payload || !isSameReportDate(reportDate, payload.report_date)) {
    return { cards: [], hasData: false };
  }

  const counts = { high: 0, medium: 0, low: 0 };
  for (const event of payload.alert_events) {
    counts[event.severity] += 1;
  }

  return {
    hasData: payload.alert_events.length > 0,
    cards: [
      { id: "high", label: "高风险", count: counts.high, tone: counts.high > 0 ? "up" : "muted" },
      { id: "mid", label: "中风险", count: counts.medium, tone: counts.medium > 0 ? "warn" : "muted" },
      { id: "low", label: "低风险", count: counts.low, tone: "muted" },
    ],
  };
}
