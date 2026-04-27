import type { ResearchCalendarEvent } from "../api/contracts";
import type { CalendarItem } from "../components/CalendarList";

const KIND_ZH: Record<ResearchCalendarEvent["kind"], string> = {
  macro: "宏观",
  supply: "供给面",
  auction: "发行/招标",
  internal: "内部",
};

/** `DashboardHubCalendarItem` / task strip uses this kind; list rows use `note`/labels instead. */
export function researchCalendarEventHubKind(
  event: ResearchCalendarEvent,
): "macro" | "internal" | "supply" {
  return event.kind === "macro" ? "macro" : event.kind === "internal" ? "internal" : "supply";
}

/** Maps API-shaped research calendar rows to hub/calendar list items (display only). */
export function mapResearchCalendarEventToCalendarItem(event: ResearchCalendarEvent): CalendarItem {
  const raw = event.date.trim();
  const date =
    raw.length === 0 ? "暂无" : raw.length >= 10 ? raw.slice(5, 10) : raw;
  return {
    date,
    event: event.title,
    issuerLabel: event.issuer?.trim() || undefined,
    amount: event.amount_label ?? undefined,
    level: event.severity,
    note: event.note?.trim() || KIND_ZH[event.kind],
    sourceUrl: event.source_url?.trim() || undefined,
    sourceLabel: event.source_label?.trim() || undefined,
  };
}
