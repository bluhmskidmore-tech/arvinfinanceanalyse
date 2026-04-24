import type { ResearchCalendarEvent } from "../api/contracts";
import type { CalendarItem } from "../components/CalendarList";

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
    raw.length === 0 ? "n/a" : raw.length >= 10 ? raw.slice(5, 10) : raw;
  return {
    date,
    event: event.title,
    amount: event.amount_label ?? undefined,
    level: event.severity,
    note: event.note ?? event.kind,
  };
}
